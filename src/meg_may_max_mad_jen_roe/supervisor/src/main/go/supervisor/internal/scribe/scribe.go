package scribe

import (
	"context"
	"fmt"
	"io"
	"log/slog"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"time"

	"gopkg.in/natefinch/lumberjack.v2"
)

const logDirUser = "/tmp/supervisor"
const logDirRoot = "/var/log/supervisor"

func EnableStdout(level slog.Level) {
	scribeLoggerMutex.Lock()
	defer scribeLoggerMutex.Unlock()
	scribeLoggerLevel = level
	scribeLoggerMode = "stdout"
	scribeLoggerInstance = slog.New(slog.NewTextHandler(os.Stdout, &slog.HandlerOptions{Level: level}))
	slog.SetDefault(scribeLoggerInstance)
}

func EnableFile(level slog.Level, cmd string, maxSizeMB, maxBackups, maxAgeDays int) error {
	file := fmt.Sprintf("%s-pid-%d.log", cmd, os.Getpid())
	dir := logDirUser
	if os.Geteuid() == 0 {
		dir = logDirRoot
	}
	if err := os.MkdirAll(dir, 0755); err != nil {
		return err
	}
	path := filepath.Join(dir, file)
	scribeLoggerMutex.Lock()
	defer scribeLoggerMutex.Unlock()
	scribeLoggerLevel = level
	scribeLoggerMode = "file"
	writer := &lumberjack.Logger{Filename: path, MaxSize: maxSizeMB, MaxBackups: maxBackups, MaxAge: maxAgeDays, Compress: true}
	scribeLoggerInstance = slog.New(slog.NewTextHandler(io.MultiWriter(writer), &slog.HandlerOptions{Level: level}))
	slog.SetDefault(scribeLoggerInstance)
	return nil
}

func Disable() {
	scribeLoggerMutex.Lock()
	defer scribeLoggerMutex.Unlock()
	scribeLoggerMode = "disabled"
	scribeLoggerInstance = slog.New(slog.NewTextHandler(io.Discard, nil))
	slog.SetDefault(scribeLoggerInstance)
}

func Level() slog.Level {
	scribeLoggerMutex.Lock()
	defer scribeLoggerMutex.Unlock()
	return scribeLoggerLevel
}

func Mode() string {
	scribeLoggerMutex.Lock()
	defer scribeLoggerMutex.Unlock()
	return scribeLoggerMode
}

func EnableBuffer(level slog.Level, capacity int) *LogBuffer {
	scribeLoggerMutex.Lock()
	defer scribeLoggerMutex.Unlock()
	scribeLoggerLevel = level
	scribeLoggerMode = "buffer"
	buf := &LogBuffer{lines: make([]LogLine, capacity)}
	scribeLoggerInstance = slog.New(&bufferHandler{level: level, buffer: buf})
	slog.SetDefault(scribeLoggerInstance)
	return buf
}

type LogLine struct {
	Time    time.Time
	Level   slog.Level
	Message string
}

type LogBuffer struct {
	mutex   sync.Mutex
	lines   []LogLine
	head    int
	count   int
	version uint64
}

func (b *LogBuffer) Push(line LogLine) {
	b.mutex.Lock()
	b.lines[b.head] = line
	b.head = (b.head + 1) % len(b.lines)
	if b.count < len(b.lines) {
		b.count++
	}
	b.version++
	b.mutex.Unlock()
}

func (b *LogBuffer) Tail(n int) []LogLine {
	b.mutex.Lock()
	defer b.mutex.Unlock()
	if b.count == 0 || n <= 0 {
		return nil
	}
	if n > b.count {
		n = b.count
	}
	result := make([]LogLine, n)
	start := (b.head - n + len(b.lines)) % len(b.lines)
	for i := range n {
		result[i] = b.lines[(start+i)%len(b.lines)]
	}
	return result
}

func (b *LogBuffer) Version() uint64 {
	b.mutex.Lock()
	defer b.mutex.Unlock()
	return b.version
}

type bufferHandler struct {
	level  slog.Level
	buffer *LogBuffer
}

func (h *bufferHandler) Enabled(_ context.Context, level slog.Level) bool {
	return level >= h.level
}

func (h *bufferHandler) Handle(_ context.Context, record slog.Record) error {
	var sb strings.Builder
	sb.WriteString(messagePadder.pad(record.Message))
	first := true
	record.Attrs(func(a slog.Attr) bool {
		sb.WriteByte(' ')
		if first {
			first = false
			sb.WriteString(scopePadder.pad(a.Key + "=" + a.Value.String()))
			return true
		}
		val := a.Value.String()
		if p, ok := padders[a.Key]; ok {
			val = p.pad(val)
		}
		sb.WriteString(a.Key)
		sb.WriteByte('=')
		sb.WriteString(val)
		return true
	})
	h.buffer.Push(LogLine{Time: record.Time, Level: record.Level, Message: sb.String()})
	return nil
}

func (h *bufferHandler) WithAttrs(_ []slog.Attr) slog.Handler { return h }
func (h *bufferHandler) WithGroup(_ string) slog.Handler      { return h }

type padder struct {
	mu    sync.Mutex
	width int
}

func newPadder(minWidth int) *padder {
	return &padder{width: minWidth}
}

func (p *padder) pad(s string) string {
	p.mu.Lock()
	if len(s) > p.width {
		p.width = len(s)
	}
	w := p.width
	p.mu.Unlock()
	if len(s) >= w {
		return s
	}
	return s + strings.Repeat(" ", w-len(s))
}

var messagePadder = newPadder(9)
var scopePadder = newPadder(18)

var padders = map[string]*padder{
	"phase":    newPadder(9),
	"duration": newPadder(8),
	"received": newPadder(8),
	"transmit": newPadder(8),
}

var (
	scribeLoggerMutex    sync.Mutex
	scribeLoggerLevel    slog.Level
	scribeLoggerMode     string
	scribeLoggerInstance *slog.Logger
)
