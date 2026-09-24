package probe

import (
	"context"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"slices"
	"sort"
	"strings"
	"supervisor/internal/config"
	"supervisor/internal/metric"
	"supervisor/internal/scribe"
	"supervisor/internal/stats"
	"sync"
	"sync/atomic"
	"time"
)

type backupProbe struct {
	cache      *metric.RecordCache
	mask       [metric.MetricMax]bool
	configPath string
	hostName   string
	serverHost bool
	stages     []metric.BackupStage
	root       string

	failedBackupStagesInt *stats.IntStats
	haltedBackupStagesInt *stats.IntStats
	usedBackupSpaceInt    *stats.IntStats

	snapshotMu    sync.Mutex
	snapshot      *backupSnapshot
	snapshotPrint string
	backupRunning sync.Mutex
	backupActive  atomic.Bool
	reapRunning   sync.Mutex
	leadRunning   sync.Mutex
	leadWatch     *brokerWatcher
	leadStale     int
	reapIdle      int
	reapNotice    int
	reapStale     int
	reapArming    bool
	reapPaused    bool
	reapWatch     *brokerWatcher
}

func newBackupProbe() *backupProbe {
	backupProbeInstance = &backupProbe{root: backupRunRoot()}
	return backupProbeInstance
}

func (*backupProbe) subject() scribe.Subject { return scribe.SubjectHost("") }

func (*backupProbe) dormant() bool { return false }

func (p *backupProbe) metrics() []metric.ID {
	return []metric.ID{metric.MetricHostHaltedBackupStages, metric.MetricHostFailedBackupStages, metric.MetricHostUsedBackupSpace}
}

func (p *backupProbe) gates() []metric.GateID { return nil }

func (p *backupProbe) duties() []string {
	return []string{metric.LeaderDutyBackup}
}

func (p *backupProbe) create(configPath string, cache *metric.RecordCache, mask [metric.MetricMax]bool, periods config.Periods) error {
	p.cache = cache
	p.mask = mask
	p.configPath = configPath
	loaded := config.Load(configPath)
	p.hostName = loaded.Host()
	createStart := config.NowIncludingSuspend()
	p.stages = backupStagesOf(loaded.HostStages(p.hostName))
	if len(p.stages) == 0 {
		p.stages = []metric.BackupStage{metric.BackupStagePrimary, metric.BackupStageSecondary}
		scribe.Log(scribe.SourceProbeBackup, scribe.SubjectHost(p.hostName), scribe.ActionStart).Warnf("faulting", createStart,
			"[%s] declares no backup stages, assuming [%s]", p.configPath, backupStagesNamed(p.stages))
	}
	p.serverHost = slices.Contains(p.stages, metric.BackupStageTertiary)
	p.failedBackupStagesInt = stats.NewIntStats(periods.TrendHours, float64(periods.PulseMillis)/1000.0, float64(periods.PollMillis)/1000.0)
	p.haltedBackupStagesInt = stats.NewIntStats(periods.TrendHours, float64(periods.PulseMillis)/1000.0, float64(periods.PollMillis)/1000.0)
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
			metric.MetricHostHaltedBackupStages,
			metric.ServiceNameUnset,
			p.haltedBackupStages,
			p.haltedBackupStagesInt,
			func() int8 { return p.haltedBackupStagesInt.PulseMax() },
			func() int8 { return p.haltedBackupStagesInt.TrendMax() },
		),
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
	if snapshot != nil && snapshot.abandoned {
		return 100, derivedf(scribe.ActionCompute, "computed [100] pct failed, scheduled run [%s] started [%s] ago wrote no roll-up and stopped reporting past the [%s] ceiling, so every stage it owns is unaccounted for",
			snapshot.dir, snapshot.age().Round(time.Minute), backupRunCeiling), nil
	}
	if snapshot != nil && snapshot.running {
		return 0, derivedInertf(scribe.ActionCompute, "computed [0] pct failed, run [%s] started [%s] ago has not written its roll-up yet so the metric is inert and always ok",
			snapshot.dir, snapshot.age().Round(time.Minute)), nil
	}
	if snapshot == nil || snapshot.host == nil || snapshot.age() > backupStaleWindow {
		if !p.everRolled() {
			return 0, derivation{}, fmt.Errorf("no backup verdict, no scheduled run has ever rolled up under [%s], so no stage ratio can be computed [%w]", p.root, errEnvironment)
		}
		return 100, derivedf(scribe.ActionCompute, "computed [100] pct failed, no run directory under [%s] holds a status document inside the [%s] window",
			p.root, backupStaleWindow), nil
	}
	run := max(snapshot.host.StagesRun, 1)
	value := percentValue(float64(snapshot.host.StagesFailed) / float64(run) * 100.0)
	return value, derivedf(scribe.ActionCompute, "computed [%d] pct failed, run [%s] aged [%s] reported [%d] of [%d] stages failed",
		value, snapshot.dir, snapshot.age().Round(time.Minute), snapshot.host.StagesFailed, run), nil
}

