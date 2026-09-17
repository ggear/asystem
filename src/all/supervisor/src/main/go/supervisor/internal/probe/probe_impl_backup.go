package probe

import (
	"context"
	"encoding/json"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"regexp"
	"slices"
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
	stages     []string
	root       string
	runner     string

	failedBackupStagesInt *stats.IntStats
	haltedBackupStagesInt *stats.IntStats
	usedBackupSpaceInt    *stats.IntStats

	snapshotMu      sync.Mutex
	snapshot        *backupSnapshot
	snapshotTakenAt time.Time
	snapshotPrint   string
	backupRunning   sync.Mutex
	backupActive    atomic.Bool
	reapRunning     sync.Mutex
	leadRunning     sync.Mutex
	leadWatch       *brokerWatcher
	leadStale       int
	reapIdle        int
	reapNotice      int
	reapStale       int
	reapArming      bool
	reapPaused      bool
	reapWatch       *brokerWatcher
}

func newBackupProbe() *backupProbe {
	backupProbeInstance = &backupProbe{root: backupRunRoot, runner: backupRunner}
	return backupProbeInstance
}

func (*backupProbe) subject() scribe.Subject { return scribe.SubjectHost("") }

func (*backupProbe) dormant() bool { return false }

func (p *backupProbe) metrics() []metric.ID {
	return []metric.ID{metric.MetricHostHaltedBackupStages, metric.MetricHostFailedBackupStages, metric.MetricHostUsedBackupSpace}
}

func (p *backupProbe) gates() []metric.GateID { return nil }

func (p *backupProbe) campaigns() []leaderRole {
	if !p.serverHost {
		return nil
	}
	return []leaderRole{{name: metric.LeaderRoleBackup, eligible: func() []string { return backupExpectedServers(p.configPath) }}}
}

