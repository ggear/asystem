package probe

import (
	"context"
	"fmt"
	"os"
	"path/filepath"
	"slices"
	"strings"
	"time"

	"supervisor/internal/config"
	"supervisor/internal/metric"
	"supervisor/internal/scribe"
)

func runTertiaryStage(ctx context.Context, request stageRequest, counters *stageCounters) (stageResult, error) {
	loaded := config.Load(request.ConfigPath)
	homeRoot := backupHomeRoot()
	stagePath := stageDir(request.RunPath, metric.BackupStageTertiary)

	if len(backupTargets()) == 0 {
		scribe.Log(scribe.SourceBackup, scribe.SubjectStage(metric.BackupStageTertiary), scribe.ActionStart).Infof("excluded", time.Now(),
			"[%s] is declared by no entry in [%s], so this host mirrors nothing and the stage is skipped", config.DirBackup, backupFstabPath)
		return stageResult{skipped: true}, nil
	}
	if err := powerBackupDisk(request.ConfigPath, metric.CommandOn); err != nil {
		scribe.Log(scribe.SourceBackup, scribe.SubjectStage(metric.BackupStageTertiary), scribe.ActionPublish).Warnf("faulting", time.Now(),
			"[%v] powering the backup disk on, carrying on in case it is already powered", err)
	}
	defer tertiaryCleanup(ctx, request)

	cursor := kernelCursor(ctx)
	if err := attachBackupDisk(ctx); err != nil {
		return stageResult{}, err
	}
	unclean := kernelReplayed(kernelSince(ctx, cursor))
	if unclean {
		scribe.Log(scribe.SourceBackup, scribe.SubjectStage(metric.BackupStageTertiary), scribe.ActionStart).Warnf("faulting", time.Now(),
			"[%s] replayed its log at mount, so the previous unmount was unclean", config.DirBackup)
	}
	if !ready(ctx) {
		return stageResult{}, fmt.Errorf("[/backup] %s, refusing to mirror", diagnosed(ctx, config.DirBackup))
	}
	if deviceID(config.DirBackup) == deviceID(homeRoot) {
		return stageResult{}, fmt.Errorf("[/backup] shares a filesystem with [%s], refusing to mirror onto the host", homeRoot)
	}

	for _, share := range backupShares() {
		_ = mountTarget(ctx, share)
	}
	_ = os.WriteFile(filepath.Join(stagePath, tertiaryDeviceMarker), fmt.Appendf(nil, "%d", deviceID(config.DirBackup)), 0o644)
	expected := expectedMirrorBytes(ctx, filepath.Dir(request.RunPath), request.RunID)
	counters.addTotal(int(expected / bytesPerMebibyte))
	stopProgress := reportMirrorProgress(ctx, usedBytes(ctx, config.DirBackup), expected, request.Expires)
	defer stopProgress()

	failed := false
	for _, share := range mountedLocalShares(ctx) {
		if err := ctx.Err(); err != nil {
			return stageResult{}, err
		}
		index := strings.TrimPrefix(share, config.DirShare+"/")
		target := filepath.Join(config.DirBackup, tertiaryShareDirectory, index)
		if !mountpointCheck(ctx, share) {
			scribe.Log(scribe.SourceBackup, scribe.SubjectStage(metric.BackupStageTertiary), scribe.ActionStart).Warnf("faulting", time.Now(), "[%s] vanished mid-run, skipping", share)
			failed = true
			continue
		}
		if held, reason := attached(ctx, stagePath); !held {
			scribe.Log(scribe.SourceBackup, scribe.SubjectStage(metric.BackupStageTertiary), scribe.ActionStop).Errorf("faulting", time.Now(),
				"[%s] %s, aborting before writing anywhere else", config.DirBackup, reason)
			failed = true
			break
		}
		rsyncTemp := filepath.Join(target, ".rsync")
		_ = os.MkdirAll(rsyncTemp, 0o755)
		pruneStale(rsyncTemp, tertiaryPartialKeep)

		mirrorStarted := time.Now()
		scribe.Log(scribe.SourceBackup, scribe.SubjectStage(metric.BackupStageTertiary), scribe.ActionStart).Infof("mirrored", mirrorStarted, "[%s] mirroring to [%s]", share, target)
		stats, rsyncErr := runRsync(ctx, "-a", "--delete", "--stats",
			"--exclude", "/tmp/", "--exclude", ".rsync/", "--exclude", ".rsync-*", "--exclude", "/.lock",
			"--partial-dir="+rsyncTemp, "--", share+"/", target+"/")
		if rsyncErr != nil {
			failed = true
		}
		counters.addTransfer(stats.filesTransferred, stats.totalTransferredBytes/bytesPerMebibyte, stats.filesCreated,
			stats.filesDeleted, stats.filesListed, stats.totalFileSizeBytes/bytesPerMebibyte, stats.totalBytesSent/bytesPerMebibyte)
		scribe.Log(scribe.SourceBackup, scribe.SubjectStage(metric.BackupStageTertiary), scribe.ActionStop).Infof("mirrored", mirrorStarted,
			"[%s] mirrored in [%s], running total [%d] MiB", share, time.Since(mirrorStarted).Round(time.Second), counters.snapshotSizeMB())
	}

	stopProgress()

	scrubOK := true
	if verified(ctx, config.DirBackup) {
		snapshotShares(ctx, request, loaded)
		scrubOK = runScrub(ctx, request)
	} else {
		scribe.Log(scribe.SourceBackup, scribe.SubjectStage(metric.BackupStageTertiary), scribe.ActionStop).Errorf("faulting", time.Now(),
			"[%s] %s, so it was neither snapshotted nor scrubbed", config.DirBackup, diagnosed(ctx, config.DirBackup))
		failed = true
	}

	percent, usedMB, totalMB, ok := measureUsage(ctx, config.DirBackup)
	result := stageResult{diskUnclean: unclean}
	if ok {
		result.diskUsagePerc, result.diskUsedMB, result.diskTotalMB = percent, usedMB, totalMB
	}

	switch {
	case failed && !scrubOK:
		return result, errStageMirrorAndScrub
	case failed:
		return result, errStageMirror
	case !scrubOK:
		return result, errStageScrub
	}
	return result, nil
}

