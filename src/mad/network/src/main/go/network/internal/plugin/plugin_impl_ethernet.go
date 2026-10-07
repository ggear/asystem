package plugin

import (
	"context"
	"slices"
	"strconv"
	"strings"
	"time"

	"network/internal/remote"
	"network/internal/schema"
	"network/internal/scribe"
)

var (
	ethernetDevices      = []string{"udm-dar", "usw-dar-ceiling"}
	ethernetDevice       = declareDevices("ethernet/switch", "wired network health, one row per gateway or switch", "switch", "name of the gateway or switch", ethernetDevices, true)
	ethernetPowered      = schema.Declare("ethernet/powered", "power drawn over ethernet, one row per device a monitored switch powers", aggregateCadence)
	ethernetPoweredName  = ethernetPowered.Subject("powered", "name of the device on the powered port, or the switch and port name where no device is known")
	ethernetPoweredPower = ethernetPowered.Float("power_w", "W", "power the device draws from its switch port")
)

type ethernetSample struct {
	devices []deviceReading
	powered []ethernetPoweredReading
}

type ethernetPoweredReading struct {
	name  string
	power float64
}

type ethernetPlugin struct {
	probe  func(ctx context.Context) ([]remote.GatewayDevice, []remote.GatewayClient, error)
	state  *StateTracker
	deltas *deltaTracker
}

func newEthernetPlugin() *ethernetPlugin {
	return &ethernetPlugin{probe: probeEthernet, state: NewStateTracker(StateOn), deltas: newDeltaTracker()}
}

func (p *ethernetPlugin) Name() string { return "ethernet" }

func (p *ethernetPlugin) Mode() Mode { return ModeSnapshot }

func (p *ethernetPlugin) Poll(ctx context.Context) (Sample, error) {
	devices, clients, err := p.probe(ctx)
	if err != nil {
		return Sample{}, err
	}
	sample := ethernetSample{
		devices: readDevices(devices, ethernetDevices, p.deltas, time.Now()),
		powered: readEthernet(devices, clients, ethernetDevices),
	}
	scribe.LogDebug("ethernet", "polled devices [%d] monitored [%d] powered [%d]", len(devices), len(sample.devices), len(sample.powered))
	return Sample{Readings: sample}, nil
}

func (p *ethernetPlugin) Aggregate(samples []Sample) (Aggregate, error) {
	return diagnoseEthernet(samples), nil
}

func (p *ethernetPlugin) Command(context.Context, State) error {
	return nil
}

func (p *ethernetPlugin) State() *StateTracker { return p.state }

func probeEthernet(ctx context.Context) ([]remote.GatewayDevice, []remote.GatewayClient, error) {
	devices, clients, err := sharedGateway.fetch(ctx)
	if err != nil {
		return nil, nil, err
	}
	scribe.LogDebug("ethernet", "probed devices [%d] clients [%d]", len(devices), len(clients))
	return devices, clients, nil
}

func readEthernet(devices []remote.GatewayDevice, clients []remote.GatewayClient, switches []string) []ethernetPoweredReading {
	port := func(device string, index int) string { return device + "/" + strconv.Itoa(index) }
	byName := make(map[string]remote.GatewayDevice, len(devices))
	byMac := make(map[string]string, len(devices))
	for _, device := range devices {
		byName[device.Name] = device
		byMac[device.Mac] = device.Name
	}
	uplinked := map[string][]string{}
	for _, device := range devices {
		if device.Uplink.UplinkDeviceName != "" {
			key := port(device.Uplink.UplinkDeviceName, device.Uplink.UplinkRemotePort)
			uplinked[key] = append(uplinked[key], device.Name)
		}
	}
	attached := map[string][]string{}
	for _, client := range clients {
		device, known := byMac[client.SwMac]
		label := client.Name
		if label == "" {
			label, _, _ = strings.Cut(client.Hostname, ".")
		}
		if known && client.SwPort > 0 && label != "" {
			key := port(device, client.SwPort)
			attached[key] = append(attached[key], label)
		}
	}
	var readings []ethernetPoweredReading
	var fallbacks []string
	for _, name := range switches {
		for _, powered := range byName[name].PortTable {
			watts, err := strconv.ParseFloat(powered.PoePower, 64)
			if err != nil || watts <= 0 {
				continue
			}
			fallback := name + "/" + powered.Name
			label := fallback
			if names := uplinked[port(name, powered.PortIdx)]; len(names) > 0 {
				label = slices.Min(names)
			} else if names := attached[port(name, powered.PortIdx)]; len(names) > 0 {
				label = slices.Min(names)
			}
			readings = append(readings, ethernetPoweredReading{name: label, power: watts})
			fallbacks = append(fallbacks, fallback)
		}
	}
	counts := map[string]int{}
	for _, reading := range readings {
		counts[reading.name]++
	}
	for index := range readings {
		if counts[readings[index].name] > 1 {
			readings[index].name = fallbacks[index]
		}
	}
	return readings
}

func diagnoseEthernet(samples []Sample) Aggregate {
	sample := latestReading[ethernetSample](samples)
	result := diagnoseDevices(sample.devices, ethernetDevice)
	result.Points = append(result.Points, reportEthernet(sample.powered)...)
	return result
}

func reportEthernet(readings []ethernetPoweredReading) []schema.Point {
	points := make([]schema.Point, 0, len(readings))
	for _, reading := range readings {
		points = append(points, ethernetPowered.Point(
			ethernetPoweredName.Of(reading.name),
			ethernetPoweredPower.Of(round(reading.power, 2))))
	}
	return points
}

func init() {
	register(newEthernetPlugin())
}
