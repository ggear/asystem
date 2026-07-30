package plugins

import (
	"context"
	"errors"
	"testing"
	"time"

	"networks/internal/plugin"
)

func TestCerts_Poll(t *testing.T) {
	now := time.Now()
	p := &certsPlugin{probe: func(context.Context, string, string) (probeResult, error) {
		return probeResult{notBefore: now.Add(-30 * 24 * time.Hour), notAfter: now.Add(60 * 24 * time.Hour), verified: true}, nil
	}}
	msg, err := p.Poll(context.Background())
	if err != nil {
		t.Fatalf("poll: unexpected error %v", err)
	}
	if len(msg.Points) != len(endpoints) {
		t.Fatalf("points: got %d want %d (one per endpoint)", len(msg.Points), len(endpoints))
	}
	point := msg.Points[0]
	if verified, _ := point.Bool("verified"); !verified {
		t.Errorf("verified: got false want true")
	}
	days, ok := point.Float("days_to_expiry")
	if !ok {
		t.Fatal("days_to_expiry: got null want a value")
	}
	if days <= 59 || days > 60 {
		t.Errorf("days_to_expiry: got %v want ~60", days)
	}
	validity, ok := point.Float("validity_pct")
	if !ok {
		t.Fatal("validity_pct: got null want a value")
	}
	if validity < 66 || validity > 67 {
		t.Errorf("validity_pct: got %v want ~66.7 (60 of 90 days remaining)", validity)
	}
}

func TestCerts_PollUnverified(t *testing.T) {
	p := &certsPlugin{probe: func(context.Context, string, string) (probeResult, error) {
		return probeResult{}, errors.New("probe timeout")
	}}
	msg, err := p.Poll(context.Background())
	if err != nil {
		t.Fatalf("poll: unexpected error %v", err)
	}
	if len(msg.Points) != len(endpoints) {
		t.Fatalf("points: got %d want %d", len(msg.Points), len(endpoints))
	}
	point := msg.Points[0]
	if verified, _ := point.Bool("verified"); verified {
		t.Errorf("verified: got true want false on probe failure")
	}
	if _, ok := point.Float("days_to_expiry"); ok {
		t.Errorf("days_to_expiry: got a value want null on probe failure")
	}
}

func TestCerts_Diagnose(t *testing.T) {
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
			name:           "fit_valid",
			samples:        []plugin.Sample{certsPoll(endpointSample{"a:443", true, 90, 60})},
			expectedStatus: plugin.StatusFit,
			expectedOK:     true,
			expectedScore:  60,
			expectedDetail: "VALID",
			expectedError:  false,
		},
		{
			name:           "sick_expiring_soon",
			samples:        []plugin.Sample{certsPoll(endpointSample{"a:443", true, 10, 5})},
			expectedStatus: plugin.StatusSick,
			expectedOK:     true,
			expectedScore:  5,
			expectedDetail: "EXPIRING_SOON",
			expectedError:  false,
		},
		{
			name:           "sick_verify_failed",
			samples:        []plugin.Sample{certsPoll(endpointSample{"a:443", true, 90, 60}, endpointSample{addr: "b:443", verified: false})},
			expectedStatus: plugin.StatusSick,
			expectedOK:     true,
			expectedScore:  60,
			expectedDetail: "VERIFY_FAILED",
			expectedError:  false,
		},
		{
			name:           "dead_unreachable",
			samples:        []plugin.Sample{certsPoll(endpointSample{addr: "a:443", verified: false})},
			expectedStatus: plugin.StatusDead,
			expectedOK:     false,
			expectedScore:  0,
			expectedDetail: "PROBE_UNREACHABLE",
			expectedError:  false,
		},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			got, err := newCertsPlugin().Aggregate(test.samples)
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

type endpointSample struct {
	addr     string
	verified bool
	days     float64
	pct      float64
}

func certsPoll(samples ...endpointSample) plugin.Sample {
	points := make([]plugin.Point, 0, len(samples))
	for _, s := range samples {
		tags := []plugin.Tag{{Key: "scope", Value: "endpoint"}, {Key: "endpoint", Value: s.addr}}
		if s.verified {
			points = append(points, plugin.NewPoint(tags, plugin.Float("days_to_expiry", s.days), plugin.Float("validity_pct", s.pct), plugin.Bool("verified", true)))
		} else {
			points = append(points, plugin.NewPoint(tags, plugin.Null("days_to_expiry"), plugin.Null("validity_pct"), plugin.Bool("verified", false)))
		}
	}
	return plugin.Sample{Plugin: "certs", Points: points}
}
