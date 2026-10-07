package plugin

import (
	"context"
	"errors"
	"slices"
	"testing"
	"time"

	"network/internal/remote"
)

func TestEthernet_Poll(t *testing.T) {
	now := time.Now().Unix()
	devices := []remote.GatewayDevice{{Name: "unmonitored", State: 1, LastSeen: now}}
	for _, name := range ethernetDevices {
		devices = append(devices, remote.GatewayDevice{Name: name, State: 1, LastSeen: now, SystemStats: remote.GatewaySystemStats{CPU: "12.5", Memory: "40"}})
	}
	p := newEthernetPlugin()
	p.probe = func(context.Context) ([]remote.GatewayDevice, []remote.GatewayClient, error) {
		return devices, nil, nil
	}
	sample, err := p.Poll(context.Background())
	if err != nil {
		t.Fatalf("poll: unexpected error %v", err)
	}
	readings, _ := sample.Readings.(ethernetSample)
	if len(readings.devices) != len(ethernetDevices) {
		t.Fatalf("readings: got %d want %d (one per monitored device, unmonitored skipped)", len(readings.devices), len(ethernetDevices))
	}
	for index, reading := range readings.devices {
		if reading.name != ethernetDevices[index] || !reading.up || reading.cpu != 12.5 {
			t.Errorf("reading[%d]: got %+v want monitored device [%s] up with cpu 12.5", index, reading, ethernetDevices[index])
		}
	}
}

func TestEthernet_PollError(t *testing.T) {
	p := newEthernetPlugin()
	p.probe = func(context.Context) ([]remote.GatewayDevice, []remote.GatewayClient, error) {
		return nil, nil, errors.New("controller unreachable")
	}
	if _, err := p.Poll(context.Background()); err == nil {
		t.Fatal("poll: expected probe error to propagate, got nil")
	}
	if got, _ := p.Aggregate([]Sample{{}}); got.Status != StatusDead {
		t.Errorf("aggregate after failed poll: got %s want dead", got.Status)
	}
}

func TestEthernet_Read(t *testing.T) {
	devices := []remote.GatewayDevice{
		{Name: "usw-dar-ceiling", Mac: "sw", PortTable: []remote.GatewayPort{
			{PortIdx: 1, Name: "Port 1", PoePower: "7.96"},
			{PortIdx: 2, Name: "Port 2", PoePower: "2.84"},
			{PortIdx: 4, Name: "Port 4", PoePower: "0.00"},
			{PortIdx: 6, Name: "Garden Lights", PoePower: "1.50"},
			{PortIdx: 9, Name: "Port 9"},
		}},
		{Name: "uap-dar-hallway", Uplink: remote.GatewayUplink{UplinkDeviceName: "usw-dar-ceiling", UplinkRemotePort: 1}},
		{Name: "usw-unmonitored", Mac: "other", PortTable: []remote.GatewayPort{{PortIdx: 1, PoePower: "9.00"}}},
	}
	clients := []remote.GatewayClient{
		{Hostname: "uvc-dar-ada.local.janeandgraham.com", SwMac: "sw", SwPort: 2},
		{Name: "a-phone-on-the-ap", Hostname: "phone", SwMac: "sw", SwPort: 1},
		{Name: "raspbpi-jen", SwMac: "sw", SwPort: 9},
	}
	readings := readEthernet(devices, clients, []string{"usw-dar-ceiling"})
	expected := []ethernetPoweredReading{
		{name: "uap-dar-hallway", power: 7.96},
		{name: "uvc-dar-ada", power: 2.84},
		{name: "usw-dar-ceiling/Garden Lights", power: 1.5},
	}
	if len(readings) != len(expected) {
		t.Fatalf("readings: got %+v want %+v (unpowered ports and unmonitored switches skipped)", readings, expected)
	}
	for index, want := range expected {
		if readings[index] != want {
			t.Errorf("reading[%d]: got %+v want %+v", index, readings[index], want)
		}
	}
}

func TestEthernet_ReadLabelsAreStable(t *testing.T) {
	devices := []remote.GatewayDevice{
		{Name: "sw", Mac: "sw", PortTable: []remote.GatewayPort{
			{PortIdx: 1, Name: "Port 1", PoePower: "3.00"},
			{PortIdx: 2, Name: "Port 2", PoePower: "3.00"},
			{PortIdx: 3, Name: "Port 3", PoePower: "5.00"},
		}},
	}
	clients := []remote.GatewayClient{
		{Hostname: "uvc-g4-instant.local", SwMac: "sw", SwPort: 1},
		{Hostname: "uvc-g4-instant.local", SwMac: "sw", SwPort: 2},
		{Name: "zeta-sensor", SwMac: "sw", SwPort: 3},
		{Name: "alpha-flex", SwMac: "sw", SwPort: 3},
	}
	for range 3 {
		slices.Reverse(clients)
		got := readEthernet(devices, clients, []string{"sw"})
		want := []ethernetPoweredReading{{name: "sw/Port 1", power: 3}, {name: "sw/Port 2", power: 3}, {name: "alpha-flex", power: 5}}
		if !slices.Equal(got, want) {
			t.Fatalf("readings: got %+v want %+v (colliding labels fall back to the port, several clients pick the first by name in any order)", got, want)
		}
	}
}

func TestEthernet_Report(t *testing.T) {
	points := reportEthernet([]ethernetPoweredReading{{name: "uvc-dar-ada", power: 2.844}})
	if len(points) != 1 {
		t.Fatalf("points: got %d want 1", len(points))
	}
	if name, _ := ethernetPoweredName.Read(points[0]); name != "uvc-dar-ada" {
		t.Errorf("powered: got %q want uvc-dar-ada", name)
	}
	if power, ok := ethernetPoweredPower.Read(points[0]); !ok || power != 2.84 {
		t.Errorf("power_w: got %v (set %v) want 2.84", power, ok)
	}
}
