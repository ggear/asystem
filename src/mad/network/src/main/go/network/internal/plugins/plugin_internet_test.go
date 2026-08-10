package plugins

import (
	"context"
	"errors"
	"strings"
	"testing"
	"time"

	"network/internal/plugin"
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
		samples        []plugin.Sample
		expectedStatus plugin.Status
		expectedOK     bool
		expectedScore  int
		expectedReason string
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
			expectedReason: "UP",
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
			expectedReason: "ELEVATED_LOSS",
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
			expectedReason: "ELEVATED_LOSS",
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
			expectedReason: "HIGH_LATENCY",
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
			expectedReason: "ISP_DOWN",
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
			expectedReason: "LAN_DOWN",
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
			if !strings.HasPrefix(got.Reason, test.expectedReason) {
				t.Errorf("reason: got %q want prefix %q", got.Reason, test.expectedReason)
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
	readings := make([]internetReading, 0, len(samples))
	for ip, s := range samples {
		reading := internetReading{target: ip, gateway: s.scope == gatewayScope, lossPct: s.loss}
		if s.loss < 100 {
			reading.rttMs = s.rtt
			reading.jitter = s.jitter
			reading.hasRTT = true
		}
		readings = append(readings, reading)
	}
	return plugin.Sample{Plugin: "internet", Readings: readings}
}

func readingByTarget(readings []internetReading, target string) (internetReading, bool) {
	for _, reading := range readings {
		if reading.target == target {
			return reading, true
		}
	}
	return internetReading{}, false
}

func TestInternet_Report(t *testing.T) {
	accumulators := map[string]*targetAccumulator{
		"10.0.2.1": {gateway: true, lossSum: 0, lossCount: 1, rttSum: 2, rttCount: 1, jitterSum: 1, jitterCount: 1},
		"1.1.1.1":  {lossSum: 10, lossCount: 1, rttSum: 24, rttCount: 1, jitterSum: 3, jitterCount: 1},
		"8.8.8.8":  {lossSum: 100, lossCount: 1},
	}
	points := reportInternet([]string{"10.0.2.1", "1.1.1.1", "8.8.8.8"}, accumulators)
	if len(points) != len(accumulators) {
		t.Fatalf("points: got %d want %d (one per target)", len(points), len(accumulators))
	}
	for index, expected := range []string{gatewayScope, "1.1.1.1", "8.8.8.8"} {
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
	if _, ok := internetRTT.Read(points[2]); ok {
		t.Errorf("rtt_ms without a reply: got set want unset")
	}
}
