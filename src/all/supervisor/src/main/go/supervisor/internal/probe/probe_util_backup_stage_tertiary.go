package probe

import (
	"bytes"
	"context"
	"fmt"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"sync"
	"sync/atomic"
	"time"

	"supervisor/internal/config"
	"supervisor/internal/metric"
	"supervisor/internal/scribe"
)

func runTertiaryStage(ctx context.Context, request stageRequest, counters *stageCounters) (result stageResult, runErr error) {
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
	defer func() {
		if percent, usedMB, totalMB, ok := measureUsage(context.WithoutCancel(ctx), config.DirBackup); ok {
			result.diskUsagePerc, result.diskUsedMB, result.diskTotalMB = percent, usedMB, totalMB
		}
	}()
	if err := attachBackupDisk(ctx); err != nil {
		return result, err
	}
	result.diskUnclean = kernelReplayed(kernelSince(ctx, cursor))
	if result.diskUnclean {
		scribe.Log(scribe.SourceBackup, scribe.SubjectStage(metric.BackupStageTertiary), scribe.ActionStart).Warnf("faulting", time.Now(),
			"[%s] replayed its log at mount, so the previous unmount was unclean", config.DirBackup)
	}
	if !ready(ctx) {
		return result, fmt.Errorf("[%s] %s, refusing to mirror", config.DirBackup, diagnosed(ctx, config.DirBackup))
	}
	if deviceID(config.DirBackup) == deviceID(homeRoot) {
		return result, fmt.Errorf("[%s] shares a filesystem with [%s], refusing to mirror onto the host", config.DirBackup, homeRoot)
	}

	for _, share := range backupShares() {
		_ = mountTarget(ctx, share)
	}
	_ = os.WriteFile(filepath.Join(stagePath, tertiaryDeviceMarker), fmt.Appendf(nil, "%d", deviceID(config.DirBackup)), 0o644)
	shares := mountedLocalShares(ctx)
	expected := mirrorExpectation(ctx, shares)
	counters.addTotal(int(expected / bytesPerMebibyte))
	progress := &rsyncProgress{}
	stopProgress := reportMirrorProgress(ctx, progress, expected, request.Expires)
	defer stopProgress()

	failed := false
	for _, share := range shares {
		if err := ctx.Err(); err != nil {
			return result, err
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
		stats, rsyncErr := runRsync(ctx, progress,
			mirrorArguments(share, target, "--info=progress2", "--partial-dir="+rsyncTemp)...)
		progress.completed(int64(stats.totalTransferredBytes))
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

func mirrorArguments(share, target string, extra ...string) []string {
	arguments := []string{"-a", "--delete", "--stats",
		"--exclude", "/tmp/", "--exclude", ".rsync/", "--exclude", ".rsync-*", "--exclude", "/.lock"}
	arguments = append(arguments, extra...)
	return append(arguments, "--", share+"/", target+"/")
}

func mirrorExpectation(ctx context.Context, shares []string) int64 {
	started := time.Now()
	subject := scribe.SubjectStage(metric.BackupStageTertiary)
	total, files := int64(0), 0
	for _, share := range shares {
		shareStarted := time.Now()
		target := filepath.Join(config.DirBackup, tertiaryShareDirectory, strings.TrimPrefix(share, config.DirShare+"/"))
		stats, err := runRsync(ctx, nil, mirrorArguments(share, target, "--dry-run")...)
		if err != nil {
			scribe.Log(scribe.SourceBackup, subject, scribe.ActionCompute).Warnf("faulting", shareStarted,
				"[%s] could not be measured before mirroring, so this stage reports no total [%v]", share, err)
			return 0
		}
		total += int64(stats.totalTransferredBytes)
		files += stats.filesTransferred
		scribe.Log(scribe.SourceBackup, subject, scribe.ActionCompute).Infof("measured", shareStarted,
			"[%s] will send [%s] GiB over [%d] files", share, backupSized(intReading(int64(stats.totalTransferredBytes)/bytesPerGibibyte)), stats.filesTransferred)
	}
	if len(shares) > 1 {
		scribe.Log(scribe.SourceBackup, subject, scribe.ActionCompute).Infof("measured", started,
			"[%s] GiB over [%d] files across [%d] shares is what this mirror will send", backupSized(intReading(total/bytesPerGibibyte)), files, len(shares))
	}
	return total
}

func reportMirrorProgress(ctx context.Context, progress *rsyncProgress, expected int64, deadline time.Time) func() {
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
				moved := progress.bytes()
				samples.push(now, moved)
				rate := samples.rate()
				remaining := mirrorRemaining(moved, expected, rate)
				scribe.Log(scribe.SourceBackup, scribe.SubjectStage(metric.BackupStageTertiary), scribe.ActionCompute).Infof("mirrored", now,
					"%s", backupProgressed(intReading(moved/bytesPerGibibyte), mirrorTotal(moved, expected),
						mirrorPercent(moved, expected), remaining, backupEta(now, remaining), rate, backupBounded(now, remaining, deadline)))
			}
		}
	}()
	return func() {
		stop()
		<-done
	}
}

func mirrorTotal(moved, expected int64) reading {
	if expected <= 0 || moved > expected {
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

type rsyncProgress struct {
	mu      sync.Mutex
	tail    []byte
	sending atomic.Int64
	sent    atomic.Int64
}

func (p *rsyncProgress) Write(data []byte) (int, error) {
	p.mu.Lock()
	p.tail = append(p.tail, data...)
	for {
		cut := bytes.IndexAny(p.tail, "\r\n")
		if cut < 0 {
			break
		}
		line := string(p.tail[:cut])
		p.tail = p.tail[cut+1:]
		if sent, ok := rsyncSent(line); ok {
			p.sending.Store(sent)
		}
	}
	if len(p.tail) > rsyncProgressTail {
		p.tail = nil
	}
	p.mu.Unlock()
	return len(data), nil
}

func (p *rsyncProgress) completed(sent int64) {
	p.sent.Add(max(sent, p.sending.Load()))
	p.sending.Store(0)
}

func (p *rsyncProgress) bytes() int64 {
	return p.sent.Load() + p.sending.Load()
}

func rsyncSent(line string) (int64, bool) {
	if !strings.Contains(line, "%") {
		return 0, false
	}
	fields := strings.Fields(line)
	if len(fields) == 0 {
		return 0, false
	}
	digits := onlyDigits(fields[0])
	if digits == "0" {
		return 0, false
	}
	sent, _ := strconv.ParseInt(digits, 10, 64)
	return sent, true
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

	rsyncProgressTail = 4096
)
