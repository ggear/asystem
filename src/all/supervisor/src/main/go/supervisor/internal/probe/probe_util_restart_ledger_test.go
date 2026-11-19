package probe

import (
	"os"
	"path/filepath"
	"reflect"
	"testing"
	"time"
)

func newTestLedger(t *testing.T) (*restartLedger, string) {
	t.Helper()
	path := filepath.Join(t.TempDir(), "restart", "ledger.json")
	return newRestartLedger(path), path
}

func TestProbeUtilRestartLedger_Count(t *testing.T) {
	at := time.Unix(1_700_000_000, 0)
	tests := []struct {
		name          string
		recorded      [][2]string
		service       string
		container     string
		expectedCount int
	}{
		{name: "empty_ledger_counts_nothing", service: "plex", container: "a", expectedCount: 0},
		{name: "restarts_of_one_container_add_up", recorded: [][2]string{{"plex", "a"}, {"plex", "a"}}, service: "plex", container: "a", expectedCount: 2},
		{name: "a_recreated_container_starts_again_from_zero", recorded: [][2]string{{"plex", "a"}, {"plex", "a"}}, service: "plex", container: "b", expectedCount: 0},
		{name: "recording_against_a_recreated_container_replaces_the_old_count", recorded: [][2]string{{"plex", "a"}, {"plex", "a"}, {"plex", "b"}}, service: "plex", container: "b", expectedCount: 1},
		{name: "services_are_counted_apart", recorded: [][2]string{{"plex", "a"}, {"sonarr", "c"}}, service: "sonarr", container: "c", expectedCount: 1},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			ledger, _ := newTestLedger(t)
			for _, entry := range test.recorded {
				if err := ledger.record(entry[0], entry[1], at); err != nil {
					t.Fatalf("record failed with [%v]", err)
				}
			}
			if got := ledger.count(test.service, test.container); got != test.expectedCount {
				t.Fatalf("count: got %d want %d", got, test.expectedCount)
			}
		})
	}
}

func TestProbeUtilRestartLedger_History(t *testing.T) {
	first, second := time.Unix(1_700_000_000, 0), time.Unix(1_700_000_600, 0)
	tests := []struct {
		name            string
		act             func(*restartLedger) error
		expectedAttempt []time.Time
		expectedStreak  int
		expectedCount   int
	}{
		{name: "an_attempt_is_kept_with_its_time", act: func(l *restartLedger) error { return l.record("plex", "a", first) }, expectedAttempt: []time.Time{first}, expectedStreak: 1, expectedCount: 1},
		{name: "two_attempts_build_a_streak", act: func(l *restartLedger) error {
			_ = l.record("plex", "a", first)
			return l.record("plex", "a", second)
		}, expectedAttempt: []time.Time{first, second}, expectedStreak: 2, expectedCount: 2},
		{name: "settling_clears_the_streak_but_keeps_the_attempts_and_the_count", act: func(l *restartLedger) error {
			_ = l.record("plex", "a", first)
			return l.settled("plex", "a")
		}, expectedAttempt: []time.Time{first}, expectedStreak: 0, expectedCount: 1},
		{name: "a_refund_takes_the_last_attempt_back", act: func(l *restartLedger) error {
			_ = l.record("plex", "a", first)
			_ = l.record("plex", "a", second)
			return l.refund("plex", "a")
		}, expectedAttempt: []time.Time{first}, expectedStreak: 1, expectedCount: 1},
		{name: "a_refund_with_nothing_recorded_changes_nothing", act: func(l *restartLedger) error { return l.refund("plex", "a") }, expectedAttempt: []time.Time{}, expectedStreak: 0, expectedCount: 0},
		{name: "a_new_boot_clears_attempts_and_streak_but_not_the_count", act: func(l *restartLedger) error {
			_ = l.booted("boot-1")
			_ = l.record("plex", "a", first)
			return l.booted("boot-2")
		}, expectedAttempt: []time.Time{}, expectedStreak: 0, expectedCount: 1},
		{name: "the_same_boot_keeps_everything", act: func(l *restartLedger) error {
			_ = l.booted("boot-1")
			_ = l.record("plex", "a", first)
			return l.booted("boot-1")
		}, expectedAttempt: []time.Time{first}, expectedStreak: 1, expectedCount: 1},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			ledger, path := newTestLedger(t)
			if err := test.act(ledger); err != nil {
				t.Fatalf("act failed with [%v]", err)
			}
			for _, view := range []*restartLedger{ledger, newRestartLedger(path)} {
				history := view.history("plex", "a")
				if len(history.attempts) == 0 {
					history.attempts = []time.Time{}
				}
				if !reflect.DeepEqual(history.attempts, test.expectedAttempt) || history.streak != test.expectedStreak || view.count("plex", "a") != test.expectedCount {
					t.Fatalf("history: got attempts %v streak %d count %d want attempts %v streak %d count %d",
						history.attempts, history.streak, view.count("plex", "a"), test.expectedAttempt, test.expectedStreak, test.expectedCount)
				}
			}
		})
	}
}

