package probe

import (
	"context"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"testing"
	"time"

	"supervisor/internal/metric"
)

type restartRig struct {
	t       *testing.T
	engine  *restartEngine
	clock   time.Time
	script  *restartScript
	emitted []string
	runs    []string
	runExit int
	mutex   sync.Mutex
}

func newRestartRig(t *testing.T, policyText string) *restartRig {
	t.Helper()
	rig := &restartRig{t: t, clock: time.Date(2026, 11, 19, 12, 0, 0, 0, time.UTC), script: &restartScript{}}
	install := t.TempDir()
	for _, service := range []string{"plex", "sonarr"} {
		directory := filepath.Join(install, service, "latest")
		if err := os.MkdirAll(directory, 0o755); err != nil {
			t.Fatalf("mkdir failed with [%v]", err)
		}
		if err := os.WriteFile(filepath.Join(directory, "restart.sh"), []byte("#"), 0o644); err != nil {
			t.Fatalf("write failed with [%v]", err)
		}
	}
	loader := newRestartPolicyLoader()
	loader.install = install
	loader.run = func(_ context.Context, _ time.Duration, _ string, args ...string) (string, int, bool) {
		if strings.HasSuffix(strings.Join(args, " "), "enabled") {
			return "", 0, false
		}
		return policyText, 0, false
	}
	rig.engine = &restartEngine{
		ledger:   newRestartLedger(filepath.Join(t.TempDir(), "ledger.json")),
		checker:  restartChecker{run: rig.script.run, dial: func(string, time.Duration) error { return nil }, fstab: filepath.Join(t.TempDir(), "fstab")},
		loader:   loader,
		started:  rig.clock.Add(-time.Hour),
		now:      func() time.Time { return rig.clock },
		bootID:   func() string { return "boot-1" },
		held:     func() bool { return false },
		limit:    func(string) (time.Duration, error) { return 5 * time.Minute, nil },
		tracked:  make(map[string]*restartTracked),
		emit:     func(service string, line string) { rig.record(&rig.emitted, service+" "+line) },
		fastPath: false,
	}
	_ = rig.engine.ledger.booted("boot-1")
	rig.engine.run = func(_ context.Context, service string, _ time.Duration) (int, string) {
		rig.record(&rig.runs, service)
		return rig.runExit, "Restarted [" + service + "]"
	}
	return rig
}

func (r *restartRig) record(target *[]string, line string) {
	r.mutex.Lock()
	defer r.mutex.Unlock()
	*target = append(*target, line)
}

func (r *restartRig) observation(service string, health string) restartObservation {
	return restartObservation{
		service:     service,
		container:   service + "-1",
		health:      health,
		startedAt:   r.clock.Add(-time.Hour),
		healthcheck: restartHealthcheck{interval: 2 * time.Minute, startPeriod: time.Minute, retries: 3},
	}
}

func (r *restartRig) evaluate(observations ...restartObservation) map[string]restartStatus {
	statuses := r.engine.evaluate(context.Background(), observations)
	r.engine.workers.Wait()
	return statuses
}

func (r *restartRig) advance(by time.Duration) { r.clock = r.clock.Add(by) }

func (r *restartRig) restarted() []string {
	r.mutex.Lock()
	defer r.mutex.Unlock()
	return append([]string(nil), r.runs...)
}

