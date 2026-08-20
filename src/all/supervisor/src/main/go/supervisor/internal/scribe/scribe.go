package scribe

import (
	"context"
	"fmt"
	"io"
	"log/slog"
	"os"
	"path/filepath"
	"runtime"
	"slices"
	"strings"
	"sync"
	"time"

	"gopkg.in/natefinch/lumberjack.v2"
)

const (
	logDirUser    = "/tmp/supervisor"
	logDirUserMac = "Library/Logs/supervisor"
	logDirRoot    = "/var/log/supervisor"
	timeLayout    = "2006-01-02 15:04:05"
)

func EnableStdout(level slog.Level) {
	scribeLoggerMutex.Lock()
	defer scribeLoggerMutex.Unlock()
	scribeLoggerLevel = level
	scribeLoggerMode = "stdout"
	scribeLoggerInstance = slog.New(&streamHandler{level: level, writer: os.Stdout})
	slog.SetDefault(scribeLoggerInstance)
}

func EnableFile(level slog.Level, cmd string, maxSizeMB, maxBackups, maxAgeDays int) error {
	writer, err := fileWriter(cmd, maxSizeMB, maxBackups, maxAgeDays)
	if err != nil {
		return err
	}
	scribeLoggerMutex.Lock()
	defer scribeLoggerMutex.Unlock()
	scribeLoggerLevel = level
	scribeLoggerMode = "file"
	scribeLoggerInstance = slog.New(&streamHandler{level: level, writer: writer})
	slog.SetDefault(scribeLoggerInstance)
	return nil
}

func EnableStdoutAndFile(level slog.Level, cmd string, maxSizeMB, maxBackups, maxAgeDays int) error {
	writer, err := fileWriter(cmd, maxSizeMB, maxBackups, maxAgeDays)
	if err != nil {
		return err
	}
	scribeLoggerMutex.Lock()
	defer scribeLoggerMutex.Unlock()
	scribeLoggerLevel = level
	scribeLoggerMode = "stdout+file"
	multi := io.MultiWriter(os.Stdout, writer)
	scribeLoggerInstance = slog.New(&streamHandler{level: level, writer: multi})
	slog.SetDefault(scribeLoggerInstance)
	return nil
}

