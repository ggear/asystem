package probe

import (
	"context"
	"encoding/json"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"regexp"
	"sort"
	"strings"
	"supervisor/internal/config"
	"supervisor/internal/metric"
	"supervisor/internal/scribe"
	"supervisor/internal/stats"
	"sync"
	"sync/atomic"
	"syscall"
	"time"
)

type backupProbe struct {
	cache      *metric.RecordCache
	mask       [metric.MetricMax]bool
	periods    config.Periods
	configPath string
	hostName   string
	serverHost bool
	root       string
	runner     string

	failedBackupStagesInt *stats.IntStats
	usedBackupSpaceInt    *stats.IntStats

	snapshotMu      sync.Mutex
	snapshot        *backupSnapshot
	snapshotTakenAt time.Time
	backupRunning   sync.Mutex
	backupActive    atomic.Bool
	reapRunning     sync.Mutex
	reapIdle        int
	reapWatch       *brokerWatcher
}

func newBackupProbe() *backupProbe {
	backupProbeInstance = &backupProbe{root: backupRunRoot, runner: backupRunner}
	return backupProbeInstance
}

func (*backupProbe) subject() scribe.Subject { return scribe.SubjectHost("") }

// TODO: Return false to arm the backup driver, dormant so the estate can be released with it
func (*backupProbe) dormant() bool { return true }

func (p *backupProbe) metrics() []metric.ID {
	return []metric.ID{metric.MetricHostFailedBackupStages, metric.MetricHostUsedBackupSpace}
}

func (p *backupProbe) gates() []metric.GateID { return nil }

func (p *backupProbe) create(configPath string, cache *metric.RecordCache, mask [metric.MetricMax]bool, periods config.Periods) error {
	p.cache = cache
	p.mask = mask
	p.periods = periods
	p.configPath = configPath
	loaded := config.Load(configPath)
	p.hostName = loaded.Host()
	_, p.serverHost = loaded.HostIndex(p.hostName)
	p.failedBackupStagesInt = stats.NewIntStats(periods.TrendHours, float64(periods.PulseMillis)/1000.0, float64(periods.PollMillis)/1000.0)
	p.usedBackupSpaceInt = stats.NewIntStats(periods.TrendHours, float64(periods.PulseMillis)/1000.0, float64(periods.PollMillis)/1000.0)
	return nil
}

func (p *backupProbe) records() *metric.RecordCache { return p.cache }

func (p *backupProbe) hasMetric(id metric.ID) bool {
	return id >= 0 && id < metric.MetricMax && p.mask[id]
}

func (p *backupProbe) poll(ctx context.Context, isPulse bool) error {
	runCacheMetricTasks(p, isPulse, nil, []cacheMetricTask{
		newCacheMetricTask(
			metric.ValueInt,
			metric.MetricHostFailedBackupStages,
			metric.ServiceNameUnset,
			p.failedBackupStages,
			p.failedBackupStagesInt,
			func() int8 { return p.failedBackupStagesInt.PulseMax() },
			func() int8 { return p.failedBackupStagesInt.TrendMax() },
		),
		newCacheMetricTask(
			metric.ValueInt,
			metric.MetricHostUsedBackupSpace,
			metric.ServiceNameUnset,
			p.usedBackupSpace,
			p.usedBackupSpaceInt,
			func() int8 { return p.usedBackupSpaceInt.PulseMax() },
			func() int8 { return p.usedBackupSpaceInt.TrendMax() },
		),
	})
	return nil
}