func reportMirrorProgress(ctx context.Context, opened, expected int64, deadline time.Time) func() {
	progressCtx, stop := context.WithCancel(ctx)
	done := make(chan struct{})
	go func() {
		defer close(done)
		samples := newSampleRing(ringPoints, ringQuantum)
		ticker := time.NewTicker(backupProgressHeartbeat)
		defer ticker.Stop()
		for {
			select {
			case <-progressCtx.Done():
				return
			case now := <-ticker.C:
				moved := max(usedBytes(progressCtx, config.DirBackup)-opened, 0)
				samples.push(now, moved)
				rate := samples.rate()
				remaining := mirrorRemaining(moved, expected, rate)
				scribe.Log(scribe.SourceBackup, scribe.SubjectStage(metric.BackupStageTertiary), scribe.ActionCompute).Infof("mirrored", now,
					"%s", backupProgressed(intReading(moved/bytesPerGibibyte), mirrorTotal(expected),
						mirrorPercent(moved, expected), remaining, backupEta(now, remaining), rate, backupBounded(now, remaining, deadline)))
			}
		}
	}()
	return func() {
		stop()
		<-done
	}
}

func mirrorTotal(expected int64) reading {
	if expected <= 0 {
		return unknownReading()
	}
	return intReading(expected / bytesPerGibibyte)
}

func mirrorPercent(moved, expected int64) reading {
	if expected <= 0 || moved > expected {
		return unknownReading()
	}
	return floatReading(float64(moved) * 100 / float64(expected))
}

func mirrorRemaining(moved, expected int64, rate reading) reading {
	if expected <= 0 || moved > expected || !rate.Known() || rate.Value() <= 0 {
		return unknownReading()
	}
	return floatReading(float64(expected-moved) / bytesPerMebibyte / rate.Value() / 60)
}

func stopTertiaryStage(ctx context.Context, request stageRequest) error {
	tertiaryCleanup(ctx, request)
	return nil
}

func tertiaryCleanup(parent context.Context, request stageRequest) {
	ctx, cancel := context.WithTimeout(context.WithoutCancel(parent), tertiaryCleanupWait)
	defer cancel()
	stagePath := stageDir(request.RunPath, metric.BackupStageTertiary)
	homeRoot := backupHomeRoot()
	_ = os.Remove(filepath.Join(stagePath, tertiaryDeviceMarker))
	cancelScrub(ctx)
	if detachable(ctx, config.DirBackup, homeRoot) {
		_, _, _ = bounded(ctx, stageBoundedWait, "btrfs", "balance", "cancel", config.DirBackup)
	}
	pattern := `rsync .*` + config.DirBackup + `/` + tertiaryShareDirectory
	_, _, _ = bounded(ctx, stageBoundedWait, "pkill", "-CONT", "-f", pattern)
	_, _, _ = bounded(ctx, stageBoundedWait, "pkill", "-TERM", "-f", pattern)
	reapProcesses(ctx, pattern)
	_, _, _ = bounded(ctx, stageBoundedWait, "sync", "-f", config.DirBackup)
	detachAll(ctx, homeRoot)
}

func attachBackupDisk(ctx context.Context) error {
	deadline := time.Now().Add(tertiaryDiskWait)
	for {
		pending := false
		for _, target := range backupTargets() {
			if _, ok := declaredDevice(target); !ok {
				pending = true
			}
		}
		if !pending {
			break
		}
		if time.Now().After(deadline) {
			return fmt.Errorf("timed out after [%s] waiting for the backup disk to enumerate", tertiaryDiskWait)
		}
		select {
		case <-ctx.Done():
			return ctx.Err()
		case <-time.After(tertiaryDiskPoll):
		}
	}
	var failed error
	for _, target := range backupTargets() {
		if err := mountTarget(ctx, target); err != nil {
			failed = err
		}
	}
	return failed
}

