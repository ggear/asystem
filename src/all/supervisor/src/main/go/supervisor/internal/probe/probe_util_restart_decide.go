package probe

import (
	"fmt"
	"time"
)

func restartBackoff(settle time.Duration, streak int, jitter float64) time.Duration {
	wait := restartBackoffCap
	if shift := max(streak-1, 0); shift < 8 {
		wait = min(restartBackoffCap, max(settle, restartBackoffFloor)<<shift)
	}
	return time.Duration(float64(wait) * (1 + jitter))
}

func decideRestart(in restartInput) restartDecision {
	interval := in.healthcheck.interval
	window := interval * time.Duration(in.healthcheck.retries)
	settle := window
	grace := window
	if in.release {
		settle += in.healthcheck.startPeriod
		grace = in.healthcheck.startPeriod
	}
	settle = max(settle, in.policy.settleMin)
	grace = max(grace, in.policy.settleMin)
	lateGrace := grace
	if !in.release && in.policy.settleMin > 0 {
		lateGrace = in.policy.settleMin
	}
	var last time.Time
	recent := 0
	for _, attempt := range in.attempts {
		if in.now.Sub(attempt) < restartWindow {
			recent++
		}
		if attempt.After(last) {
			last = attempt
		}
	}
	if in.health == restartHealthHealthy {
		if !in.stableSince.IsZero() && in.now.Sub(in.stableSince) >= 2*interval {
			return restartDecision{state: restartStateOK, reason: "healthy and stable", reset: true}
		}
		if recent > 0 {
			return restartDecision{state: restartStateSettling, reason: "healthy after a restart, confirming it holds"}
		}
		return restartDecision{state: restartStateOK, reason: "healthy"}
	}
	if !last.IsZero() && in.now.Sub(last) < settle {
		return restartDecision{state: restartStateSettling, reason: "judging the service after its restart"}
	}
	age := in.now.Sub(in.startedAt)
	unhealthy := in.health == restartHealthUnhealthy && !in.unhealthySince.IsZero() && in.now.Sub(in.unhealthySince) >= interval && age >= grace
	late := in.requiresLapsed && in.requiresMet && !in.requiresHeldSince.IsZero() && in.probeFailed && in.probeEnd.After(in.requiresHeldSince.Add(in.policy.stable)) && age >= lateGrace
	if !unhealthy && !late {
		if in.health == restartHealthUnhealthy {
			return restartDecision{state: restartStateSuspect, reason: "unhealthy, inside its grace"}
		}
		looping := 0
		for _, rise := range in.rises {
			if in.now.Sub(rise) < window {
				looping++
			}
		}
		if looping >= restartLoopRises {
			return restartDecision{state: restartStateSuspect, reason: fmt.Sprintf("crash looping, docker restarted it at least [%d] times inside [%s], left to docker", restartLoopRises, window)}
		}
		return restartDecision{state: restartStateOK, reason: "not judged, " + in.health}
	}
	if recent >= restartAttemptsMax {
		return restartDecision{state: restartStateExhausted, reason: fmt.Sprintf("budget spent, [%d] restarts in [%s]", recent, restartWindow)}
	}
	waiting := func(reason string) restartDecision {
		return restartDecision{state: restartStateWaiting, reason: reason}
	}
	if warmed := in.supervisorStarted.Add(interval); in.now.Before(warmed) {
		return waiting("supervisor started recently")
	}
	if in.hostHold {
		return waiting("host is asleep, being put to sleep or being woken")
	}
	if !in.requiresMet {
		return waiting("a prerequisite is not met")
	}
	if stable := in.requiresHeldSince.Add(in.policy.stable); in.now.Before(stable) {
		return waiting(fmt.Sprintf("prerequisites held for less than [%s]", in.policy.stable))
	}
	if !last.IsZero() {
		if until := last.Add(restartBackoff(settle, in.streak, in.jitter)); in.now.Before(until) {
			return waiting("backing off after the last restart")
		}
	}
	if in.hostInFlight {
		return waiting("another restart is in flight on this host")
	}
	if spaced := in.hostLast.Add(restartHostSpacing); !in.hostLast.IsZero() && in.now.Before(spaced) {
		return waiting("another restart was made on this host a moment ago")
	}
	if in.hostHour >= restartHostHourlyMax {
		return waiting("this host has used its restarts for the hour")
	}
	return restartDecision{state: restartStateRestarting, reason: "unhealthy with every prerequisite held", act: true}
}

type restartHealthcheck struct {
	interval    time.Duration
	startPeriod time.Duration
	retries     int
}

type restartInput struct {
	now               time.Time
	health            string
	startedAt         time.Time
	healthcheck       restartHealthcheck
	policy            restartPolicy
	unhealthySince    time.Time
	stableSince       time.Time
	requiresMet       bool
	requiresHeldSince time.Time
	attempts          []time.Time
	rises             []time.Time
	streak            int
	supervisorStarted time.Time
	hostHold          bool
	hostInFlight      bool
	hostLast          time.Time
	hostHour          int
	requiresLapsed    bool
	release           bool
	probeEnd          time.Time
	probeFailed       bool
	jitter            float64
}

type restartDecision struct {
	state  string
	reason string
	act    bool
	reset  bool
}

const (
	restartHealthHealthy   = "healthy"
	restartHealthUnhealthy = "unhealthy"
	restartAttemptsMax     = 3
	restartLoopRises       = 2
	restartWindow          = 24 * time.Hour
	restartBackoffCap      = time.Hour
	restartBackoffFloor    = time.Minute
	restartHostSpacing     = time.Minute
	restartHostHourlyMax   = 6
)
