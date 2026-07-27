package plugins

import (
	"context"
	"errors"
	"testing"

	"networks/internal/engine"
	"networks/internal/plugin"
)

func TestEthernet_Poll(t *testing.T) {
	rx, tx := int64(1), int64(2)
	probe := func(context.Context) ([]engine.RouterDevice, error) {
		return []engine.RouterDevice{
			{Name: "core", Type: switchType, PortTable: []engine.RouterPort{
				{PortIdx: 1, Enable: true, Up: true, Speed: 1000, FullDuplex: true, RxErrors: rx, TxErrors: tx},
				{PortIdx: 9, Enable: false, Up: false},
			}},
			{Name: "attic-ap", Type: apType, PortTable: []engine.RouterPort{{PortIdx: 1, Enable: true, Up: true}}},
		}, nil
	}
	p := &ethernetPlugin{probe: probe, lastErrors: map[string]int64{}}
	first, err := p.Poll(context.Background())
	if err != nil {
		t.Fatalf("poll: unexpected error %v", err)
	}
	if got, _ := first.Points[0].Int("errors"); got != 0 {
		t.Errorf("errors first poll: got %d want 0 (baseline, no delta yet)", got)
	}
	rx, tx = 2, 5
	msg, err := p.Poll(context.Background())
	if err != nil {
		t.Fatalf("poll: unexpected error %v", err)
	}
	if len(msg.Points) != 1 {
		t.Fatalf("points: got %d want 1 (disabled port and non-switch device must be skipped)", len(msg.Points))
	}
	point := msg.Points[0]
	if got, _ := point.Tag("switch"); got != "core" {
		t.Errorf("switch tag: got %q want core", got)
	}
	if got, _ := point.Tag("port"); got != "1" {
		t.Errorf("port tag: got %q want 1", got)
	}
	if up, _ := point.Bool("up"); !up {
		t.Errorf("up: got false want true")
	}
	if got, _ := point.Int("speed"); got != 1000 {
		t.Errorf("speed: got %d want 1000", got)
	}
	if fd, _ := point.Bool("full_duplex"); !fd {
		t.Errorf("full_duplex: got false want true")
	}
	if got, _ := point.Int("errors"); got != 4 {
		t.Errorf("errors: got %d want 4 (rx+tx delta since last poll)", got)
	}
}

func TestEthernet_PollError(t *testing.T) {
	p := &ethernetPlugin{probe: func(context.Context) ([]engine.RouterDevice, error) { return nil, errors.New("controller unreachable") }}
	if _, err := p.Poll(context.Background()); err == nil {
		t.Fatal("poll: expected probe error to propagate, got nil")
	}
}

func TestEthernet_Diagnose(t *testing.T) {
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
			name:           "fit_all_up",
			samples:        []plugin.Sample{ethernetPoll(portSample{"1", true, 1000, true, 0}, portSample{"2", true, 1000, true, 0})},
			expectedStatus: plugin.StatusFit,
			expectedOK:     true,
			expectedScore:  100,
			expectedDetail: "UP",
			expectedError:  false,
		},
		{
			name:           "sick_port_down",
			samples:        []plugin.Sample{ethernetPoll(portSample{"1", true, 1000, true, 0}, portSample{"2", false, 0, false, 0})},
			expectedStatus: plugin.StatusSick,
			expectedOK:     true,
			expectedScore:  50,
			expectedDetail: "PORT_DOWN",
			expectedError:  false,
		},
		{
			name:           "sick_speed_degraded",
			samples:        []plugin.Sample{ethernetPoll(portSample{"1", true, 1000, true, 0}, portSample{"2", true, 100, true, 0})},
			expectedStatus: plugin.StatusSick,
			expectedOK:     true,
			expectedScore:  90,
			expectedDetail: "SPEED_DEGRADED",
			expectedError:  false,
		},
		{
			name:           "sick_link_errors",
			samples:        []plugin.Sample{ethernetPoll(portSample{"1", true, 1000, true, 0}, portSample{"2", true, 1000, true, 42})},
			expectedStatus: plugin.StatusSick,
			expectedOK:     true,
			expectedScore:  90,
			expectedDetail: "LINK_ERRORS",
			expectedError:  false,
		},
		{
			name:           "dead_all_down",
			samples:        []plugin.Sample{ethernetPoll(portSample{"1", false, 0, false, 0}, portSample{"2", false, 0, false, 0})},
			expectedStatus: plugin.StatusDead,
			expectedOK:     false,
			expectedScore:  0,
			expectedDetail: "PORT_DOWN",
			expectedError:  false,
		},
		{
			name:           "dead_switch_unreachable",
			samples:        []plugin.Sample{ethernetPoll()},
			expectedStatus: plugin.StatusDead,
			expectedOK:     false,
			expectedScore:  0,
			expectedDetail: "SWITCH_UNREACHABLE",
			expectedError:  false,
		},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			got, err := newEthernetPlugin().Aggregate(test.samples)
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

type portSample struct {
	port       string
	up         bool
	speed      int64
	fullDuplex bool
	errors     int64
}

func ethernetPoll(samples ...portSample) plugin.Sample {
	points := make([]plugin.Point, 0, len(samples))
	for _, s := range samples {
		tags := []plugin.Tag{{Key: "scope", Value: "port"}, {Key: "switch", Value: "core"}, {Key: "port", Value: s.port}}
		points = append(points, plugin.NewPoint(tags, plugin.Bool("up", s.up), plugin.Int("speed", s.speed), plugin.Bool("full_duplex", s.fullDuplex), plugin.Int("errors", s.errors)))
	}
	return plugin.Sample{Plugin: "ethernet", Points: points}
}

func pointByTag(points []plugin.Point, key, value string) (plugin.Point, bool) {
	for _, point := range points {
		if v, _ := point.Tag(key); v == value {
			return point, true
		}
	}
	return plugin.Point{}, false
}
