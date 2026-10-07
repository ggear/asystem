package plugin

import (
	"context"
	"errors"
	"testing"
	"time"

	"network/internal/remote"
)

func TestWireless_Poll(t *testing.T) {
	now := time.Now().Unix()
	devices := []remote.GatewayDevice{{Name: "unmonitored", State: 1, LastSeen: now}}
	for _, name := range wirelessDevices {
		devices = append(devices, remote.GatewayDevice{Name: name, State: 1, LastSeen: now, SystemStats: remote.GatewaySystemStats{CPU: "12.5", Memory: "40"}})
	}
	p := newWirelessPlugin()
	p.probe = func(context.Context) ([]remote.GatewayDevice, error) { return devices, nil }
	sample, err := p.Poll(context.Background())
	if err != nil {
		t.Fatalf("poll: unexpected error %v", err)
	}
	readings, _ := sample.Readings.([]deviceReading)
	if len(readings) != len(wirelessDevices) {
		t.Fatalf("readings: got %d want %d (one per monitored device, unmonitored skipped)", len(readings), len(wirelessDevices))
	}
	for index, reading := range readings {
		if reading.name != wirelessDevices[index] || !reading.up || reading.cpu != 12.5 {
			t.Errorf("reading[%d]: got %+v want monitored device [%s] up with cpu 12.5", index, reading, wirelessDevices[index])
		}
	}
}

func TestWireless_PollError(t *testing.T) {
	p := newWirelessPlugin()
	p.probe = func(context.Context) ([]remote.GatewayDevice, error) {
		return nil, errors.New("controller unreachable")
	}
	if _, err := p.Poll(context.Background()); err == nil {
		t.Fatal("poll: expected probe error to propagate, got nil")
	}
	if got, _ := p.Aggregate([]Sample{{}}); got.Status != StatusDead {
		t.Errorf("aggregate after failed poll: got %s want dead", got.Status)
	}
}
