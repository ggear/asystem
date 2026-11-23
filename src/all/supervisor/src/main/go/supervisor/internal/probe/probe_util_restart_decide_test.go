package probe

import (
	"testing"
	"time"
)

func TestProbeUtilRestartDecide_Decide(t *testing.T) {
	tests := []struct {
		name          string
		change        func(*restartInput)
		expectedState string
		expectedAct   bool
		expectedReset bool
	}{
		{name: "an_unhealthy_service_with_everything_held_is_restarted", change: func(*restartInput) {}, expectedState: restartStateRestarting, expectedAct: true},
		{name: "a_healthy_service_is_left_alone", change: func(in *restartInput) { in.health = restartHealthHealthy }, expectedState: restartStateOK},
		{name: "a_stable_healthy_service_resets_its_streak", change: func(in *restartInput) {
			in.health = restartHealthHealthy
			in.stableSince = in.now.Add(-5 * time.Minute)
		}, expectedState: restartStateOK, expectedReset: true},
		{name: "a_service_healthy_for_less_than_two_intervals_after_a_restart_is_still_settling", change: func(in *restartInput) {
			in.health = restartHealthHealthy
			in.stableSince = in.now.Add(-time.Minute)
			in.attempts = []time.Time{in.now.Add(-3 * time.Minute)}
		}, expectedState: restartStateSettling},
		{name: "a_service_still_starting_is_not_judged", change: func(in *restartInput) { in.health = "starting" }, expectedState: restartStateOK},
		{name: "a_service_docker_keeps_restarting_is_suspect_and_left_to_docker", change: func(in *restartInput) {
			in.health = "starting"
			in.startedAt = in.now.Add(-20 * time.Second)
			in.rises = []time.Time{in.now.Add(-20 * time.Second), in.now.Add(-40 * time.Second)}
		}, expectedState: restartStateSuspect},
		{name: "one_docker_restart_inside_the_window_is_not_a_loop", change: func(in *restartInput) {
			in.health = "starting"
			in.startedAt = in.now.Add(-20 * time.Second)
			in.rises = []time.Time{in.now.Add(-20 * time.Second), in.now.Add(-time.Hour)}
		}, expectedState: restartStateOK},
		{name: "unhealthy_for_less_than_one_interval_is_only_suspect", change: func(in *restartInput) { in.unhealthySince = in.now.Add(-time.Minute) }, expectedState: restartStateSuspect},
		{name: "unhealthy_inside_the_normal_grace_is_only_suspect", change: func(in *restartInput) { in.startedAt = in.now.Add(-5 * time.Minute) }, expectedState: restartStateSuspect},
		{name: "unhealthy_past_the_normal_grace_is_judged_without_waiting_for_the_start_period", change: func(in *restartInput) {
			in.healthcheck.startPeriod = 15 * time.Minute
			in.startedAt = in.now.Add(-7 * time.Minute)
		}, expectedState: restartStateRestarting, expectedAct: true},
		{name: "a_release_is_not_judged_inside_its_start_period", change: func(in *restartInput) {
			in.release = true
			in.healthcheck.startPeriod = 15 * time.Minute
			in.startedAt = in.now.Add(-10 * time.Minute)
		}, expectedState: restartStateSuspect},
		{name: "a_release_is_judged_once_its_start_period_has_passed", change: func(in *restartInput) {
			in.release = true
			in.healthcheck.startPeriod = 15 * time.Minute
			in.startedAt = in.now.Add(-16 * time.Minute)
		}, expectedState: restartStateRestarting, expectedAct: true},
		{name: "a_settle_min_longer_than_the_health_check_holds_judgement", change: func(in *restartInput) {
			in.startedAt = in.now.Add(-20 * time.Minute)
			in.policy.settleMin = 30 * time.Minute
		}, expectedState: restartStateSuspect},
		{name: "a_normal_start_is_judged_again_one_health_window_after_its_restart", change: func(in *restartInput) {
			in.healthcheck.startPeriod = 15 * time.Minute
			in.attempts = []time.Time{in.now.Add(-7 * time.Minute)}
		}, expectedState: restartStateRestarting, expectedAct: true},
		{name: "a_normal_start_is_still_being_judged_inside_one_health_window_of_its_restart", change: func(in *restartInput) {
			in.healthcheck.startPeriod = 15 * time.Minute
			in.attempts = []time.Time{in.now.Add(-5 * time.Minute)}
		}, expectedState: restartStateSettling},
		{name: "a_release_is_still_being_judged_for_its_start_period_after_a_restart", change: func(in *restartInput) {
			in.release = true
			in.healthcheck.startPeriod = 15 * time.Minute
			in.startedAt = in.now.Add(-20 * time.Minute)
			in.attempts = []time.Time{in.now.Add(-7 * time.Minute)}
		}, expectedState: restartStateSettling},
		{name: "a_restart_made_inside_the_settle_is_being_judged", change: func(in *restartInput) { in.attempts = []time.Time{in.now.Add(-3 * time.Minute)} }, expectedState: restartStateSettling},
		{name: "a_just_started_supervisor_waits_one_interval", change: func(in *restartInput) { in.supervisorStarted = in.now.Add(-time.Minute) }, expectedState: restartStateWaiting},
		{name: "a_host_asleep_or_waking_holds_every_restart", change: func(in *restartInput) { in.hostHold = true }, expectedState: restartStateWaiting},
		{name: "an_unmet_prerequisite_holds_the_restart", change: func(in *restartInput) { in.requiresMet = false }, expectedState: restartStateWaiting},
		{name: "a_prerequisite_not_held_for_the_stable_period_holds_the_restart", change: func(in *restartInput) { in.requiresHeldSince = in.now.Add(-30 * time.Second) }, expectedState: restartStateWaiting},
		{name: "a_service_with_no_requirements_is_restarted_once_unhealthy", change: func(in *restartInput) {
			in.requiresHeldSince = in.now.Add(-time.Hour)
			in.policy = restartPolicy{}
		}, expectedState: restartStateRestarting, expectedAct: true},
		{name: "the_back_off_after_a_restart_holds_the_next", change: func(in *restartInput) {
			in.attempts = []time.Time{in.now.Add(-8 * time.Minute)}
			in.streak = 2
		}, expectedState: restartStateWaiting},
		{name: "the_back_off_has_passed", change: func(in *restartInput) {
			in.attempts = []time.Time{in.now.Add(-8 * time.Minute)}
			in.streak = 1
		}, expectedState: restartStateRestarting, expectedAct: true},
		{name: "three_restarts_in_the_window_exhaust_the_budget", change: func(in *restartInput) {
			in.attempts = []time.Time{in.now.Add(-20 * time.Hour), in.now.Add(-12 * time.Hour), in.now.Add(-9 * time.Hour)}
			in.streak = 3
		}, expectedState: restartStateExhausted},
		{name: "restarts_older_than_the_window_do_not_count", change: func(in *restartInput) {
			in.attempts = []time.Time{in.now.Add(-30 * time.Hour), in.now.Add(-28 * time.Hour), in.now.Add(-26 * time.Hour)}
		}, expectedState: restartStateRestarting, expectedAct: true},
		{name: "one_restart_in_flight_on_the_host_holds_the_next", change: func(in *restartInput) { in.hostInFlight = true }, expectedState: restartStateWaiting},
		{name: "a_restart_on_the_host_a_moment_ago_holds_the_next", change: func(in *restartInput) { in.hostLast = in.now.Add(-10 * time.Second) }, expectedState: restartStateWaiting},
		{name: "a_restart_on_the_host_a_while_ago_does_not", change: func(in *restartInput) { in.hostLast = in.now.Add(-5 * time.Minute) }, expectedState: restartStateRestarting, expectedAct: true},
		{name: "a_host_that_has_used_its_hourly_restarts_holds_the_next", change: func(in *restartInput) { in.hostHour = restartHostHourlyMax }, expectedState: restartStateWaiting},
		{name: "a_lapsed_prerequisite_with_a_probe_still_failing_after_it_was_stable_restarts_the_service", change: lapsed(func(*restartInput) {}), expectedState: restartStateRestarting, expectedAct: true},
		{name: "a_prerequisite_that_never_lapsed_leaves_a_starting_service_to_docker", change: lapsed(func(in *restartInput) { in.requiresLapsed = false }), expectedState: restartStateOK},
		{name: "a_lapsed_prerequisite_needs_to_be_met", change: lapsed(func(in *restartInput) { in.requiresMet = false }), expectedState: restartStateOK},
		{name: "a_probe_that_ended_before_the_prerequisite_was_stable_proves_nothing", change: lapsed(func(in *restartInput) { in.probeEnd = in.requiresHeldSince.Add(30 * time.Second) }), expectedState: restartStateOK},
		{name: "a_passing_probe_proves_nothing", change: lapsed(func(in *restartInput) { in.probeFailed = false }), expectedState: restartStateOK},
		{name: "a_lapsed_prerequisite_with_no_settle_min_waits_out_the_normal_grace", change: lapsed(func(in *restartInput) { in.startedAt = in.now.Add(-3 * time.Minute) }), expectedState: restartStateOK},
		{name: "a_lapsed_prerequisite_with_a_settle_min_does_not_wait_out_the_normal_grace", change: lapsed(func(in *restartInput) {
			in.startedAt = in.now.Add(-3 * time.Minute)
			in.policy.settleMin = 30 * time.Second
		}), expectedState: restartStateRestarting, expectedAct: true},
		{name: "a_lapsed_prerequisite_waits_for_its_settle_min", change: lapsed(func(in *restartInput) {
			in.startedAt = in.now.Add(-3 * time.Minute)
			in.policy.settleMin = 5 * time.Minute
		}), expectedState: restartStateOK},
		{name: "a_lapsed_prerequisite_during_a_release_waits_out_the_start_period", change: lapsed(func(in *restartInput) {
			in.release = true
			in.healthcheck.startPeriod = 15 * time.Minute
		}), expectedState: restartStateOK},
		{name: "a_lapsed_prerequisite_waits_for_a_settle_min_longer_than_the_age", change: lapsed(func(in *restartInput) { in.policy.settleMin = 30 * time.Minute }), expectedState: restartStateOK},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			in := restartBase()
			testCase.change(&in)
			decision := decideRestart(in)
			if decision.state != testCase.expectedState || decision.act != testCase.expectedAct || decision.reset != testCase.expectedReset {
				t.Fatalf("decision: got state [%s] act [%v] reset [%v] reason [%s] want state [%s] act [%v] reset [%v]",
					decision.state, decision.act, decision.reset, decision.reason, testCase.expectedState, testCase.expectedAct, testCase.expectedReset)
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
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			if got := restartBackoff(settle, testCase.streak, testCase.jitter); got != testCase.expectedWait {
				t.Fatalf("wait: got %s want %s", got, testCase.expectedWait)
			}
		})
	}
	if got := restartBackoff(10*time.Second, 1, 0); got != restartBackoffFloor {
		t.Fatalf("wait under the floor: got %s want %s", got, restartBackoffFloor)
	}
}

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

func lapsed(change func(*restartInput)) func(*restartInput) {
	return func(in *restartInput) {
		in.health = "starting"
		in.startedAt = in.now.Add(-10 * time.Minute)
		in.unhealthySince = time.Time{}
		in.requiresLapsed = true
		in.probeFailed = true
		in.probeEnd = in.now.Add(-10 * time.Second)
		change(in)
	}
}
