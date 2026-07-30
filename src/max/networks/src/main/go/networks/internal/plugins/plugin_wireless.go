package plugins

import (
	"context"
	"fmt"
	"log/slog"
	"math"

	"networks/internal/config"
	"networks/internal/engine"
	"networks/internal/plugin"
)

const (
	apType           = "uap"
	experienceFitMin = 80.0
)

type wirelessPlugin struct {
	probe func(ctx context.Context) ([]engine.RouterDevice, error)
	state *plugin.StateTracker
}

func newWirelessPlugin() *wirelessPlugin {
	return &wirelessPlugin{probe: probeWireless, state: plugin.NewStateTracker(plugin.StateOn)}
}

func (p *wirelessPlugin) Name() string { return "wireless" }

func (p *wirelessPlugin) Mode() plugin.Mode { return plugin.ModeSnapshot }

func (p *wirelessPlugin) Poll(ctx context.Context) (plugin.Sample, error) {
	devices, err := p.probe(ctx)
	if err != nil {
		return plugin.Sample{}, err
	}
	points := make([]plugin.Point, 0, len(devices))
	for _, device := range devices {
		if device.Type != apType {
			continue
		}
		tags := []plugin.Tag{{Key: "scope", Value: "ap"}, {Key: "ap", Value: device.Name}}
		points = append(points, plugin.NewPoint(tags, plugin.Bool("up", device.State == 1), plugin.Int("experience", int64(device.Satisfaction)), plugin.Int("num_clients", int64(device.NumSta))))
	}
	return plugin.Sample{Points: points}, nil
}

func (p *wirelessPlugin) Aggregate(samples []plugin.Sample) (plugin.Aggregate, error) {
	return diagnoseWireless(samples), nil
}

func (p *wirelessPlugin) Command(ctx context.Context, newState plugin.State) error {
	return nil
}

func (p *wirelessPlugin) State() *plugin.StateTracker { return p.state }

func probeWireless(ctx context.Context) ([]engine.RouterDevice, error) {
	cfg := config.Load()
	client, err := engine.NewRouterClient(cfg.UnifiURL(), cfg.UnifiSite(), cfg.UnifiUser(), cfg.UnifiPassword())
	if err != nil {
		return nil, err
	}
	devices, err := client.Devices(ctx)
	if err != nil {
		return nil, err
	}
	slog.Debug("probe", "plugin", "wireless", "devices", len(devices))
	return devices, nil
}

func diagnoseWireless(samples []plugin.Sample) plugin.Aggregate {
	points := plugin.LatestPoints(samples)
	total := 0
	up := 0
	experienceSum := 0.0
	experienceCount := 0
	for _, point := range points {
		total++
		isUp, _ := point.Bool("up")
		if isUp {
			up++
			if experience, ok := point.Float("experience"); ok {
				experienceSum += experience
				experienceCount++
			}
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
	result := plugin.Aggregate{}
	switch {
	case total == 0:
		result = plugin.Diagnose(plugin.StatusDead, 0, "CONTROLLER_UNREACHABLE", "controller unreachable or no access points reporting")
	case up == 0:
		result = plugin.Diagnose(plugin.StatusDead, 0, "AP_DOWN", "all access points down across window")
	case upRatio == 1 && meanExperience >= experienceFitMin:
		result = plugin.Diagnose(plugin.StatusFit, score, "UP", "all access points up with good client experience")
	case up < total:
		result = plugin.Diagnose(plugin.StatusSick, score, "AP_DOWN", fmt.Sprintf("%d/%d access points up", up, total))
	default:
		result = plugin.Diagnose(plugin.StatusSick, score, "POOR_CLIENTS", fmt.Sprintf("mean client experience %.0f%%", meanExperience))
	}
	result.Points = reportWireless(result.Score, up, total, meanExperience, points)
	return result
}

func reportWireless(score, up, total int, meanExperience float64, apPoints []plugin.Point) []plugin.Point {
	summary := plugin.NewPoint([]plugin.Tag{{Key: "scope", Value: "summary"}},
		plugin.Int("score", int64(score)),
		plugin.Int("aps_up", int64(up)),
		plugin.Int("aps_total", int64(total)),
		plugin.Float("mean_experience", plugin.Round(meanExperience, 1)))
	return plugin.PrependSummaryPoints(summary, apPoints)
}

func init() {
	plugin.Register(newWirelessPlugin())
}
