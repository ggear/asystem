package scribe

import (
	"fmt"
	"io"
	"log"
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
	log.SetOutput(os.Stdout)
	slog.SetLogLoggerLevel(level)
}

func Disable() {
	scribeMutex.Lock()
	defer scribeMutex.Unlock()
	scribeMode = "disabled"
	log.SetOutput(io.Discard)
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
	scribeMutex sync.Mutex
	scribeLevel slog.Level
	scribeMode  string
)
