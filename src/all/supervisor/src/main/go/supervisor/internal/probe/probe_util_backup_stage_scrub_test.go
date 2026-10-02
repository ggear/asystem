package probe

import (
	"context"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"slices"
	"strings"
	"sync"
	"sync/atomic"
	"testing"
	"time"

	"supervisor/internal/metric"
	"supervisor/internal/scribe"
)

func TestProbeUtilBackupStageScrub_TheWindowFallsFourTimesAYear(t *testing.T) {
	scrubbed := 0
	for month := time.January; month <= time.December; month++ {
		action, _ := scrubAction(false, metric.BackupTriggerSystem, "",
			time.Date(2026, month, 1, 2, 0, 0, 0, time.Local))
		if action == scrubActionStart {
			scrubbed++
		}
	}
	if scrubbed != 12/scrubWindowMonths {
		t.Errorf("scrubbed in [%d] months of the year, want [%d] from a [%d] month window", scrubbed, 12/scrubWindowMonths, scrubWindowMonths)
	}
}

func TestProbeUtilBackupStageScrub_TheReportingCadencesHoldTheirRelations(t *testing.T) {
	if scrubPublishInterval < backupProgressHeartbeat {
		t.Errorf("scrubPublishInterval [%s] is shorter than backupProgressHeartbeat [%s], so every tick dials the broker",
			scrubPublishInterval, backupProgressHeartbeat)
	}
	if scrubSilenceGrace <= backupProgressHeartbeat {
		t.Errorf("scrubSilenceGrace [%s] is within one heartbeat [%s], so a single unanswered poll fails the scrub",
			scrubSilenceGrace, backupProgressHeartbeat)
	}
	if scrubSilenceGrace >= scrubMargin {
		t.Errorf("scrubSilenceGrace [%s] outlasts the margin [%s] the scrub reserves inside the run deadline",
			scrubSilenceGrace, scrubMargin)
	}
}

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
	original := stageStream
	t.Cleanup(func() { stageStream = original })
	stageStream = func(_ context.Context, _ io.Writer, name string, args ...string) (string, int, bool) {
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

func TestProbeUtilBackupStageScrub_ProgressIsMeasuredFromTheFirstPollWhenBtrfsNamesATotal(t *testing.T) {
	tests := []struct {
		name             string
		status           string
		raw              string
		expectedProgress float64
		expectedMeasured bool
	}{
		{name: "a_fresh_pass_seconds_in_is_measured_against_the_named_total",
			status:           "Status:           running\nTotal to scrub:   7.69TiB\nBytes scrubbed:   1.70GiB  (0.02%)",
			raw:              "\tdata_bytes_scrubbed: 1825361100\n\ttree_bytes_scrubbed: 0",
			expectedProgress: 1825361100 / (7.69 * 1099511627776) * 100, expectedMeasured: true},
		{name: "every_binary_unit_btrfs_prints_is_understood",
			status:           "Status:           running\nTotal to scrub:   512.00MiB\nBytes scrubbed:   256.00MiB  (50.00%)",
			raw:              "\tdata_bytes_scrubbed: 201326592\n\ttree_bytes_scrubbed: 67108864",
			expectedProgress: 50, expectedMeasured: true},
		{name: "no_named_total_falls_back_to_the_printed_percentage",
			status:           "Status:           running\nBytes scrubbed:   982.55GiB  (98.44%)",
			raw:              "\tdata_bytes_scrubbed: 1050725752832\n\ttree_bytes_scrubbed: 4276305920",
			expectedProgress: 98.44, expectedMeasured: false},
		{name: "an_unparseable_total_falls_back_to_the_printed_percentage",
			status:           "Status:           running\nTotal to scrub:   lots\nBytes scrubbed:   982.55GiB  (98.44%)",
			raw:              "\tdata_bytes_scrubbed: 1050725752832\n\ttree_bytes_scrubbed: 4276305920",
			expectedProgress: 98.44, expectedMeasured: false},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			fakeExec(t, map[string]string{
				"btrfs scrub status -R /backup": testCase.raw,
				"btrfs scrub status /backup":    testCase.status,
			})
			reading, ok := scrubReadNow(context.Background())
			if !ok {
				t.Fatalf("scrubReadNow() not ok")
			}
			if reading.measured != testCase.expectedMeasured {
				t.Errorf("measured = %t, want %t", reading.measured, testCase.expectedMeasured)
			}
			if diff := reading.progress - testCase.expectedProgress; diff > 0.0001 || diff < -0.0001 {
				t.Errorf("progress = %.6f, want %.6f", reading.progress, testCase.expectedProgress)
			}
		})
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
	scrubMonth := scrubWindowFrom + time.Month(scrubWindowMonths)
	inWindow := time.Date(2026, scrubMonth, 2, 2, 0, 0, 0, time.Local)
	lateInWindow := time.Date(2026, scrubMonth, 20, 2, 0, 0, 0, time.Local)
	outsideMonth := time.Date(2026, scrubMonth+1, 2, 2, 0, 0, 0, time.Local)
	scrubbedThisMonth := "Scrub started:    " + inWindow.Format(time.ANSIC)
	scrubbedLastMonth := "Scrub started:    " + inWindow.AddDate(0, -1, 0).Format(time.ANSIC)
	resumedThisMonth := "Scrub resumed:    " + inWindow.Format(time.ANSIC) + "\nStatus:           finished"
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
		{name: "a_scheduled_run_late_in_a_scrub_month_catches_up_a_missed_pass", trigger: metric.BackupTriggerSystem, status: scrubbedLastMonth, now: lateInWindow,
			expectedAction: "start"},
		{name: "a_scheduled_run_late_in_a_scrub_month_after_its_pass_does_not", trigger: metric.BackupTriggerSystem, status: scrubbedThisMonth, now: lateInWindow,
			expectedReason: true},
		{name: "a_scheduled_run_in_a_month_between_scrubs_does_not", trigger: metric.BackupTriggerSystem, status: scrubbedLastMonth, now: outsideMonth,
			expectedReason: true},
		{name: "an_interrupted_pass_resumes_in_a_month_between_scrubs", trigger: metric.BackupTriggerSystem, status: "Status:           interrupted", now: outsideMonth,
			expectedAction: "resume"},
		{name: "a_hand_run_does_not_scrub_unasked", trigger: metric.BackupTriggerManual, status: scrubbedLastMonth, now: inWindow,
			expectedReason: true},
		{name: "a_hand_run_asked_for_it_scrubs", forced: true, trigger: metric.BackupTriggerManual, status: scrubbedLastMonth, now: lateInWindow,
			expectedAction: "start"},
		{name: "a_pass_this_month_already_is_skipped", trigger: metric.BackupTriggerSystem, status: scrubbedThisMonth, now: inWindow,
			expectedReason: true},
		{name: "a_pass_finished_by_a_resume_this_month_is_skipped", trigger: metric.BackupTriggerSystem, status: resumedThisMonth, now: inWindow,
			expectedReason: true},
		{name: "asking_forces_past_a_pass_this_month", forced: true, trigger: metric.BackupTriggerSystem, status: scrubbedThisMonth, now: inWindow,
			expectedAction: "start"},
		{name: "an_interrupted_pass_resumes_whatever_the_window_says", trigger: metric.BackupTriggerSystem, status: "Status:           interrupted", now: lateInWindow,
			expectedAction: "resume"},
		{name: "an_aborted_pass_resumes_on_a_hand_run_too", trigger: metric.BackupTriggerManual, status: "Status:           aborted", now: lateInWindow,
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
		name      string
		marker    string
		cancelled bool
		expected  string
	}{
		{name: "no_marker_and_no_cancel_is_no_halt", expected: ""},
		{name: "a_timed_out_marker", marker: stageTimedOutMarker, expected: metric.BackupStateTimeout},
		{name: "a_stopped_marker", marker: stageStoppedMarker, expected: metric.BackupStateStopped},
		{name: "an_interrupt_leaves_no_marker_and_still_halts", cancelled: true, expected: metric.BackupStateStopped},
		{name: "a_marker_outranks_a_cancel", marker: stageTimedOutMarker, cancelled: true, expected: metric.BackupStateTimeout},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			stagePath := t.TempDir()
			if testCase.marker != "" {
				if err := os.WriteFile(filepath.Join(stagePath, testCase.marker), nil, 0o644); err != nil {
					t.Fatalf("write marker: %v", err)
				}
			}
			if got := scrubHalt(stagePath, testCase.cancelled); got != testCase.expected {
				t.Errorf("scrubHalt() = %q, want %q", got, testCase.expected)
			}
		})
	}
}

