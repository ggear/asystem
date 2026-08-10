package plugins

import (
	"context"
	"errors"
	"strings"
	"testing"

	"network/internal/plugin"
	"network/internal/remote"
)

func TestEthernet_Poll(t *testing.T) {
	rx, tx := int64(1), int64(2)
	probe := func(context.Context) ([]remote.GatewayDevice, error) {
		return []remote.GatewayDevice{
			{Name: "core", Type: switchType, PortTable: []remote.GatewayPort{
				{PortIdx: 1, Enable: true, Up: true, Speed: 1000, FullDuplex: true, RxErrors: rx, TxErrors: tx},
				{PortIdx: 9, Enable: false, Up: false},
			}},
			{Name: "attic-ap", Type: apType, PortTable: []remote.GatewayPort{{PortIdx: 1, Enable: true, Up: true}}},
		}, nil
	}
	p := &ethernetPlugin{probe: probe, deltas: plugin.NewDeltaTracker()}
	first, err := p.Poll(context.Background())
	if err != nil {
		t.Fatalf("poll: unexpected error %v", err)
	}
	firstReadings, _ := first.Readings.([]ethernetReading)
	if got := firstReadings[0].errors; got != 0 {
		t.Errorf("errors first poll: got %d want 0 (baseline, no delta yet)", got)
	}
	rx, tx = 2, 5
	msg, err := p.Poll(context.Background())
	if err != nil {
		t.Fatalf("poll: unexpected error %v", err)
	}
	readings, _ := msg.Readings.([]ethernetReading)
	if len(readings) != 1 {
		t.Fatalf("readings: got %d want 1 (disabled port and non-switch device must be skipped)", len(readings))
	}
	reading := readings[0]
	if !reading.up {
		t.Errorf("up: got false want true")
	}
	if reading.speed != 1000 {
		t.Errorf("speed: got %d want 1000", reading.speed)
	}
	if !reading.fullDuplex {
		t.Errorf("full_duplex: got false want true")
	}
	if reading.errors != 4 {
		t.Errorf("errors: got %d want 4 (rx+tx delta since last poll)", reading.errors)
	}
}

func TestEthernet_PollError(t *testing.T) {
	p := &ethernetPlugin{probe: func(context.Context) ([]remote.GatewayDevice, error) {
		return nil, errors.New("controller unreachable")
	}}
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
		expectedReason string
		expectedError  bool
	}{
		{
			name:           "fit_all_up",
			samples:        []plugin.Sample{ethernetPoll(portSample{"1", true, 1000, true, 0}, portSample{"2", true, 1000, true, 0})},
			expectedStatus: plugin.StatusFit,
			expectedOK:     true,
			expectedScore:  100,
			expectedReason: "UP",
			expectedError:  false,
		},
		{
			name:           "sick_port_down",
			samples:        []plugin.Sample{ethernetPoll(portSample{"1", true, 1000, true, 0}, portSample{"2", false, 0, false, 0})},
			expectedStatus: plugin.StatusSick,
			expectedOK:     true,
			expectedScore:  50,
			expectedReason: "PORT_DOWN",
			expectedError:  false,
		},
		{
			name:           "sick_speed_degraded",
			samples:        []plugin.Sample{ethernetPoll(portSample{"1", true, 1000, true, 0}, portSample{"2", true, 100, true, 0})},
			expectedStatus: plugin.StatusSick,
			expectedOK:     true,
			expectedScore:  90,
			expectedReason: "SPEED_DEGRADED",
			expectedError:  false,
		},
		{
			name:           "sick_link_errors",
			samples:        []plugin.Sample{ethernetPoll(portSample{"1", true, 1000, true, 0}, portSample{"2", true, 1000, true, 42})},
			expectedStatus: plugin.StatusSick,
			expectedOK:     true,
			expectedScore:  90,
			expectedReason: "LINK_ERRORS",
			expectedError:  false,
		},
		{
			name:           "dead_all_down",
			samples:        []plugin.Sample{ethernetPoll(portSample{"1", false, 0, false, 0}, portSample{"2", false, 0, false, 0})},
			expectedStatus: plugin.StatusDead,
			expectedOK:     false,
			expectedScore:  0,
			expectedReason: "PORT_DOWN",
			expectedError:  false,
		},
		{
			name:           "dead_switch_unreachable",
			samples:        []plugin.Sample{ethernetPoll()},
			expectedStatus: plugin.StatusDead,
			expectedOK:     false,
			expectedScore:  0,
			expectedReason: "SWITCH_UNREACHABLE",
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
			if !strings.HasPrefix(got.Reason, test.expectedReason) {
				t.Errorf("reason: got %q want prefix %q", got.Reason, test.expectedReason)
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
	readings := make([]ethernetReading, 0, len(samples))
	for _, s := range samples {
		readings = append(readings, ethernetReading{
			up: s.up, speed: s.speed, fullDuplex: s.fullDuplex, errors: s.errors})
	}
	return plugin.Sample{Plugin: "ethernet", Readings: readings}
}

func TestEthernet_Report(t *testing.T) {
	readings := []ethernetReading{
		{port: "usw-rack/1", up: true, speed: expectedSpeed, fullDuplex: true},
		{port: "usw-rack/2", up: true, speed: 100, fullDuplex: true, errors: 3},
		{port: "usw-rack/3"},
	}
	points := reportEthernet(readings)
	if len(points) != len(readings) {
		t.Fatalf("points: got %d want %d (one per port)", len(points), len(readings))
	}
	for index, expected := range []string{"usw-rack/1", "usw-rack/2", "usw-rack/3"} {
		if name, ok := ethernetName.Read(points[index]); !ok || name != expected {
			t.Errorf("port[%d]: got %q want %q", index, name, expected)
		}
	}
	if degraded, _ := ethernetDegraded.Read(points[0]); degraded {
		t.Errorf("degraded[1]: got true want false at expected speed")
	}
	if degraded, _ := ethernetDegraded.Read(points[1]); !degraded {
		t.Errorf("degraded[2]: got false want true below expected speed")
	}
	if degraded, _ := ethernetDegraded.Read(points[2]); degraded {
		t.Errorf("degraded[3]: got true want false on a down port")
	}
	if errors, _ := ethernetErrors.Read(points[1]); errors != 3 {
		t.Errorf("errors[2]: got %d want 3", errors)
	}
}
