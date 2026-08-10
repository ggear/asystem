package plugins

import (
	"context"
	"errors"
	"strings"
	"testing"
	"time"

	"network/internal/plugin"
)

func TestWeewx_Poll(t *testing.T) {
	p := &weewxPlugin{probe: func(context.Context) (float64, bool, bool, error) {
		return 82.4, true, true, nil
	}}
	msg, err := p.Poll(context.Background())
	if err != nil {
		t.Fatalf("poll: unexpected error %v", err)
	}
	reading, ok := msg.Readings.(weewxReading)
	if !ok {
		t.Fatal("readings: got none want a weewx reading")
	}
	if !reading.hasQuality || reading.quality != 82.4 {
		t.Errorf("quality: got %v has=%v want 82.4", reading.quality, reading.hasQuality)
	}
	if !reading.fresh {
		t.Errorf("fresh: got false want true")
	}
}

func TestWeewx_PollError(t *testing.T) {
	p := &weewxPlugin{probe: func(context.Context) (float64, bool, bool, error) {
		return 0, false, false, errors.New("broker unreachable")
	}}
	if _, err := p.Poll(context.Background()); err == nil {
		t.Fatal("poll: expected probe error to propagate, got nil")
	}
}

func TestWeewx_Diagnose(t *testing.T) {
	tests := []struct {
		name           string
		samples        []plugin.Sample
		expectedStatus plugin.Status
		expectedOK     bool
		expectedScore  int
		expectedReason string
	}{
		{
			name:           "fit_fresh_strong_signal",
			samples:        []plugin.Sample{weewxPoll(true, true, 82)},
			expectedStatus: plugin.StatusFit,
			expectedOK:     true,
			expectedScore:  82,
			expectedReason: "HEALTHY",
		},
		{
			name:           "sick_fresh_weak_signal",
			samples:        []plugin.Sample{weewxPoll(true, true, 30)},
			expectedStatus: plugin.StatusSick,
			expectedOK:     true,
			expectedScore:  30,
			expectedReason: "WEAK_SIGNAL",
		},
		{
			name:           "dead_stale_ignores_signal",
			samples:        []plugin.Sample{weewxPoll(false, true, 82)},
			expectedStatus: plugin.StatusDead,
			expectedOK:     false,
			expectedScore:  0,
			expectedReason: "STALE",
		},
		{
			name:           "dead_fresh_no_signal",
			samples:        []plugin.Sample{weewxPoll(true, false, 0)},
			expectedStatus: plugin.StatusDead,
			expectedOK:     false,
			expectedScore:  0,
			expectedReason: "NO_DATA",
		},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			got, err := newWeewxPlugin().Aggregate(test.samples)
			if err != nil {
				t.Fatalf("aggregate: unexpected error %v", err)
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

func TestWeewx_Read(t *testing.T) {
	now := time.Unix(1785117984, 0)
	tests := []struct {
		name           string
		signal         string
		status         string
		wantQuality    float64
		wantHasQuality bool
		wantFresh      bool
	}{
		{name: "fresh_and_quality", signal: "82.4", status: `{"timestamp":1785117984,"pulse":{"ok":true,"value":true}}`, wantQuality: 82.4, wantHasQuality: true, wantFresh: true},
		{name: "within_hour", signal: "50", status: `{"timestamp":1785115000,"pulse":{"ok":true}}`, wantQuality: 50, wantHasQuality: true, wantFresh: true},
		{name: "stale", signal: "90", status: `{"timestamp":1785110000,"pulse":{"ok":true}}`, wantQuality: 90, wantHasQuality: true, wantFresh: false},
		{name: "pulse_down", signal: "90", status: `{"timestamp":1785117984,"pulse":{"ok":false}}`, wantQuality: 90, wantHasQuality: true, wantFresh: false},
		{name: "missing_timestamp", signal: "90", status: `{"pulse":{"ok":true}}`, wantQuality: 90, wantHasQuality: true, wantFresh: false},
		{name: "invalid_status", signal: "90", status: `not-json`, wantQuality: 90, wantHasQuality: true, wantFresh: false},
		{name: "empty_signal", signal: "", status: `{"timestamp":1785117984,"pulse":{"ok":true}}`, wantQuality: 0, wantHasQuality: false, wantFresh: true},
		{name: "non_numeric_signal", signal: "good", status: `{"timestamp":1785117984,"pulse":{"ok":true}}`, wantQuality: 0, wantHasQuality: false, wantFresh: true},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			quality, hasQuality, fresh := readWeewx([]byte(test.signal), []byte(test.status), now)
			if hasQuality != test.wantHasQuality || quality != test.wantQuality {
				t.Errorf("quality: got (%v,%v) want (%v,%v)", quality, hasQuality, test.wantQuality, test.wantHasQuality)
			}
			if fresh != test.wantFresh {
				t.Errorf("fresh: got %v want %v", fresh, test.wantFresh)
			}
		})
	}
}

func weewxPoll(fresh, hasQuality bool, quality float64) plugin.Sample {
	return plugin.Sample{Plugin: "weewx", Readings: weewxReading{
		quality: quality, hasQuality: hasQuality, fresh: fresh}}
}

func TestWeewx_Report(t *testing.T) {
	points := reportWeewx(weewxReading{quality: 82.5, hasQuality: true, fresh: true})
	if len(points) != 1 {
		t.Fatalf("points: got %d want 1", len(points))
	}
	if name, ok := weewxName.Read(points[0]); !ok || name != weewxConsoleName {
		t.Errorf("console: got %q want %q", name, weewxConsoleName)
	}
	if fresh, _ := weewxFresh.Read(points[0]); !fresh {
		t.Errorf("fresh: got false want true")
	}
	if quality, _ := weewxQuality.Read(points[0]); quality != 82.5 {
		t.Errorf("quality_pct: got %v want 82.5", quality)
	}
	points = reportWeewx(weewxReading{fresh: false})
	if _, ok := weewxQuality.Read(points[0]); ok {
		t.Errorf("quality_pct without a retained reading: got set want unset")
	}
}
