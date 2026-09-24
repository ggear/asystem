package probe

import (
	"context"
	"encoding/json"
	"fmt"
	"math"
	"os"
	"path/filepath"
	"regexp"
	"strconv"
	"strings"
	"time"

	"supervisor/internal/config"
	"supervisor/internal/metric"
	"supervisor/internal/scribe"
)

func runScrub(ctx context.Context, request stageRequest) bool {
	started := time.Now()
	stagePath := stageDir(request.RunPath, request.Stage)
	host := configHost(request.ConfigPath)
	subject := scribe.SubjectStage(request.Stage)
	skipped := func(reason string, args ...any) bool {
		scribe.Log(scribe.SourceBackup, subject, scribe.ActionCompute).Infof("excluded", started, reason, args...)
		writeScrubSummary(request, host, scrubDocument(request, metric.BackupStateSkipped, true, started, scrubReading{}))
		return true
	}

	forced := request.Scrub
	if !commandAvailable("btrfs") {
		return skipped("[%s] not scrubbing, [btrfs] is not on the path", config.DirBackup)
	}
	if _, code, abandoned := bounded(ctx, stageBoundedWait, "btrfs", "filesystem", "show", config.DirBackup); abandoned || code != 0 {
		return skipped("[%s] not scrubbing, btrfs did not answer for it", config.DirBackup)
	}
	statusOut, code, abandoned := bounded(ctx, stageBoundedWait, "btrfs", "scrub", "status", config.DirBackup)
	if abandoned || code != 0 {
		return skipped("[%s] not scrubbing, it did not report a scrub status", config.DirBackup)
	}

	action, reason := scrubAction(forced, request.Trigger, statusOut, started)
	if reason != "" {
		return skipped("[%s] not scrubbing, %s", config.DirBackup, reason)
	}

	hard := scrubDeadline(request, started)
	if !hard.After(started) {
		return skipped("[%s] not scrubbing, no time is left inside the run deadline", config.DirBackup)
	}

	cursor := kernelCursor(ctx)
	scribe.Log(scribe.SourceBackup, subject, scribe.ActionStart).Infof("scrubbed", started,
		"[%s] scrub [%s] at [%s], polling every [%s]", config.DirBackup, action, hard.Format(backupTimeFormat), scrubPollInterval)
	if out, code, abandoned := bounded(ctx, stageBoundedWait, "btrfs", "scrub", action, "-c", "3", "-n", "15", config.DirBackup); abandoned || code != 0 {
		scribe.Log(scribe.SourceBackup, subject, scribe.ActionCompute).Errorf("faulting", started,
			"[%s] scrub [%s] exited [%d] abandoned [%t] reporting [%s], the disk was not scrubbed", config.DirBackup, action, code,
			abandoned, strings.Join(strings.Fields(out), " "))
		writeScrubSummary(request, host, scrubDocument(request, metric.BackupStateFailure, false, started, scrubReading{}))
		return false
	}
	baseline, _ := scrubReadNow(ctx)

	reached := 0.0
	silent := 0
	halt := ""
	samples := newSampleRing(ringPoints, ringQuantum)
	var lastReading scrubReading
	for {
		select {
		case <-ctx.Done():
			cancelScrub(ctx)
			goto finished
		case <-time.After(scrubPollInterval):
		}
		if time.Now().After(hard) {
			scribe.Log(scribe.SourceBackup, subject, scribe.ActionStop).Warnf("faulting", started,
				"[%s] scrub ran past [%s], cancelling it, resumed on the next run", config.DirBackup, hard.Format(backupTimeFormat))
			halt = metric.BackupStateTimeout
			cancelScrub(ctx)
			break
		}
		reading, ok := scrubReadNow(ctx)
		if !ok {
			silent++
			scribe.Log(scribe.SourceBackup, subject, scribe.ActionSample).Warnf("faulting", started,
				"[%s] scrub status unanswered [%d] of [%d] times, the disk may have gone", config.DirBackup, silent, scrubSilenceLimit)
			if silent < scrubSilenceLimit {
				continue
			}
			halt = metric.BackupStateFailure
			cancelScrub(ctx)
			break
		}
		silent = 0
		lastReading = reading
		if reading.progress >= 1 {
			reached = reading.progress
		}
		display := reading
		display.progress = reached
		running := scrubDocument(request, metric.BackupStateRunning, false, started, display)
		running.ExpiresTS = hard.Format(time.RFC3339)
		writeScrubSummary(request, host, running)
		now := time.Now()
		samples.push(now, int64(reading.scrubbedMB)*bytesPerMebibyte)
		rate := samples.rate()
		remaining := scrubRemaining(reading, reached, rate)
		scribe.Log(scribe.SourceBackup, subject, scribe.ActionCompute).Infof("scrubbed", now,
			"%s", backupProgressed("scrubbed", intReading(int64(reading.scrubbedMB)/mebibytesPerGibibyte), scrubTotal(reading, reached),
				scrubPercent(reached), remaining, backupEta(now, remaining), rate))
		if !reading.running {
			break
		}
	}

finished:
	ctx = context.WithoutCancel(ctx)
	if final, ok := scrubReadNow(ctx); ok {
		lastReading = final
	}
	if halt == "" {
		halt = scrubHalt(stagePath)
	}
	if lastReading.progress == 0 {
		lastReading.progress = reached
	}
	lastReading.found = max(lastReading.found-baseline.found, 0)
	lastReading.corrected = max(lastReading.corrected-baseline.corrected, 0)
	lastReading.uncorrectable = max(lastReading.uncorrectable-baseline.uncorrectable, 0)

	deviceErrors, counted := deviceStatsSum(ctx)
	state, success := metric.BackupStateSuccess, true
	if halt != "" {
		state, success = halt, false
	}
	if !counted {
		state, success = metric.BackupStateFailure, false
		scribe.Log(scribe.SourceBackup, subject, scribe.ActionCompute).Errorf("faulting", started,
			"[%s] device stats could not be read, so this scrub cannot report the disk clean", config.DirBackup)
	}
	var corrupt []string
	if lastReading.found > 0 || lastReading.uncorrectable > 0 || deviceErrors > 0 {
		state, success = metric.BackupStateFailure, false
		logged := kernelSince(ctx, cursor)
		corrupt = kernelCorrupted(logged)
		scrubLog(ctx, stagePath, corrupt, kernelFaulted(logged))
		if len(corrupt) > 0 {
			scribe.Log(scribe.SourceBackup, subject, scribe.ActionCompute).Errorf("faulting", started,
				"[%s] scrub found [%d] errors with [%d] uncorrectable and [%d] device errors across [%d] files, delete them and re-mirror, listed in [%s]",
				config.DirBackup, lastReading.found, lastReading.uncorrectable, deviceErrors, len(corrupt), filepath.Join(stagePath, scrubLogLeaf))
		} else {
			scribe.Log(scribe.SourceBackup, subject, scribe.ActionCompute).Errorf("faulting", started,
				"[%s] scrub found [%d] errors with [%d] uncorrectable and [%d] device errors naming no corrupt file, so the disk read badly rather than held bad data, see [%s]",
				config.DirBackup, lastReading.found, lastReading.uncorrectable, deviceErrors, filepath.Join(stagePath, scrubLogLeaf))
		}
	}
	if deviceErrors > 0 || lastReading.found > 0 {
		_, _, _ = bounded(ctx, stageBoundedWait, "btrfs", "device", "stats", "-z", config.DirBackup)
	}
	relocated := 0
	if state == metric.BackupStateSuccess && time.Now().Before(hard) {
		relocated = runBalance(ctx, subject)
	}
	document := scrubDocument(request, state, success, started, lastReading)
	document.DeviceErrors = deviceErrors
	document.ChunksRelocated = relocated
	document.FilesToDeleteCount = len(corrupt)
	if len(corrupt) > kernelCorruptNamed {
		corrupt = corrupt[:kernelCorruptNamed]
	}
	document.FilesToDelete = strings.Join(corrupt, ",")
	writeScrubSummary(request, host, document)
	scribe.Log(scribe.SourceBackup, subject, scribe.ActionStop).Infof("scrubbed", started,
		"[%s] scrub finished as [%s] at [%s] percent having scrubbed [%s] MiB with [%d] chunks relocated",
		config.DirBackup, state, backupPercent(floatReading(lastReading.progress)), backupSized(intReading(int64(lastReading.scrubbedMB))), relocated)
	return success
}

