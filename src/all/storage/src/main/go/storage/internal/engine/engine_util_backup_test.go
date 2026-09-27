package engine

import (
	"encoding/json"
	"os"
	"path/filepath"
	"testing"
)

func TestEngineUtilBackup_NewestBackupReading(t *testing.T) {
	cases := []struct {
		name          string
		runs          map[string]*tertiaryStatus
		want          *backupReading
		expectedError bool
	}{
		{
			name: "newest of several runs wins",
			runs: map[string]*tertiaryStatus{
				"2026-09-01_01-00-00": {DiskTotalMB: 100, DiskUsedMB: 50, FinishedTS: "2026-09-01T02:00:00Z"},
				"2026-09-25_01-00-00": {DiskTotalMB: 200, DiskUsedMB: 80, FinishedTS: "2026-09-25T02:00:00Z"},
			},
			want: &backupReading{RunID: "2026-09-25_01-00-00", MeasuredTS: "2026-09-25T02:00:00Z", TotalBytes: 200 * 1024 * 1024, UsedBytes: 80 * 1024 * 1024},
		},
		{
			name: "a newer run with no tertiary document falls to the next, not to zero",
			runs: map[string]*tertiaryStatus{
				"2026-09-01_01-00-00": {DiskTotalMB: 100, DiskUsedMB: 50, FinishedTS: "2026-09-01T02:00:00Z"},
				"2026-09-25_01-00-00": nil,
			},
			want: &backupReading{RunID: "2026-09-01_01-00-00", MeasuredTS: "2026-09-01T02:00:00Z", TotalBytes: 100 * 1024 * 1024, UsedBytes: 50 * 1024 * 1024},
		},
		{
			name: "a disk_total_mb of zero is not a reading",
			runs: map[string]*tertiaryStatus{
				"2026-09-25_01-00-00": {DiskTotalMB: 0, DiskUsedMB: 0, FinishedTS: "2026-09-25T02:00:00Z"},
			},
			want: nil,
		},
		{
			name: "an empty tree",
			runs: map[string]*tertiaryStatus{},
			want: nil,
		},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			root := t.TempDir()
			for run, status := range c.runs {
				dir := filepath.Join(root, run, "stage", "tertiary")
				if err := os.MkdirAll(dir, 0o755); err != nil {
					t.Fatal(err)
				}
				if status == nil {
					continue
				}
				data, err := json.Marshal(status)
				if err != nil {
					t.Fatal(err)
				}
				if err := os.WriteFile(filepath.Join(dir, "status.json"), data, 0o644); err != nil {
					t.Fatal(err)
				}
			}
			got := newestBackupReading(root)
			assertBackupReading(t, got, c.want)
		})
	}
}

func TestEngineUtilBackup_NewestBackupReading_UnparseableDocument(t *testing.T) {
	root := t.TempDir()
	dir := filepath.Join(root, "2026-09-25_01-00-00", "stage", "tertiary")
	if err := os.MkdirAll(dir, 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(dir, "status.json"), []byte("not json"), 0o644); err != nil {
		t.Fatal(err)
	}
	if got := newestBackupReading(root); got != nil {
		t.Errorf("got %+v want nil", got)
	}
}

func assertBackupReading(t *testing.T, got, want *backupReading) {
	t.Helper()
	if (got == nil) != (want == nil) {
		t.Fatalf("got %+v want %+v", got, want)
	}
	if got == nil {
		return
	}
	if *got != *want {
		t.Errorf("got %+v want %+v", *got, *want)
	}
}
