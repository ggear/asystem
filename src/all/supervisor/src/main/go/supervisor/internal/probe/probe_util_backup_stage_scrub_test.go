package probe

import (
	"context"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"supervisor/internal/metric"
	"supervisor/internal/scribe"
)

func fixtureStages(t *testing.T, relPath string) string {
	t.Helper()
	path, err := filepath.Abs(filepath.Join("..", "..", "..", "..", "..", "test", "resources", "backup", relPath))
	if err != nil {
		t.Fatalf("resolve fixture path: %v", err)
	}
	data, err := os.ReadFile(path)
	if err != nil {
		t.Fatalf("fixture not found at %s: %v", path, err)
	}
	lines := strings.Split(strings.TrimRight(string(data), "\n"), "\n")
	if len(lines) > 0 && strings.HasPrefix(lines[0], "$ ") {
		lines = lines[1:]
	}
	if len(lines) > 0 && strings.HasPrefix(lines[len(lines)-1], "[exit ") {
		lines = lines[:len(lines)-1]
	}
	return strings.Join(lines, "\n")
}

func fakeExec(t *testing.T, table map[string]string) {
	t.Helper()
	original := stageExec
	t.Cleanup(func() { stageExec = original })
	stageExec = func(_ context.Context, name string, args ...string) (string, int, bool) {
		key := name + " " + strings.Join(args, " ")
		if output, ok := table[key]; ok {
			return output, 0, false
		}
		t.Fatalf("fakeExec: no exact match for command [%s]", key)
		return "", 0, false
	}
}

func TestProbeUtilBackupStageScrub_ReadNowAgainstCapturedRunningStatus(t *testing.T) {
	fakeExec(t, map[string]string{
		"btrfs scrub status -R /backup": fixtureStages(t, "btrfs/scrub-status-raw-running.txt"),
		"btrfs scrub status /backup":    fixtureStages(t, "btrfs/scrub-status-running.txt"),
	})
	reading, ok := scrubReadNow(context.Background())
	if !ok {
		t.Fatalf("scrubReadNow() not ok")
	}
	if !reading.running {
		t.Errorf("expected running=true against a live running status")
	}
	if reading.progress < 98 || reading.progress > 99 {
		t.Errorf("progress = %.2f, want ~98.44", reading.progress)
	}
	wantScrubbedMB := 1050725752832 / 1048576
	if reading.scrubbedMB != wantScrubbedMB {
		t.Errorf("scrubbedMB = %d, want %d", reading.scrubbedMB, wantScrubbedMB)
	}
	if reading.found != 0 || reading.corrected != 0 || reading.uncorrectable != 0 {
		t.Errorf("expected no errors, got found=%d corrected=%d uncorrectable=%d", reading.found, reading.corrected, reading.uncorrectable)
	}
}

func TestProbeUtilBackupStageScrub_ReadNowAgainstCapturedAbortedStatusIsNotRunning(t *testing.T) {
	fakeExec(t, map[string]string{
		"btrfs scrub status -R /backup": fixtureStages(t, "btrfs/scrub-status-raw-aborted.txt"),
		"btrfs scrub status /backup":    fixtureStages(t, "btrfs/scrub-status-aborted.txt"),
	})
	reading, ok := scrubReadNow(context.Background())
	if !ok {
		t.Fatalf("scrubReadNow() not ok")
	}
	if reading.running {
		t.Errorf("expected running=false against an aborted status")
	}
}

func TestProbeUtilBackupStageScrub_ReadNowAgainstNeverScrubbedHasNoPercentage(t *testing.T) {
	fakeExec(t, map[string]string{
		"btrfs scrub status -R /backup": fixtureStages(t, "btrfs/scrub-status-raw-never-scrubbed.txt"),
		"btrfs scrub status /backup":    fixtureStages(t, "btrfs/scrub-status-never-scrubbed.txt"),
	})
	reading, ok := scrubReadNow(context.Background())
	if !ok {
		t.Fatalf("scrubReadNow() not ok")
	}
	if reading.progress != 0 {
		t.Errorf("progress = %.2f, want 0 (no percentage in a never-scrubbed status)", reading.progress)
	}
}

