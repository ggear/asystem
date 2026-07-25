package scribe

import (
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
	scribeInstance = slog.New(slog.NewTextHandler(os.Stdout, &slog.HandlerOptions{Level: level}))
	slog.SetDefault(scribeInstance)
}

func Disable() {
	scribeMutex.Lock()
	defer scribeMutex.Unlock()
	scribeMode = "disabled"
	scribeInstance = slog.New(slog.NewTextHandler(io.Discard, &slog.HandlerOptions{}))
	slog.SetDefault(scribeInstance)
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

var (
	scribeMutex    sync.Mutex
	scribeLevel    slog.Level
	scribeMode     string
	scribeInstance *slog.Logger
)