func TestProbeUtilRestart_Evaluate(t *testing.T) {
	tests := []struct {
		name            string
		policy          string
		prepare         func(*restartRig)
		steps           func(*restartRig) map[string]restartStatus
		expectedState   string
		expectedRuns    []string
		expectedAttempt int
	}{
		{
			name: "act_mode_restarts_an_unhealthy_service_after_its_grace_and_counts_the_attempt",
			steps: func(r *restartRig) map[string]restartStatus {
				r.evaluate(r.observation("plex", "unhealthy"))
				r.advance(3 * time.Minute)
				return r.evaluate(r.observation("plex", "unhealthy"))
			},
			expectedState: metric.RestartStateRestarting, expectedRuns: []string{"plex"}, expectedAttempt: 1,
		},
		{
			name: "a_healthy_service_is_never_restarted",
			steps: func(r *restartRig) map[string]restartStatus {
				r.advance(time.Hour)
				return r.evaluate(r.observation("plex", "healthy"))
			},
			expectedState: metric.RestartStateOK, expectedRuns: nil, expectedAttempt: 0,
		},
		{
			name:    "a_host_that_is_asleep_or_waking_restarts_nothing",
			prepare: func(r *restartRig) { r.engine.held = func() bool { return true } },
			steps: func(r *restartRig) map[string]restartStatus {
				r.evaluate(r.observation("plex", "unhealthy"))
				r.advance(3 * time.Minute)
				return r.evaluate(r.observation("plex", "unhealthy"))
			},
			expectedState: metric.RestartStateWaiting, expectedRuns: nil, expectedAttempt: 0,
		},
		{
			name: "a_ledger_that_cannot_be_written_fails_closed",
			prepare: func(r *restartRig) {
				r.engine.ledger = newRestartLedger(filepath.Join(os.DevNull, "ledger.json"))
			},
			steps: func(r *restartRig) map[string]restartStatus {
				r.evaluate(r.observation("plex", "unhealthy"))
				r.advance(3 * time.Minute)
				return r.evaluate(r.observation("plex", "unhealthy"))
			},
			expectedState: metric.RestartStateWaiting, expectedRuns: nil, expectedAttempt: 0,
		},
		{
			name: "unreadable_install_limits_fail_closed",
			prepare: func(r *restartRig) {
				r.engine.limit = func(string) (time.Duration, error) { return 0, os.ErrNotExist }
			},
			steps: func(r *restartRig) map[string]restartStatus {
				r.evaluate(r.observation("plex", "unhealthy"))
				r.advance(3 * time.Minute)
				return r.evaluate(r.observation("plex", "unhealthy"))
			},
			expectedState: metric.RestartStateWaiting, expectedRuns: nil, expectedAttempt: 0,
		},
		{
			name:    "a_restart_the_installer_skipped_is_refunded",
			prepare: func(r *restartRig) { r.runExit = restartExitSkipped },
			steps: func(r *restartRig) map[string]restartStatus {
				r.evaluate(r.observation("plex", "unhealthy"))
				r.advance(3 * time.Minute)
				r.evaluate(r.observation("plex", "unhealthy"))
				r.advance(time.Second)
				return r.evaluate(r.observation("plex", "unhealthy"))
			},
			expectedState: metric.RestartStateRestarting, expectedRuns: []string{"plex", "plex"}, expectedAttempt: 1,
		},
		{
			name: "only_one_service_is_restarted_per_pass_and_the_first_in_name_order_goes_first",
			steps: func(r *restartRig) map[string]restartStatus {
				r.evaluate(r.observation("sonarr", "unhealthy"), r.observation("plex", "unhealthy"))
				r.advance(3 * time.Minute)
				return r.evaluate(r.observation("sonarr", "unhealthy"), r.observation("plex", "unhealthy"))
			},
			expectedState: metric.RestartStateRestarting, expectedRuns: []string{"plex"}, expectedAttempt: 1,
		},
		{
			name: "an_unmet_prerequisite_holds_the_restart", policy: "requires=tcp:broker:32404\n",
			prepare: func(r *restartRig) {
				r.engine.checker.dial = func(string, time.Duration) error { return os.ErrNotExist }
			},
			steps: func(r *restartRig) map[string]restartStatus {
				r.evaluate(r.observation("plex", "unhealthy"))
				r.advance(10 * time.Minute)
				return r.evaluate(r.observation("plex", "unhealthy"))
			},
			expectedState: metric.RestartStateWaiting, expectedRuns: nil, expectedAttempt: 0,
		},
		{
			name: "a_prerequisite_must_hold_for_the_stable_period_before_the_restart", policy: "requires=tcp:broker:32404\nrequires_stable=5m\n",
			steps: func(r *restartRig) map[string]restartStatus {
				r.evaluate(r.observation("plex", "unhealthy"))
				r.advance(3 * time.Minute)
				return r.evaluate(r.observation("plex", "unhealthy"))
			},
			expectedState: metric.RestartStateWaiting, expectedRuns: nil, expectedAttempt: 0,
		},
		{
			name: "a_prerequisite_that_has_held_long_enough_allows_the_restart", policy: "requires=tcp:broker:32404\nrequires_stable=5m\n",
			steps: func(r *restartRig) map[string]restartStatus {
				r.evaluate(r.observation("plex", "unhealthy"))
				r.advance(6 * time.Minute)
				return r.evaluate(r.observation("plex", "unhealthy"))
			},
			expectedState: metric.RestartStateRestarting, expectedRuns: []string{"plex"}, expectedAttempt: 1,
		},
		{
			name: "a_prerequisite_that_drops_restarts_the_stable_clock", policy: "requires=tcp:broker:32404\nrequires_stable=5m\n",
			steps: func(r *restartRig) map[string]restartStatus {
				r.evaluate(r.observation("plex", "unhealthy"))
				r.advance(3 * time.Minute)
				r.engine.checker.dial = func(string, time.Duration) error { return os.ErrNotExist }
				r.evaluate(r.observation("plex", "unhealthy"))
				r.engine.checker.dial = func(string, time.Duration) error { return nil }
				r.advance(3 * time.Minute)
				return r.evaluate(r.observation("plex", "unhealthy"))
			},
			expectedState: metric.RestartStateWaiting, expectedRuns: nil, expectedAttempt: 0,
		},
		{
			name: "a_module_hook_that_is_not_ready_holds_the_restart", policy: "requires=tcp:broker:32404\n",
			prepare: func(r *restartRig) {
				plain := r.engine.loader.run
				r.engine.loader.run = func(ctx context.Context, limit time.Duration, name string, args ...string) (string, int, bool) {
					if args[len(args)-1] == "ready" {
						return "", 1, false
					}
					return plain(ctx, limit, name, args...)
				}
			},
			steps: func(r *restartRig) map[string]restartStatus {
				r.evaluate(r.observation("plex", "unhealthy"))
				r.advance(10 * time.Minute)
				return r.evaluate(r.observation("plex", "unhealthy"))
			},
			expectedState: metric.RestartStateWaiting, expectedRuns: nil, expectedAttempt: 0,
		},
		{
			name: "a_budget_spent_in_the_ledger_exhausts_the_service",
			prepare: func(r *restartRig) {
				for index := range restartAttemptsMax {
					_ = r.engine.ledger.record("plex", "plex-1", r.clock.Add(-time.Duration(20-index)*time.Hour))
				}
			},
			steps: func(r *restartRig) map[string]restartStatus {
				r.evaluate(r.observation("plex", "unhealthy"))
				r.advance(3 * time.Minute)
				return r.evaluate(r.observation("plex", "unhealthy"))
			},
			expectedState: metric.RestartStateExhausted, expectedRuns: nil, expectedAttempt: restartAttemptsMax,
		},
		{
			name: "a_recreated_container_starts_with_a_fresh_budget",
			prepare: func(r *restartRig) {
				for index := range restartAttemptsMax {
					_ = r.engine.ledger.record("plex", "plex-0", r.clock.Add(-time.Duration(20-index)*time.Hour))
				}
			},
			steps: func(r *restartRig) map[string]restartStatus {
				r.evaluate(r.observation("plex", "unhealthy"))
				r.advance(3 * time.Minute)
				return r.evaluate(r.observation("plex", "unhealthy"))
			},
			expectedState: metric.RestartStateRestarting, expectedRuns: []string{"plex"}, expectedAttempt: 1,
		},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			rig := newRestartRig(t, test.policy)
			if test.prepare != nil {
				test.prepare(rig)
			}
			statuses := test.steps(rig)
			status, found := statuses["plex"]
			if !found {
				t.Fatalf("no status for plex in %v", statuses)
			}
			if status.state != test.expectedState || status.attempts != test.expectedAttempt || strings.Join(rig.restarted(), ",") != strings.Join(test.expectedRuns, ",") {
				t.Fatalf("got state [%s] reason [%s] attempts [%d] runs %v want state [%s] attempts [%d] runs %v",
					status.state, status.reason, status.attempts, rig.restarted(), test.expectedState, test.expectedAttempt, test.expectedRuns)
			}
		})
	}
}

