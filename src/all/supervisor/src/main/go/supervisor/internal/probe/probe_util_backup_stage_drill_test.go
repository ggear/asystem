package probe

import (
	"os"
	"path/filepath"
	"testing"
	"time"

	"supervisor/internal/config"
	"supervisor/internal/metric"
)

func TestProbeUtilBackupStageDrill_BackupDrillDue(t *testing.T) {
	now := time.Date(2026, 11, 5, 12, 0, 0, 0, time.Local)
	tests := []struct {
		name     string
		runs     []backupKeepRun
		policy   backupKeepPolicy
		expected []string
	}{
		{
			"a closed week's newest full is due and the current week's is not",
			[]backupKeepRun{keepFixture("2026-10-27_01-00-00", true, "", ""), keepFixture("2026-10-28_01-00-00", true, "", ""), keepFixture("2026-11-03_01-00-00", true, "", "")},
			backupKeepPolicy{weekly: 4}, []string{"2026-10-28_01-00-00"},
		},
		{
			"a drilled point is not due again",
			[]backupKeepRun{drilledFixture(keepFixture("2026-10-28_01-00-00", true, "", ""), true)},
			backupKeepPolicy{weekly: 4}, nil,
		},
		{
			"a point whose drill failed is judged and not retried every night",
			[]backupKeepRun{judgedFixture(keepFixture("2026-10-28_01-00-00", true, "", ""))},
			backupKeepPolicy{weekly: 4}, nil,
		},
		{
			"the first full of a new software generation is due inside the current week",
			[]backupKeepRun{softwareFixture(keepFixture("2026-11-03_01-00-00", true, "", ""), "old", true), softwareFixture(keepFixture("2026-11-04_01-00-00", true, "", ""), "new", false), softwareFixture(keepFixture("2026-11-05_01-00-00", true, "", ""), "new", false)},
			backupKeepPolicy{weekly: 4}, []string{"2026-11-04_01-00-00"},
		},
		{
			"a manifest naming no software starts no generation",
			[]backupKeepRun{keepFixture("2026-11-04_01-00-00", true, "", "")},
			backupKeepPolicy{weekly: 4}, nil,
		},
		{
			"points past the quota are left alone",
			[]backupKeepRun{keepFixture("2026-09-01_01-00-00", true, "", ""), keepFixture("2026-10-28_01-00-00", true, "", "")},
			backupKeepPolicy{weekly: 1}, []string{"2026-10-28_01-00-00"},
		},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			actual := backupDrillDue(test.runs, test.policy, now)
			if len(actual) != len(test.expected) || (len(actual) > 0 && actual[0] != test.expected[0]) {
				t.Errorf("due: got %v want %v", actual, test.expected)
			}
		})
	}
}

func TestProbeUtilBackupStageDrill_ReportReleaseDrills(t *testing.T) {
	tests := []struct {
		name     string
		verdicts map[string]string
		expected int
	}{
		{"failure superseded by a pass", map[string]string{"2026-11-01_01-00-00": metric.BackupStateFailure, "2026-11-02_01-00-00": metric.BackupStateSuccess}, 0},
		{"newest failed", map[string]string{"2026-11-01_01-00-00": metric.BackupStateSuccess, "2026-11-02_01-00-00": metric.BackupStateFailure}, 1},
		{"none", map[string]string{}, 0},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			t.Setenv(config.BackupHomeEnvVar, t.TempDir())
			for run, verdict := range test.verdicts {
				if err := writeAtomicDrill(backupDrillPath(filepath.Join(serviceHomeDir("mod"), run), "primary"), verdict); err != nil {
					t.Fatal(err)
				}
			}
			first, second := reportReleaseDrills("mod"), reportReleaseDrills("mod")
			if first != test.expected || second != test.expected {
				t.Errorf("release drills: got first [%d] second [%d] want [%d] both, a failure stands until a later pass", first, second, test.expected)
			}
		})
	}
}

func TestProbeUtilBackupStageDrill_FlagBackupDrillFailed(t *testing.T) {
	path := filepath.Join(t.TempDir(), "status.json")
	if err := writeAtomic(path, serviceSummary{SuccessBool: true, Kind: "full"}); err != nil {
		t.Fatal(err)
	}
	flagBackupDrillFailed(path)
	document := readSummary[serviceSummary](path)
	if document == nil || !document.SuccessBool || !document.DrillFailedBool || document.Kind != "full" {
		t.Errorf("status: got %+v want the backup kept successful, flagged, and its other fields intact", document)
	}
}

func TestProbeUtilBackupStageDrill_RetainedFailures(t *testing.T) {
	tests := []struct {
		name             string
		software         map[string]string
		verdicts         map[string]string
		expectedRetained bool
		expectedFailing  bool
	}{
		{"a failure behind a newer pass is retained but not failing", map[string]string{"2026-11-01_01-00-00": "s", "2026-11-02_01-00-00": "s"},
			map[string]string{"2026-11-01_01-00-00": metric.BackupStateFailure, "2026-11-02_01-00-00": metric.BackupStateSuccess}, true, false},
		{"a newest failure is failing", map[string]string{"2026-11-01_01-00-00": "s"}, map[string]string{"2026-11-01_01-00-00": metric.BackupStateFailure}, true, true},
		{"a failure on a point naming no software proves nothing", map[string]string{"2026-11-01_01-00-00": ""}, map[string]string{"2026-11-01_01-00-00": metric.BackupStateFailure}, false, false},
		{"skipped is never a failure", map[string]string{"2026-11-01_01-00-00": "s"}, map[string]string{"2026-11-01_01-00-00": metric.BackupStateSkipped}, false, false},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			target := t.TempDir()
			for run, verdict := range test.verdicts {
				plantBackupManifest(t, target, run, backupManifest{Kind: "full", Verdict: metric.BackupStateSuccess, SourceSoftware: test.software[run]})
				if err := writeAtomicDrill(backupDrillPath(filepath.Join(target, run), "secondary"), verdict); err != nil {
					t.Fatal(err)
				}
			}
			if retained, failing := backupDrillRetained(target), backupDrillFailing(target); retained != test.expectedRetained || failing != test.expectedFailing {
				t.Errorf("drills: got retained [%t] failing [%t] want retained [%t] failing [%t]", retained, failing, test.expectedRetained, test.expectedFailing)
			}
		})
	}
}

func writeAtomicDrill(path, verdict string) error {
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		return err
	}
	return writeAtomic(path, backupDrill{Verdict: verdict})
}
