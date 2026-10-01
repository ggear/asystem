package probe

import (
	"bytes"
	"context"
	"fmt"
	"os"
	"path/filepath"
	"slices"
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
		if percent, usedMB, totalMB, ok := measureUsage(context.WithoutCancel(ctx), scribe.SubjectStage(metric.BackupStageTertiary), config.DirBackup); ok {
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
		_ = mountTarget(ctx, scribe.SubjectStage(metric.BackupStageTertiary), share)
	}
	_ = os.WriteFile(filepath.Join(stagePath, tertiaryDeviceMarker), fmt.Appendf(nil, "%d", deviceID(config.DirBackup)), 0o644)
	shares := mountedLocalShares(ctx)
	expected := measureStage(ctx, shares)
	counters.addTotal(int(expected.mirrorBytes / bytesPerMebibyte))
	mirroring := &rsyncProgress{}
	expungedBytes := int64(0)

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

		expunging := &expungeProgress{sizes: expected.expungeSizes[share]}
		expungeStarted := time.Now()
		scribe.Log(scribe.SourceBackup, scribe.SubjectStage(metric.BackupStageTertiary), scribe.ActionStart).Infof("expunged", expungeStarted, "[%s] starting", share)
		stopExpunging := reportStageProgress(ctx, "expunged",
			func() int64 { return expungedBytes + expunging.bytes() }, expected.expungeBytes, request.Expires)
		expungeStats, expungeErr := runRsync(ctx, expunging, expungeArguments(share, target)...)
		stopExpunging()
		expungedBytes += expunging.bytes()
		if expungeErr != nil {
			failed = true
		}
		counters.addTransfer(0, 0, 0, expungeStats.filesDeleted, 0, 0, 0)
		scribe.Log(scribe.SourceBackup, scribe.SubjectStage(metric.BackupStageTertiary), scribe.ActionStop).Infof("expunged", expungeStarted,
			"[%s] stopping with %s", share, backupMoved(intReading(expunging.bytes()/bytesPerMebibyte), time.Since(expungeStarted)))

		rsyncTemp := filepath.Join(target, ".rsync")
		_ = os.MkdirAll(rsyncTemp, 0o755)
		pruneStale(rsyncTemp, tertiaryPartialKeep)

		mirrorStarted := time.Now()
		scribe.Log(scribe.SourceBackup, scribe.SubjectStage(metric.BackupStageTertiary), scribe.ActionStart).Infof("mirrored", mirrorStarted, "[%s] starting", share)
		stopMirroring := reportStageProgress(ctx, "mirrored", mirroring.bytes, expected.mirrorBytes, request.Expires)
		stats, rsyncErr := runRsync(ctx, mirroring,
			mirrorArguments(share, target, "--info=progress2", "--partial-dir="+rsyncTemp)...)
		mirroring.completed(int64(stats.totalTransferredBytes))
		stopMirroring()
		if rsyncErr != nil {
			failed = true
		} else {
			clearDirectory(rsyncTemp)
		}
		counters.addTransfer(stats.filesTransferred, stats.totalTransferredBytes/bytesPerMebibyte, stats.filesCreated,
			stats.filesDeleted, stats.filesListed, stats.totalFileSizeBytes/bytesPerMebibyte, stats.totalBytesSent/bytesPerMebibyte)
		scribe.Log(scribe.SourceBackup, scribe.SubjectStage(metric.BackupStageTertiary), scribe.ActionStop).Infof("mirrored", mirrorStarted,
			"[%s] stopping with %s", share, backupMoved(intReading(int64(stats.totalTransferredBytes)/bytesPerMebibyte), time.Since(mirrorStarted)))
	}

	if err := ctx.Err(); err != nil {
		return result, err
	}
	scrubOK := true
	if verified(ctx, config.DirBackup) {
		snapshotShares(ctx, request, loaded)
		if percent, usedMB, totalMB, ok := measureUsage(ctx, scribe.SubjectStage(metric.BackupStageTertiary), config.DirBackup); ok {
			result.diskUsagePerc, result.diskUsedMB, result.diskTotalMB = percent, usedMB, totalMB
		}
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
	return rsyncArguments([]string{"-a", "--force", "--stats"}, share, target, extra...)
}

