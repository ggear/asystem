package plugin

import (
	"context"
	"errors"
	"strings"
	"testing"
	"time"
)

func TestInternet_Poll(t *testing.T) {
	p := &internetPlugin{targets: internetPingTargets(gatewayIP), probe: func(_ context.Context, ip string) (time.Duration, error) {
		if ip == "1.1.1.1" {
			return 10 * time.Millisecond, nil
		}
		return 0, errors.New("unreachable")
	}}
	msg, err := p.Poll(context.Background())
	if err != nil {
		t.Fatalf("poll: unexpected error %v", err)
	}
	readings, _ := msg.Readings.([]internetReading)
	if len(readings) != len(p.targets) {
		t.Fatalf("readings: got %d want %d (one per target)", len(readings), len(p.targets))
	}
	reachable, ok := readingByTarget(readings, "1.1.1.1")
	if !ok {
		t.Fatal("1.1.1.1 reading missing")
	}
	if reachable.lossPct != 0 {
		t.Errorf("1.1.1.1 loss_pct: got %v want 0", reachable.lossPct)
	}
	if !reachable.hasRTT {
		t.Errorf("1.1.1.1 rtt: got none want a value")
	}
	down, ok := readingByTarget(readings, "8.8.8.8")
	if !ok {
		t.Fatal("8.8.8.8 reading missing")
	}
	if down.lossPct != 100 {
		t.Errorf("8.8.8.8 loss_pct: got %v want 100", down.lossPct)
	}
	if down.hasRTT {
		t.Errorf("8.8.8.8 rtt: got a value want none")
	}
}