func scrubAction(forced bool, trigger, status string, now time.Time) (action, reason string) {
	lower := strings.ToLower(status)
	if strings.Contains(lower, "interrupted") || strings.Contains(lower, "aborted") {
		return "resume", ""
	}
	if !forced && (trigger != metric.BackupTriggerSystem || now.Day() < scrubWindowDay || now.Day() >= scrubWindowDay+scrubWindowDays) {
		return "", fmt.Sprintf("a [%s] run outside days [%d] to [%d] of the month does not scrub, pass [--scrub] to force one",
			trigger, scrubWindowDay, scrubWindowDay+scrubWindowDays-1)
	}
	if since := scrubStartedField(status); !forced && since != "" && sameScrubMonth(since, now) {
		return "", fmt.Sprintf("the last pass started [%s] in this month already, pass [--scrub] to force one", since)
	}
	return "start", ""
}

func scrubHalt(stagePath string) string {
	if _, err := os.Stat(filepath.Join(stagePath, stageTimedOutMarker)); err == nil {
		return metric.BackupStateTimeout
	}
	if _, err := os.Stat(filepath.Join(stagePath, stageStoppedMarker)); err == nil {
		return metric.BackupStateStopped
	}
	return ""
}

func scrubLog(ctx context.Context, stagePath string, corrupt, faulted []string) {
	counters, _, _ := bounded(ctx, stageBoundedWait, "btrfs", "scrub", "status", "-R", config.DirBackup)
	stats, _, _ := bounded(ctx, stageBoundedWait, "btrfs", "device", "stats", config.DirBackup)
	sections := []string{counters, stats, strings.Join(corrupt, "\n"), strings.Join(faulted, "\n")}
	_ = os.WriteFile(filepath.Join(stagePath, scrubLogLeaf), []byte(strings.Join(sections, "\n\n")+"\n"), 0o644)
}

