package probe

import (
	"os"
	"strings"
	"testing"
	"time"

	"supervisor/internal/metric"
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
		ring.push(base.Add(time.Duration(index)*time.Second), int64(index)*bytesPerMebibyte)
	}
	if got := len(ring.points); got != 1 {
		t.Errorf("points = %d, want 1 with every sample below the quantum dropped", got)
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
			expected: "mirrored [   5] GiB"},
		{name: "total_known", total: intReading(90), percent: unknownReading(), remain: unknownReading(), rate: unknownReading(),
			expected: "mirrored [   5] GiB of [  90] GiB"},
		{name: "rate_known_holds_an_unknown_total_with_a_dash", total: unknownReading(), percent: unknownReading(), remain: unknownReading(), rate: floatReading(102),
			expected: "mirrored [   5] GiB of [   -] GiB at [102] MiB/s"},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			got := backupProgressed(backupVerb(metric.BackupStageTertiary), intReading(5), testCase.total, testCase.percent, testCase.remain,
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
