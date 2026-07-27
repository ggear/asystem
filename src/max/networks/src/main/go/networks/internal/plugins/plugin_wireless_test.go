package plugins

import (
	"context"
	"errors"
	"testing"

	"networks/internal/engine"
	"networks/internal/plugin"
)

func TestWireless_Poll(t *testing.T) {
	devices := []engine.RouterDevice{
		{Name: "deck", Type: apType, State: 1, Satisfaction: 90, NumSta: 4},
		{Name: "hallway", Type: apType, State: 0, Satisfaction: 0, NumSta: 0},
		{Name: "core", Type: switchType, State: 1},
	}
	p := &wirelessPlugin{probe: func(context.Context) ([]engine.RouterDevice, error) {
		return devices, nil
	}}
	msg, err := p.Poll(context.Background())
	if err != nil {
		t.Fatalf("poll: unexpected error %v", err)
	}
	if len(msg.Points) != 2 {
		t.Fatalf("points: got %d want 2 (switch must be skipped)", len(msg.Points))
	}
	deck, ok := pointByTag(msg.Points, "ap", "deck")
	if !ok {
		t.Fatal("deck ap point missing")
	}
	if up, _ := deck.Bool("up"); !up {
		t.Errorf("deck up: got false want true")
	}
	if got, _ := deck.Int("experience"); got != 90 {
		t.Errorf("deck experience: got %d want 90", got)
	}
	if got, _ := deck.Int("num_clients"); got != 4 {
		t.Errorf("deck num_clients: got %d want 4", got)
	}
	hallway, ok := pointByTag(msg.Points, "ap", "hallway")
	if !ok {
		t.Fatal("hallway ap point missing")
	}
	if up, _ := hallway.Bool("up"); up {
		t.Errorf("hallway up: got true want false")
	}
}

func TestWireless_PollError(t *testing.T) {
	p := &wirelessPlugin{probe: func(context.Context) ([]engine.RouterDevice, error) {
		return nil, errors.New("controller unreachable")
	}}
	if _, err := p.Poll(context.Background()); err == nil {
		t.Fatal("poll: expected probe error to propagate, got nil")
	}
}

func TestWireless_Diagnose(t *testing.T) {
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
			name:           "fit_all_up_good_experience",
			samples:        []plugin.Sample{wirelessPoll(apSample{"deck", true, 90}, apSample{"hallway", true, 90})},
			expectedStatus: plugin.StatusFit,
			expectedOK:     true,
			expectedScore:  95,
			expectedDetail: "UP",
			expectedError:  false,
		},
		{
			name:           "sick_ap_down",
			samples:        []plugin.Sample{wirelessPoll(apSample{"deck", true, 90}, apSample{"hallway", false, 0})},
			expectedStatus: plugin.StatusSick,
			expectedOK:     true,
			expectedScore:  70,
			expectedDetail: "AP_DOWN",
			expectedError:  false,
		},
		{
			name:           "sick_poor_clients",
			samples:        []plugin.Sample{wirelessPoll(apSample{"deck", true, 60}, apSample{"hallway", true, 60})},
			expectedStatus: plugin.StatusSick,
			expectedOK:     true,
			expectedScore:  80,
			expectedDetail: "POOR_CLIENTS",
			expectedError:  false,
		},
		{
			name:           "dead_all_down",
			samples:        []plugin.Sample{wirelessPoll(apSample{"deck", false, 0}, apSample{"hallway", false, 0})},
			expectedStatus: plugin.StatusDead,
			expectedOK:     false,
			expectedScore:  0,
			expectedDetail: "AP_DOWN",
			expectedError:  false,
		},
		{
			name:           "dead_controller_unreachable",
			samples:        []plugin.Sample{wirelessPoll()},
			expectedStatus: plugin.StatusDead,
			expectedOK:     false,
			expectedScore:  0,
			expectedDetail: "CONTROLLER_UNREACHABLE",
			expectedError:  false,
		},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			got, err := newWirelessPlugin().Aggregate(test.samples)
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

type apSample struct {
	name string
	up   bool
	exp  int64
}

func wirelessPoll(samples ...apSample) plugin.Sample {
	points := make([]plugin.Point, 0, len(samples))
	for _, s := range samples {
		tags := []plugin.Tag{{Key: "scope", Value: "ap"}, {Key: "ap", Value: s.name}}
		points = append(points, plugin.NewPoint(tags, plugin.Bool("up", s.up), plugin.Int("experience", s.exp), plugin.Int("num_clients", 0)))
	}
	return plugin.Sample{Plugin: "wireless", Points: points}
}