func TestProbeUtilBackupStageScrub_DeviceStatsSumCannotCountWhenBtrfsDoesNotAnswer(t *testing.T) {
	stageStreamReturns(t, "", 1, false)
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
	stageStreamReturns(t, "ERROR: error during balancing", 1, false)
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
		{name: "a_tail_rounding_to_one_hundred_percent_reports_the_scrubbed_figure", scrubbedMB: 1020417, reached: 99.94, expectedTotal: 1020417},
		{name: "a_half_way_pass_scales_by_the_percentage", scrubbedMB: 512000, reached: 50.0, expectedTotal: 1024000},
		{name: "an_early_pass_keeps_the_unrounded_percentage_rather_than_shrinking_the_disk", scrubbedMB: 8644, reached: 0.87, expectedTotal: 993563},
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
			scrubbed := intReading(int64(reading.scrubbedMB))
			if scrubPercent(test.reached).Rounded() == 100 && total.Rounded() != scrubbed.Rounded() {
				t.Errorf("scrubTotal at 100 percent: got %d want the scrubbed cell %d", total.Rounded(), scrubbed.Rounded())
			}
		})
	}
}

func TestProbeUtilBackupStageScrub_OriginNamesWhatThePassIsContinuing(t *testing.T) {
	tests := []struct {
		name     string
		action   string
		status   string
		expected string
	}{
		{name: "a_fresh_pass_says_so", action: scrubActionStart, status: "Scrub started:    Mon Sep 22 01:00:00 2026",
			expected: "of a fresh pass"},
		{name: "a_resume_names_the_date_it_reads", action: scrubActionResume, status: "Scrub started:    Mon Sep 22 01:00:00 2026",
			expected: "of the pass from [Mon Sep 22 01:00:00 2026]"},
		{name: "a_resume_with_no_date_stays_honest", action: scrubActionResume, status: "no stats available",
			expected: "of an unfinished pass"},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			if origin := scrubOrigin(testCase.action, testCase.status); origin != testCase.expected {
				t.Errorf("scrubOrigin() = %q, want %q", origin, testCase.expected)
			}
		})
	}
}

