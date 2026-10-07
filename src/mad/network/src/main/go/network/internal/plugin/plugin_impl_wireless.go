package plugin

import (
	"context"
	"time"

	"network/internal/remote"
	"network/internal/scribe"
)

var (
	wirelessDevices = []string{"uap-dar-hallway", "uap-dar-deck-north", "uap-dar-deck-south"}
	wirelessDevice  = declareDevices("wireless/accesspoint", "access point health, one row per access point", "accesspoint", "name of the access point", wirelessDevices, false)
)

type wirelessPlugin struct {
	probe  func(ctx context.Context) ([]remote.GatewayDevice, error)
	state  *StateTracker
	deltas *deltaTracker
}

func newWirelessPlugin() *wirelessPlugin {
	return &wirelessPlugin{probe: probeWireless, state: NewStateTracker(StateOn), deltas: newDeltaTracker()}
}

func (p *wirelessPlugin) Name() string { return "wireless" }

func (p *wirelessPlugin) Mode() Mode { return ModeSnapshot }

func (p *wirelessPlugin) Poll(ctx context.Context) (Sample, error) {
	devices, err := p.probe(ctx)
	if err != nil {
		return Sample{}, err
	}
	readings := readDevices(devices, wirelessDevices, p.deltas, time.Now())
	scribe.LogDebug("wireless", "polled devices [%d] monitored [%d]", len(devices), len(readings))
	return Sample{Readings: readings}, nil
}

func (p *wirelessPlugin) Aggregate(samples []Sample) (Aggregate, error) {
	return diagnoseDevices(latestReading[[]deviceReading](samples), wirelessDevice), nil
}

func (p *wirelessPlugin) Command(context.Context, State) error {
	return nil
}

func (p *wirelessPlugin) State() *StateTracker { return p.state }

func probeWireless(ctx context.Context) ([]remote.GatewayDevice, error) {
	devices, _, err := sharedGateway.fetch(ctx)
	if err != nil {
		return nil, err
	}
	scribe.LogDebug("wireless", "probed devices [%d]", len(devices))
	return devices, nil
}

func init() {
	register(newWirelessPlugin())
}
