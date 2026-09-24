package probe

import (
	"cmp"
	"context"
	"fmt"
	"os"
	"slices"
	"strconv"
	"strings"
	"syscall"
	"time"

	"supervisor/internal/config"
	"supervisor/internal/metric"
	"supervisor/internal/scribe"
)

type BackupCommand int

type BackupRequest struct {
	Command  BackupCommand
	Trigger  string
	Config   string
	RunID    string
	Stage    metric.BackupStage
	Argument string
	Timeout  time.Duration
	Scrub    bool
}

func BackupStageOf(text string) (metric.BackupStage, error) {
	for _, stage := range backupStages {
		if strings.EqualFold(text, string(stage)) {
			return stage, nil
		}
	}
	return "", fmt.Errorf("stage reads [%s], taking one of [%s]", text, backupStagesNamed(backupStages))
}

func BackupPrepared(request BackupRequest) (BackupRequest, error) {
	if request.Command < backupCommandFirst || request.Command > backupCommandLast {
		return request, fmt.Errorf("unknown backup command [%d]", request.Command)
	}
	if request.Trigger != metric.BackupTriggerSystem && request.Trigger != metric.BackupTriggerManual {
		return request, fmt.Errorf("trigger reads [%s], taking [%s] or [%s]", request.Trigger, metric.BackupTriggerSystem, metric.BackupTriggerManual)
	}
	if request.Stage != "" {
		if _, err := BackupStageOf(string(request.Stage)); err != nil {
			return request, err
		}
		if request.Command != BackupCommandStart {
			return request, fmt.Errorf("[--stage] is only valid for [start], not [%s]", request.Command)
		}
	}
	if request.Scrub && request.Stage != "" && request.Stage != metric.BackupStageTertiary {
		return request, fmt.Errorf("[--scrub] is only valid for the [%s] stage, not [%s]", metric.BackupStageTertiary, request.Stage)
	}
	if request.Command == BackupCommandAuto && request.Argument != "" &&
		request.Argument != backupAutoOn && request.Argument != backupAutoOff {
		return request, fmt.Errorf("auto reads [%s], taking [%s] to turn the reaper on or [%s] to turn it off",
			request.Argument, backupAutoOn, backupAutoOff)
	}
	if slices.Contains(backupRunVerbs, request.Command) {
		request.RunID = cmp.Or(request.RunID, request.Argument)
		if request.RunID == "" && request.Command == BackupCommandStart {
			request.RunID = time.Now().Format(backupTimestampFormat)
		}
	}
	return request, nil
}

func BackupStageLog(request BackupRequest) string {
	return stageLogPath(backupRunPath(backupRunRoot(), request.RunID), request.Stage)
}

func Backup(ctx context.Context, request BackupRequest) error {
	request, err := BackupPrepared(request)
	if err != nil {
		return err
	}
	switch request.Command {
	case BackupCommandStart:
		return runBackupStart(ctx, request)
	case BackupCommandStop:
		return runBackupStop(ctx, request)
	case BackupCommandTail:
		return runBackupTail(request)
	case BackupCommandList:
		return runBackupList()
	case BackupCommandAuto:
		return runBackupAuto(request)
	default:
		return fmt.Errorf("unknown backup command [%d]", request.Command)
	}
}

func (c BackupCommand) String() string {
	if c < backupCommandFirst || c > backupCommandLast {
		return backupCommandUnnamed
	}
	return backupCommandNames[c]
}

func runBackupStart(ctx context.Context, request BackupRequest) error {
	root := backupRunRoot()
	runPath := backupRunPath(root, request.RunID)
	if err := os.MkdirAll(root, 0o755); err != nil {
		return fmt.Errorf("backup run root [%s] could not be created [%w]", root, err)
	}
	locked := lockPath(root)
	lock, err := os.OpenFile(locked, os.O_CREATE|os.O_RDWR, 0o644)
	if err != nil {
		return fmt.Errorf("backup run lock [%s] could not be opened [%w]", locked, err)
	}
	defer func() { _ = lock.Close() }()
	if err := syscall.Flock(int(lock.Fd()), syscall.LOCK_EX|syscall.LOCK_NB); err != nil {
		return fmt.Errorf("another backup run holds [%s], refusing to start", locked)
	}
	defer func() { _ = syscall.Flock(int(lock.Fd()), syscall.LOCK_UN) }()
	if err := os.MkdirAll(runPath, 0o755); err != nil {
		return fmt.Errorf("backup run directory [%s] could not be created [%w]", runPath, err)
	}

	stages := backupStages
	if request.Stage != "" {
		stages = []metric.BackupStage{request.Stage}
	}
	started := time.Now()
	expires := backupExpiry(request.Config, started, request.Timeout)
	host := scribe.SubjectHost(config.Load(request.Config).Host())
	scribe.Log(scribe.SourceBackup, host, scribe.ActionStart).Infof("schedule", started,
		"[%s] backup run over [%d] stages triggered by [%s]", request.RunID, len(stages), request.Trigger)

	var stageErr error
	for _, stage := range stages {
		staged := stageRequest{
			Stage: stage, RunID: request.RunID, RunPath: runPath, Expires: expires,
			Trigger: request.Trigger, ConfigPath: request.Config, Scrub: request.Scrub,
		}
		if stageErr = runStage(ctx, staged); stageErr != nil {
			break
		}
	}
	pruneRuns(root, host, started)
	document := finishRun(root, request.RunID, started)
	_ = publishRunStatus(request.Config, document)
	scribe.Log(scribe.SourceBackup, host, scribe.ActionStop).Infof("finished", started,
		"[%s] backup run resolved as [%s]", request.RunID, document.State)
	if stageErr != nil {
		return fmt.Errorf("run [%s] did not complete cleanly [%w]", request.RunID, stageErr)
	}
	return nil
}

