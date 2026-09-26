package probe

import (
	"context"
	"io"
	"os"
	"path/filepath"
	"slices"
	"testing"
	"time"

	"supervisor/internal/metric"
)

func TestProbeUtilBackupStageTertiary_MirrorTotal(t *testing.T) {
	tests := []struct {
		name     string
		moved    int64
		expected int64
		known    bool
		value    int64
	}{
		{name: "unknown_when_expected_is_zero", expected: 0, known: false},
		{name: "unknown_when_expected_is_negative", expected: -1, known: false},
		{name: "unknown_once_the_copy_has_passed_the_estimate", moved: 89 * bytesPerGibibyte, expected: 79 * bytesPerGibibyte, known: false},
		{name: "known_converts_bytes_to_gibibytes", expected: 3 * bytesPerGibibyte, known: true, value: 3},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			got := mirrorTotal(testCase.moved, testCase.expected)
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

func TestProbeUtilBackupStageTertiary_RsyncSentReadsTheProgressCounter(t *testing.T) {
	tests := []struct {
		name     string
		line     string
		expected int64
		known    bool
	}{
		{name: "a_progress2_line_carries_grouped_digits", line: "  1,234,567,890  12%   45.67MB/s    0:01:23", expected: 1234567890, known: true},
		{name: "a_completed_line_still_parses", line: "85,899,345,920 100%  205.31MB/s    0:06:39 (xfr#12, to-chk=0/99)", expected: 85899345920, known: true},
		{name: "a_stats_line_is_not_progress", line: "Total transferred file size: 1,234 bytes"},
		{name: "a_bare_percentage_with_no_count_is_not_progress", line: "  ...  50%"},
		{name: "an_empty_line_is_not_progress", line: ""},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			got, ok := rsyncSent(test.line)
			if ok != test.known {
				t.Fatalf("rsyncSent(%q) ok = %v, want %v", test.line, ok, test.known)
			}
			if test.known && got != test.expected {
				t.Errorf("rsyncSent(%q) = %d, want %d", test.line, got, test.expected)
			}
		})
	}
}

func TestProbeUtilBackupStageTertiary_ProgressCarriesCompletedSharesPastTheNextInvocation(t *testing.T) {
	progress := &rsyncProgress{}
	if _, err := progress.Write([]byte("  1,000  1%  10MB/s\r  2,000  2%  10MB/s\r")); err != nil {
		t.Fatalf("Write: %v", err)
	}
	if got := progress.bytes(); got != 2000 {
		t.Errorf("bytes() = %d, want the newest counter 2000", got)
	}
	progress.completed(3000)
	if got := progress.bytes(); got != 3000 {
		t.Errorf("bytes() = %d, want the share's own figure 3000 once it finished", got)
	}
	if _, err := progress.Write([]byte("  500  1%  10MB/s\r")); err != nil {
		t.Fatalf("Write: %v", err)
	}
	if got := progress.bytes(); got != 3500 {
		t.Errorf("bytes() = %d, want the finished share plus the one in flight", got)
	}
}

func TestProbeUtilBackupStageTertiary_ProgressSurvivesAChunkSplitMidLine(t *testing.T) {
	progress := &rsyncProgress{}
	for _, chunk := range []string{"  9,", "999  5%  1MB/s", "\r"} {
		if _, err := progress.Write([]byte(chunk)); err != nil {
			t.Fatalf("Write: %v", err)
		}
	}
	if got := progress.bytes(); got != 9999 {
		t.Errorf("bytes() = %d, want 9999 reassembled across chunks", got)
	}
}

func TestProbeUtilBackupStageTertiary_MirrorArgumentsKeepEveryOptionBeforeTheTerminator(t *testing.T) {
	arguments := mirrorArguments("/share/10", "/backup/share/10", "--dry-run", "--info=progress2")
	tail := arguments[len(arguments)-3:]
	if !slices.Equal(tail, []string{"--", "/share/10/", "/backup/share/10/"}) {
		t.Fatalf("mirrorArguments() ends %v, want the terminator then the source then the target, since rsync takes its last argument as the destination and an option after [--] is silently mirrored into a directory of that name", tail)
	}
	for _, option := range []string{"--dry-run", "--info=progress2", "--delete", "--stats"} {
		if slices.Index(arguments, option) > slices.Index(arguments, "--") {
			t.Errorf("mirrorArguments() places [%s] after the terminator, where rsync reads it as a path", option)
		}
	}
	if slices.Contains(mirrorArguments("/share/10", "/backup/share/10"), "--dry-run") {
		t.Errorf("mirrorArguments() carries [--dry-run] with no extra option asked for, so the real mirror would write nothing")
	}
}

func TestProbeUtilBackupStageTertiary_ExpectationSumsTheDryRunAndFailsClosed(t *testing.T) {
	tests := []struct {
		name     string
		exit     int
		expected int64
	}{
		{name: "the_dry_run_of_each_share_is_summed", exit: 0, expected: 2 * 4096},
		{name: "a_dry_run_that_failed_reports_no_total_at_all", exit: 1, expected: 0},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			original := stageStream
			t.Cleanup(func() { stageStream = original })
			dryRuns := 0
			stageStream = func(_ context.Context, _ io.Writer, name string, args ...string) (string, int, bool) {
				share := []string{"/share/10", "/share/11"}[dryRuns]
				if name != "rsync" || !slices.Equal(args, mirrorArguments(share, filepath.Join("/backup", tertiaryShareDirectory, filepath.Base(share)), "--dry-run")) {
					t.Errorf("expectation shelled out to [%s %v], want exactly the mirror arguments plus [--dry-run]", name, args)
				}
				dryRuns++
				return "Number of regular files transferred: 3\nTotal transferred file size: 4,096 bytes\n", test.exit, false
			}
			got := mirrorExpectation(context.Background(), []string{"/share/10", "/share/11"})
			if got != test.expected {
				t.Errorf("mirrorExpectation() = %d, want %d", got, test.expected)
			}
			if test.exit == 0 && dryRuns != 2 {
				t.Errorf("dry runs = %d, want one per share", dryRuns)
			}
		})
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
			total := mirrorTotal(test.moved, test.expected)
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
	originalExec := stageStream
	t.Cleanup(func() { stageStream = originalExec })
	stageStream = func(_ context.Context, _ io.Writer, _ string, _ ...string) (string, int, bool) {
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
