package scribe

import (
	"bytes"
	"fmt"
	"log/slog"
	"os"
	"path/filepath"
	"supervisor/internal/testutil"
	"testing"
)

func TestScribe_Stdout(t *testing.T) {
	tests := []struct {
		name     string
		setup    func()
		logFunc  func(string)
		expected bool
	}{
		{
			name:     "Enabled",
			setup:    func() { EnableStdout(slog.LevelDebug) },
			logFunc:  func(message string) { slog.Debug(message) },
			expected: true,
		},
		{
			name:     "Disabled",
			setup:    func() { EnableStdout(9) },
			logFunc:  func(message string) { slog.Error(message) },
			expected: false,
		},
		{
			name:     "Enabled",
			setup:    func() { EnableStdout(slog.LevelDebug) },
			logFunc:  func(message string) { slog.Debug(message) },
			expected: true,
		},
		{
			name:     "Disabled",
			setup:    func() { Disable() },
			logFunc:  func(message string) { slog.Error(message) },
			expected: false,
		},
	}
	for index, testCase := range tests {
		testCase := testCase
		name := fmt.Sprintf("%s_%d", testCase.name, index)
		message := fmt.Sprintf("Expected log message %d", index)
		if !testCase.expected {
			message = fmt.Sprintf("UNEXPECTED LOG MESSAGE %d!!!!", index)
		}
		t.Run(name, func(t *testing.T) {
			testCase.setup()
			t.Logf("Log in mode [%s] and level [%v]", Mode(), Level())
			testCase.logFunc(message)
		})
	}
}

func TestScribe_File(t *testing.T) {
	tests := []struct {
		name     string
		setup    func(string)
		logFunc  func(string)
		expected bool
	}{
		{
			name:     "Enabled",
			setup:    func(logPath string) { EnableFile(slog.LevelDebug, logPath, 10, 7, 30) },
			logFunc:  func(message string) { slog.Debug(message) },
			expected: true,
		},
		{
			name:     "Disabled",
			setup:    func(logPath string) { EnableFile(9, logPath, 10, 7, 30) },
			logFunc:  func(message string) { slog.Error(message) },
			expected: false,
		},
		{
			name:     "Enabled",
			setup:    func(logPath string) { EnableFile(slog.LevelDebug, logPath, 10, 7, 30) },
			logFunc:  func(message string) { slog.Debug(message) },
			expected: true,
		},
		{
			name:     "Disabled",
			setup:    func(logPath string) { Disable() },
			logFunc:  func(message string) { slog.Error(message) },
			expected: false,
		},
	}
	baseDir := testutil.FindDir(t, "target")
	for index, testCase := range tests {
		testCase := testCase
		name := fmt.Sprintf("%s_%d", testCase.name, index)
		message := fmt.Sprintf("Expected log message %d", index)
		if !testCase.expected {
			message = fmt.Sprintf("UNEXPECTED LOG MESSAGE %d!!!!", index)
		}
		logPath := filepath.Join(baseDir, fmt.Sprintf("supervisor-test-%d.log", index))
		t.Run(name, func(t *testing.T) {
			_ = os.Remove(logPath)
			testCase.setup(logPath)
			t.Logf("Log in mode [%s] and level [%v]", Mode(), Level())
			testCase.logFunc(message)
			content, err := os.ReadFile(logPath)
			if err != nil {
				if !testCase.expected && os.IsNotExist(err) {
					return
				}
				t.Fatalf("ReadFile failed: %v", err)
			}
			contains := bytes.Contains(content, []byte(message))
			if testCase.expected && !contains {
				t.Fatalf("expected log message %q, got %q", message, string(content))
			}
			if !testCase.expected && contains {
				t.Fatalf("unexpected log message %q in %q", message, string(content))
			}
		})
	}
}