func TestProbeUtilBackupStageScrub_APassOpensItsDocumentBeforeTheFirstPoll(t *testing.T) {
	tests := []struct {
		name            string
		status          string
		expectedResumed bool
	}{
		{name: "a_fresh_pass_opens_as_running", status: "no stats available"},
		{name: "a_resumed_pass_says_so_from_the_first_document",
			status: "Status:           interrupted\nScrub started:    Mon Sep 22 01:00:00 2026", expectedResumed: true},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			originalStream, originalAvailable := stageStream, commandAvailable
			t.Cleanup(func() { stageStream, commandAvailable = originalStream, originalAvailable })
			commandAvailable = func(string) bool { return true }
			stageStream = func(_ context.Context, _ io.Writer, _ string, args ...string) (string, int, bool) {
				if len(args) > 1 && args[1] == "status" {
					return testCase.status, 0, false
				}
				return "", 0, false
			}
			request := stageRequest{Stage: metric.BackupStageTertiary, RunID: "2026-09-24_16-23-57",
				RunPath: t.TempDir(), Expires: time.Now().Add(time.Hour), Scrub: true,
				Trigger: metric.BackupTriggerManual, ConfigPath: filepath.Join(t.TempDir(), "config.json")}
			ctx, cancel := context.WithCancel(context.Background())
			finished := make(chan struct{})
			go func() { defer close(finished); _ = runScrub(ctx, request) }()
			t.Cleanup(func() { cancel(); <-finished })

			path := scrubStatusPath(request.RunPath)
			var document *scrubSummary
			for attempt := 0; attempt < 200 && document == nil; attempt++ {
				document = readScrubSummary(path)
				if document == nil {
					time.Sleep(10 * time.Millisecond)
				}
			}
			if document == nil {
				t.Fatalf("scrub wrote no document before its first [%s] poll, so list renders [%s]",
					backupProgressHeartbeat, backupUnknownCell)
			}
			if document.State != metric.BackupStateRunning {
				t.Errorf("state = %q, want %q", document.State, metric.BackupStateRunning)
			}
			if document.ResumedBool != testCase.expectedResumed {
				t.Errorf("resumed_bool = %v, want %v", document.ResumedBool, testCase.expectedResumed)
			}
			if document.ExpiresTS == "" {
				t.Errorf("expires_ts is empty, want the scrub deadline the reaper and list read")
			}
			expected := metric.BackupStateRunning
			if testCase.expectedResumed {
				expected = backupResumedCell
			}
			if word := scrubWord(*document); word != expected {
				t.Errorf("scrubWord() = %q, want %q so list never shows a blank cell for a live pass", word, expected)
			}
		})
	}
}