func TestInternet_Diagnose(t *testing.T) {
	tests := []struct {
		name           string
		samples        []Sample
		expectedStatus Status
		expectedScore  int
		expectedReason string
	}{
		{
			name: "fit_all_healthy",
			samples: []Sample{internetPoll(map[string]internetSample{
				gatewayIP: {true, 0, 1, 0.2},
				"1.1.1.1": {false, 0, 12, 1},
				"8.8.8.8": {false, 0, 14, 1},
				"9.9.9.9": {false, 0, 20, 2},
			})},
			expectedStatus: StatusFit,
			expectedScore:  100,
			expectedReason: "UP",
		},
		{
			name: "sick_elevated_loss",
			samples: []Sample{internetPoll(map[string]internetSample{
				gatewayIP: {true, 0, 1, 0.2},
				"1.1.1.1": {false, 10, 12, 1},
				"8.8.8.8": {false, 10, 14, 1},
				"9.9.9.9": {false, 10, 20, 2},
			})},
			expectedStatus: StatusSick,
			expectedScore:  90,
			expectedReason: "ELEVATED_LOSS",
		},
		{
			name: "sick_one_target_down_two_of_three",
			samples: []Sample{internetPoll(map[string]internetSample{
				gatewayIP: {true, 0, 1, 0.2},
				"1.1.1.1": {false, 0, 12, 1},
				"8.8.8.8": {false, 0, 14, 1},
				"9.9.9.9": {false, 100, 0, 0},
			})},
			expectedStatus: StatusSick,
			expectedScore:  52,
			expectedReason: "ELEVATED_LOSS",
		},
		{
			name: "fit_judged_on_the_rounded_latency_it_prints",
			samples: []Sample{internetPoll(map[string]internetSample{
				gatewayIP: {true, 0, 1, 0.2},
				"1.1.1.1": {false, 0, 100.04, 1},
				"8.8.8.8": {false, 0, 100.04, 1},
				"9.9.9.9": {false, 0, 100.04, 1},
			})},
			expectedStatus: StatusFit,
			expectedScore:  100,
			expectedReason: "UP",
		},
		{
			name: "sick_high_latency",
			samples: []Sample{internetPoll(map[string]internetSample{
				gatewayIP: {true, 0, 1, 0.2},
				"1.1.1.1": {false, 0, 150, 5},
				"8.8.8.8": {false, 0, 150, 5},
				"9.9.9.9": {false, 0, 150, 5},
			})},
			expectedStatus: StatusSick,
			expectedScore:  90,
			expectedReason: "HIGH_LATENCY",
		},
		{
			name: "dead_isp_down",
			samples: []Sample{internetPoll(map[string]internetSample{
				gatewayIP: {true, 0, 1, 0.2},
				"1.1.1.1": {false, 100, 0, 0},
				"8.8.8.8": {false, 100, 0, 0},
				"9.9.9.9": {false, 100, 0, 0},
			})},
			expectedStatus: StatusDead,
			expectedScore:  0,
			expectedReason: "ISP_DOWN",
		},
		{
			name: "dead_lan_down",
			samples: []Sample{internetPoll(map[string]internetSample{
				gatewayIP: {true, 100, 0, 0},
				"1.1.1.1": {false, 0, 12, 1},
				"8.8.8.8": {false, 0, 14, 1},
				"9.9.9.9": {false, 0, 20, 2},
			})},
			expectedStatus: StatusDead,
			expectedScore:  0,
			expectedReason: "LAN_DOWN",
		},
		{
			name: "dead_latest_poll_isp_down",
			samples: []Sample{internetPoll(map[string]internetSample{
				gatewayIP: {true, 0, 1, 0.2},
				"1.1.1.1": {false, 0, 12, 1},
				"8.8.8.8": {false, 0, 14, 1},
				"9.9.9.9": {false, 0, 20, 2},
			}), internetPoll(map[string]internetSample{
				gatewayIP: {true, 0, 1, 0.2},
				"1.1.1.1": {false, 0, 12, 1},
				"8.8.8.8": {false, 0, 14, 1},
				"9.9.9.9": {false, 0, 20, 2},
			}), internetPoll(map[string]internetSample{
				gatewayIP: {true, 0, 1, 0.2},
				"1.1.1.1": {false, 100, 0, 0},
				"8.8.8.8": {false, 100, 0, 0},
				"9.9.9.9": {false, 100, 0, 0},
			})},
			expectedStatus: StatusDead,
			expectedScore:  0,
			expectedReason: "ISP_DOWN",
		},
		{
			name: "dead_latest_poll_lan_down",
			samples: []Sample{internetPoll(map[string]internetSample{
				gatewayIP: {true, 0, 1, 0.2},
				"1.1.1.1": {false, 0, 12, 1},
				"8.8.8.8": {false, 0, 14, 1},
				"9.9.9.9": {false, 0, 20, 2},
			}), internetPoll(map[string]internetSample{
				gatewayIP: {true, 100, 0, 0},
				"1.1.1.1": {false, 100, 0, 0},
				"8.8.8.8": {false, 100, 0, 0},
				"9.9.9.9": {false, 100, 0, 0},
			})},
			expectedStatus: StatusDead,
			expectedScore:  0,
			expectedReason: "LAN_DOWN",
		},
		{
			name: "sick_recovering_after_dead_polls",
			samples: []Sample{internetPoll(map[string]internetSample{
				gatewayIP: {true, 0, 1, 0.2},
				"1.1.1.1": {false, 100, 0, 0},
				"8.8.8.8": {false, 100, 0, 0},
				"9.9.9.9": {false, 100, 0, 0},
			}), internetPoll(map[string]internetSample{
				gatewayIP: {true, 0, 1, 0.2},
				"1.1.1.1": {false, 100, 0, 0},
				"8.8.8.8": {false, 100, 0, 0},
				"9.9.9.9": {false, 100, 0, 0},
			}), internetPoll(map[string]internetSample{
				gatewayIP: {true, 0, 1, 0.2},
				"1.1.1.1": {false, 0, 12, 1},
				"8.8.8.8": {false, 0, 14, 1},
				"9.9.9.9": {false, 0, 20, 2},
			})},
			expectedStatus: StatusSick,
			expectedScore:  33,
			expectedReason: "ELEVATED_LOSS",
		},
		{
			name: "fit_without_gateway_target",
			samples: []Sample{internetPoll(map[string]internetSample{
				"1.1.1.1": {false, 0, 12, 1},
				"8.8.8.8": {false, 0, 14, 1},
				"9.9.9.9": {false, 0, 20, 2},
			})},
			expectedStatus: StatusFit,
			expectedScore:  100,
			expectedReason: "UP",
		},
		{
			name: "fit_empty_latest_poll_ignored",
			samples: []Sample{internetPoll(map[string]internetSample{
				gatewayIP: {true, 0, 1, 0.2},
				"1.1.1.1": {false, 0, 12, 1},
				"8.8.8.8": {false, 0, 14, 1},
				"9.9.9.9": {false, 0, 20, 2},
			}), {}},
			expectedStatus: StatusFit,
			expectedScore:  100,
			expectedReason: "UP",
		},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			got := diagnoseInternet(test.samples)
			if got.Status != test.expectedStatus {
				t.Errorf("status: got %s want %s", got.Status, test.expectedStatus)
			}
			if got.Score != test.expectedScore {
				t.Errorf("score: got %d want %d", got.Score, test.expectedScore)
			}
			if !strings.HasPrefix(got.Reason, test.expectedReason) {
				t.Errorf("reason: got %q want prefix %q", got.Reason, test.expectedReason)
			}
		})
	}
}