func Disable() {
	scribeLoggerMutex.Lock()
	defer scribeLoggerMutex.Unlock()
	scribeLoggerMode = "disabled"
	scribeLoggerInstance = slog.New(&streamHandler{level: slog.LevelError + 1, writer: io.Discard})
	slog.SetDefault(scribeLoggerInstance)
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

func EnableBufferAndFile(level slog.Level, cmd string, capacity, maxSizeMB, maxBackups, maxAgeDays int) (*LogBuffer, error) {
	writer, err := fileWriter(cmd, maxSizeMB, maxBackups, maxAgeDays)
	if err != nil {
		return nil, err
	}
	scribeLoggerMutex.Lock()
	defer scribeLoggerMutex.Unlock()
	scribeLoggerLevel = level
	scribeLoggerMode = "buffer+file"
	buf := &LogBuffer{lines: make([]LogLine, capacity)}
	scribeLoggerInstance = slog.New(&multiHandler{handlers: []slog.Handler{
		&bufferHandler{level: level, buffer: buf},
		&streamHandler{level: level, writer: writer},
	}})
	slog.SetDefault(scribeLoggerInstance)
	return buf, nil
}

func Engine(tag, name string) Logger {
	return Logger{tag: tag, key: "engine", name: name}
}

func Probe(tag, name string) Logger {
	return Logger{tag: tag, key: "probe", name: name}
}

type Logger struct {
	tag  string
	key  string
	name string
}

func (l Logger) Debug(phase string, started time.Time, detail string, args ...any) {
	l.log(slog.LevelDebug, phase, started, detail, args...)
}

func (l Logger) Info(phase string, started time.Time, detail string, args ...any) {
	l.log(slog.LevelInfo, phase, started, detail, args...)
}

func (l Logger) Warn(phase string, started time.Time, detail string, args ...any) {
	l.log(slog.LevelWarn, phase, started, detail, args...)
}

func (l Logger) Error(phase string, started time.Time, detail string, args ...any) {
	l.log(slog.LevelError, phase, started, detail, args...)
}

func (l Logger) log(level slog.Level, phase string, started time.Time, detail string, args ...any) {
	if len(args) > 0 {
		detail = fmt.Sprintf(detail, args...)
	}
	slog.Log(context.Background(), level, l.tag, l.key, l.name, keyPhase, phase, keyDuration, time.Since(started), keyDetail, detail)
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
	h.buffer.Push(LogLine{Time: record.Time, Level: record.Level, Message: format(record)})
	return nil
}

func (h *bufferHandler) WithAttrs(_ []slog.Attr) slog.Handler { return h }
func (h *bufferHandler) WithGroup(_ string) slog.Handler      { return h }

type multiHandler struct {
	handlers []slog.Handler
}

func (h *multiHandler) Enabled(ctx context.Context, level slog.Level) bool {
	for _, handler := range h.handlers {
		if handler.Enabled(ctx, level) {
			return true
		}
	}
	return false
}

func (h *multiHandler) Handle(ctx context.Context, record slog.Record) error {
	var failed error
	for _, handler := range h.handlers {
		if !handler.Enabled(ctx, record.Level) {
			continue
		}
		if err := handler.Handle(ctx, record.Clone()); err != nil && failed == nil {
			failed = err
		}
	}
	return failed
}

func (h *multiHandler) WithAttrs(_ []slog.Attr) slog.Handler { return h }
func (h *multiHandler) WithGroup(_ string) slog.Handler      { return h }

type streamHandler struct {
	level  slog.Level
	writer io.Writer
	mutex  sync.Mutex
}

func (h *streamHandler) Enabled(_ context.Context, level slog.Level) bool {
	return level >= h.level
}

func (h *streamHandler) Handle(_ context.Context, record slog.Record) error {
	line := fmt.Sprintf("%s %-5s %s\n", record.Time.Format(timeLayout), record.Level.String(), format(record))
	h.mutex.Lock()
	defer h.mutex.Unlock()
	_, err := io.WriteString(h.writer, line)
	return err
}

func (h *streamHandler) WithAttrs(_ []slog.Attr) slog.Handler { return h }
func (h *streamHandler) WithGroup(_ string) slog.Handler      { return h }

func format(record slog.Record) string {
	columns := make([]string, len(columnWidths))
	detail := ""
	record.Attrs(func(a slog.Attr) bool {
		switch {
		case a.Key == keyDetail:
			detail = a.Value.String()
		case a.Key == keyDuration:
			columns[columnDuration] = duration(a.Value)
		case a.Key == keyPhase:
			columns[columnPhase] = a.Key + "=" + a.Value.String()
		case slices.Contains(keysEngine, a.Key):
			columns[columnEngine] = a.Key + "=" + a.Value.String()
		}
		return true
	})
	var builder strings.Builder
	builder.WriteString(pad(record.Message, widthTag))
	for index, width := range columnWidths {
		builder.WriteByte(' ')
		builder.WriteString(pad(columns[index], width))
	}
	if detail != "" {
		builder.WriteString(" " + keyDetail + "=")
		builder.WriteString(detail)
	}
	return strings.TrimRight(builder.String(), " ")
}

func duration(value slog.Value) string {
	text := value.String()
	if value.Kind() == slog.KindDuration {
		text = fmt.Sprintf("%dms", value.Duration().Milliseconds())
	}
	prefix := keyDuration + "="
	if space := widthDuration - len(prefix) - len(text); space > 0 {
		return prefix + strings.Repeat(" ", space) + text
	}
	return prefix + text
}

func pad(text string, width int) string {
	if len(text) >= width {
		return text
	}
	return text + strings.Repeat(" ", width-len(text))
}

const (
	columnEngine = iota
	columnPhase
	columnDuration
)

const (
	keyDetail   = "detail"
	keyDuration = "duration"
	keyPhase    = "phase"
)

const (
	widthTag      = 9
	widthEngine   = 18
	widthPhase    = 16
	widthDuration = 18
)

var (
	columnWidths = []int{widthEngine, widthPhase, widthDuration}
	keysEngine   = []string{"engine", "probe"}
)

var (
	scribeLoggerMutex    sync.Mutex
	scribeLoggerLevel    slog.Level
	scribeLoggerMode     string
	scribeLoggerInstance *slog.Logger
)

func logDir() string {
	if os.Geteuid() == 0 {
		return logDirRoot
	}
	if runtime.GOOS == "darwin" {
		if home, err := os.UserHomeDir(); err == nil {
			return filepath.Join(home, logDirUserMac)
		}
	}
	return logDirUser
}

func fileWriter(cmd string, maxSizeMB, maxBackups, maxAgeDays int) (io.Writer, error) {
	dir := logDir()
	if err := os.MkdirAll(dir, 0755); err != nil {
		return nil, fmt.Errorf("create log directory failed [%s] [%w]", dir, err)
	}
	path := filepath.Join(dir, fmt.Sprintf("%s-pid-%d.log", cmd, os.Getpid()))
	return &lumberjack.Logger{Filename: path, MaxSize: maxSizeMB, MaxBackups: maxBackups, MaxAge: maxAgeDays, Compress: true}, nil
}