func TestProbeUtilBackupStageScrub_APassPausedAtItsDeadlineLeavesTheStageHealthy(t *testing.T) {
	tests := []struct {
		name            string
		statusCode      int
		deviceStats     string
		stalled         bool
		expectedHealthy bool
		expectedState   string
	}{
		{name: "a_clean_pass_paused_at_its_deadline_resumes_next_run", deviceStats: "btrfs/device-stats-mounted-backup.txt",
			expectedHealthy: true, expectedState: metric.BackupStatePausing},
		{name: "a_paused_pass_that_made_no_progress_fails", deviceStats: "btrfs/device-stats-mounted-backup.txt", stalled: true,
			expectedHealthy: false, expectedState: metric.BackupStateFailure},
		{name: "a_paused_pass_with_device_errors_fails", deviceStats: "",
			expectedHealthy: false, expectedState: metric.BackupStateFailure},
		{name: "an_unreadable_scrub_status_fails_rather_than_skips", statusCode: 1,
			expectedHealthy: false, expectedState: metric.BackupStateFailure},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			deviceStats := "[/dev/sdb1].read_io_errs    3"
			if testCase.deviceStats != "" {
				deviceStats = fixtureStages(t, testCase.deviceStats)
			}
			outputs := map[string]string{
				"btrfs scrub status /backup":    fixtureStages(t, "btrfs/scrub-status-running.txt"),
				"btrfs scrub status -R /backup": fixtureStages(t, "btrfs/scrub-status-raw-running.txt"),
				"btrfs device stats /backup":    deviceStats,
			}
			request := stageRequest{Stage: metric.BackupStageTertiary, RunID: "2026-10-01_01-00-10",
				RunPath: t.TempDir(), Expires: time.Now().Add(scrubMargin + time.Millisecond), Scrub: true,
				Trigger: metric.BackupTriggerSystem, ConfigPath: filepath.Join(t.TempDir(), "config.json")}
			originalStream, originalAvailable := stageStream, commandAvailable
			t.Cleanup(func() { stageStream, commandAvailable = originalStream, originalAvailable })
			commandAvailable = func(string) bool { return true }
			polled := 0
			stageStream = func(_ context.Context, _ io.Writer, name string, args ...string) (string, int, bool) {
				key := name + " " + strings.Join(args, " ")
				if key == "btrfs scrub status /backup" && testCase.statusCode != 0 {
					return "ERROR: not a btrfs filesystem: /backup", testCase.statusCode, false
				}
				if key == "btrfs scrub status -R /backup" {
					polled++
					if polled == 1 && !testCase.stalled {
						return strings.Replace(outputs[key], "data_bytes_scrubbed: 1050725752832", "data_bytes_scrubbed: 1040725752832", 1), 0, false
					}
				}
				return outputs[key], 0, false
			}

			healthy := runScrub(context.Background(), request)
			if healthy != testCase.expectedHealthy {
				t.Errorf("runScrub() = %t, want %t", healthy, testCase.expectedHealthy)
			}
			document := readScrubSummary(scrubStatusPath(request.RunPath))
			if document == nil || document.State != testCase.expectedState {
				t.Fatalf("scrub document = %+v, want state %q", document, testCase.expectedState)
			}
			if document.SuccessBool {
				t.Errorf("success_bool = true, want false since no pass finished")
			}
		})
	}
}