func scrubTotal(reading scrubReading, reached float64) reading {
	if reached <= 0 {
		return unknownReading()
	}
	return intReading(int64(float64(reading.scrubbedMB)*100/math.Round(reached)) / mebibytesPerGibibyte)
}

func scrubPercent(reached float64) reading {
	if reached <= 0 {
		return unknownReading()
	}
	return floatReading(reached)
}

func scrubRemaining(reading scrubReading, reached float64, rate reading) reading {
	if reached <= 0 || reached >= 100 || !rate.Known() || rate.Value() <= 0 {
		return unknownReading()
	}
	remaining := float64(reading.scrubbedMB)/reached*100 - float64(reading.scrubbedMB)
	return floatReading(remaining / rate.Value() / 60)
}

func cancelScrub(ctx context.Context) {
	if !commandAvailable("btrfs") {
		return
	}
	_, _, _ = bounded(context.WithoutCancel(ctx), stageBoundedWait, "btrfs", "scrub", "cancel", config.DirBackup)
}

func scrubReadNow(ctx context.Context) (scrubReading, bool) {
	rawOut, code, abandoned := bounded(ctx, stageBoundedWait, "btrfs", "scrub", "status", "-R", config.DirBackup)
	if abandoned || code != 0 {
		return scrubReading{}, false
	}
	statusOut, code, abandoned := bounded(ctx, stageBoundedWait, "btrfs", "scrub", "status", config.DirBackup)
	if abandoned || code != 0 {
		return scrubReading{}, false
	}
	reading := scrubReading{
		scrubbedMB:    int(scrubCounter(rawOut, "data_bytes_scrubbed") / bytesPerMebibyte),
		corrected:     int(scrubCounter(rawOut, "corrected_errors")),
		uncorrectable: int(scrubCounter(rawOut, "uncorrectable_errors")),
		found:         int(scrubCounter(rawOut, "csum_errors") + scrubCounter(rawOut, "verify_errors") + scrubCounter(rawOut, "super_errors")),
	}
	if match := scrubProgressPattern.FindStringSubmatch(statusOut); match != nil {
		if value, err := strconv.ParseFloat(match[1], 64); err == nil {
			reading.progress = min(value, 100)
		}
	}
	lower := strings.ToLower(statusOut)
	rawLower := strings.ToLower(rawOut)
	if strings.Contains(lower, "aborted") || strings.Contains(lower, "interrupted") {
		reading.running = false
	} else {
		reading.running = strings.Contains(rawLower, "status:") && strings.Contains(rawLower, "running")
	}
	return reading, true
}

func scrubCounter(output, key string) int64 {
	match := scrubCounterPatterns[key].FindStringSubmatch(output)
	if match == nil {
		return 0
	}
	value, _ := strconv.ParseInt(match[1], 10, 64)
	return value
}

func deviceStatsSum(ctx context.Context) (int, bool) {
	out, code, abandoned := bounded(ctx, stageBoundedWait, "btrfs", "device", "stats", config.DirBackup)
	if abandoned || code != 0 {
		return 0, false
	}
	total := 0
	for _, pattern := range deviceStatsPatterns {
		for _, match := range pattern.FindAllStringSubmatch(out, -1) {
			value, _ := strconv.Atoi(match[1])
			total += value
		}
	}
	return total, true
}

