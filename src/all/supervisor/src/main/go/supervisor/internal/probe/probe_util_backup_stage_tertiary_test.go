package probe

import (
	"context"
	"os"
	"path/filepath"
	"testing"
	"time"

	"supervisor/internal/metric"
)

func TestProbeUtilBackupStageTertiary_MirrorTotal(t *testing.T) {
	tests := []struct {
		name     string
		expected int64
		known    bool
		value    int64
	}{
		{name: "unknown_when_expected_is_zero", expected: 0, known: false},
		{name: "unknown_when_expected_is_negative", expected: -1, known: false},
		{name: "known_converts_bytes_to_gibibytes", expected: 3 * bytesPerGibibyte, known: true, value: 3},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			got := mirrorTotal(testCase.expected)
			if got.Known() != testCase.known {
				t.Fatalf("mirrorTotal() known = %v, want %v", got.Known(), testCase.known)
			}
			if testCase.known && got.Rounded() != testCase.value {
				t.Errorf("mirrorTotal() = %d, want %d", got.Rounded(), testCase.value)
			}
		})
	}
}

func TestProbeUtilBackupStageTertiary_MirrorPercent(t *testing.T) {
	tests := []struct {
		name     string
		moved    int64
		expected int64
		known    bool
		value    float64
	}{
		{name: "unknown_when_expected_is_zero", moved: 10, expected: 0, known: false},
		{name: "unknown_when_moved_exceeds_expected", moved: 200, expected: 100, known: false},
		{name: "halfway", moved: 50, expected: 100, known: true, value: 50},
		{name: "moved_equal_to_expected_is_complete", moved: 100, expected: 100, known: true, value: 100},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			got := mirrorPercent(testCase.moved, testCase.expected)
			if got.Known() != testCase.known {
				t.Fatalf("mirrorPercent() known = %v, want %v", got.Known(), testCase.known)
			}
			if testCase.known && got.Value() != testCase.value {
				t.Errorf("mirrorPercent() = %v, want %v", got.Value(), testCase.value)
			}
		})
	}
}

func TestProbeUtilBackupStageTertiary_MirrorRemaining(t *testing.T) {
	tests := []struct {
		name     string
		moved    int64
		expected int64
		rate     reading
		known    bool
	}{
		{name: "unknown_when_expected_is_zero", moved: 10, expected: 0, rate: floatReading(10), known: false},
		{name: "unknown_when_moved_exceeds_expected", moved: 200, expected: 100, rate: floatReading(10), known: false},
		{name: "unknown_when_rate_is_unknown", moved: 10, expected: 100, rate: unknownReading(), known: false},
		{name: "unknown_when_rate_is_zero", moved: 10, expected: 100, rate: floatReading(0), known: false},
		{name: "unknown_when_rate_is_negative", moved: 10, expected: 100, rate: floatReading(-1), known: false},
		{name: "known_with_a_positive_rate", moved: 10 * bytesPerMebibyte, expected: 110 * bytesPerMebibyte, rate: floatReading(10), known: true},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			got := mirrorRemaining(testCase.moved, testCase.expected, testCase.rate)
			if got.Known() != testCase.known {
				t.Fatalf("mirrorRemaining() known = %v, want %v", got.Known(), testCase.known)
			}
		})
	}
}

func writeTertiaryStatus(t *testing.T, root, runID string, sizeMB int) {
	t.Helper()
	path := stageStatusPath(backupRunPath(root, runID), metric.BackupStageTertiary)
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		t.Fatalf("mkdir: %v", err)
	}
	if err := writeAtomic(path, backupSummary{RunID: runID, State: metric.BackupStateSuccess, SizeMB: sizeMB}); err != nil {
		t.Fatalf("write: %v", err)
	}
}

func TestProbeUtilBackupStageTertiary_PreviousTertiaryBytesSkipsTheCurrentAndLaterRuns(t *testing.T) {
	root := t.TempDir()
	writeTertiaryStatus(t, root, "2026-09-20_01-00-00", 100)
	writeTertiaryStatus(t, root, "2026-09-21_01-00-00", 200)
	writeTertiaryStatus(t, root, "2026-09-22_01-00-00", 300)
	got := previousTertiaryBytes(root, "2026-09-21_01-00-00")
	expected := int64(100) * 1048576
	if got != expected {
		t.Errorf("previousTertiaryBytes() = %d, want %d taken from the newest run strictly before [2026-09-21_01-00-00]", got, expected)
	}
}

func TestProbeUtilBackupStageTertiary_PreviousTertiaryBytesSkipsAZeroSizedRun(t *testing.T) {
	root := t.TempDir()
	writeTertiaryStatus(t, root, "2026-09-20_01-00-00", 150)
	writeTertiaryStatus(t, root, "2026-09-21_01-00-00", 0)
	got := previousTertiaryBytes(root, "2026-09-22_01-00-00")
	expected := int64(150) * 1048576
	if got != expected {
		t.Errorf("previousTertiaryBytes() = %d, want %d, skipping the zero-sized run", got, expected)
	}
}

func TestProbeUtilBackupStageTertiary_PreviousTertiaryBytesAgainstNoPriorRun(t *testing.T) {
	root := t.TempDir()
	if got := previousTertiaryBytes(root, "2026-09-22_01-00-00"); got != 0 {
		t.Errorf("previousTertiaryBytes() = %d, want 0 with no prior runs", got)
	}
}