func (p *backupProbe) everRolled() bool {
	rolled, _ := filepath.Glob(statusPath(backupRunPath(p.root, "*")))
	return len(rolled) > 0
}

func (p *backupProbe) haltedBackupStages() (int8, derivation, error) {
	snapshot := p.documents()
	if snapshot != nil && snapshot.running {
		return 0, derivedInertf(scribe.ActionCompute, "computed [0] pct halted, run [%s] started [%s] ago has not written its roll-up yet so the metric is inert and always ok",
			snapshot.dir, snapshot.age().Round(time.Minute)), nil
	}
	if snapshot == nil || snapshot.host == nil || snapshot.age() > backupStaleWindow {
		return 0, derivedInertf(scribe.ActionCompute, "computed [0] pct halted, no run directory under [%s] holds a status document inside the [%s] window so the metric is inert and always ok",
			p.root, backupStaleWindow), nil
	}
	run := max(snapshot.host.StagesRun, 1)
	value := percentValue(float64(snapshot.host.StagesHalted) / float64(run) * 100.0)
	return value, derivedf(scribe.ActionCompute, "computed [%d] pct halted, run [%s] aged [%s] reported [%d] of [%d] stages halted by a stop or a timeout",
		value, snapshot.dir, snapshot.age().Round(time.Minute), snapshot.host.StagesHalted, run), nil
}

func (p *backupProbe) usedBackupSpace() (int8, derivation, error) {
	snapshot := p.documents()
	if snapshot == nil || snapshot.tertiary == nil || snapshot.tertiary.State == metric.BackupStateRunning {
		if !p.serverHost {
			return 0, derivedInertf(scribe.ActionCompute, "computed [0] pct used, host [%s] owns no share index so it runs no tertiary stage and holds no backup disk, so the metric is inert and always ok", p.hostName), nil
		}
		if snapshot != nil && snapshot.running {
			return 0, derivedInertf(scribe.ActionCompute, "computed [0] pct used, run [%s] started [%s] ago has not measured the backup disk yet so the metric is inert and always ok",
				snapshot.dir, snapshot.age().Round(time.Minute)), nil
		}
		if snapshot != nil && snapshot.abandoned {
			return 0, derivation{}, fmt.Errorf("no backup volume reading, scheduled run [%s] stopped reporting [%s] ago so its last disk usage cannot be trusted [%w]", snapshot.dir, snapshot.age().Round(time.Minute), errEnvironment)
		}
		return 0, derivation{}, fmt.Errorf("no backup volume reading, this host has written no tertiary stage document under [%s] [%w]", p.root, errEnvironment)
	}
	value := percentValue(snapshot.tertiary.DiskUsagePerc)
	return value, derivedf(scribe.ActionCompute, "computed [%d] pct used, tertiary stage of run [%s] aged [%s] measured [%.1f] pct disk usage on /backup",
		value, snapshot.dir, snapshot.age().Round(time.Minute), snapshot.tertiary.DiskUsagePerc), nil
}

func (p *backupProbe) serviceSuccess(service string) (bool, bool, string) {
	snapshot := p.documents()
	if snapshot == nil || snapshot.age() > backupStaleWindow {
		return false, false, ""
	}
	success, found := snapshot.services[service]
	return success, found, snapshot.dir
}