func TestProbeUtilRestart_NotEnrolled(t *testing.T) {
	rig := newRestartRig(t, "")
	rig.engine.loader.run = func(context.Context, time.Duration, string, ...string) (string, int, bool) { return "", 1, false }
	if statuses := rig.evaluate(rig.observation("plex", "unhealthy")); len(statuses) != 0 {
		t.Fatalf("statuses for a service that is not enrolled: got %v want none", statuses)
	}
}

func TestProbeUtilRestart_Settled(t *testing.T) {
	rig := newRestartRig(t, "")
	if err := rig.engine.ledger.record("plex", "plex-1", rig.clock.Add(-30*time.Minute)); err != nil {
		t.Fatalf("record failed with [%v]", err)
	}
	rig.evaluate(rig.observation("plex", "healthy"))
	rig.advance(5 * time.Minute)
	rig.evaluate(rig.observation("plex", "healthy"))
	if got := rig.engine.ledger.history("plex", "plex-1").streak; got != 0 {
		t.Fatalf("streak after a service stayed healthy for two intervals: got %d want 0", got)
	}
	if got := rig.engine.ledger.count("plex", "plex-1"); got != 1 {
		t.Fatalf("count after settling: got %d want 1", got)
	}
}

func TestProbeUtilRestart_Reported(t *testing.T) {
	rig := newRestartRig(t, "")
	for range 3 {
		rig.evaluate(rig.observation("plex", "healthy"))
	}
	if len(rig.emitted) != 1 {
		t.Fatalf("lines for a service that did not change: got %v want one state line", rig.emitted)
	}
	rig.advance(3 * time.Minute)
	rig.evaluate(rig.observation("plex", "unhealthy"))
	if len(rig.emitted) != 2 {
		t.Fatalf("lines after the state changed: got %v want two", rig.emitted)
	}
}