func (p *backupProbe) failedBackupStages() (int8, derivation, error) {
	snapshot := p.documents()
	if snapshot != nil && snapshot.running {
		return 0, derivedInertf(scribe.ActionCompute, "computed [0] pct failed, run [%s] started [%s] ago has not written its roll-up yet so the metric is inert and always ok",
			snapshot.dir, snapshot.age().Round(time.Minute)), nil
	}
	if snapshot == nil || snapshot.host == nil || snapshot.age() > backupStaleWindow {
		return 100, derivedf(scribe.ActionCompute, "computed [100] pct failed, no run directory under [%s] holds a status document inside the [%s] window",
			p.root, backupStaleWindow), nil
	}
	run := max(snapshot.host.StagesRun, 1)
	value := percentValue(float64(snapshot.host.StagesFailed) / float64(run) * 100.0)
	return value, derivedf(scribe.ActionCompute, "computed [%3d] pct failed, run [%s] aged [%s] reported [%d] of [%d] stages failed",
		value, snapshot.dir, snapshot.age().Round(time.Minute), snapshot.host.StagesFailed, run), nil
}

func (p *backupProbe) usedBackupSpace() (int8, derivation, error) {
	snapshot := p.documents()
	if snapshot == nil || snapshot.tertiary == nil || snapshot.tertiary.State == "running" {
		if !p.serverHost {
			return 0, derivedInertf(scribe.ActionCompute, "computed [0] pct used, host [%s] owns no share index so it runs no tertiary stage and holds no backup disk, so the metric is inert and always ok", p.hostName), nil
		}
		if snapshot != nil && snapshot.running {
			return 0, derivedInertf(scribe.ActionCompute, "computed [0] pct used, run [%s] started [%s] ago has not measured the backup disk yet so the metric is inert and always ok",
				snapshot.dir, snapshot.age().Round(time.Minute)), nil
		}
		return 0, derivation{}, fmt.Errorf("no backup volume reading, this host has written no tertiary stage document under [%s] [%w]", p.root, errEnvironment)
	}
	value := percentValue(snapshot.tertiary.DiskUsagePerc)
	return value, derivedf(scribe.ActionCompute, "computed [%3d] pct used, tertiary stage of run [%s] aged [%s] measured [%.1f] pct disk usage on /backup",
		value, snapshot.dir, snapshot.age().Round(time.Minute), snapshot.tertiary.DiskUsagePerc), nil
}

func (p *backupProbe) serviceSuccess(service string) (bool, bool) {
	snapshot := p.documents()
	if snapshot == nil || snapshot.age() > backupStaleWindow {
		return false, false
	}
	success, found := snapshot.services[service]
	return success, found
}

func (p *backupProbe) reap(ctx context.Context) {
	if !p.reapRunning.TryLock() {
		return
	}
	defer p.reapRunning.Unlock()
	if !p.serverHost {
		return
	}
	reapStart := config.NowIncludingSuspend()
	loaded := config.Load(p.configPath)
	if snapshot := readNewestRun(p.root); snapshot != nil {
		p.reapLocalStale(ctx, snapshot)
	}
	if p.backupActive.Load() {
		return
	}
	commandTopic, stateTopic := loaded.BackupCommandTopic(), loaded.BackupStateTopic()
	if commandTopic == "" || stateTopic == "" {
		return
	}
	if p.reapWatch == nil {
		watch, err := brokerWatch(p.configPath, p.hostName, stateTopic, clusterLeaderTopic, "supervisor/+/backup/stage/tertiary/status")
		if err != nil {
			scribe.Log(scribe.SourceProbeBackup, scribe.SubjectHost(p.hostName), scribe.ActionConnect).Warnf("faulting", reapStart, "[%v] watching the estate, retrying on the next tick", err)
			return
		}
		p.reapWatch = watch
	}
	retained, watching := p.reapWatch.readRetained()
	if !watching {
		p.reapIdle = 0
		return
	}
	if !strings.EqualFold(strings.TrimSpace(retained[stateTopic]), "on") {
		p.reapIdle = 0
		return
	}
	var lease backupLease
	if json.Unmarshal([]byte(retained[clusterLeaderTopic]), &lease) == nil && !lease.expired() {
		p.reapIdle = 0
		return
	}
	for topic, payload := range retained {
		if !strings.HasSuffix(topic, "/backup/stage/tertiary/status") {
			continue
		}
		var document backupDocument
		if json.Unmarshal([]byte(payload), &document) != nil || document.State != "running" || document.ExpiresTS == "" {
			continue
		}
		if expires, perr := time.Parse(time.RFC3339, document.ExpiresTS); perr == nil && time.Now().Before(expires) {
			p.reapIdle = 0
			return
		}
	}
	p.reapIdle++
	if p.reapIdle < reaperIdleTicks {
		return
	}
	p.reapIdle = 0
	isLeader, leaderClient := electBackupLeader(p.configPath, p.hostName, "reaper-"+time.Now().Format(backupRunStamp))
	if !isLeader || leaderClient == nil {
		return
	}
	_ = leaderClient.publishCommand(commandTopic, "OFF")
	_ = leaderClient.publishRetained(clusterLeaderTopic, "")
	leaderClient.close()
	scribe.Log(scribe.SourceProbeBackup, scribe.SubjectHost(p.hostName), scribe.ActionPublish).Infof("released", reapStart, "[%s] backup disk powered down, no tertiary stage running for [%d] ticks", commandTopic, reaperIdleTicks)
}

