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
	incident := []keepRun{
		keepFixture("2026-10-19_01-00-28", true, "", metric.BackupStateSuccess),
		keepFixture("2026-10-20_01-00-08", false, "2026-10-19_01-00-28", metric.BackupStateSuccess),
		keepFixture("2026-10-21_01-00-08", false, "2026-10-20_01-00-08", metric.BackupStateSuccess),
		keepFixture("2026-10-22_01-00-08", false, "2026-10-21_01-00-08", metric.BackupStateSuccess),
		keepFixture("2026-10-22_08-11-23", false, "2026-10-22_01-00-08", metric.BackupStateRegressed),
	}
	tests := []struct {
		name     string
		runs     []keepRun
		policy   keepPolicy
		expected []string
	}{
		{"empty", nil, keepPolicy{window: time.Hour}, nil},
		{
			"a single run is always kept",
			[]keepRun{keepFixture("2026-10-10_01-00-00", true, "", "")},
			keepPolicy{daily: 1, weekly: 1, monthly: 1},
			[]string{"2026-10-10_01-00-00"},
		},
		{
			"window drops the old full but the closure keeps what kept deltas hang off",
			[]keepRun{
				keepFixture("2026-10-10_01-00-00", true, "", metric.BackupStateSuccess),
				keepFixture("2026-10-20_01-00-00", true, "", metric.BackupStateSuccess),
				keepFixture("2026-10-24_01-00-00", false, "2026-10-20_01-00-00", metric.BackupStateSuccess),
				keepFixture("2026-10-25_01-00-00", false, "2026-10-24_01-00-00", metric.BackupStateSuccess),
			},
			keepPolicy{window: 36 * time.Hour},
			[]string{"2026-10-20_01-00-00", "2026-10-24_01-00-00", "2026-10-25_01-00-00"},
		},
		{
			"a regressed newest run pins the last good run and its full",
			incident,
			keepPolicy{window: time.Hour},
			[]string{"2026-10-19_01-00-28", "2026-10-20_01-00-08", "2026-10-21_01-00-08", "2026-10-22_01-00-08", "2026-10-22_08-11-23"},
		},
		{
			"an accepted regressed run releases the anchor",
			append(slices.Clone(incident[:4]), keepRun{name: "2026-10-22_08-11-23", at: now, full: true, verdict: metric.BackupStateRegressed, accepted: true}),
			keepPolicy{window: time.Hour},
			[]string{"2026-10-22_08-11-23"},
		},
		{
			"a delta with no manifest hangs off the run before it",
			[]keepRun{
				keepFixture("2026-10-10_01-00-00", true, "", ""),
				keepFixture("2026-10-24_01-00-00", false, "", ""),
				keepFixture("2026-10-25_01-00-00", false, "", ""),
			},
			keepPolicy{window: 36 * time.Hour},
			[]string{"2026-10-10_01-00-00", "2026-10-24_01-00-00", "2026-10-25_01-00-00"},
		},
		{
			"gfs keeps the daily tier, weekly and monthly fulls",
			[]keepRun{
				keepFixture("2026-08-03_01-00-00", true, "", metric.BackupStateSuccess),
				keepFixture("2026-09-14_01-00-00", true, "", metric.BackupStateSuccess),
				keepFixture("2026-09-28_01-00-00", true, "", metric.BackupStateSuccess),
				keepFixture("2026-10-05_01-00-00", true, "", metric.BackupStateSuccess),
				keepFixture("2026-10-12_01-00-00", true, "", metric.BackupStateSuccess),
				keepFixture("2026-10-25_01-00-00", true, "", metric.BackupStateSuccess),
			},
			keepPolicy{daily: 1, weekly: 2, monthly: 2},
			[]string{"2026-10-12_01-00-00", "2026-10-25_01-00-00", "2026-09-28_01-00-00"},
		},
		{
			"the daily tier counts days and keeps every run on them",
			[]keepRun{
				keepFixture("2026-09-27_01-00-10", true, "", ""),
				keepFixture("2026-09-27_15-14-09", true, "", ""),
				keepFixture("2026-09-28_01-00-54", true, "", ""),
				keepFixture("2026-10-01_01-00-13", true, "", ""),
				keepFixture("2026-10-01_11-10-26", true, "", ""),
				keepFixture("2026-10-01_12-05-50", true, "", ""),
			},
			keepPolicy{daily: 2},
			[]string{"2026-10-01_01-00-13", "2026-10-01_11-10-26", "2026-10-01_12-05-50", "2026-09-28_01-00-54"},
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
		name          string
		runs          []string
		policy        keepPolicy
		expected      []string
		expectedError bool
	}{
		{"runs outside the keep set go and a directory outside the run form stays", daily, keepPolicy{daily: 4}, append([]string{"notes"}, daily[2:]...), false},
		{"no declared window prunes nothing", daily, keepPolicy{}, append([]string{"notes"}, daily...), false},
		{"exactly half is pruned", daily[:4], keepPolicy{daily: 2}, append([]string{"notes"}, daily[2:4]...), false},
		{"more than half is refused and nothing goes", daily[:4], keepPolicy{daily: 1}, append([]string{"notes"}, daily[:4]...), true},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			dir := t.TempDir()
			for _, name := range append([]string{"notes"}, test.runs...) {
				if err := os.MkdirAll(filepath.Join(dir, name), 0o755); err != nil {
					t.Fatal(err)
				}
			}
			err := pruneBackupRuns(t.Context(), scribe.SubjectNone, dir, test.policy)
			entries, readErr := os.ReadDir(dir)
			if readErr != nil {
				t.Fatal(readErr)
			}
			var actual []string
			for _, entry := range entries {
				actual = append(actual, entry.Name())
			}
			slices.Sort(test.expected)
			if (err != nil) != test.expectedError || !slices.Equal(actual, test.expected) {
				t.Errorf("prune: got error [%v] and %v want error [%t] and %v", err, actual, test.expectedError, test.expected)
			}
		})
	}
}

func TestProbeUtilBackupKeep_ReadKeepRuns(t *testing.T) {
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
			runs := readKeepRuns(root)
			if len(runs) != 1 || runs[0].full != test.expected {
				t.Errorf("full: got %v want %v", runs, test.expected)
			}
		})
	}
}

func keepFixture(name string, full bool, parent, verdict string) keepRun {
	at, _ := time.ParseInLocation(backupTimestampFormat, name, time.Local)
	return keepRun{name: name, at: at, full: full, parent: parent, verdict: verdict}
}
