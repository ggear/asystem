package probe

import (
	"fmt"
	"io"
	"math"
	"os"
	"slices"
	"strconv"
	"strings"
	"time"

	"supervisor/internal/metric"
	"supervisor/internal/scribe"
)

func runBackupList() error {
	root := backupRunRoot()
	rows := backupTable(root)
	if len(rows) == 0 {
		scribe.Log(scribe.SourceBackup, scribe.SubjectNone, scribe.ActionCensus).Warnf("faulting", time.Now(), "[none] backup runs under [%s]", root)
		return nil
	}
	fmt.Println()
	for _, row := range rows {
		fmt.Println(row)
	}
	fmt.Println()
	return nil
}

func runBackupTail(request BackupRequest) error {
	root := backupRunRoot()
	runID, err := backupResolveRun(root, request.RunID)
	if err != nil {
		return err
	}
	scribe.Log(scribe.SourceBackup, scribe.SubjectNone, scribe.ActionStart).Infof("followed", time.Now(),
		"[%s] tracking this run under [%s]", runID, backupRunPath(root, runID))
	running := func() bool {
		snapshot := readBackupRun(root, runID)
		if snapshot.host != nil {
			return false
		}
		for _, stage := range backupStages {
			if document := snapshot.stages[stage]; document != nil && document.State == metric.BackupStateRunning {
				return true
			}
		}
		return false
	}
	offset := int64(0)
	for {
		offset = tailLog(runLogPath(backupRunPath(root, runID)), offset)
		if !running() {
			break
		}
		time.Sleep(backupTailPoll)
	}
	offset = tailLog(runLogPath(backupRunPath(root, runID)), offset)
	fmt.Println()
	for _, heading := range backupHeading() {
		fmt.Println(heading)
	}
	fmt.Println(backupListRow(root, runID))
	fmt.Println(backupRule("+", '-'))
	fmt.Println()
	return nil
}

func tailLog(path string, offset int64) int64 {
	file, err := os.Open(path)
	if err != nil {
		return offset
	}
	defer func() { _ = file.Close() }()
	if _, err := file.Seek(offset, io.SeekStart); err != nil {
		return offset
	}
	data, err := io.ReadAll(file)
	if err != nil || len(data) == 0 {
		return offset
	}
	fmt.Print(string(data))
	return offset + int64(len(data))
}

func backupHeading() []string {
	return []string{backupRule("+", '-'),
		backupRow(
			"STARTED (RUN-ID)",
			"FINISHED",
			"DURATION",
			"TRIGGER",
			"PRIMARY",
			"SECONDARY",
			"TERTIARY",
			"SCRUB",
			"DELTA",
			"SIZE",
			"FREE",
			"USED",
			"RESULT",
		),
		backupRule("+", '=')}
}

func backupTable(root string) []string {
	runs := backupRuns(root)
	if len(runs) == 0 {
		return nil
	}
	rows := backupHeading()
	for _, run := range slices.Backward(runs) {
		rows = append(rows, backupListRow(root, run))
	}
	return append(rows, backupRule("+", '-'))
}

func backupListRow(root, run string) string {
	snapshot := readBackupRun(root, run)
	runPath := backupRunPath(root, run)
	trigger := unknownCell
	cells := make([]string, 0, len(backupStages))
	states := map[metric.BackupStage]string{}
	sized, size := false, 0
	usedDiskMB, totalDiskMB := -1, -1
	for _, stage := range backupStages {
		document := snapshot.stages[stage]
		cells = append(cells, backupStateWord(document))
		if document == nil {
			continue
		}
		states[stage] = document.State
		if trigger == unknownCell && document.Trigger != "" {
			trigger = document.Trigger
		}
		size += document.SizeMB
		sized = true
		if stage == metric.BackupStageTertiary {
			usedDiskMB, totalDiskMB = document.DiskUsedMB, document.DiskTotalMB
		}
	}
	scrubState, scrubDeclared := unknownCell, ""
	if document := readScrubSummary(scrubStatusPath(runPath)); document != nil {
		scrubState, scrubDeclared = document.State, document.State
	}
	result := resolvedState(states, scrubDeclared)
	if snapshot.host != nil {
		result = snapshot.host.State
	}
	began, _ := runStarted(backupSummary{RunID: run})
	finished, elapsed := unknownCell, unknownCell
	latest := latestFinished(snapshot)
	if result == metric.BackupStateRunning {
		elapsed = backupElapsed(int64(time.Since(began).Seconds()))
	} else if !latest.IsZero() {
		if latest.After(began) {
			elapsed = backupElapsed(int64(latest.Sub(began).Seconds()))
		}
		finished = latest.Format(backupTimestampFormat)
	}
	sizeReading := unknownReading()
	if sized {
		sizeReading = intReading(int64(size))
	}
	freeReading := unknownReading()
	usedReading := unknownReading()
	volume := unknownReading()
	if usedDiskMB >= 0 {
		usedReading = intReading(int64(usedDiskMB))
	}
	if usedDiskMB >= 0 && totalDiskMB >= 0 {
		freeReading = intReading(int64(totalDiskMB - usedDiskMB))
	}
	if snapshot.tertiary != nil {
		volume = floatReading(snapshot.tertiary.DiskUsagePerc)
	}
	return backupRow(append([]string{run, finished, elapsed, trigger}, append(cells, scrubState,
		backupMegabytes(sizeReading), backupTerabytes(usedReading), backupTerabytes(freeReading), backupBar(volume), result)...)...)
}

