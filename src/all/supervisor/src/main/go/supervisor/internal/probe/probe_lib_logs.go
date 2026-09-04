package probe

import (
	"bytes"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"regexp"
	"sort"
	"strconv"
	"strings"
	"sync"
	"syscall"
	"time"

	"supervisor/internal/config"
	"supervisor/internal/metric"
	"supervisor/internal/scribe"
)

func init() {
	scribe.Attribute(scribe.SourceProbeLogs,
		metric.MetricHostFailedLogs)
}

type logSet struct {
	mutex     sync.Mutex
	roots     []string
	path      string
	file      *os.File
	boot      time.Time
	carry     []byte
	buffer    []byte
	records   []logRecord
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
	roots := []string{logBareRoot}
	if mount != "" {
		roots = []string{mount, logBareRoot}
	}
	created := &logSet{roots: roots, buffer: make([]byte, logBufferBytes)}
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

func (s *logSet) attempted() string {
	paths := make([]string, 0, len(s.roots))
	for _, root := range s.roots {
		paths = append(paths, filepath.Join(root, logDevicePath))
	}
	return strings.Join(paths, " ")
}

func (s *logSet) errorsWithin(window time.Duration) (int, bool) {
	censusStart := time.Now()
	s.mutex.Lock()
	defer s.mutex.Unlock()
	if !s.open() {
		return 0, false
	}
	drain := !s.drained
	s.consume()
	s.drained = true
	s.evict(config.NowIncludingSuspend().Add(-window))
	if drain {
		s.report(censusStart, window)
	}
	return len(s.records), true
}

func (s *logSet) report(censusStart time.Time, window time.Duration) {
	counted := s.census()
	if len(counted) == 0 {
		return
	}
	logger := scribe.Log(scribe.SourceProbeLogs, scribe.SubjectMetric(metric.MetricHostFailedLogs), scribe.ActionSample)
	logger.Debugf("examined", censusStart, "[%d] kernel errors already in the ring across [%d] distinct messages within window [%s], showing the most frequent [%d]",
		len(s.records), len(counted), window, min(len(counted), logCensusMax))
	for index, entry := range counted {
		if index >= logCensusMax {
			return
		}
		logger.Debugf("examined", censusStart, "[%4d] kernel errors logged [%s]", entry.count, entry.message)
	}
}

func (s *logSet) census() []logCount {
	counts := map[string]int{}
	for _, record := range s.records {
		counts[record.message]++
	}
	counted := make([]logCount, 0, len(counts))
	for message, count := range counts {
		counted = append(counted, logCount{message: message, count: count})
	}
	sort.Slice(counted, func(first, second int) bool {
		if counted[first].count != counted[second].count {
			return counted[first].count > counted[second].count
		}
		return counted[first].message < counted[second].message
	})
	return counted
}

func (s *logSet) leading() (string, int) {
	s.mutex.Lock()
	defer s.mutex.Unlock()
	counted := s.census()
	if len(counted) == 0 {
		return logNoMessage, 0
	}
	return counted[0].message, counted[0].count
}

func (s *logSet) open() bool {
	if s.opened {
		return s.available
	}
	s.opened = true
	var failures []string
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
		scribe.Log(scribe.SourceProbeLogs, scribe.SubjectMetric(metric.MetricHostFailedLogs), scribe.ActionSample).Infof("followed", time.Now(), "[%s] for kernel errors", path)
		return true
	}
	scribe.Log(scribe.SourceProbeLogs, scribe.SubjectMetric(metric.MetricHostFailedLogs), scribe.ActionSample).Warnf("noaccess", time.Now(), "[0] errors reported, kernel log %s, needs [CAP_SYSLOG] and device [%s]", strings.Join(failures, " and "), logDeviceNode)
	return false
}

func (s *logSet) consume() {
	shouts := 0
	for range logReadsMax {
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

type logRecord struct {
	stamp   time.Time
	message string
}

type logCount struct {
	message string
	count   int
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
		if len(s.records) >= logStampsMax {
			continue
		}
		clipped := strings.TrimSpace(message)
		if len(clipped) > logMessageMax {
			clipped = clipped[:logMessageMax-3] + "..."
		}
		s.records = append(s.records, logRecord{stamp: stamp, message: clipped})
		if s.drained && shouts < logShoutsMax {
			shouts++
			scribe.Log(scribe.SourceProbeLogs, scribe.SubjectMetric(metric.MetricHostFailedLogs), scribe.ActionSample).Warnf("observed", time.Now(), "[%s] kernel logged [%s]", stamp.Format(time.RFC3339), clipped)
		}
	}
}

func (s *logSet) evict(cutoff time.Time) {
	keep := 0
	for keep < len(s.records) && s.records[keep].stamp.Before(cutoff) {
		keep++
	}
	if keep > 0 {
		s.records = append(s.records[:0], s.records[keep:]...)
	}
}

func (s *logSet) close() {
	s.mutex.Lock()
	defer s.mutex.Unlock()
	if s.file != nil {
		_ = s.file.Close()
		s.file = nil
	}
	s.opened = false
	s.available = false
	s.drained = false
	s.records = nil
	s.carry = nil
}

func parseLogRecord(line string, boot time.Time) (time.Time, string, bool) {
	if line == "" || line[0] == ' ' || line[0] == '\t' {
		return time.Time{}, "", false
	}
	before, after, ok := strings.Cut(line, ";")
	if !ok {
		return time.Time{}, "", false
	}
	fields := strings.Split(before, ",")
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
	if !isLogError(priority, after) {
		return time.Time{}, "", false
	}
	return boot.Add(time.Duration(micros) * time.Microsecond), after, true
}

func isLogError(priority int, message string) bool {
	if logIgnoring(message) {
		return false
	}
	if priority&logLevelMask <= logLevelError {
		return true
	}
	return strings.Contains(strings.ToLower(message), logErrorText)
}

func logIgnoring(message string) bool {
	for _, pattern := range logIgnore {
		if pattern.MatchString(message) {
			return true
		}
	}
	return false
}

func bootTime(root string) time.Time {
	data, err := os.ReadFile(filepath.Join(root, logUptimePath))
	if err != nil {
		return config.NowIncludingSuspend()
	}
	fields := strings.Fields(string(data))
	if len(fields) == 0 {
		return config.NowIncludingSuspend()
	}
	seconds, err := strconv.ParseFloat(fields[0], 64)
	if err != nil {
		return config.NowIncludingSuspend()
	}
	return config.NowIncludingSuspend().Add(-time.Duration(seconds * float64(time.Second)))
}

const (
	logBareRoot    = "/"
	logDevicePath  = "dev/kmsg"
	logDeviceNode  = "/dev/kmsg"
	logUptimePath  = "proc/uptime"
	logErrorText   = "error"
	logLevelMask   = 7
	logLevelError  = 3
	logBufferBytes = 8192
	logReadsMax    = 4096
	logStampsMax   = 4096
	logShoutsMax   = 5
	logCensusMax   = 10
	logNoMessage   = "no message"
	logMessageMax  = 120
)

var (
	logIgnore []*regexp.Regexp

	logCache   = map[string]*logSet{}
	logCacheMu sync.RWMutex
)
