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

func TestProbeUtilBackupMerge_Merge(t *testing.T) {
	tests := []struct {
		name           string
		force          bool
		mergeCatchesUp bool
		hooks          string
		expectedCode   int
		expectedMerged string
	}{
		{"a bare merge plans and writes nothing", false, true, "", 0, ""},
		{"force merges only the units that differ", true, true, "", 0, "b/1\n"},
		{"force faults when live never catches up", true, false, "", 1, "b/1\n"},
		{"a module without restore_merged is refused", true, true, "unset -f restore_merged", 1, ""},
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
			plantBackupManifest(t, root, run, backupManifest{Kind: "full", Verdict: metric.BackupStateSuccess})
			live, log := filepath.Join(work, "live"), filepath.Join(work, "merged.log")
			if err := os.WriteFile(live, []byte("a/1 5\nb/1 1\n"), 0o644); err != nil {
				t.Fatal(err)
			}
			update := ":"
			if test.mergeCatchesUp {
				update = fmt.Sprintf(`printf 'a/1 5\nb/1 3\n' > %q`, live)
			}
			script := filepath.Join(work, "restore.sh")
			body := fmt.Sprintf(`backup_fingerprinted() { if [ "$1" = live ]; then cat %q; else printf 'a/1 5\nb/1 3\n'; fi; }
restore_staged() { echo scratch; }
restore_sealed() { :; }
restore_teardown() { :; }
restore_live_address() { echo live; }
restore_merged() { echo "$1" >> %q; %s; }
%s
`, live, log, update, test.hooks)
			if err := os.WriteFile(script, []byte(body), 0o644); err != nil {
				t.Fatal(err)
			}
			t.Setenv("RESTORE_VERIFY_ATTEMPTS", "2")
			t.Setenv("RESTORE_VERIFY_SLEEP", "0")
			ctx, cancel := context.WithTimeout(context.Background(), time.Minute)
			defer cancel()
			var stdout, stderr bytes.Buffer
			code := BackupModuleMerge(ctx, BackupModuleRequest{Arguments: []string{"mod"}, Source: source, Script: script, Force: test.force, NoBackup: true, LockPeriod: time.Second}, &stdout, &stderr)
			merged, _ := os.ReadFile(log)
			if code != test.expectedCode || string(merged) != test.expectedMerged {
				t.Errorf("merge: got code [%d] merged [%q] stdout [%s] stderr [%s] want code [%d] merged [%q]", code, merged, stdout.String(), stderr.String(), test.expectedCode, test.expectedMerged)
			}
		})
	}
}