func (p *backupProbe) armReaper(started time.Time) bool {
	p.reapArming = true
	client, err := brokerDial(p.configPath, "manual")
	if err != nil {
		scribe.Log(scribe.SourceProbeBackup, scribe.SubjectHost(p.hostName), scribe.ActionPublish).Warnf("faulting", started, "[%v] arming [%s], retrying on every reaper tick until it is reached", err, allReaperTopic)
		return false
	}
	defer client.close()
	armed, _ := json.Marshal(backupReaperSummary{State: metric.CommandOn})
	if err := client.publishRetained(allReaperTopic, string(armed)); err != nil {
		scribe.Log(scribe.SourceProbeBackup, scribe.SubjectHost(p.hostName), scribe.ActionPublish).Warnf("faulting", started, "[%v] arming [%s], retrying on every reaper tick until it is reached", err, allReaperTopic)
		return false
	}
	p.reapArming = false
	p.reapNotice = 0
	scribe.Log(scribe.SourceProbeBackup, scribe.SubjectHost(p.hostName), scribe.ActionPublish).Infof("released", started, "[%s] armed, the backup disk is powered down again when nothing needs it", allReaperTopic)
	return true
}

func (p *backupProbe) reapQuiet() bool {
	p.reapIdle = 0
	p.reapNotice++
	if p.reapNotice < reaperNoticeTicks {
		return false
	}
	p.reapNotice = 0
	return true
}

