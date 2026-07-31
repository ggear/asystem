package plugins

import (
	"context"
	"fmt"
	"math"
	"strconv"

	"networks/internal/config"
	"networks/internal/engine"
	"networks/internal/plugin"
	"networks/internal/scribe"
)

const (
	switchType    = "usw"
	expectedSpeed = 1000
)

type ethernetPlugin struct {
	probe  func(ctx context.Context) ([]engine.RouterDevice, error)
	state  *plugin.StateTracker
	deltas *plugin.DeltaTracker
}

func newEthernetPlugin() *ethernetPlugin {
	return &ethernetPlugin{probe: probeEthernet, state: plugin.NewStateTracker(plugin.StateOn), deltas: plugin.NewDeltaTracker()}
}

func (p *ethernetPlugin) Name() string { return "ethernet" }

func (p *ethernetPlugin) Mode() plugin.Mode { return plugin.ModeSnapshot }

func (p *ethernetPlugin) Poll(ctx context.Context) (plugin.Sample, error) {
	devices, err := p.probe(ctx)
	if err != nil {
		return plugin.Sample{}, err
	}
	var points []plugin.Point
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
			tags := []plugin.Tag{{Key: "scope", Value: "port"}, {Key: "switch", Value: device.Name}, {Key: "port", Value: strconv.Itoa(port.PortIdx)}}
			points = append(points, plugin.NewPoint(tags,
				plugin.Bool("up", port.Up),
				plugin.Int("speed", int64(port.Speed)),
				plugin.Bool("full_duplex", port.FullDuplex),
				plugin.Int("errors", errors)))
		}
	}
	scribe.Debugf("ethernet", "polled devices [%d] ports [%d]", len(devices), len(points))
	return plugin.Sample{Points: points}, nil
}

func (p *ethernetPlugin) Aggregate(samples []plugin.Sample) (plugin.Aggregate, error) {
	return diagnoseEthernet(samples), nil
}

func (p *ethernetPlugin) Command(ctx context.Context, newState plugin.State) error {
	return nil
}

func (p *ethernetPlugin) State() *plugin.StateTracker { return p.state }

func probeEthernet(ctx context.Context) ([]engine.RouterDevice, error) {
	cfg := config.Load()
	client, err := engine.NewRouterClient(cfg.UnifiURL(), cfg.UnifiSite(), cfg.UnifiUser(), cfg.UnifiToken())
	if err != nil {
		return nil, err
	}
	devices, err := client.Devices(ctx)
	if err != nil {
		return nil, err
	}
	scribe.Debugf("ethernet", "probed devices [%d]", len(devices))
	return devices, nil
}

func diagnoseEthernet(samples []plugin.Sample) plugin.Aggregate {
	points := plugin.LatestPoints(samples)
	total := 0
	up := 0
	degraded := 0
	errored := 0
	for _, point := range points {
		total++
		isUp, _ := point.Bool("up")
		if !isUp {
			continue
		}
		up++
		speed, _ := point.Float("speed")
		fullDuplex, _ := point.Bool("full_duplex")
		if (speed > 0 && speed < expectedSpeed) || !fullDuplex {
			degraded++
		}
		if errs, ok := point.Float("errors"); ok && errs > 0 {
			errored++
		}
	}
	upRatio := 0.0
	if total > 0 {
		upRatio = float64(up) / float64(total)
	}
	result := plugin.Aggregate{}
	switch {
	case total == 0:
		result = plugin.Diagnose(plugin.StatusDead, 0, "SWITCH_UNREACHABLE", "switch unreachable or no monitored ports reporting")
	case up == 0:
		result = plugin.Diagnose(plugin.StatusDead, 0, "PORT_DOWN", "all monitored ports down across window")
	case upRatio == 1 && degraded == 0 && errored == 0:
		result = plugin.Diagnose(plugin.StatusFit, 100, "UP", "all monitored ports up at expected speed")
	default:
		score := plugin.Clamp(int(math.Round(upRatio*100)) - degraded*10 - errored*10)
		switch {
		case up < total:
			result = plugin.Diagnose(plugin.StatusSick, score, "PORT_DOWN", fmt.Sprintf("%d/%d monitored ports up", up, total))
		case degraded > 0:
			result = plugin.Diagnose(plugin.StatusSick, score, "SPEED_DEGRADED", fmt.Sprintf("%d ports below expected speed or half-duplex", degraded))
		default:
			result = plugin.Diagnose(plugin.StatusSick, score, "LINK_ERRORS", fmt.Sprintf("%d ports reporting errors", errored))
		}
	}
	result.Points = reportEthernet(result.Score, up, total, degraded, errored, points)
	return result
}

func reportEthernet(score, up, total, degraded, errored int, portPoints []plugin.Point) []plugin.Point {
	summary := plugin.NewPoint([]plugin.Tag{{Key: "scope", Value: "summary"}},
		plugin.Int("score", int64(score)),
		plugin.Int("ports_up", int64(up)),
		plugin.Int("ports_total", int64(total)),
		plugin.Int("degraded_count", int64(degraded)),
		plugin.Int("error_count", int64(errored)))
	return plugin.PrependSummaryPoints(summary, portPoints)
}

func init() {
	plugin.Register(newEthernetPlugin())
}