func expungeArguments(share, target string, extra ...string) []string {
	return rsyncArguments([]string{"-a", "--delete", "--existing", "--ignore-existing", "--stats", "--info=del"}, share, target, extra...)
}

func measureArguments(share, target string, extra ...string) []string {
	return rsyncArguments([]string{"-a", "--delete", "--stats", "--info=del", "--dry-run"}, share, target, extra...)
}

func rsyncArguments(flags []string, share, target string, extra ...string) []string {
	arguments := append(slices.Clone(flags),
		"--exclude", "/tmp/", "--exclude", ".rsync/", "--exclude", ".rsync-*", "--exclude", "/.lock")
	arguments = append(arguments, extra...)
	return append(arguments, "--", share+"/", target+"/")
}

func measureStage(ctx context.Context, shares []string) stageExpectation {
	started := time.Now()
	subject := scribe.SubjectStage(metric.BackupStageTertiary)
	measured := stageExpectation{expungeSizes: make(map[string]map[string]int64, len(shares))}
	for _, share := range shares {
		shareStarted := time.Now()
		target := filepath.Join(config.DirBackup, tertiaryShareDirectory, strings.TrimPrefix(share, config.DirShare+"/"))
		listed := &expungeListing{}
		stats, err := runRsync(ctx, listed, measureArguments(share, target)...)
		if err != nil {
			scribe.Log(scribe.SourceBackup, subject, scribe.ActionCompute).Warnf("faulting", shareStarted,
				"[%s] could not be measured before mirroring, so this stage reports no total [%v]", share, err)
			return stageExpectation{}
		}
		sizes, expunging := expungeSizes(target, listed.taken())
		measured.expungeSizes[share] = sizes
		measured.expungeBytes += expunging
		measured.expungeFiles += stats.filesDeleted
		measured.mirrorBytes += int64(stats.totalTransferredBytes)
		measured.mirrorFiles += stats.filesTransferred
		scribe.Log(scribe.SourceBackup, subject, scribe.ActionCompute).Infof("measured", shareStarted,
			"[%s] having [%s] GiB over [%s] files to expunge", share,
			backupSizedGibibytes(intReading(expunging/bytesPerMebibyte)), backupCounted(intReading(int64(stats.filesDeleted))))
		scribe.Log(scribe.SourceBackup, subject, scribe.ActionCompute).Infof("measured", shareStarted,
			"[%s] having [%s] GiB over [%s] files to mirror", share,
			backupSizedGibibytes(intReading(int64(stats.totalTransferredBytes)/bytesPerMebibyte)), backupCounted(intReading(int64(stats.filesTransferred))))
	}
	if len(shares) > 1 {
		scribe.Log(scribe.SourceBackup, subject, scribe.ActionCompute).Infof("measured", started,
			"[%s] GiB over [%s] files across [%d] shares is what this stage will expunge",
			backupSizedGibibytes(intReading(measured.expungeBytes/bytesPerMebibyte)), backupCounted(intReading(int64(measured.expungeFiles))), len(shares))
		scribe.Log(scribe.SourceBackup, subject, scribe.ActionCompute).Infof("measured", started,
			"[%s] GiB over [%s] files across [%d] shares is what this stage will mirror",
			backupSizedGibibytes(intReading(measured.mirrorBytes/bytesPerMebibyte)), backupCounted(intReading(int64(measured.mirrorFiles))), len(shares))
	}
	return measured
}

func expungeSizes(target string, paths []string) (map[string]int64, int64) {
	sizes, total := make(map[string]int64, len(paths)), int64(0)
	for _, path := range paths {
		info, err := os.Lstat(filepath.Join(target, path))
		if err != nil || info.IsDir() {
			continue
		}
		sizes[path] = info.Size()
		total += info.Size()
	}
	return sizes, total
}

