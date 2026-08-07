package plugins

import (
	"context"
	"fmt"
	"math"

	"networks/internal/config"
	"networks/internal/plugin"
	"networks/internal/remote"
	"networks/internal/schema"
	"networks/internal/scribe"
)

const (
	apType           = "uap"
	experienceFitMin = 80.0
)

var (
	wirelessAccessPoint   = schema.Declare("wireless/accesspoint", "access point health across the wireless estate", aggregateCadence)
	wirelessOK            = wirelessAccessPoint.Bool("ok", "every access point up with good client experience")
	wirelessScore         = wirelessAccessPoint.Int("score", "", "diagnosis score from 0 to 100")
	wirelessApsTotal      = wirelessAccessPoint.Int("aps_total", "", "access points known to the controller")
	wirelessApsOK         = wirelessAccessPoint.Int("aps_ok", "", "access points reporting up")
	wirelessAvgExperience = wirelessAccessPoint.Float("avg_experience_pct", "%", "mean client experience across the access points that are up")
)

type wirelessReading struct {
	up         bool
	experience int64
	clients    int64
}

type wirelessPlugin struct {
	probe   func(ctx context.Context) ([]remote.GatewayDevice, error)
	gateway *remote.Gateway
	state   *plugin.StateTracker
}

func newWirelessPlugin() *wirelessPlugin {
	p := &wirelessPlugin{state: plugin.NewStateTracker(plugin.StateOn)}
	p.probe = p.probeWireless
	return p
}

func (p *wirelessPlugin) Name() string { return "wireless" }

func (p *wirelessPlugin) Mode() plugin.Mode { return plugin.ModeSnapshot }

func (p *wirelessPlugin) Poll(ctx context.Context) (plugin.Sample, error) {
	devices, err := p.probe(ctx)
	if err != nil {
		return plugin.Sample{}, err
	}
	readings := make([]wirelessReading, 0, len(devices))
	for _, device := range devices {
		if device.Type != apType {
			continue
		}
		readings = append(readings, wirelessReading{
			up: device.State == 1, experience: int64(device.Satisfaction), clients: int64(device.NumSta)})
	}
	scribe.LogDebug("wireless", "polled devices [%d] aps [%d]", len(devices), len(readings))
	return plugin.Sample{Readings: readings}, nil
}

func (p *wirelessPlugin) Aggregate(samples []plugin.Sample) (plugin.Aggregate, error) {
	return diagnoseWireless(samples), nil
}

func (p *wirelessPlugin) Command(ctx context.Context, newState plugin.State) error {
	return nil
}

func (p *wirelessPlugin) State() *plugin.StateTracker { return p.state }

func (p *wirelessPlugin) probeWireless(ctx context.Context) ([]remote.GatewayDevice, error) {
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
	scribe.LogDebug("wireless", "probed devices [%d]", len(devices))
	return devices, nil
}

func diagnoseWireless(samples []plugin.Sample) plugin.Aggregate {
	readings := plugin.Latest[[]wirelessReading](samples)
	total := 0
	up := 0
	experienceSum := 0.0
	experienceCount := 0
	for _, reading := range readings {
		total++
		if reading.up {
			up++
			experienceSum += float64(reading.experience)
			experienceCount++
		}
	}
	meanExperience := 0.0
	if experienceCount > 0 {
		meanExperience = experienceSum / float64(experienceCount)
	}
	upRatio := 0.0
	if total > 0 {
		upRatio = float64(up) / float64(total)
	}
	score := plugin.Clamp(int(math.Round((upRatio*100 + meanExperience) / 2)))
	stats := wirelessStats{up: up, total: total, meanExperience: meanExperience}
	result := plugin.Aggregate{}
	switch {
	case total == 0:
		result = plugin.Diagnose(plugin.StatusDead, 0, "CONTROLLER_UNREACHABLE: controller unreachable or no access points reporting")
	case up == 0:
		result = plugin.Diagnose(plugin.StatusDead, 0, "AP_DOWN: all access points down across window")
	case upRatio == 1 && meanExperience >= experienceFitMin:
		result = plugin.Diagnose(plugin.StatusFit, score, "UP: all access points up with good client experience")
	case up < total:
		result = plugin.Diagnose(plugin.StatusSick, score, fmt.Sprintf("AP_DOWN: only [%d] of [%d] access points up", up, total))
	default:
		result = plugin.Diagnose(plugin.StatusSick, score, fmt.Sprintf("POOR_CLIENTS: mean client experience [%.0f%%]", meanExperience))
	}
	stats.score = result.Score
	stats.ok = result.OK
	result.Points = reportWireless(stats)
	return result
}

func reportWireless(stats wirelessStats) []schema.Point {
	return []schema.Point{wirelessAccessPoint.Point(
		wirelessOK.Of(stats.ok),
		wirelessScore.Of(int64(stats.score)),
		wirelessApsTotal.Of(int64(stats.total)),
		wirelessApsOK.Of(int64(stats.up)),
		wirelessAvgExperience.Of(plugin.Round(stats.meanExperience, 1)))}
}

type wirelessStats struct {
	ok             bool
	score          int
	up             int
	total          int
	meanExperience float64
}

func init() {
	plugin.Register(newWirelessPlugin())
}
