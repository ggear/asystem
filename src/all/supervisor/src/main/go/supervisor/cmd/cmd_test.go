package cmd

import (
	"log/slog"
	"testing"

	"supervisor/internal/config"
)

func TestCmd_MakeLevel(t *testing.T) {
	tests := []struct {
		name          string
		level         string
		expected      slog.Level
		expectedError bool
	}{
		{"debug", "debug", slog.LevelDebug, false},
		{"case and space are forgiven", "  WARN ", slog.LevelWarn, false},
		{"error", "error", slog.LevelError, false},
		{"an unknown word is refused", "trace", slog.LevelInfo, true},
		{"an empty word is refused", "", slog.LevelInfo, true},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			level, err := makeLevel(testCase.level)
			if level != testCase.expected || (err != nil) != testCase.expectedError {
				t.Errorf("level: got [%v] error [%v] want [%v] error [%t]", level, err, testCase.expected, testCase.expectedError)
			}
		})
	}
}

func TestCmd_MakePeriods(t *testing.T) {
	tests := []struct {
		name          string
		poll          string
		pulseFactor   string
		trend         string
		cache         string
		snapshot      string
		heartbeat     string
		expected      config.Periods
		expectedError bool
	}{
		{"heartbeat rounds up to a whole number of pulses", "1s", "5", "24h", "10m", "1m", "12s",
			config.Periods{PollMillis: 1000, PulseMillis: 5000, TrendHours: 24, CacheMins: 10, SnapshotMins: 1, HeartbeatSecs: 15}, false},
		{"a heartbeat on a pulse boundary is kept", "1s", "5", "1h", "1m", "1m", "10s",
			config.Periods{PollMillis: 1000, PulseMillis: 5000, TrendHours: 1, CacheMins: 1, SnapshotMins: 1, HeartbeatSecs: 10}, false},
		{"a zero poll is refused", "0s", "5", "1h", "1m", "1m", "10s", config.Periods{}, true},
		{"a pulse factor below one is refused", "1s", "0", "1h", "1m", "1m", "10s", config.Periods{}, true},
		{"a pulse factor that is not a number is refused", "1s", "x", "1h", "1m", "1m", "10s", config.Periods{}, true},
		{"a trend that is not whole hours is refused", "1s", "5", "90m", "1m", "1m", "10s", config.Periods{}, true},
		{"a negative cache is refused", "1s", "5", "1h", "-1m", "1m", "10s", config.Periods{}, true},
		{"a snapshot that is not whole minutes is refused", "1s", "5", "1h", "1m", "30s", "10s", config.Periods{}, true},
		{"a zero heartbeat is refused", "1s", "5", "1h", "1m", "1m", "0s", config.Periods{}, true},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			periods, err := makePeriods(testCase.poll, testCase.pulseFactor, testCase.trend, testCase.cache, testCase.snapshot, testCase.heartbeat)
			if periods != testCase.expected || (err != nil) != testCase.expectedError {
				t.Errorf("periods: got [%+v] error [%v] want [%+v] error [%t]", periods, err, testCase.expected, testCase.expectedError)
			}
		})
	}
}

func TestCmd_IncludedHosts(t *testing.T) {
	tests := []struct {
		name       string
		selected   []string
		configured []string
		expected   string
	}{
		{"every configured host is a wildcard", []string{"b", "a"}, []string{"a", "b"}, "*"},
		{"a subset is named", []string{"a"}, []string{"a", "b"}, "a"},
		{"a host the config does not know is named", []string{"a", "z"}, []string{"a", "b"}, "a,z"},
		{"nothing configured names the selection", []string{"a", "b"}, nil, "a,b"},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			if actual := includedHosts(testCase.selected, testCase.configured); actual != testCase.expected {
				t.Errorf("hosts: got [%s] want [%s]", actual, testCase.expected)
			}
		})
	}
}
