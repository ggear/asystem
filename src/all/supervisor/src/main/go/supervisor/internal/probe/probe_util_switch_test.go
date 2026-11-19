package probe

import (
	"context"
	"errors"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"testing"
	"time"
)

func TestProbeUtilSwitch_Parse(t *testing.T) {
	tests := []struct {
		name            string
		topic           string
		payload         string
		expectedRequest switchRequest
		expectedOther   bool
		expectedError   bool
	}{
		{name: "on_for_this_host", topic: "supervisor/macmini-may/command/service/sonarr", payload: "ON", expectedRequest: switchRequest{service: "sonarr", on: true}},
		{name: "off_for_this_host", topic: "supervisor/macmini-may/command/service/sonarr", payload: "OFF", expectedRequest: switchRequest{service: "sonarr"}},
		{name: "case_and_space_do_not_matter", topic: "supervisor/macmini-may/command/service/sonarr", payload: " on\n", expectedRequest: switchRequest{service: "sonarr", on: true}},
		{name: "another_hosts_command_is_not_ours", topic: "supervisor/macmini-mad/command/service/plex", payload: "ON", expectedOther: true},
		{name: "a_host_scope_is_not_a_service_command", topic: "supervisor/macmini-may/command/host/macmini-may", payload: "ON", expectedError: true},
		{name: "a_short_topic_is_refused", topic: "supervisor/macmini-may/command/service", payload: "ON", expectedError: true},
		{name: "an_empty_service_is_refused", topic: "supervisor/macmini-may/command/service/", payload: "ON", expectedError: true},
		{name: "any_other_payload_is_refused", topic: "supervisor/macmini-may/command/service/sonarr", payload: "RESTART", expectedError: true},
		{name: "an_empty_payload_is_refused", topic: "supervisor/macmini-may/command/service/sonarr", payload: "", expectedError: true},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			request, err := parseSwitchCommand("macmini-may", test.topic, []byte(test.payload))
			if got := errors.Is(err, errSwitchOther); got != test.expectedOther {
				t.Fatalf("other host: got %v want %v", got, test.expectedOther)
			}
			if failed := err != nil && !test.expectedOther; failed != test.expectedError {
				t.Fatalf("error: got [%v] want error [%v]", err, test.expectedError)
			}
			if err == nil && request != test.expectedRequest {
				t.Fatalf("request: got %+v want %+v", request, test.expectedRequest)
			}
		})
	}
}

type switchRig struct {
	switcher *switcher
	mutex    sync.Mutex
	runs     []string
	release  chan struct{}
	exit     int
}

func newSwitchRig(t *testing.T, running bool, asleep bool) *switchRig {
	t.Helper()
	rig := &switchRig{release: make(chan struct{})}
	rig.switcher = &switcher{
		busy:    make(map[string]bool),
		log:     newSwitchLog(t.TempDir()),
		running: func(context.Context, string) bool { return running },
		asleep:  func(string) bool { return asleep },
		known:   func(service string) bool { return service != "ghost" },
		limit: func(string, string) (time.Duration, error) {
			return time.Minute, nil
		},
		run: func(_ context.Context, service string, verb string, _ time.Duration) (int, string) {
			rig.mutex.Lock()
			rig.runs = append(rig.runs, service+" "+verb)
			rig.mutex.Unlock()
			<-rig.release
			return rig.exit, "Done [" + service + "]"
		},
	}
	return rig
}

func (r *switchRig) performed() []string {
	r.mutex.Lock()
	defer r.mutex.Unlock()
	return append([]string(nil), r.runs...)
}