func TestProbeUtilBackupStageScrub_ProgressClampedOverOneHundred(t *testing.T) {
	fakeExec(t, map[string]string{
		"btrfs scrub status -R /backup": fixtureStages(t, "btrfs/scrub-status-raw-running.txt"),
		"btrfs scrub status /backup": `UUID:             619d6da6-ca70-473b-9d2c-b3c105b153cc
Status:           running
Bytes scrubbed:   998.11GiB  (100.15%)
Error summary:    no errors found`,
	})
	reading, ok := scrubReadNow(context.Background())
	if !ok {
		t.Fatalf("scrubReadNow() not ok")
	}
	if reading.progress != 100 {
		t.Errorf("progress = %.2f, want 100 (a resumed pass legitimately exceeds 100%%, must clamp)", reading.progress)
	}
}

func TestProbeUtilBackupStageScrub_DeviceStatsSumAgainstCapturedClean(t *testing.T) {
	fakeExec(t, map[string]string{
		"btrfs device stats /backup": fixtureStages(t, "btrfs/device-stats-mounted-backup.txt"),
	})
	sum, counted := deviceStatsSum(context.Background())
	if sum != 0 || !counted {
		t.Errorf("deviceStatsSum() = (%d, %t), want (0, true) against an all-clean device stats block", sum, counted)
	}
}

func TestProbeUtilBackupStageScrub_DeviceStatsSumCountsNonZero(t *testing.T) {
	fakeExec(t, map[string]string{
		"btrfs device stats /backup": `[/dev/sdb1].write_io_errs    2
[/dev/sdb1].read_io_errs     3
[/dev/sdb1].flush_io_errs    0
[/dev/sdb1].corruption_errs  1
[/dev/sdb1].generation_errs  0`,
	})
	sum, counted := deviceStatsSum(context.Background())
	if sum != 6 || !counted {
		t.Errorf("deviceStatsSum() = (%d, %t), want (6, true)", sum, counted)
	}
}

func TestProbeUtilBackupStageScrub_ActionScrubsOnlyWhenAskedOrDue(t *testing.T) {
	inWindow := time.Date(2026, 9, scrubWindowDay+1, 2, 0, 0, 0, time.Local)
	outsideWindow := time.Date(2026, 9, scrubWindowDay+scrubWindowDays, 2, 0, 0, 0, time.Local)
	scrubbedThisMonth := "Scrub started:    Tue Sep  1 01:05:00 2026"
	scrubbedLastMonth := "Scrub started:    Sat Aug  1 01:05:00 2026"
	tests := []struct {
		name           string
		forced         bool
		trigger        string
		status         string
		now            time.Time
		expectedAction string
		expectedReason bool
	}{
		{name: "a_scheduled_run_inside_the_window_scrubs", trigger: metric.BackupTriggerSystem, status: scrubbedLastMonth, now: inWindow,
			expectedAction: "start"},
		{name: "a_scheduled_run_outside_the_window_does_not", trigger: metric.BackupTriggerSystem, status: scrubbedLastMonth, now: outsideWindow,
			expectedReason: true},
		{name: "a_hand_run_does_not_scrub_unasked", trigger: metric.BackupTriggerManual, status: scrubbedLastMonth, now: inWindow,
			expectedReason: true},
		{name: "a_hand_run_asked_for_it_scrubs", forced: true, trigger: metric.BackupTriggerManual, status: scrubbedLastMonth, now: outsideWindow,
			expectedAction: "start"},
		{name: "a_pass_this_month_already_is_skipped", trigger: metric.BackupTriggerSystem, status: scrubbedThisMonth, now: inWindow,
			expectedReason: true},
		{name: "asking_forces_past_a_pass_this_month", forced: true, trigger: metric.BackupTriggerSystem, status: scrubbedThisMonth, now: inWindow,
			expectedAction: "start"},
		{name: "an_interrupted_pass_resumes_whatever_the_window_says", trigger: metric.BackupTriggerSystem, status: "Status:           interrupted", now: outsideWindow,
			expectedAction: "resume"},
		{name: "an_aborted_pass_resumes_on_a_hand_run_too", trigger: metric.BackupTriggerManual, status: "Status:           aborted", now: outsideWindow,
			expectedAction: "resume"},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			action, reason := scrubAction(testCase.forced, testCase.trigger, testCase.status, testCase.now)
			if action != testCase.expectedAction || (reason != "") != testCase.expectedReason {
				t.Errorf("scrubAction() = (%q, %q), want action %q and a reason %t", action, reason, testCase.expectedAction, testCase.expectedReason)
			}
		})
	}
}

