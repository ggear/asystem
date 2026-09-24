package probe

import (
	"context"
	"errors"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"supervisor/internal/config"
	"supervisor/internal/metric"
)

func TestProbeUtilBackupStage_DirectoryStatsSumsFilesAndSizeRecursively(t *testing.T) {
	dir := t.TempDir()
	if err := os.MkdirAll(filepath.Join(dir, "nested"), 0o755); err != nil {
		t.Fatalf("mkdir nested: %v", err)
	}
	if err := os.WriteFile(filepath.Join(dir, "a.txt"), make([]byte, 1048576), 0o644); err != nil {
		t.Fatalf("write a.txt: %v", err)
	}
	if err := os.WriteFile(filepath.Join(dir, "nested", "b.txt"), make([]byte, 2*1048576), 0o644); err != nil {
		t.Fatalf("write b.txt: %v", err)
	}
	files, sizeMB := directoryStats(dir)
	if files != 2 {
		t.Errorf("files = %d, want 2", files)
	}
	if sizeMB != 3 {
		t.Errorf("sizeMB = %d, want 3", sizeMB)
	}
}

func TestProbeUtilBackupStage_DirectoryStatsAgainstAMissingDirectory(t *testing.T) {
	files, sizeMB := directoryStats(filepath.Join(t.TempDir(), "missing"))
	if files != 0 || sizeMB != 0 {
		t.Errorf("directoryStats() = (%d, %d), want (0, 0) against a missing directory", files, sizeMB)
	}
}

func TestProbeUtilBackupStage_VerdictRanksTheHaltCausesAboveTheRunResult(t *testing.T) {
	tests := []struct {
		name            string
		cause           error
		runErr          error
		skipped         bool
		expectedState   string
		expectedSuccess bool
	}{
		{name: "a_timeout_outranks_a_clean_return", cause: errStageTimedOut,
			expectedState: metric.BackupStateTimeout, expectedSuccess: false},
		{name: "a_timeout_outranks_a_failure", cause: errStageTimedOut, runErr: errors.New("rsync exited [23]"),
			expectedState: metric.BackupStateTimeout, expectedSuccess: false},
		{name: "an_external_stop_reads_as_stopped", cause: errStageStopped,
			expectedState: metric.BackupStateStopped, expectedSuccess: false},
		{name: "a_detached_disk_reads_as_stopped", cause: errStageDetached,
			expectedState: metric.BackupStateStopped, expectedSuccess: false},
		{name: "a_cancelled_parent_is_an_ordinary_failure", cause: context.Canceled, runErr: errors.New("share vanished"),
			expectedState: metric.BackupStateFailure, expectedSuccess: false},
		{name: "a_failure_outranks_a_skip", runErr: errors.New("service backup failed"), skipped: true,
			expectedState: metric.BackupStateFailure, expectedSuccess: false},
		{name: "a_skip_is_a_success", skipped: true,
			expectedState: metric.BackupStateSkipped, expectedSuccess: true},
		{name: "nothing_wrong_is_a_success",
			expectedState: metric.BackupStateSuccess, expectedSuccess: true},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			state, success := stageVerdict(testCase.cause, testCase.runErr, testCase.skipped)
			if state != testCase.expectedState || success != testCase.expectedSuccess {
				t.Errorf("stageVerdict() = (%q, %t), want (%q, %t)", state, success, testCase.expectedState, testCase.expectedSuccess)
			}
		})
	}
}

func TestProbeUtilBackupStage_RunStageWritesTheVerdictItResolved(t *testing.T) {
	tests := []struct {
		name            string
		stage           metric.BackupStage
		expires         time.Duration
		expectedState   string
		expectedSuccess bool
		expectedError   bool
	}{
		{name: "a_primary_stage_with_nothing_enrolled_succeeds", stage: metric.BackupStagePrimary, expires: time.Hour,
			expectedState: metric.BackupStateSuccess, expectedSuccess: true},
		{name: "an_unknown_stage_fails_and_still_writes_its_document", stage: metric.BackupStage("quaternary"),
			expectedState: metric.BackupStateFailure, expectedError: true},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			home := t.TempDir()
			t.Setenv(config.BackupHomeEnvVar, home)
			configPath := filepath.Join(home, "config.json")
			if err := os.WriteFile(configPath, []byte(`{"asystem":{"host":"testhost"}}`), 0o644); err != nil {
				t.Fatalf("write config: %v", err)
			}
			runPath := filepath.Join(home, "supervisor", "backup", "2026-09-22_01-00-00")
			request := stageRequest{Stage: testCase.stage, RunID: "2026-09-22_01-00-00", RunPath: runPath,
				Trigger: metric.BackupTriggerManual, ConfigPath: configPath}
			if testCase.expires > 0 {
				request.Expires = time.Now().Add(testCase.expires)
			}
			err := runStage(t.Context(), request)
			if (err != nil) != testCase.expectedError {
				t.Fatalf("runStage() error = %v, expectedError %v", err, testCase.expectedError)
			}
			document := readBackupSummary(stageStatusPath(runPath, testCase.stage))
			if document == nil {
				t.Fatalf("runStage() wrote no stage document under [%s]", runPath)
			}
			if document.State != testCase.expectedState || document.SuccessBool != testCase.expectedSuccess {
				t.Errorf("document = (%q, %t), want (%q, %t)", document.State, document.SuccessBool,
					testCase.expectedState, testCase.expectedSuccess)
			}
			if document.RunID != request.RunID || document.Trigger != metric.BackupTriggerManual {
				t.Errorf("document run [%q] trigger [%q], want [%q] and [%q]", document.RunID, document.Trigger,
					request.RunID, metric.BackupTriggerManual)
			}
			if document.StartedTS == "" || document.FinishedTS == "" {
				t.Errorf("document started [%q] finished [%q], want both stamped", document.StartedTS, document.FinishedTS)
			}
			if document.ExpiresTS != "" {
				t.Errorf("document expires [%q], want the liveness cleared once the stage has finished", document.ExpiresTS)
			}
			if testCase.expires > 0 && document.TimeoutHours != int(testCase.expires.Hours()) {
				t.Errorf("document timeout [%d] hours, want [%d] read back from the run deadline",
					document.TimeoutHours, int(testCase.expires.Hours()))
			}
		})
	}
}

func TestProbeUtilBackupStage_RealStageExecTakesTheExitStatusOfACommandLeavingAChildOnItsPipes(t *testing.T) {
	out, code, abandoned := realStageExec(context.Background(), "sh", "-c", "echo started; sleep 3 & exit 0")
	if code != 0 || abandoned {
		t.Errorf("realStageExec: got code %d abandoned %v want 0 false", code, abandoned)
	}
	if !strings.Contains(out, "started") {
		t.Errorf("realStageExec output: got %q want it to contain started", out)
	}
}
