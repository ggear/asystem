package probe

import (
	"os"
	"path/filepath"
	"reflect"
	"regexp"
	"slices"
	"strings"
	"testing"
	"time"
)

func TestProbeUtilRestartPolicy_Parse(t *testing.T) {
	tests := []struct {
		name           string
		text           string
		expectedPolicy restartPolicy
		expectedError  bool
	}{
		{name: "empty_text_is_the_default", text: "", expectedPolicy: restartPolicy{stable: restartStableDefault}},
		{name: "blank_lines_and_comments_are_ignored", text: "\n# a note\n  \nrequires=mount:/share/10\n", expectedPolicy: restartPolicy{stable: restartStableDefault, requires: []restartRequirement{{kind: "mount", target: "/share/10"}}}},
		{name: "every_kind_and_both_durations", text: "requires=mount:/share/10\nrequires=mounts:all-cifs\nrequires=tcp:broker:32404\nrequires=mqtt:broker:32404:mqttv5\nrequires=healthy:vernemq\nrequires_stable=90s\nsettle_min=10m", expectedPolicy: restartPolicy{
			stable: 90 * time.Second, settleMin: 10 * time.Minute, requires: []restartRequirement{
				{kind: "mount", target: "/share/10"}, {kind: "mounts", target: "all-cifs"}, {kind: "tcp", target: "broker:32404"}, {kind: "mqtt", target: "broker:32404:mqttv5"}, {kind: "healthy", target: "vernemq"},
			},
		}},
		{name: "a_zero_stable_is_allowed", text: "requires_stable=0s", expectedPolicy: restartPolicy{}},
		{name: "a_line_without_equals_is_refused", text: "requires", expectedError: true},
		{name: "an_unknown_key_is_refused", text: "retries=3", expectedError: true},
		{name: "an_unknown_kind_is_refused", text: "requires=dns:broker", expectedError: true},
		{name: "a_relative_mount_is_refused", text: "requires=mount:share/10", expectedError: true},
		{name: "mounts_other_than_all_cifs_is_refused", text: "requires=mounts:all", expectedError: true},
		{name: "a_tcp_target_without_a_port_is_refused", text: "requires=tcp:broker", expectedError: true},
		{name: "an_mqtt_target_without_a_protocol_is_refused", text: "requires=mqtt:broker:32404", expectedError: true},
		{name: "an_mqtt_target_with_an_unknown_protocol_is_refused", text: "requires=mqtt:broker:32404:mqttv6", expectedError: true},
		{name: "an_mqtt_target_without_a_port_is_refused", text: "requires=mqtt:broker::mqttv5", expectedError: true},
		{name: "a_missing_target_is_refused", text: "requires=mount:", expectedError: true},
		{name: "a_bad_duration_is_refused", text: "requires_stable=soon", expectedError: true},
		{name: "a_negative_duration_is_refused", text: "settle_min=-1s", expectedError: true},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			policy, err := parseRestartPolicy(testCase.text)
			if (err != nil) != testCase.expectedError {
				t.Fatalf("error: got [%v] want error [%v]", err, testCase.expectedError)
			}
			if !testCase.expectedError && !reflect.DeepEqual(policy, testCase.expectedPolicy) {
				t.Fatalf("policy: got %+v want %+v", policy, testCase.expectedPolicy)
			}
		})
	}
}

func TestProbeUtilRestartPolicy_TheContractNamesEveryMQTTProtocol(t *testing.T) {
	path, err := filepath.Abs(filepath.Join("..", "..", "..", "..", "..", "..", "..", "_", "src", "build", "python", "asystem", "container.py"))
	if err != nil {
		t.Fatalf("resolve container.py: %v", err)
	}
	source, err := os.ReadFile(path)
	if err != nil {
		t.Fatalf("read the shared build library at %s: %v", path, err)
	}
	contract := regexp.MustCompile(`(?s)RESTART_CONTRACT = """.*?"""`).Find(source)
	if contract == nil {
		t.Fatalf("found no RESTART_CONTRACT in %s, the parse has rotted", path)
	}
	named := regexp.MustCompile(`mqtt:<host>:<port>:<([a-z0-9|]+)>`).FindSubmatch(contract)
	if named == nil {
		t.Fatalf("found no mqtt:<host>:<port>:<protocol|...> in RESTART_CONTRACT, the parse has rotted")
	}
	declared := strings.Split(string(named[1]), "|")
	if !slices.Equal(slices.Sorted(slices.Values(declared)), slices.Sorted(slices.Values(restartMQTTProtocols))) {
		t.Errorf("protocols: got %v in RESTART_CONTRACT want %v", declared, restartMQTTProtocols)
	}
}
