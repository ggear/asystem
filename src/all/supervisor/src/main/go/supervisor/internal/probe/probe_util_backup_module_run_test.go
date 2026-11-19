package probe

import (
	"bytes"
	"context"
	"os"
	"os/exec"
	"path/filepath"
	"testing"
	"time"

	"supervisor/internal/metric"
)

func TestProbeUtilBackupModuleRun_Lifecycle(t *testing.T) {
	if _, err := exec.LookPath("bash"); err != nil {
		t.Skip("no bash")
	}
	written := `backup_written() { local target="$(dirname "$BACKUP_SOURCE_PATH")/backup/${BACKUP_RUN_TIMESTAMP}/mod_at_${BACKUP_RUN_TIMESTAMP}_from_1.0_full.sql.gz"; mkdir -p "$(dirname "$target")"; echo "$target" >"${BACKUP_STATE_DIR}/target"; printf '%s' "$BACKUP_PAYLOAD" | gzip >"$target.tmp"; }`
	corrupt := `backup_written() { local target="$(dirname "$BACKUP_SOURCE_PATH")/backup/${BACKUP_RUN_TIMESTAMP}/mod_at_${BACKUP_RUN_TIMESTAMP}_from_1.0_full.sql.gz"; mkdir -p "$(dirname "$target")"; echo "$target" >"${BACKUP_STATE_DIR}/target"; echo plain >"$target.tmp"; }`
	tests := []struct {
		name            string
		body            string
		payload         string
		priorVerdict    string
		priorUnits      []backupFingerprintUnit
		skipHours       int
		expectedCode    int
		expectedRuns    int
		expectedVerdict string
	}{
		{"first_backup_succeeds", written, "-- Current Database: `a`\nINSERT;\n", "", nil, 0, 0, 1, metric.BackupStateSuccess},
		{"shrink_flagged_regressed", written, "-- Current Database: `a`\nI;\n", metric.BackupStateSuccess, []backupFingerprintUnit{{"a", 1000}}, 0, 0, 2, metric.BackupStateRegressed},
		{"regressed_prior_is_not_a_baseline", written, "-- Current Database: `a`\nI;\n", metric.BackupStateRegressed, []backupFingerprintUnit{{"a", 1000}}, 0, 0, 2, metric.BackupStateSuccess},
		{"throttled_run_is_skipped", written, "x", metric.BackupStateSuccess, []backupFingerprintUnit{{"a", 1}}, 1000, 0, 1, ""},
		{"failing_hook_leaves_no_run", `backup_written() { return 1; }`, "", "", nil, 0, 1, 0, ""},
		{"nothing_named", `backup_written() { :; }`, "", "", nil, 0, 1, 0, ""},
		{"corrupt_archive_leaves_no_run", corrupt, "", "", nil, 0, 1, 0, ""},
		{"failing_completed_hook_fails_the_run_and_keeps_the_archive", written + "\nbackup_completed() { return 1; }", "-- Current Database: `a`\nINSERT;\n", "", nil, 0, 1, 1, metric.BackupStateSuccess},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			dir := t.TempDir()
			source := filepath.Join(dir, "mod", "1.0")
			if err := os.MkdirAll(source, 0o755); err != nil {
				t.Fatal(err)
			}
			root := filepath.Join(dir, "mod", treeBackupDirectory)
			if testCase.priorUnits != nil {
				recent := time.Now().Add(-2 * time.Hour).Format(backupTimestampFormat)
				plantBackupManifest(t, root, recent, backupManifest{Kind: "full", Verdict: testCase.priorVerdict, Fingerprint: testCase.priorUnits})
				if err := os.WriteFile(filepath.Join(root, recent, "mod_at_"+recent+"_from_1.0_full.sql.gz"), []byte("x"), 0o644); err != nil {
					t.Fatal(err)
				}
			}
			replaced := filepath.Join(dir, "mod", "replaced", "2026-11-01_01-00-00")
			if err := os.MkdirAll(replaced, 0o755); err != nil {
				t.Fatal(err)
			}
			script := filepath.Join(dir, "backup.sh")
			if err := os.WriteFile(script, []byte("backup_completed() { echo completed >>\""+dir+"/trail\"; }\n"+testCase.body+"\n"), 0o755); err != nil {
				t.Fatal(err)
			}
			t.Setenv("BACKUP_PAYLOAD", testCase.payload)
			t.Setenv(moduleLockHeldVariable, "")
			request := BackupModuleRequest{Arguments: []string{"mod"}, Source: source, Script: script, SkipPeriod: time.Duration(testCase.skipHours) * time.Hour, ShrinkPercent: 20, LockPeriod: time.Second, TimeoutPeriod: time.Hour}
			var stdout, stderr bytes.Buffer
			if code := BackupModuleRun(context.Background(), request, &stdout, &stderr); code != testCase.expectedCode {
				t.Fatalf("BackupModuleRun: got code [%d] want [%d] stdout [%s] stderr [%s]", code, testCase.expectedCode, stdout.String(), stderr.String())
			}
			runs := backupRuns(root)
			if len(runs) != testCase.expectedRuns {
				t.Fatalf("BackupModuleRun: got runs %v want [%d]", runs, testCase.expectedRuns)
			}
			_, replacedErr := os.Stat(replaced)
			if kept := replacedErr == nil; kept == (testCase.expectedVerdict == metric.BackupStateSuccess) {
				t.Errorf("BackupModuleRun: got replaced kept [%t] want [%t] for verdict [%s]", kept, testCase.expectedVerdict != metric.BackupStateSuccess, testCase.expectedVerdict)
			}
			if testCase.expectedVerdict == "" {
				return
			}
			manifest, found := readBackupManifest(root, runs[len(runs)-1])
			if !found || manifest.Verdict != testCase.expectedVerdict {
				t.Fatalf("BackupModuleRun: got manifest %v found %t want verdict [%s]", manifest, found, testCase.expectedVerdict)
			}
		})
	}
}

