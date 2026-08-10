package plugins

import (
	"context"
	"errors"
	"strings"
	"testing"
	"time"

	"network/internal/plugin"
)

func TestDomain_Poll(t *testing.T) {
	p := &domainPlugin{probe: func(_ context.Context, _, _ string) (domainResult, error) {
		return domainResult{addresses: []string{"10.0.0.1"}, latency: 12 * time.Millisecond}, nil
	}}
	msg, err := p.Poll(context.Background())
	if err != nil {
		t.Fatalf("poll: unexpected error %v", err)
	}
	readings, _ := msg.Readings.([]domainReading)
	if len(readings) != len(domainResolvers) {
		t.Fatalf("readings: got %d want %d (one per resolver)", len(readings), len(domainResolvers))
	}
	reading := readings[0]
	if !reading.resolved {
		t.Errorf("resolved: got false want true")
	}
	if reading.addresses != "10.0.0.1" {
		t.Errorf("addresses: got %q want %q", reading.addresses, "10.0.0.1")
	}
}

func TestDomain_PollUnresolved(t *testing.T) {
	p := &domainPlugin{probe: func(context.Context, string, string) (domainResult, error) {
		return domainResult{}, errors.New("server timeout")
	}}
	msg, err := p.Poll(context.Background())
	if err != nil {
		t.Fatalf("poll: unexpected error %v", err)
	}
	readings, _ := msg.Readings.([]domainReading)
	if len(readings) != len(domainResolvers) {
		t.Fatalf("readings: got %d want %d", len(readings), len(domainResolvers))
	}
	if readings[0].resolved {
		t.Errorf("resolved: got true want false on probe failure")
	}
	if readings[0].latencyMs != 0 {
		t.Errorf("latency: got %v want 0 on probe failure", readings[0].latencyMs)
	}
}

func TestDomain_Diagnose(t *testing.T) {
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
			name: "fit_all_agree",
			samples: []plugin.Sample{domainPoll(
				resolverSample{"cloudflare", true, "10.0.0.1", 8},
				resolverSample{"google", true, "10.0.0.1", 9},
				resolverSample{"quad9", true, "10.0.0.1", 11})},
			expectedStatus: plugin.StatusFit,
			expectedOK:     true,
			expectedScore:  100,
			expectedReason: "RESOLVED",
			expectedError:  false,
		},
		{
			name: "sick_partial_resolution",
			samples: []plugin.Sample{domainPoll(
				resolverSample{"cloudflare", true, "10.0.0.1", 8},
				resolverSample{"google", true, "10.0.0.1", 9},
				resolverSample{name: "quad9", resolved: false})},
			expectedStatus: plugin.StatusSick,
			expectedOK:     true,
			expectedScore:  67,
			expectedReason: "PARTIAL_RESOLUTION",
			expectedError:  false,
		},
		{
			name: "sick_record_mismatch",
			samples: []plugin.Sample{domainPoll(
				resolverSample{"cloudflare", true, "10.0.0.1", 8},
				resolverSample{"google", true, "10.0.0.1", 9},
				resolverSample{"quad9", true, "10.0.0.2", 11})},
			expectedStatus: plugin.StatusSick,
			expectedOK:     true,
			expectedScore:  67,
			expectedReason: "RECORD_MISMATCH",
			expectedError:  false,
		},
		{
			name: "dead_no_resolution",
			samples: []plugin.Sample{domainPoll(
				resolverSample{name: "cloudflare", resolved: false},
				resolverSample{name: "google", resolved: false})},
			expectedStatus: plugin.StatusDead,
			expectedOK:     false,
			expectedScore:  0,
			expectedReason: "NO_RESOLUTION",
			expectedError:  false,
		},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			got, err := newDomainPlugin().Aggregate(test.samples)
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

type resolverSample struct {
	name      string
	resolved  bool
	addresses string
	latency   float64
}

func domainPoll(samples ...resolverSample) plugin.Sample {
	readings := make([]domainReading, 0, len(samples))
	for _, s := range samples {
		readings = append(readings, domainReading{
			resolver: s.name, addresses: s.addresses, resolved: s.resolved, latencyMs: s.latency})
	}
	return plugin.Sample{Plugin: "domain", Readings: readings}
}

func TestDomain_Report(t *testing.T) {
	readings := []domainReading{
		{resolver: "cloudflare", addresses: "10.0.0.1", resolved: true, latencyMs: 12},
		{resolver: "google", addresses: "10.0.0.2", resolved: true, latencyMs: 20},
		{resolver: "quad9"},
	}
	points := reportDomain(readings, "10.0.0.1")
	if len(points) != len(readings) {
		t.Fatalf("points: got %d want %d (one per resolver)", len(points), len(readings))
	}
	for index, expected := range []string{"cloudflare", "google", "quad9"} {
		if name, ok := domainResolverName.Read(points[index]); !ok || name != expected {
			t.Errorf("resolver[%d]: got %q want %q", index, name, expected)
		}
	}
	if agreed, _ := domainOK.Read(points[0]); !agreed {
		t.Errorf("ok[cloudflare]: got false want true on consensus match")
	}
	if agreed, _ := domainOK.Read(points[1]); agreed {
		t.Errorf("ok[google]: got true want false off consensus")
	}
	if resolved, _ := domainResolved.Read(points[2]); resolved {
		t.Errorf("resolved[quad9]: got true want false")
	}
	if latency, _ := domainLatencyMs.Read(points[0]); latency != 12 {
		t.Errorf("latency_ms[cloudflare]: got %v want 12", latency)
	}
}