func (p *backupProbe) reapLocalStale(ctx context.Context, snapshot *backupSnapshot) {
	document := snapshot.tertiary
	if document == nil || document.State != "running" || document.ExpiresTS == "" {
		return
	}
	expires, err := time.Parse(time.RFC3339, document.ExpiresTS)
	if err != nil || time.Now().Before(expires) {
		return
	}
	if _, statErr := os.Stat(p.runner); statErr != nil {
		return
	}
	staleStart := config.NowIncludingSuspend()
	runPath := filepath.Join(p.root, snapshot.dir)
	scribe.Log(scribe.SourceProbeBackup, scribe.SubjectHost(p.hostName), scribe.ActionStop).Warnf("faulting", staleStart, "[%s] tertiary stage still running with liveness expired at [%s], stopping it", snapshot.dir, document.ExpiresTS)
	stop := exec.CommandContext(context.WithoutCancel(ctx), "bash", p.runner, "tertiary", "stop", snapshot.dir)
	stop.Env = append(os.Environ(), "BACKUP_RUN_ID="+snapshot.dir, "BACKUP_RUN_PATH="+runPath, "BACKUP_RUN_ID_PASSED=1")
	_ = stop.Run()
	stale := *document
	stale.State = "timeout"
	stale.FinishedTS = time.Now().Format(time.RFC3339)
	stale.ExpiresTS = ""
	writeDocumentAtomic(stageStatusPath(runPath, "tertiary"), stale)
	p.refresh()
}

func (p *backupProbe) documents() *backupSnapshot {
	p.snapshotMu.Lock()
	defer p.snapshotMu.Unlock()
	if p.snapshot != nil && config.SinceIncludingSuspend(p.snapshotTakenAt) < config.CacheWindow(p.periods.CacheMins) {
		return p.snapshot
	}
	p.snapshot = readNewestRun(p.root)
	p.snapshotTakenAt = config.NowIncludingSuspend()
	return p.snapshot
}

func (p *backupProbe) refresh() {
	p.snapshotMu.Lock()
	p.snapshot = nil
	p.snapshotMu.Unlock()
}

