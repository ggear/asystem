package plugins

import (
	"context"
	"errors"
	"testing"
	"time"

	"networks/internal/plugin"
)

func TestDomain_Poll(t *testing.T) {
	p := &domainPlugin{probe: func(_ context.Context, _, _ string) (domainResult, error) {
		return domainResult{addresses: []string{"10.0.0.1"}, latency: 12 * time.Millisecond}, nil
	}}
	msg, err := p.Poll(context.Background())
	if err != nil {
		t.Fatalf("poll: unexpected error %v", err)
	}
	if len(msg.Points) != len(resolvers) {
		t.Fatalf("points: got %d want %d (one per resolver)", len(msg.Points), len(resolvers))
	}
	point := msg.Points[0]
	if resolved, _ := point.Bool("resolved"); !resolved {
		t.Errorf("resolved: got false want true")
	}
	if addresses, _ := point.Tag("addresses"); addresses != "10.0.0.1" {
		t.Errorf("addresses: got %q want %q", addresses, "10.0.0.1")
	}
	if _, ok := point.Float("latency_ms"); !ok {
		t.Fatal("latency_ms: got null want a value")
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
	if len(msg.Points) != len(resolvers) {
		t.Fatalf("points: got %d want %d", len(msg.Points), len(resolvers))
	}
	point := msg.Points[0]
	if resolved, _ := point.Bool("resolved"); resolved {
		t.Errorf("resolved: got true want false on probe failure")
	}
	if _, ok := point.Float("latency_ms"); ok {
		t.Errorf("latency_ms: got a value want null on probe failure")
	}
}

func TestDomain_Diagnose(t *testing.T) {
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
			name: "fit_all_agree",
			samples: []plugin.Sample{domainPoll(
				resolverSample{"cloudflare", true, "10.0.0.1", 8},
				resolverSample{"google", true, "10.0.0.1", 9},
				resolverSample{"quad9", true, "10.0.0.1", 11})},
			expectedStatus: plugin.StatusFit,
			expectedOK:     true,
			expectedScore:  100,
			expectedDetail: "RESOLVED",
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
			expectedDetail: "PARTIAL_RESOLUTION",
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
			expectedDetail: "RECORD_MISMATCH",
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
			expectedDetail: "NO_RESOLUTION",
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
			if got.Detail != test.expectedDetail {
				t.Errorf("detail: got %s want %s", got.Detail, test.expectedDetail)
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
	points := make([]plugin.Point, 0, len(samples))
	for _, s := range samples {
		tags := []plugin.Tag{{Key: "scope", Value: "resolver"}, {Key: "resolver", Value: s.name}, {Key: "addresses", Value: s.addresses}}
		if s.resolved {
			points = append(points, plugin.NewPoint(tags, plugin.Bool("resolved", true), plugin.Float("latency_ms", s.latency)))
		} else {
			points = append(points, plugin.NewPoint(tags, plugin.Bool("resolved", false), plugin.Null("latency_ms")))
		}
	}
	return plugin.Sample{Plugin: "domain", Points: points}
}
