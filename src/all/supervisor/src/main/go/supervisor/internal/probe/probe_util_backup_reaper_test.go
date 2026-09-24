package probe

import (
	"testing"
	"time"
)

func TestProbeUtilBackupReaper_PauseUntilTargetsTheNextScheduledHour(t *testing.T) {
	tests := []struct {
		name     string
		now      time.Time
		expected time.Time
	}{
		{name: "before_the_scheduled_hour_same_day", now: time.Date(2026, 9, 22, 0, 30, 0, 0, time.UTC),
			expected: time.Date(2026, 9, 22, backupScheduledHour, 0, 0, 0, time.UTC)},
		{name: "at_the_scheduled_hour_rolls_to_the_next_day", now: time.Date(2026, 9, 22, backupScheduledHour, 0, 0, 0, time.UTC),
			expected: time.Date(2026, 9, 23, backupScheduledHour, 0, 0, 0, time.UTC)},
		{name: "after_the_scheduled_hour_rolls_to_the_next_day", now: time.Date(2026, 9, 22, 10, 0, 0, 0, time.UTC),
			expected: time.Date(2026, 9, 23, backupScheduledHour, 0, 0, 0, time.UTC)},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			if got := backupReaperPauseUntil(testCase.now); !got.Equal(testCase.expected) {
				t.Errorf("backupReaperPauseUntil(%s) = %s, want %s", testCase.now, got, testCase.expected)
			}
		})
	}
}