func ready(ctx context.Context) bool {
	if !verified(ctx, config.DirBackup) || !alive(ctx, config.DirBackup) {
		return false
	}
	out, code, abandoned := bounded(ctx, stageBoundedWait, "findmnt", "-M", config.DirBackup, "-n", "-o", "FSTYPE")
	if abandoned || code != 0 {
		return false
	}
	lines := strings.Split(strings.TrimSpace(out), "\n")
	return len(lines) > 0 && isLocalFilesystem(strings.TrimSpace(lines[len(lines)-1]))
}

func attached(ctx context.Context, stagePath string) (bool, string) {
	data, err := os.ReadFile(filepath.Join(stagePath, tertiaryDeviceMarker))
	if err != nil {
		return true, ""
	}
	expected := strings.TrimSpace(string(data))
	if expected == "" {
		return true, ""
	}
	held, reason := inspected(ctx, config.DirBackup)
	if !held {
		return false, reason
	}
	if fmt.Sprintf("%d", deviceID(config.DirBackup)) != expected {
		return false, "carries a filesystem other than the one this stage claimed"
	}
	return true, reason
}

func pruneStale(dir string, age time.Duration) {
	entries, err := os.ReadDir(dir)
	if err != nil {
		return
	}
	cutoff := time.Now().Add(-age)
	for _, entry := range entries {
		info, err := entry.Info()
		if err != nil || info.ModTime().After(cutoff) {
			continue
		}
		_ = os.RemoveAll(filepath.Join(dir, entry.Name()))
	}
}

func expectedMirrorBytes(ctx context.Context, root, runID string) int64 {
	var sources int64
	for _, share := range mountedLocalShares(ctx) {
		sources += usedBytes(ctx, share)
	}
	if verified(ctx, config.DirBackup) {
		remaining := sources - usedBytes(ctx, config.DirBackup)
		if remaining > sources/100 {
			return remaining
		}
	}
	return previousTertiaryBytes(root, runID)
}

func previousTertiaryBytes(root, runID string) int64 {
	runs := backupRuns(root)
	for _, run := range slices.Backward(runs) {
		if run >= runID {
			continue
		}
		document := readBackupSummary(stageStatusPath(backupRunPath(root, run), metric.BackupStageTertiary))
		if document != nil && document.SizeMB > 0 {
			return int64(document.SizeMB) * bytesPerMebibyte
		}
	}
	return 0
}

func snapshotShares(ctx context.Context, request stageRequest, loaded *config.Config) {
	if !commandAvailable("btrfs") {
		return
	}
	entries, err := os.ReadDir(filepath.Join(config.DirBackup, tertiaryShareDirectory))
	if err != nil {
		return
	}
	for _, entry := range entries {
		if !entry.IsDir() {
			continue
		}
		subvolume := filepath.Join(config.DirBackup, tertiaryShareDirectory, entry.Name())
		_, code, abandoned := bounded(ctx, stageBoundedWait, "btrfs", "subvolume", "show", subvolume)
		if abandoned {
			continue
		}
		if code != 0 {
			scribe.Log(scribe.SourceBackup, scribe.SubjectStage(metric.BackupStageTertiary), scribe.ActionCompute).Warnf("faulting", time.Now(),
				"[%s] is not a btrfs subvolume, so it cannot be snapshotted and keeps no history", subvolume)
			continue
		}
		snapshots := filepath.Join(config.DirBackup, tertiarySnapshotDirectory, tertiaryShareDirectory, entry.Name())
		_ = os.MkdirAll(snapshots, 0o755)
		target := filepath.Join(snapshots, request.RunID)
		_, snapCode, snapAbandoned := bounded(ctx, stageBoundedWait, "btrfs", "subvolume", "snapshot", "-r", subvolume, target)
		if snapAbandoned || snapCode != 0 {
			scribe.Log(scribe.SourceBackup, scribe.SubjectStage(metric.BackupStageTertiary), scribe.ActionCompute).Errorf("faulting", time.Now(),
				"[%s] snapshot failed, keeping its history unpruned", subvolume)
			continue
		}
		scribe.Log(scribe.SourceBackup, scribe.SubjectStage(metric.BackupStageTertiary), scribe.ActionCompute).Infof("snapshot", time.Now(),
			"[%s] snapshotted to [%s]", subvolume, target)
		gfsThin(ctx, snapshots, loaded)
	}
}

func reapProcesses(ctx context.Context, pattern string) {
	deadline := time.Now().Add(tertiaryReapWait)
	for {
		_, code, abandoned := stageExec(ctx, "pgrep", "-f", pattern)
		if abandoned || code != 0 {
			return
		}
		if time.Now().After(deadline) {
			return
		}
		select {
		case <-ctx.Done():
			return
		case <-time.After(time.Second):
		}
	}
}

const (
	tertiaryDiskWait    = 120 * time.Second
	tertiaryDiskPoll    = time.Second
	tertiaryReapWait    = 15 * time.Second
	tertiaryCleanupWait = 5 * time.Minute

	tertiaryPartialKeep       = 7 * 24 * time.Hour
	tertiaryDeviceMarker      = "disk-device"
	tertiaryShareDirectory    = "share"
	tertiarySnapshotDirectory = ".snapshots"
)
