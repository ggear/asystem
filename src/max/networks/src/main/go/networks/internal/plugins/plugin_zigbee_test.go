package plugins

import (
	"context"
	"errors"
	"strings"
	"testing"

	"networks/internal/plugin"
)

func TestZigbee_Poll(t *testing.T) {
	p := &zigbeePlugin{probe: func(context.Context) (bool, bool, []zigbeeReading, error) {
		return true, false, []zigbeeReading{
			{name: "lamp", lqi: 120, hasLQI: true, available: true},
			{name: "coord", isCoordinator: true},
			{name: "plug", available: false},
		}, nil
	}}
	msg, err := p.Poll(context.Background())
	if err != nil {
		t.Fatalf("poll: unexpected error %v", err)
	}
	sample, ok := msg.Readings.(zigbeeSample)
	if !ok {
		t.Fatal("readings: got none want a zigbee sample")
	}
	if !sample.online {
		t.Errorf("bridge online: got false want true")
	}
	if len(sample.devices) != 2 {
		t.Fatalf("devices: got %d want 2 (coordinator skipped)", len(sample.devices))
	}
	lamp := deviceByName(sample.devices, "lamp")
	if lamp == nil {
		t.Fatal("lamp reading missing")
	}
	if !lamp.hasLQI || lamp.lqi != 120 {
		t.Errorf("lamp lqi: got (%d,%v) want (120,true)", lamp.lqi, lamp.hasLQI)
	}
	if !lamp.available {
		t.Errorf("lamp available: got false want true")
	}
	plug := deviceByName(sample.devices, "plug")
	if plug == nil {
		t.Fatal("plug reading missing")
	}
	if plug.hasLQI {
		t.Errorf("plug lqi: got a value want none (no lqi reported)")
	}
	if plug.available {
		t.Errorf("plug available: got true want false")
	}
}

func TestZigbee_PollError(t *testing.T) {
	p := &zigbeePlugin{probe: func(context.Context) (bool, bool, []zigbeeReading, error) {
		return false, false, nil, errors.New("broker unreachable")
	}}
	if _, err := p.Poll(context.Background()); err == nil {
		t.Fatal("poll: expected probe error to propagate, got nil")
	}
}

func TestZigbee_Diagnose(t *testing.T) {
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
			name:           "fit_healthy",
			samples:        []plugin.Sample{zigbeePoll(true, deviceSample{"lamp", true, 100, true}, deviceSample{"plug", true, 100, true})},
			expectedStatus: plugin.StatusFit,
			expectedOK:     true,
			expectedScore:  82,
			expectedReason: "HEALTHY",
			expectedError:  false,
		},
		{
			name:           "sick_devices_offline",
			samples:        []plugin.Sample{zigbeePoll(true, deviceSample{"lamp", true, 100, true}, deviceSample{name: "plug", available: false})},
			expectedStatus: plugin.StatusSick,
			expectedOK:     true,
			expectedScore:  47,
			expectedReason: "DEVICES_OFFLINE",
			expectedError:  false,
		},
		{
			name:           "sick_weak_links",
			samples:        []plugin.Sample{zigbeePoll(true, deviceSample{"lamp", true, 20, true}, deviceSample{"plug", true, 20, true})},
			expectedStatus: plugin.StatusSick,
			expectedOK:     true,
			expectedScore:  72,
			expectedReason: "WEAK_LINKS",
			expectedError:  false,
		},
		{
			name:           "dead_coordinator_down",
			samples:        []plugin.Sample{zigbeePoll(false, deviceSample{"lamp", true, 100, true})},
			expectedStatus: plugin.StatusDead,
			expectedOK:     false,
			expectedScore:  0,
			expectedReason: "COORDINATOR_DOWN",
			expectedError:  false,
		},
		{
			name:           "dead_no_devices",
			samples:        []plugin.Sample{zigbeePoll(true)},
			expectedStatus: plugin.StatusDead,
			expectedOK:     false,
			expectedScore:  0,
			expectedReason: "COORDINATOR_DOWN",
			expectedError:  false,
		},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			got, err := newZigbeePlugin().Aggregate(test.samples)
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

func TestZigbee_Read(t *testing.T) {
	base := zigbeeBaseTopic
	messages := map[string][]byte{
		base + "/bridge/state":      []byte(`{"state":"online"}`),
		base + "/bridge/info":       []byte(`{"permit_join":true}`),
		base + "/bridge/devices":    []byte(`[{"friendly_name":"lamp","type":"EndDevice"},{"friendly_name":"coord","type":"Coordinator"}]`),
		base + "/bridge/logging":    []byte(`ignored`),
		base + "/lamp":              []byte(`{"linkquality":42}`),
		base + "/lamp/availability": []byte(`online`),
	}
	online, permit, devices := readZigbee(base, messages)
	if !online {
		t.Errorf("online: got false want true")
	}
	if !permit {
		t.Errorf("permit_join: got false want true")
	}
	if len(devices) != 2 {
		t.Fatalf("devices: got %d want 2", len(devices))
	}
	lamp, coord := deviceByName(devices, "lamp"), deviceByName(devices, "coord")
	if lamp == nil || coord == nil {
		t.Fatalf("expected lamp and coord, got %+v", devices)
	}
	if !lamp.hasLQI || lamp.lqi != 42 {
		t.Errorf("lamp lqi: got (%d,%v) want (42,true)", lamp.lqi, lamp.hasLQI)
	}
	if !lamp.available {
		t.Errorf("lamp available: got false want true")
	}
	if !coord.isCoordinator {
		t.Errorf("coord isCoordinator: got false want true")
	}
}

func TestZigbee_ReadEdges(t *testing.T) {
	base := zigbeeBaseTopic
	messages := map[string][]byte{
		base + "/bridge/state":   []byte("offline"),
		base + "/bridge/info":    []byte(`not json`),
		base + "/bridge/devices": []byte(`[{"friendly_name":"plug","type":"EndDevice"}]`),
		base + "/plug":           []byte(`{"linkquality":null}`),
	}
	online, permit, devices := readZigbee(base, messages)
	if online {
		t.Errorf("online: got true want false (plain 'offline')")
	}
	if permit {
		t.Errorf("permit: got true want false (malformed info)")
	}
	if len(devices) != 1 {
		t.Fatalf("devices: got %d want 1", len(devices))
	}
	if devices[0].hasLQI {
		t.Errorf("plug lqi: got hasLQI true want false (null linkquality)")
	}
	if devices[0].available {
		t.Errorf("plug available: got true want false (no availability message)")
	}
}

func deviceByName(devices []zigbeeReading, name string) *zigbeeReading {
	for i := range devices {
		if devices[i].name == name {
			return &devices[i]
		}
	}
	return nil
}

type deviceSample struct {
	name      string
	available bool
	lqi       int
	hasLQI    bool
}

func zigbeePoll(bridgeOnline bool, samples ...deviceSample) plugin.Sample {
	devices := make([]zigbeeReading, 0, len(samples))
	for _, s := range samples {
		devices = append(devices, zigbeeReading{
			name: s.name, available: s.available, lqi: s.lqi, hasLQI: s.hasLQI})
	}
	return plugin.Sample{Plugin: "zigbee", Readings: zigbeeSample{online: bridgeOnline, devices: devices}}
}
