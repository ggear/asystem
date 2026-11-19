package probe

import (
	"reflect"
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
		{name: "every_kind_and_both_durations", text: "requires=mount:/share/10\nrequires=mounts:all-cifs\nrequires=tcp:broker:32404\nrequires=mqtt:broker:32404\nrequires=healthy:vernemq\nrequires_stable=90s\nsettle_min=10m", expectedPolicy: restartPolicy{
			stable: 90 * time.Second, settleMin: 10 * time.Minute, requires: []restartRequirement{
				{kind: "mount", target: "/share/10"}, {kind: "mounts", target: "all-cifs"}, {kind: "tcp", target: "broker:32404"}, {kind: "mqtt", target: "broker:32404"}, {kind: "healthy", target: "vernemq"},
			},
		}},
		{name: "a_zero_stable_is_allowed", text: "requires_stable=0s", expectedPolicy: restartPolicy{}},
		{name: "a_line_without_equals_is_refused", text: "requires", expectedError: true},
		{name: "an_unknown_key_is_refused", text: "retries=3", expectedError: true},
		{name: "an_unknown_kind_is_refused", text: "requires=dns:broker", expectedError: true},
		{name: "a_relative_mount_is_refused", text: "requires=mount:share/10", expectedError: true},
		{name: "mounts_other_than_all_cifs_is_refused", text: "requires=mounts:all", expectedError: true},
		{name: "a_tcp_target_without_a_port_is_refused", text: "requires=tcp:broker", expectedError: true},
		{name: "a_missing_target_is_refused", text: "requires=mount:", expectedError: true},
		{name: "a_bad_duration_is_refused", text: "requires_stable=soon", expectedError: true},
		{name: "a_negative_duration_is_refused", text: "settle_min=-1s", expectedError: true},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			policy, err := parseRestartPolicy(test.text)
			if (err != nil) != test.expectedError {
				t.Fatalf("error: got [%v] want error [%v]", err, test.expectedError)
			}
			if !test.expectedError && !reflect.DeepEqual(policy, test.expectedPolicy) {
				t.Fatalf("policy: got %+v want %+v", policy, test.expectedPolicy)
			}
		})
	}
}
