package probe

import (
	"context"
	"io"
	"os"
	"path/filepath"
	"slices"
	"testing"
	"time"

	"supervisor/internal/config"
	"supervisor/internal/metric"
)

func TestProbeUtilBackupStageTertiary_ProgressTotal(t *testing.T) {
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
		{name: "known_converts_bytes_to_mebibytes_for_the_formatter", expected: 3 * bytesPerGibibyte, known: true, value: 3 * mebibytesPerGibibyte},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			got := progressTotal(testCase.moved, testCase.expected)
			if got.Known() != testCase.known {
				t.Fatalf("progressTotal() known = %v, want %v", got.Known(), testCase.known)
			}
			if testCase.known && got.Rounded() != testCase.value {
				t.Errorf("progressTotal() = %d, want %d", got.Rounded(), testCase.value)
			}
		})
	}
}

func TestProbeUtilBackupStageTertiary_ProgressPercent(t *testing.T) {
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
			got := progressPercent(testCase.moved, testCase.expected)
			if got.Known() != testCase.known {
				t.Fatalf("progressPercent() known = %v, want %v", got.Known(), testCase.known)
			}
			if testCase.known && got.Value() != testCase.value {
				t.Errorf("progressPercent() = %v, want %v", got.Value(), testCase.value)
			}
		})
	}
}

func TestProbeUtilBackupStageTertiary_ProgressRemaining(t *testing.T) {
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
			got := progressRemaining(testCase.moved, testCase.expected, testCase.rate)
			if got.Known() != testCase.known {
				t.Fatalf("progressRemaining() known = %v, want %v", got.Known(), testCase.known)
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

func TestProbeUtilBackupStageTertiary_ArgumentsKeepEveryOptionBeforeTheTerminator(t *testing.T) {
	builders := map[string]func(string, string, ...string) []string{
		"mirror":  mirrorArguments,
		"expunge": expungeArguments,
		"measure": measureArguments,
	}
	for name, builder := range builders {
		t.Run(name, func(t *testing.T) {
			arguments := builder("/share/10", "/backup/share/10", "--info=progress2")
			tail := arguments[len(arguments)-3:]
			if !slices.Equal(tail, []string{"--", "/share/10/", "/backup/share/10/"}) {
				t.Fatalf("%sArguments() ends %v, want the terminator then the source then the target, since rsync takes its last argument as the destination and an option after [--] is silently mirrored into a directory of that name", name, tail)
			}
			for _, option := range []string{"-a", "--stats", "--info=progress2", "--exclude"} {
				if slices.Index(arguments, option) > slices.Index(arguments, "--") {
					t.Errorf("%sArguments() places [%s] after the terminator, where rsync reads it as a path", name, option)
				}
			}
		})
	}
}

func TestProbeUtilBackupStageTertiary_OnlyTheExpungePassDeletesAndOnlyTheMeasurePassIsDry(t *testing.T) {
	mirror := mirrorArguments("/share/10", "/backup/share/10")
	if slices.Contains(mirror, "--delete") {
		t.Errorf("mirrorArguments() carries [--delete], so a deletion would be counted against the addition it was netted out of, which is what the expunge pass exists to separate")
	}
	if !slices.Contains(mirror, "--force") {
		t.Errorf("mirrorArguments() carries no [--force], so a directory the source has replaced with a file cannot be overwritten now that the mirror no longer deletes")
	}
	for name, arguments := range map[string][]string{"expunge": expungeArguments("/share/10", "/backup/share/10"), "measure": measureArguments("/share/10", "/backup/share/10")} {
		for _, option := range []string{"--delete", "--info=del"} {
			if !slices.Contains(arguments, option) {
				t.Errorf("%sArguments() carries no [%s], so the pass reports no deletion at all", name, option)
			}
		}
	}
	for _, option := range []string{"--existing", "--ignore-existing"} {
		if !slices.Contains(expungeArguments("/share/10", "/backup/share/10"), option) {
			t.Errorf("expungeArguments() carries no [%s], so the expunge pass would transfer as well as delete", option)
		}
	}
	if slices.Contains(expungeArguments("/share/10", "/backup/share/10"), "--dry-run") {
		t.Errorf("expungeArguments() carries [--dry-run], so the expunge pass would delete nothing")
	}
	if !slices.Contains(measureArguments("/share/10", "/backup/share/10"), "--dry-run") {
		t.Errorf("measureArguments() carries no [--dry-run], so measuring the stage would mutate the mirror")
	}
}

func TestProbeUtilBackupStageTertiary_ExpectationSumsTheDryRunAndFailsClosed(t *testing.T) {
	tests := []struct {
		name        string
		exit        int
		mirrorBytes int64
		mirrorFiles int
		expungeFile int
	}{
		{name: "the_dry_run_of_each_share_is_summed", exit: 0, mirrorBytes: 2 * 4096, mirrorFiles: 6, expungeFile: 4},
		{name: "a_dry_run_that_failed_reports_no_total_at_all", exit: 1},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			original := stageStream
			t.Cleanup(func() { stageStream = original })
			shares := []string{"/share/10", "/share/11"}
			dryRuns := 0
			stageStream = func(_ context.Context, sink io.Writer, name string, args ...string) (string, int, bool) {
				share := shares[dryRuns]
				target := filepath.Join(config.DirBackup, tertiaryShareDirectory, filepath.Base(share))
				if name != "rsync" || !slices.Equal(args, measureArguments(share, target)) {
					t.Errorf("expectation shelled out to [%s %v], want exactly the measure arguments", name, args)
				}
				dryRuns++
				if sink != nil {
					_, _ = sink.Write([]byte("deleting gone/\ndeleting stale.txt\n"))
				}
				return "Number of regular files transferred: 3\nNumber of deleted files: 2\nTotal transferred file size: 4,096 bytes\n", test.exit, false
			}
			got := measureStage(context.Background(), shares)
			if got.mirrorBytes != test.mirrorBytes || got.mirrorFiles != test.mirrorFiles || got.expungeFiles != test.expungeFile {
				t.Errorf("measureStage() = mirror %d bytes over %d files, expunge %d files, want %d %d %d",
					got.mirrorBytes, got.mirrorFiles, got.expungeFiles, test.mirrorBytes, test.mirrorFiles, test.expungeFile)
			}
			if test.exit == 0 && dryRuns != 2 {
				t.Errorf("dry runs = %d, want one per share", dryRuns)
			}
			if test.exit != 0 && got.expungeSizes != nil {
				t.Errorf("measureStage() kept a deletion set after a failed dry run, want no figure at all rather than a partial one")
			}
		})
	}
}