func backupRow(values ...string) string {
	var out strings.Builder
	out.WriteByte('|')
	for index, value := range values {
		width := backupListWidths[index]
		if backupListRights[index] {
			fmt.Fprintf(&out, " %*s |", width, value)
		} else {
			fmt.Fprintf(&out, " %-*s |", width, value)
		}
	}
	return out.String()
}

func backupRule(joined string, fill byte) string {
	var out strings.Builder
	out.WriteByte('+')
	for index, width := range backupListWidths {
		if index > 0 {
			out.WriteString(joined)
		}
		out.WriteString(strings.Repeat(string(fill), width+2))
	}
	out.WriteByte('+')
	return out.String()
}

func backupStateWord(document *backupSummary) string {
	if document == nil {
		return unknownCell
	}
	if document.State == "" {
		return unknownState
	}
	return document.State
}

func latestFinished(snapshot *backupSnapshot) time.Time {
	var latest time.Time
	for _, stage := range backupStages {
		document := snapshot.stages[stage]
		if document == nil || document.FinishedTS == "" {
			continue
		}
		if finished, err := time.Parse(time.RFC3339, document.FinishedTS); err == nil && finished.After(latest) {
			latest = finished
		}
	}
	return latest
}

func backupBounded(now time.Time, remaining reading, deadline time.Time) string {
	if !remaining.Known() || remaining.Value() < 0 || deadline.IsZero() {
		return ""
	}
	if now.Add(time.Duration(remaining.Rounded()) * time.Minute).After(deadline) {
		return fmt.Sprintf(" BEYOND timeout time [%s]", deadline.Format(backupTimeFormat))
	}
	return fmt.Sprintf(" within timeout time [%s]", deadline.Format(backupTimeFormat))
}

func backupProgressed(verb string, copied, total, percent, remaining reading, eta string, rate reading, bounded string) string {
	last := 0
	if total.known {
		last = 1
	}
	if rate.known {
		last = 2
	}
	if percent.known {
		last = 3
	}
	if remaining.known {
		last = 4
	}
	line := fmt.Sprintf("%s [%s] GiB", verb, backupSized(copied))
	if last >= 1 {
		line += fmt.Sprintf(" of [%s] GiB", backupSized(total))
	}
	if last >= 2 {
		line += fmt.Sprintf(" at [%s] MiB/s", backupThroughput(rate))
	}
	if last >= 3 {
		line += fmt.Sprintf(" at [%s] percent complete", backupPercent(percent))
	}
	if last >= 4 {
		line += fmt.Sprintf(" and estimated to complete in [%s] min at [%s]%s", backupMinutes(remaining), eta, bounded)
	}
	return line
}

func backupVerb(stage metric.BackupStage) string {
	switch stage {
	case metric.BackupStagePrimary:
		return "exported"
	case metric.BackupStageSecondary:
		return "promoted"
	case metric.BackupStageTertiary:
		return "mirrored"
	default:
		return "captured"
	}
}

func backupEta(now time.Time, remainingMinutes reading) string {
	if !remainingMinutes.known || remainingMinutes.value < 0 {
		return unknownEta
	}
	return now.Add(time.Duration(remainingMinutes.Rounded()) * time.Minute).Format(backupTimeFormat)
}

func backupRated(megabytes, seconds reading) reading {
	if !megabytes.known || !seconds.known || seconds.value <= 0 || megabytes.value < 0 {
		return unknownReading()
	}
	return floatReading(megabytes.value / seconds.value)
}

func backupSized(r reading) string { return padLeft(digits(r), backupSizedWidth) }

func backupPercent(r reading) string { return padLeft(digits(r), backupPercentWidth) }

func backupThroughput(r reading) string { return padLeft(digits(r), backupThroughputWidth) }

func backupMinutes(r reading) string { return padLeft(digits(r), backupMinutesWidth) }