func TestInternet_DiagnoseLatestDeadReportsLatestPoll(t *testing.T) {
	healthy := internetPoll(map[string]internetSample{
		gatewayIP: {true, 0, 1, 0.2},
		"1.1.1.1": {false, 0, 12, 1},
	})
	down := internetPoll(map[string]internetSample{
		gatewayIP: {true, 0, 1, 0.2},
		"1.1.1.1": {false, 100, 0, 0},
	})
	got := diagnoseInternet([]Sample{healthy, healthy, down})
	for _, point := range got.Points {
		if name, _ := internetName.Read(point); name != "1.1.1.1" {
			continue
		}
		if loss, _ := internetLoss.Read(point); loss != 100 {
			t.Errorf("loss_pct: got %v want 100 from the latest poll alone", loss)
		}
		if rtt, ok := internetRTT.Read(point); !ok || rtt != 0 {
			t.Errorf("rtt_ms: got %v (set %v) want 0 from the latest poll alone", rtt, ok)
		}
		return
	}
	t.Fatalf("points: no row for target 1.1.1.1 in %v", got.Points)
}

func TestInternet_Read(t *testing.T) {
	avg, jitter := readInternet([]float64{10, 20, 30})
	if avg != 20 {
		t.Errorf("avg: got %v want 20", avg)
	}
	if jitter < 8.16 || jitter > 8.17 {
		t.Errorf("jitter: got %v want ~8.165 (stddev)", jitter)
	}
}

func TestInternet_Report(t *testing.T) {
	accumulators := map[string]*internetPingAccumulator{
		"10.0.2.1": {gateway: true, polls: 1, replied: 1, rttSum: 2, jitterSum: 1},
		"1.1.1.1":  {polls: 1, replied: 1, lossSum: 10, rttSum: 24, jitterSum: 3},
		"8.8.8.8":  {polls: 1, lossSum: 100},
	}
	points := reportInternet([]string{"10.0.2.1", "1.1.1.1", "8.8.8.8"}, accumulators)
	if len(points) != len(accumulators) {
		t.Fatalf("points: got %d want %d (one per target)", len(points), len(accumulators))
	}
	for index, expected := range []string{internetGatewayName, "1.1.1.1", "8.8.8.8"} {
		if name, ok := internetName.Read(points[index]); !ok || name != expected {
			t.Errorf("target[%d]: got %q want %q", index, name, expected)
		}
	}
	if reachable, _ := internetReachable.Read(points[1]); !reachable {
		t.Errorf("reachable[1.1.1.1]: got false want true")
	}
	if reachable, _ := internetReachable.Read(points[2]); reachable {
		t.Errorf("reachable[8.8.8.8]: got true want false at total loss")
	}
	if loss, _ := internetLoss.Read(points[1]); loss != 10 {
		t.Errorf("loss_pct[1.1.1.1]: got %v want 10", loss)
	}
	if rtt, ok := internetRTT.Read(points[2]); !ok || rtt != 0 {
		t.Errorf("rtt_ms without a reply: got %v (set %v) want 0", rtt, ok)
	}
	if jitter, ok := internetJitter.Read(points[2]); !ok || jitter != 0 {
		t.Errorf("jitter_ms without a reply: got %v (set %v) want 0", jitter, ok)
	}
}

const gatewayIP = "10.0.4.1"

type internetSample struct {
	gateway bool
	loss    float64
	rtt     float64
	jitter  float64
}

func internetPoll(samples map[string]internetSample) Sample {
	readings := make([]internetReading, 0, len(samples))
	for ip, s := range samples {
		reading := internetReading{target: ip, gateway: s.gateway, lossPct: s.loss}
		if s.loss < 100 {
			reading.rttMs = s.rtt
			reading.jitter = s.jitter
			reading.hasRTT = true
		}
		readings = append(readings, reading)
	}
	return Sample{Readings: readings}
}

func readingByTarget(readings []internetReading, target string) (internetReading, bool) {
	for _, reading := range readings {
		if reading.target == target {
			return reading, true
		}
	}
	return internetReading{}, false
}