func (p *backupProbe) cycle(ctx context.Context, hour int, isHour bool) {
	p.reap(ctx)
	if !isHour || hour != backupScheduledHour {
		return
	}
	if !p.backupRunning.TryLock() {
		return
	}
	defer p.backupRunning.Unlock()
	p.backupActive.Store(true)
	defer p.backupActive.Store(false)
	runStart := time.Now()
	if err := os.MkdirAll(p.root, 0o755); err != nil {
		scribe.Log(scribe.SourceProbeBackup, scribe.SubjectHost(p.hostName), scribe.ActionStart).Errorf("faulting", runStart, "[%s] backup run root could not be created with [%v]", p.root, err)
		return
	}
	lock, err := os.OpenFile(filepath.Join(p.root, ".lock"), os.O_CREATE|os.O_RDWR, 0o644)
	if err != nil {
		scribe.Log(scribe.SourceProbeBackup, scribe.SubjectHost(p.hostName), scribe.ActionStart).Errorf("faulting", runStart, "[%s] backup run lock could not be opened with [%v]", p.root, err)
		return
	}
	defer lock.Close()
	if err := syscall.Flock(int(lock.Fd()), syscall.LOCK_EX|syscall.LOCK_NB); err != nil {
		scribe.Log(scribe.SourceProbeBackup, scribe.SubjectHost(p.hostName), scribe.ActionStart).Debugf("deferred", runStart, "[held] backup run lock, another run is in progress, skipping")
		return
	}
	defer syscall.Flock(int(lock.Fd()), syscall.LOCK_UN)

	runID := time.Now().Format(backupRunStamp)
	runPath := filepath.Join(p.root, runID)
	if err := os.MkdirAll(runPath, 0o755); err != nil {
		scribe.Log(scribe.SourceProbeBackup, scribe.SubjectHost(p.hostName), scribe.ActionStart).Errorf("faulting", runStart, "[%s] backup run directory could not be created with [%v]", runPath, err)
		return
	}
	stages := []string{"primary", "secondary"}
	if p.serverHost {
		stages = append(stages, "tertiary")
	}
	isLeader := false
	var leaderClient *brokerClient
	if p.serverHost {
		isLeader, leaderClient = electBackupLeader(p.configPath, p.hostName, runID)
		p.powerBackupDisk("ON", runStart)
	}
	scribe.Log(scribe.SourceProbeBackup, scribe.SubjectHost(p.hostName), scribe.ActionStart).Infof("schedule", runStart, "[%s] backup run over [%d] stages", runID, len(stages))
	leaseCancel := context.CancelFunc(func() {})
	if isLeader && leaderClient != nil {
		p.publishClusterStatus(leaderClient, runID, "running", runStart, true, 0, 0)
		var leaseCtx context.Context
		leaseCtx, leaseCancel = context.WithCancel(ctx)
		go func() {
			ticker := time.NewTicker(leaderLeaseRefresh)
			defer ticker.Stop()
			for {
				select {
				case <-leaseCtx.Done():
					return
				case <-ticker.C:
					p.refreshLease(leaderClient, runID)
				}
			}
		}()
	}
	failed, attempted := 0, 0
	for _, stage := range stages {
		attempted++
		if err := p.runStage(ctx, stage, runID, runPath); err != nil {
			failed++
			scribe.Log(scribe.SourceProbeBackup, scribe.SubjectHost(p.hostName), scribe.ActionStart).Warnf("faulting", runStart, "[%s] backup stage failed with [%v], stopping the run", stage, err)
			break
		}
	}
	leaseCancel()
	p.pruneRuns(runStart)
	document := p.writeRunDocument(runPath, runID, attempted, failed, runStart)
	p.publishHostStatus(document)
	p.refresh()
	if isLeader && leaderClient != nil {
		p.finishLeadership(ctx, leaderClient, runID, runStart)
		leaderClient.close()
	}
	scribe.Log(scribe.SourceProbeBackup, scribe.SubjectHost(p.hostName), scribe.ActionStop).Infof("finished", runStart, "[%s] backup run, [%d] of [%d] stages failed", runID, failed, len(stages))
}

func (p *backupProbe) pruneRuns(started time.Time) {
	entries, err := os.ReadDir(p.root)
	if err != nil {
		return
	}
	var runs []string
	for _, entry := range entries {
		if entry.IsDir() && backupRunDirPattern.MatchString(entry.Name()) {
			runs = append(runs, entry.Name())
		}
	}
	if len(runs) <= backupRunsKept {
		return
	}
	sort.Strings(runs)
	pruned := runs[:len(runs)-backupRunsKept]
	for _, run := range pruned {
		if err := os.RemoveAll(filepath.Join(p.root, run)); err != nil {
			scribe.Log(scribe.SourceProbeBackup, scribe.SubjectHost(p.hostName), scribe.ActionRemove).Warnf("faulting", started, "[%s] backup run directory could not be removed with [%v]", run, err)
		}
	}
	scribe.Log(scribe.SourceProbeBackup, scribe.SubjectHost(p.hostName), scribe.ActionRemove).Debugf("expunged", started, "[%d] backup run directories beyond the newest [%d] under [%s]", len(pruned), backupRunsKept, p.root)
}

