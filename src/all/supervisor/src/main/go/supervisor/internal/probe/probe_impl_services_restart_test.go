package probe

import (
	"testing"
	"time"

	"github.com/docker/docker/api/types/container"
	"supervisor/internal/metric"
)

func restartInspect(health string, startedAt string, healthcheck *container.HealthConfig) container.InspectResponse {
	response := container.InspectResponse{
		ContainerJSONBase: &container.ContainerJSONBase{ID: "abc", State: &container.State{StartedAt: startedAt}},
		Config:            &container.Config{Image: "plex:1", Healthcheck: healthcheck},
	}
	if health != "" {
		response.State.Health = &container.Health{Status: health}
	}
	return response
}

func TestProbeImplServicesRestart_ObservationOf(t *testing.T) {
	started := "2026-11-19T01:00:00.123456789Z"
	tests := []struct {
		name             string
		health           string
		startedAt        string
		healthcheck      *container.HealthConfig
		expectedObserved bool
		expectedHealth   string
		expectedCheck    restartHealthcheck
	}{
		{name: "a_container_with_a_health_check_is_observed", health: "unhealthy", startedAt: started, healthcheck: &container.HealthConfig{Interval: 2 * time.Minute, StartPeriod: time.Minute, Retries: 3}, expectedObserved: true, expectedHealth: "unhealthy", expectedCheck: restartHealthcheck{interval: 2 * time.Minute, startPeriod: time.Minute, retries: 3}},
		{name: "unset_timings_take_dockers_defaults", health: "starting", startedAt: started, healthcheck: &container.HealthConfig{}, expectedObserved: true, expectedHealth: "starting", expectedCheck: restartHealthcheck{interval: restartDockerDefaultInterval, retries: restartDockerDefaultRetries}},
		{name: "a_container_with_no_health_check_is_not_observed", startedAt: started, healthcheck: nil, expectedObserved: false},
		{name: "a_container_with_no_health_state_is_not_observed", startedAt: started, healthcheck: &container.HealthConfig{Interval: time.Minute}, expectedObserved: false},
		{name: "an_unreadable_start_time_is_not_observed", health: "healthy", startedAt: "yesterday", healthcheck: &container.HealthConfig{Interval: time.Minute}, expectedObserved: false},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			observation, observed := restartObservationOf("plex", restartInspect(test.health, test.startedAt, test.healthcheck))
			if observed != test.expectedObserved {
				t.Fatalf("observed: got %v want %v", observed, test.expectedObserved)
			}
			if observed && observation.image != "plex:1" {
				t.Fatalf("image: got [%s] want [plex:1]", observation.image)
			}
			if observed && (observation.health != test.expectedHealth || observation.healthcheck != test.expectedCheck || observation.container != "abc" || observation.service != "plex" || observation.startedAt.IsZero()) {
				t.Fatalf("observation: got %+v want health [%s] check %+v", observation, test.expectedHealth, test.expectedCheck)
			}
		})
	}
	if _, observed := restartObservationOf("plex", container.InspectResponse{}); observed {
		t.Fatalf("an inspect with no base section: got observed want not")
	}
}

func TestProbeImplServicesRestart_Attempts(t *testing.T) {
	tests := []struct {
		name             string
		latest           map[string]restartStatus
		expectedAttempts int8
	}{
		{name: "a_service_that_is_not_enrolled_reads_zero", latest: map[string]restartStatus{}, expectedAttempts: 0},
		{name: "an_enrolled_service_reads_its_attempts", latest: map[string]restartStatus{"plex": {state: metric.RestartStateWaiting, reason: "x", attempts: 2}}, expectedAttempts: 2},
		{name: "a_spent_budget_reads_three", latest: map[string]restartStatus{"plex": {state: metric.RestartStateExhausted, attempts: restartAttemptsMax}}, expectedAttempts: restartAttemptsMax},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			probe := newServicesProbe()
			probe.restart = &restartEngine{latest: test.latest}
			attempts, _, err := probe.restartAttempts("plex")
			if err != nil || attempts != test.expectedAttempts {
				t.Fatalf("attempts: got %d error [%v] want %d", attempts, err, test.expectedAttempts)
			}
		})
	}
}

