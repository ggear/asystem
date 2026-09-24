package probe

import (
	"os"
	"path/filepath"
	"testing"

	"supervisor/internal/metric"

	"supervisor/internal/config"
)

func TestProbeUtilBackupTree_RunRootHonoursTheOverrideEnvVar(t *testing.T) {
	tests := []struct {
		name     string
		override string
		expected string
	}{
		{name: "default", override: "", expected: filepath.Join(config.DirServiceHome, treeModule, treeBackupDirectory)},
		{name: "overridden", override: "/mnt/backup", expected: filepath.Join("/mnt/backup", treeModule, treeBackupDirectory)},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			t.Setenv(config.BackupHomeEnvVar, testCase.override)
			if got := backupRunRoot(); got != testCase.expected {
				t.Errorf("backupRunRoot() = %q, want %q", got, testCase.expected)
			}
		})
	}
}

func TestProbeUtilBackupTree_BackupRunsFiltersAndSorts(t *testing.T) {
	root := t.TempDir()
	for _, name := range []string{"2026-09-22_01-00-00", "2026-09-20_01-00-00", "2026-09-21_01-00-00", ".lock", "not-a-run", "2026-09-19_01-00-00.txt"} {
		if err := os.MkdirAll(filepath.Join(root, name), 0o755); err != nil {
			t.Fatalf("mkdir fixture [%s]: %v", name, err)
		}
	}
	if err := os.WriteFile(filepath.Join(root, "2026-09-18_01-00-00"), []byte("not a directory"), 0o644); err != nil {
		t.Fatalf("write fixture file: %v", err)
	}
	got := backupRuns(root)
	expected := []string{"2026-09-20_01-00-00", "2026-09-21_01-00-00", "2026-09-22_01-00-00"}
	if len(got) != len(expected) {
		t.Fatalf("backupRuns() = %v, want %v", got, expected)
	}
	for index, run := range expected {
		if got[index] != run {
			t.Errorf("backupRuns()[%d] = %q, want %q", index, got[index], run)
		}
	}
}

func TestProbeUtilBackupTree_BackupRunsAgainstAMissingRoot(t *testing.T) {
	if got := backupRuns(filepath.Join(t.TempDir(), "missing")); got != nil {
		t.Errorf("backupRuns() = %v, want nil for a root that does not exist", got)
	}
}

func TestProbeUtilBackupTree_ReadBackupRunAssemblesFromScatteredDocuments(t *testing.T) {
	root := t.TempDir()
	runID := "2026-09-22_01-00-00"
	runPath := backupRunPath(root, runID)
	writeStatus := func(path string, document backupSummary) {
		if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
			t.Fatalf("mkdir [%s]: %v", path, err)
		}
		if err := writeAtomic(path, document); err != nil {
			t.Fatalf("write [%s]: %v", path, err)
		}
	}
	writeStatus(stageStatusPath(runPath, metric.BackupStagePrimary), backupSummary{RunID: runID, State: metric.BackupStateSuccess})
	writeStatus(stageStatusPath(runPath, metric.BackupStageSecondary), backupSummary{RunID: runID, State: metric.BackupStateSuccess})
	writeStatus(stageStatusPath(runPath, metric.BackupStageTertiary), backupSummary{RunID: runID, State: metric.BackupStateSuccess, Trigger: metric.BackupTriggerSystem})
	writeStatus(serviceStatusPath(runPath, "plex"), backupSummary{RunID: runID, SuccessBool: true})
	writeStatus(serviceStatusPath(runPath, "postgres"), backupSummary{RunID: runID, SuccessBool: false})

	snapshot := readBackupRun(root, runID)

	if snapshot.staged != 3 {
		t.Errorf("Staged = %d, want 3", snapshot.staged)
	}
	if snapshot.tertiary == nil || snapshot.tertiary.Trigger != metric.BackupTriggerSystem {
		t.Errorf("Tertiary = %+v, want the tertiary document carrying the trigger", snapshot.tertiary)
	}
	if snapshot.trigger != metric.BackupTriggerSystem {
		t.Errorf("Trigger = %q, want %q taken from the first stage document that carries one", snapshot.trigger, metric.BackupTriggerSystem)
	}
	if snapshot.host != nil {
		t.Errorf("Host = %+v, want nil when no run-root status.json was written", snapshot.host)
	}
	if !snapshot.services["plex"] {
		t.Errorf("Services[plex] = false, want true")
	}
	if snapshot.services["postgres"] {
		t.Errorf("Services[postgres] = true, want false")
	}
}

func TestProbeUtilBackupTree_ReadBackupRunTriggerPrefersThePrimaryStageOverLaterOnes(t *testing.T) {
	root := t.TempDir()
	runID := "2026-09-22_01-00-00"
	runPath := backupRunPath(root, runID)
	writeStatus := func(path string, document backupSummary) {
		if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
			t.Fatalf("mkdir [%s]: %v", path, err)
		}
		if err := writeAtomic(path, document); err != nil {
			t.Fatalf("write [%s]: %v", path, err)
		}
	}
	writeStatus(stageStatusPath(runPath, metric.BackupStagePrimary), backupSummary{RunID: runID, State: metric.BackupStateSuccess, Trigger: metric.BackupTriggerManual})
	writeStatus(stageStatusPath(runPath, metric.BackupStageSecondary), backupSummary{RunID: runID, State: metric.BackupStateSuccess, Trigger: metric.BackupTriggerSystem})

	snapshot := readBackupRun(root, runID)

	if snapshot.trigger != metric.BackupTriggerManual {
		t.Errorf("Trigger = %q, want %q taken from primary before secondary", snapshot.trigger, metric.BackupTriggerManual)
	}
}

func TestProbeUtilBackupTree_ReadBackupRunAgainstAnEmptyRunHasNoStages(t *testing.T) {
	root := t.TempDir()
	runID := "2026-09-22_01-00-00"
	if err := os.MkdirAll(backupRunPath(root, runID), 0o755); err != nil {
		t.Fatalf("mkdir run: %v", err)
	}
	snapshot := readBackupRun(root, runID)
	if snapshot.staged != 0 {
		t.Errorf("Staged = %d, want 0", snapshot.staged)
	}
	if snapshot.tertiary != nil {
		t.Errorf("Tertiary = %+v, want nil", snapshot.tertiary)
	}
	if len(snapshot.services) != 0 {
		t.Errorf("Services = %v, want empty", snapshot.services)
	}
}
