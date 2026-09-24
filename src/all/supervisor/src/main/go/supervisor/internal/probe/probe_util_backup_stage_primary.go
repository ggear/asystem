package probe

import (
	"context"
	"encoding/json"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"sort"
	"strconv"
	"strings"
	"time"

	"supervisor/internal/config"
	"supervisor/internal/metric"
	"supervisor/internal/scribe"
)

func runPrimaryStage(ctx context.Context, request stageRequest, counters *stageCounters) (stageResult, error) {
	loaded := config.Load(request.ConfigPath)
	host := loaded.Host()
	configured := loaded.Services(host)
	var enrolled []string
	for _, service := range configured {
		script := moduleBackupScript(service)
		if info, err := os.Stat(script); err == nil && info.Mode()&0o111 != 0 {
			enrolled = append(enrolled, service)
		}
	}
	sort.Strings(enrolled)
	scribe.Log(scribe.SourceBackup, scribe.SubjectStage(metric.BackupStagePrimary), scribe.ActionStart).Infof("enrolled", time.Now(),
		"[%d] configured services, of which [%d] ship a backup.sh", len(configured), len(enrolled))

	failed := 0
	for index, service := range enrolled {
		if err := ctx.Err(); err != nil {
			return stageResult{}, err
		}
		if runOneService(ctx, request, loaded, service, index+1, len(enrolled), counters) != nil {
			failed++
		}
	}
	scribe.Log(scribe.SourceBackup, scribe.SubjectStage(metric.BackupStagePrimary), scribe.ActionStop).Infof("reported", time.Now(),
		"[%d] services attempted with [%d] failed", len(enrolled), failed)
	if failed > 0 {
		return stageResult{}, fmt.Errorf("[%d] of [%d] service backups failed", failed, len(enrolled))
	}
	return stageResult{}, nil
}

func runOneService(ctx context.Context, request stageRequest, loaded *config.Config, service string, index, total int, counters *stageCounters) error {
	dir := serviceDir(request.RunPath, service)
	statusPath := serviceStatusPath(request.RunPath, service)
	if err := os.MkdirAll(dir, 0o755); err != nil {
		return fmt.Errorf("service directory [%s] could not be created [%w]", dir, err)
	}
	host := loaded.Host()
	subject := scribe.SubjectService(service)

	running, health := dockerServiceState(ctx, service)
	if !running {
		scribe.Log(scribe.SourceBackup, subject, scribe.ActionStart).Warnf("faulting", time.Now(),
			"[%s] skipped [%d/%d], container is not running", service, index, total)
		return fmt.Errorf("container [%s] is not running", service)
	}
	if health == "starting" {
		scribe.Log(scribe.SourceBackup, subject, scribe.ActionStart).Warnf("faulting", time.Now(),
			"[%s] skipped [%d/%d], container is still starting", service, index, total)
		return fmt.Errorf("container [%s] is still starting", service)
	}

	started := time.Now()
	backupDir := serviceHomeDir(service)
	previous := newestBackupDir(backupDir)

	scribe.Log(scribe.SourceBackup, subject, scribe.ActionStart).Infof("starting", started,
		"[%s] started [%d/%d]", service, index, total)
	_ = writeAtomic(statusPath, serviceSummary{
		RunID: request.RunID, State: metric.BackupStateRunning, StartedTS: started.Format(time.RFC3339),
	})

	logPath := serviceLogPath(request.RunPath, service)
	logFile, err := os.Create(logPath)
	if err != nil {
		return fmt.Errorf("service log [%s] could not be created [%w]", logPath, err)
	}
	defer func() { _ = logFile.Close() }()

	script := moduleBackupScript(service)
	command := exec.CommandContext(ctx, "bash", script)
	command.Stdin = nil
	command.Stdout = logFile
	command.Stderr = logFile
	command.Env = append(os.Environ(),
		moduleSkipHoursVariable+"="+strconv.Itoa(moduleSkipHours()),
		moduleRestartVariable+"=true",
		backupTimeoutVariable+"="+strconv.Itoa(moduleTimeoutHours(loaded, request)))
	runErr := command.Run()

	state, ok := metric.BackupStateSuccess, true
	if runErr != nil {
		state, ok = metric.BackupStateFailure, false
	}
	newest := newestBackupDir(backupDir)
	if state == metric.BackupStateSuccess && newest == previous {
		state = metric.BackupStateSkipped
	}

	sizeMB, files, kind, version := 0, 0, "unknown", "unknown"
	if newest != "" {
		files, sizeMB = directoryStats(newest)
		kind, version = parseBackupArtefact(service, newest)
	}
	document := serviceSummary{
		RunID: request.RunID, BackupID: backupIdentity(newest),
		State: state, StartedTS: started.Format(time.RFC3339), FinishedTS: time.Now().Format(time.RFC3339),
		DurationS: int(time.Since(started).Seconds()), SuccessBool: ok, Kind: kind, Version: version,
		FileCount: files, SizeMB: sizeMB,
	}
	_ = writeAtomic(statusPath, document)

	scribe.Log(scribe.SourceBackup, subject, scribe.ActionStop).Infof("finished", started,
		"[%s] finished as [%s], kind [%s], version [%s], size [%d] MiB", service, state, kind, version, sizeMB)

	if state == metric.BackupStateSuccess {
		counters.addTransfer(files, sizeMB, files, 0, 0, 0, 0)
	}
	if client, dialErr := brokerDial(request.ConfigPath, "primary"); dialErr == nil {
		defer client.close()
		if payload, marshalErr := json.Marshal(document); marshalErr == nil {
			_ = client.publishRetained(metric.TopicBackupService(host, service), string(payload))
		}
	}
	if !ok {
		return fmt.Errorf("service [%s] backup script exited non-zero", service)
	}
	return nil
}

