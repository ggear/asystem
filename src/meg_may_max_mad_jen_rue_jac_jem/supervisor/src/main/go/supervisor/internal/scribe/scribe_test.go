package scribe

import (
	"bytes"
	"fmt"
	"log/slog"
	"os"
	"path/filepath"
	"testing"
	"time"
)

func TestScribe_Stdout(t *testing.T) {
	tests := []struct {
		name     string
		setup    func()
		logFunc  func(string)
		expected bool
	}{
		{
			name:     "happy_debug_enabled",
			setup:    func() { EnableStdout(slog.LevelDebug) },
			logFunc:  func(message string) { slog.Debug(message) },
			expected: true,
		},
		{
			name:     "happy_level_too_high",
			setup:    func() { EnableStdout(9) },
			logFunc:  func(message string) { slog.Error(message) },
			expected: false,
		},
		{
			name:     "happy_re_enabled",
			setup:    func() { EnableStdout(slog.LevelDebug) },
			logFunc:  func(message string) { slog.Debug(message) },
			expected: true,
		},
		{
			name:     "happy_disabled",
			setup:    func() { Disable() },
			logFunc:  func(message string) { slog.Error(message) },
			expected: false,
		},
	}
	for index, testCase := range tests {
		testCase := testCase
		message := fmt.Sprintf("Expected log message %d", index)
		if !testCase.expected {
			message = fmt.Sprintf("UNEXPECTED LOG MESSAGE %d!!!!", index)
		}
		t.Run(testCase.name, func(t *testing.T) {
			testCase.setup()
			t.Logf("Log in mode [%s] and level [%v]", Mode(), Level())
			testCase.logFunc(message)
		})
	}
}

func TestScribe_File(t *testing.T) {
	tests := []struct {
		name     string
		setup    func(string) error
		logFunc  func(string)
		expected bool
	}{
		{
			name:     "happy_debug_enabled",
			setup:    func(cmd string) error { return EnableFile(slog.LevelDebug, cmd, 10, 7, 30) },
			logFunc:  func(message string) { slog.Debug(message) },
			expected: true,
		},
		{
			name:     "happy_level_too_high",
			setup:    func(cmd string) error { return EnableFile(9, cmd, 10, 7, 30) },
			logFunc:  func(message string) { slog.Error(message) },
			expected: false,
		},
		{
			name:     "happy_re_enabled",
			setup:    func(cmd string) error { return EnableFile(slog.LevelDebug, cmd, 10, 7, 30) },
			logFunc:  func(message string) { slog.Debug(message) },
			expected: true,
		},
		{
			name:     "happy_disabled",
			setup:    func(cmd string) error { Disable(); return nil },
			logFunc:  func(message string) { slog.Error(message) },
			expected: false,
		},
	}
	logDir := logDirUser
	if os.Geteuid() == 0 {
		logDir = logDirRoot
	}
	for index, testCase := range tests {
		testCase := testCase
		message := fmt.Sprintf("Expected log message %d", index)
		if !testCase.expected {
			message = fmt.Sprintf("UNEXPECTED LOG MESSAGE %d!!!!", index)
		}
		cmdName := fmt.Sprintf("supervisor-test-%d", index)
		logPath := filepath.Join(logDir, fmt.Sprintf("%s-pid-%d.log", cmdName, os.Getpid()))
		t.Run(testCase.name, func(t *testing.T) {
			_ = os.Remove(logPath)
			if err := testCase.setup(cmdName); err != nil {
				t.Fatalf("Got err = %v, expected nil", err)
			}
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
				t.Fatalf("Got log content = %q, expected to contain %q", string(content), message)
			}
			if !testCase.expected && contains {
				t.Fatalf("Got log content contains %q, expected not to", message)
			}
		})
	}
}

func TestScribe_Buffer(t *testing.T) {
	tests := []struct {
		name          string
		pushCount     int
		tailN         int
		expectedCount int
		expectedError bool
	}{
		{
			name:          "happy_single_push",
			pushCount:     1,
			tailN:         10,
			expectedCount: 1,
			expectedError: false,
		},
		{
			name:          "happy_tail_less_than_count",
			pushCount:     10,
			tailN:         3,
			expectedCount: 3,
			expectedError: false,
		},
		{
			name:          "happy_tail_more_than_count",
			pushCount:     5,
			tailN:         10,
			expectedCount: 5,
			expectedError: false,
		},
		{
			name:          "happy_wrap_around",
			pushCount:     80,
			tailN:         50,
			expectedCount: 50,
			expectedError: false,
		},
		{
			name:          "happy_exact_capacity",
			pushCount:     50,
			tailN:         50,
			expectedCount: 50,
			expectedError: false,
		},
		{
			name:          "happy_empty_tail",
			pushCount:     0,
			tailN:         10,
			expectedCount: 0,
			expectedError: false,
		},
		{
			name:          "happy_tail_zero",
			pushCount:     10,
			tailN:         0,
			expectedCount: 0,
			expectedError: false,
		},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			buf := &LogBuffer{lines: make([]LogLine, 50)}
			for i := range testCase.pushCount {
				buf.Push(LogLine{
					Time:    time.Now(),
					Level:   slog.LevelInfo,
					Message: fmt.Sprintf("message %d", i),
				})
			}
			tail := buf.Tail(testCase.tailN)
			if len(tail) != testCase.expectedCount {
				t.Fatalf("Got tail length = %d, expected %d", len(tail), testCase.expectedCount)
			}
			if testCase.pushCount > 0 && testCase.expectedCount > 0 {
				lastMsg := tail[len(tail)-1].Message
				expectedMsg := fmt.Sprintf("message %d", testCase.pushCount-1)
				if lastMsg != expectedMsg {
					t.Fatalf("Got last message = %q, expected %q", lastMsg, expectedMsg)
				}
			}
			expectedVersion := uint64(testCase.pushCount)
			if buf.Version() != expectedVersion {
				t.Fatalf("Got version = %d, expected %d", buf.Version(), expectedVersion)
			}
		})
	}
}

func TestScribe_BufferHandler(t *testing.T) {
	tests := []struct {
		name          string
		level         slog.Level
		logFunc       func(string)
		expected      bool
		expectedError bool
	}{
		{
			name:          "happy_debug_captured",
			level:         slog.LevelDebug,
			logFunc:       func(msg string) { slog.Debug(msg) },
			expected:      true,
			expectedError: false,
		},
		{
			name:          "happy_info_captured",
			level:         slog.LevelDebug,
			logFunc:       func(msg string) { slog.Info(msg) },
			expected:      true,
			expectedError: false,
		},
		{
			name:          "happy_error_captured",
			level:         slog.LevelDebug,
			logFunc:       func(msg string) { slog.Error(msg) },
			expected:      true,
			expectedError: false,
		},
		{
			name:          "happy_filtered_by_level",
			level:         slog.LevelError,
			logFunc:       func(msg string) { slog.Debug(msg) },
			expected:      false,
			expectedError: false,
		},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			buf := EnableBuffer(testCase.level, 50)
			msg := fmt.Sprintf("test-%s", testCase.name)
			testCase.logFunc(msg)
			tail := buf.Tail(1)
			found := len(tail) > 0 && bytes.Contains([]byte(tail[0].Message), []byte(msg))
			if found != testCase.expected {
				t.Fatalf("Got message found = %v, expected %v", found, testCase.expected)
			}
		})
	}
}