func (p *backupProbe) reap(ctx context.Context) {
	if !p.reapRunning.TryLock() {
		return
	}
	defer p.reapRunning.Unlock()
	if snapshot := readNewestRun(p.root); snapshot != nil {
		p.reapLocalStale(ctx, snapshot)
	}
	if !p.serverHost {
		return
	}
	reapStart := config.NowIncludingSuspend()
	loaded := config.Load(p.configPath)
	if p.backupActive.Load() {
		return
	}
	commandTopic, stateTopic := loaded.BackupCommandTopic(), loaded.BackupStateTopic()
	if commandTopic == "" || stateTopic == "" {
		return
	}
	if p.reapWatch == nil {
		watch, err := brokerWatch(p.configPath, p.hostName, stateTopic, allBackupStatusTopic, allReaperTopic, metric.TopicBackupStage(anyHost, metric.BackupStageTertiary))
		if err != nil {
			scribe.Log(scribe.SourceProbeBackup, scribe.SubjectHost(p.hostName), scribe.ActionConnect).Warnf("faulting", reapStart, "[%v] watching the cluster, retrying on the next tick", err)
			return
		}
		p.reapWatch = watch
	}
	retained, watching := p.reapWatch.readRetained()
	if !watching {
		p.reapIdle = 0
		p.reapStale++
		if p.reapStale >= reaperStaleTicks {
			p.reapStale = 0
			p.reapWatch.close()
			p.reapWatch = nil
			scribe.Log(scribe.SourceProbeBackup, scribe.SubjectHost(p.hostName), scribe.ActionConnect).Warnf("faulting", reapStart,
				"[%d] ticks with nothing watched, redialling the cluster watch", reaperStaleTicks)
		}
		return
	}
	p.reapStale = 0
	flag, declared := retained[allReaperTopic]
	var reaper backupReaperSummary
	if declared {
		_ = json.Unmarshal([]byte(flag), &reaper)
	}
	switch {
	case !declared:
		scribe.Log(scribe.SourceProbeBackup, scribe.SubjectHost(p.hostName), scribe.ActionPublish).Infof("restored", reapStart,
			"[%s] is absent, asserting the armed default the broker no longer carries", allReaperTopic)
		p.armReaper(reapStart)
	case strings.EqualFold(strings.TrimSpace(reaper.State), metric.CommandOff) && !reaper.Paused():
		scribe.Log(scribe.SourceProbeBackup, scribe.SubjectHost(p.hostName), scribe.ActionPublish).Infof("restored", reapStart,
			"[%s] paused until [%s], which has passed, arming it again", allReaperTopic, reaper.ExpiresTS)
		p.armReaper(reapStart)
	case p.reapArming:
		p.armReaper(reapStart)
	}
	if paused := reaper.Paused(); paused != p.reapPaused {
		p.reapPaused = paused
		if paused {
			scribe.Log(scribe.SourceProbeBackup, scribe.SubjectHost(p.hostName), scribe.ActionStop).Infof("excluded", reapStart,
				"[%s] is off until [%s], the backup disk stays powered", allReaperTopic, reaper.ExpiresTS)
		} else {
			scribe.Log(scribe.SourceProbeBackup, scribe.SubjectHost(p.hostName), scribe.ActionStart).Infof("restored", reapStart,
				"[%s] is on, the backup disk is powered down again when nothing needs it", allReaperTopic)
		}
	}
	if p.reapPaused {
		if p.reapQuiet() {
			scribe.Log(scribe.SourceProbeBackup, scribe.SubjectHost(p.hostName), scribe.ActionStop).Infof("deferred", reapStart,
				"[%s] is still off until [%s], the backup disk stays powered", allReaperTopic, reaper.ExpiresTS)
		}
		return
	}
	if !strings.EqualFold(strings.TrimSpace(retained[stateTopic]), metric.CommandOn) {
		if p.reapQuiet() {
			scribe.Log(scribe.SourceProbeBackup, scribe.SubjectHost(p.hostName), scribe.ActionStop).Infof("deferred", reapStart,
				"[%s] does not report the disk on, so there is nothing to power down", stateTopic)
		}
		return
	}
	var coordinated backupSummary
	if json.Unmarshal([]byte(retained[allBackupStatusTopic]), &coordinated) == nil && coordinated.State == metric.BackupStateRunning {
		if started, perr := time.Parse(time.RFC3339, coordinated.StartedTS); perr == nil && time.Since(started) < backupRunCeiling {
			if p.reapQuiet() {
				scribe.Log(scribe.SourceProbeBackup, scribe.SubjectHost(p.hostName), scribe.ActionStop).Infof("deferred", reapStart,
					"[%s] reports a run started [%s] still coordinating, leaving the disk powered", allBackupStatusTopic, coordinated.StartedTS)
			}
			return
		}
	}
	for topic, payload := range retained {
		if !strings.HasSuffix(topic, tertiaryStatusSuffix) {
			continue
		}
		var document backupSummary
		if json.Unmarshal([]byte(payload), &document) != nil || document.State != metric.BackupStateRunning || document.ExpiresTS == "" {
			continue
		}
		if expires, perr := time.Parse(time.RFC3339, document.ExpiresTS); perr == nil && time.Now().Before(expires) {
			if p.reapQuiet() {
				scribe.Log(scribe.SourceProbeBackup, scribe.SubjectHost(p.hostName), scribe.ActionStop).Infof("deferred", reapStart,
					"[%s] still reports a tertiary stage running, leaving the disk powered", topic)
			}
			return
		}
	}
	p.reapIdle++
	if p.reapIdle < reaperIdleTicks {
		return
	}
	p.reapIdle = reaperIdleTicks
	if leading, _ := Leading(metric.LeaderDutyBackup); !leading {
		if p.reapQuiet() {
			scribe.Log(scribe.SourceProbeBackup, scribe.SubjectHost(p.hostName), scribe.ActionStop).Infof("deferred", reapStart,
				"[%s] duty is not held by this host, leaving the power down to its leader", metric.LeaderDutyBackup)
		}
		return
	}
	client, err := brokerDial(p.configPath, "reaper")
	if err != nil {
		scribe.Log(scribe.SourceProbeBackup, scribe.SubjectHost(p.hostName), scribe.ActionConnect).Warnf("faulting", reapStart,
			"[%v] reaching the broker to power down [%s], retrying on the next tick", err, commandTopic)
		return
	}
	defer client.close()
	if leading, _ := Leading(metric.LeaderDutyBackup); !leading {
		return
	}
	if err := client.publishCommand(commandTopic, metric.CommandOff); err != nil {
		scribe.Log(scribe.SourceProbeBackup, scribe.SubjectHost(p.hostName), scribe.ActionPublish).Warnf("faulting", reapStart,
			"[%v] powering down [%s], retrying on the next tick", err, commandTopic)
		return
	}
	p.reapIdle = 0
	p.reapNotice = 0
	scribe.Log(scribe.SourceProbeBackup, scribe.SubjectHost(p.hostName), scribe.ActionPublish).Infof("released", reapStart, "[%s] backup disk powered down, no tertiary stage running for [%d] ticks", commandTopic, reaperIdleTicks)
}

