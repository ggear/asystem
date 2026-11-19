package probe

import (
	"fmt"
	"os"
	"path/filepath"
	"reflect"
	"testing"
	"time"
)

func TestMain(m *testing.M) {
	directory, err := os.MkdirTemp("", "supervisor-probe-")
	if err != nil {
		fmt.Fprintf(os.Stderr, "temp directory failed with [%v]\n", err)
		os.Exit(1)
	}
	restartLedgerPath = filepath.Join(directory, "ledger.json")
	code := m.Run()
	_ = os.RemoveAll(directory)
	os.Exit(code)
}

func newTestLedger(t *testing.T) (*restartLedger, string) {
	t.Helper()
	path := filepath.Join(t.TempDir(), "restart", "ledger.json")
	return newRestartLedger(path), path
}

func TestProbeUtilRestartLedger_Observed(t *testing.T) {
	start := time.Unix(1_700_000_000, 0)
	type seen struct {
		container string
		docker    int
		after     time.Duration
	}
	tests := []struct {
		name               string
		attempted          []time.Duration
		sightings          []seen
		reload             bool
		expectedDocker     int
		expectedSupervised int
	}{
		{name: "a_first_sighting_is_a_baseline_and_counts_nothing", sightings: []seen{{"a", 5, 0}}, expectedDocker: 0},
		{name: "a_rise_in_dockers_total_is_counted", sightings: []seen{{"a", 2, 0}, {"a", 5, time.Minute}}, expectedDocker: 3},
		{name: "a_steady_total_adds_nothing", sightings: []seen{{"a", 2, 0}, {"a", 2, time.Minute}, {"a", 2, time.Hour}}, expectedDocker: 0},
		{name: "a_rise_ages_out_after_the_window", sightings: []seen{{"a", 2, 0}, {"a", 5, time.Minute}, {"a", 5, 25 * time.Hour}}, expectedDocker: 0},
		{name: "a_rise_inside_the_window_is_kept", sightings: []seen{{"a", 2, 0}, {"a", 5, time.Minute}, {"a", 5, 23 * time.Hour}}, expectedDocker: 3},
		{name: "a_recreated_container_is_baselined_again", sightings: []seen{{"a", 2, 0}, {"a", 4, time.Minute}, {"b", 3, 2 * time.Minute}}, expectedDocker: 0},
		{name: "rises_survive_a_new_ledger_reading_the_same_file", sightings: []seen{{"a", 2, 0}, {"a", 6, time.Minute}}, reload: true, expectedDocker: 4},
		{name: "supervisor_attempts_inside_the_window_are_counted", attempted: []time.Duration{time.Minute, 2 * time.Minute}, sightings: []seen{{"a", 0, 10 * time.Minute}}, expectedSupervised: 2},
		{name: "supervisor_attempts_age_out_after_the_window", attempted: []time.Duration{time.Minute}, sightings: []seen{{"a", 0, 25 * time.Hour}}, expectedSupervised: 0},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			ledger, path := newTestLedger(t)
			for _, after := range test.attempted {
				if err := ledger.record("plex", "a", start.Add(after)); err != nil {
					t.Fatalf("record failed with [%v]", err)
				}
			}
			var docker, supervised int
			var err error
			for index, sighting := range test.sightings {
				if test.reload && index == len(test.sightings)-1 {
					ledger = newRestartLedger(path)
				}
				if docker, supervised, err = ledger.observed("plex", sighting.container, sighting.docker, start.Add(sighting.after)); err != nil {
					t.Fatalf("observed failed with [%v]", err)
				}
			}
			if docker != test.expectedDocker || supervised != test.expectedSupervised {
				t.Fatalf("observed: got docker %d supervised %d want docker %d supervised %d", docker, supervised, test.expectedDocker, test.expectedSupervised)
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
	}{
		{name: "an_attempt_is_kept_with_its_time", act: func(l *restartLedger) error { return l.record("plex", "a", first) }, expectedAttempt: []time.Time{first}, expectedStreak: 1},
		{name: "two_attempts_build_a_streak", act: func(l *restartLedger) error {
			_ = l.record("plex", "a", first)
			return l.record("plex", "a", second)
		}, expectedAttempt: []time.Time{first, second}, expectedStreak: 2},
		{name: "settling_clears_the_streak_but_keeps_the_attempts", act: func(l *restartLedger) error {
			_ = l.record("plex", "a", first)
			return l.settled("plex", "a")
		}, expectedAttempt: []time.Time{first}, expectedStreak: 0},
		{name: "a_refund_takes_the_last_attempt_back", act: func(l *restartLedger) error {
			_ = l.record("plex", "a", first)
			_ = l.record("plex", "a", second)
			return l.refund("plex", "a")
		}, expectedAttempt: []time.Time{first}, expectedStreak: 1},
		{name: "a_refund_with_nothing_recorded_changes_nothing", act: func(l *restartLedger) error { return l.refund("plex", "a") }, expectedAttempt: []time.Time{}, expectedStreak: 0},
		{name: "a_new_boot_clears_attempts_and_streak", act: func(l *restartLedger) error {
			_ = l.booted("boot-1")
			_ = l.record("plex", "a", first)
			return l.booted("boot-2")
		}, expectedAttempt: []time.Time{}, expectedStreak: 0},
		{name: "the_same_boot_keeps_everything", act: func(l *restartLedger) error {
			_ = l.booted("boot-1")
			_ = l.record("plex", "a", first)
			return l.booted("boot-1")
		}, expectedAttempt: []time.Time{first}, expectedStreak: 1},
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
				if !reflect.DeepEqual(history.attempts, test.expectedAttempt) || history.streak != test.expectedStreak {
					t.Fatalf("history: got attempts %v streak %d want attempts %v streak %d",
						history.attempts, history.streak, test.expectedAttempt, test.expectedStreak)
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
}

func TestProbeUtilRestartLedger_Persist(t *testing.T) {
	tests := []struct {
		name             string
		content          *string
		expectedAttempts int
	}{
		{name: "a_reopened_ledger_keeps_its_attempts", expectedAttempts: 2},
		{name: "a_corrupt_file_reads_as_empty", content: new("{")},
		{name: "a_null_file_reads_as_empty", content: new("null")},
		{name: "a_file_with_no_services_reads_as_empty", content: new(`{"boot":"x"}`)},
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
			if got := len(newRestartLedger(path).history("plex", "a").attempts); got != test.expectedAttempts {
				t.Fatalf("attempts: got %d want %d", got, test.expectedAttempts)
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
	if _, _, err := ledger.observed("plex", "a", 1, time.Unix(1, 0)); err == nil {
		t.Fatalf("observed: got nil want an error")
	}
	if got := len(ledger.history("plex", "a").attempts); got != 0 {
		t.Fatalf("attempts after a failed write: got %d want 0", got)
	}
}

//go:fix inline