func TestProbeUtilRestart_ParseInstallLimit(t *testing.T) {
	tests := []struct {
		name          string
		script        string
		names         []string
		expected      time.Duration
		expectedError bool
	}{
		{name: "the_named_limits_plus_the_margin", script: "SERVICE_STOP_SECONDS=120\nSERVICE_WAIT_RESTART_SECONDS=120\n", names: []string{"SERVICE_STOP_SECONDS", "SERVICE_WAIT_RESTART_SECONDS"}, expected: 270 * time.Second},
		{name: "other_assignments_are_ignored", script: "SERVICE_STOP_GRACE_SECONDS=30\nSERVICE_STOP_SECONDS=60\nSERVICE_WAIT_RESTART_SECONDS=90\n", names: []string{"SERVICE_STOP_SECONDS", "SERVICE_WAIT_RESTART_SECONDS"}, expected: 180 * time.Second},
		{name: "a_name_given_twice_counts_twice", script: "SERVICE_STOP_SECONDS=100\n", names: []string{"SERVICE_STOP_SECONDS", "SERVICE_STOP_SECONDS"}, expected: 230 * time.Second},
		{name: "a_missing_limit_is_an_error", script: "SERVICE_STOP_SECONDS=120\n", names: []string{"SERVICE_STOP_SECONDS", "SERVICE_WAIT_RESTART_SECONDS"}, expectedError: true},
		{name: "a_script_with_neither_is_an_error", script: "echo hello\n", names: []string{"SERVICE_STOP_SECONDS"}, expectedError: true},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			got, err := parseInstallLimit(test.script, test.names...)
			if (err != nil) != test.expectedError || got != test.expected {
				t.Fatalf("limit: got %s error [%v] want %s error [%v]", got, err, test.expected, test.expectedError)
			}
		})
	}
}

func TestProbeUtilRestart_Jitter(t *testing.T) {
	seen := map[float64]bool{}
	for streak := range 40 {
		got := restartJitter("plex", streak)
		if got < -0.1 || got > 0.1 {
			t.Fatalf("jitter out of range: got %f", got)
		}
		seen[got] = true
	}
	if len(seen) < 5 {
		t.Fatalf("jitter takes too few values: got %d", len(seen))
	}
	if restartJitter("plex", 1) != restartJitter("plex", 1) {
		t.Fatalf("jitter is not deterministic")
	}
}

