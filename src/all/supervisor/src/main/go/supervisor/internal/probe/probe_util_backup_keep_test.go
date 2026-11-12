package probe

import (
	"os"
	"path/filepath"
	"slices"
	"testing"
	"time"

	"supervisor/internal/metric"
	"supervisor/internal/scribe"
)

func TestProbeUtilBackupKeep_KeepSet(t *testing.T) {
	now := time.Date(2026, 10, 26, 12, 0, 0, 0, time.Local)
	incident := []backupKeepRun{
		keepFixture("2026-10-19_01-00-28", true, "", metric.BackupStateSuccess),
		keepFixture("2026-10-20_01-00-08", false, "2026-10-19_01-00-28", metric.BackupStateSuccess),
		keepFixture("2026-10-21_01-00-08", false, "2026-10-20_01-00-08", metric.BackupStateSuccess),
		keepFixture("2026-10-22_01-00-08", false, "2026-10-21_01-00-08", metric.BackupStateSuccess),
		keepFixture("2026-10-22_08-11-23", false, "2026-10-22_01-00-08", metric.BackupStateRegressed),
	}
	tests := []struct {
		name     string
		runs     []backupKeepRun
		policy   backupKeepPolicy
		expected []string
	}{
		{"empty", nil, backupKeepPolicy{window: time.Hour}, nil},
		{
			"a single run is always kept",
			[]backupKeepRun{keepFixture("2026-10-10_01-00-00", true, "", "")},
			backupKeepPolicy{daily: 1, weekly: 1, monthly: 1},
			[]string{"2026-10-10_01-00-00"},
		},
		{
			"window drops the old full but the closure keeps what kept deltas hang off",
			[]backupKeepRun{
				keepFixture("2026-10-10_01-00-00", true, "", metric.BackupStateSuccess),
				keepFixture("2026-10-20_01-00-00", true, "", metric.BackupStateSuccess),
				keepFixture("2026-10-24_01-00-00", false, "2026-10-20_01-00-00", metric.BackupStateSuccess),
				keepFixture("2026-10-25_01-00-00", false, "2026-10-24_01-00-00", metric.BackupStateSuccess),
			},
			backupKeepPolicy{window: 36 * time.Hour},
			[]string{"2026-10-20_01-00-00", "2026-10-24_01-00-00", "2026-10-25_01-00-00"},
		},
		{
			"a regressed newest run pins the last good run and its full",
			incident,
			backupKeepPolicy{window: time.Hour},
			[]string{"2026-10-19_01-00-28", "2026-10-20_01-00-08", "2026-10-21_01-00-08", "2026-10-22_01-00-08", "2026-10-22_08-11-23"},
		},
		{
			"an accepted regressed run releases the anchor",
			append(slices.Clone(incident[:4]), backupKeepRun{name: "2026-10-22_08-11-23", at: now, full: true, verdict: metric.BackupStateRegressed, accepted: true}),
			backupKeepPolicy{window: time.Hour},
			[]string{"2026-10-22_08-11-23"},
		},
		{
			"a delta with no manifest hangs off the run before it",
			[]backupKeepRun{
				keepFixture("2026-10-10_01-00-00", true, "", ""),
				keepFixture("2026-10-24_01-00-00", false, "", ""),
				keepFixture("2026-10-25_01-00-00", false, "", ""),
			},
			backupKeepPolicy{window: 36 * time.Hour},
			[]string{"2026-10-10_01-00-00", "2026-10-24_01-00-00", "2026-10-25_01-00-00"},
		},
		{
			"gfs keeps the daily tier, weekly and monthly fulls",
			[]backupKeepRun{
				keepFixture("2026-08-03_01-00-00", true, "", metric.BackupStateSuccess),
				keepFixture("2026-09-14_01-00-00", true, "", metric.BackupStateSuccess),
				keepFixture("2026-09-28_01-00-00", true, "", metric.BackupStateSuccess),
				keepFixture("2026-10-05_01-00-00", true, "", metric.BackupStateSuccess),
				keepFixture("2026-10-12_01-00-00", true, "", metric.BackupStateSuccess),
				keepFixture("2026-10-25_01-00-00", true, "", metric.BackupStateSuccess),
			},
			backupKeepPolicy{daily: 1, weekly: 2, monthly: 2},
			[]string{"2026-10-12_01-00-00", "2026-10-25_01-00-00", "2026-09-28_01-00-00"},
		},
		{
			"the daily tier counts days and keeps every run on them",
			[]backupKeepRun{
				keepFixture("2026-09-27_01-00-10", true, "", ""),
				keepFixture("2026-09-27_15-14-09", true, "", ""),
				keepFixture("2026-09-28_01-00-54", true, "", ""),
				keepFixture("2026-10-01_01-00-13", true, "", ""),
				keepFixture("2026-10-01_11-10-26", true, "", ""),
				keepFixture("2026-10-01_12-05-50", true, "", ""),
			},
			backupKeepPolicy{daily: 2},
			[]string{"2026-10-01_01-00-13", "2026-10-01_11-10-26", "2026-10-01_12-05-50", "2026-09-28_01-00-54"},
		},
		{
			"gating keeps an undrilled bucket point but it fills no quota, so the older drilled point stays",
			[]backupKeepRun{
				drilledFixture(keepFixture("2026-10-05_01-00-00", true, "", ""), true),
				drilledFixture(keepFixture("2026-10-12_01-00-00", true, "", ""), true),
				drilledFixture(keepFixture("2026-10-19_01-00-00", true, "", ""), false),
			},
			backupKeepPolicy{weekly: 2, gated: true},
			[]string{"2026-10-05_01-00-00", "2026-10-12_01-00-00", "2026-10-19_01-00-00"},
		},
		{
			"without gating the same runs fill the quota by newest",
			[]backupKeepRun{
				drilledFixture(keepFixture("2026-10-05_01-00-00", true, "", ""), true),
				drilledFixture(keepFixture("2026-10-12_01-00-00", true, "", ""), true),
				drilledFixture(keepFixture("2026-10-19_01-00-00", true, "", ""), false),
			},
			backupKeepPolicy{weekly: 2},
			[]string{"2026-10-12_01-00-00", "2026-10-19_01-00-00"},
		},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			var actual []string
			for name := range backupKeepSet(test.runs, test.policy, now) {
				actual = append(actual, name)
			}
			slices.Sort(actual)
			slices.Sort(test.expected)
			if !slices.Equal(actual, test.expected) {
				t.Errorf("kept: got %v want %v", actual, test.expected)
			}
		})
	}
}