func (p *backupProbe) create(configPath string, cache *metric.RecordCache, mask [metric.MetricMax]bool, periods config.Periods) error {
	p.cache = cache
	p.mask = mask
	p.periods = periods
	p.configPath = configPath
	loaded := config.Load(configPath)
	p.hostName = loaded.Host()
	createStart := config.NowIncludingSuspend()
	p.stages = loaded.HostStages(p.hostName)
	if len(p.stages) == 0 {
		p.stages = backupStages[:2]
		scribe.Log(scribe.SourceProbeBackup, scribe.SubjectHost(p.hostName), scribe.ActionStart).Warnf("faulting", createStart,
			"[%s] declares no backup stages, assuming [%s]", p.configPath, strings.Join(p.stages, ","))
	}
	p.serverHost = slices.Contains(p.stages, backupStageTertiary)
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
	rolled, _ := filepath.Glob(filepath.Join(p.root, "*", "status.json"))
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
		scribe.Log(scribe.SourceProbeBackup, scribe.SubjectHost(p.hostName), scribe.ActionPublish).Warnf("faulting", started, "[%v] arming [%s], retrying on every reaper tick until it is reached", err, clusterReaperTopic)
		return false
	}
	defer client.close()
	armed, _ := json.Marshal(backupReaper{State: metric.CommandOn})
	if err := client.publishRetained(clusterReaperTopic, string(armed)); err != nil {
		scribe.Log(scribe.SourceProbeBackup, scribe.SubjectHost(p.hostName), scribe.ActionPublish).Warnf("faulting", started, "[%v] arming [%s], retrying on every reaper tick until it is reached", err, clusterReaperTopic)
		return false
	}
	p.reapArming = false
	p.reapNotice = 0
	scribe.Log(scribe.SourceProbeBackup, scribe.SubjectHost(p.hostName), scribe.ActionPublish).Infof("released", started, "[%s] armed, the backup disk is powered down again when nothing needs it", clusterReaperTopic)
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
		watch, err := brokerWatch(p.configPath, p.hostName, stateTopic, clusterStatusTopic, clusterReaperTopic, "supervisor/+/backup/stage/tertiary/status")
		if err != nil {
			scribe.Log(scribe.SourceProbeBackup, scribe.SubjectHost(p.hostName), scribe.ActionConnect).Warnf("faulting", reapStart, "[%v] watching the estate, retrying on the next tick", err)
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
				"[%d] ticks with nothing watched, redialling the estate watch", reaperStaleTicks)
		}
		return
	}
	p.reapStale = 0
	flag, declared := retained[clusterReaperTopic]
	var reaper backupReaper
	if declared {
		_ = json.Unmarshal([]byte(flag), &reaper)
	}
	switch {
	case !declared:
		scribe.Log(scribe.SourceProbeBackup, scribe.SubjectHost(p.hostName), scribe.ActionPublish).Infof("restored", reapStart,
			"[%s] is absent, asserting the armed default the broker no longer carries", clusterReaperTopic)
		p.armReaper(reapStart)
	case strings.EqualFold(strings.TrimSpace(reaper.State), metric.CommandOff) && !reaper.paused():
		scribe.Log(scribe.SourceProbeBackup, scribe.SubjectHost(p.hostName), scribe.ActionPublish).Infof("restored", reapStart,
			"[%s] paused until [%s], which has passed, arming it again", clusterReaperTopic, reaper.ExpiresTS)
		p.armReaper(reapStart)
	case p.reapArming:
		p.armReaper(reapStart)
	}
	if paused := reaper.paused(); paused != p.reapPaused {
		p.reapPaused = paused
		if paused {
			scribe.Log(scribe.SourceProbeBackup, scribe.SubjectHost(p.hostName), scribe.ActionStop).Infof("excluded", reapStart,
				"[%s] is off until [%s], the backup disk stays powered", clusterReaperTopic, reaper.ExpiresTS)
		} else {
			scribe.Log(scribe.SourceProbeBackup, scribe.SubjectHost(p.hostName), scribe.ActionStart).Infof("restored", reapStart,
				"[%s] is on, the backup disk is powered down again when nothing needs it", clusterReaperTopic)
		}
	}
	if p.reapPaused {
		if p.reapQuiet() {
			scribe.Log(scribe.SourceProbeBackup, scribe.SubjectHost(p.hostName), scribe.ActionStop).Infof("deferred", reapStart,
				"[%s] is still off until [%s], the backup disk stays powered", clusterReaperTopic, reaper.ExpiresTS)
		}
		return
	}
	if !strings.EqualFold(strings.TrimSpace(retained[stateTopic]), "on") {
		if p.reapQuiet() {
			scribe.Log(scribe.SourceProbeBackup, scribe.SubjectHost(p.hostName), scribe.ActionStop).Infof("deferred", reapStart,
				"[%s] does not report the disk on, so there is nothing to power down", stateTopic)
		}
		return
	}
	var coordinated backupDocument
	if json.Unmarshal([]byte(retained[clusterStatusTopic]), &coordinated) == nil && coordinated.State == metric.BackupStateRunning {
		if started, perr := time.Parse(time.RFC3339, coordinated.StartedTS); perr == nil && time.Since(started) < backupRunCeiling {
			if p.reapQuiet() {
				scribe.Log(scribe.SourceProbeBackup, scribe.SubjectHost(p.hostName), scribe.ActionStop).Infof("deferred", reapStart,
					"[%s] reports a run started [%s] still coordinating, leaving the disk powered", clusterStatusTopic, coordinated.StartedTS)
			}
			return
		}
	}
	for topic, payload := range retained {
		if !strings.HasSuffix(topic, "/backup/stage/tertiary/status") {
			continue
		}
		var document backupDocument
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
	if leading, _ := Leading(metric.LeaderRoleBackup); !leading {
		if p.reapQuiet() {
			scribe.Log(scribe.SourceProbeBackup, scribe.SubjectHost(p.hostName), scribe.ActionStop).Infof("deferred", reapStart,
				"[%s] election is not held by this host, leaving the power down to its leader", metric.LeaderRoleBackup)
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
	if leading, _ := Leading(metric.LeaderRoleBackup); !leading {
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
	if _, statErr := os.Stat(p.runner); statErr != nil {
		return
	}
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
		stop := exec.CommandContext(stopCtx, "bash", p.runner, "stop", snapshot.dir, "--stage", stage)
		stop.Env = append(os.Environ(), "BACKUP_RUN_ID="+snapshot.dir, "BACKUP_RUN_PATH="+runPath, "BACKUP_RUN_ID_PASSED=1")
		stop.Cancel = func() error { return stop.Process.Signal(syscall.SIGTERM) }
		stop.WaitDelay = backupStageKillGrace
		if stopErr := stop.Run(); stopErr != nil {
			scribe.Log(scribe.SourceProbeBackup, scribe.SubjectHost(p.hostName), scribe.ActionStop).Warnf("faulting", staleStart, "[%-9s] stage of run [%s] did not stop within [%s], abandoning it with [%v]", stage, snapshot.dir, backupStopDeadline, stopErr)
		}
		stopCancel()
		stale := *document
		stale.State = metric.BackupStateTimedout
		stale.FinishedTS = time.Now().Format(time.RFC3339)
		stale.ExpiresTS = ""
		writeDocumentAtomic(stageStatusPath(runPath, stage), stale)
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
	if p.snapshot != nil && printed == p.snapshotPrint &&
		config.SinceIncludingSuspend(p.snapshotTakenAt) < config.CacheWindow(p.periods.CacheMins) {
		return p.snapshot
	}
	p.snapshot = readNewestRun(p.root)
	p.snapshotPrint = printed
	p.snapshotTakenAt = config.NowIncludingSuspend()
	return p.snapshot
}

func (p *backupProbe) fingerprint() string {
	entries, err := os.ReadDir(p.root)
	if err != nil {
		return ""
	}
	newest := ""
	for _, entry := range entries {
		if entry.IsDir() && backupRunDirPattern.MatchString(entry.Name()) && entry.Name() > newest {
			newest = entry.Name()
		}
	}
	if newest == "" {
		return ""
	}
	runPath := filepath.Join(p.root, newest)
	marks := []string{newest}
	for _, path := range append([]string{filepath.Join(runPath, "status.json")}, stageStatusPaths(runPath)...) {
		info, err := os.Stat(path)
		if err != nil {
			marks = append(marks, "-")
			continue
		}
		marks = append(marks, info.ModTime().UTC().Format(time.RFC3339Nano))
	}
	return strings.Join(marks, "/")
}

func stageStatusPaths(runPath string) []string {
	paths := make([]string, 0, len(backupStages))
	for _, stage := range backupStages {
		paths = append(paths, stageStatusPath(runPath, stage))
	}
	return paths
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
	stages := p.stages
	if p.serverHost {
		p.powerBackupDisk(metric.CommandOn, runStart)
	}
	scribe.Log(scribe.SourceProbeBackup, scribe.SubjectHost(p.hostName), scribe.ActionStart).Infof("schedule", runStart, "[%s] backup run over [%d] stages", runID, len(stages))
	failed, attempted := 0, 0
	for _, stage := range stages {
		attempted++
		if err := p.runStage(ctx, stage, runID, runPath); err != nil {
			failed++
			scribe.Log(scribe.SourceProbeBackup, scribe.SubjectHost(p.hostName), scribe.ActionStart).Warnf("faulting", runStart, "[%s] backup stage failed with [%v], stopping the run", stage, err)
			break
		}
	}
	p.pruneRuns(runStart)
	document := p.writeRunDocument(runPath, runID, attempted, failed, runStart)
	p.publishHostStatus(document)
	p.refresh()
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
	command := exec.CommandContext(stageCtx, "bash", p.runner, "start", runID, "--stage", stage)
	command.Env = append(os.Environ(), "BACKUP_RUN_ID="+runID, "BACKUP_RUN_PATH="+runPath, "BACKUP_RUN_ID_PASSED=1")
	command.Cancel = func() error { return command.Process.Signal(syscall.SIGTERM) }
	command.WaitDelay = backupStageKillGrace
	command.Stdout = logFile
	command.Stderr = logFile
	runErr := command.Run()
	if runErr != nil {
		stopCtx, stopCancel := context.WithTimeout(context.WithoutCancel(ctx), backupStopDeadline)
		defer stopCancel()
		stop := exec.CommandContext(stopCtx, "bash", p.runner, "stop", runID, "--stage", stage)
		stop.Env = command.Env
		stop.Cancel = func() error { return stop.Process.Signal(syscall.SIGTERM) }
		stop.WaitDelay = backupStageKillGrace
		stop.Stdout = logFile
		stop.Stderr = logFile
		_ = stop.Run()
		return fmt.Errorf("stage [%s] exited with [%w]", stage, runErr)
	}
	return nil
}

func (p *backupProbe) writeRunDocument(runPath, runID string, stagesRun, stagesFailed int, started time.Time) backupDocument {
	state := metric.BackupStateFailed
	if stagesFailed == 0 {
		state = metric.BackupStateComplete
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
	for _, stage := range backupStages {
		staged := readStageDocument(stageStatusPath(runPath, stage))
		if staged == nil {
			continue
		}
		document.FileCount += staged.FileCount
		document.SizeMB += staged.SizeMB
		document.FilesCreated += staged.FilesCreated
		document.FilesDeleted += staged.FilesDeleted
		document.SentMB += staged.SentMB
		if stage == backupStageTertiary {
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

func (p *backupProbe) lead() {
	if !p.serverHost || !p.leadRunning.TryLock() {
		return
	}
	defer p.leadRunning.Unlock()
	leading, epoch := Leading(metric.LeaderRoleBackup)
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
		watch, err := brokerWatch(p.configPath, p.hostName, "supervisor/+/backup/status", "supervisor/+/backup/stage/+/status", clusterStatusTopic)
		if err != nil {
			scribe.Log(scribe.SourceProbeBackup, scribe.SubjectHost(p.hostName), scribe.ActionConnect).Warnf("deferred", leadStart, "[%v] watching the estate run, retrying on the next tick", err)
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
			scribe.Log(scribe.SourceProbeBackup, scribe.SubjectHost(p.hostName), scribe.ActionConnect).Warnf("faulting", leadStart, "[%d] ticks with the estate run unwatched, redialling", reaperStaleTicks)
		}
		return
	}
	p.leadStale = 0
	expected := backupExpectedServers(p.configPath)
	decision := backupEstateDecision(retained, expected, time.Now())
	if decision.action == backupEstateIdle {
		return
	}
	client, err := brokerDial(p.configPath, "coordinate")
	if err != nil {
		scribe.Log(scribe.SourceProbeBackup, scribe.SubjectHost(p.hostName), scribe.ActionConnect).Warnf("deferred", leadStart, "[%v] reaching the broker to coordinate the estate run, retrying on the next tick", err)
		return
	}
	defer client.close()
	if leading, current := Leading(metric.LeaderRoleBackup); !leading || current != epoch {
		return
	}
	if decision.action == backupEstateClose {
		if topic := config.Load(p.configPath).BackupCommandTopic(); topic != "" {
			if err := client.publishCommand(topic, metric.CommandOff); err != nil {
				scribe.Log(scribe.SourceProbeBackup, scribe.SubjectHost(p.hostName), scribe.ActionPublish).Warnf("faulting", leadStart, "[%v] powering down [%s], retrying on the next tick", err, topic)
				return
			}
		}
	}
	document := map[string]any{
		"run_id":         decision.started.Format(backupRunStamp),
		"state":          decision.state,
		"started_ts":     decision.started.Format(time.RFC3339),
		"duration_s":     int(time.Since(decision.started).Seconds()),
		"success_bool":   decision.state == metric.BackupStateComplete,
		"power_bool":     decision.action != backupEstateClose,
		"hosts_expected": len(expected),
		"hosts_reported": decision.reported,
		"hosts_failed":   decision.failed,
		"leader_host":    p.hostName,
		"leader_epoch":   epoch,
	}
	if decision.action == backupEstateClose {
		document["finished_ts"] = time.Now().Format(time.RFC3339)
	}
	payload, _ := json.Marshal(document)
	if err := client.publishRetained(clusterStatusTopic, string(payload)); err != nil {
		scribe.Log(scribe.SourceProbeBackup, scribe.SubjectHost(p.hostName), scribe.ActionPublish).Warnf("faulting", leadStart, "[%v] publishing the [%s] estate run, retrying on the next tick", err, decision.state)
		return
	}
	switch decision.action {
	case backupEstateOpen:
		scribe.Log(scribe.SourceProbeBackup, scribe.SubjectHost(p.hostName), scribe.ActionRegister).Infof("assigned", leadStart, "[%s] estate run opened at epoch [%d], [%d] of [%d] hosts reported", decision.started.Format(time.RFC3339), epoch, decision.reported, len(expected))
	case backupEstateClose:
		scribe.Log(scribe.SourceProbeBackup, scribe.SubjectHost(p.hostName), scribe.ActionStop).Infof("finished", leadStart, "[%s] estate run closed as [%s], disk powered down, [%d] of [%d] hosts reported", decision.started.Format(time.RFC3339), decision.state, decision.reported, len(expected))
	}
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

type backupEstateAction int

type backupEstate struct {
	action   backupEstateAction
	state    string
	started  time.Time
	reported int
	failed   int
}

func backupEstateDecision(retained map[string]string, expected []string, now time.Time) backupEstate {
	terminal := map[string]bool{metric.BackupStateComplete: true, metric.BackupStateFailed: true, metric.BackupStateTimedout: true}
	var estate backupDocument
	estateStarted := time.Time{}
	if json.Unmarshal([]byte(retained[clusterStatusTopic]), &estate) == nil {
		estateStarted, _ = time.Parse(time.RFC3339, estate.StartedTS)
	}
	decision := backupEstate{action: backupEstateIdle}
	switch {
	case estate.State == metric.BackupStateRunning && !estateStarted.IsZero():
		decision.action, decision.started = backupEstateRefresh, estateStarted
	default:
		for _, host := range expected {
			prefix := "supervisor/" + host + "/backup/stage/"
			for topic, payload := range retained {
				stage, found := strings.CutPrefix(topic, prefix)
				if !found || strings.Count(stage, "/") != 1 || !strings.HasSuffix(stage, "/status") {
					continue
				}
				var document backupDocument
				if json.Unmarshal([]byte(payload), &document) != nil || document.State != metric.BackupStateRunning || document.Trigger != metric.BackupTriggerScheduled {
					continue
				}
				expires, expiresErr := time.Parse(time.RFC3339, document.ExpiresTS)
				if expiresErr != nil || !now.Before(expires) {
					continue
				}
				started, startedOK := backupRunStarted(document)
				if !startedOK || now.Sub(started) > backupRunCeiling || (!estateStarted.IsZero() && !started.After(estateStarted.Add(backupRunSkew))) {
					continue
				}
				if decision.started.IsZero() || started.Before(decision.started) {
					decision.action, decision.started = backupEstateOpen, started
				}
			}
		}
	}
	if decision.action == backupEstateIdle {
		return decision
	}
	earliest := decision.started.Add(-backupRunSkew)
	for _, host := range expected {
		var document backupDocument
		if json.Unmarshal([]byte(retained["supervisor/"+host+"/backup/status"]), &document) == nil &&
			terminal[document.State] && reportedForRun(document, earliest) {
			decision.reported++
			if !document.SuccessBool {
				decision.failed++
			}
		}
	}
	decision.state = metric.BackupStateRunning
	switch {
	case decision.reported >= len(expected) && decision.failed > 0:
		decision.action, decision.state = backupEstateClose, metric.BackupStateFailed
	case decision.reported >= len(expected):
		decision.action, decision.state = backupEstateClose, metric.BackupStateComplete
	case now.Sub(decision.started) > backupRunCeiling:
		decision.action, decision.state = backupEstateClose, metric.BackupStateTimedout
	}
	return decision
}

type backupReaper struct {
	State     string `json:"state"`
	ExpiresTS string `json:"expires_ts"`
}

func (r backupReaper) paused() bool {
	if !strings.EqualFold(strings.TrimSpace(r.State), metric.CommandOff) {
		return false
	}
	expires, err := time.Parse(time.RFC3339, r.ExpiresTS)
	return err == nil && time.Now().Before(expires)
}

func backupRunStarted(document backupDocument) (time.Time, bool) {
	if started, err := time.ParseInLocation(backupRunStamp, document.RunID, time.Local); err == nil {
		return started, true
	}
	started, err := time.Parse(time.RFC3339, document.StartedTS)
	return started, err == nil
}

func reportedForRun(document backupDocument, earliest time.Time) bool {
	started, err := time.Parse(time.RFC3339, document.StartedTS)
	return err == nil && !started.Before(earliest)
}

func backupExpectedServers(configPath string) []string {
	var servers []string
	loaded := config.Load(configPath)
	for _, host := range loaded.Hosts() {
		if slices.Contains(loaded.HostStages(host), backupStageTertiary) {
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
	TotalMB       int     `json:"total_mb,omitempty"`
	SizeMB        int     `json:"size_mb,omitempty"`
	FilesHeld     int     `json:"files_held,omitempty"`
	FilesCreated  int     `json:"files_created,omitempty"`
	FilesDeleted  int     `json:"files_deleted,omitempty"`
	SizeHeldMB    int     `json:"size_held_mb,omitempty"`
	SentMB        int     `json:"sent_mb,omitempty"`
	StagesRun     int     `json:"stages_run,omitempty"`
	StagesFailed  int     `json:"stages_failed,omitempty"`
	StagesHalted  int     `json:"stages_halted,omitempty"`
}

type backupSnapshot struct {
	dir       string
	at        time.Time
	staged    int
	running   bool
	abandoned bool
	trigger   string
	host      *backupDocument
	tertiary  *backupDocument
	stages    map[string]*backupDocument
	services  map[string]bool
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
	newest := readRun(root, runs[len(runs)-1])
	started := newest.host == nil && newest.staged > 0
	running := started && newest.age() <= backupRunCeiling
	abandoned := started && !running && newest.trigger == metric.BackupTriggerScheduled
	snapshot := newest
	for index := len(runs) - 2; !abandoned && snapshot.host == nil && index >= 0; index-- {
		candidate := readRun(root, runs[index])
		if candidate.age() > backupStaleWindow {
			break
		}
		if candidate.host != nil {
			snapshot = candidate
		}
	}
	snapshot.running = running
	snapshot.abandoned = abandoned
	return snapshot
}

func readRun(root, dir string) *backupSnapshot {
	at, _ := time.ParseInLocation(backupRunStamp, dir, time.Local)
	snapshot := &backupSnapshot{dir: dir, at: at, stages: map[string]*backupDocument{}, services: map[string]bool{}}
	runPath := filepath.Join(root, dir)
	snapshot.host = readStageDocument(filepath.Join(runPath, "status.json"))
	staged, _ := filepath.Glob(filepath.Join(runPath, "stage", "*", "status.json"))
	snapshot.staged = len(staged)
	for _, path := range staged {
		if document := readStageDocument(path); document != nil {
			snapshot.stages[filepath.Base(filepath.Dir(path))] = document
		}
	}
	snapshot.tertiary = snapshot.stages[backupStageTertiary]
	for _, stage := range backupStages {
		if document := snapshot.stages[stage]; document != nil && document.Trigger != "" {
			snapshot.trigger = document.Trigger
			break
		}
	}
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
	backupStopDeadline   = 10 * time.Minute
	backupRunSkew        = 10 * time.Minute
	backupRunsKept       = 30
	backupScheduledHour  = 1
	reaperIdleTicks      = 2
	reaperNoticeTicks    = 15
	reaperStaleTicks     = 5

	clusterReaperTopic = "supervisor/" + metric.HostCluster + "/backup/reaper"
	clusterStatusTopic = "supervisor/" + metric.HostCluster + "/backup/status"
)

const backupStageTertiary = "tertiary"

const (
	backupEstateIdle backupEstateAction = iota
	backupEstateOpen
	backupEstateRefresh
	backupEstateClose
)

var (
	backupProbeInstance *backupProbe

	backupStages = []string{"primary", "secondary", backupStageTertiary}

	backupRunDirPattern = regexp.MustCompile(`^\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}$`)
)