func TestProbeUtilBackupStageScrub_AResumeBtrfsRefusesStartsAFreshPass(t *testing.T) {
	originalStream, originalAvailable := stageStream, commandAvailable
	t.Cleanup(func() { stageStream, commandAvailable = originalStream, originalAvailable })
	commandAvailable = func(string) bool { return true }
	var issued []string
	stageStream = func(_ context.Context, _ io.Writer, name string, args ...string) (string, int, bool) {
		key := name + " " + strings.Join(args, " ")
		switch key {
		case "btrfs scrub status /backup":
			return "Scrub resumed:    Thu Oct  1 11:11:16 2026\nStatus:           aborted", 0, false
		case "btrfs scrub resume -c 3 -n 15 /backup":
			issued = append(issued, "resume")
			return "ERROR: no scrub to resume", 1, false
		case "btrfs scrub start -c 3 -n 15 /backup":
			issued = append(issued, "start")
			return "", 0, false
		case "btrfs device stats /backup":
			return fixtureStages(t, "btrfs/device-stats-mounted-backup.txt"), 0, false
		}
		return "", 0, false
	}
	request := stageRequest{Stage: metric.BackupStageTertiary, RunID: "2026-10-02_01-00-10",
		RunPath: t.TempDir(), Expires: time.Now().Add(time.Hour), Trigger: metric.BackupTriggerSystem,
		ConfigPath: filepath.Join(t.TempDir(), "config.json")}

	_ = runScrub(context.Background(), request)
	if !slices.Equal(issued, []string{"resume", "start"}) {
		t.Errorf("issued %v, want a refused resume followed by a fresh start", issued)
	}
	if document := readScrubSummary(scrubStatusPath(request.RunPath)); document == nil || document.ResumedBool {
		t.Errorf("scrub document = %+v, want resumed_bool false for the fresh pass that replaced the refused resume", document)
	}
}

func TestProbeUtilBackupStageScrub_AStopThatUnmountsTheDiskLeavesTheFilesystemBeneathAlone(t *testing.T) {
	for _, cancelled := range []bool{true, false} {
		t.Run(fmt.Sprintf("cancelled_%t", cancelled), func(t *testing.T) {
			stopScrubUnderneath(t, cancelled)
		})
	}
}

func stopScrubUnderneath(t *testing.T, cancelled bool) {
	originalStream, originalAvailable := stageStream, commandAvailable
	t.Cleanup(func() { stageStream, commandAvailable = originalStream, originalAvailable })
	commandAvailable = func(string) bool { return true }
	var unmounted atomic.Bool
	var touched []string
	var touchedMu sync.Mutex
	root := "UUID:             ff55f331-1d06-4a57-a65f-89e457b3a3d0\n\tno stats available"
	stageStream = func(_ context.Context, _ io.Writer, name string, args ...string) (string, int, bool) {
		key := name + " " + strings.Join(args, " ")
		if strings.HasPrefix(key, "btrfs device stats") {
			touchedMu.Lock()
			touched = append(touched, key)
			touchedMu.Unlock()
		}
		switch key {
		case "btrfs scrub status /backup":
			if unmounted.Load() {
				return root, 0, false
			}
			return fixtureStages(t, "btrfs/scrub-status-running.txt"), 0, false
		case "btrfs scrub status -R /backup":
			if unmounted.Load() {
				return root, 0, false
			}
			return fixtureStages(t, "btrfs/scrub-status-raw-running.txt"), 0, false
		case "btrfs device stats /backup":
			return fixtureStages(t, "btrfs/device-stats-mounted-backup.txt"), 0, false
		}
		return "", 0, false
	}
	request := stageRequest{Stage: metric.BackupStageTertiary, RunID: "2026-10-01_12-48-04",
		RunPath: t.TempDir(), Expires: time.Now().Add(time.Hour), Scrub: true, Trigger: metric.BackupTriggerManual,
		ConfigPath: filepath.Join(t.TempDir(), "config.json")}
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	stagePath := stageDir(request.RunPath, request.Stage)
	if err := os.MkdirAll(stagePath, 0o755); err != nil {
		t.Fatalf("mkdir stage: %v", err)
	}
	go func() {
		time.Sleep(backupProgressHeartbeat + time.Second)
		_ = os.WriteFile(filepath.Join(stagePath, stageStoppedMarker), nil, 0o644)
		unmounted.Store(true)
		if cancelled {
			cancel()
		}
	}()

	if runScrub(ctx, request) {
		t.Errorf("runScrub() = true, want false for a stopped pass")
	}
	document := readScrubSummary(scrubStatusPath(request.RunPath))
	wantScrubbedMB := 1050725752832 / 1048576
	if document == nil || document.State != metric.BackupStateStopped || document.ScrubbedMB != wantScrubbedMB {
		t.Errorf("scrub document = %+v, want stopped with scrubbed_mb [%d] from its own last reading, not the filesystem beneath", document, wantScrubbedMB)
	}
	touchedMu.Lock()
	defer touchedMu.Unlock()
	if len(touched) != 0 {
		t.Errorf("issued %q, want no device stats read or reset once the scrubbed filesystem is gone", touched)
	}
}