func TestProbeUtilBackupKeep_PruneBackupRuns(t *testing.T) {
	daily := []string{"2026-10-01_01-00-00", "2026-10-02_01-00-00", "2026-10-03_01-00-00", "2026-10-04_01-00-00", "2026-10-05_01-00-00", "2026-10-06_01-00-00"}
	tests := []struct {
		name     string
		runs     []string
		policy   backupKeepPolicy
		expected []string
	}{
		{"runs outside the keep set go and a directory outside the run form stays", daily, backupKeepPolicy{daily: 4}, append([]string{"notes"}, daily[2:]...)},
		{"no declared window prunes nothing", daily, backupKeepPolicy{}, append([]string{"notes"}, daily...)},
		{"exactly half is pruned", daily[:4], backupKeepPolicy{daily: 2}, append([]string{"notes"}, daily[2:4]...)},
		{"more than half prunes only the oldest half", daily[:4], backupKeepPolicy{daily: 1}, append([]string{"notes"}, daily[2:4]...)},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			dir := t.TempDir()
			for _, name := range append([]string{"notes"}, test.runs...) {
				if err := os.MkdirAll(filepath.Join(dir, name), 0o755); err != nil {
					t.Fatal(err)
				}
			}
			pruneBackupRuns(t.Context(), scribe.SubjectNone, dir, test.policy)
			entries, readErr := os.ReadDir(dir)
			if readErr != nil {
				t.Fatal(readErr)
			}
			var actual []string
			for _, entry := range entries {
				actual = append(actual, entry.Name())
			}
			slices.Sort(test.expected)
			if !slices.Equal(actual, test.expected) {
				t.Errorf("prune: got %v want %v", actual, test.expected)
			}
		})
	}
}

func TestProbeUtilBackupKeep_ReadBackupKeepRuns(t *testing.T) {
	tests := []struct {
		name      string
		artefacts []string
		expected  bool
	}{
		{"a full artefact is a full", []string{"m_full.tar.gz"}, true},
		{"a delta artefact is not", []string{"m_delta.tar.gz"}, false},
		{"a snapshot holds no artefacts so it stands alone as a full", []string{"data.txt"}, true},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			root := t.TempDir()
			run := filepath.Join(root, "2026-10-19_01-00-00")
			if err := os.MkdirAll(run, 0o755); err != nil {
				t.Fatal(err)
			}
			for _, artefact := range test.artefacts {
				if err := os.WriteFile(filepath.Join(run, artefact), nil, 0o644); err != nil {
					t.Fatal(err)
				}
			}
			runs := readBackupKeepRuns(root)
			if len(runs) != 1 || runs[0].full != test.expected {
				t.Errorf("full: got %v want %v", runs, test.expected)
			}
		})
	}
}

func TestProbeUtilBackupKeep_ReadBackupKeepRunsDrills(t *testing.T) {
	tests := []struct {
		name            string
		verdict         string
		expectedDrilled bool
		expectedJudged  bool
	}{
		{"a pass counts as drilled", metric.BackupStateSuccess, true, true},
		{"a skip counts as drilled", metric.BackupStateSkipped, true, true},
		{"a failure is judged but not drilled", metric.BackupStateFailure, false, true},
		{"no verdict is neither", "", false, false},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			root := t.TempDir()
			run := filepath.Join(root, "2026-10-19_01-00-00")
			if err := os.MkdirAll(run, 0o755); err != nil {
				t.Fatal(err)
			}
			if test.verdict != "" {
				if err := writeAtomicDrill(backupDrillPath(run, "secondary"), test.verdict); err != nil {
					t.Fatal(err)
				}
			}
			runs := readBackupKeepRuns(root)
			if len(runs) != 1 || runs[0].drilled != test.expectedDrilled || runs[0].judged != test.expectedJudged {
				t.Errorf("drills: got %+v want drilled [%t] judged [%t]", runs, test.expectedDrilled, test.expectedJudged)
			}
		})
	}
}

func keepFixture(name string, full bool, parent, verdict string) backupKeepRun {
	at, _ := time.ParseInLocation(backupTimestampFormat, name, time.Local)
	return backupKeepRun{name: name, at: at, full: full, parent: parent, verdict: verdict}
}

func drilledFixture(run backupKeepRun, drilled bool) backupKeepRun {
	run.drilled, run.judged = drilled, true
	return run
}
