package plugins

import (
	"context"
	"errors"
	"testing"
	"time"

	"networks/internal/plugin"
)

const gatewayIP = "10.0.4.1"

func TestInternet_Poll(t *testing.T) {
	p := &internetPlugin{targets: buildTargets(gatewayIP), probe: func(_ context.Context, ip string) (time.Duration, error) {
		if ip == "1.1.1.1" {
			return 10 * time.Millisecond, nil
		}
		return 0, errors.New("unreachable")
	}}
	msg, err := p.Poll(context.Background())
	if err != nil {
		t.Fatalf("poll: unexpected error %v", err)
	}
	if len(msg.Points) != len(p.targets) {
		t.Fatalf("points: got %d want %d (one per target)", len(msg.Points), len(p.targets))
	}
	reachable, ok := pointByTag(msg.Points, "target", "1.1.1.1")
	if !ok {
		t.Fatal("1.1.1.1 point missing")
	}
	if loss, _ := reachable.Float("loss_pct"); loss != 0 {
		t.Errorf("1.1.1.1 loss_pct: got %v want 0", loss)
	}
	if _, hasRTT := reachable.Float("avg_rtt_ms"); !hasRTT {
		t.Errorf("1.1.1.1 avg_rtt_ms: got null want a value")
	}
	down, ok := pointByTag(msg.Points, "target", "8.8.8.8")
	if !ok {
		t.Fatal("8.8.8.8 point missing")
	}
	if loss, _ := down.Float("loss_pct"); loss != 100 {
		t.Errorf("8.8.8.8 loss_pct: got %v want 100", loss)
	}
	if _, hasRTT := down.Float("avg_rtt_ms"); hasRTT {
		t.Errorf("8.8.8.8 avg_rtt_ms: got a value want null")
	}
}

func TestInternet_Diagnose(t *testing.T) {
	tests := []struct {
		name           string
		samples        []plugin.Sample
		expectedStatus plugin.Status
		expectedOK     bool
		expectedScore  int
		expectedDetail string
		expectedError  bool
	}{
		{
			name: "fit_all_healthy",
			samples: []plugin.Sample{internetPoll(map[string]internetSample{
				gatewayIP: {"gateway", 0, 1, 0.2},
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
			samples: []plugin.Sample{internetPoll(map[string]internetSample{
				gatewayIP: {"gateway", 0, 1, 0.2},
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
			samples: []plugin.Sample{internetPoll(map[string]internetSample{
				gatewayIP: {"gateway", 0, 1, 0.2},
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
			samples: []plugin.Sample{internetPoll(map[string]internetSample{
				gatewayIP: {"gateway", 0, 1, 0.2},
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
			samples: []plugin.Sample{internetPoll(map[string]internetSample{
				gatewayIP: {"gateway", 0, 1, 0.2},
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
			samples: []plugin.Sample{internetPoll(map[string]internetSample{
				gatewayIP: {"gateway", 100, 0, 0},
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

func TestInternet_Read(t *testing.T) {
	avg, minRTT, maxRTT, jitter := readInternet([]float64{10, 20, 30})
	if avg != 20 {
		t.Errorf("avg: got %v want 20", avg)
	}
	if minRTT != 10 {
		t.Errorf("min: got %v want 10", minRTT)
	}
	if maxRTT != 30 {
		t.Errorf("max: got %v want 30", maxRTT)
	}
	if jitter < 8.16 || jitter > 8.17 {
		t.Errorf("jitter: got %v want ~8.165 (stddev)", jitter)
	}
}

type internetSample struct {
	scope  string
	loss   float64
	rtt    float64
	jitter float64
}

func internetPoll(samples map[string]internetSample) plugin.Sample {
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
	return plugin.Sample{Plugin: "internet", Points: points}
}