func runBackupStop(ctx context.Context, request BackupRequest) error {
	root := backupRunRoot()
	runID, err := backupResolveRun(root, request.RunID)
	if err != nil {
		return err
	}
	runPath := backupRunPath(root, runID)
	stopped, refused := 0, 0
	for _, stage := range backupStages {
		document := readBackupSummary(stageStatusPath(runPath, stage))
		if document == nil || document.State != metric.BackupStateRunning {
			continue
		}
		staged := stageRequest{Stage: stage, RunID: runID, RunPath: runPath, ConfigPath: request.Config}
		if stopErr := stopStage(ctx, staged); stopErr != nil {
			scribe.Log(scribe.SourceBackup, scribe.SubjectStage(stage), scribe.ActionStop).Warnf("faulting", time.Now(),
				"[%s] stage stop reported [%v]", stage, stopErr)
			refused++
			continue
		}
		stopped++
	}
	if stopped == 0 && refused == 0 {
		fmt.Printf("no active stage found for run [%s]\n", runID)
		return nil
	}
	if refused > 0 {
		return fmt.Errorf("stopped [%d] of [%d] active stage(s) of run [%s]", stopped, stopped+refused, runID)
	}
	fmt.Printf("stopped [%d] active stage(s) of run [%s]\n", stopped, runID)
	return nil
}

func backupResolveRun(root, runID string) (string, error) {
	if runID != "" {
		return runID, nil
	}
	runs := backupRuns(root)
	if len(runs) == 0 {
		return "", fmt.Errorf("[none] backup run found under [%s]", root)
	}
	return runs[len(runs)-1], nil
}

func backupExpiry(configPath string, started time.Time, timeout time.Duration) time.Time {
	expires := time.Time{}
	if hours := config.Load(configPath).BackupTimeoutHours(); hours > 0 {
		expires = started.Add(time.Duration(hours) * time.Hour)
	}
	if override := os.Getenv(backupTimeoutVariable); override != "" {
		if hours, parseErr := strconv.Atoi(override); parseErr == nil && hours > 0 {
			expires = started.Add(time.Duration(hours) * time.Hour)
		}
	}
	if timeout > 0 {
		expires = started.Add(timeout)
	}
	return expires
}

func pruneRuns(root string, host scribe.Subject, started time.Time) {
	runs := backupRuns(root)
	if len(runs) <= backupRunsKept {
		return
	}
	pruned := runs[:len(runs)-backupRunsKept]
	for _, run := range pruned {
		if err := os.RemoveAll(backupRunPath(root, run)); err != nil {
			scribe.Log(scribe.SourceBackup, host, scribe.ActionRemove).Warnf("faulting", started,
				"[%s] backup run directory could not be removed with [%v]", run, err)
		}
	}
	scribe.Log(scribe.SourceBackup, host, scribe.ActionRemove).Debugf("expunged", started,
		"[%d] backup run directories beyond the newest [%d] under [%s]", len(pruned), backupRunsKept, root)
}

func backupStagesNamed(stages []metric.BackupStage) string {
	named := make([]string, 0, len(stages))
	for _, stage := range stages {
		named = append(named, string(stage))
	}
	return strings.Join(named, ", ")
}

func backupStagesOf(names []string) []metric.BackupStage {
	stages := make([]metric.BackupStage, 0, len(names))
	for _, name := range names {
		stages = append(stages, metric.BackupStage(name))
	}
	return stages
}

const (
	BackupCommandStart BackupCommand = iota
	BackupCommandStop
	BackupCommandTail
	BackupCommandList
	BackupCommandAuto
	backupCommandFirst = BackupCommandStart
	backupCommandLast  = BackupCommandAuto
)

const (
	backupTimestampFormat = "2006-01-02_15-04-05"
	backupDateFormat      = "2006-01-02"
	backupTimeFormat      = "15:04:05"
)

const (
	backupRunsKept        = 30
	backupScheduledHour   = 1
	backupTimeoutVariable = "BACKUP_TIMEOUT_HOURS"

	backupCommandUnnamed = "unnamed"
)

var (
	backupStages = []metric.BackupStage{
		metric.BackupStagePrimary,
		metric.BackupStageSecondary,
		metric.BackupStageTertiary,
	}

	backupRunVerbs = []BackupCommand{
		BackupCommandStart,
		BackupCommandStop,
		BackupCommandTail,
	}

	backupCommandNames = map[BackupCommand]string{
		BackupCommandStart: "start",
		BackupCommandStop:  "stop",
		BackupCommandTail:  "tail",
		BackupCommandList:  "list",
		BackupCommandAuto:  "auto",
	}
)
