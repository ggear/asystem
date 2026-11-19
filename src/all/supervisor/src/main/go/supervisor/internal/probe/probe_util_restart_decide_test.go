package probe

import (
	"testing"
	"time"

	"supervisor/internal/metric"
)

func restartBase() restartInput {
	now := time.Date(2026, 11, 19, 12, 0, 0, 0, time.UTC)
	return restartInput{
		now:               now,
		health:            restartHealthUnhealthy,
		startedAt:         now.Add(-time.Hour),
		healthcheck:       restartHealthcheck{interval: 2 * time.Minute, startPeriod: time.Minute, retries: 3},
		policy:            restartPolicy{stable: time.Minute},
		unhealthySince:    now.Add(-10 * time.Minute),
		requiresMet:       true,
		requiresHeldSince: now.Add(-5 * time.Minute),
		supervisorStarted: now.Add(-time.Hour),
	}
}

func TestProbeUtilRestartDecide_Decide(t *testing.T) {
	tests := []struct {
		name          string
		change        func(*restartInput)
		expectedState string
		expectedAct   bool
		expectedReset bool
	}{
		{name: "an_unhealthy_service_with_everything_held_is_restarted", change: func(*restartInput) {}, expectedState: metric.RestartStateRestarting, expectedAct: true},
		{name: "a_healthy_service_is_left_alone", change: func(in *restartInput) { in.health = restartHealthHealthy }, expectedState: metric.RestartStateOK},
		{name: "a_stable_healthy_service_resets_its_streak", change: func(in *restartInput) {
			in.health = restartHealthHealthy
			in.stableSince = in.now.Add(-5 * time.Minute)
		}, expectedState: metric.RestartStateOK, expectedReset: true},
		{name: "a_service_healthy_for_less_than_two_intervals_after_a_restart_is_still_settling", change: func(in *restartInput) {
			in.health = restartHealthHealthy
			in.stableSince = in.now.Add(-time.Minute)
			in.attempts = []time.Time{in.now.Add(-3 * time.Minute)}
		}, expectedState: metric.RestartStateSettling},
		{name: "a_service_still_starting_is_not_judged", change: func(in *restartInput) { in.health = "starting" }, expectedState: metric.RestartStateOK},
		{name: "unhealthy_for_less_than_one_interval_is_only_suspect", change: func(in *restartInput) { in.unhealthySince = in.now.Add(-time.Minute) }, expectedState: metric.RestartStateSuspect},
		{name: "unhealthy_inside_its_settle_is_only_suspect", change: func(in *restartInput) { in.startedAt = in.now.Add(-5 * time.Minute) }, expectedState: metric.RestartStateSuspect},
		{name: "a_settle_min_longer_than_the_health_check_holds_judgement", change: func(in *restartInput) {
			in.startedAt = in.now.Add(-20 * time.Minute)
			in.policy.settleMin = 30 * time.Minute
		}, expectedState: metric.RestartStateSuspect},
		{name: "a_restart_made_inside_the_settle_is_being_judged", change: func(in *restartInput) { in.attempts = []time.Time{in.now.Add(-3 * time.Minute)} }, expectedState: metric.RestartStateSettling},
		{name: "a_just_started_supervisor_waits_one_interval", change: func(in *restartInput) { in.supervisorStarted = in.now.Add(-time.Minute) }, expectedState: metric.RestartStateWaiting},
		{name: "a_host_asleep_or_waking_holds_every_restart", change: func(in *restartInput) { in.hostHold = true }, expectedState: metric.RestartStateWaiting},
		{name: "an_unmet_prerequisite_holds_the_restart", change: func(in *restartInput) { in.requiresMet = false }, expectedState: metric.RestartStateWaiting},
		{name: "a_prerequisite_not_held_for_the_stable_period_holds_the_restart", change: func(in *restartInput) { in.requiresHeldSince = in.now.Add(-30 * time.Second) }, expectedState: metric.RestartStateWaiting},
		{name: "a_service_with_no_requirements_is_restarted_once_unhealthy", change: func(in *restartInput) {
			in.requiresHeldSince = in.now.Add(-time.Hour)
			in.policy = restartPolicy{}
		}, expectedState: metric.RestartStateRestarting, expectedAct: true},
		{name: "the_back_off_after_a_restart_holds_the_next", change: func(in *restartInput) {
			in.attempts = []time.Time{in.now.Add(-8 * time.Minute)}
			in.streak = 2
		}, expectedState: metric.RestartStateWaiting},
		{name: "the_back_off_has_passed", change: func(in *restartInput) {
			in.attempts = []time.Time{in.now.Add(-8 * time.Minute)}
			in.streak = 1
		}, expectedState: metric.RestartStateRestarting, expectedAct: true},
		{name: "three_restarts_in_the_window_exhaust_the_budget", change: func(in *restartInput) {
			in.attempts = []time.Time{in.now.Add(-20 * time.Hour), in.now.Add(-12 * time.Hour), in.now.Add(-9 * time.Hour)}
			in.streak = 3
		}, expectedState: metric.RestartStateExhausted},
		{name: "restarts_older_than_the_window_do_not_count", change: func(in *restartInput) {
			in.attempts = []time.Time{in.now.Add(-30 * time.Hour), in.now.Add(-28 * time.Hour), in.now.Add(-26 * time.Hour)}
		}, expectedState: metric.RestartStateRestarting, expectedAct: true},
		{name: "one_restart_in_flight_on_the_host_holds_the_next", change: func(in *restartInput) { in.hostInFlight = true }, expectedState: metric.RestartStateWaiting},
		{name: "a_restart_on_the_host_a_moment_ago_holds_the_next", change: func(in *restartInput) { in.hostLast = in.now.Add(-10 * time.Second) }, expectedState: metric.RestartStateWaiting},
		{name: "a_restart_on_the_host_a_while_ago_does_not", change: func(in *restartInput) { in.hostLast = in.now.Add(-5 * time.Minute) }, expectedState: metric.RestartStateRestarting, expectedAct: true},
		{name: "a_host_that_has_used_its_hourly_restarts_holds_the_next", change: func(in *restartInput) { in.hostHour = restartHostHourlyMax }, expectedState: metric.RestartStateWaiting},
		{name: "the_fast_path_restarts_a_service_that_started_before_its_prerequisite", change: func(in *restartInput) {
			in.fastPath = true
			in.health = "starting"
			in.startedAt = in.now.Add(-10 * time.Minute)
			in.unhealthySince = time.Time{}
		}, expectedState: metric.RestartStateRestarting, expectedAct: true},
		{name: "the_fast_path_is_off_unless_enabled", change: func(in *restartInput) {
			in.health = "starting"
			in.startedAt = in.now.Add(-10 * time.Minute)
			in.unhealthySince = time.Time{}
		}, expectedState: metric.RestartStateOK},
		{name: "the_fast_path_never_fires_for_a_service_that_started_after_its_prerequisite", change: func(in *restartInput) {
			in.fastPath = true
			in.health = "starting"
			in.startedAt = in.now.Add(-2 * time.Minute)
			in.unhealthySince = time.Time{}
		}, expectedState: metric.RestartStateOK},
		{name: "the_fast_path_needs_its_prerequisite_met", change: func(in *restartInput) {
			in.fastPath = true
			in.health = "starting"
			in.startedAt = in.now.Add(-10 * time.Minute)
			in.unhealthySince = time.Time{}
			in.requiresMet = false
		}, expectedState: metric.RestartStateOK},
		{name: "the_fast_path_still_waits_for_its_prerequisite_to_be_stable", change: func(in *restartInput) {
			in.fastPath = true
			in.health = "starting"
			in.startedAt = in.now.Add(-10 * time.Minute)
			in.unhealthySince = time.Time{}
			in.requiresHeldSince = in.now.Add(-20 * time.Second)
		}, expectedState: metric.RestartStateWaiting},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			in := restartBase()
			test.change(&in)
			decision := decideRestart(in)
			if decision.state != test.expectedState || decision.act != test.expectedAct || decision.reset != test.expectedReset {
				t.Fatalf("decision: got state [%s] act [%v] reset [%v] reason [%s] want state [%s] act [%v] reset [%v]",
					decision.state, decision.act, decision.reset, decision.reason, test.expectedState, test.expectedAct, test.expectedReset)
			}
		})
	}
}

func TestProbeUtilRestartDecide_Backoff(t *testing.T) {
	settle := 7 * time.Minute
	tests := []struct {
		name         string
		streak       int
		jitter       float64
		expectedWait time.Duration
	}{
		{name: "the_first_streak_waits_one_settle", streak: 1, expectedWait: 7 * time.Minute},
		{name: "each_further_attempt_doubles_it", streak: 3, expectedWait: 28 * time.Minute},
		{name: "it_is_capped_at_an_hour", streak: 6, expectedWait: time.Hour},
		{name: "a_very_long_streak_does_not_overflow", streak: 80, expectedWait: time.Hour},
		{name: "jitter_scales_the_wait", streak: 1, jitter: 0.1, expectedWait: 7*time.Minute + 42*time.Second},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			if got := restartBackoff(settle, test.streak, test.jitter); got != test.expectedWait {
				t.Fatalf("wait: got %s want %s", got, test.expectedWait)
			}
		})
	}
	if got := restartBackoff(10*time.Second, 1, 0); got != restartBackoffFloor {
		t.Fatalf("wait under the floor: got %s want %s", got, restartBackoffFloor)
	}
}
