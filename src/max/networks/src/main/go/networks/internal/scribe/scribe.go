package scribe

import (
	"context"
	"fmt"
	"io"
	"log/slog"
	"os"
	"strings"
	"sync"
)

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

type handler struct{}

func (h *handler) Enabled(_ context.Context, level slog.Level) bool {
	scribeMutex.Lock()
	defer scribeMutex.Unlock()
	return level >= scribeLevel
}

func (h *handler) Handle(_ context.Context, record slog.Record) error {
	subject := "*"
	message := record.Message
	if rest, ok := strings.CutPrefix(message, "plugin ["); ok {
		if end := strings.IndexByte(rest, ']'); end >= 0 {
			subject = rest[:end]
			message = strings.TrimPrefix(rest[end+1:], " ")
		}
	}
	var line strings.Builder
	line.WriteString(record.Time.Format("2006/01/02 15:04:05"))
	line.WriteByte(' ')
	fmt.Fprintf(&line, "%-5s", record.Level.String())
	line.WriteByte(' ')
	fmt.Fprintf(&line, "%-10s", "["+subject+"]")
	line.WriteByte(' ')
	line.WriteString(message)
	record.Attrs(func(attr slog.Attr) bool {
		fmt.Fprintf(&line, " %s=[%v]", attr.Key, attr.Value.Any())
		return true
	})
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

var (
	scribeMutex  sync.Mutex
	scribeLevel  slog.Level
	scribeMode   string
	scribeWriter io.Writer
)
