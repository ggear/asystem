package scribe

import (
	"io"
	"log/slog"
	"os"
	"sync"

	"gopkg.in/natefinch/lumberjack.v2"
)

const DefaultLogFile = "/var/log/supervisor/supervisor.log"

func EnableStdout(level slog.Level) {
	scribeLoggerMutex.Lock()
	defer scribeLoggerMutex.Unlock()
	scribeLoggerLevel = level
	scribeLoggerMode = "stdout"
	scribeLoggerInstance = slog.New(slog.NewTextHandler(os.Stdout, &slog.HandlerOptions{Level: level}))
	slog.SetDefault(scribeLoggerInstance)
}

func EnableFile(level slog.Level, path string, maxSizeMB, maxBackups, maxAgeDays int) {
	scribeLoggerMutex.Lock()
	defer scribeLoggerMutex.Unlock()
	if path == "" {
		path = DefaultLogFile
	}
	scribeLoggerLevel = level
	scribeLoggerMode = "file"
	writer := &lumberjack.Logger{Filename: path, MaxSize: maxSizeMB, MaxBackups: maxBackups, MaxAge: maxAgeDays, Compress: true}
	scribeLoggerInstance = slog.New(slog.NewTextHandler(io.MultiWriter(writer), &slog.HandlerOptions{Level: level}))
	slog.SetDefault(scribeLoggerInstance)
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

var (
	scribeLoggerMutex    sync.Mutex
	scribeLoggerLevel    slog.Level
	scribeLoggerMode     string
	scribeLoggerInstance *slog.Logger
)