func reportStageProgress(ctx context.Context, verb string, moved func() int64, expected int64, deadline time.Time) func() {
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
				carried := moved()
				samples.push(now, carried)
				rate := samples.rate()
				remaining := progressRemaining(carried, expected, rate)
				scribe.Log(scribe.SourceBackup, scribe.SubjectStage(metric.BackupStageTertiary), scribe.ActionCompute).Infof(verb, now,
					"%s", backupProgressed(intReading(carried/bytesPerMebibyte), progressTotal(carried, expected),
						progressPercent(carried, expected), remaining, backupEta(now, remaining), rate, backupBounded(now, remaining, deadline)))
			}
		}
	}()
	return func() {
		stop()
		<-done
	}
}

func progressTotal(moved, expected int64) reading {
	if expected <= 0 || moved > expected {
		return unknownReading()
	}
	return intReading(expected / bytesPerMebibyte)
}

func progressPercent(moved, expected int64) reading {
	if expected <= 0 || moved > expected {
		return unknownReading()
	}
	return floatReading(float64(moved) * 100 / float64(expected))
}

func progressRemaining(moved, expected int64, rate reading) reading {
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
	detachAll(ctx, scribe.SubjectStage(metric.BackupStageTertiary), homeRoot)
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
		if err := mountTarget(ctx, scribe.SubjectStage(metric.BackupStageTertiary), target); err != nil {
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
		gfsThin(ctx, scribe.SubjectStage(metric.BackupStageTertiary), snapshots, loaded)
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

type stageExpectation struct {
	mirrorBytes, expungeBytes int64
	mirrorFiles, expungeFiles int
	expungeSizes              map[string]map[string]int64
}

type lineReader struct {
	mu   sync.Mutex
	tail []byte
}

func (r *lineReader) push(data []byte, consume func(line string)) {
	r.mu.Lock()
	defer r.mu.Unlock()
	r.tail = append(r.tail, data...)
	for {
		cut := bytes.IndexAny(r.tail, "\r\n")
		if cut < 0 {
			break
		}
		consume(string(r.tail[:cut]))
		r.tail = r.tail[cut+1:]
	}
	if len(r.tail) > rsyncProgressTail {
		r.tail = nil
	}
}

type expungeListing struct {
	lines lineReader
	paths []string
}

func (l *expungeListing) taken() []string {
	l.lines.mu.Lock()
	defer l.lines.mu.Unlock()
	return l.paths
}

func (l *expungeListing) Write(data []byte) (int, error) {
	l.lines.push(data, func(line string) {
		if path, ok := rsyncDeleted(line); ok {
			l.paths = append(l.paths, path)
		}
	})
	return len(data), nil
}

type expungeProgress struct {
	lines   lineReader
	sizes   map[string]int64
	removed atomic.Int64
}

func (p *expungeProgress) Write(data []byte) (int, error) {
	p.lines.push(data, func(line string) {
		if path, ok := rsyncDeleted(line); ok {
			p.removed.Add(p.sizes[path])
		}
	})
	return len(data), nil
}

func (p *expungeProgress) bytes() int64 {
	return p.removed.Load()
}

type rsyncProgress struct {
	lines   lineReader
	sending atomic.Int64
	sent    atomic.Int64
}

func (p *rsyncProgress) Write(data []byte) (int, error) {
	p.lines.push(data, func(line string) {
		if sent, ok := rsyncSent(line); ok {
			p.sending.Store(sent)
		}
	})
	return len(data), nil
}

func (p *rsyncProgress) completed(sent int64) {
	p.sent.Add(max(sent, p.sending.Load()))
	p.sending.Store(0)
}

func (p *rsyncProgress) bytes() int64 {
	return p.sent.Load() + p.sending.Load()
}

func rsyncDeleted(line string) (string, bool) {
	path, ok := strings.CutPrefix(strings.TrimSpace(line), rsyncDeletingPrefix)
	if !ok || path == "" {
		return "", false
	}
	return path, true
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

	rsyncProgressTail   = 4096
	rsyncDeletingPrefix = "deleting "
)