func TestProbeUtilRestartLedger_Bounded(t *testing.T) {
	ledger, _ := newTestLedger(t)
	for index := range restartAttemptsKept + 5 {
		if err := ledger.record("plex", "a", time.Unix(int64(1_700_000_000+index), 0)); err != nil {
			t.Fatalf("record failed with [%v]", err)
		}
	}
	if got := len(ledger.history("plex", "a").attempts); got != restartAttemptsKept {
		t.Fatalf("attempts kept: got %d want %d", got, restartAttemptsKept)
	}
	if got := ledger.count("plex", "a"); got != restartAttemptsKept+5 {
		t.Fatalf("count: got %d want %d", got, restartAttemptsKept+5)
	}
}

func TestProbeUtilRestartLedger_Persist(t *testing.T) {
	tests := []struct {
		name          string
		content       *string
		expectedCount int
	}{
		{name: "a_reopened_ledger_keeps_its_counts", expectedCount: 2},
		{name: "a_corrupt_file_reads_as_empty", content: new("{"), expectedCount: 0},
		{name: "a_null_file_reads_as_empty", content: new("null"), expectedCount: 0},
		{name: "a_file_with_no_services_reads_as_empty", content: new(`{"boot":"x"}`), expectedCount: 0},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			path := filepath.Join(t.TempDir(), "ledger.json")
			if test.content == nil {
				first := newRestartLedger(path)
				for range 2 {
					if err := first.record("plex", "a", time.Unix(1, 0)); err != nil {
						t.Fatalf("record failed with [%v]", err)
					}
				}
			} else if err := os.WriteFile(path, []byte(*test.content), 0o644); err != nil {
				t.Fatalf("write failed with [%v]", err)
			}
			if got := newRestartLedger(path).count("plex", "a"); got != test.expectedCount {
				t.Fatalf("count: got %d want %d", got, test.expectedCount)
			}
		})
	}
}

func TestProbeUtilRestartLedger_Unwritable(t *testing.T) {
	blocker := filepath.Join(t.TempDir(), "file")
	if err := os.WriteFile(blocker, nil, 0o644); err != nil {
		t.Fatalf("write failed with [%v]", err)
	}
	ledger := newRestartLedger(filepath.Join(blocker, "ledger.json"))
	if err := ledger.record("plex", "a", time.Unix(1, 0)); err == nil {
		t.Fatalf("record: got nil want an error")
	}
	if got := ledger.count("plex", "a"); got != 0 {
		t.Fatalf("count after a failed write: got %d want 0", got)
	}
	if got := len(ledger.history("plex", "a").attempts); got != 0 {
		t.Fatalf("attempts after a failed write: got %d want 0", got)
	}
}

func TestProbeUtilRestartLedger_Nil(t *testing.T) {
	var ledger *restartLedger
	if got := ledger.count("plex", "a"); got != 0 {
		t.Fatalf("count on a nil ledger: got %d want 0", got)
	}
}

//go:fix inline
