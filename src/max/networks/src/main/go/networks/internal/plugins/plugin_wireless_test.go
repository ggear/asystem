package plugins

import (
	"testing"

	"networks/internal/plugin"
)

type apSample struct {
	name string
	up   bool
	exp  int64
}

func wirelessPulse(samples ...apSample) plugin.Message {
	points := make([]plugin.Point, 0, len(samples))
	for _, s := range samples {
		tags := []plugin.Tag{{Key: "scope", Value: "ap"}, {Key: "ap", Value: s.name}}
		points = append(points, plugin.NewPoint(tags, plugin.Bool("up", s.up), plugin.Int("experience", s.exp), plugin.Int("num_clients", 0)))
	}
	return plugin.Message{Plugin: "wireless", Points: points}
}

func TestDecideWireless(t *testing.T) {
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
			name:           "fit_all_up_good_experience",
			samples:        []plugin.Message{wirelessPulse(apSample{"deck", true, 90}, apSample{"hallway", true, 90})},
			expectedStatus: plugin.StatusFit,
			expectedOK:     true,
			expectedScore:  95,
			expectedDetail: "UP",
			expectedError:  false,
		},
		{
			name:           "sick_ap_down",
			samples:        []plugin.Message{wirelessPulse(apSample{"deck", true, 90}, apSample{"hallway", false, 0})},
			expectedStatus: plugin.StatusSick,
			expectedOK:     true,
			expectedScore:  70,
			expectedDetail: "AP_DOWN",
			expectedError:  false,
		},
		{
			name:           "sick_poor_clients",
			samples:        []plugin.Message{wirelessPulse(apSample{"deck", true, 60}, apSample{"hallway", true, 60})},
			expectedStatus: plugin.StatusSick,
			expectedOK:     true,
			expectedScore:  80,
			expectedDetail: "POOR_CLIENTS",
			expectedError:  false,
		},
		{
			name:           "dead_all_down",
			samples:        []plugin.Message{wirelessPulse(apSample{"deck", false, 0}, apSample{"hallway", false, 0})},
			expectedStatus: plugin.StatusDead,
			expectedOK:     false,
			expectedScore:  0,
			expectedDetail: "AP_DOWN",
			expectedError:  false,
		},
		{
			name:           "dead_controller_unreachable",
			samples:        []plugin.Message{wirelessPulse()},
			expectedStatus: plugin.StatusDead,
			expectedOK:     false,
			expectedScore:  0,
			expectedDetail: "CONTROLLER_UNREACHABLE",
			expectedError:  false,
		},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			got, err := newWirelessPlugin().Aggregate(test.samples)
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
