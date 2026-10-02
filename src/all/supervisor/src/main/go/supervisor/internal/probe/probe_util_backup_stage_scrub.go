package probe

import (
	"context"
	"encoding/json"
	"fmt"
	"math"
	"os"
	"path/filepath"
	"regexp"
	"slices"
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
		publishScrubSummary(request, host, scrubDocument(request, metric.BackupStateSkipped, true, started, scrubReading{}))
		return true
	}

	forced := request.Scrub
	if !commandAvailable("btrfs") {
		scribe.Log(scribe.SourceBackup, subject, scribe.ActionCompute).Errorf("faulting", started,
			"[%s] cannot be scrubbed, [btrfs] is not on the path", config.DirBackup)
		publishScrubSummary(request, host, scrubDocument(request, metric.BackupStateFailure, false, started, scrubReading{}))
		return false
	}
	statusOut, code, abandoned := bounded(ctx, stageBoundedWait, "btrfs", "scrub", "status", config.DirBackup)
	if abandoned || code != 0 {
		scribe.Log(scribe.SourceBackup, subject, scribe.ActionCompute).Errorf("faulting", started,
			"[%s] scrub status exited [%d] abandoned [%t] reporting [%s], the disk cannot be scrubbed", config.DirBackup, code,
			abandoned, strings.Join(strings.Fields(statusOut), " "))
		publishScrubSummary(request, host, scrubDocument(request, metric.BackupStateFailure, false, started, scrubReading{}))
		return false
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
	out, code, abandoned := bounded(ctx, stageBoundedWait, "btrfs", "scrub", action, "-c", "3", "-n", "15", config.DirBackup)
	if !abandoned && code != 0 && action == scrubActionResume {
		scribe.Log(scribe.SourceBackup, subject, scribe.ActionStart).Warnf("faulting", started,
			"[%s] scrub [resume] exited [%d] reporting [%s], starting a fresh pass instead",
			config.DirBackup, code, strings.Join(strings.Fields(out), " "))
		action = scrubActionStart
		out, code, abandoned = bounded(ctx, stageBoundedWait, "btrfs", "scrub", action, "-c", "3", "-n", "15", config.DirBackup)
	}
	if abandoned || code != 0 {
		scribe.Log(scribe.SourceBackup, subject, scribe.ActionCompute).Errorf("faulting", started,
			"[%s] scrub [%s] exited [%d] abandoned [%t] reporting [%s], the disk was not scrubbed", config.DirBackup, action, code,
			abandoned, strings.Join(strings.Fields(out), " "))
		publishScrubSummary(request, host, scrubDocument(request, metric.BackupStateFailure, false, started, scrubReading{}))
		return false
	}
	scribe.Log(scribe.SourceBackup, subject, scribe.ActionStart).Infof("scrubbed", started,
		"[%s] scrub [%s] %s, pausing at [%s] to resume next run",
		config.DirBackup, action, scrubOrigin(action, statusOut), hard.Format(backupTimeFormat))
	resumed := action == scrubActionResume
	opening := scrubDocument(request, metric.BackupStateRunning, false, started, scrubReading{})
	opening.ResumedBool = resumed
	opening.ExpiresTS = hard.Format(time.RFC3339)
	publishScrubSummary(request, host, opening)
	baseline, _ := scrubReadNow(ctx)

	reached := 0.0
	var silent time.Time
	halt := ""
	cancelled := false
	paused := false
	samples := newSampleRing(ringPoints, ringQuantum)
	published := time.Now()
	var lastReading scrubReading
	for {
		select {
		case <-ctx.Done():
			cancelScrub(ctx)
			cancelled = true
			goto finished
		case <-time.After(backupProgressHeartbeat):
		}
		if time.Now().After(hard) {
			scribe.Log(scribe.SourceBackup, subject, scribe.ActionStop).Infof("scrubbed", started,
				"[%s] scrub reached [%s], pausing it at [%s] percent to resume on the next run", config.DirBackup,
				hard.Format(backupTimeFormat), backupPercent(floatReading(reached)))
			halt = metric.BackupStatePausing
			paused = true
			cancelScrub(ctx)
			break
		}
		reading, ok := scrubReadNow(ctx)
		if !ok {
			if silent.IsZero() {
				silent = time.Now()
			}
			scribe.Log(scribe.SourceBackup, subject, scribe.ActionSample).Warnf("faulting", started,
				"[%s] scrub status unanswered for [%s] s of [%s] s, the disk may have gone", config.DirBackup,
				elapsedSeconds(time.Since(silent)), elapsedSeconds(scrubSilenceGrace))
			if time.Since(silent) < scrubSilenceGrace {
				continue
			}
			halt = metric.BackupStateFailure
			cancelScrub(ctx)
			break
		}
		silent = time.Time{}
		if scrubbing := scrubUUID(statusOut); scrubbing != "" && reading.uuid != scrubbing {
			break
		}
		lastReading = reading
		if reading.progress >= 1 || (reading.measured && reading.progress > 0) {
			reached = reading.progress
		}
		display := reading
		display.progress = reached
		running := scrubDocument(request, metric.BackupStateRunning, false, started, display)
		running.ResumedBool = resumed
		running.ExpiresTS = hard.Format(time.RFC3339)
		now := time.Now()
		if now.Sub(published) >= scrubPublishInterval {
			published = now
			publishScrubSummary(request, host, running)
		} else {
			_ = writeScrubSummary(request, running)
		}
		samples.push(now, int64(reading.scrubbedMB)*bytesPerMebibyte)
		rate := samples.rate()
		remaining := scrubRemaining(reading, reached, rate)
		scribe.Log(scribe.SourceBackup, subject, scribe.ActionCompute).Infof("scrubbed", now,
			"%s", backupProgressed(intReading(int64(reading.scrubbedMB)), scrubTotal(reading, reached),
				scrubPercent(reached), remaining, backupEta(now, remaining), rate, backupBounded(now, remaining, hard)))
		if !reading.running {
			break
		}
	}

finished:
	ctx = context.WithoutCancel(ctx)
	scrubbing := scrubUUID(statusOut)
	final, ok := scrubReadNow(ctx)
	held := ok && scrubbing != "" && final.uuid == scrubbing
	if halt == "" {
		halt = scrubHalt(stagePath, cancelled)
	}
	if held {
		lastReading = final
	} else if halt == metric.BackupStateStopped || halt == metric.BackupStateTimeout {
		scribe.Log(scribe.SourceBackup, subject, scribe.ActionCompute).Infof("excluded", started,
			"[%s] released by the [%s] stage, keeping the last reading, skipping device stats", config.DirBackup, halt)
	} else {
		scribe.Log(scribe.SourceBackup, subject, scribe.ActionCompute).Warnf("faulting", started,
			"[%s] lost filesystem [%s] mid scrub, keeping the last reading, skipping device stats",
			config.DirBackup, scrubbing)
	}
	if lastReading.progress == 0 {
		lastReading.progress = reached
	}
	lastReading.found = max(lastReading.found-baseline.found, 0)
	lastReading.corrected = max(lastReading.corrected-baseline.corrected, 0)
	lastReading.uncorrectable = max(lastReading.uncorrectable-baseline.uncorrectable, 0)

	deviceErrors, counted := 0, false
	if held {
		deviceErrors, counted = deviceStatsSum(ctx)
	}
	state, success := metric.BackupStateSuccess, true
	if halt != "" {
		state, success = halt, false
	}
	if !counted && (halt == "" || paused) {
		state, success = metric.BackupStateFailure, false
		scribe.Log(scribe.SourceBackup, subject, scribe.ActionCompute).Errorf("faulting", started,
			"[%s] device stats could not be read, so this scrub cannot report the disk clean", config.DirBackup)
	}
	if paused && lastReading.scrubbedMB <= baseline.scrubbedMB {
		state, success = metric.BackupStateFailure, false
		scribe.Log(scribe.SourceBackup, subject, scribe.ActionCompute).Errorf("faulting", started,
			"[%s] scrub made no progress past [%s] GiB, so resuming would never finish", config.DirBackup,
			backupSizedGibibytes(intReading(int64(baseline.scrubbedMB))))
	}
	var files []scrubCorruptFile
	if lastReading.found > 0 || lastReading.uncorrectable > 0 || deviceErrors > 0 {
		state, success = metric.BackupStateFailure, false
		logged := kernelSince(ctx, cursor)
		subvolumes := map[int64]string{}
		if listed, code, abandoned := bounded(ctx, stageBoundedWait, "btrfs", "subvolume", "list", config.DirBackup); !abandoned && code == 0 {
			for _, match := range scrubSubvolumePattern.FindAllStringSubmatch(listed, -1) {
				if id, err := strconv.ParseInt(match[1], 10, 64); err == nil {
					subvolumes[id] = strings.TrimSpace(match[2])
				}
			}
		}
		files = scrubCorruptFiles(kernelCorrupted(logged), subvolumes)
		mounted := held && verified(ctx, config.DirBackup)
		for index := range files {
			file := &files[index]
			switch {
			case file.source == "":
				file.outcome = scrubOutcomeUnmapped
			case !file.live:
				file.outcome = scrubOutcomeSnapshot
			case !mounted:
				file.outcome = scrubOutcomeKept
			default:
				file.outcome = scrubOutcomeDeleted
				if _, code, abandoned := bounded(ctx, stageBoundedWait, "rm", "-f", "--", file.mirror); abandoned || code != 0 {
					file.outcome = scrubOutcomeKept
				}
			}
		}
		listing := make([]string, 0, len(files))
		for _, file := range files {
			listing = append(listing, fmt.Sprintf("%-8s %4d %s", file.outcome, file.snapshots, file.mirror))
		}
		scrubLog(ctx, stagePath, listing, kernelFaulted(logged))
	}
	if deviceErrors > 0 || lastReading.found > 0 {
		_, _, _ = bounded(ctx, stageBoundedWait, "btrfs", "device", "stats", "-z", config.DirBackup)
	}
	relocated := 0
	if held && state == metric.BackupStateSuccess && time.Now().Before(hard) {
		relocated = runBalance(ctx, subject)
	}
	document := scrubDocument(request, state, success, started, lastReading)
	document.ResumedBool = resumed
	document.DeviceErrors = deviceErrors
	document.ChunksRelocated = relocated
	document.FilesToDeleteCount = len(files)
	named := make([]string, 0, min(len(files), kernelCorruptNamed))
	for _, file := range files[:min(len(files), kernelCorruptNamed)] {
		named = append(named, file.mirror)
	}
	document.FilesToDelete = strings.Join(named, ",")
	publishScrubSummary(request, host, document)
	for _, line := range scrubReport(state, resumed, lastReading, deviceErrors, counted, relocated, files) {
		logger := scribe.Log(scribe.SourceBackup, subject, scribe.ActionStop)
		if line.fault {
			logger.Errorf(line.verb, started, "%s", line.detail)
		} else {
			logger.Infof(line.verb, started, "%s", line.detail)
		}
	}
	return success || state == metric.BackupStatePausing
}