func TestProbeUtilBackupStageScrub_HaltReadsTheMarkerTheStageLeft(t *testing.T) {
	tests := []struct {
		name     string
		marker   string
		expected string
	}{
		{name: "no_marker_is_no_halt", expected: ""},
		{name: "a_timed_out_marker", marker: stageTimedOutMarker, expected: metric.BackupStateTimeout},
		{name: "a_stopped_marker", marker: stageStoppedMarker, expected: metric.BackupStateStopped},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			stagePath := t.TempDir()
			if testCase.marker != "" {
				if err := os.WriteFile(filepath.Join(stagePath, testCase.marker), nil, 0o644); err != nil {
					t.Fatalf("write marker: %v", err)
				}
			}
			if got := scrubHalt(stagePath); got != testCase.expected {
				t.Errorf("scrubHalt() = %q, want %q", got, testCase.expected)
			}
		})
	}
}

func TestProbeUtilBackupStageScrub_DeviceStatsSumCannotCountWhenBtrfsDoesNotAnswer(t *testing.T) {
	stageExecReturns(t, "", 1, false)
	if sum, counted := deviceStatsSum(context.Background()); sum != 0 || counted {
		t.Errorf("deviceStatsSum() = (%d, %t), want (0, false) so the scrub cannot report a clean disk", sum, counted)
	}
}

func TestProbeUtilBackupStageScrub_BalanceReportsTheChunksItRelocated(t *testing.T) {
	fakeExec(t, map[string]string{
		"btrfs balance start -dusage=10 -musage=10 /backup": "Done, had to relocate 7 out of 4021 chunks",
	})
	if got := runBalance(context.Background(), scribe.SubjectStage(metric.BackupStageTertiary)); got != 7 {
		t.Errorf("runBalance() = %d, want 7 chunks relocated", got)
	}
}

func TestProbeUtilBackupStageScrub_BalanceReportsNothingWhenItCouldNotRun(t *testing.T) {
	stageExecReturns(t, "ERROR: error during balancing", 1, false)
	if got := runBalance(context.Background(), scribe.SubjectStage(metric.BackupStageTertiary)); got != 0 {
		t.Errorf("runBalance() = %d, want 0 when the balance did not run", got)
	}
}

func TestProbeUtilBackupStageScrub_DeadlineLeavesAMarginInsideTheRun(t *testing.T) {
	started := time.Date(2026, 9, 22, 1, 0, 0, 0, time.Local)
	tests := []struct {
		name     string
		expires  time.Time
		expected time.Time
	}{
		{name: "no_run_deadline_gives_an_hour", expected: started.Add(time.Hour)},
		{name: "a_run_deadline_keeps_the_margin", expires: started.Add(3 * time.Hour), expected: started.Add(3*time.Hour - scrubMargin)},
		{name: "a_deadline_inside_the_margin_leaves_no_time", expires: started.Add(scrubMargin / 2), expected: started},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			got := scrubDeadline(stageRequest{Expires: testCase.expires}, started)
			if !got.Equal(testCase.expected) {
				t.Errorf("scrubDeadline() = %s, want %s", got, testCase.expected)
			}
		})
	}
}

func TestProbeUtilBackupStageScrub_TotalAgreesWithTheScrubbedCellAndThePercentage(t *testing.T) {
	cases := []struct {
		name          string
		scrubbedMB    int
		reached       float64
		expectedTotal int64
	}{
		{name: "a_tail_rounding_to_one_hundred_percent_reports_the_scrubbed_figure", scrubbedMB: 1020417, reached: 99.94, expectedTotal: 996},
		{name: "a_half_way_pass_scales_by_the_rounded_percentage", scrubbedMB: 512000, reached: 50.0, expectedTotal: 1000},
		{name: "nothing_scrubbed_yet_is_unknown", scrubbedMB: 0, reached: 0, expectedTotal: 0},
	}
	for _, test := range cases {
		t.Run(test.name, func(t *testing.T) {
			reading := scrubReading{scrubbedMB: test.scrubbedMB}
			total := scrubTotal(reading, test.reached)
			if test.reached <= 0 {
				if total.Known() {
					t.Errorf("scrubTotal: got %v want unknown", total.Rounded())
				}
				return
			}
			if !total.Known() || total.Rounded() != test.expectedTotal {
				t.Errorf("scrubTotal: got %d want %d", total.Rounded(), test.expectedTotal)
			}
			scrubbed := intReading(int64(reading.scrubbedMB) / mebibytesPerGibibyte)
			if scrubPercent(test.reached).Rounded() == 100 && total.Rounded() != scrubbed.Rounded() {
				t.Errorf("scrubTotal at 100 percent: got %d want the scrubbed cell %d", total.Rounded(), scrubbed.Rounded())
			}
		})
	}
}
