package probe

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"math"
	"os"
	"os/exec"
	"path/filepath"
	"sync"
	"time"

	"supervisor/internal/config"
	"supervisor/internal/metric"
	"supervisor/internal/scribe"
)

func runStage(ctx context.Context, request stageRequest) error {
	stagePath := stageDir(request.RunPath, request.Stage)
	if err := os.MkdirAll(stagePath, 0o755); err != nil {
		return fmt.Errorf("stage directory [%s] could not be created [%w]", stagePath, err)
	}
	started := time.Now()
	stoppedMarker := filepath.Join(stagePath, stageStoppedMarker)
	_ = os.Remove(stoppedMarker)

	stageCtx, cancel := context.WithCancelCause(ctx)
	defer cancel(nil)
	if !request.Expires.IsZero() {
		deadline := request.Expires
		if !time.Now().Before(deadline) {
			deadline = time.Now().Add(stageExpiredGrace)
		}
		timer := time.AfterFunc(time.Until(deadline), func() { cancel(errStageTimedOut) })
		defer timer.Stop()
	}
	stop := context.AfterFunc(stageCtx, func() {
		if errors.Is(context.Cause(stageCtx), errStageTimedOut) {
			_ = os.WriteFile(filepath.Join(stagePath, stageTimedOutMarker), nil, 0o644)
		}
	})
	defer stop()

	subject := scribe.SubjectStage(request.Stage)
	deadlineText := "none"
	timeoutHours := 0
	if !request.Expires.IsZero() {
		deadlineText = request.Expires.Format(backupTimeFormat)
		timeoutHours = int(math.Round(request.Expires.Sub(started).Hours()))
	}
	scribe.Log(scribe.SourceBackup, subject, scribe.ActionStart).Infof("starting", started,
		"[%s] stage [%s] timeout [%s]", request.RunID, request.Stage, deadlineText)

	announce := func(document backupSummary) {
		client, dialErr := brokerDial(request.ConfigPath, "stages")
		if dialErr != nil {
			return
		}
		defer client.close()
		if payload, marshalErr := json.Marshal(document); marshalErr == nil {
			_ = client.publishRetained(metric.TopicBackupStage(configHost(request.ConfigPath), request.Stage), string(payload))
		}
	}
	beat := func(quiet bool) backupSummary {
		document := backupSummary{
			RunID: request.RunID, State: metric.BackupStateRunning, Trigger: request.Trigger,
			StartedTS: started.Format(time.RFC3339), DurationS: int(time.Since(started).Seconds()),
			ExpiresTS: time.Now().Add(stageLivenessGrace).Format(time.RFC3339), TimeoutHours: timeoutHours,
		}
		_ = writeAtomic(stageStatusPath(request.RunPath, request.Stage), document)
		if !quiet {
			scribe.Log(scribe.SourceBackup, subject, scribe.ActionPublish).Debugf("beaconed", started,
				"[%s] stage [%s] still running, liveness refreshed to [%s]", request.RunID, request.Stage,
				time.Now().Add(stageLivenessGrace).Format(backupTimeFormat))
		}
		return document
	}
	announce(beat(true))
	refreshed := time.Now()
	backgroundDone := make(chan struct{})
	backgroundCtx, stopBackground := context.WithCancel(stageCtx)
	go func() {
		defer close(backgroundDone)
		ticker := time.NewTicker(stageLivenessInterval)
		defer ticker.Stop()
		for {
			select {
			case <-backgroundCtx.Done():
				return
			case <-ticker.C:
				if _, err := os.Stat(stoppedMarker); err == nil {
					cancel(errStageStopped)
					continue
				}
				if request.Stage == metric.BackupStageTertiary && !attached(backgroundCtx, stagePath) {
					scribe.Log(scribe.SourceBackup, subject, scribe.ActionStop).Errorf("faulting", started,
						"[%s] %s, stopping this stage before it writes anywhere else", config.DirBackup,
						diagnosed(backgroundCtx, config.DirBackup))
					cancel(errStageDetached)
					continue
				}
				loud := time.Since(refreshed) >= stageHeartbeatRefresh
				document := beat(!loud)
				if loud {
					refreshed = time.Now()
					announce(document)
				}
			}
		}
	}()
	defer func() {
		stopBackground()
		<-backgroundDone
	}()

	counters := &stageCounters{}
	var result stageResult
	var runErr error
	switch request.Stage {
	case metric.BackupStagePrimary:
		result, runErr = runPrimaryStage(stageCtx, request, counters)
	case metric.BackupStageSecondary:
		result, runErr = runSecondaryStage(stageCtx, request, counters)
	case metric.BackupStageTertiary:
		result, runErr = runTertiaryStage(stageCtx, request, counters)
	default:
		runErr = fmt.Errorf("unknown stage [%s]", request.Stage)
	}

	state, success := stageVerdict(context.Cause(stageCtx), runErr, result.skipped)

	document := backupSummary{
		RunID: request.RunID, State: state, Trigger: request.Trigger,
		StartedTS: started.Format(time.RFC3339), FinishedTS: time.Now().Format(time.RFC3339),
		DurationS: int(time.Since(started).Seconds()), SuccessBool: success, TimeoutHours: timeoutHours,
		TotalMB: counters.totalMB, FileCount: counters.fileCount, SizeMB: counters.sizeMB,
		FilesHeld: counters.filesHeld, FilesCreated: counters.filesCreated, FilesDeleted: counters.filesDeleted,
		SizeHeldMB: counters.sizeHeldMB, SentMB: counters.sentMB,
		DiskUsagePerc: result.diskUsagePerc, DiskUsedMB: result.diskUsedMB,
		DiskTotalMB: result.diskTotalMB, DiskUncleanBool: result.diskUnclean,
	}
	path := stageStatusPath(request.RunPath, request.Stage)
	if writeErr := writeAtomic(path, document); writeErr != nil {
		scribe.Log(scribe.SourceBackup, subject, scribe.ActionPublish).Warnf("faulting", time.Now(),
			"[%s] stage document could not be written [%v]", path, writeErr)
	} else {
		announce(document)
	}

	if runErr != nil {
		scribe.Log(scribe.SourceBackup, subject, scribe.ActionStop).Warnf("faulting", started,
			"[%s] stage [%s] finished as [%s] with [%v]", request.RunID, request.Stage, state, runErr)
		return fmt.Errorf("stage [%s] failed [%w]", request.Stage, runErr)
	}
	scribe.Log(scribe.SourceBackup, subject, scribe.ActionStop).Infof("finished", started,
		"[%s] stage [%s] finished as [%s], [%s] MiB at [%s] MiB/s", request.RunID, request.Stage, state,
		backupSized(intReading(int64(document.SizeMB))), backupThroughput(backupRated(intReading(int64(document.SizeMB)), intReading(int64(document.DurationS)))))
	return nil
}

