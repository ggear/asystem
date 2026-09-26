package probe

import (
	"io"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"supervisor/internal/metric"
	"supervisor/internal/scribe"
)

func TestProbeUtilBackupRender_RateIsUnknownBelowThreePoints(t *testing.T) {
	ring := newSampleRing(ringPoints, ringQuantum)
	base := time.Now()
	ring.push(base, 0)
	if ring.rate().Known() {
		t.Errorf("rate() known with one point, want unknown")
	}
	ring.push(base.Add(10*time.Second), 200*bytesPerMebibyte)
	if ring.rate().Known() {
		t.Errorf("rate() known with two points, want unknown")
	}
	ring.push(base.Add(20*time.Second), 400*bytesPerMebibyte)
	if !ring.rate().Known() {
		t.Errorf("rate() unknown with three points, want a rate")
	}
}

func TestProbeUtilBackupRender_RateMeasuresTheGainNotTheCumulativeTotal(t *testing.T) {
	ring := newSampleRing(ringPoints, ringQuantum)
	base := time.Date(2026, 9, 22, 7, 55, 4, 0, time.UTC)
	ring.push(base, 0)
	ring.push(base.Add(9*time.Hour+55*time.Minute+15*time.Second), 1050725752832)
	ring.push(base.Add(9*time.Hour+55*time.Minute+35*time.Second), 1054196064256)
	rate := ring.rate()
	if !rate.Known() {
		t.Fatalf("rate() unknown, want a rate")
	}
	if got := rate.Rounded(); got < 164 || got > 167 {
		t.Errorf("rate() = %d MiB/s, want ~165 and not btrfs's cumulative 28", got)
	}
}

func TestProbeUtilBackupRender_ACounterGoingBackwardsRestartsTheWindow(t *testing.T) {
	ring := newSampleRing(ringPoints, ringQuantum)
	base := time.Now()
	for index := range 6 {
		ring.push(base.Add(time.Duration(index)*10*time.Second), int64(index)*200*bytesPerMebibyte)
	}
	if !ring.rate().Known() {
		t.Fatalf("rate() unknown with a full window, want a rate")
	}
	ring.push(base.Add(60*time.Second), 100*bytesPerMebibyte)
	if ring.rate().Known() {
		t.Errorf("rate() known straight after a decrease, want the window restarted")
	}
}

func TestProbeUtilBackupRender_QuantumSuppressesSamplesTooSmallToMeasure(t *testing.T) {
	ring := newSampleRing(ringPoints, ringQuantum)
	base := time.Now()
	ring.push(base, 0)
	for index := 1; index <= 5; index++ {
		ring.push(base.Add(time.Duration(index)*time.Second), int64(index)*bytesPerMebibyte/10)
	}
	if got := len(ring.points); got != 1 {
		t.Errorf("points = %d, want 1 with every sample below the quantum dropped", got)
	}
	ring.push(base.Add(6*time.Second), 2*bytesPerMebibyte)
	if got := len(ring.points); got != 2 {
		t.Errorf("points = %d, want a sample at the quantum admitted", got)
	}
}

func TestProbeUtilBackupRender_ProgressCutsTheLineAtTheLastMeasuredField(t *testing.T) {
	tests := []struct {
		name     string
		total    reading
		percent  reading
		remain   reading
		rate     reading
		expected string
	}{
		{name: "copied_only", total: unknownReading(), percent: unknownReading(), remain: unknownReading(), rate: unknownReading(),
			expected: "[   5] GiB"},
		{name: "total_known", total: intReading(90), percent: unknownReading(), remain: unknownReading(), rate: unknownReading(),
			expected: "[   5] GiB of [  90] GiB"},
		{name: "rate_known_holds_an_unknown_total_with_a_dash", total: unknownReading(), percent: unknownReading(), remain: unknownReading(), rate: floatReading(102),
			expected: "[   5] GiB of [   -] GiB at [102] MiB/s"},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			got := backupProgressed(intReading(5), testCase.total, testCase.percent, testCase.remain,
				backupEta(time.Now(), testCase.remain), testCase.rate, "")
			if got != testCase.expected {
				t.Errorf("backupProgressed() = %q, want %q", got, testCase.expected)
			}
		})
	}
}

func TestProbeUtilBackupRender_EveryRowCarriesOneCellPerDeclaredColumn(t *testing.T) {
	if len(backupListRights) != len(backupListWidths) {
		t.Fatalf("declared %d widths against %d alignments, want one of each", len(backupListWidths), len(backupListRights))
	}
	root := t.TempDir()
	run := "2026-09-22_01-00-00"
	runPath := backupRunPath(root, run)
	if err := os.MkdirAll(stageDir(runPath, metric.BackupStageTertiary), 0o755); err != nil {
		t.Fatalf("mkdir tertiary: %v", err)
	}
	if err := writeAtomic(stageStatusPath(runPath, metric.BackupStageTertiary), backupSummary{
		RunID: run, State: metric.BackupStateSuccess, Trigger: metric.BackupTriggerSystem, SuccessBool: true,
		FinishedTS: time.Now().Format(time.RFC3339), SizeMB: 4096, DiskUsedMB: 7700000, DiskTotalMB: 9000000,
		DiskUsagePerc: 85.5,
	}); err != nil {
		t.Fatalf("write tertiary: %v", err)
	}
	cells := func(row string) int { return strings.Count(row, "|") - 1 }
	for _, row := range backupTable(root) {
		if strings.HasPrefix(row, "+") {
			continue
		}
		if got := cells(row); got != len(backupListWidths) {
			t.Errorf("row [%s] carries %d cells, want %d", row, got, len(backupListWidths))
		}
	}
	if got := cells(backupListRow(root, run)); got != len(backupListWidths) {
		t.Errorf("backupListRow() carries %d cells, want %d", got, len(backupListWidths))
	}
}

