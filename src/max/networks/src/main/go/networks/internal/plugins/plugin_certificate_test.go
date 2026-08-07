package plugins

import (
	"context"
	"errors"
	"strings"
	"testing"
	"time"

	"networks/internal/plugin"
)

func TestCertificate_Poll(t *testing.T) {
	now := time.Now()
	p := &certificatePlugin{probe: func(context.Context, string) (certificateResult, error) {
		return certificateResult{notBefore: now.Add(-30 * 24 * time.Hour), notAfter: now.Add(60 * 24 * time.Hour)}, nil
	}}
	msg, err := p.Poll(context.Background())
	if err != nil {
		t.Fatalf("poll: unexpected error %v", err)
	}
	readings, _ := msg.Readings.([]certificateReading)
	if len(readings) != len(certificateEndpoints) {
		t.Fatalf("readings: got %d want %d (one per endpoint)", len(readings), len(certificateEndpoints))
	}
	reading := readings[0]
	if !reading.verified {
		t.Errorf("verified: got false want true")
	}
	if reading.days <= 59 || reading.days > 60 {
		t.Errorf("days: got %v want ~60", reading.days)
	}
	if reading.validity < 66 || reading.validity > 67 {
		t.Errorf("validity: got %v want ~66.7 (60 of 90 days remaining)", reading.validity)
	}
}

func TestCertificate_PollUnverified(t *testing.T) {
	p := &certificatePlugin{probe: func(context.Context, string) (certificateResult, error) {
		return certificateResult{}, errors.New("probe timeout")
	}}
	msg, err := p.Poll(context.Background())
	if err != nil {
		t.Fatalf("poll: unexpected error %v", err)
	}
	readings, _ := msg.Readings.([]certificateReading)
	if len(readings) != len(certificateEndpoints) {
		t.Fatalf("readings: got %d want %d", len(readings), len(certificateEndpoints))
	}
	if readings[0].verified {
		t.Errorf("verified: got true want false on probe failure")
	}
	if readings[0].days != 0 {
		t.Errorf("days: got %v want 0 on probe failure", readings[0].days)
	}
}

func TestCertificate_Diagnose(t *testing.T) {
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
			name:           "fit_valid",
			samples:        []plugin.Sample{certificatePoll(endpointSample{"a:443", true, 90, 60})},
			expectedStatus: plugin.StatusFit,
			expectedOK:     true,
			expectedScore:  60,
			expectedReason: "VALID",
			expectedError:  false,
		},
		{
			name:           "sick_expiring_soon",
			samples:        []plugin.Sample{certificatePoll(endpointSample{"a:443", true, 10, 5})},
			expectedStatus: plugin.StatusSick,
			expectedOK:     true,
			expectedScore:  5,
			expectedReason: "EXPIRING_SOON",
			expectedError:  false,
		},
		{
			name:           "sick_verify_failed",
			samples:        []plugin.Sample{certificatePoll(endpointSample{"a:443", true, 90, 60}, endpointSample{addr: "b:443", verified: false})},
			expectedStatus: plugin.StatusSick,
			expectedOK:     true,
			expectedScore:  60,
			expectedReason: "VERIFY_FAILED",
			expectedError:  false,
		},
		{
			name:           "dead_unreachable",
			samples:        []plugin.Sample{certificatePoll(endpointSample{addr: "a:443", verified: false})},
			expectedStatus: plugin.StatusDead,
			expectedOK:     false,
			expectedScore:  0,
			expectedReason: "PROBE_UNREACHABLE",
			expectedError:  false,
		},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			got, err := newCertificatePlugin().Aggregate(test.samples)
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

type endpointSample struct {
	addr     string
	verified bool
	days     float64
	pct      float64
}

func certificatePoll(samples ...endpointSample) plugin.Sample {
	readings := make([]certificateReading, 0, len(samples))
	for _, s := range samples {
		readings = append(readings, certificateReading{
			endpoint: s.addr, days: s.days, validity: s.pct, verified: s.verified})
	}
	return plugin.Sample{Plugin: "certificate", Readings: readings}
}