func stageVerdict(cause, runErr error, skipped bool) (string, bool) {
	switch {
	case errors.Is(cause, errStageTimedOut):
		return metric.BackupStateTimeout, false
	case errors.Is(cause, errStageStopped), errors.Is(cause, errStageDetached):
		return metric.BackupStateStopped, false
	case runErr != nil:
		return metric.BackupStateFailure, false
	case skipped:
		return metric.BackupStateSkipped, true
	default:
		return metric.BackupStateSuccess, true
	}
}

func stopStage(ctx context.Context, request stageRequest) error {
	stagePath := stageDir(request.RunPath, request.Stage)
	_ = os.WriteFile(filepath.Join(stagePath, stageStoppedMarker), nil, 0o644)
	switch request.Stage {
	case metric.BackupStagePrimary:
		return stopPrimaryStage(ctx, request)
	case metric.BackupStageSecondary:
		return stopSecondaryStage(ctx, request)
	case metric.BackupStageTertiary:
		return stopTertiaryStage(ctx, request)
	default:
		return nil
	}
}

func bounded(ctx context.Context, limit time.Duration, name string, args ...string) (stdout string, exitCode int, abandoned bool) {
	boundedCtx, cancel := context.WithTimeout(ctx, limit)
	defer cancel()
	return stageExec(boundedCtx, name, args...)
}

