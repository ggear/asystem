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
	engine := &restartEngine{
		ledger:  newRestartLedger(restartLedgerPath),
		checker: newRestartChecker(),
		loader:  newRestartPolicyLoader(),
		log:     log,
		started: time.Now(),
		now:     time.Now,
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
	e.checked = make(map[restartRequirement]bool)
	now := e.now()
	_ = e.ledger.booted(e.bootID())
	held := e.held()
	if e.wasHeld && !held {
		_ = e.ledger.woken()
	}
	e.wasHeld = held
	slices.SortFunc(observations, func(left, right restartObservation) int { return strings.Compare(left.service, right.service) })
	for _, observation := range observations {
		policy, enabled, err := e.loader.load(ctx, observation.service)
		if err != nil {
			statuses[observation.service] = restartStatus{state: metric.RestartStateWaiting, reason: "policy unreadable [" + err.Error() + "]"}
			e.report(observation, statuses[observation.service])
			continue
		}
		if !enabled || observation.service == restartSelf {
			delete(e.tracked, observation.service)
			continue
		}
		statuses[observation.service] = e.step(ctx, now, held, policy, observation)
		e.report(observation, statuses[observation.service])
	}
	return statuses
}

func (e *restartEngine) step(ctx context.Context, now time.Time, held bool, policy restartPolicy, observation restartObservation) restartStatus {
	tracked := e.trackedOf(observation.service, observation.container)
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
	unwell := observation.health != restartHealthHealthy || observation.failingStreak > 0
	met := true
	if unwell {
		for _, requirement := range policy.requires {
			satisfied, checked := e.checked[requirement]
			if !checked {
				satisfied = e.checker.met(ctx, requirement)
				e.checked[requirement] = satisfied
			}
			if !satisfied {
				met = false
				break
			}
		}
	}
	if met && unwell && !e.loader.ready(ctx, observation.service) {
		met = false
	}
	if !unwell {
		tracked.requiresLapsed = false
	} else if !met {
		tracked.requiresLapsed = true
	}
	switch {
	case !unwell || !met:
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
		rises:             history.rises,
		streak:            history.streak,
		supervisorStarted: e.started,
		hostHold:          held,
		hostInFlight:      e.inFlight,
		hostLast:          hostLast,
		hostHour:          len(e.hostRestarts),
		requiresLapsed:    tracked.requiresLapsed,
		release:           history.image == "" || history.image != observation.image,
		probeEnd:          observation.probeEnd,
		probeFailed:       observation.probeFailed,
		jitter:            restartJitter(observation.service, history.streak),
	})
	if decision.reset && history.streak > 0 {
		_ = e.ledger.settled(observation.service, observation.container)
	}
	if decision.reset && observation.image != "" && observation.image != history.image {
		_ = e.ledger.imaged(observation.service, observation.container, observation.image)
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
	logger.Infof("restarts", started, "[%s] attempt [%d] of [%d], install.sh restart limited to [%s]", scribe.Fit(observation.service, restartWidthService), attempt, restartAttemptsMax, scribe.Fit(limit.String(), restartWidthLimit))
	code, output := e.run(ctx, observation.service, limit)
	for line := range strings.SplitSeq(strings.TrimSpace(output), "\n") {
		if line != "" {
			e.emit(observation.service, "install.sh | "+line)
		}
	}
	e.emit(observation.service, fmt.Sprintf("restart [%s] exit [%d] took [%s]", observation.service, code, e.now().Sub(started).Truncate(time.Millisecond)))
	if code != 0 && code != restartExitSkipped {
		logger.Warnf("restarts", started, "[%s] exit [%3d], install.sh restart failed, the attempt stays counted", scribe.Fit(observation.service, restartWidthService), code)
	} else {
		logger.Infof("restarts", started, "[%s] exit [%3d], install.sh restart finished", scribe.Fit(observation.service, restartWidthService), code)
	}
	e.mutex.Lock()
	defer e.mutex.Unlock()
	if code == restartExitSkipped {
		_ = e.ledger.refund(observation.service, observation.container)
		e.hostRestarts = slices.DeleteFunc(e.hostRestarts, func(restarted time.Time) bool { return restarted.Equal(at) })
	}
	e.inFlight = false
}

func (e *restartEngine) trackedOf(service string, container string) *restartTracked {
	tracked := e.tracked[service]
	if tracked == nil || tracked.container != container {
		tracked = &restartTracked{container: container}
		e.tracked[service] = tracked
	}
	return tracked
}

func (e *restartEngine) report(observation restartObservation, status restartStatus) {
	service := observation.service
	tracked := e.trackedOf(service, observation.container)
	line := fmt.Sprintf("state [%s] reason [%s]", status.state, status.reason)
	if tracked.reported == line {
		return
	}
	tracked.reported = line
	e.emit(service, line)
	logger := scribe.Log(scribe.SourceProbeRestart, scribe.SubjectService(service), scribe.ActionCompute)
	switch status.state {
	case metric.RestartStateExhausted:
		logger.Warnf("deciding", e.now(), "[%s] state, because [%s]", scribe.Fit(status.state, restartWidthState), scribe.Fit(status.reason, restartWidthReason))
	case metric.RestartStateRestarting:
		logger.Infof("deciding", e.now(), "[%s] state, because [%s]", scribe.Fit(status.state, restartWidthState), scribe.Fit(status.reason, restartWidthReason))
	default:
		logger.Debugf("deciding", e.now(), "[%s] state, because [%s]", scribe.Fit(status.state, restartWidthState), scribe.Fit(status.reason, restartWidthReason))
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
	service       string
	container     string
	image         string
	health        string
	startedAt     time.Time
	healthcheck   restartHealthcheck
	probeEnd      time.Time
	probeFailed   bool
	failingStreak int
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
	requiresLapsed bool
	reported       string
}

type restartEngine struct {
	mutex        sync.Mutex
	workers      sync.WaitGroup
	ledger       *restartLedger
	checker      restartChecker
	loader       *restartPolicyLoader
	log          *restartLog
	started      time.Time
	now          func() time.Time
	bootID       func() string
	held         func() bool
	limit        func(service string) (time.Duration, error)
	run          func(ctx context.Context, service string, limit time.Duration) (int, string)
	emit         func(service string, line string)
	tracked      map[string]*restartTracked
	checked      map[restartRequirement]bool
	hostRestarts []time.Time
	inFlight     bool
	wasHeld      bool

	evaluating  atomic.Bool
	latestMutex sync.Mutex
	latest      map[string]restartStatus
}

const (
	restartExitSkipped  = 10
	restartRunMargin    = 30 * time.Second
	restartInstallLeaf  = "install.sh"
	restartBootIDPath   = "/proc/sys/kernel/random/boot_id"
	restartJitterSpread = 21

	restartWidthService = 14
	restartWidthState   = 10
	restartWidthReason  = 44
	restartWidthLimit   = 6

	restartSelf                  = "supervisor"
	restartDockerDefaultInterval = 30 * time.Second
	restartDockerDefaultRetries  = 3
)

var (
	installLimitPattern = regexp.MustCompile(`(?m)^(SERVICE_[A-Z_]+_SECONDS)=([0-9]+)$`)
)
