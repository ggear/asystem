package plugin

import (
	"testing"
	"time"
)

func TestPluginImpl_Filter(t *testing.T) {
	tests := []struct {
		name          string
		names         []string
		expectedNames []string
		expectedError bool
	}{
		{name: "empty_returns_all", names: nil, expectedNames: []string{"certificate", "domain", "ethernet", "internet", "weewx", "wireless", "zigbee"}, expectedError: false},
		{name: "single", names: []string{"zigbee"}, expectedNames: []string{"zigbee"}, expectedError: false},
		{name: "dedup_and_trim", names: []string{" internet ", "internet"}, expectedNames: []string{"internet"}, expectedError: false},
		{name: "unknown_errors", names: []string{"gamma"}, expectedNames: nil, expectedError: true},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			got, err := Filter(testCase.names)
			if (err != nil) != testCase.expectedError {
				t.Fatalf("error mismatch: got %v want error=%v", err, testCase.expectedError)
			}
			if testCase.expectedError {
				return
			}
			if len(got) != len(testCase.expectedNames) {
				t.Fatalf("count mismatch: got %d want %d", len(got), len(testCase.expectedNames))
			}
			for i, p := range got {
				if p.Name() != testCase.expectedNames[i] {
					t.Fatalf("name mismatch at %d: got %s want %s", i, p.Name(), testCase.expectedNames[i])
				}
			}
		})
	}
}

func TestPluginImpl_MarshalJSON(t *testing.T) {
	tests := []struct {
		name          string
		message       Aggregate
		expected      string
		expectedError bool
	}{
		{
			name:          "sick_diagnose",
			message:       Aggregate{Timestamp: time.Unix(1737686400, 0), OK: true, Status: StatusSick, Score: 72},
			expected:      `{"timestamp":1737686400,"ok":true,"status":"sick","score":72}`,
			expectedError: false,
		},
		{
			name:          "dead_diagnose",
			message:       Aggregate{Timestamp: time.Unix(1737686400, 0), OK: false, Status: StatusDead, Score: 0},
			expected:      `{"timestamp":1737686400,"ok":false,"status":"dead","score":0}`,
			expectedError: false,
		},
		{
			name:          "fit_diagnose",
			message:       Aggregate{Timestamp: time.Unix(1737686400, 0), OK: true, Status: StatusFit, Score: 100},
			expected:      `{"timestamp":1737686400,"ok":true,"status":"fit","score":100}`,
			expectedError: false,
		},
		{
			name:          "status_is_escaped",
			message:       Aggregate{Timestamp: time.Unix(1737686400, 0), OK: true, Status: Status("bad\"\nstatus"), Score: 1},
			expected:      `{"timestamp":1737686400,"ok":true,"status":"bad\"\nstatus","score":1}`,
			expectedError: false,
		},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			got, err := testCase.message.MarshalJSON()
			if (err != nil) != testCase.expectedError {
				t.Fatalf("error mismatch: got %v want error=%v", err, testCase.expectedError)
			}
			if string(got) != testCase.expected {
				t.Fatalf("json mismatch:\n got %s\nwant %s", got, testCase.expected)
			}
		})
	}
}

func TestPluginImpl_ParseState(t *testing.T) {
	tests := []struct {
		name          string
		payload       string
		expectedState State
		expectedOK    bool
	}{
		{name: "on", payload: "ON", expectedState: StateOn, expectedOK: true},
		{name: "off", payload: "OFF", expectedState: StateOff, expectedOK: true},
		{name: "lower_trimmed", payload: " on ", expectedState: StateOn, expectedOK: true},
		{name: "unknown", payload: "check", expectedState: StateOff, expectedOK: false},
		{name: "empty", payload: "", expectedState: StateOff, expectedOK: false},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			state, ok := ParseState(testCase.payload)
			if ok != testCase.expectedOK {
				t.Fatalf("ok: got %v want %v", ok, testCase.expectedOK)
			}
			if state != testCase.expectedState {
				t.Errorf("state: got %s want %s", state, testCase.expectedState)
			}
		})
	}
}