func TestProbeUtilBackupStageScrub_CorruptFilesMapEachSubvolumeBackOntoTheLiveMirror(t *testing.T) {
	subvolumes := map[int64]string{
		256: "share/10",
		257: ".snapshots/share/10/2026-09-30_01-00-49",
		258: ".snapshots/share/10/2026-10-01_01-00-11",
		259: "share/11",
	}
	tests := []struct {
		name        string
		corruptions []kernelCorruption
		expected    []scrubCorruptFile
	}{
		{name: "a_live_copy_and_its_snapshots_are_one_file",
			corruptions: []kernelCorruption{{root: 256, path: "media/a.mkv"}, {root: 257, path: "media/a.mkv"}, {root: 258, path: "media/a.mkv"}},
			expected:    []scrubCorruptFile{{mirror: "/backup/share/10/media/a.mkv", source: "/share/10/media/a.mkv", snapshots: 2, live: true}}},
		{name: "a_file_named_by_snapshots_alone_is_not_live",
			corruptions: []kernelCorruption{{root: 257, path: "media/gone.mkv"}},
			expected:    []scrubCorruptFile{{mirror: "/backup/share/10/media/gone.mkv", source: "/share/10/media/gone.mkv", snapshots: 1}}},
		{name: "files_sort_by_their_mirror_path",
			corruptions: []kernelCorruption{{root: 259, path: "b.mkv"}, {root: 256, path: "Film (2010)/film.mkv"}},
			expected: []scrubCorruptFile{
				{mirror: "/backup/share/10/Film (2010)/film.mkv", source: "/share/10/Film (2010)/film.mkv", live: true},
				{mirror: "/backup/share/11/b.mkv", source: "/share/11/b.mkv", live: true}}},
		{name: "an_unlisted_root_reads_from_the_top_level",
			corruptions: []kernelCorruption{{root: 5, path: "share/10/media/a.mkv"}},
			expected:    []scrubCorruptFile{{mirror: "/backup/share/10/media/a.mkv", source: "/share/10/media/a.mkv", live: true}}},
		{name: "a_file_outside_the_share_mirror_has_no_source",
			corruptions: []kernelCorruption{{root: 5, path: "lost+found/x"}},
			expected:    []scrubCorruptFile{{mirror: "/backup/lost+found/x", live: true}}},
		{name: "a_path_climbing_out_of_the_share_has_no_source",
			corruptions: []kernelCorruption{{root: 256, path: "../../../etc/passwd"}},
			expected:    []scrubCorruptFile{{mirror: "/etc/passwd", live: true}}},
		{name: "nothing_named_is_nothing_to_delete"},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			got := scrubCorruptFiles(testCase.corruptions, subvolumes)
			if !slices.Equal(got, testCase.expected) && (len(got) != 0 || len(testCase.expected) != 0) {
				t.Errorf("scrubCorruptFiles() = %+v, want %+v", got, testCase.expected)
			}
		})
	}
}