func realStageExec(ctx context.Context, name string, args ...string) (string, int, bool) {
	command := exec.CommandContext(ctx, name, args...)
	command.Stdin = nil
	buffer := &lockedBuffer{}
	command.Stdout = buffer
	command.Stderr = buffer
	command.WaitDelay = stageExecAbandon
	runErr := command.Run()
	if ctx.Err() != nil {
		return buffer.String(), stageBoundedAbandoned, true
	}
	if runErr == nil {
		return buffer.String(), 0, false
	}
	if exitErr, ok := errors.AsType[*exec.ExitError](runErr); ok {
		return buffer.String(), exitErr.ExitCode(), false
	}
	if errors.Is(runErr, exec.ErrWaitDelay) && command.ProcessState != nil {
		return buffer.String(), command.ProcessState.ExitCode(), false
	}
	return buffer.String(), -1, false
}

func (b *lockedBuffer) Write(data []byte) (int, error) {
	b.mu.Lock()
	defer b.mu.Unlock()
	return b.buffer.Write(data)
}

func (b *lockedBuffer) String() string {
	b.mu.Lock()
	defer b.mu.Unlock()
	return b.buffer.String()
}

func moduleBackupScript(service string) string {
	return filepath.Join(config.DirInstall, service, config.DirInstallLatestLink, moduleBackupLeaf)
}

func configHost(configPath string) string {
	return config.Load(configPath).Host()
}

func commandAvailable(name string) bool {
	_, err := exec.LookPath(name)
	return err == nil
}

func directoryStats(dir string) (files, sizeMB int) {
	var total int64
	_ = filepath.Walk(dir, func(_ string, info os.FileInfo, err error) error {
		if err != nil || info.IsDir() {
			return nil
		}
		files++
		total += info.Size()
		return nil
	})
	return files, int(total / bytesPerMebibyte)
}

type stageRequest struct {
	Stage      metric.BackupStage
	RunID      string
	RunPath    string
	Expires    time.Time
	Trigger    string
	ConfigPath string
	Scrub      bool
}

type stageResult struct {
	skipped       bool
	diskUsagePerc float64
	diskUsedMB    int
	diskTotalMB   int
	diskUnclean   bool
}

type stageCounters struct {
	mu                                                                                    sync.Mutex
	totalMB, fileCount, sizeMB, filesHeld, filesCreated, filesDeleted, sizeHeldMB, sentMB int
}

func (c *stageCounters) addTotal(mb int) {
	c.mu.Lock()
	c.totalMB += mb
	c.mu.Unlock()
}

func (c *stageCounters) addTransfer(files, sizeMB, filesCreated, filesDeleted, filesHeld, sizeHeldMB, sentMB int) {
	c.mu.Lock()
	c.fileCount += files
	c.sizeMB += sizeMB
	c.filesCreated += filesCreated
	c.filesDeleted += filesDeleted
	c.filesHeld += filesHeld
	c.sizeHeldMB += sizeHeldMB
	c.sentMB += sentMB
	c.mu.Unlock()
}

func (c *stageCounters) snapshotSizeMB() int {
	c.mu.Lock()
	defer c.mu.Unlock()
	return c.sizeMB
}

type lockedBuffer struct {
	mu     sync.Mutex
	buffer bytes.Buffer
}

type execFunc func(ctx context.Context, name string, args ...string) (stdout string, exitCode int, abandoned bool)

var stageExec = execFunc(realStageExec)

var (
	errStageTimedOut = errors.New("stage timed out")
	errStageStopped  = errors.New("stage stopped")
	errStageDetached = errors.New("backup disk detached mid stage")
)

const (
	moduleSkipHoursDefault  = 1
	moduleSkipHoursVariable = "BACKUP_SKIP_HOURS"
	moduleRestartVariable   = "BACKUP_SERVICE_RESTART"
	moduleBackupPruneFlag   = "--prune-gfs"
	moduleBackupLeaf        = "backup.sh"

	moduleBackupScriptPattern = config.DirInstall + `/[a-z0-9_-]*/` + config.DirInstallLatestLink + `/` + moduleBackupLeaf
)

const (
	stageExpiredGrace     = time.Minute
	stageLivenessInterval = 10 * time.Second
	stageLivenessGrace    = time.Hour
	stageHeartbeatRefresh = 10 * time.Minute

	stageBoundedWait      = 60 * time.Second
	stageBoundedAbandoned = 124
	stageExecAbandon      = 2 * time.Second

	stageTimedOutMarker = ".timedout"
	stageStoppedMarker  = ".stopped"
)
