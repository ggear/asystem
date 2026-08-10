package scribe

import (
	"context"
	"fmt"
	"io"
	"log/slog"
	"os"
	"strconv"
	"strings"
	"sync"
	"time"
)

const Global = "*"

func EnableStdout(level slog.Level) {
	scribeMutex.Lock()
	defer scribeMutex.Unlock()
	scribeLevel = level
	scribeMode = "stdout"
	scribeWriter = os.Stdout
	slog.SetDefault(slog.New(&handler{}))
}

func Disable() {
	scribeMutex.Lock()
	defer scribeMutex.Unlock()
	scribeMode = "disabled"
	scribeWriter = io.Discard
}

func Level() slog.Level {
	scribeMutex.Lock()
	defer scribeMutex.Unlock()
	return scribeLevel
}

func Mode() string {
	scribeMutex.Lock()
	defer scribeMutex.Unlock()
	return scribeMode
}

func ParseLevel(raw string) (slog.Level, error) {
	switch strings.ToLower(strings.TrimSpace(raw)) {
	case "debug":
		return slog.LevelDebug, nil
	case "info":
		return slog.LevelInfo, nil
	case "warn", "warning":
		return slog.LevelWarn, nil
	case "error":
		return slog.LevelError, nil
	default:
		return slog.LevelInfo, fmt.Errorf("invalid log level [%s]", raw)
	}
}

func LogDebug(subject, format string, args ...any) { emit(slog.LevelDebug, subject, format, args...) }

func LogInfo(subject, format string, args ...any) { emit(slog.LevelInfo, subject, format, args...) }

func LogWarn(subject, format string, args ...any) { emit(slog.LevelWarn, subject, format, args...) }

func LogError(subject, format string, args ...any) { emit(slog.LevelError, subject, format, args...) }

func LogDiagnosis(subject, status string, score int, took time.Duration, reason string) {
	scoreText := strconv.Itoa(score)
	tookText := fmt.Sprintf("%dms", took.Milliseconds())
	level := slog.LevelInfo
	switch status {
	case "sick":
		level = slog.LevelWarn
	case "dead":
		level = slog.LevelError
	}
	emit(level,
		subject,
		"diagnosed as ... [%s] %s with score ... [%s] %s because [%s] in [%s]",
		status,
		leader(6-len(status)),
		scoreText,
		leader(5-len(scoreText)),
		reason,
		tookText,
	)
}

func emit(level slog.Level, subject, format string, args ...any) {
	logger := slog.Default()
	ctx := context.Background()
	if !logger.Enabled(ctx, level) {
		return
	}
	logger.LogAttrs(ctx, level, fmt.Sprintf(format, args...), slog.String(subjectKey, subject))
}

func leader(width int) string {
	if width < 0 {
		width = 0
	}
	return strings.Repeat(".", width)
}

type handler struct{}

func (h *handler) Enabled(_ context.Context, level slog.Level) bool {
	scribeMutex.Lock()
	defer scribeMutex.Unlock()
	return level >= scribeLevel
}

func (h *handler) Handle(_ context.Context, record slog.Record) error {
	subject := Global
	var attrs strings.Builder
	record.Attrs(func(attr slog.Attr) bool {
		if attr.Key == subjectKey {
			subject = attr.Value.String()
			return true
		}
		fmt.Fprintf(&attrs, " %s=[%v]", attr.Key, attr.Value.Any())
		return true
	})
	var line strings.Builder
	line.WriteString(record.Time.Format("2006/01/02 15:04:05"))
	line.WriteByte(' ')
	fmt.Fprintf(&line, "%-5s", record.Level.String())
	line.WriteByte(' ')
	fmt.Fprintf(&line, "%-10s", "["+subject+"]")
	line.WriteByte(' ')
	line.WriteString(record.Message)
	line.WriteString(attrs.String())
	line.WriteByte('\n')
	scribeMutex.Lock()
	writer := scribeWriter
	scribeMutex.Unlock()
	if writer == nil {
		return nil
	}
	_, err := io.WriteString(writer, line.String())
	return err
}

func (h *handler) WithAttrs(_ []slog.Attr) slog.Handler { return h }

func (h *handler) WithGroup(_ string) slog.Handler { return h }

const subjectKey = "subject"

var (
	scribeMutex  sync.Mutex
	scribeLevel  slog.Level
	scribeMode   string
	scribeWriter io.Writer
)
