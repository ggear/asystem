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
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			got, err := ParseLevel(testCase.raw)
			if (err != nil) != testCase.expectedError {
				t.Fatalf("error mismatch: got %v want error=%v", err, testCase.expectedError)
			}
			if got != testCase.expected {
				t.Fatalf("level mismatch: got %v want %v", got, testCase.expected)
			}
		})
	}
}