func (p *backupProbe) runStage(ctx context.Context, stage, runID, runPath string) error {
	if _, err := os.Stat(p.runner); err != nil {
		return fmt.Errorf("stage runner [%s] is absent [%w]", p.runner, err)
	}
	stagePath := filepath.Join(runPath, "stage", stage)
	if err := os.MkdirAll(stagePath, 0o755); err != nil {
		return fmt.Errorf("stage directory [%s] could not be created [%w]", stagePath, err)
	}
	logPath := filepath.Join(stagePath, "output.log")
	logFile, err := os.Create(logPath)
	if err != nil {
		return fmt.Errorf("stage log [%s] could not be created [%w]", logPath, err)
	}
	defer logFile.Close()
	stageCtx := ctx
	if hours := config.Load(p.configPath).BackupTimeoutHours(); hours > 0 {
		var cancel context.CancelFunc
		stageCtx, cancel = context.WithTimeout(ctx, time.Duration(hours)*time.Hour)
		defer cancel()
	}
	command := exec.CommandContext(stageCtx, "bash", p.runner, stage, "start", runID)
	command.Env = append(os.Environ(), "BACKUP_RUN_ID="+runID, "BACKUP_RUN_PATH="+runPath, "BACKUP_RUN_ID_PASSED=1")
	command.Cancel = func() error { return command.Process.Signal(syscall.SIGTERM) }
	command.WaitDelay = backupStageKillGrace
	command.Stdout = logFile
	command.Stderr = logFile
	runErr := command.Run()
	if runErr != nil {
		stop := exec.CommandContext(context.WithoutCancel(ctx), "bash", p.runner, stage, "stop", runID)
		stop.Env = command.Env
		stop.Stdout = logFile
		stop.Stderr = logFile
		_ = stop.Run()
		return fmt.Errorf("stage [%s] exited with [%w]", stage, runErr)
	}
	return nil
}

func (p *backupProbe) writeRunDocument(runPath, runID string, stagesRun, stagesFailed int, started time.Time) backupDocument {
	state := "failed"
	if stagesFailed == 0 {
		state = "complete"
	}
	document := backupDocument{
		RunID:        runID,
		State:        state,
		StartedTS:    started.Format(time.RFC3339),
		FinishedTS:   time.Now().Format(time.RFC3339),
		DurationS:    int(time.Since(started).Seconds()),
		SuccessBool:  stagesFailed == 0,
		StagesRun:    stagesRun,
		StagesFailed: stagesFailed,
	}
	for _, stage := range []string{"primary", "secondary", "tertiary"} {
		staged := readStageDocument(stageStatusPath(runPath, stage))
		if staged == nil {
			continue
		}
		document.FileCount += staged.FileCount
		document.SizeMB += staged.SizeMB
		document.FilesCreated += staged.FilesCreated
		document.FilesDeleted += staged.FilesDeleted
		document.SentMB += staged.SentMB
		if stage == "tertiary" {
			document.DiskUsagePerc = staged.DiskUsagePerc
			document.FilesHeld = staged.FilesHeld
			document.SizeHeldMB = staged.SizeHeldMB
		}
	}
	writeDocumentAtomic(filepath.Join(runPath, "status.json"), document)
	return document
}

func (p *backupProbe) powerBackupDisk(state string, started time.Time) {
	topic := config.Load(p.configPath).BackupCommandTopic()
	if topic == "" {
		return
	}
	client, err := brokerDial(p.configPath, "power")
	if err != nil {
		scribe.Log(scribe.SourceProbeBackup, scribe.SubjectHost(p.hostName), scribe.ActionPublish).Warnf("faulting", started, "[%s] backup disk power [%s] not sent, broker unreachable with [%v]", topic, state, err)
		return
	}
	defer client.close()
	_ = client.publishCommand(topic, state)
}

