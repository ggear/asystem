package probe

import (
	"context"
	"errors"
	"fmt"
	"io"
	"os"
	"os/exec"
	"path/filepath"
	"slices"
	"sort"
	"strconv"
	"strings"
	"time"

	"supervisor/internal/config"
	"supervisor/internal/metric"
	"supervisor/internal/scribe"
)

func runSecondaryStage(ctx context.Context, request stageRequest, counters *stageCounters) (stageResult, error) {
	loaded := config.Load(request.ConfigPath)
	host := loaded.Host()

	share, err := resolveShare(ctx, loaded, host)
	if err != nil {
		return stageResult{}, err
	}
	scribe.Log(scribe.SourceBackup, scribe.SubjectStage(metric.BackupStageSecondary), scribe.ActionStart).Infof("resolved", time.Now(), "[%s] resolved share", share)
	if err := mountTarget(ctx, share); err != nil {
		return stageResult{}, err
	}
	if err := os.MkdirAll(filepath.Join(share, treeBackupDirectory), 0o755); err != nil {
		return stageResult{}, fmt.Errorf("share backup directory could not be created [%w]", err)
	}

	servicePath := serviceRoot(request.RunPath)
	adopted := ""
	if _, err := os.Stat(stageDir(request.RunPath, metric.BackupStagePrimary)); err != nil {
		root := filepath.Dir(request.RunPath)
		if run, ok := adoptedRun(root); ok {
			adopted = run
			servicePath = serviceRoot(backupRunPath(root, run))
			scribe.Log(scribe.SourceBackup, scribe.SubjectStage(metric.BackupStageSecondary), scribe.ActionStart).Infof("adopting", time.Now(),
				"[%s] ran no primary, adopting the service list of run [%s]", request.RunID, run)
		} else {
			scribe.Log(scribe.SourceBackup, scribe.SubjectStage(metric.BackupStageSecondary), scribe.ActionStart).Warnf("faulting", time.Now(),
				"[%s] ran no primary and no earlier run recorded one", request.RunID)
		}
	}

	promote := append([]string{treeModule}, gradedServices(servicePath, true)...)
	for _, service := range gradedServices(servicePath, false) {
		scribe.Log(scribe.SourceBackup, scribe.SubjectService(service), scribe.ActionStart).Warnf("faulting", time.Now(),
			"[%s] not promoting, its primary backup did not succeed", service)
	}
	if len(promote) == 1 {
		label := adopted
		if label == "" {
			label = request.RunID
		}
		scribe.Log(scribe.SourceBackup, scribe.SubjectStage(metric.BackupStageSecondary), scribe.ActionStart).Warnf("faulting", time.Now(),
			"[%s] recorded no successful service backup, promoting supervisor alone", label)
	}

	counters.addTotal(pendingPromotionMB(share, host, promote))
	scribe.Log(scribe.SourceBackup, scribe.SubjectStage(metric.BackupStageSecondary), scribe.ActionStart).Infof("promoted", time.Now(),
		"[%d] services promoting to [%s/backup]", len(promote), share)

	failed := 0
	for index, service := range promote {
		if err := ctx.Err(); err != nil {
			return stageResult{}, err
		}
		if promoteErr := promoteOneService(ctx, request, share, host, service, index+1, len(promote), counters); promoteErr != nil {
			failed++
		}
	}

	percent, usedMB, totalMB, ok := measureUsage(ctx, share)
	result := stageResult{}
	if ok {
		result.diskUsagePerc, result.diskUsedMB, result.diskTotalMB = percent, usedMB, totalMB
	}
	if failed > 0 {
		return result, fmt.Errorf("[%d] of [%d] service promotions failed", failed, len(promote))
	}
	return result, nil
}

