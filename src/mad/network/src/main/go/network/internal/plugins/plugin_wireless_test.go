package plugins

import (
	"context"
	"errors"
	"strings"
	"testing"

	"network/internal/plugin"
	"network/internal/remote"
)

func TestWireless_Poll(t *testing.T) {
	devices := []remote.GatewayDevice{
		{Name: "deck", Type: apType, State: 1, Satisfaction: 90, NumSta: 4},
		{Name: "hallway", Type: apType, State: 0, Satisfaction: 0, NumSta: 0},
		{Name: "core", Type: switchType, State: 1},
	}
	p := &wirelessPlugin{probe: func(context.Context) ([]remote.GatewayDevice, error) {
		return devices, nil
	}}
	msg, err := p.Poll(context.Background())
	if err != nil {
		t.Fatalf("poll: unexpected error %v", err)
	}
	readings, _ := msg.Readings.([]wirelessReading)
	if len(readings) != 2 {
		t.Fatalf("readings: got %d want 2 (switch must be skipped)", len(readings))
	}
	deck := readings[0]
	if !deck.up {
		t.Errorf("deck up: got false want true")
	}
	if deck.experience != 90 {
		t.Errorf("deck experience: got %d want 90", deck.experience)
	}
	if deck.clients != 4 {
		t.Errorf("deck clients: got %d want 4", deck.clients)
	}
	if readings[1].up {
		t.Errorf("hallway up: got true want false")
	}
}

func TestWireless_PollError(t *testing.T) {
	p := &wirelessPlugin{probe: func(context.Context) ([]remote.GatewayDevice, error) {
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
		expectedReason string
		expectedError  bool
	}{
		{
			name:           "fit_all_up_good_experience",
			samples:        []plugin.Sample{wirelessPoll(apSample{"deck", true, 90}, apSample{"hallway", true, 90})},
			expectedStatus: plugin.StatusFit,
			expectedOK:     true,
			expectedScore:  95,
			expectedReason: "UP",
			expectedError:  false,
		},
		{
			name:           "sick_ap_down",
			samples:        []plugin.Sample{wirelessPoll(apSample{"deck", true, 90}, apSample{"hallway", false, 0})},
			expectedStatus: plugin.StatusSick,
			expectedOK:     true,
			expectedScore:  70,
			expectedReason: "AP_DOWN",
			expectedError:  false,
		},
		{
			name:           "sick_poor_clients",
			samples:        []plugin.Sample{wirelessPoll(apSample{"deck", true, 60}, apSample{"hallway", true, 60})},
			expectedStatus: plugin.StatusSick,
			expectedOK:     true,
			expectedScore:  80,
			expectedReason: "POOR_CLIENTS",
			expectedError:  false,
		},
		{
			name:           "dead_all_down",
			samples:        []plugin.Sample{wirelessPoll(apSample{"deck", false, 0}, apSample{"hallway", false, 0})},
			expectedStatus: plugin.StatusDead,
			expectedOK:     false,
			expectedScore:  0,
			expectedReason: "AP_DOWN",
			expectedError:  false,
		},
		{
			name:           "dead_controller_unreachable",
			samples:        []plugin.Sample{wirelessPoll()},
			expectedStatus: plugin.StatusDead,
			expectedOK:     false,
			expectedScore:  0,
			expectedReason: "CONTROLLER_UNREACHABLE",
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
			if !strings.HasPrefix(got.Reason, test.expectedReason) {
				t.Errorf("reason: got %q want prefix %q", got.Reason, test.expectedReason)
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
	readings := make([]wirelessReading, 0, len(samples))
	for _, s := range samples {
		readings = append(readings, wirelessReading{up: s.up, experience: s.exp})
	}
	return plugin.Sample{Plugin: "wireless", Readings: readings}
}

func TestWireless_Report(t *testing.T) {
	readings := []wirelessReading{
		{name: "ap-study", up: true, experience: 94, clients: 7},
		{name: "ap-shed", up: false},
	}
	points := reportWireless(readings)
	if len(points) != len(readings) {
		t.Fatalf("points: got %d want %d (one per access point)", len(points), len(readings))
	}
	for index, expected := range []string{"ap-study", "ap-shed"} {
		if name, ok := wirelessName.Read(points[index]); !ok || name != expected {
			t.Errorf("accesspoint[%d]: got %q want %q", index, name, expected)
		}
	}
	if up, _ := wirelessUp.Read(points[0]); !up {
		t.Errorf("up[ap-study]: got false want true")
	}
	if experience, _ := wirelessExperience.Read(points[0]); experience != 94 {
		t.Errorf("experience_pct[ap-study]: got %v want 94", experience)
	}
	if clients, _ := wirelessClients.Read(points[0]); clients != 7 {
		t.Errorf("clients[ap-study]: got %d want 7", clients)
	}
}
