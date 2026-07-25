package plugins

import (
	"testing"

	"networks/internal/plugin"
)

type deviceSample struct {
	name      string
	available bool
	lqi       int
	hasLQI    bool
}

func zigbeePulse(bridgeOnline bool, samples ...deviceSample) plugin.Message {
	points := []plugin.Point{plugin.NewPoint([]plugin.Tag{{Key: "scope", Value: "bridge"}}, plugin.Bool("online", bridgeOnline), plugin.Bool("permit_join", false))}
	for _, s := range samples {
		tags := []plugin.Tag{{Key: "scope", Value: "device"}, {Key: "device", Value: s.name}}
		lqiField := plugin.Null("lqi")
		if s.hasLQI {
			lqiField = plugin.Int("lqi", int64(s.lqi))
		}
		points = append(points, plugin.NewPoint(tags, lqiField, plugin.Bool("available", s.available)))
	}
	return plugin.Message{Plugin: "zigbee", Points: points}
}

func TestDecideZigbee(t *testing.T) {
	tests := []struct {
		name           string
		samples        []plugin.Message
		expectedStatus plugin.Status
		expectedOK     bool
		expectedScore  int
		expectedDetail string
		expectedError  bool
	}{
		{
			name:           "fit_healthy",
			samples:        []plugin.Message{zigbeePulse(true, deviceSample{"lamp", true, 100, true}, deviceSample{"plug", true, 100, true})},
			expectedStatus: plugin.StatusFit,
			expectedOK:     true,
			expectedScore:  82,
			expectedDetail: "HEALTHY",
			expectedError:  false,
		},
		{
			name:           "sick_devices_offline",
			samples:        []plugin.Message{zigbeePulse(true, deviceSample{"lamp", true, 100, true}, deviceSample{name: "plug", available: false})},
			expectedStatus: plugin.StatusSick,
			expectedOK:     true,
			expectedScore:  47,
			expectedDetail: "DEVICES_OFFLINE",
			expectedError:  false,
		},
		{
			name:           "sick_weak_links",
			samples:        []plugin.Message{zigbeePulse(true, deviceSample{"lamp", true, 20, true}, deviceSample{"plug", true, 20, true})},
			expectedStatus: plugin.StatusSick,
			expectedOK:     true,
			expectedScore:  72,
			expectedDetail: "WEAK_LINKS",
			expectedError:  false,
		},
		{
			name:           "dead_coordinator_down",
			samples:        []plugin.Message{zigbeePulse(false, deviceSample{"lamp", true, 100, true})},
			expectedStatus: plugin.StatusDead,
			expectedOK:     false,
			expectedScore:  0,
			expectedDetail: "COORDINATOR_DOWN",
			expectedError:  false,
		},
		{
			name:           "dead_no_devices",
			samples:        []plugin.Message{zigbeePulse(true)},
			expectedStatus: plugin.StatusDead,
			expectedOK:     false,
			expectedScore:  0,
			expectedDetail: "COORDINATOR_DOWN",
			expectedError:  false,
		},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			got, err := newZigbeePlugin().Aggregate(test.samples)
			if (err != nil) != test.expectedError {
				t.Fatalf("error mismatch: got %v want error=%v", err, test.expectedError)
			}
			if got.Status != test.expectedStatus {
				t.Errorf("status: got %s want %s", got.Status, test.expectedStatus)
			}
			if got.OK != test.expectedOK {
				t.Errorf("ok: got %v want %v", got.OK, test.expectedOK)
			}
			if got.Score != test.expectedScore {
				t.Errorf("score: got %d want %d", got.Score, test.expectedScore)
			}
			if got.Detail != test.expectedDetail {
				t.Errorf("detail: got %s want %s", got.Detail, test.expectedDetail)
			}
		})
	}
}

func TestParseState(t *testing.T) {
	tests := []struct {
		name     string
		payload  string
		expected string
	}{
		{name: "plain", payload: "online", expected: "online"},
		{name: "trimmed", payload: "  offline\n", expected: "offline"},
		{name: "json_state", payload: `{"state":"online"}`, expected: "online"},
		{name: "json_missing_state", payload: `{"other":1}`, expected: ""},
		{name: "malformed_json_returns_raw", payload: "{oops", expected: "{oops"},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			if got := parseState([]byte(test.payload)); got != test.expected {
				t.Errorf("got %q want %q", got, test.expected)
			}
		})
	}
}

func TestParsePermitJoin(t *testing.T) {
	tests := []struct {
		name     string
		payload  string
		expected bool
	}{
		{name: "true", payload: `{"permit_join":true}`, expected: true},
		{name: "false", payload: `{"permit_join":false}`, expected: false},
		{name: "missing", payload: `{}`, expected: false},
		{name: "garbage", payload: "not json", expected: false},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			if got := parsePermitJoin([]byte(test.payload)); got != test.expected {
				t.Errorf("got %v want %v", got, test.expected)
			}
		})
	}
}

func TestParseDevices(t *testing.T) {
	devices := parseDevices([]byte(`[{"friendly_name":"lamp","type":"EndDevice"},{"friendly_name":"coord","type":"Coordinator"}]`))
	if len(devices) != 2 {
		t.Fatalf("count: got %d want 2", len(devices))
	}
	if devices[0].FriendlyName != "lamp" || devices[0].Type != "EndDevice" {
		t.Errorf("device[0]: got %+v", devices[0])
	}
	if devices[1].FriendlyName != "coord" || devices[1].Type != "Coordinator" {
		t.Errorf("device[1]: got %+v", devices[1])
	}
	if got := parseDevices([]byte("not json")); got != nil {
		t.Errorf("invalid payload: got %+v want nil", got)
	}
}

func TestParseLinkQuality(t *testing.T) {
	tests := []struct {
		name       string
		payload    string
		expected   int
		expectedOK bool
	}{
		{name: "present", payload: `{"linkquality":42}`, expected: 42, expectedOK: true},
		{name: "present_zero", payload: `{"linkquality":0}`, expected: 0, expectedOK: true},
		{name: "null", payload: `{"linkquality":null}`, expected: 0, expectedOK: false},
		{name: "missing", payload: `{}`, expected: 0, expectedOK: false},
		{name: "garbage", payload: "not json", expected: 0, expectedOK: false},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			got, ok := parseLinkQuality([]byte(test.payload))
			if got != test.expected || ok != test.expectedOK {
				t.Errorf("got (%d,%v) want (%d,%v)", got, ok, test.expected, test.expectedOK)
			}
		})
	}
}