func TestProbeUtilBackupStageScrub_ReportStatesTheVerdictAndTheRepairOnLinesThatNeverWrap(t *testing.T) {
	widest := strings.Repeat("/very-long-directory-name", 20) + "/film.mkv"
	many := make([]scrubCorruptFile, kernelCorruptNamed+5)
	for index := range many {
		many[index] = scrubCorruptFile{mirror: fmt.Sprintf("/backup/share/10/media/%03d.mkv", index), source: "/share/10/x",
			outcome: scrubOutcomeDeleted, snapshots: 999, live: true}
	}
	tests := []struct {
		name      string
		state     string
		reading   scrubReading
		device    int
		counted   bool
		files     []scrubCorruptFile
		faults    int
		contained []string
	}{
		{name: "a_clean_pass_says_so_with_its_chunks", state: metric.BackupStateSuccess, counted: true,
			reading:   scrubReading{scrubbedMB: 8016038, progress: 100},
			contained: []string{"finished as [success] at [100] percent of [7828.2] GiB, a [resumed] pass with [4] chunks relocated", "the disk is clean"}},
		{name: "unread_device_stats_never_claim_clean", state: metric.BackupStateFailure,
			contained: []string{"[-] on the device, its device stats unread"}},
		{name: "a_deleted_file_names_the_next_run_and_the_command", state: metric.BackupStateFailure, counted: true,
			reading: scrubReading{found: 2, uncorrectable: 2},
			files:   []scrubCorruptFile{{mirror: "/backup/share/10/media/a.mkv", source: "/share/10/media/a.mkv", outcome: scrubOutcomeDeleted, snapshots: 3, live: true}},
			faults:  3,
			contained: []string{"[1] files corrupt, see [scrub.log]", "[deleted ] corrupt in the mirror and [  3] snapshots",
				"[/backup/share/10/media/a.mkv]", "run [abackup start] now to mirror them again"}},
		{name: "a_file_it_could_not_delete_is_left_to_the_operator", state: metric.BackupStateFailure, counted: true,
			reading:   scrubReading{found: 1},
			files:     []scrubCorruptFile{{mirror: "/backup/share/10/a.mkv", source: "/share/10/a.mkv", outcome: scrubOutcomeKept, live: true}},
			faults:    3,
			contained: []string{"[kept    ] corrupt in the mirror", "delete each by hand then run [abackup start]"}},
		{name: "a_snapshot_only_file_warns_against_restoring_it", state: metric.BackupStateFailure, counted: true,
			reading:   scrubReading{found: 1},
			files:     []scrubCorruptFile{{mirror: "/backup/share/10/a.mkv", source: "/share/10/a.mkv", outcome: scrubOutcomeSnapshot, snapshots: 2}},
			faults:    2,
			contained: []string{"[snapshot] corrupt in [  2] snapshots alone, never restore it from them"}},
		{name: "errors_naming_no_file_point_at_the_hardware", state: metric.BackupStateFailure, counted: true,
			device: 4, faults: 2, contained: []string{"[4] on the device", "check its cable and SMART"}},
		{name: "a_path_too_long_for_the_column_keeps_its_tail", state: metric.BackupStateFailure, counted: true,
			reading:   scrubReading{found: 1},
			files:     []scrubCorruptFile{{mirror: "/backup/share/10" + widest, source: "/share/10" + widest, outcome: scrubOutcomeKept, snapshots: 999, live: true}},
			faults:    3,
			contained: []string{"/film.mkv]", "[~"}},
		{name: "more_files_than_are_named_point_at_the_log", state: metric.BackupStateFailure, counted: true,
			reading: scrubReading{found: 999999, corrected: 999999, uncorrectable: 999999}, device: 999999, files: many,
			faults: 2 + kernelCorruptNamed + 1, contained: []string{"[5] more corrupt files are named in [scrub.log]"}},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			resumed, relocated := false, 0
			if testCase.state == metric.BackupStateSuccess {
				resumed, relocated = true, 4
			}
			lines := scrubReport(testCase.state, resumed, testCase.reading, testCase.device, testCase.counted, relocated, testCase.files)
			var rendered []string
			faults := 0
			for _, line := range lines {
				rendered = append(rendered, line.detail)
				if line.fault {
					faults++
				}
				if !strings.HasPrefix(line.detail, "[") {
					t.Errorf("report line does not lead with a bracketed value\n%s", line.detail)
				}
				if len(line.detail) > scribe.Detailed() {
					t.Errorf("report line is [%d] characters against a [%d] detail column, so it wraps\n%s",
						len(line.detail), scribe.Detailed(), line.detail)
				}
			}
			if faults != testCase.faults {
				t.Errorf("report raised [%d] error lines, want [%d]\n%s", faults, testCase.faults, strings.Join(rendered, "\n"))
			}
			joined := strings.Join(rendered, "\n")
			for _, want := range testCase.contained {
				if !strings.Contains(joined, want) {
					t.Errorf("report does not say %q\n%s", want, joined)
				}
			}
		})
	}
}

