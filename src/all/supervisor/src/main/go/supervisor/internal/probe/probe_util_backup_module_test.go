package probe

import (
	"bytes"
	"context"
	"io"
	"os"
	"path/filepath"
	"strconv"
	"testing"
	"time"

	"supervisor/internal/metric"
)

func TestProbeUtilBackupModule_Verbs(t *testing.T) {
	home := filepath.Join(t.TempDir(), "mod")
	source := filepath.Join(home, "1.0")
	root := filepath.Join(home, treeBackupDirectory)
	if err := os.MkdirAll(filepath.Join(root, "2026-11-01_01-00-00"), 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.MkdirAll(source, 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(root, "2026-11-01_01-00-00", "mod_at_2026-11-01_01-00-00_from_1.0_full.tar.gz"), []byte("x"), 0o644); err != nil {
		t.Fatal(err)
	}
	plantBackupManifest(t, root, "2026-11-01_01-00-00", backupManifest{Kind: "full", Verdict: metric.BackupStateRegressed})
	verb := func(arguments ...string) BackupModuleRequest {
		return BackupModuleRequest{Arguments: arguments, Source: source, Run: "2026-11-02_01-00-00"}
	}
	tests := []struct {
		name           string
		run            func(context.Context, BackupModuleRequest, io.Writer, io.Writer) int
		request        BackupModuleRequest
		expectedCode   int
		expectedStdout string
	}{
		{"parent_names_the_nearest_earlier_full", BackupModuleParent, verb("mod"), 0, "2026-11-01_01-00-00\n"},
		{"epoch_of_a_run", BackupModuleEpoch, BackupModuleRequest{Arguments: []string{"2026-11-01_01-00-00"}}, 0, strconv.FormatInt(backupRunTime("2026-11-01_01-00-00").Unix(), 10) + "\n"},
		{"epoch_of_an_artefact_name_uses_its_trailing_stamp", BackupModuleEpoch, BackupModuleRequest{Arguments: []string{"full-2026-11-01_01-00-00"}}, 0, strconv.FormatInt(backupRunTime("2026-11-01_01-00-00").Unix(), 10) + "\n"},
		{"missing_module_name", BackupModuleParent, BackupModuleRequest{}, 2, ""},
		{"run_without_a_script", BackupModuleRun, verb("mod"), 2, ""},
		{"unresolvable_source", BackupModuleParent, BackupModuleRequest{Arguments: []string{"mod"}, Source: filepath.Join(home, "gone")}, 2, ""},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			var stdout, stderr bytes.Buffer
			if code := testCase.run(context.Background(), testCase.request, &stdout, &stderr); code != testCase.expectedCode || stdout.String() != testCase.expectedStdout {
				t.Fatalf("verb: got code [%d] stdout [%q] stderr [%q] want code [%d] stdout [%q]", code, stdout.String(), stderr.String(), testCase.expectedCode, testCase.expectedStdout)
			}
		})
	}
}

func TestProbeUtilBackupModule_Accept(t *testing.T) {
	const run = "2026-11-01_01-00-00"
	tests := []struct {
		name             string
		accepted         string
		expectedCode     int
		expectedVerdict  string
		expectedAccepted bool
	}{
		{"a regressed run is released and marked accepted", run, 0, metric.BackupStateSuccess, true},
		{"an unknown run changes nothing", "2026-11-09_01-00-00", 1, metric.BackupStateRegressed, false},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			source := filepath.Join(t.TempDir(), "mod", "1.0")
			if err := os.MkdirAll(source, 0o755); err != nil {
				t.Fatal(err)
			}
			root := filepath.Join(filepath.Dir(source), treeBackupDirectory)
			plantBackupManifest(t, root, run, backupManifest{Kind: "full", Verdict: metric.BackupStateRegressed, Evidence: []string{"gone"}})
			code := BackupModuleAccept(t.Context(), BackupModuleRequest{Arguments: []string{"mod", testCase.accepted}, Source: source}, io.Discard, io.Discard)
			manifest, _ := readBackupManifest(root, run)
			if code != testCase.expectedCode || manifest.Verdict != testCase.expectedVerdict || manifest.Accepted != testCase.expectedAccepted {
				t.Errorf("BackupModuleAccept() = code [%d] verdict [%s] accepted [%t], want [%d] [%s] [%t]", code, manifest.Verdict, manifest.Accepted, testCase.expectedCode, testCase.expectedVerdict, testCase.expectedAccepted)
			}
		})
	}
}

func TestProbeUtilBackupModule_LockBackupModule(t *testing.T) {
	t.Setenv(moduleLockHeldVariable, "")
	source := filepath.Join(t.TempDir(), "mod", "1.0")
	var stderr bytes.Buffer
	release, first := lockBackupModule(&stderr, "mod", source, time.Second)
	held := os.Getenv(moduleLockHeldVariable)
	_ = os.Setenv(moduleLockHeldVariable, "")
	_, second := lockBackupModule(&stderr, "mod", source, time.Second)
	_ = os.Setenv(moduleLockHeldVariable, held)
	_, reentrant := lockBackupModule(&stderr, "mod", source, time.Second)
	release()
	_ = os.Setenv(moduleLockHeldVariable, "")
	again, afterRelease := lockBackupModule(&stderr, "mod", source, time.Second)
	again()
	if !first || second || !reentrant || !afterRelease || held != "mod" {
		t.Errorf("lock: got first [%t] second [%t] reentrant [%t] afterRelease [%t] held [%s] want true false true true mod", first, second, reentrant, afterRelease, held)
	}
}

func TestProbeUtilBackupModule_LockBackupModuleRefusesWhenTheLockCannotBeCreated(t *testing.T) {
	t.Setenv(moduleLockHeldVariable, "")
	blocker := filepath.Join(t.TempDir(), "blocker")
	if err := os.WriteFile(blocker, nil, 0o644); err != nil {
		t.Fatal(err)
	}
	var stderr bytes.Buffer
	if _, locked := lockBackupModule(&stderr, "mod", filepath.Join(blocker, "mod", "1.0"), time.Second); locked {
		t.Errorf("lock: got locked [%t] want false", locked)
	}
}