func (p *backupProbe) reapLocalStale(ctx context.Context, snapshot *backupSnapshot) {
	reaped := false
	runPath := filepath.Join(p.root, snapshot.dir)
	for _, stage := range backupStages {
		document := snapshot.stages[stage]
		if document == nil || document.State != metric.BackupStateRunning || document.ExpiresTS == "" {
			continue
		}
		expires, err := time.Parse(time.RFC3339, document.ExpiresTS)
		if err != nil || time.Now().Before(expires) {
			continue
		}
		staleStart := config.NowIncludingSuspend()
		scribe.Log(scribe.SourceProbeBackup, scribe.SubjectHost(p.hostName), scribe.ActionStop).Warnf("faulting", staleStart, "[%-9s] stage of run [%s] still running with liveness expired at [%s], stopping it", stage, snapshot.dir, document.ExpiresTS)
		stopCtx, stopCancel := context.WithTimeout(context.WithoutCancel(ctx), backupStopDeadline)
		stopErr := stopStage(stopCtx, stageRequest{Stage: stage, RunID: snapshot.dir, RunPath: runPath, ConfigPath: p.configPath})
		stopCancel()
		if stopErr != nil {
			scribe.Log(scribe.SourceProbeBackup, scribe.SubjectHost(p.hostName), scribe.ActionStop).Warnf("faulting", staleStart, "[%-9s] stage of run [%s] did not stop within [%s], abandoning it with [%v]", stage, snapshot.dir, backupStopDeadline, stopErr)
		}
		stale := haltedStage(*document, metric.BackupStateTimeout)
		_ = writeAtomic(stageStatusPath(runPath, stage), stale)
		publishStageStatus(p.configPath, stage, stale)
		reaped = true
	}
	if reaped {
		p.refresh()
	}
}

func (p *backupProbe) documents() *backupSnapshot {
	p.snapshotMu.Lock()
	defer p.snapshotMu.Unlock()
	printed := p.fingerprint()
	if p.snapshot != nil && printed == p.snapshotPrint {
		return p.snapshot
	}
	p.snapshot = readNewestRun(p.root)
	p.snapshotPrint = printed
	return p.snapshot
}

func (p *backupProbe) fingerprint() string {
	runs := backupRuns(p.root)
	if len(runs) == 0 {
		return ""
	}
	newest := runs[len(runs)-1]
	runPath := backupRunPath(p.root, newest)
	paths := []string{statusPath(runPath)}
	for _, stage := range backupStages {
		paths = append(paths, stageStatusPath(runPath, stage))
	}
	marks := []string{newest}
	for _, path := range paths {
		info, err := os.Stat(path)
		if err != nil {
			marks = append(marks, "-")
			continue
		}
		marks = append(marks, info.ModTime().UTC().Format(time.RFC3339Nano))
	}
	return strings.Join(marks, "/")
}

func (p *backupProbe) refresh() {
	p.snapshotMu.Lock()
	p.snapshot = nil
	p.snapshotMu.Unlock()
}

func (p *backupProbe) cycle(ctx context.Context, hour int, isHour bool) {
	p.lead()
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
	p.armReaper(runStart)
	if p.serverHost {
		if err := powerBackupDisk(p.configPath, metric.CommandOn); err != nil {
			scribe.Log(scribe.SourceProbeBackup, scribe.SubjectHost(p.hostName), scribe.ActionPublish).Warnf("faulting", runStart,
				"[%v] powering the backup disk on, the run mounts it anyway in case it is already powered", err)
		}
	}
	request := BackupRequest{Command: BackupCommandStart, Trigger: metric.BackupTriggerSystem, Config: p.configPath}
	if err := Backup(ctx, request); err != nil {
		scribe.Log(scribe.SourceProbeBackup, scribe.SubjectHost(p.hostName), scribe.ActionStop).Warnf("faulting", runStart, "[%v] scheduled backup run did not complete cleanly", err)
	}
	p.refresh()
}