func promoteOneService(ctx context.Context, request stageRequest, share, host, service string, index, total int, counters *stageCounters) error {
	source := serviceHomeDir(service) + "/"
	target := promotionTarget(service, share, host)
	if _, err := os.Stat(strings.TrimSuffix(source, "/")); err != nil {
		scribe.Log(scribe.SourceBackup, scribe.SubjectService(service), scribe.ActionStart).Warnf("faulting", time.Now(),
			"[%s] skipped [%d/%d], no backup directory at [%s]", service, index, total, source)
		return fmt.Errorf("no backup directory for [%s]", service)
	}
	rsyncTemp := filepath.Join(target, ".rsync")
	if err := os.MkdirAll(rsyncTemp, 0o755); err != nil {
		return err
	}
	clearDirectory(rsyncTemp)

	started := time.Now()
	scribe.Log(scribe.SourceBackup, scribe.SubjectService(service), scribe.ActionStart).Infof("promoted", started,
		"[%s] promoting [%d/%d] from [%s] to [%s]", service, index, total, source, target)

	stats, rsyncErr := runRsync(ctx, nil, "-a", "--stats", "--out-format=%t %o %f %l",
		"--exclude", "/.lock", "--exclude", ".rsync/", "--exclude", ".rsync-*",
		"--temp-dir="+rsyncTemp, "--", source, target+"/")
	counters.addTransfer(stats.filesTransferred, stats.totalTransferredBytes/bytesPerMebibyte, stats.filesCreated,
		stats.filesDeleted, stats.filesListed, stats.totalFileSizeBytes/bytesPerMebibyte, stats.totalBytesSent/bytesPerMebibyte)
	scribe.Log(scribe.SourceBackup, scribe.SubjectService(service), scribe.ActionStop).Infof("promoted", started,
		"[%s] promoted in [%s], running total [%d] MiB", service, time.Since(started).Round(time.Second), counters.snapshotSizeMB())

	pruner := moduleBackupScript(service)
	if info, statErr := os.Stat(pruner); statErr == nil && info.Mode()&0o111 != 0 {
		scribe.Log(scribe.SourceBackup, scribe.SubjectService(service), scribe.ActionCompute).Infof("thinning", time.Now(),
			"[%s] thinning with the module pruner", target)
		command := exec.CommandContext(ctx, "bash", pruner, moduleBackupPruneFlag, target)
		command.Stdin = nil
		if pruneErr := command.Run(); pruneErr != nil {
			scribe.Log(scribe.SourceBackup, scribe.SubjectService(service), scribe.ActionCompute).Warnf("faulting", time.Now(),
				"[%s] module pruner exited with [%v], its history is unthinned", target, pruneErr)
		}
	} else {
		scribe.Log(scribe.SourceBackup, scribe.SubjectService(service), scribe.ActionCompute).Infof("thinning", time.Now(),
			"[%s] thinning with the generic pruner, the module ships none", target)
		gfsThin(ctx, target, config.Load(request.ConfigPath))
	}
	return rsyncErr
}

func stopSecondaryStage(ctx context.Context, _ stageRequest) error {
	pattern := "rsync .*" + backupHomeRoot()
	_, _, _ = bounded(ctx, stageBoundedWait, "pkill", "-CONT", "-f", pattern)
	_, _, _ = bounded(ctx, stageBoundedWait, "pkill", "-TERM", "-f", pattern)
	return nil
}

func resolveShare(ctx context.Context, loaded *config.Config, host string) (string, error) {
	if index, ok := loaded.HostIndex(host); ok {
		declared := fmt.Sprintf("%s/%d0", config.DirShare, index)
		if mountpointCheck(ctx, declared) {
			return declared, nil
		}
		scribe.Log(scribe.SourceBackup, scribe.SubjectStage(metric.BackupStageSecondary), scribe.ActionStart).Warnf("faulting", time.Now(),
			"[%s] is this host's declared share and is not mounted, looking for another", declared)
	}
	for _, mount := range backupShares() {
		if mountpointCheck(ctx, mount) {
			return mount, nil
		}
	}
	return "", fmt.Errorf("[none] share destination is mounted for host [%s]", host)
}

func promotionTarget(service, share, host string) string {
	if service == treeModule {
		return filepath.Join(share, treeBackupDirectory, service, host)
	}
	return filepath.Join(share, treeBackupDirectory, service)
}

func gradedServices(servicePath string, want bool) []string {
	entries, err := os.ReadDir(servicePath)
	if err != nil {
		return nil
	}
	var names []string
	for _, entry := range entries {
		if !entry.IsDir() {
			continue
		}
		document := readSummary[serviceSummary](filepath.Join(servicePath, entry.Name(), treeStatusLeaf))
		if document == nil || document.SuccessBool != want {
			continue
		}
		names = append(names, entry.Name())
	}
	sort.Strings(names)
	return names
}

func adoptedRun(root string) (string, bool) {
	runs := backupRuns(root)
	for _, run := range slices.Backward(runs) {
		path := serviceRoot(backupRunPath(root, run))
		if info, err := os.Stat(path); err == nil && info.IsDir() {
			return run, true
		}
	}
	return "", false
}

func pendingPromotionMB(share, host string, promote []string) int {
	pending := 0
	for _, service := range promote {
		source := serviceHomeDir(service)
		target := promotionTarget(service, share, host)
		_, sourceMB := directoryStats(source)
		_, targetMB := directoryStats(target)
		pending += sourceMB - targetMB
	}
	if pending < 0 {
		pending = 0
	}
	return pending
}