func stopPrimaryStage(ctx context.Context, request stageRequest) error {
	_, _, _ = bounded(ctx, stageBoundedWait, "pkill", "-CONT", "-f", moduleBackupScriptPattern)
	_, _, _ = bounded(ctx, stageBoundedWait, "pkill", "-TERM", "-f", moduleBackupScriptPattern)
	return nil
}

func dockerServiceState(ctx context.Context, service string) (running bool, health string) {
	names, _, _ := stageExec(ctx, "docker", "ps", "--filter", "name=^/"+service+"$", "--filter", "status=running", "--format", "{{.Names}}")
	running = strings.TrimSpace(names) == service
	if !running {
		return false, ""
	}
	out, _, _ := stageExec(ctx, "docker", "inspect", "--format", "{{if .State.Health}}{{.State.Health.Status}}{{end}}", service)
	return true, strings.TrimSpace(out)
}

func newestBackupDir(root string) string {
	entries, err := os.ReadDir(root)
	if err != nil {
		return ""
	}
	var names []string
	for _, entry := range entries {
		if entry.IsDir() && treeRunPattern.MatchString(entry.Name()) {
			names = append(names, entry.Name())
		}
	}
	if len(names) == 0 {
		return ""
	}
	sort.Strings(names)
	return filepath.Join(root, names[len(names)-1])
}

func parseBackupArtefact(service, dir string) (kind, version string) {
	kind, version = "unknown", "unknown"
	entries, err := os.ReadDir(dir)
	if err != nil {
		return
	}
	var files []string
	for _, entry := range entries {
		if !entry.IsDir() {
			files = append(files, entry.Name())
		}
	}
	if len(files) == 0 {
		return
	}
	sort.Strings(files)
	file := files[0]
	stem := file
	switch {
	case strings.Contains(file, "_delta."):
		kind = "delta"
		stem = strings.SplitN(file, "_delta.", 2)[0]
	case strings.Contains(file, "_full."):
		kind = "full"
		stem = strings.SplitN(file, "_full.", 2)[0]
	}
	timestamp := filepath.Base(dir)
	switch {
	case strings.Contains(stem, "_from_"):
		version = stem[strings.LastIndex(stem, "_from_")+len("_from_"):]
	default:
		prefix := service + "_" + timestamp + "_"
		if after, ok := strings.CutPrefix(stem, prefix); ok {
			version = after
		}
	}
	if version == "" || version == stem {
		version = "unknown"
	}
	return
}

func backupIdentity(newest string) string {
	if newest == "" {
		return "none"
	}
	return filepath.Base(newest)
}

func moduleSkipHours() int {
	if override := os.Getenv(moduleSkipHoursVariable); override != "" {
		if hours, err := strconv.Atoi(override); err == nil && hours >= 0 {
			return hours
		}
	}
	return moduleSkipHoursDefault
}

func moduleTimeoutHours(loaded *config.Config, request stageRequest) int {
	if !request.Expires.IsZero() {
		if hours := int(time.Until(request.Expires).Hours()); hours > 0 {
			return hours
		}
	}
	return loaded.BackupTimeoutHours()
}