func scrubAction(forced bool, trigger, status string, now time.Time) (action, reason string) {
	lower := strings.ToLower(status)
	if strings.Contains(lower, "interrupted") || strings.Contains(lower, "aborted") {
		return scrubActionResume, ""
	}
	if !forced && trigger != metric.BackupTriggerSystem {
		return "", fmt.Sprintf("a [%s] run does not scrub, pass [--scrub] to force one", trigger)
	}
	if !forced && (int(now.Month())-int(scrubWindowFrom))%scrubWindowMonths != 0 {
		return "", fmt.Sprintf("a scrub falls every [%d] months from [%s], and [%s] is not one, pass [--scrub] to force one",
			scrubWindowMonths, scrubWindowFrom, now.Month())
	}
	if since := scrubStartedField(status); !forced && since != "" && sameScrubMonth(since, now) {
		return "", fmt.Sprintf("the last pass started [%s] in this month already, pass [--scrub] to force one", since)
	}
	return scrubActionStart, ""
}

func scrubOrigin(action, status string) string {
	if action != scrubActionResume {
		return "of a fresh pass"
	}
	if since := scrubStartedField(status); since != "" {
		return fmt.Sprintf("of the pass from [%s]", since)
	}
	return "of an unfinished pass"
}

func scrubCorruptFiles(corruptions []kernelCorruption, subvolumes map[int64]string) []scrubCorruptFile {
	byMirror := map[string]*scrubCorruptFile{}
	for _, corruption := range corruptions {
		subvolume, snapshot := subvolumes[corruption.root], false
		if rest, ok := strings.CutPrefix(subvolume, tertiarySnapshotDirectory+"/"); ok {
			subvolume, snapshot = filepath.Dir(rest), true
		}
		relative := filepath.Join(subvolume, corruption.path)
		mirror := filepath.Join(config.DirBackup, relative)
		file, ok := byMirror[mirror]
		if !ok {
			file = &scrubCorruptFile{mirror: mirror}
			if rest, under := strings.CutPrefix(relative, tertiaryShareDirectory+"/"); under && !strings.HasPrefix(rest, "..") {
				file.source = filepath.Join(config.DirShare, rest)
			}
			byMirror[mirror] = file
		}
		if snapshot {
			file.snapshots++
		} else {
			file.live = true
		}
	}
	files := make([]scrubCorruptFile, 0, len(byMirror))
	for _, file := range byMirror {
		files = append(files, *file)
	}
	slices.SortFunc(files, func(left, right scrubCorruptFile) int { return strings.Compare(left.mirror, right.mirror) })
	return files
}