func (p *backupProbe) lead() {
	if !p.serverHost || !p.leadRunning.TryLock() {
		return
	}
	defer p.leadRunning.Unlock()
	leading, epoch := Leading(metric.LeaderDutyBackup)
	if !leading {
		if p.leadWatch != nil {
			p.leadWatch.close()
			p.leadWatch = nil
			p.leadStale = 0
		}
		return
	}
	leadStart := time.Now()
	if p.leadWatch == nil {
		watch, err := brokerWatch(p.configPath, p.hostName, metric.TopicBackupStatus(anyHost), metric.TopicBackupStage(anyHost, anyLevel), allBackupStatusTopic)
		if err != nil {
			scribe.Log(scribe.SourceProbeBackup, scribe.SubjectHost(p.hostName), scribe.ActionConnect).Warnf("deferred", leadStart, "[%v] watching the cluster backup run, retrying on the next tick", err)
			return
		}
		p.leadWatch = watch
	}
	retained, watching := p.leadWatch.readRetained()
	if !watching {
		p.leadStale++
		if p.leadStale >= reaperStaleTicks {
			p.leadStale = 0
			p.leadWatch.close()
			p.leadWatch = nil
			scribe.Log(scribe.SourceProbeBackup, scribe.SubjectHost(p.hostName), scribe.ActionConnect).Warnf("faulting", leadStart, "[%d] ticks with the cluster backup run unwatched, redialling", reaperStaleTicks)
		}
		return
	}
	p.leadStale = 0
	expected := backupExpectedServers(p.configPath)
	decision := backupClusterRunDecision(retained, expected, time.Now())
	if decision.action == backupClusterRunIdle {
		return
	}
	client, err := brokerDial(p.configPath, "coordinate")
	if err != nil {
		scribe.Log(scribe.SourceProbeBackup, scribe.SubjectHost(p.hostName), scribe.ActionConnect).Warnf("deferred", leadStart, "[%v] reaching the broker to coordinate the cluster backup run, retrying on the next tick", err)
		return
	}
	defer client.close()
	if leading, current := Leading(metric.LeaderDutyBackup); !leading || current != epoch {
		return
	}
	if decision.action == backupClusterRunClose {
		if topic := config.Load(p.configPath).BackupCommandTopic(); topic != "" {
			if err := client.publishCommand(topic, metric.CommandOff); err != nil {
				scribe.Log(scribe.SourceProbeBackup, scribe.SubjectHost(p.hostName), scribe.ActionPublish).Warnf("faulting", leadStart, "[%v] powering down [%s], retrying on the next tick", err, topic)
				return
			}
		}
	}
	document := backupClusterSummary{
		RunID:         decision.started.Format(backupTimestampFormat),
		State:         decision.state,
		StartedTS:     decision.started.Format(time.RFC3339),
		DurationS:     int(time.Since(decision.started).Seconds()),
		SuccessBool:   decision.state == metric.BackupStateSuccess,
		PowerBool:     decision.action != backupClusterRunClose,
		HostsExpected: len(expected),
		HostsReported: decision.reported,
		HostsFailed:   decision.failed,
		LeaderHost:    p.hostName,
		LeaderEpoch:   epoch,
	}
	if decision.action == backupClusterRunClose {
		document.FinishedTS = time.Now().Format(time.RFC3339)
	}
	payload, _ := json.Marshal(document)
	if err := client.publishRetained(allBackupStatusTopic, string(payload)); err != nil {
		scribe.Log(scribe.SourceProbeBackup, scribe.SubjectHost(p.hostName), scribe.ActionPublish).Warnf("faulting", leadStart, "[%v] publishing the [%s] cluster backup run, retrying on the next tick", err, decision.state)
		return
	}
	switch decision.action {
	case backupClusterRunOpen:
		scribe.Log(scribe.SourceProbeBackup, scribe.SubjectHost(p.hostName), scribe.ActionRegister).Infof("assigned", leadStart, "[%s] cluster backup run opened at epoch [%d], [%d] of [%d] hosts reported", decision.started.Format(time.RFC3339), epoch, decision.reported, len(expected))
	case backupClusterRunClose:
		scribe.Log(scribe.SourceProbeBackup, scribe.SubjectHost(p.hostName), scribe.ActionStop).Infof("finished", leadStart, "[%s] cluster backup run closed as [%s], disk powered down, [%d] of [%d] hosts reported", decision.started.Format(time.RFC3339), decision.state, decision.reported, len(expected))
	}
}

type backupClusterRunAction int

type backupClusterRun struct {
	action   backupClusterRunAction
	state    string
	started  time.Time
	reported int
	failed   int
}

