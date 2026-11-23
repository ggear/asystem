package probe

import (
	"context"
	"errors"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"
)

type restartCall struct {
	name string
	args []string
}

type restartScript struct {
	exits   map[string]int
	outputs map[string]string
	calls   []restartCall
}

func TestProbeUtilRestartRequires_Met(t *testing.T) {
	fstab := filepath.Join(t.TempDir(), "fstab")
	if err := os.WriteFile(fstab, []byte("# a note\nUUID=1 /boot ext4 defaults 0 2\n//mad/share-10 /share/10 cifs defaults 0 0\n//may/share-30 /share/30 cifs defaults 0 0\n"), 0o644); err != nil {
		t.Fatalf("write failed with [%v]", err)
	}
	tests := []struct {
		name        string
		requirement restartRequirement
		exits       map[string]int
		outputs     map[string]string
		dialError   error
		noFstab     bool
		expected    bool
	}{
		{name: "a_mount_that_lists_and_is_not_just_an_automount_is_met", requirement: restartRequirement{kind: "mount", target: "/share/10"}, outputs: map[string]string{"findmnt -n -o FSTYPE -M /share/10": "autofs\ncifs\n"}, expected: true},
		{name: "a_mount_that_is_only_an_automount_is_not_met", requirement: restartRequirement{kind: "mount", target: "/share/10"}, outputs: map[string]string{"findmnt -n -o FSTYPE -M /share/10": "autofs\n"}, expected: false},
		{name: "a_mount_that_fails_to_list_is_not_met", requirement: restartRequirement{kind: "mount", target: "/share/10"}, exits: map[string]int{"ls -A /share/10": 2}, expected: false},
		{name: "a_path_that_is_not_a_mount_point_is_not_met", requirement: restartRequirement{kind: "mount", target: "/share/10"}, exits: map[string]int{"findmnt": 1}, expected: false},
		{name: "every_cifs_entry_mounted_is_met", requirement: restartRequirement{kind: "mounts", target: "all-cifs"}, outputs: map[string]string{"findmnt -n -o FSTYPE -M /share/10": "cifs", "findmnt -n -o FSTYPE -M /share/30": "cifs"}, expected: true},
		{name: "one_cifs_entry_missing_is_not_met", requirement: restartRequirement{kind: "mounts", target: "all-cifs"}, outputs: map[string]string{"findmnt -n -o FSTYPE -M /share/10": "cifs", "findmnt -n -o FSTYPE -M /share/30": "autofs"}, expected: false},
		{name: "no_cifs_entries_at_all_is_not_met", requirement: restartRequirement{kind: "mounts", target: "all-cifs"}, noFstab: true, expected: false},
		{name: "a_tcp_connection_that_opens_is_met", requirement: restartRequirement{kind: "tcp", target: "broker:32404"}, expected: true},
		{name: "a_tcp_connection_that_is_refused_is_not_met", requirement: restartRequirement{kind: "tcp", target: "broker:32404"}, dialError: errors.New("refused"), expected: false},
		{name: "an_mqtt_round_trip_that_returns_its_message_is_met", requirement: restartRequirement{kind: "mqtt", target: "broker:32404:mqttv5"}, outputs: map[string]string{"bash": "ok\n"}, expected: true},
		{name: "an_mqtt_round_trip_that_returns_nothing_is_not_met", requirement: restartRequirement{kind: "mqtt", target: "broker:32404:mqttv5"}, expected: false},
		{name: "an_mqtt_target_without_a_protocol_is_not_met", requirement: restartRequirement{kind: "mqtt", target: "broker:32404"}, outputs: map[string]string{"bash": "ok\n"}, expected: false},
		{name: "a_healthy_service_is_met", requirement: restartRequirement{kind: "healthy", target: "vernemq"}, outputs: map[string]string{"docker inspect --format {{.State.Health.Status}} vernemq": "healthy\n"}, expected: true},
		{name: "a_starting_service_is_not_met", requirement: restartRequirement{kind: "healthy", target: "vernemq"}, outputs: map[string]string{"docker inspect --format {{.State.Health.Status}} vernemq": "starting\n"}, expected: false},
		{name: "an_unknown_kind_is_not_met", requirement: restartRequirement{kind: "dns", target: "broker"}, expected: false},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			script := &restartScript{exits: testCase.exits, outputs: testCase.outputs}
			checker := restartChecker{
				run:   script.run,
				dial:  func(string, time.Duration) error { return testCase.dialError },
				fstab: fstab,
			}
			if testCase.noFstab {
				checker.fstab = filepath.Join(t.TempDir(), "missing")
			}
			if got := checker.met(context.Background(), testCase.requirement); got != testCase.expected {
				t.Fatalf("met: got %v want %v, calls %v", got, testCase.expected, script.calls)
			}
		})
	}
}

func TestProbeUtilRestartRequires_MQTTSpeaksTheNamedProtocol(t *testing.T) {
	tests := []struct {
		name     string
		accepts  string
		target   string
		expected bool
	}{
		{name: "a_broker_accepting_the_named_protocol_is_met", accepts: "mqttv5", target: "broker:32404:mqttv5", expected: true},
		{name: "a_broker_refusing_the_named_protocol_is_not_met", accepts: "mqttv311", target: "broker:32404:mqttv5", expected: false},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			bin := t.TempDir()
			broker := `#!/usr/bin/env bash
[[ "$1" == "-V" && "$2" == "` + testCase.accepts + `" ]] || exit 1
`
			if err := os.WriteFile(filepath.Join(bin, "mosquitto_pub"), []byte(broker), 0o755); err != nil {
				t.Fatalf("write failed with [%v]", err)
			}
			if err := os.WriteFile(filepath.Join(bin, "mosquitto_sub"), []byte(broker+"echo ok\n"), 0o755); err != nil {
				t.Fatalf("write failed with [%v]", err)
			}
			t.Setenv("PATH", bin+string(os.PathListSeparator)+os.Getenv("PATH"))
			if met := newRestartChecker().met(context.Background(), restartRequirement{kind: restartKindMQTT, target: testCase.target}); met != testCase.expected {
				t.Errorf("met: got %v want %v", met, testCase.expected)
			}
		})
	}
}

func (s *restartScript) run(_ context.Context, _ time.Duration, name string, args ...string) (string, int, bool) {
	s.calls = append(s.calls, restartCall{name: name, args: args})
	key := name + " " + strings.Join(args, " ")
	output := ""
	for prefix, text := range s.outputs {
		if strings.HasPrefix(key, prefix) {
			output = text
		}
	}
	for prefix, code := range s.exits {
		if strings.HasPrefix(key, prefix) {
			return output, code, false
		}
	}
	return output, 0, false
}
