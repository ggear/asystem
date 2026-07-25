package plugins

import (
	"testing"

	"networks/internal/plugin"
)

type internetSample struct {
	scope  string
	loss   float64
	rtt    float64
	jitter float64
}

func internetPulse(samples map[string]internetSample) plugin.Message {
	points := make([]plugin.Point, 0, len(samples))
	for ip, s := range samples {
		fields := []plugin.Field{plugin.Float("loss_pct", s.loss)}
		if s.loss < 100 {
			fields = append(fields, plugin.Float("avg_rtt_ms", s.rtt), plugin.Float("jitter_ms", s.jitter))
		} else {
			fields = append(fields, plugin.Null("avg_rtt_ms"), plugin.Null("jitter_ms"))
		}
		points = append(points, plugin.NewPoint([]plugin.Tag{{Key: "scope", Value: s.scope}, {Key: "target", Value: ip}}, fields...))
	}
	return plugin.Message{Plugin: "internet", Points: points}
}

func TestDecideInternet(t *testing.T) {
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
			name: "fit_all_healthy",
			samples: []plugin.Message{internetPulse(map[string]internetSample{
				Gateway:   {"gateway", 0, 1, 0.2},
				"1.1.1.1": {"target", 0, 12, 1},
				"8.8.8.8": {"target", 0, 14, 1},
				"9.9.9.9": {"target", 0, 20, 2},
			})},
			expectedStatus: plugin.StatusFit,
			expectedOK:     true,
			expectedScore:  100,
			expectedDetail: "UP",
			expectedError:  false,
		},
		{
			name: "sick_elevated_loss",
			samples: []plugin.Message{internetPulse(map[string]internetSample{
				Gateway:   {"gateway", 0, 1, 0.2},
				"1.1.1.1": {"target", 10, 12, 1},
				"8.8.8.8": {"target", 10, 14, 1},
				"9.9.9.9": {"target", 10, 20, 2},
			})},
			expectedStatus: plugin.StatusSick,
			expectedOK:     true,
			expectedScore:  90,
			expectedDetail: "ELEVATED_LOSS",
			expectedError:  false,
		},
		{
			name: "sick_one_target_down_two_of_three",
			samples: []plugin.Message{internetPulse(map[string]internetSample{
				Gateway:   {"gateway", 0, 1, 0.2},
				"1.1.1.1": {"target", 0, 12, 1},
				"8.8.8.8": {"target", 0, 14, 1},
				"9.9.9.9": {"target", 100, 0, 0},
			})},
			expectedStatus: plugin.StatusSick,
			expectedOK:     true,
			expectedScore:  52,
			expectedDetail: "ELEVATED_LOSS",
			expectedError:  false,
		},
		{
			name: "sick_high_latency",
			samples: []plugin.Message{internetPulse(map[string]internetSample{
				Gateway:   {"gateway", 0, 1, 0.2},
				"1.1.1.1": {"target", 0, 150, 5},
				"8.8.8.8": {"target", 0, 150, 5},
				"9.9.9.9": {"target", 0, 150, 5},
			})},
			expectedStatus: plugin.StatusSick,
			expectedOK:     true,
			expectedScore:  90,
			expectedDetail: "HIGH_LATENCY",
			expectedError:  false,
		},
		{
			name: "dead_isp_down",
			samples: []plugin.Message{internetPulse(map[string]internetSample{
				Gateway:   {"gateway", 0, 1, 0.2},
				"1.1.1.1": {"target", 100, 0, 0},
				"8.8.8.8": {"target", 100, 0, 0},
				"9.9.9.9": {"target", 100, 0, 0},
			})},
			expectedStatus: plugin.StatusDead,
			expectedOK:     false,
			expectedScore:  0,
			expectedDetail: "ISP_DOWN",
			expectedError:  false,
		},
		{
			name: "dead_lan_down",
			samples: []plugin.Message{internetPulse(map[string]internetSample{
				Gateway:   {"gateway", 100, 0, 0},
				"1.1.1.1": {"target", 0, 12, 1},
				"8.8.8.8": {"target", 0, 14, 1},
				"9.9.9.9": {"target", 0, 20, 2},
			})},
			expectedStatus: plugin.StatusDead,
			expectedOK:     false,
			expectedScore:  0,
			expectedDetail: "LAN_DOWN",
			expectedError:  false,
		},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			got, err := newInternetPlugin().Aggregate(test.samples)
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