func TestProbeUtilRestart_HostBudget(t *testing.T) {
	tests := []struct {
		name          string
		holdRun       bool
		secondAfter   time.Duration
		expectedState string
		expectedRuns  []string
	}{
		{name: "a_restart_still_in_flight_holds_the_next_even_long_after_the_spacing", holdRun: true, secondAfter: 10 * time.Minute, expectedState: metric.RestartStateWaiting, expectedRuns: []string{"plex"}},
		{name: "a_restart_that_finished_a_moment_ago_still_holds_the_next_by_the_spacing", secondAfter: 10 * time.Second, expectedState: metric.RestartStateWaiting, expectedRuns: []string{"plex"}},
		{name: "a_restart_that_finished_long_ago_does_not_hold_the_next", secondAfter: 10 * time.Minute, expectedState: metric.RestartStateRestarting, expectedRuns: []string{"plex", "sonarr"}},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			rig := newRestartRig(t, "")
			release := make(chan struct{})
			if test.holdRun {
				rig.engine.run = func(_ context.Context, service string, _ time.Duration) (int, string) {
					rig.record(&rig.runs, service)
					<-release
					return 0, ""
				}
			}
			rig.engine.evaluate(context.Background(), []restartObservation{rig.observation("plex", "unhealthy"), rig.observation("sonarr", "unhealthy")})
			rig.advance(3 * time.Minute)
			rig.engine.evaluate(context.Background(), []restartObservation{rig.observation("plex", "unhealthy"), rig.observation("sonarr", "unhealthy")})
			rig.advance(time.Second)
			if !test.holdRun {
				rig.engine.workers.Wait()
			}
			rig.engine.evaluate(context.Background(), []restartObservation{rig.observation("plex", "healthy"), rig.observation("sonarr", "unhealthy")})
			rig.advance(test.secondAfter)
			statuses := rig.engine.evaluate(context.Background(), []restartObservation{rig.observation("plex", "healthy"), rig.observation("sonarr", "unhealthy")})
			if test.holdRun {
				close(release)
			}
			rig.engine.workers.Wait()
			if got := statuses["sonarr"].state; got != test.expectedState {
				t.Fatalf("second service: got state [%s] reason [%s] want [%s]", got, statuses["sonarr"].reason, test.expectedState)
			}
			if got := rig.restarted(); strings.Join(got, ",") != strings.Join(test.expectedRuns, ",") {
				t.Fatalf("restarts: got %v want %v", got, test.expectedRuns)
			}
		})
	}
}

func TestProbeUtilRestart_Tracking(t *testing.T) {
	tests := []struct {
		name          string
		policy        string
		steps         func(*restartRig) map[string]restartStatus
		expectedState string
	}{
		{
			name: "a_prerequisite_seen_while_the_service_was_healthy_does_not_count_towards_its_stable_period", policy: "requires=tcp:broker:32404\nrequires_stable=5m\n",
			steps: func(r *restartRig) map[string]restartStatus {
				r.evaluate(r.observation("plex", "unhealthy"))
				r.advance(time.Minute)
				r.evaluate(r.observation("plex", "healthy"))
				r.advance(4 * time.Minute)
				r.evaluate(r.observation("plex", "unhealthy"))
				r.advance(3 * time.Minute)
				return r.evaluate(r.observation("plex", "unhealthy"))
			},
			expectedState: metric.RestartStateWaiting,
		},
		{
			name: "a_recreated_container_is_not_judged_by_how_long_its_predecessor_was_unhealthy",
			steps: func(r *restartRig) map[string]restartStatus {
				r.evaluate(r.observation("plex", "unhealthy"))
				r.advance(3 * time.Minute)
				recreated := r.observation("plex", "unhealthy")
				recreated.container = "plex-2"
				return r.evaluate(recreated)
			},
			expectedState: metric.RestartStateSuspect,
		},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			rig := newRestartRig(t, test.policy)
			statuses := test.steps(rig)
			if got := statuses["plex"].state; got != test.expectedState || len(rig.restarted()) != 0 {
				t.Fatalf("got state [%s] reason [%s] runs %v want state [%s] and no restart", got, statuses["plex"].reason, rig.restarted(), test.expectedState)
			}
		})
	}
}

func TestProbeUtilRestart_NeverItself(t *testing.T) {
	rig := newRestartRig(t, "")
	rig.engine.loader.install = func() string {
		install := t.TempDir()
		directory := filepath.Join(install, "supervisor", "latest")
		if err := os.MkdirAll(directory, 0o755); err != nil {
			t.Fatalf("mkdir failed with [%v]", err)
		}
		if err := os.WriteFile(filepath.Join(directory, "restart.sh"), []byte("#"), 0o644); err != nil {
			t.Fatalf("write failed with [%v]", err)
		}
		return install
	}()
	rig.evaluate(rig.observation("supervisor", "unhealthy"))
	rig.advance(10 * time.Minute)
	if statuses := rig.evaluate(rig.observation("supervisor", "unhealthy")); len(statuses) != 0 || len(rig.restarted()) != 0 {
		t.Fatalf("supervisor: got statuses %v runs %v want none", statuses, rig.restarted())
	}
}