func backupClusterRunDecision(retained map[string]string, expected []string, now time.Time) backupClusterRun {
	var clusterRun backupSummary
	clusterRunStarted := time.Time{}
	if json.Unmarshal([]byte(retained[allBackupStatusTopic]), &clusterRun) == nil {
		clusterRunStarted, _ = time.Parse(time.RFC3339, clusterRun.StartedTS)
	}
	decision := backupClusterRun{action: backupClusterRunIdle}
	switch {
	case clusterRun.State == metric.BackupStateRunning && !clusterRunStarted.IsZero():
		decision.action, decision.started = backupClusterRunRefresh, clusterRunStarted
	default:
		for _, host := range expected {
			prefix := metric.TopicBackupStagePrefix(host)
			for topic, payload := range retained {
				stage, found := strings.CutPrefix(topic, prefix)
				if !found || strings.Count(stage, "/") != 1 || !strings.HasSuffix(stage, "/status") {
					continue
				}
				var document backupSummary
				if json.Unmarshal([]byte(payload), &document) != nil || document.State != metric.BackupStateRunning || document.Trigger != metric.BackupTriggerSystem {
					continue
				}
				expires, expiresErr := time.Parse(time.RFC3339, document.ExpiresTS)
				if expiresErr != nil || !now.Before(expires) {
					continue
				}
				started, startedOK := runStarted(document)
				if !startedOK || now.Sub(started) > backupRunCeiling || (!clusterRunStarted.IsZero() && !started.After(clusterRunStarted.Add(backupRunSkew))) {
					continue
				}
				if decision.started.IsZero() || started.Before(decision.started) {
					decision.action, decision.started = backupClusterRunOpen, started
				}
			}
		}
	}
	if decision.action == backupClusterRunIdle {
		return decision
	}
	earliest := decision.started.Add(-backupRunSkew)
	for _, host := range expected {
		var document backupSummary
		if json.Unmarshal([]byte(retained[metric.TopicBackupStatus(host)]), &document) == nil &&
			backupTerminal(document.State) && reportedForRun(document, earliest) {
			decision.reported++
			if !document.SuccessBool {
				decision.failed++
			}
		}
	}
	decision.state = metric.BackupStateRunning
	switch {
	case decision.reported >= len(expected) && decision.failed > 0:
		decision.action, decision.state = backupClusterRunClose, metric.BackupStateFailure
	case decision.reported >= len(expected):
		decision.action, decision.state = backupClusterRunClose, metric.BackupStateSuccess
	case now.Sub(decision.started) > backupRunCeiling:
		decision.action, decision.state = backupClusterRunClose, metric.BackupStateTimeout
	}
	return decision
}

func backupExpectedServers(configPath string) []string {
	var servers []string
	loaded := config.Load(configPath)
	for _, host := range loaded.Hosts() {
		if slices.Contains(backupStagesOf(loaded.HostStages(host)), metric.BackupStageTertiary) {
			servers = append(servers, host)
		}
	}
	sort.Strings(servers)
	return servers
}

func readNewestRun(root string) *backupSnapshot {
	runs := backupRuns(root)
	if len(runs) == 0 {
		return nil
	}
	newest := readBackupRun(root, runs[len(runs)-1])
	started := newest.host == nil && newest.staged > 0
	newest.running = started && newest.age() <= backupRunCeiling
	newest.abandoned = started && !newest.running && newest.trigger == metric.BackupTriggerSystem
	if newest.host != nil || newest.abandoned {
		return newest
	}
	for index := len(runs) - 2; index >= 0; index-- {
		candidate := readBackupRun(root, runs[index])
		if candidate.age() > backupStaleWindow {
			break
		}
		if candidate.host != nil {
			return candidate
		}
	}
	return newest
}

const (
	backupRunCeiling   = 5 * time.Hour
	backupStaleWindow  = 24*time.Hour + backupRunCeiling
	backupStopDeadline = 10 * time.Minute
	backupRunSkew      = 10 * time.Minute
	reaperIdleTicks    = 2
	reaperNoticeTicks  = 15
	reaperStaleTicks   = 5
)

const (
	anyHost  = "+"
	anyLevel = "+"
)

const (
	backupClusterRunIdle backupClusterRunAction = iota
	backupClusterRunOpen
	backupClusterRunRefresh
	backupClusterRunClose
)

var (
	backupProbeInstance *backupProbe

	allReaperTopic       = metric.TopicBackupReaper()
	allBackupStatusTopic = metric.TopicBackupStatus(metric.HostAll)
	tertiaryStatusSuffix = strings.TrimPrefix(metric.TopicBackupStage(anyHost, metric.BackupStageTertiary), metric.TopicBackupRoot(anyHost))
)
