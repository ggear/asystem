package probe

import (
	"bytes"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"regexp"
	"strconv"
	"strings"
	"sync"
	"syscall"
	"time"

	"supervisor/internal/scribe"
)

type logSet struct {
	mu        sync.Mutex
	roots     []string
	path      string
	file      *os.File
	boot      time.Time
	carry     []byte
	buffer    []byte
	stamps    []time.Time
	opened    bool
	available bool
	drained   bool
}

func loadLogs(mount string) *logSet {
	logCacheMu.RLock()
	if cached, ok := logCache[mount]; ok {
		logCacheMu.RUnlock()
		return cached
	}
	logCacheMu.RUnlock()
	logCacheMu.Lock()
	defer logCacheMu.Unlock()
	if cached, ok := logCache[mount]; ok {
		return cached
	}
	created := &logSet{roots: logRoots(mount), buffer: make([]byte, logBufferBytes)}
	logCache[mount] = created
	return created
}

func resetLogs() {
	logCacheMu.Lock()
	defer logCacheMu.Unlock()
	for _, set := range logCache {
		set.close()
	}
	clear(logCache)
}

func (s *logSet) errorsWithin(window time.Duration) (int, bool) {
	s.mu.Lock()
	defer s.mu.Unlock()
	if !s.open() {
		return 0, false
	}
	s.consume()
	s.drained = true
	s.evict(time.Now().Add(-window))
	return len(s.stamps), true
}

func (s *logSet) open() bool {
	if s.opened {
		return s.available
	}
	s.opened = true
	failures := []string{}
	for _, root := range s.roots {
		path := filepath.Join(root, logDevicePath)
		file, err := os.OpenFile(path, os.O_RDONLY|syscall.O_NONBLOCK, 0)
		if err != nil {
			failures = append(failures, fmt.Sprintf("[%s] with [%v]", path, err))
			continue
		}
		s.path = path
		s.file = file
		s.boot = bootTime(root)
		s.available = true
		scribe.Probe("state", "host").Info("logs", time.Now(), "following [%s] for kernel errors", path)
		return true
	}
	scribe.Probe("state", "host").Warn("logs", time.Now(), "unreadable kernel log %s, reporting [0] errors, needs [CAP_SYSLOG] and device [%s]", strings.Join(failures, " and "), logDeviceNode)
	return false
}

func (s *logSet) consume() {
	shouts := 0
	for reads := 0; reads < logReadsMax; reads++ {
		count, err := s.read()
		if count > 0 {
			s.carry = append(s.carry, s.buffer[:count]...)
			shouts = s.scan(shouts)
			continue
		}
		if errors.Is(err, syscall.EINTR) || errors.Is(err, syscall.EPIPE) {
			continue
		}
		return
	}
}

func (s *logSet) read() (int, error) {
	raw, err := s.file.SyscallConn()
	if err != nil {
		return 0, err
	}
	count := 0
	var readErr error
	if err := raw.Read(func(fd uintptr) bool {
		count, readErr = syscall.Read(int(fd), s.buffer)
		return true
	}); err != nil {
		return 0, err
	}
	return count, readErr
}

func (s *logSet) scan(shouts int) int {
	for {
		end := bytes.IndexByte(s.carry, '\n')
		if end < 0 {
			return shouts
		}
		line := string(s.carry[:end])
		s.carry = s.carry[end+1:]
		stamp, message, ok := parseLogRecord(line, s.boot)
		if !ok {
			continue
		}
		if len(s.stamps) >= logStampsMax {
			continue
		}
		s.stamps = append(s.stamps, stamp)
		if s.drained && shouts < logShoutsMax {
			shouts++
			scribe.Probe("state", "host").Error("logs", time.Now(), "kernel [%s] logged [%s]", stamp.Format(time.RFC3339), clipLogMessage(message))
		}
	}
}

func (s *logSet) evict(cutoff time.Time) {
	keep := 0
	for keep < len(s.stamps) && s.stamps[keep].Before(cutoff) {
		keep++
	}
	if keep > 0 {
		s.stamps = append(s.stamps[:0], s.stamps[keep:]...)
	}
}

func (s *logSet) close() {
	s.mu.Lock()
	defer s.mu.Unlock()
	if s.file != nil {
		_ = s.file.Close()
		s.file = nil
	}
	s.opened = false
	s.available = false
	s.drained = false
	s.stamps = nil
	s.carry = nil
}

func parseLogRecord(line string, boot time.Time) (time.Time, string, bool) {
	if line == "" || line[0] == ' ' || line[0] == '\t' {
		return time.Time{}, "", false
	}
	split := strings.IndexByte(line, ';')
	if split < 0 {
		return time.Time{}, "", false
	}
	fields := strings.Split(line[:split], ",")
	if len(fields) < 3 {
		return time.Time{}, "", false
	}
	priority, err := strconv.Atoi(fields[0])
	if err != nil {
		return time.Time{}, "", false
	}
	micros, err := strconv.ParseInt(fields[2], 10, 64)
	if err != nil {
		return time.Time{}, "", false
	}
	message := line[split+1:]
	if !isLogError(priority, message) {
		return time.Time{}, "", false
	}
	return boot.Add(time.Duration(micros) * time.Microsecond), message, true
}

func isLogError(priority int, message string) bool {
	if matchedLog(logIgnore, message) {
		return false
	}
	if priority&logLevelMask <= logLevelError {
		return true
	}
	return strings.Contains(strings.ToLower(message), logErrorText)
}

func matchedLog(patterns []*regexp.Regexp, message string) bool {
	for _, pattern := range patterns {
		if pattern.MatchString(message) {
			return true
		}
	}
	return false
}

func compileLog(patterns string) []*regexp.Regexp {
	compiled := []*regexp.Regexp{}
	for _, pattern := range strings.Split(patterns, "\n") {
		pattern = strings.TrimSpace(pattern)
		if pattern == "" {
			continue
		}
		expression, err := regexp.Compile(pattern)
		if err != nil {
			continue
		}
		compiled = append(compiled, expression)
	}
	return compiled
}

func clipLogMessage(message string) string {
	trimmed := strings.TrimSpace(message)
	if len(trimmed) <= logMessageMax {
		return trimmed
	}
	return trimmed[:logMessageMax-3] + "..."
}

func bootTime(root string) time.Time {
	data, err := os.ReadFile(filepath.Join(root, logUptimePath))
	if err != nil {
		return time.Now()
	}
	fields := strings.Fields(string(data))
	if len(fields) == 0 {
		return time.Now()
	}
	seconds, err := strconv.ParseFloat(fields[0], 64)
	if err != nil {
		return time.Now()
	}
	return time.Now().Add(-time.Duration(seconds * float64(time.Second)))
}

func logRoots(mount string) []string {
	if mount == "" {
		return []string{logHostRoot}
	}
	return []string{mount, logHostRoot}
}

const logIgnorePatterns = `
`

const (
	logHostRoot        = "/"
	logDevicePath      = "dev/kmsg"
	logDeviceNode      = "/dev/kmsg"
	logUptimePath      = "proc/uptime"
	logErrorText       = "error"
	logLevelMask       = 7
	logLevelError      = 3
	logBufferBytes     = 8192
	logReadsMax        = 4096
	logStampsMax       = 4096
	logShoutsMax       = 5
	logMessageMax      = 120
	logErrorBudget     = 10.0
	logErrorPulseOfMax = 100.0 / logErrorBudget
)

var (
	logIgnore  = compileLog(logIgnorePatterns)
	logCache   = map[string]*logSet{}
	logCacheMu sync.RWMutex
)
