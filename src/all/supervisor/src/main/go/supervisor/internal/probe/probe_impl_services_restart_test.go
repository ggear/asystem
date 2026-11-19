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
		Config:            &container.Config{Healthcheck: healthcheck},
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

func TestProbeImplServicesRestart_FastPath(t *testing.T) {
	tests := []struct {
		name         string
		fast         string
		expectedFast bool
	}{
		{name: "unset_has_no_fast_path"},
		{name: "the_fast_path_is_on_only_when_asked", fast: "on", expectedFast: true},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			t.Setenv(restartFastPathEnv, test.fast)
			engine := newRestartEngine()
			if engine.fastPath != test.expectedFast {
				t.Fatalf("engine: got fast %v want fast %v", engine.fastPath, test.expectedFast)
			}
		})
	}
}

func TestProbeImplServicesRestart_Count(t *testing.T) {
	tests := []struct {
		name          string
		dockerCount   int
		supervised    int
		expectedCount float64
	}{
		{name: "docker_alone", dockerCount: 2, expectedCount: 2},
		{name: "supervisor_alone", supervised: 3, expectedCount: 3},
		{name: "the_two_add_up", dockerCount: 2, supervised: 1, expectedCount: 3},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			probe := newServicesProbe()
			probe.restart = &restartEngine{ledger: newRestartLedger(t.TempDir() + "/ledger.json")}
			for range test.supervised {
				if err := probe.restart.ledger.record("plex", "abc", time.Unix(1, 0)); err != nil {
					t.Fatalf("record failed with [%v]", err)
				}
			}
			inspect := restartInspect("healthy", "2026-11-19T01:00:00Z", &container.HealthConfig{})
			inspect.RestartCount = test.dockerCount
			got, _, err := probe.restartCount("plex", inspect)
			if err != nil || got != test.expectedCount {
				t.Fatalf("restart count: got %f error [%v] want %f", got, err, test.expectedCount)
			}
		})
	}
}