func TestProbeUtilSwitch_Handle(t *testing.T) {
	tests := []struct {
		name             string
		running          bool
		asleep           bool
		request          switchRequest
		limitError       error
		expectedDecision string
		expectedRuns     []string
	}{
		{name: "on_wakes_a_service_that_is_asleep", asleep: true, request: switchRequest{service: "plex", on: true}, expectedDecision: "accepted", expectedRuns: []string{"plex start"}},
		{name: "on_starts_a_service_that_is_down_without_the_marker", request: switchRequest{service: "plex", on: true}, expectedDecision: "accepted", expectedRuns: []string{"plex start"}},
		{name: "on_does_nothing_to_a_service_already_running", running: true, request: switchRequest{service: "plex", on: true}, expectedDecision: "already on"},
		{name: "off_puts_a_running_service_to_sleep", running: true, request: switchRequest{service: "plex"}, expectedDecision: "accepted", expectedRuns: []string{"plex sleep"}},
		{name: "off_marks_a_stopped_service_that_has_no_marker", request: switchRequest{service: "plex"}, expectedDecision: "accepted", expectedRuns: []string{"plex sleep"}},
		{name: "off_does_nothing_to_a_service_already_asleep", asleep: true, request: switchRequest{service: "plex"}, expectedDecision: "already asleep"},
		{name: "off_on_a_running_service_that_has_the_marker_still_sleeps_it", running: true, asleep: true, request: switchRequest{service: "plex"}, expectedDecision: "accepted", expectedRuns: []string{"plex sleep"}},
		{name: "an_unknown_service_is_refused", request: switchRequest{service: "ghost", on: true}, expectedDecision: "unknown service"},
		{name: "unreadable_install_limits_fail_closed", request: switchRequest{service: "plex", on: true}, limitError: os.ErrNotExist, expectedDecision: "limits unreadable"},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			rig := newSwitchRig(t, test.running, test.asleep)
			if test.limitError != nil {
				rig.switcher.limit = func(string, string) (time.Duration, error) { return 0, test.limitError }
			}
			decision := rig.switcher.handle(context.Background(), test.request)
			close(rig.release)
			rig.switcher.workers.Wait()
			if decision != test.expectedDecision || strings.Join(rig.performed(), ",") != strings.Join(test.expectedRuns, ",") {
				t.Fatalf("got decision [%s] runs %v want decision [%s] runs %v", decision, rig.performed(), test.expectedDecision, test.expectedRuns)
			}
		})
	}
}

func TestProbeUtilSwitch_OneCommandPerServiceAtATime(t *testing.T) {
	rig := newSwitchRig(t, true, false)
	first := rig.switcher.handle(context.Background(), switchRequest{service: "plex"})
	second := rig.switcher.handle(context.Background(), switchRequest{service: "plex"})
	other := rig.switcher.handle(context.Background(), switchRequest{service: "sonarr"})
	close(rig.release)
	rig.switcher.workers.Wait()
	again := rig.switcher.handle(context.Background(), switchRequest{service: "plex"})
	rig.switcher.workers.Wait()
	if first != "accepted" || second != "busy" || other != "accepted" || again != "accepted" {
		t.Fatalf("decisions: got [%s] [%s] [%s] [%s] want accepted busy accepted accepted", first, second, other, again)
	}
	if got := len(rig.performed()); got != 3 {
		t.Fatalf("runs: got %d want 3 (%v)", got, rig.performed())
	}
}

func TestProbeUtilSwitch_LogsWhatHappened(t *testing.T) {
	rig := newSwitchRig(t, true, false)
	rig.exit = 1
	home := t.TempDir()
	rig.switcher.log = newSwitchLog(home)
	rig.switcher.handle(context.Background(), switchRequest{service: "plex"})
	close(rig.release)
	rig.switcher.workers.Wait()
	data, err := os.ReadFile(filepath.Join(home, "plex", "switch", "switch.log"))
	if err != nil {
		t.Fatalf("read failed with [%v]", err)
	}
	if !strings.Contains(string(data), "Done [plex]") {
		t.Fatalf("switch.log lacks the script's own output: %s", data)
	}
}

func TestProbeUtilSwitch_ServiceAsleep(t *testing.T) {
	original := installRoot
	installRoot = t.TempDir()
	t.Cleanup(func() { installRoot = original })
	if serviceAsleep("plex") {
		t.Fatalf("a service with no install directory: got asleep want not")
	}
	if err := os.MkdirAll(filepath.Join(installRoot, "plex"), 0o755); err != nil {
		t.Fatal(err)
	}
	if serviceAsleep("plex") {
		t.Fatalf("a service with no marker: got asleep want not")
	}
	if err := os.WriteFile(filepath.Join(installRoot, "plex", installSleepMarker), nil, 0o644); err != nil {
		t.Fatal(err)
	}
	if !serviceAsleep("plex") {
		t.Fatalf("a service with the marker: got not asleep want asleep")
	}
}