func (p *backupProbe) refreshLease(client *brokerClient, runID string) {
	payload, _ := json.Marshal(backupLeaseFor(p.hostName, runID))
	_ = client.publishRetained(clusterLeaderTopic, string(payload))
}

func (p *backupProbe) publishClusterStatus(client *brokerClient, runID, state string, started time.Time, powered bool, reported, failed int) {
	expected := backupExpectedServers(p.configPath)
	document := map[string]any{
		"run_id":         runID,
		"state":          state,
		"started_ts":     started.Format(time.RFC3339),
		"duration_s":     int(time.Since(started).Seconds()),
		"success_bool":   state == "complete",
		"power_bool":     powered,
		"hosts_expected": len(expected),
		"hosts_reported": reported,
		"hosts_failed":   failed,
	}
	if state != "running" {
		document["finished_ts"] = time.Now().Format(time.RFC3339)
	}
	payload, _ := json.Marshal(document)
	_ = client.publishRetained(clusterStatusTopic, string(payload))
}

func (p *backupProbe) publishHostStatus(document backupDocument) {
	client, err := brokerDial(p.configPath, "status")
	if err != nil {
		return
	}
	defer client.close()
	payload, _ := json.Marshal(document)
	_ = client.publishRetained("supervisor/"+p.hostName+"/backup/status", string(payload))
}

func (p *backupProbe) finishLeadership(ctx context.Context, client *brokerClient, runID string, started time.Time) {
	expected := backupExpectedServers(p.configPath)
	deadline := time.Now().Add(backupRunCeiling)
	terminal := map[string]bool{"complete": true, "failed": true, "timeout": true}
	reported, failedHosts, timedOut := 0, 0, true
	for time.Now().Before(deadline) {
		reported, failedHosts = 0, 0
		statuses, statusesErr := client.readRetained("supervisor/+/backup/status")
		if statusesErr != nil {
			scribe.Log(scribe.SourceProbeBackup, scribe.SubjectHost(p.hostName), scribe.ActionSubscribe).Warnf("deferred", started, "[%v] reading host statuses, retrying on the next poll", statusesErr)
		}
		for _, host := range expected {
			var document backupDocument
			if json.Unmarshal([]byte(statuses["supervisor/"+host+"/backup/status"]), &document) == nil &&
				document.RunID == runID && terminal[document.State] {
				reported++
				if !document.SuccessBool {
					failedHosts++
				}
			}
		}
		if reported >= len(expected) {
			timedOut = false
			break
		}
		p.refreshLease(client, runID)
		p.publishClusterStatus(client, runID, "running", started, true, reported, failedHosts)
		select {
		case <-ctx.Done():
			return
		case <-time.After(leaderPollInterval):
		}
	}
	terminalState := "complete"
	if timedOut {
		terminalState = "timeout"
	} else if failedHosts > 0 {
		terminalState = "failed"
	}
	if topic := config.Load(p.configPath).BackupCommandTopic(); topic != "" {
		_ = client.publishCommand(topic, "OFF")
		scribe.Log(scribe.SourceProbeBackup, scribe.SubjectHost(p.hostName), scribe.ActionPublish).Infof("released", started, "[%s] backup disk powered down after run [%s]", topic, runID)
	}
	p.publishClusterStatus(client, runID, terminalState, started, false, reported, failedHosts)
	_ = client.publishRetained(clusterLeaderTopic, "")
	scribe.Log(scribe.SourceProbeBackup, scribe.SubjectHost(p.hostName), scribe.ActionRemove).Infof("released", started, "[%s] backup lease cleared, run [%s] ended [%s]", clusterLeaderTopic, runID, terminalState)
}

type backupLease struct {
	Host      string `json:"host"`
	Epoch     int64  `json:"epoch"`
	RunID     string `json:"run_id"`
	ClaimedTS string `json:"claimed_ts"`
	ExpiresTS string `json:"expires_ts"`
}

