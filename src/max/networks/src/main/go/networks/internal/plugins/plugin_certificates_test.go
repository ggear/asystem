package plugins

import (
	"testing"

	"networks/internal/plugin"
)

type endpointSample struct {
	addr     string
	verified bool
	days     float64
	pct      float64
}

func certificatesPulse(samples ...endpointSample) plugin.Message {
	points := make([]plugin.Point, 0, len(samples))
	for _, s := range samples {
		tags := []plugin.Tag{{Key: "scope", Value: "endpoint"}, {Key: "endpoint", Value: s.addr}}
		if s.verified {
			points = append(points, plugin.NewPoint(tags, plugin.Float("days_to_expiry", s.days), plugin.Float("validity_pct", s.pct), plugin.Bool("verified", true)))
		} else {
			points = append(points, plugin.NewPoint(tags, plugin.Null("days_to_expiry"), plugin.Null("validity_pct"), plugin.Bool("verified", false)))
		}
	}
	return plugin.Message{Plugin: "certificates", Points: points}
}

func TestDecideCertificates(t *testing.T) {
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
			name:           "fit_valid",
			samples:        []plugin.Message{certificatesPulse(endpointSample{"a:443", true, 90, 60})},
			expectedStatus: plugin.StatusFit,
			expectedOK:     true,
			expectedScore:  60,
			expectedDetail: "VALID",
			expectedError:  false,
		},
		{
			name:           "sick_expiring_soon",
			samples:        []plugin.Message{certificatesPulse(endpointSample{"a:443", true, 10, 5})},
			expectedStatus: plugin.StatusSick,
			expectedOK:     true,
			expectedScore:  5,
			expectedDetail: "EXPIRING_SOON",
			expectedError:  false,
		},
		{
			name:           "sick_verify_failed",
			samples:        []plugin.Message{certificatesPulse(endpointSample{"a:443", true, 90, 60}, endpointSample{addr: "b:443", verified: false})},
			expectedStatus: plugin.StatusSick,
			expectedOK:     true,
			expectedScore:  60,
			expectedDetail: "VERIFY_FAILED",
			expectedError:  false,
		},
		{
			name:           "dead_unreachable",
			samples:        []plugin.Message{certificatesPulse(endpointSample{addr: "a:443", verified: false})},
			expectedStatus: plugin.StatusDead,
			expectedOK:     false,
			expectedScore:  0,
			expectedDetail: "PROBE_UNREACHABLE",
			expectedError:  false,
		},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			got, err := newCertificatesPlugin().Aggregate(test.samples)
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