func TestProbeUtilBackupStageTertiary_PruneStaleRemovesOnlyEntriesOlderThanTheAge(t *testing.T) {
	dir := t.TempDir()
	fresh := filepath.Join(dir, "fresh")
	stale := filepath.Join(dir, "stale")
	if err := os.Mkdir(fresh, 0o755); err != nil {
		t.Fatalf("mkdir fresh: %v", err)
	}
	if err := os.Mkdir(stale, 0o755); err != nil {
		t.Fatalf("mkdir stale: %v", err)
	}
	old := time.Now().Add(-48 * time.Hour)
	if err := os.Chtimes(stale, old, old); err != nil {
		t.Fatalf("chtimes: %v", err)
	}
	pruneStale(dir, 24*time.Hour)
	if _, err := os.Stat(fresh); err != nil {
		t.Errorf("fresh entry was pruned, want it kept")
	}
	if _, err := os.Stat(stale); !os.IsNotExist(err) {
		t.Errorf("stale entry survived, want it pruned")
	}
}

func TestProbeUtilBackupStageTertiary_PruneStaleAgainstAMissingDirectory(t *testing.T) {
	pruneStale(filepath.Join(t.TempDir(), "missing"), time.Hour)
}

func TestProbeUtilBackupStageTertiary_AttachedHoldsUntilTheStageClaimsADisk(t *testing.T) {
	cases := []struct {
		name     string
		marker   string
		written  bool
		expected bool
	}{
		{name: "no_marker_yet_so_the_disk_is_still_enumerating", expected: true},
		{name: "an_empty_marker_claims_nothing", written: true, expected: true},
	}
	for _, test := range cases {
		t.Run(test.name, func(t *testing.T) {
			stagePath := t.TempDir()
			if test.written {
				if err := os.WriteFile(filepath.Join(stagePath, tertiaryDeviceMarker), []byte(test.marker), 0o644); err != nil {
					t.Fatalf("write marker: %v", err)
				}
			}
			got, reason := attached(context.Background(), stagePath)
			if got != test.expected {
				t.Errorf("attached: got %v want %v", got, test.expected)
			}
			if reason != "" {
				t.Errorf("attached reason: got %q want it silent while the stage has claimed nothing", reason)
			}
		})
	}
}

func TestProbeUtilBackupStageTertiary_MirrorCellsAgreeWithEachOther(t *testing.T) {
	cases := []struct {
		name            string
		moved, expected int64
		expectedCopied  int64
		expectedTotal   int64
		expectedPercent int64
	}{
		{name: "a_complete_mirror_reports_the_same_figure_twice", moved: 1045008384, expected: 1045008384, expectedCopied: 0, expectedTotal: 0, expectedPercent: 100},
		{name: "a_part_mirror_truncates_both_cells_alike", moved: 600 * bytesPerGibibyte, expected: 1000 * bytesPerGibibyte, expectedCopied: 600, expectedTotal: 1000, expectedPercent: 60},
	}
	for _, test := range cases {
		t.Run(test.name, func(t *testing.T) {
			copied := intReading(test.moved / bytesPerGibibyte)
			total := mirrorTotal(test.expected)
			percent := mirrorPercent(test.moved, test.expected)
			if copied.Rounded() != test.expectedCopied || total.Rounded() != test.expectedTotal {
				t.Errorf("mirror cells: got copied %d total %d want %d %d", copied.Rounded(), total.Rounded(), test.expectedCopied, test.expectedTotal)
			}
			if percent.Rounded() != test.expectedPercent {
				t.Errorf("mirrorPercent: got %d want %d", percent.Rounded(), test.expectedPercent)
			}
			if percent.Rounded() == 100 && copied.Rounded() != total.Rounded() {
				t.Errorf("mirror at 100 percent: copied %d disagrees with total %d", copied.Rounded(), total.Rounded())
			}
		})
	}
}

func TestProbeUtilBackupStageTertiary_AHostDeclaringNoBackupDiskSkipsTheStage(t *testing.T) {
	fstab := filepath.Join(t.TempDir(), "fstab")
	if err := os.WriteFile(fstab, []byte("UUID=abc  /share/10  ext4  defaults  0 2\n"), 0o644); err != nil {
		t.Fatalf("write fstab: %v", err)
	}
	original := backupFstabPath
	t.Cleanup(func() { backupFstabPath = original })
	backupFstabPath = fstab
	originalExec := stageExec
	t.Cleanup(func() { stageExec = originalExec })
	stageExec = func(_ context.Context, _ string, _ ...string) (string, int, bool) {
		t.Error("a host with no backup target shelled out, want the stage to end before it powers or mounts anything")
		return "", 1, false
	}

	result, err := runTertiaryStage(t.Context(), stageRequest{Stage: metric.BackupStageTertiary, RunPath: t.TempDir(),
		RunID: "2026-09-22_01-00-00", ConfigPath: filepath.Join(t.TempDir(), "config.json")}, &stageCounters{})
	if err != nil {
		t.Fatalf("runTertiaryStage() error = %v, want a skip rather than a fault", err)
	}
	if !result.skipped {
		t.Errorf("runTertiaryStage() skipped = false, want a host mirroring nowhere to skip the stage")
	}
	if state, success := stageVerdict(nil, err, result.skipped); state != metric.BackupStateSkipped || !success {
		t.Errorf("stageVerdict() = (%q, %v), want (%q, true)", state, success, metric.BackupStateSkipped)
	}
}
