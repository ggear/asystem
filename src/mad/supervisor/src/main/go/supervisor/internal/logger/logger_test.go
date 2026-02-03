package logger

import (
	"bytes"
	"log/slog"
	"path/filepath"
	"testing"
)

func TestLogger_Typical(t *testing.T) {
	EnableVarlog(slog.LevelDebug, filepath.Join(t.TempDir(), "supervisor.log"))
	EnableStdout(slog.LevelDebug)
	slog.Debug("expected debug message one")
	EnableStdout(9)
	slog.Error("UNEXPECTED ERROR MESSAGE ONE!!!")
	EnableStdout(slog.LevelDebug)
	slog.Debug("expected debug message two")
	Disable()
	slog.Error("UNEXPECTED ERROR MESSAGE TWO!!!")
}

func TestLogger_Disable(t *testing.T) {
	tests := []struct {
		name       string
		setup      func() func()
		logMessage string
		want       string
	}{
		{"Disable", func() func() {
			Disable()
			return func() { Disable() }
		}, "testCase disable", ""},
		{"EnableStdout", func() func() {
			EnableStdout(slog.LevelDebug)
			return func() { Disable() }
		}, "stdout message", "stdout message"},
		{"EnableVarlog", func() func() {
			EnableVarlog(slog.LevelInfo, filepath.Join(t.TempDir(), "supervisor.log"))
			return func() { Disable() }
		}, "varlog message", "varlog message"},
		{"EnableSyslog", func() func() {
			defer func() { _ = recover() }()
			EnableSyslog(slog.LevelInfo, "testtool")
			return func() { Disable() }
		}, "syslog message", "syslog message"},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			cleanup := testCase.setup()
			defer cleanup()
			var buf bytes.Buffer
			slog.SetDefault(slog.New(slog.NewTextHandler(&buf, &slog.HandlerOptions{Level: slog.LevelDebug})))
			slog.Info(testCase.logMessage)
			got := buf.String()
			if testCase.want != "" && !bytes.Contains([]byte(got), []byte(testCase.want)) {
				t.Fatalf("%s failed: expected %q in log, got %q", testCase.name, testCase.want, got)
			}
		})
	}
}