func TestProbeUtilBackupRender_BoundedStatesWhetherTheEstimateBeatsTheDeadline(t *testing.T) {
	now := time.Date(2026, 9, 24, 10, 54, 19, 0, time.Local)
	deadline := now.Add(2 * time.Hour)
	cases := []struct {
		name      string
		remaining reading
		deadline  time.Time
		expected  string
	}{
		{name: "an_estimate_inside_the_deadline_is_within", remaining: floatReading(78), deadline: deadline,
			expected: " within timeout time [12:54:19]"},
		{name: "an_estimate_past_the_deadline_is_beyond", remaining: floatReading(200), deadline: deadline,
			expected: " BEYOND timeout time [12:54:19]"},
		{name: "no_estimate_states_nothing", remaining: unknownReading(), deadline: deadline},
		{name: "no_deadline_states_nothing", remaining: floatReading(78)},
	}
	for _, test := range cases {
		t.Run(test.name, func(t *testing.T) {
			if got := backupBounded(now, test.remaining, test.deadline); got != test.expected {
				t.Errorf("backupBounded() = %q, want %q", got, test.expected)
			}
		})
	}
}

func TestProbeUtilBackupRender_AProgressLineFitsOneDetailColumn(t *testing.T) {
	tests := []struct {
		name     string
		verb     string
		copied   reading
		total    reading
		percent  reading
		remains  reading
		rate     reading
		deadline time.Time
	}{
		{name: "every_field_at_its_widest", verb: backupVerb(metric.BackupStageTertiary), copied: intReading(9999),
			total: intReading(9999), percent: intReading(100), remains: intReading(9999), rate: intReading(999),
			deadline: time.Date(2026, 9, 24, 23, 59, 59, 0, time.Local)},
		{name: "a_deadline_it_will_miss", verb: backupVerb(metric.BackupStageTertiary), copied: intReading(9999),
			total: intReading(9999), percent: intReading(100), remains: intReading(9999), rate: intReading(999),
			deadline: time.Date(2026, 9, 24, 12, 6, 0, 0, time.Local)},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			now := time.Date(2026, 9, 24, 12, 5, 53, 0, time.Local)
			line := backupProgressed(testCase.copied, testCase.total, testCase.percent, testCase.remains,
				backupEta(now, testCase.remains), testCase.rate, backupBounded(now, testCase.remains, testCase.deadline))
			if strings.HasPrefix(line, testCase.verb) {
				t.Errorf("progress line repeats the verb column it sits beside\n%s", line)
			}
			if !strings.HasPrefix(line, "[") {
				t.Errorf("progress line does not lead with a bracketed value\n%s", line)
			}
			if len(line) > scribe.Detailed() {
				t.Errorf("progress line is [%d] characters against a [%d] detail column, so it wraps\n%s",
					len(line), scribe.Detailed(), line)
			}
		})
	}
}

func TestProbeUtilBackupRender_ScrubWordSeparatesAResumedPassFromAFreshOne(t *testing.T) {
	tests := []struct {
		name     string
		document scrubSummary
		expected string
	}{
		{name: "a_fresh_pass_is_running", document: scrubSummary{State: metric.BackupStateRunning}, expected: metric.BackupStateRunning},
		{name: "a_resumed_pass_says_so", document: scrubSummary{State: metric.BackupStateRunning, ResumedBool: true}, expected: backupResumedCell},
		{name: "a_finished_pass_keeps_its_state", document: scrubSummary{State: metric.BackupStateSuccess, ResumedBool: true}, expected: metric.BackupStateSuccess},
		{name: "an_empty_state_is_unknown", document: scrubSummary{}, expected: backupUnknownState},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			if word := scrubWord(testCase.document); word != testCase.expected {
				t.Errorf("scrubWord() = %q, want %q", word, testCase.expected)
			}
		})
	}
}

