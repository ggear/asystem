package probe

import (
	"bytes"
	"context"
	"fmt"
	"os"
	"path/filepath"
	"testing"
	"time"

	"supervisor/internal/metric"
)

func TestProbeUtilBackupRestore_Replace(t *testing.T) {
	tests := []struct {
		name            string
		verdict         string
		force           bool
		hooks           string
		from            string
		expectedCode    int
		expectedApplied bool
	}{
		{"a bare restore plans and applies nothing", metric.BackupStateSuccess, false, `restore_applied() { echo yes > "$APPLIED"; }`, "", 0, false},
		{"force applies a stopped module through its hook", metric.BackupStateSuccess, true, `RESTORE_SERVICE_STATE=stopped; restore_applied() { echo yes > "$APPLIED"; }`, "", 0, true},
		{"force without restore_applied faults", metric.BackupStateSuccess, true, ":", "", 1, false},
		{"a failing restore_applied faults", metric.BackupStateSuccess, true, `restore_applied() { return 1; }`, "", 1, false},
		{"naming a regressed run needs force", metric.BackupStateRegressed, false, `restore_applied() { echo yes > "$APPLIED"; }`, "2026-11-01_01-00-00", 1, false},
		{"the default run skips a regressed one", metric.BackupStateRegressed, false, `restore_applied() { echo yes > "$APPLIED"; }`, "", 1, false},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			work := t.TempDir()
			home := filepath.Join(work, "mod")
			source := filepath.Join(home, "1.0")
			root := filepath.Join(home, treeBackupDirectory)
			run := "2026-11-01_01-00-00"
			for _, dir := range []string{source, filepath.Join(root, run)} {
				if err := os.MkdirAll(dir, 0o755); err != nil {
					t.Fatal(err)
				}
			}
			if err := os.WriteFile(filepath.Join(root, run, "mod_full.tar.gz"), tarGzipped(t, "x", "y"), 0o644); err != nil {
				t.Fatal(err)
			}
			plantBackupManifest(t, root, run, backupManifest{Kind: "full", Verdict: test.verdict})
			applied := filepath.Join(work, "applied")
			script := filepath.Join(work, "restore.sh")
			if err := os.WriteFile(script, []byte(fmt.Sprintf("APPLIED=%q\nrestore_service_state() { echo \"${RESTORE_SERVICE_STATE:-stopped}\"; }\n%s\n", applied, test.hooks)), 0o644); err != nil {
				t.Fatal(err)
			}
			ctx, cancel := context.WithTimeout(context.Background(), time.Minute)
			defer cancel()
			var stdout, stderr bytes.Buffer
			request := BackupModuleRequest{Arguments: []string{"mod"}, Source: source, Script: script, From: test.from, Force: test.force, NoBackup: true, LockPeriod: time.Second}
			code := BackupModuleRestore(ctx, request, &stdout, &stderr)
			_, statErr := os.Stat(applied)
			if code != test.expectedCode || (statErr == nil) != test.expectedApplied {
				t.Errorf("restore: got code [%d] applied [%t] stdout [%s] stderr [%s] want code [%d] applied [%t]", code, statErr == nil, stdout.String(), stderr.String(), test.expectedCode, test.expectedApplied)
			}
		})
	}
}

func TestProbeUtilBackupRestore_ReportedRestoreLine(t *testing.T) {
	tests := []struct {
		name     string
		text     string
		expected string
	}{
		{"a known label takes the first column", "artifact  [x]", "   artifact  [x]"},
		{"free text is indented under the labels", "something else", "             something else"},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			if actual := reportedRestoreLine(test.text); actual != test.expected {
				t.Errorf("line: got [%q] want [%q]", actual, test.expected)
			}
		})
	}
}

func TestProbeUtilBackupRestore_RecordStage(t *testing.T) {
	tests := []struct {
		name         string
		record       string
		expectedCode int
	}{
		{"an unknown stage is a usage error", "tertiary", 2},
		{"a typo is a usage error", "primry", 2},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			var stdout, stderr bytes.Buffer
			request := BackupModuleRequest{Arguments: []string{"mod"}, Source: t.TempDir(), Script: "restore.sh", Record: test.record}
			if code := BackupModuleDrill(context.Background(), request, &stdout, &stderr); code != test.expectedCode {
				t.Errorf("drill: got code [%d] want [%d]", code, test.expectedCode)
			}
		})
	}
}

func TestProbeUtilBackupRestore_RestoreFiles(t *testing.T) {
	home := filepath.Join(t.TempDir(), "mod")
	source := filepath.Join(home, "1.0")
	target := filepath.Join(source, "config")
	for _, dir := range []string{target} {
		if err := os.MkdirAll(dir, 0o755); err != nil {
			t.Fatal(err)
		}
	}
	for name, content := range map[string]string{"keep/db": "old", "keep/db-wal": "sidecar", "keep/db-2026-11-01": "carry", "stale": "newer"} {
		path := filepath.Join(target, name)
		if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
			t.Fatal(err)
		}
		if err := os.WriteFile(path, []byte(content), 0o644); err != nil {
			t.Fatal(err)
		}
	}
	archive := filepath.Join(t.TempDir(), "a.tar.gz")
	if err := os.WriteFile(archive, tarGzipped(t, "keep/db", "restored"), 0o644); err != nil {
		t.Fatal(err)
	}
	var stdout, stderr bytes.Buffer
	code := BackupModuleRestoreFiles(context.Background(), BackupModuleRequest{
		Arguments: []string{"mod"}, Source: source, Target: target, File: archive, Run: "2026-11-01_01-00-00", Paths: "keep", Carry: []string{"db-*", "*-wal"},
	}, &stdout, &stderr)
	read := func(name string) string {
		data, _ := os.ReadFile(filepath.Join(target, name))
		return string(data)
	}
	if code != 0 || read("keep/db") != "restored" || read("keep/db-2026-11-01") != "carry" || read("keep/db-wal") != "" || read("stale") != "newer" {
		t.Errorf("restore files: got code [%d] db [%s] carried [%s] sidecar [%s] stderr [%s]", code, read("keep/db"), read("keep/db-2026-11-01"), read("keep/db-wal"), stderr.String())
	}
}