func TestProbeImplServicesRestart_Count(t *testing.T) {
	tests := []struct {
		name          string
		firstSeen     int
		dockerCount   int
		supervised    int
		age           time.Duration
		expectedCount float64
	}{
		{name: "a_total_already_there_at_first_sight_is_not_counted", firstSeen: 4, dockerCount: 4, expectedCount: 0},
		{name: "docker_alone", dockerCount: 2, expectedCount: 2},
		{name: "supervisor_alone", supervised: 3, expectedCount: 3},
		{name: "the_two_add_up", dockerCount: 2, supervised: 1, expectedCount: 3},
		{name: "only_the_rise_since_first_sight_counts", firstSeen: 4, dockerCount: 6, expectedCount: 2},
		{name: "a_rise_ages_out_on_the_engine_clock", dockerCount: 2, age: 25 * time.Hour, expectedCount: 0},
		{name: "a_supervisor_attempt_ages_out_on_the_engine_clock", supervised: 1, age: 25 * time.Hour, expectedCount: 0},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			probe := newServicesProbe()
			clock := time.Date(2026, 11, 19, 12, 0, 0, 0, time.UTC)
			probe.restart = &restartEngine{ledger: newRestartLedger(t.TempDir() + "/ledger.json"), now: func() time.Time { return clock }}
			for range test.supervised {
				if err := probe.restart.ledger.record("plex", "abc", clock); err != nil {
					t.Fatalf("record failed with [%v]", err)
				}
			}
			inspect := restartInspect("healthy", "2026-11-19T01:00:00Z", &container.HealthConfig{})
			inspect.RestartCount = test.firstSeen
			if _, _, err := probe.restartCount("plex", inspect); err != nil {
				t.Fatalf("first restart count failed with [%v]", err)
			}
			inspect.RestartCount = test.dockerCount
			got, _, err := probe.restartCount("plex", inspect)
			if err == nil && test.age > 0 {
				clock = clock.Add(test.age)
				got, _, err = probe.restartCount("plex", inspect)
			}
			if err != nil || got != test.expectedCount {
				t.Fatalf("restart count: got %f error [%v] want %f", got, err, test.expectedCount)
			}
		})
	}
}

func TestProbeImplServicesRestart_ObservationProbe(t *testing.T) {
	ended := time.Date(2026, 11, 19, 1, 2, 3, 0, time.UTC)
	tests := []struct {
		name           string
		log            []*container.HealthcheckResult
		failingStreak  int
		expectedFailed bool
		expectedEnd    time.Time
	}{
		{name: "no_probe_yet_reads_as_not_failed"},
		{name: "the_last_probe_failing_is_failed", log: []*container.HealthcheckResult{{ExitCode: 0, End: ended.Add(-time.Minute)}, {ExitCode: 1, End: ended}}, expectedFailed: true, expectedEnd: ended},
		{name: "the_failing_streak_is_carried_while_docker_still_says_healthy", failingStreak: 2},
		{name: "the_last_probe_passing_is_not_failed", log: []*container.HealthcheckResult{{ExitCode: 1, End: ended.Add(-time.Minute)}, {ExitCode: 0, End: ended}}, expectedEnd: ended},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			inspect := restartInspect("starting", "2026-11-19T01:00:00Z", &container.HealthConfig{Interval: time.Minute})
			inspect.State.Health.Log = test.log
			inspect.State.Health.FailingStreak = test.failingStreak
			observation, _ := restartObservationOf("plex", inspect)
			if observation.probeFailed != test.expectedFailed || !observation.probeEnd.Equal(test.expectedEnd) || observation.failingStreak != test.failingStreak {
				t.Fatalf("probe: got failed %v end %v want failed %v end %v", observation.probeFailed, observation.probeEnd, test.expectedFailed, test.expectedEnd)
			}
		})
	}
}
