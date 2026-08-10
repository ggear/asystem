package scribe

import (
	"log/slog"
	"testing"
)

func TestScribe_ParseLevel(t *testing.T) {
	tests := []struct {
		name          string
		raw           string
		expected      slog.Level
		expectedError bool
	}{
		{name: "debug", raw: "debug", expected: slog.LevelDebug, expectedError: false},
		{name: "info", raw: "INFO", expected: slog.LevelInfo, expectedError: false},
		{name: "warn", raw: " warn ", expected: slog.LevelWarn, expectedError: false},
		{name: "error", raw: "error", expected: slog.LevelError, expectedError: false},
		{name: "invalid", raw: "loud", expected: slog.LevelInfo, expectedError: true},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			got, err := ParseLevel(test.raw)
			if (err != nil) != test.expectedError {
				t.Fatalf("error mismatch: got %v want error=%v", err, test.expectedError)
			}
			if got != test.expected {
				t.Fatalf("level mismatch: got %v want %v", got, test.expected)
			}
		})
	}
}

func TestScribe_EnableStdout(t *testing.T) {
	EnableStdout(slog.LevelDebug)
	if Level() != slog.LevelDebug {
		t.Fatalf("level: got %v want debug", Level())
	}
	if Mode() != "stdout" {
		t.Fatalf("mode: got %q want stdout", Mode())
	}
	Disable()
	if Mode() != "disabled" {
		t.Fatalf("mode: got %q want disabled", Mode())
	}
}
