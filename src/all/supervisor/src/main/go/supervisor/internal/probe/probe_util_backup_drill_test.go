package probe

import (
	"archive/tar"
	"bytes"
	"compress/gzip"
	"context"
	"fmt"
	"os"
	"path/filepath"
	"testing"
	"time"

	"supervisor/internal/metric"
)

func TestProbeUtilBackupDrill_Drill(t *testing.T) {
	tests := []struct {
		name            string
		manifestBytes   int64
		script          string
		expectedCode    int
		expectedVerdict string
	}{
		{"a held manifest drills green", 5, ":", 0, metric.BackupStateSuccess},
		{"a manifest wanting more than the artifact holds fails", 50, ":", 1, metric.BackupStateFailure},
		{"a scratch that moves after sealing fails", 5, `restore_sealed() { printf more >> "$1/data/a.txt"; }`, 1, metric.BackupStateFailure},
		{"a truncated artifact fails by name", 5, ":", 1, metric.BackupStateFailure},
		{"a failing module check fails", 5, `restore_checked() { return 1; }`, 1, metric.BackupStateFailure},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			home := filepath.Join(t.TempDir(), "mod")
			source := filepath.Join(home, "1.0")
			root := filepath.Join(home, treeBackupDirectory)
			if err := os.MkdirAll(source, 0o755); err != nil {
				t.Fatal(err)
			}
			run := "2026-11-01_01-00-00"
			if err := os.MkdirAll(filepath.Join(root, run), 0o755); err != nil {
				t.Fatal(err)
			}
			if err := os.WriteFile(filepath.Join(root, run, "mod_full.tar.gz"), tarGzipped(t, "data/a.txt", "hello"), 0o644); err != nil {
				t.Fatal(err)
			}
			plantBackupManifest(t, root, run, backupManifest{Kind: "full", Verdict: metric.BackupStateSuccess, SourceSoftware: "1.0", Fingerprint: []backupFingerprintUnit{{name: "data", count: test.manifestBytes}}})
			script := filepath.Join(t.TempDir(), "restore.sh")
			if err := os.WriteFile(script, []byte(test.script+"\n"), 0o644); err != nil {
				t.Fatal(err)
			}
			if test.name == "a truncated artifact fails by name" {
				artefact := filepath.Join(root, run, "mod_full.tar.gz")
				whole, _ := os.ReadFile(artefact)
				if err := os.WriteFile(artefact, whole[:len(whole)/2], 0o644); err != nil {
					t.Fatal(err)
				}
			}
			var stdout, stderr bytes.Buffer
			ctx, cancel := context.WithTimeout(context.Background(), time.Minute)
			defer cancel()
			code := BackupModuleDrill(ctx, BackupModuleRequest{Arguments: []string{"mod"}, Source: source, Script: script, Record: "secondary", LockPeriod: time.Second}, &stdout, &stderr)
			drill, found := readBackupDrill(backupDrillPath(filepath.Join(root, run), "secondary"))
			if code != test.expectedCode || !found || drill.Verdict != test.expectedVerdict {
				t.Errorf("drill: got code [%d] verdict [%s] found [%t] stdout [%s] stderr [%s] want code [%d] verdict [%s]", code, drill.Verdict, found, stdout.String(), stderr.String(), test.expectedCode, test.expectedVerdict)
			}
		})
	}
}

func TestProbeUtilBackupDrill_Compatible(t *testing.T) {
	tests := []struct {
		name     string
		point    backupManifest
		expected bool
	}{
		{"same software", backupManifest{SourceSoftware: "18-2.30"}, true},
		{"software differs", backupManifest{SourceSoftware: "18-2.20"}, false},
		{"a manifest naming no software is skipped", backupManifest{SourceVersion: "1"}, false},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			if actual := backupCompatible(test.point, "18-2.30"); actual != test.expected {
				t.Errorf("compatible: got [%t] want [%t]", actual, test.expected)
			}
		})
	}
}

