package probe

import (
	"context"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"
)

func TestProbeUtilRestartLoad_Load(t *testing.T) {
	tests := []struct {
		name            string
		script          *string
		enabledExit     int
		enabledAbandon  bool
		policyText      string
		policyExit      int
		expectedEnabled bool
		expectedStable  time.Duration
		expectedError   bool
	}{
		{name: "no_script_is_not_enrolled", expectedEnabled: false},
		{name: "a_script_whose_switch_is_off_is_not_enrolled", script: new("#"), enabledExit: 1, expectedEnabled: false},
		{name: "an_enrolled_module_returns_its_policy", script: new("#"), policyText: "requires=mount:/share/10\nrequires_stable=90s\n", expectedEnabled: true, expectedStable: 90 * time.Second},
		{name: "an_enrolled_module_with_no_policy_gets_the_default", script: new("#"), expectedEnabled: true, expectedStable: restartStableDefault},
		{name: "an_abandoned_switch_hook_is_an_error", script: new("#"), enabledAbandon: true, expectedError: true},
		{name: "a_failing_policy_hook_is_an_error", script: new("#"), policyExit: 3, expectedError: true},
		{name: "an_invalid_policy_is_an_error", script: new("#"), policyText: "requires=dns:x\n", expectedError: true},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			install := t.TempDir()
			if test.script != nil {
				directory := filepath.Join(install, "plex", "latest")
				if err := os.MkdirAll(directory, 0o755); err != nil {
					t.Fatalf("mkdir failed with [%v]", err)
				}
				if err := os.WriteFile(filepath.Join(directory, "restart.sh"), []byte(*test.script), 0o644); err != nil {
					t.Fatalf("write failed with [%v]", err)
				}
			}
			loader := newRestartPolicyLoader()
			loader.install = install
			loader.run = func(_ context.Context, _ time.Duration, _ string, args ...string) (string, int, bool) {
				if strings.HasSuffix(strings.Join(args, " "), "enabled") {
					return "", test.enabledExit, test.enabledAbandon
				}
				return test.policyText, test.policyExit, false
			}
			policy, enabled, err := loader.load(context.Background(), "plex")
			if (err != nil) != test.expectedError || enabled != test.expectedEnabled {
				t.Fatalf("load: got enabled [%v] error [%v] want enabled [%v] error [%v]", enabled, err, test.expectedEnabled, test.expectedError)
			}
			if enabled && policy.stable != test.expectedStable {
				t.Fatalf("stable: got %s want %s", policy.stable, test.expectedStable)
			}
		})
	}
}

func TestProbeUtilRestartLoad_Cache(t *testing.T) {
	install := t.TempDir()
	directory := filepath.Join(install, "plex", "latest")
	if err := os.MkdirAll(directory, 0o755); err != nil {
		t.Fatalf("mkdir failed with [%v]", err)
	}
	script := filepath.Join(directory, "restart.sh")
	if err := os.WriteFile(script, []byte("#"), 0o644); err != nil {
		t.Fatalf("write failed with [%v]", err)
	}
	calls := 0
	loader := newRestartPolicyLoader()
	loader.install = install
	loader.run = func(context.Context, time.Duration, string, ...string) (string, int, bool) {
		calls++
		return "", 0, false
	}
	for range 3 {
		if _, _, err := loader.load(context.Background(), "plex"); err != nil {
			t.Fatalf("load failed with [%v]", err)
		}
	}
	if calls != 2 {
		t.Fatalf("hook runs for three loads of an unchanged script: got %d want 2", calls)
	}
	if err := os.WriteFile(script, []byte("# changed"), 0o644); err != nil {
		t.Fatalf("write failed with [%v]", err)
	}
	if _, _, err := loader.load(context.Background(), "plex"); err != nil {
		t.Fatalf("load failed with [%v]", err)
	}
	if calls != 4 {
		t.Fatalf("hook runs after the script changed: got %d want 4", calls)
	}
}

func TestProbeUtilRestartLoad_Ready(t *testing.T) {
	tests := []struct {
		name          string
		exit          int
		abandoned     bool
		expectedReady bool
	}{
		{name: "a_hook_that_returns_zero_is_ready", expectedReady: true},
		{name: "a_hook_that_returns_non_zero_is_not_ready", exit: 3, expectedReady: false},
		{name: "an_abandoned_hook_is_not_ready", abandoned: true, expectedReady: false},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			loader := newRestartPolicyLoader()
			loader.run = func(_ context.Context, _ time.Duration, _ string, args ...string) (string, int, bool) {
				if args[len(args)-1] != "ready" {
					t.Fatalf("hook: got [%v] want ready", args)
				}
				return "", test.exit, test.abandoned
			}
			if got := loader.ready(context.Background(), "plex"); got != test.expectedReady {
				t.Fatalf("ready: got %v want %v", got, test.expectedReady)
			}
		})
	}
}