func scrubReport(state string, resumed bool, reading scrubReading, deviceErrors int, counted bool, relocated int, files []scrubCorruptFile) []scrubReportLine {
	pass := "fresh"
	if resumed {
		pass = "resumed"
	}
	lines := []scrubReportLine{{verb: "scrubbed", detail: fmt.Sprintf(
		"[%s] scrub finished as [%s] at [%s] percent of [%s] GiB, a [%s] pass with [%d] chunks relocated",
		config.DirBackup, state, backupPercent(floatReading(reading.progress)),
		backupSizedGibibytes(intReading(int64(reading.scrubbedMB))), pass, relocated)}}
	device := "-"
	if counted {
		device = strconv.Itoa(deviceErrors)
	}
	faulted := reading.found > 0 || reading.uncorrectable > 0 || deviceErrors > 0
	verdict := ", the disk is clean"
	switch {
	case faulted:
		verdict = fmt.Sprintf(", [%d] files corrupt, see [%s]", len(files), scrubLogLeaf)
	case !counted:
		verdict = ", its device stats unread"
	}
	lines = append(lines, scrubReportLine{fault: faulted, verb: "scrubbed", detail: fmt.Sprintf(
		"[%s] scrub found [%d] errors, [%d] corrected, [%d] uncorrectable, [%s] on the device%s",
		config.DirBackup, reading.found, reading.corrected, reading.uncorrectable, device, verdict)})
	if !faulted {
		return lines
	}
	tally := map[string]int{}
	for index, file := range files {
		tally[file.outcome]++
		if index >= kernelCorruptNamed {
			continue
		}
		var prefix string
		switch file.outcome {
		case scrubOutcomeDeleted:
			prefix = fmt.Sprintf("[%-8s] corrupt in the mirror and [%3d] snapshots, the next run sends it again", file.outcome, file.snapshots)
		case scrubOutcomeKept:
			prefix = fmt.Sprintf("[%-8s] corrupt in the mirror and [%3d] snapshots, delete it then run [abackup start]", file.outcome, file.snapshots)
		case scrubOutcomeSnapshot:
			prefix = fmt.Sprintf("[%-8s] corrupt in [%3d] snapshots alone, never restore it from them", file.outcome, file.snapshots)
		default:
			prefix = fmt.Sprintf("[%-8s] corrupt outside the share mirror, nothing will send it again", file.outcome)
		}
		budget := scribe.Detailed() - len(prefix) - len(" []")
		lines = append(lines, scrubReportLine{fault: true, verb: "faulting", detail: prefix + " [" + scribe.Tail(file.mirror, budget) + "]"})
	}
	if len(files) > kernelCorruptNamed {
		lines = append(lines, scrubReportLine{fault: true, verb: "faulting", detail: fmt.Sprintf(
			"[%d] more corrupt files are named in [%s] beside this run's stage log", len(files)-kernelCorruptNamed, scrubLogLeaf)})
	}
	if count := tally[scrubOutcomeDeleted]; count > 0 {
		lines = append(lines, scrubReportLine{fault: true, verb: "faulting", detail: fmt.Sprintf(
			"[%d] corrupt files deleted from [%s], run [abackup start] now to mirror them again, or the next scheduled run will",
			count, config.DirBackup)})
	}
	if count := tally[scrubOutcomeKept]; count > 0 {
		lines = append(lines, scrubReportLine{fault: true, verb: "faulting", detail: fmt.Sprintf(
			"[%d] corrupt files could not be deleted from [%s], delete each by hand then run [abackup start]",
			count, config.DirBackup)})
	}
	if len(files) == 0 {
		lines = append(lines, scrubReportLine{fault: true, verb: "faulting", detail: fmt.Sprintf(
			"[%s] errors name no file so the disk read badly, check its cable and SMART then run [abackup start --scrub]",
			config.DirBackup)})
	}
	return lines
}