func TestProbeUtilBackupStageScrub_CorruptionDeletesTheLiveMirrorCopyAndNeverASnapshotOne(t *testing.T) {
	fstab := filepath.Join(t.TempDir(), "fstab")
	if err := os.WriteFile(fstab, []byte("/dev/null  /backup  btrfs  noauto  0 2\n"), 0o644); err != nil {
		t.Fatalf("write fstab: %v", err)
	}
	originalFstab, originalStream, originalAvailable := backupFstabPath, stageStream, commandAvailable
	t.Cleanup(func() {
		backupFstabPath, stageStream, commandAvailable = originalFstab, originalStream, originalAvailable
	})
	backupFstabPath = fstab
	commandAvailable = func(string) bool { return true }
	clean := fixtureStages(t, "btrfs/scrub-status-raw-running.txt")
	finished := strings.Replace(strings.Replace(clean, "Status:           running", "Status:           finished", 1),
		"csum_errors: 0", "csum_errors: 3", 1)
	finished = strings.Replace(finished, "uncorrectable_errors: 0", "uncorrectable_errors: 3", 1)
	finished = strings.Replace(finished, "data_bytes_scrubbed: 1050725752832", "data_bytes_scrubbed: 1060725752832", 1)
	warning := "BTRFS warning (device sdb1): checksum error at logical 1 on dev /dev/sdb1, physical 1, root %d, inode 9, offset 0, length 4096, links 1 (path: %s)"
	kernel := strings.Join([]string{"before the scrub",
		fmt.Sprintf(warning, 256, "media/a.mkv"), fmt.Sprintf(warning, 257, "media/a.mkv"), fmt.Sprintf(warning, 257, "media/gone.mkv")}, "\n")
	var removed []string
	polled, dmesg := 0, 0
	stageStream = func(_ context.Context, _ io.Writer, name string, args ...string) (string, int, bool) {
		key := strings.TrimSpace(name + " " + strings.Join(args, " "))
		switch {
		case key == "btrfs scrub status /backup":
			return fixtureStages(t, "btrfs/scrub-status-running.txt"), 0, false
		case key == "btrfs scrub status -R /backup":
			polled++
			if polled == 1 {
				return clean, 0, false
			}
			return finished, 0, false
		case key == "dmesg":
			dmesg++
			if dmesg == 1 {
				return "before the scrub", 0, false
			}
			return kernel, 0, false
		case key == "btrfs subvolume list /backup":
			return "ID 256 gen 9 top level 5 path share/10\nID 257 gen 9 top level 5 path .snapshots/share/10/2026-09-30_01-00-49\n", 0, false
		case key == "btrfs device stats /backup":
			return fixtureStages(t, "btrfs/device-stats-mounted-backup.txt"), 0, false
		case key == "findmnt -M /backup -n -o SOURCE":
			return "/dev/null", 0, false
		case strings.HasPrefix(key, "rm -f -- "):
			removed = append(removed, strings.TrimPrefix(key, "rm -f -- "))
		}
		return "", 0, false
	}
	request := stageRequest{Stage: metric.BackupStageTertiary, RunID: "2026-10-02_01-00-55",
		RunPath: t.TempDir(), Expires: time.Now().Add(time.Hour), Scrub: true, Trigger: metric.BackupTriggerSystem,
		ConfigPath: filepath.Join(t.TempDir(), "config.json")}

	if runScrub(context.Background(), request) {
		t.Errorf("runScrub() = true, want false for a pass that found corrupt files")
	}
	if !slices.Equal(removed, []string{"/backup/share/10/media/a.mkv"}) {
		t.Errorf("removed %q, want only the live mirror copy, never one named by a read-only snapshot alone", removed)
	}
	document := readScrubSummary(scrubStatusPath(request.RunPath))
	if document == nil || document.State != metric.BackupStateFailure || document.FilesToDeleteCount != 2 ||
		document.FilesToDelete != "/backup/share/10/media/a.mkv,/backup/share/10/media/gone.mkv" {
		t.Errorf("scrub document = %+v, want a failure naming both corrupt files", document)
	}
	listing, err := os.ReadFile(filepath.Join(stageDir(request.RunPath, request.Stage), scrubLogLeaf))
	if err != nil || !strings.Contains(string(listing), "deleted     1 /backup/share/10/media/a.mkv") ||
		!strings.Contains(string(listing), "snapshot    1 /backup/share/10/media/gone.mkv") {
		t.Errorf("scrub log = %q, want each corrupt file with its outcome and full path", listing)
	}
}