func TestProbeUtilBackupStageTertiary_ExpungeSizesPriceOnlyTheFilesStillOnTheMirror(t *testing.T) {
	target := t.TempDir()
	if err := os.MkdirAll(filepath.Join(target, "media", "old"), 0o755); err != nil {
		t.Fatalf("mkdir: %v", err)
	}
	if err := os.WriteFile(filepath.Join(target, "media", "one.mkv"), []byte("eleven byt"), 0o644); err != nil {
		t.Fatalf("write: %v", err)
	}
	sizes, total := expungeSizes(target, []string{"media/one.mkv", "media/old/", "media/vanished.mkv"})
	if total != 10 {
		t.Errorf("expungeSizes() total = %d, want the 10 bytes of the one file that is there, since a directory and a vanished path cost nothing", total)
	}
	if len(sizes) != 1 || sizes["media/one.mkv"] != 10 {
		t.Errorf("expungeSizes() = %v, want only the sized file", sizes)
	}
}

func TestProbeUtilBackupStageTertiary_ExpungeProgressPricesEachDeletionFromTheMeasuredSet(t *testing.T) {
	progress := &expungeProgress{sizes: map[string]int64{"media/one.mkv": 1000, "media/two.mkv": 2000}}
	if _, err := progress.Write([]byte("deleting media/one.mkv\ndeleting media/old/\ndeleting media/tw")); err != nil {
		t.Fatalf("Write: %v", err)
	}
	if got := progress.bytes(); got != 1000 {
		t.Errorf("bytes() = %d, want only the priced deletion 1000, since a directory carries no size and a split line is not a deletion yet", got)
	}
	if _, err := progress.Write([]byte("o.mkv\n")); err != nil {
		t.Fatalf("Write: %v", err)
	}
	if got := progress.bytes(); got != 3000 {
		t.Errorf("bytes() = %d, want 3000 once the split line reassembled", got)
	}
}

func TestProbeUtilBackupStageTertiary_RsyncDeletedReadsOnlyADeletionLine(t *testing.T) {
	tests := []struct {
		line, path string
		known      bool
	}{
		{line: "deleting media/one.mkv", path: "media/one.mkv", known: true},
		{line: "deleting media/old/", path: "media/old/", known: true},
		{line: "deleting ", known: false},
		{line: "media/one.mkv", known: false},
		{line: "        1,000  1%  10MB/s", known: false},
		{line: "", known: false},
	}
	for _, test := range tests {
		got, ok := rsyncDeleted(test.line)
		if ok != test.known {
			t.Fatalf("rsyncDeleted(%q) ok = %v, want %v", test.line, ok, test.known)
		}
		if test.known && got != test.path {
			t.Errorf("rsyncDeleted(%q) = %q, want %q", test.line, got, test.path)
		}
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
		{name: "a_complete_mirror_reports_the_same_figure_twice", moved: 1045008384, expected: 1045008384, expectedCopied: 996, expectedTotal: 996, expectedPercent: 100},
		{name: "a_part_mirror_reports_both_cells_alike", moved: 600 * bytesPerGibibyte, expected: 1000 * bytesPerGibibyte,
			expectedCopied: 600 * mebibytesPerGibibyte, expectedTotal: 1000 * mebibytesPerGibibyte, expectedPercent: 60},
	}
	for _, test := range cases {
		t.Run(test.name, func(t *testing.T) {
			copied := intReading(test.moved / bytesPerMebibyte)
			total := progressTotal(test.moved, test.expected)
			percent := progressPercent(test.moved, test.expected)
			if copied.Rounded() != test.expectedCopied || total.Rounded() != test.expectedTotal {
				t.Errorf("mirror cells: got copied %d total %d want %d %d", copied.Rounded(), total.Rounded(), test.expectedCopied, test.expectedTotal)
			}
			if percent.Rounded() != test.expectedPercent {
				t.Errorf("progressPercent: got %d want %d", percent.Rounded(), test.expectedPercent)
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