func scrubStateCleared(ctx context.Context) int {
	if commandAvailable("btrfs") && mountpointCheck(ctx, config.DirBackup) {
		cancelScrub(ctx)
	}
	states, _ := filepath.Glob(filepath.Join(scrubStateDirectory, scrubStateLeaves))
	cleared := 0
	for _, state := range states {
		if data, err := os.ReadFile(state); err == nil && strings.Contains(string(data), "finished:1") && !strings.Contains(string(data), "finished:0") {
			continue
		}
		if os.Remove(state) == nil {
			cleared++
		}
	}
	return cleared
}

func scrubHalt(stagePath string, cancelled bool) string {
	if _, err := os.Stat(filepath.Join(stagePath, stageTimedOutMarker)); err == nil {
		return metric.BackupStateTimeout
	}
	if _, err := os.Stat(filepath.Join(stagePath, stageStoppedMarker)); err == nil {
		return metric.BackupStateStopped
	}
	if cancelled {
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
	if math.Round(reached) >= 100 {
		return intReading(int64(reading.scrubbedMB))
	}
	return intReading(int64(float64(reading.scrubbedMB) * 100 / reached))
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
		uuid:          scrubUUID(statusOut),
		scrubbedMB:    int(scrubCounter(rawOut, "data_bytes_scrubbed") / bytesPerMebibyte),
		corrected:     int(scrubCounter(rawOut, "corrected_errors")),
		uncorrectable: int(scrubCounter(rawOut, "uncorrectable_errors")),
		found:         int(scrubCounter(rawOut, "csum_errors") + scrubCounter(rawOut, "verify_errors") + scrubCounter(rawOut, "super_errors")),
	}
	if total := scrubTotalBytes(statusOut); total > 0 {
		done := float64(scrubCounter(rawOut, "data_bytes_scrubbed") + scrubCounter(rawOut, "tree_bytes_scrubbed"))
		reading.progress = min(done/total*100, 100)
		reading.measured = true
	} else if match := scrubProgressPattern.FindStringSubmatch(statusOut); match != nil {
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

func scrubUUID(status string) string {
	match := scrubUUIDPattern.FindStringSubmatch(status)
	if match == nil {
		return ""
	}
	return match[1]
}

func scrubTotalBytes(status string) float64 {
	match := scrubTotalPattern.FindStringSubmatch(status)
	if match == nil {
		return 0
	}
	value, err := strconv.ParseFloat(match[1], 64)
	if err != nil {
		return 0
	}
	return value * scrubUnitBytes[match[2]]
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
	for _, pattern := range scrubDeviceStatsPatterns {
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
	if match := scrubBalanceRelocatedPattern.FindStringSubmatch(out); match != nil {
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

func writeScrubSummary(request stageRequest, document scrubSummary) error {
	path := scrubStatusPath(request.RunPath)
	_ = os.MkdirAll(filepath.Dir(path), 0o755)
	return writeAtomic(path, document)
}

func publishScrubSummary(request stageRequest, host string, document scrubSummary) {
	if err := writeScrubSummary(request, document); err != nil {
		return
	}
	if client, err := brokerDial(request.ConfigPath, "scrub"); err == nil {
		defer client.close()
		if payload, marshalErr := json.Marshal(document); marshalErr == nil {
			_ = client.publishRetained(metric.TopicBackupScrub(host), string(payload))
		}
	}
}

type scrubCorruptFile struct {
	mirror, source, outcome string
	snapshots               int
	live                    bool
}

type scrubReportLine struct {
	fault        bool
	verb, detail string
}

type scrubReading struct {
	uuid                                        string
	scrubbedMB, found, corrected, uncorrectable int
	progress                                    float64
	measured, running                           bool
}

var (
	scrubStateDirectory = "/var/lib/btrfs"

	scrubProgressPattern = regexp.MustCompile(`\(([0-9.]+)%\)`)

	scrubUUIDPattern = regexp.MustCompile(`(?m)^UUID:\s*(\S+)\s*$`)

	scrubTotalPattern = regexp.MustCompile(`(?m)^Total to scrub:\s*([0-9.]+)\s*(B|KiB|MiB|GiB|TiB|PiB)\s*$`)

	scrubUnitBytes = map[string]float64{"B": 1, "KiB": 1 << 10, "MiB": 1 << 20, "GiB": 1 << 30, "TiB": 1 << 40, "PiB": 1 << 50}

	scrubStartedPattern = regexp.MustCompile(`(?m)^Scrub (?:started|resumed):\s*(.+)$`)

	scrubBalanceRelocatedPattern = regexp.MustCompile(`relocate (\d+) out of`)

	scrubSubvolumePattern = regexp.MustCompile(`(?m)^ID (\d+) gen \d+ top level \d+ path (.+)$`)

	scrubCounterPatterns = func() map[string]*regexp.Regexp {
		patterns := map[string]*regexp.Regexp{}
		for _, key := range []string{"data_bytes_scrubbed", "tree_bytes_scrubbed", "corrected_errors", "uncorrectable_errors", "csum_errors", "verify_errors", "super_errors"} {
			patterns[key] = regexp.MustCompile(`(?m)^\s*` + regexp.QuoteMeta(key) + `:\s*(\d+)`)
		}
		return patterns
	}()

	scrubDeviceStatsPatterns = func() []*regexp.Regexp {
		var patterns []*regexp.Regexp
		for _, key := range []string{"write_io_errs", "read_io_errs", "flush_io_errs", "corruption_errs", "generation_errs"} {
			patterns = append(patterns, regexp.MustCompile(`\]\.`+regexp.QuoteMeta(key)+`\s+(\d+)`))
		}
		return patterns
	}()
)

const (
	scrubWindowMonths = 3
	scrubWindowFrom   = time.January

	scrubPublishInterval = 30 * time.Second
	scrubSilenceGrace    = 90 * time.Second
	scrubMargin          = 15 * time.Minute
	scrubBalanceWait     = time.Hour

	scrubLogLeaf = "scrub.log"

	scrubActionStart  = "start"
	scrubActionResume = "resume"

	scrubStateLeaves = "scrub.status.*"

	scrubOutcomeDeleted  = "deleted"
	scrubOutcomeKept     = "kept"
	scrubOutcomeSnapshot = "snapshot"
	scrubOutcomeUnmapped = "unmapped"
)
