package plugins

import (
	"testing"

	"networks/internal/plugin"
)

type portSample struct {
	port       string
	up         bool
	speed      int64
	fullDuplex bool
	errors     int64
}

func ethernetPulse(samples ...portSample) plugin.Message {
	points := make([]plugin.Point, 0, len(samples))
	for _, s := range samples {
		tags := []plugin.Tag{{Key: "scope", Value: "port"}, {Key: "switch", Value: "core"}, {Key: "port", Value: s.port}}
		points = append(points, plugin.NewPoint(tags, plugin.Bool("up", s.up), plugin.Int("speed", s.speed), plugin.Bool("full_duplex", s.fullDuplex), plugin.Int("errors", s.errors)))
	}
	return plugin.Message{Plugin: "ethernet", Points: points}
}

func TestDecideEthernet(t *testing.T) {
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
			name:           "fit_all_up",
			samples:        []plugin.Message{ethernetPulse(portSample{"1", true, 1000, true, 0}, portSample{"2", true, 1000, true, 0})},
			expectedStatus: plugin.StatusFit,
			expectedOK:     true,
			expectedScore:  100,
			expectedDetail: "UP",
			expectedError:  false,
		},
		{
			name:           "sick_port_down",
			samples:        []plugin.Message{ethernetPulse(portSample{"1", true, 1000, true, 0}, portSample{"2", false, 0, false, 0})},
			expectedStatus: plugin.StatusSick,
			expectedOK:     true,
			expectedScore:  50,
			expectedDetail: "PORT_DOWN",
			expectedError:  false,
		},
		{
			name:           "sick_speed_degraded",
			samples:        []plugin.Message{ethernetPulse(portSample{"1", true, 1000, true, 0}, portSample{"2", true, 100, true, 0})},
			expectedStatus: plugin.StatusSick,
			expectedOK:     true,
			expectedScore:  90,
			expectedDetail: "SPEED_DEGRADED",
			expectedError:  false,
		},
		{
			name:           "sick_link_errors",
			samples:        []plugin.Message{ethernetPulse(portSample{"1", true, 1000, true, 0}, portSample{"2", true, 1000, true, 42})},
			expectedStatus: plugin.StatusSick,
			expectedOK:     true,
			expectedScore:  90,
			expectedDetail: "LINK_ERRORS",
			expectedError:  false,
		},
		{
			name:           "dead_all_down",
			samples:        []plugin.Message{ethernetPulse(portSample{"1", false, 0, false, 0}, portSample{"2", false, 0, false, 0})},
			expectedStatus: plugin.StatusDead,
			expectedOK:     false,
			expectedScore:  0,
			expectedDetail: "PORT_DOWN",
			expectedError:  false,
		},
		{
			name:           "dead_switch_unreachable",
			samples:        []plugin.Message{ethernetPulse()},
			expectedStatus: plugin.StatusDead,
			expectedOK:     false,
			expectedScore:  0,
			expectedDetail: "SWITCH_UNREACHABLE",
			expectedError:  false,
		},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			got, err := newEthernetPlugin().Aggregate(test.samples)
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
