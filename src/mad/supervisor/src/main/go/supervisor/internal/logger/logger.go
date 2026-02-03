package logger

import (
	"io"
	"log/slog"
	"log/syslog"
	"os"
	"path/filepath"
)

const VarLogFile = "/var/log/supervisor.log"

var currentFile *os.File

func Disable() {
	if currentFile != nil {
		currentFile.Close()
		currentFile = nil
	}
	slog.SetDefault(slog.New(slog.NewTextHandler(io.Discard, nil)))
}

func EnableStdout(level slog.Level) {
	if currentFile != nil {
		currentFile.Close()
		currentFile = nil
	}
	slog.SetDefault(slog.New(slog.NewTextHandler(os.Stdout, &slog.HandlerOptions{Level: level})))
}

func EnableSyslog(level slog.Level, tag string) {
	if currentFile != nil {
		currentFile.Close()
		currentFile = nil
	}
	writer, errorValue := syslog.New(syslog.LOG_INFO|syslog.LOG_DAEMON, tag)
	if errorValue != nil {
		panic(errorValue)
	}
	slog.SetDefault(slog.New(slog.NewTextHandler(writer, &slog.HandlerOptions{Level: level})))
}

func EnableVarlog(level slog.Level, logFile string) {
	if currentFile != nil {
		currentFile.Close()
	}
	dir := filepath.Dir(logFile)
	if errorValue := os.MkdirAll(dir, 0755); errorValue != nil {
		panic(errorValue)
	}
	file, errorValue := os.OpenFile(logFile, os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0644)
	if errorValue != nil {
		panic(errorValue)
	}
	currentFile = file
	slog.SetDefault(slog.New(slog.NewTextHandler(file, &slog.HandlerOptions{Level: level})))
}