func TestProbeUtilBackupRender_TailDropsTheHeaderTheStreamedLogCarries(t *testing.T) {
	path := filepath.Join(t.TempDir(), "run.log")
	header := scribe.Header()
	body := header + "\n09-24T12:50:34 INFO  backup   host   start   0ms starting [a run]\n"
	if err := os.WriteFile(path, []byte(body), 0o644); err != nil {
		t.Fatalf("write run log: %v", err)
	}
	printed, offset := capturedStdout(t, func() int64 { return tailLog(path, 0) })
	if strings.Contains(printed, "DETAIL") {
		t.Errorf("tailLog() printed a second header\n%s", printed)
	}
	if !strings.Contains(printed, "starting [a run]") {
		t.Errorf("tailLog() dropped the line it was following\n%s", printed)
	}
	if offset != int64(len(body)) {
		t.Errorf("tailLog() = %d, want the whole file consumed at %d", offset, len(body))
	}
	if _, again := capturedStdout(t, func() int64 { return tailLog(path, offset) }); again != offset {
		t.Errorf("tailLog() moved past the end of the file")
	}
	if err := os.WriteFile(path, []byte(body+"09-24T12:50:35 INFO  backup   host   start   0ms half a li"), 0o644); err != nil {
		t.Fatalf("append partial line: %v", err)
	}
	printed, held := capturedStdout(t, func() int64 { return tailLog(path, offset) })
	if printed != "" || held != offset {
		t.Errorf("tailLog() = (%q, %d), want a line still being written withheld until its newline arrives", printed, held)
	}
}

func capturedStdout(t *testing.T, body func() int64) (string, int64) {
	t.Helper()
	reader, writer, err := os.Pipe()
	if err != nil {
		t.Fatalf("pipe: %v", err)
	}
	original := os.Stdout
	os.Stdout = writer
	offset := body()
	os.Stdout = original
	_ = writer.Close()
	printed, _ := io.ReadAll(reader)
	return string(printed), offset
}

func TestProbeUtilBackupRender_AnUnmeasuredBackupDiskRendersNoSizeFreeOrUsed(t *testing.T) {
	tests := []struct {
		name          string
		diskTotalMB   int
		diskUsedMB    int
		diskUsagePerc float64
		expectedCells int
	}{
		{name: "a_stage_that_measured_the_disk", diskTotalMB: 900, diskUsedMB: 700, diskUsagePerc: 77.8},
		{name: "a_stage_that_never_mounted_it", expectedCells: 3},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			root, run := t.TempDir(), "2026-09-22_01-00-00"
			path := stageStatusPath(backupRunPath(root, run), metric.BackupStageTertiary)
			if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
				t.Fatalf("mkdir stage: %v", err)
			}
			if err := writeAtomic(path, backupSummary{RunID: run, State: metric.BackupStateSuccess, SizeMB: 12,
				DiskTotalMB: testCase.diskTotalMB, DiskUsedMB: testCase.diskUsedMB, DiskUsagePerc: testCase.diskUsagePerc}); err != nil {
				t.Fatalf("write stage: %v", err)
			}
			row := backupListRow(root, run)
			columns := strings.Split(row, "|")
			unknown := 0
			for _, column := range columns[len(columns)-5 : len(columns)-2] {
				if strings.TrimSpace(column) == backupUnknownCell {
					unknown++
				}
			}
			if unknown != testCase.expectedCells {
				t.Errorf("backupListRow() = %q, want [%d] of SIZE, FREE and USED unreported, got [%d]",
					row, testCase.expectedCells, unknown)
			}
		})
	}
}

func TestProbeUtilBackupRender_ARunWithNoDocumentAtAllReportsNoResult(t *testing.T) {
	root, run := t.TempDir(), "2026-09-22_01-00-00"
	if err := os.MkdirAll(backupRunPath(root, run), 0o755); err != nil {
		t.Fatalf("mkdir run: %v", err)
	}
	row := backupListRow(root, run)
	columns := strings.Split(row, "|")
	if result := strings.TrimSpace(columns[len(columns)-2]); result != backupUnknownCell {
		t.Errorf("backupListRow() RESULT = %q, want %q rather than a success over nothing", result, backupUnknownCell)
	}
}

func TestProbeUtilBackupRender_AStageThatNeverReachedTheScrubSaysWhy(t *testing.T) {
	tests := []struct {
		name           string
		tertiaryState  string
		expectedColumn string
	}{
		{name: "a_host_mirroring_nowhere_skipped_its_scrub_too", tertiaryState: metric.BackupStateSkipped,
			expectedColumn: metric.BackupStateSkipped},
		{name: "a_tertiary_that_failed_before_the_scrub_is_unknown", tertiaryState: metric.BackupStateFailure,
			expectedColumn: backupUnknownCell},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			root, run := t.TempDir(), "2026-09-24_16-30-37"
			path := stageStatusPath(backupRunPath(root, run), metric.BackupStageTertiary)
			if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
				t.Fatalf("mkdir stage: %v", err)
			}
			if err := writeAtomic(path, backupSummary{RunID: run, State: testCase.tertiaryState}); err != nil {
				t.Fatalf("write stage: %v", err)
			}
			columns := strings.Split(backupListRow(root, run), "|")
			if scrub := strings.TrimSpace(columns[8]); scrub != testCase.expectedColumn {
				t.Errorf("SCRUB = %q, want %q", scrub, testCase.expectedColumn)
			}
		})
	}
}