func backupMegabytes(r reading) string {
	if !r.known || r.value < 0 {
		return unknownCell
	}
	return groupedDigits(r.Rounded()) + " MiB"
}

func backupTerabytes(r reading) string {
	if !r.known || r.value < 0 {
		return unknownCell
	}
	tenths := int64(math.Round(r.value * 10 / mebibytesPerTebibyte))
	return fmt.Sprintf("%d.%d TiB", tenths/10, tenths%10)
}

func backupElapsed(seconds int64) string {
	return fmt.Sprintf("%02dh%02dm%02ds", seconds/3600, seconds%3600/60, seconds%60)
}

func backupBar(percent reading) string {
	if !percent.known || percent.value < 0 {
		return unknownCell
	}
	clamped := min(percent.Rounded(), 100)
	filled := int(clamped) * backupBarWidth / 100
	return fmt.Sprintf("[%s%s] %s%%", strings.Repeat("#", filled), strings.Repeat(".", backupBarWidth-filled), backupPercent(intReading(clamped)))
}

func groupedDigits(value int64) string {
	text := strconv.FormatInt(value, 10)
	if len(text) <= 3 {
		return text
	}
	var parts []string
	for len(text) > 3 {
		parts = append([]string{text[len(text)-3:]}, parts...)
		text = text[:len(text)-3]
	}
	return strings.Join(append([]string{text}, parts...), ",")
}

func digits(r reading) string {
	if !r.known {
		return unknownCell
	}
	return strconv.FormatInt(r.Rounded(), 10)
}

func padLeft(text string, width int) string {
	if len(text) >= width {
		return text
	}
	return strings.Repeat(" ", width-len(text)) + text
}

type reading struct {
	value float64
	known bool
}

func unknownReading() reading { return reading{} }

func intReading(value int64) reading { return reading{value: float64(value), known: true} }

func floatReading(value float64) reading { return reading{value: value, known: true} }

func (r reading) Known() bool { return r.known }

func (r reading) Value() float64 { return r.value }

func (r reading) Rounded() int64 { return int64(math.Round(r.value)) }

type sampleRing struct {
	points  []ringSample
	limit   int
	quantum int64
}

type ringSample struct {
	at    time.Time
	bytes int64
}

func newSampleRing(limit int, quantum int64) *sampleRing {
	return &sampleRing{limit: limit, quantum: quantum}
}

func (r *sampleRing) push(at time.Time, bytes int64) {
	if len(r.points) == 0 {
		r.points = append(r.points, ringSample{at: at, bytes: bytes})
		return
	}
	last := r.points[len(r.points)-1]
	if bytes < last.bytes {
		r.points = []ringSample{{at: at, bytes: bytes}}
		return
	}
	if bytes-last.bytes < r.quantum {
		return
	}
	r.points = append(r.points, ringSample{at: at, bytes: bytes})
	if len(r.points) > r.limit {
		r.points = r.points[len(r.points)-r.limit:]
	}
}

func (r *sampleRing) rate() reading {
	if len(r.points) < ringMinimum {
		return unknownReading()
	}
	measured := r.points[1:]
	base := measured[0].at
	var n, sumX, sumY, sumXY, sumXX float64
	for _, point := range measured {
		x := point.at.Sub(base).Seconds()
		y := float64(point.bytes)
		n++
		sumX += x
		sumY += y
		sumXY += x * y
		sumXX += x * x
	}
	denominator := n*sumXX - sumX*sumX
	if denominator == 0 {
		return unknownReading()
	}
	slope := (n*sumXY - sumX*sumY) / denominator
	if slope <= 0 {
		return unknownReading()
	}
	return floatReading(slope / bytesPerMebibyte)
}

var (
	backupListWidths = []int{19, 19, 9, 9, 9, 9, 9, 9, 11, 8, 8, 25, 10}
	backupListRights = func() []bool {
		rights := make([]bool, len(backupListWidths))
		for _, column := range []int{2, 8, 9, 10, 11} {
			rights[column] = true
		}
		return rights
	}()
)

const (
	bytesPerMebibyte     = 1048576
	bytesPerGibibyte     = 1024 * bytesPerMebibyte
	mebibytesPerGibibyte = 1024
	mebibytesPerTebibyte = 1024 * mebibytesPerGibibyte

	backupSizedWidth      = 4
	backupPercentWidth    = 2
	backupThroughputWidth = 3
	backupMinutesWidth    = 4
	backupBarWidth        = 18

	unknownEta   = "--:--:--"
	unknownCell  = "-"
	unknownState = "unknown"

	ringMinimum = 3
	ringPoints  = 12
	ringQuantum = 100 * bytesPerMebibyte

	backupProgressHeartbeat = 10 * time.Second
	backupTailPoll          = 2 * time.Second
)