func (l backupLease) expired() bool {
	expires, err := time.Parse(time.RFC3339, l.ExpiresTS)
	return err != nil || time.Now().After(expires)
}

func backupLeaseFor(host, runID string) backupLease {
	claimed := time.Now()
	return backupLease{
		Host:      host,
		Epoch:     claimed.Unix(),
		RunID:     runID,
		ClaimedTS: claimed.Format(time.RFC3339),
		ExpiresTS: claimed.Add(backupRunCeiling).Format(time.RFC3339),
	}
}

func electBackupLeader(configPath, host, runID string) (bool, *brokerClient) {
	electStart := config.NowIncludingSuspend()
	client, err := brokerHold(configPath, "election", clusterLeaderTopic)
	if err != nil {
		scribe.Log(scribe.SourceProbeBackup, scribe.SubjectHost(host), scribe.ActionConnect).Warnf("faulting", electStart, "[election] could not reach the broker with [%v], running unled", err)
		return false, nil
	}
	existing, existingErr := client.readRetained(clusterLeaderTopic)
	if existingErr != nil {
		scribe.Log(scribe.SourceProbeBackup, scribe.SubjectHost(host), scribe.ActionSubscribe).Warnf("faulting", electStart, "[election] could not read the lease with [%v], running unled", existingErr)
		client.close()
		return false, nil
	}
	if raw, ok := existing[clusterLeaderTopic]; ok && strings.TrimSpace(raw) != "" {
		var lease backupLease
		if json.Unmarshal([]byte(raw), &lease) == nil && !lease.expired() && lease.Host != host {
			scribe.Log(scribe.SourceProbeBackup, scribe.SubjectHost(host), scribe.ActionConnect).Infof("deferred", electStart, "[%s] holds the backup lease until [%s]", lease.Host, lease.ExpiresTS)
			client.close()
			return false, nil
		}
	}
	payload, _ := json.Marshal(backupLeaseFor(host, runID))
	if err := client.publishRetained(clusterLeaderTopic, string(payload)); err != nil {
		scribe.Log(scribe.SourceProbeBackup, scribe.SubjectHost(host), scribe.ActionPublish).Warnf("faulting", electStart, "[election] claim failed with [%v], running unled", err)
		client.close()
		return false, nil
	}
	confirmed, confirmedErr := client.readRetained(clusterLeaderTopic)
	if confirmedErr != nil {
		scribe.Log(scribe.SourceProbeBackup, scribe.SubjectHost(host), scribe.ActionSubscribe).Warnf("faulting", electStart, "[election] could not confirm the lease with [%v], running unled", confirmedErr)
		client.close()
		return false, nil
	}
	var winner backupLease
	if json.Unmarshal([]byte(confirmed[clusterLeaderTopic]), &winner) == nil && winner.Host == host {
		scribe.Log(scribe.SourceProbeBackup, scribe.SubjectHost(host), scribe.ActionRegister).Infof("assigned", electStart, "[%s] won the backup lease for run [%s]", host, runID)
		return true, client
	}
	scribe.Log(scribe.SourceProbeBackup, scribe.SubjectHost(host), scribe.ActionConnect).Infof("deferred", electStart, "[%s] won the backup lease, yielding", winner.Host)
	client.close()
	return false, nil
}

func backupExpectedServers(configPath string) []string {
	var servers []string
	loaded := config.Load(configPath)
	for _, host := range loaded.Hosts() {
		if _, hasIndex := loaded.HostIndex(host); hasIndex {
			servers = append(servers, host)
		}
	}
	sort.Strings(servers)
	return servers
}