func TestProbeUtilBackupDrill_VersionedHook(t *testing.T) {
	tests := []struct {
		name            string
		recorded        string
		expectedCode    int
		expectedVerdict string
	}{
		{"software matching the hook is drilled", "new", 1, metric.BackupStateFailure},
		{"software differing from the hook is skipped", "old", 0, metric.BackupStateSkipped},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			home := filepath.Join(t.TempDir(), "mod")
			source := filepath.Join(home, "2.0")
			root := filepath.Join(home, treeBackupDirectory)
			run := "2026-11-01_01-00-00"
			for _, dir := range []string{filepath.Join(root, run), source} {
				if err := os.MkdirAll(dir, 0o755); err != nil {
					t.Fatal(err)
				}
			}
			if err := os.WriteFile(filepath.Join(root, run, "mod_full.tar.gz"), tarGzipped(t, "data/a.txt", "hello"), 0o644); err != nil {
				t.Fatal(err)
			}
			plantBackupManifest(t, root, run, backupManifest{Kind: "full", Verdict: metric.BackupStateSuccess, SourceSoftware: test.recorded, Fingerprint: []backupFingerprintUnit{{name: "data", count: 5}}})
			scripts := t.TempDir()
			if err := os.WriteFile(filepath.Join(scripts, "restore.sh"), []byte("restore_staged() { return 1; }\n"), 0o644); err != nil {
				t.Fatal(err)
			}
			if err := os.WriteFile(filepath.Join(scripts, "backup.sh"), []byte("backup_versioned() { echo new; }\n"), 0o644); err != nil {
				t.Fatal(err)
			}
			var stdout, stderr bytes.Buffer
			code := BackupModuleDrill(context.Background(), BackupModuleRequest{Arguments: []string{"mod"}, Source: source, Script: filepath.Join(scripts, "restore.sh"), Record: "secondary", LockPeriod: time.Second}, &stdout, &stderr)
			drill, found := readBackupDrill(backupDrillPath(filepath.Join(root, run), "secondary"))
			if code != test.expectedCode || !found || drill.Verdict != test.expectedVerdict {
				t.Errorf("drill: got code [%d] verdict [%s] found [%t] stderr [%s] want code [%d] verdict [%s]", code, drill.Verdict, found, stderr.String(), test.expectedCode, test.expectedVerdict)
			}
		})
	}
}

func TestProbeUtilBackupDrill_StagingFailureTearsScratchDown(t *testing.T) {
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
	plantBackupManifest(t, root, run, backupManifest{Kind: "full", Verdict: metric.BackupStateSuccess, SourceSoftware: "1.0"})
	torn := filepath.Join(work, "torn")
	script := filepath.Join(work, "restore.sh")
	hooks := fmt.Sprintf("restore_staged() { return 1; }\nrestore_teardown() { echo \"$1\" > %q; }\n", torn)
	if err := os.WriteFile(script, []byte(hooks), 0o644); err != nil {
		t.Fatal(err)
	}
	var stdout, stderr bytes.Buffer
	code := BackupModuleDrill(context.Background(), BackupModuleRequest{Arguments: []string{"mod"}, Source: source, Script: script, LockPeriod: time.Second}, &stdout, &stderr)
	data, _ := os.ReadFile(torn)
	if code != 1 || len(data) == 0 {
		t.Errorf("staging failure: got code [%d] teardown arg [%q] want code 1 and the scratch directory handed to restore_teardown", code, data)
	}
}

func tarGzipped(t *testing.T, name, content string) []byte {
	t.Helper()
	var buffer bytes.Buffer
	zipped := gzip.NewWriter(&buffer)
	archive := tar.NewWriter(zipped)
	if err := archive.WriteHeader(&tar.Header{Name: name, Mode: 0o644, Size: int64(len(content)), Typeflag: tar.TypeReg}); err != nil {
		t.Fatal(err)
	}
	if _, err := archive.Write([]byte(content)); err != nil {
		t.Fatal(err)
	}
	if archive.Close() != nil || zipped.Close() != nil {
		t.Fatal("archive not closed")
	}
	return buffer.Bytes()
}

func softwareFixture(run backupKeepRun, software string, judged bool) backupKeepRun {
	run.software, run.judged = software, judged
	return run
}

func judgedFixture(run backupKeepRun) backupKeepRun {
	run.judged = true
	return run
}
