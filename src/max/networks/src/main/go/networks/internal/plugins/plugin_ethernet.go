package plugins

import (
	"context"
	"fmt"
	"math"
	"strconv"

	"networks/internal/config"
	"networks/internal/plugin"
	"networks/internal/remote"
	"networks/internal/schema"
	"networks/internal/scribe"
)

const (
	switchType    = "usw"
	expectedSpeed = 1000
)

var (
	ethernetPorts           = schema.Declare("ethernet/ports", "switch port health across the monitored ports", aggregateCadence)
	ethernetScore         = ethernetPorts.Int("score", "count", "diagnosis score from 0 to 100")
	ethernetOK            = ethernetPorts.Bool("ok", "every monitored port up at expected speed with no link errors")
	ethernetPortsTotal    = ethernetPorts.Int("ports_total", "count", "monitored ports")
	ethernetPortsOK       = ethernetPorts.Int("ports_ok", "count", "monitored ports with a live link")
	ethernetPortsDegraded = ethernetPorts.Int("ports_degraded", "count", "ports below expected speed or in half duplex")
	ethernetPortsErrored  = ethernetPorts.Int("ports_errored", "count", "ports reporting link errors this interval")
)

type ethernetReading struct {
	up         bool
	speed      int64
	fullDuplex bool
	errors     int64
}

type ethernetPlugin struct {
	probe   func(ctx context.Context) ([]remote.GatewayDevice, error)
	gateway *remote.Gateway
	state   *plugin.StateTracker
	deltas  *plugin.DeltaTracker
}

func newEthernetPlugin() *ethernetPlugin {
	p := &ethernetPlugin{state: plugin.NewStateTracker(plugin.StateOn), deltas: plugin.NewDeltaTracker()}
	p.probe = p.probeEthernet
	return p
}

func (p *ethernetPlugin) Name() string { return "ethernet" }

func (p *ethernetPlugin) Mode() plugin.Mode { return plugin.ModeSnapshot }

func (p *ethernetPlugin) Poll(ctx context.Context) (plugin.Sample, error) {
	devices, err := p.probe(ctx)
	if err != nil {
		return plugin.Sample{}, err
	}
	var readings []ethernetReading
	for _, device := range devices {
		if device.Type != switchType {
			continue
		}
		for _, port := range device.PortTable {
			if !port.Enable {
				continue
			}
			key := device.Name + "/" + strconv.Itoa(port.PortIdx)
			errors := p.deltas.Delta(key, port.RxErrors+port.TxErrors)
			readings = append(readings, ethernetReading{
				up: port.Up, speed: int64(port.Speed), fullDuplex: port.FullDuplex, errors: errors})
		}
	}
	scribe.LogDebug("ethernet", "polled devices [%d] ports [%d]", len(devices), len(readings))
	return plugin.Sample{Readings: readings}, nil
}

func (p *ethernetPlugin) Aggregate(samples []plugin.Sample) (plugin.Aggregate, error) {
	return diagnoseEthernet(samples), nil
}

func (p *ethernetPlugin) Command(ctx context.Context, newState plugin.State) error {
	return nil
}

func (p *ethernetPlugin) State() *plugin.StateTracker { return p.state }

func (p *ethernetPlugin) probeEthernet(ctx context.Context) ([]remote.GatewayDevice, error) {
	if p.gateway == nil {
		cfg := config.Load()
		gateway, err := remote.NewGateway(cfg.UnifiURL(), cfg.UnifiSite(), cfg.UnifiUser(), cfg.UnifiToken())
		if err != nil {
			return nil, err
		}
		p.gateway = gateway
	}
	devices, err := p.gateway.Devices(ctx)
	if err != nil {
		return nil, err
	}
	scribe.LogDebug("ethernet", "probed devices [%d]", len(devices))
	return devices, nil
}

func diagnoseEthernet(samples []plugin.Sample) plugin.Aggregate {
	readings := plugin.Latest[[]ethernetReading](samples)
	total := 0
	up := 0
	degraded := 0
	errored := 0
	for _, reading := range readings {
		total++
		if !reading.up {
			continue
		}
		up++
		if (reading.speed > 0 && reading.speed < expectedSpeed) || !reading.fullDuplex {
			degraded++
		}
		if reading.errors > 0 {
			errored++
		}
	}
	upRatio := 0.0
	if total > 0 {
		upRatio = float64(up) / float64(total)
	}
	stats := ethernetStats{up: up, total: total, degraded: degraded, errored: errored}
	result := plugin.Aggregate{}
	switch {
	case total == 0:
		result = plugin.Diagnose(plugin.StatusDead, 0, "SWITCH_UNREACHABLE: switch unreachable or no monitored ports reporting")
	case up == 0:
		result = plugin.Diagnose(plugin.StatusDead, 0, "PORT_DOWN: all monitored ports down across window")
	case upRatio == 1 && degraded == 0 && errored == 0:
		result = plugin.Diagnose(plugin.StatusFit, 100, "UP: all monitored ports up at expected speed")
	default:
		score := plugin.Clamp(int(math.Round(upRatio*100)) - degraded*10 - errored*10)
		switch {
		case up < total:
			result = plugin.Diagnose(plugin.StatusSick, score, fmt.Sprintf("PORT_DOWN: only [%d] of [%d] monitored ports up", up, total))
		case degraded > 0:
			result = plugin.Diagnose(plugin.StatusSick, score, fmt.Sprintf("SPEED_DEGRADED: [%d] ports below expected speed or in half-duplex", degraded))
		default:
			result = plugin.Diagnose(plugin.StatusSick, score, fmt.Sprintf("LINK_ERRORS: [%d] ports reporting errors", errored))
		}
	}
	stats.score = result.Score
	stats.ok = result.OK
	result.Points = reportEthernet(stats)
	return result
}

func reportEthernet(stats ethernetStats) []schema.Point {
	return []schema.Point{ethernetPorts.Point(
		ethernetOK.Of(stats.ok),
		ethernetScore.Of(int64(stats.score)),
		ethernetPortsTotal.Of(int64(stats.total)),
		ethernetPortsOK.Of(int64(stats.up)),
		ethernetPortsDegraded.Of(int64(stats.degraded)),
		ethernetPortsErrored.Of(int64(stats.errored)))}
}

type ethernetStats struct {
	ok       bool
	score    int
	up       int
	total    int
	degraded int
	errored  int
}

func init() {
	plugin.Register(newEthernetPlugin())
}