type backupDocument struct {
	RunID         string  `json:"run_id"`
	State         string  `json:"state"`
	Trigger       string  `json:"trigger,omitempty"`
	StartedTS     string  `json:"started_ts,omitempty"`
	FinishedTS    string  `json:"finished_ts,omitempty"`
	ExpiresTS     string  `json:"expires_ts,omitempty"`
	DurationS     int     `json:"duration_s,omitempty"`
	SuccessBool   bool    `json:"success_bool"`
	DiskUsagePerc float64 `json:"disk_usage_perc,omitempty"`
	FileCount     int     `json:"file_count,omitempty"`
	SizeMB        int     `json:"size_mb,omitempty"`
	FilesHeld     int     `json:"files_held,omitempty"`
	FilesCreated  int     `json:"files_created,omitempty"`
	FilesDeleted  int     `json:"files_deleted,omitempty"`
	SizeHeldMB    int     `json:"size_held_mb,omitempty"`
	SentMB        int     `json:"sent_mb,omitempty"`
	StagesRun     int     `json:"stages_run,omitempty"`
	StagesFailed  int     `json:"stages_failed,omitempty"`
}

type backupSnapshot struct {
	dir      string
	at       time.Time
	running  bool
	host     *backupDocument
	tertiary *backupDocument
	services map[string]bool
}

func (s *backupSnapshot) age() time.Duration {
	if s == nil || s.at.IsZero() {
		return backupStaleWindow * 100
	}
	return config.SinceIncludingSuspend(s.at)
}

func readNewestRun(root string) *backupSnapshot {
	entries, err := os.ReadDir(root)
	if err != nil {
		return nil
	}
	var runs []string
	for _, entry := range entries {
		if entry.IsDir() && backupRunDirPattern.MatchString(entry.Name()) {
			runs = append(runs, entry.Name())
		}
	}
	if len(runs) == 0 {
		return nil
	}
	sort.Strings(runs)
	dir := runs[len(runs)-1]
	at, _ := time.ParseInLocation(backupRunStamp, dir, time.Local)
	snapshot := &backupSnapshot{dir: dir, at: at, services: map[string]bool{}}
	runPath := filepath.Join(root, dir)
	snapshot.host = readStageDocument(filepath.Join(runPath, "status.json"))
	snapshot.tertiary = readStageDocument(stageStatusPath(runPath, "tertiary"))
	staged, _ := filepath.Glob(filepath.Join(runPath, "stage", "*", "status.json"))
	snapshot.running = snapshot.host == nil && len(staged) > 0 && snapshot.age() <= backupRunCeiling
	documents, _ := filepath.Glob(filepath.Join(runPath, "stage", "primary", "service", "*", "status.json"))
	for _, path := range documents {
		if document := readStageDocument(path); document != nil {
			snapshot.services[filepath.Base(filepath.Dir(path))] = document.SuccessBool
		}
	}
	return snapshot
}

func stageStatusPath(runPath, stage string) string {
	return filepath.Join(runPath, "stage", stage, "status.json")
}

func readStageDocument(path string) *backupDocument {
	data, err := os.ReadFile(path)
	if err != nil {
		return nil
	}
	var document backupDocument
	if json.Unmarshal(data, &document) != nil {
		return nil
	}
	return &document
}

func writeDocumentAtomic(path string, document backupDocument) {
	data, err := json.MarshalIndent(document, "", "  ")
	if err != nil {
		return
	}
	temporary := path + ".tmp"
	if os.WriteFile(temporary, data, 0o644) != nil {
		return
	}
	_ = os.Rename(temporary, path)
}

const (
	backupRunRoot        = "/home/asystem/supervisor/backup"
	backupRunner         = "/asystem/etc/backup.sh"
	backupRunStamp       = "2006-01-02_15-04-05"
	backupRunCeiling     = 5 * time.Hour
	backupStaleWindow    = 24*time.Hour + backupRunCeiling
	backupStageKillGrace = 2 * time.Minute
	leaderPollInterval   = 30 * time.Second
	leaderLeaseRefresh   = 15 * time.Minute
	backupRunsKept       = 30
	backupScheduledHour  = 1
	reaperIdleTicks      = 2

	clusterLeaderTopic = "supervisor/cluster-all/backup/leader"
	clusterStatusTopic = "supervisor/cluster-all/backup/status"
)

var (
	backupProbeInstance *backupProbe

	backupRunDirPattern = regexp.MustCompile(`^\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}$`)
)