func clearDirectory(dir string) {
	entries, err := os.ReadDir(dir)
	if err != nil {
		return
	}
	for _, entry := range entries {
		_ = os.RemoveAll(filepath.Join(dir, entry.Name()))
	}
}

func gfsThin(ctx context.Context, dir string, loaded *config.Config) {
	keepDaily, keepWeekly, keepMonthly := loaded.BackupKeepDaily(), loaded.BackupKeepWeekly(), loaded.BackupKeepMonthly()
	if keepDaily+keepWeekly+keepMonthly <= 0 {
		scribe.Log(scribe.SourceBackup, scribe.SubjectNone, scribe.ActionRemove).Warnf("excluded", time.Now(),
			"[%s] is not thinned, the config declares no grandfather father son window so every dated directory would be pruned", dir)
		return
	}
	entries, err := os.ReadDir(dir)
	if err != nil {
		return
	}
	var names []string
	for _, entry := range entries {
		if entry.IsDir() && treeRunPattern.MatchString(entry.Name()) {
			names = append(names, entry.Name())
		}
	}
	if len(names) <= 1 {
		return
	}
	sort.Strings(names)
	count := len(names)
	keep := map[string]bool{}
	for index := count - 1; index >= 0 && index >= count-keepDaily; index-- {
		keep[names[index]] = true
	}
	weekSeen, monthSeen := map[string]bool{}, map[string]bool{}
	for index := count - 1; index >= 0; index-- {
		name := names[index]
		timestamp := name[:10]
		if parsed, err := time.Parse(backupDateFormat, timestamp); err == nil {
			year, week := parsed.ISOWeek()
			bucket := fmt.Sprintf("%04d-%02d", year, week)
			if !weekSeen[bucket] && len(weekSeen) < keepWeekly {
				weekSeen[bucket] = true
				keep[name] = true
			}
		}
		monthBucket := timestamp[:7]
		if !monthSeen[monthBucket] && len(monthSeen) < keepMonthly {
			monthSeen[monthBucket] = true
			keep[name] = true
		}
	}
	for _, name := range names {
		if keep[name] {
			continue
		}
		path := filepath.Join(dir, name)
		_, code, abandoned := bounded(ctx, stageBoundedWait, "btrfs", "subvolume", "delete", path)
		if abandoned || code != 0 {
			if err := os.RemoveAll(path); err != nil {
				scribe.Log(scribe.SourceBackup, scribe.SubjectNone, scribe.ActionRemove).Warnf("faulting", time.Now(),
					"[%s] could not be pruned from [%s] with [%v]", name, dir, err)
				continue
			}
		}
		scribe.Log(scribe.SourceBackup, scribe.SubjectNone, scribe.ActionRemove).Infof("expunged", time.Now(),
			"[%s] pruned from [%s] outside the grandfather father son window", name, dir)
	}
}

type rsyncStats struct {
	filesTransferred, filesListed, filesCreated, filesDeleted int
	totalTransferredBytes, totalFileSizeBytes, totalBytesSent int
}

func runRsync(ctx context.Context, sink io.Writer, args ...string) (rsyncStats, error) {
	out, code, abandoned := stageStream(ctx, sink, "rsync", args...)
	if abandoned {
		return rsyncStats{}, errors.New("[abandoned] rsync did not answer within its bound")
	}
	stats := rsyncStats{
		filesTransferred:      rsyncField(out, "Number of regular files transferred: "),
		filesListed:           rsyncField(out, "Number of files: "),
		filesCreated:          rsyncField(out, "Number of created files: "),
		filesDeleted:          rsyncField(out, "Number of deleted files: "),
		totalTransferredBytes: rsyncField(out, "Total transferred file size: "),
		totalFileSizeBytes:    rsyncField(out, "Total file size: "),
		totalBytesSent:        rsyncField(out, "Total bytes sent: "),
	}
	if code != 0 {
		return stats, fmt.Errorf("rsync exited [%d]", code)
	}
	return stats, nil
}

func rsyncField(output, prefix string) int {
	for line := range strings.SplitSeq(output, "\n") {
		after, ok := strings.CutPrefix(line, prefix)
		if !ok {
			continue
		}
		token := strings.Fields(after)
		if len(token) == 0 {
			continue
		}
		digits := onlyDigits(token[0])
		value, _ := strconv.Atoi(digits)
		return value
	}
	return 0
}

func onlyDigits(text string) string {
	var builder strings.Builder
	for _, letter := range text {
		if letter >= '0' && letter <= '9' {
			builder.WriteRune(letter)
		}
	}
	if builder.Len() == 0 {
		return "0"
	}
	return builder.String()
}
