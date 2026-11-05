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

	"supervisor/internal/config"
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

func TestProbeUtilBackupManifest_VersionedModule(t *testing.T) {
	tests := []struct {
		name     string
		script   string
		expected string
	}{
		{"the hook output is recorded", "backup_versioned() { printf '18-2.30\\nextra\\n'; }", "18-2.30"},
		{"no hook falls back to the version", ":", "9.9"},
		{"an empty hook falls back to the version", "backup_versioned() { :; }", "9.9"},
		{"a failing hook falls back to the version", "backup_versioned() { echo 18; return 1; }", "9.9"},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			script := filepath.Join(t.TempDir(), "backup.sh")
			if err := os.WriteFile(script, []byte(test.script+"\n"), 0o644); err != nil {
				t.Fatal(err)
			}
			var stderr bytes.Buffer
			if actual := versionedModule(context.Background(), moduleHooks{script: script}, &stderr, "9.9"); actual != test.expected {
				t.Errorf("software: got [%s] want [%s]", actual, test.expected)
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

func TestProbeUtilBackupDrill_RestoreFiles(t *testing.T) {
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

func TestProbeUtilBackupDrill_BackupDrillDue(t *testing.T) {
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

func TestProbeUtilBackupDrill_ReportReleaseDrills(t *testing.T) {
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

func TestProbeUtilBackupDrill_DemoteBackupService(t *testing.T) {
	path := filepath.Join(t.TempDir(), "status.json")
	if err := writeAtomic(path, backupSummary{SuccessBool: true}); err != nil {
		t.Fatal(err)
	}
	target := t.TempDir()
	if err := writeAtomicDrill(backupDrillPath(filepath.Join(target, "2026-11-01_01-00-00"), "secondary"), metric.BackupStateFailure); err != nil {
		t.Fatal(err)
	}
	if err := writeAtomicDrill(backupDrillPath(filepath.Join(target, "2026-11-02_01-00-00"), "secondary"), metric.BackupStateSuccess); err != nil {
		t.Fatal(err)
	}
	if !backupDrillRetained(target) || backupDrillFailing(target) {
		t.Fatal("retained failure not seen behind a newer pass")
	}
	demoteBackupService(path)
	if document := readBackupSummary(path); document == nil || document.SuccessBool {
		t.Errorf("status: got %+v want success false", document)
	}
}

func writeAtomicDrill(path, verdict string) error {
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		return err
	}
	return writeAtomic(path, backupDrill{Verdict: verdict})
}
