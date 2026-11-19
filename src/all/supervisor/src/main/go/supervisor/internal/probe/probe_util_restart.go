package probe

import (
	"context"
	"fmt"
	"hash/fnv"
	"os"
	"path/filepath"
	"regexp"
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

func newRestartEngine() *restartEngine {
	log := newRestartLog(config.DirServiceHome)
	mode := restartModeObserve
	if os.Getenv(restartModeEnv) == restartModeAct {
		mode = restartModeAct
	}
	engine := &restartEngine{
		ledger:   newRestartLedger(restartLedgerPath),
		checker:  newRestartChecker(),
		loader:   newRestartPolicyLoader(),
		log:      log,
		mode:     mode,
		fastPath: os.Getenv(restartFastPathEnv) == "on",
		started:  time.Now(),
		now:      time.Now,
		bootID: func() string {
			data, err := os.ReadFile(restartBootIDPath)
			if err != nil {
				return ""
			}
			return strings.TrimSpace(string(data))
		},
		held: func() bool { return restartHostHeld(restartHoldPath) },
		limit: func(service string) (time.Duration, error) {
			return installLimit(service, "SERVICE_STOP_SECONDS", "SERVICE_WAIT_RESTART_SECONDS")
		},
		tracked: make(map[string]*restartTracked),
	}
	engine.run = func(ctx context.Context, service string, limit time.Duration) (int, string) {
		return runInstall(ctx, service, "restart", limit)
	}
	engine.emit = func(service string, line string) { log.write(service, "%s", line) }
	return engine
}

func installScript(service string) string {
	return filepath.Join(installRoot, service, config.DirInstallLatestLink, restartInstallLeaf)
}

func installLimit(service string, names ...string) (time.Duration, error) {
	data, err := os.ReadFile(installScript(service))
	if err != nil {
		return 0, err
	}
	return parseInstallLimit(string(data), names...)
}

func runInstall(ctx context.Context, service string, verb string, limit time.Duration) (int, string) {
	out, code, abandoned := bounded(ctx, limit, "bash", installScript(service), verb)
	if abandoned {
		return 1, out + "abandoned after the limit"
	}
	return code, out
}

func parseInstallLimit(script string, names ...string) (time.Duration, error) {
	declared := map[string]int{}
	for _, match := range installLimitPattern.FindAllStringSubmatch(script, -1) {
		value, err := strconv.Atoi(match[2])
		if err != nil {
			return 0, err
		}
		declared[match[1]] = value
	}
	total := 0
	for _, name := range names {
		if declared[name] == 0 {
			return 0, fmt.Errorf("install.sh declares no [%s]", name)
		}
		total += declared[name]
	}
	return time.Duration(total)*time.Second + restartRunMargin, nil
}

func restartJitter(service string, streak int) float64 {
	hasher := fnv.New32a()
	_, _ = fmt.Fprintf(hasher, "%s|%d", service, streak)
	return float64(int(hasher.Sum32()%restartJitterSpread)-restartJitterSpread/2) / 100
}

func (e *restartEngine) evaluate(ctx context.Context, observations []restartObservation) map[string]restartStatus {
	e.mutex.Lock()
	defer e.mutex.Unlock()
	statuses := make(map[string]restartStatus, len(observations))
	now := e.now()
	_ = e.ledger.booted(e.bootID())
	held := e.held()
	slices.SortFunc(observations, func(left, right restartObservation) int { return strings.Compare(left.service, right.service) })
	for _, observation := range observations {
		policy, enabled, err := e.loader.load(ctx, observation.service)
		if err != nil {
			statuses[observation.service] = restartStatus{state: metric.RestartStateWaiting, reason: "policy unreadable [" + err.Error() + "]"}
			e.report(observation.service, statuses[observation.service])
			continue
		}
		if !enabled || observation.service == restartSelf {
			delete(e.tracked, observation.service)
			continue
		}
		statuses[observation.service] = e.step(ctx, now, held, policy, observation)
		e.report(observation.service, statuses[observation.service])
	}
	return statuses
}

func (e *restartEngine) step(ctx context.Context, now time.Time, held bool, policy restartPolicy, observation restartObservation) restartStatus {
	tracked := e.tracked[observation.service]
	if tracked == nil || tracked.container != observation.container {
		tracked = &restartTracked{container: observation.container}
		e.tracked[observation.service] = tracked
	}
	if observation.health == restartHealthUnhealthy {
		if tracked.unhealthySince.IsZero() {
			tracked.unhealthySince = now
		}
	} else {
		tracked.unhealthySince = time.Time{}
	}
	if observation.health == restartHealthHealthy {
		if tracked.stableSince.IsZero() {
			tracked.stableSince = now
		}
	} else {
		tracked.stableSince = time.Time{}
	}
	met := true
	if observation.health != restartHealthHealthy {
		for _, requirement := range policy.requires {
			if !e.checker.met(ctx, requirement) {
				met = false
				break
			}
		}
	}
	if met && observation.health != restartHealthHealthy && !e.loader.ready(ctx, observation.service) {
		met = false
	}
	switch {
	case observation.health == restartHealthHealthy || !met:
		tracked.heldSince = time.Time{}
	case tracked.heldSince.IsZero() && len(policy.requires) > 0:
		tracked.heldSince = now
	}
	history := e.ledger.history(observation.service, observation.container)
	e.hostRestarts = slices.DeleteFunc(e.hostRestarts, func(at time.Time) bool { return now.Sub(at) >= time.Hour })
	var hostLast time.Time
	if len(e.hostRestarts) > 0 {
		hostLast = e.hostRestarts[len(e.hostRestarts)-1]
	}
	decision := decideRestart(restartInput{
		now:               now,
		health:            observation.health,
		startedAt:         observation.startedAt,
		healthcheck:       observation.healthcheck,
		policy:            policy,
		unhealthySince:    tracked.unhealthySince,
		stableSince:       tracked.stableSince,
		requiresMet:       met,
		requiresHeldSince: tracked.heldSince,
		attempts:          history.attempts,
		streak:            history.streak,
		supervisorStarted: e.started,
		hostHold:          held,
		hostInFlight:      e.inFlight,
		hostLast:          hostLast,
		hostHour:          len(e.hostRestarts),
		fastPath:          e.fastPath,
		jitter:            restartJitter(observation.service, history.streak),
	})
	if decision.reset && history.streak > 0 {
		_ = e.ledger.settled(observation.service, observation.container)
	}
	status := restartStatus{state: decision.state, reason: decision.reason}
	for _, attempt := range history.attempts {
		if now.Sub(attempt) < restartWindow {
			status.attempts++
		}
	}
	if !decision.act {
		return status
	}
	if e.mode != restartModeAct {
		status.state = metric.RestartStateWaiting
		status.reason = "observe mode, would restart now"
		return status
	}
	limit, err := e.limit(observation.service)
	if err != nil {
		status.state = metric.RestartStateWaiting
		status.reason = "install.sh limits unreadable [" + err.Error() + "]"
		return status
	}
	if err := e.ledger.record(observation.service, observation.container, now); err != nil {
		status.state = metric.RestartStateWaiting
		status.reason = "ledger could not be written, no restart made [" + err.Error() + "]"
		return status
	}
	status.attempts++
	e.inFlight = true
	e.hostRestarts = append(e.hostRestarts, now)
	e.workers.Add(1)
	go e.restart(ctx, observation, status.attempts, limit, now)
	return status
}

func (e *restartEngine) restart(ctx context.Context, observation restartObservation, attempt int, limit time.Duration, at time.Time) {
	defer e.workers.Done()
	started := e.now()
	e.emit(observation.service, fmt.Sprintf("restart [%s] attempt [%d] of [%d] limit [%s]", observation.service, attempt, restartAttemptsMax, limit))
	logger := scribe.Log(scribe.SourceProbeRestart, scribe.SubjectService(observation.service), scribe.ActionStart)
	logger.Infof("restarts", started, "[%s] attempt [%d] of [%d], install.sh restart limited to [%s]", observation.service, attempt, restartAttemptsMax, limit)
	code, output := e.run(ctx, observation.service, limit)
	for line := range strings.SplitSeq(strings.TrimSpace(output), "\n") {
		if line != "" {
			e.emit(observation.service, "install.sh | "+line)
		}
	}
	e.emit(observation.service, fmt.Sprintf("restart [%s] exit [%d] took [%s]", observation.service, code, e.now().Sub(started).Truncate(time.Millisecond)))
	if code != 0 && code != restartExitSkipped {
		logger.Warnf("restarts", started, "[%s] exit [%d], install.sh restart failed, the attempt stays counted", observation.service, code)
	} else {
		logger.Infof("restarts", started, "[%s] exit [%d], install.sh restart finished", observation.service, code)
	}
	e.mutex.Lock()
	defer e.mutex.Unlock()
	if code == restartExitSkipped {
		_ = e.ledger.refund(observation.service, observation.container)
		e.hostRestarts = slices.DeleteFunc(e.hostRestarts, func(restarted time.Time) bool { return restarted.Equal(at) })
	}
	e.inFlight = false
}

func (e *restartEngine) report(service string, status restartStatus) {
	tracked := e.tracked[service]
	if tracked == nil {
		tracked = &restartTracked{}
		e.tracked[service] = tracked
	}
	line := fmt.Sprintf("state [%s] reason [%s]", status.state, status.reason)
	if tracked.reported == line {
		return
	}
	tracked.reported = line
	e.emit(service, line)
	logger := scribe.Log(scribe.SourceProbeRestart, scribe.SubjectService(service), scribe.ActionCompute)
	switch status.state {
	case metric.RestartStateExhausted:
		logger.Warnf("deciding", e.now(), "[%s] state, because [%s]", status.state, status.reason)
	case metric.RestartStateRestarting:
		logger.Infof("deciding", e.now(), "[%s] state, because [%s]", status.state, status.reason)
	default:
		logger.Debugf("deciding", e.now(), "[%s] state, because [%s]", status.state, status.reason)
	}
}

func (e *restartEngine) tick(ctx context.Context, observations []restartObservation) {
	ctx = context.WithoutCancel(ctx)
	if !e.evaluating.CompareAndSwap(false, true) {
		return
	}
	e.workers.Go(func() {
		defer e.evaluating.Store(false)
		statuses := e.evaluate(ctx, observations)
		e.latestMutex.Lock()
		e.latest = statuses
		e.latestMutex.Unlock()
	})
}

func (e *restartEngine) status(service string) (restartStatus, bool) {
	e.latestMutex.Lock()
	defer e.latestMutex.Unlock()
	status, found := e.latest[service]
	return status, found
}

type restartObservation struct {
	service     string
	container   string
	health      string
	startedAt   time.Time
	healthcheck restartHealthcheck
}

type restartStatus struct {
	state    string
	reason   string
	attempts int
}

type restartTracked struct {
	container      string
	unhealthySince time.Time
	stableSince    time.Time
	heldSince      time.Time
	reported       string
}

type restartEngine struct {
	mutex        sync.Mutex
	workers      sync.WaitGroup
	ledger       *restartLedger
	checker      restartChecker
	loader       *restartPolicyLoader
	log          *restartLog
	mode         string
	fastPath     bool
	started      time.Time
	now          func() time.Time
	bootID       func() string
	held         func() bool
	limit        func(service string) (time.Duration, error)
	run          func(ctx context.Context, service string, limit time.Duration) (int, string)
	emit         func(service string, line string)
	tracked      map[string]*restartTracked
	hostRestarts []time.Time
	inFlight     bool

	evaluating  atomic.Bool
	latestMutex sync.Mutex
	latest      map[string]restartStatus
}

const (
	restartModeObserve  = "observe"
	restartModeAct      = "act"
	restartExitSkipped  = 10
	restartRunMargin    = 30 * time.Second
	restartInstallLeaf  = "install.sh"
	restartBootIDPath   = "/proc/sys/kernel/random/boot_id"
	restartJitterSpread = 21

	restartSelf                  = "supervisor"
	restartModeEnv               = "SUPERVISOR_RESTART_MODE"
	restartFastPathEnv           = "SUPERVISOR_RESTART_FAST"
	restartDockerDefaultInterval = 30 * time.Second
	restartDockerDefaultRetries  = 3
)

var (
	installLimitPattern = regexp.MustCompile(`(?m)^(SERVICE_[A-Z_]+_SECONDS)=([0-9]+)$`)
)