func runBalance(ctx context.Context, subject scribe.Subject) int {
	started := time.Now()
	out, code, abandoned := bounded(ctx, scrubBalanceWait, "btrfs", "balance", "start", "-dusage=10", "-musage=10", config.DirBackup)
	if abandoned || code != 0 {
		scribe.Log(scribe.SourceBackup, subject, scribe.ActionCompute).Warnf("faulting", started,
			"[%s] could not be balanced, exited [%d] abandoned [%t]", config.DirBackup, code, abandoned)
		return 0
	}
	relocated := 0
	if match := balanceRelocatedPattern.FindStringSubmatch(out); match != nil {
		relocated, _ = strconv.Atoi(match[1])
	}
	scribe.Log(scribe.SourceBackup, subject, scribe.ActionCompute).Infof("balanced", started,
		"[%s] balanced with [%d] chunks relocated", config.DirBackup, relocated)
	return relocated
}

func scrubStartedField(status string) string {
	match := scrubStartedPattern.FindStringSubmatch(status)
	if match == nil {
		return ""
	}
	return strings.TrimSpace(match[1])
}

func sameScrubMonth(since string, now time.Time) bool {
	for _, layout := range []string{"Mon Jan  2 15:04:05 2006", "Mon Jan 2 15:04:05 2006", time.ANSIC} {
		if parsed, err := time.ParseInLocation(layout, since, time.Local); err == nil {
			return parsed.Year() == now.Year() && parsed.Month() == now.Month()
		}
	}
	return false
}

func scrubDeadline(request stageRequest, started time.Time) time.Time {
	if request.Expires.IsZero() {
		return started.Add(time.Hour)
	}
	hard := request.Expires.Add(-scrubMargin)
	if !hard.After(started) {
		return started
	}
	return hard
}

func scrubDocument(request stageRequest, state string, success bool, started time.Time, reading scrubReading) scrubSummary {
	return scrubSummary{
		RunID: request.RunID, State: state, StartedTS: started.Format(time.RFC3339),
		FinishedTS: time.Now().Format(time.RFC3339), DurationS: int(time.Since(started).Seconds()),
		SuccessBool: success, ScrubbedMB: reading.scrubbedMB, ProgressPerc: reading.progress,
		ErrorsFound: reading.found, ErrorsCorrected: reading.corrected, ErrorsUncorrectable: reading.uncorrectable,
	}
}

func writeScrubSummary(request stageRequest, host string, document scrubSummary) {
	path := scrubStatusPath(request.RunPath)
	_ = os.MkdirAll(filepath.Dir(path), 0o755)
	if err := writeAtomic(path, document); err != nil {
		return
	}
	if client, err := brokerDial(request.ConfigPath, "scrub"); err == nil {
		defer client.close()
		if payload, marshalErr := json.Marshal(document); marshalErr == nil {
			_ = client.publishRetained(metric.TopicBackupScrub(host), string(payload))
		}
	}
}

type scrubReading struct {
	scrubbedMB, found, corrected, uncorrectable int
	progress                                    float64
	running                                     bool
}

var (
	scrubProgressPattern = regexp.MustCompile(`\(([0-9.]+)%\)`)

	scrubStartedPattern = regexp.MustCompile(`(?m)^Scrub started:\s*(.+)$`)

	balanceRelocatedPattern = regexp.MustCompile(`relocate (\d+) out of`)

	scrubCounterPatterns = func() map[string]*regexp.Regexp {
		patterns := map[string]*regexp.Regexp{}
		for _, key := range []string{"data_bytes_scrubbed", "corrected_errors", "uncorrectable_errors", "csum_errors", "verify_errors", "super_errors"} {
			patterns[key] = regexp.MustCompile(`(?m)^\s*` + regexp.QuoteMeta(key) + `:\s*(\d+)`)
		}
		return patterns
	}()

	deviceStatsPatterns = func() []*regexp.Regexp {
		var patterns []*regexp.Regexp
		for _, key := range []string{"write_io_errs", "read_io_errs", "flush_io_errs", "corruption_errs", "generation_errs"} {
			patterns = append(patterns, regexp.MustCompile(`\]\.`+regexp.QuoteMeta(key)+`\s+(\d+)`))
		}
		return patterns
	}()
)

const (
	scrubWindowDay  = 1
	scrubWindowDays = 3

	scrubPollInterval = 30 * time.Second
	scrubSilenceLimit = 3
	scrubMargin       = 15 * time.Minute
	scrubBalanceWait  = time.Hour

	scrubLogLeaf = "scrub.log"
)