func TestProbeUtilBackupModuleRun_EngineRestartsWhatWasRunning(t *testing.T) {
	if _, err := exec.LookPath("bash"); err != nil {
		t.Skip("no bash")
	}
	tests := []struct {
		name           string
		wasRunning     bool
		noRestart      bool
		startWorks     bool
		expectedStarts int
		expectedCode   int
	}{
		{name: "a_service_that_was_running_and_was_stopped_is_started", wasRunning: true, startWorks: true, expectedStarts: 1},
		{name: "a_service_that_was_not_running_is_left_alone", expectedStarts: 0},
		{name: "the_caller_can_decline_the_restart", wasRunning: true, noRestart: true, expectedStarts: 0},
		{name: "a_service_that_will_not_start_fails_the_run_after_every_try", wasRunning: true, expectedStarts: backupRestartTries, expectedCode: 1},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			dir := t.TempDir()
			source := filepath.Join(dir, "mod", "1.0")
			if err := os.MkdirAll(source, 0o755); err != nil {
				t.Fatal(err)
			}
			calls, starts, started := 0, 0, false
			runningOriginal, startOriginal, waitOriginal := backupServiceRunning, backupServiceStart, backupRestartWait
			t.Cleanup(func() {
				backupServiceRunning, backupServiceStart, backupRestartWait = runningOriginal, startOriginal, waitOriginal
			})
			backupRestartWait = time.Millisecond
			backupServiceRunning = func(context.Context, string) bool {
				calls++
				if calls == 1 {
					return testCase.wasRunning
				}
				return started
			}
			backupServiceStart = func(context.Context, string) error {
				starts++
				started = testCase.startWorks
				return nil
			}
			body := `backup_written() { local target="$(dirname "$BACKUP_SOURCE_PATH")/backup/${BACKUP_RUN_TIMESTAMP}/mod_at_${BACKUP_RUN_TIMESTAMP}_from_1.0_full.sql.gz"; mkdir -p "$(dirname "$target")"; echo "$target" >"${BACKUP_STATE_DIR}/target"; echo x | gzip >"$target.tmp"; }`
			script := filepath.Join(dir, "backup.sh")
			if err := os.WriteFile(script, []byte(body+"\n"), 0o755); err != nil {
				t.Fatal(err)
			}
			t.Setenv(moduleLockHeldVariable, "")
			request := BackupModuleRequest{Arguments: []string{"mod"}, Source: source, Script: script, ShrinkPercent: 20, LockPeriod: time.Second, TimeoutPeriod: time.Hour, NoRestart: testCase.noRestart}
			var stdout, stderr bytes.Buffer
			if code := BackupModuleRun(context.Background(), request, &stdout, &stderr); code != testCase.expectedCode {
				t.Fatalf("BackupModuleRun: got code [%d] want [%d] stderr [%s]", code, testCase.expectedCode, stderr.String())
			}
			if starts != testCase.expectedStarts {
				t.Fatalf("starts: got %d want %d", starts, testCase.expectedStarts)
			}
		})
	}
}
