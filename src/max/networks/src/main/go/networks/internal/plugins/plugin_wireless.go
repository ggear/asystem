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
	fetch func(ctx context.Context) ([]engine.RouterDevice, []engine.RouterStation, error)
}

func newWirelessPlugin() *wirelessPlugin {
	return &wirelessPlugin{fetch: fetchWirelessLive}
}

func (p *wirelessPlugin) Name() string { return "wireless" }

func (p *wirelessPlugin) PollPhase() bool { return false }

func (p *wirelessPlugin) Poll(ctx context.Context) (plugin.Message, error) {
	devices, _, err := p.fetch(ctx)
	if err != nil {
		return plugin.Message{}, err
	}
	points := make([]plugin.Point, 0, len(devices))
	for _, device := range devices {
		if device.Type != apType {
			continue
		}
		tags := []plugin.Tag{{Key: "scope", Value: "ap"}, {Key: "ap", Value: device.Name}}
		points = append(points, plugin.NewPoint(tags, plugin.Bool("up", device.State == 1), plugin.Int("experience", int64(device.Satisfaction)), plugin.Int("num_clients", int64(device.NumSta))))
	}
	return plugin.Message{Points: points}, nil
}

func (p *wirelessPlugin) Aggregate(samples []plugin.Message) (plugin.Message, error) {
	return decideWireless(samples), nil
}

func fetchWirelessLive(ctx context.Context) ([]engine.RouterDevice, []engine.RouterStation, error) {
	cfg := config.Load()
	client, err := engine.NewRouterClient(cfg.UnifiURL(), cfg.UnifiSite(), cfg.UnifiUser(), cfg.UnifiPassword())
	if err != nil {
		return nil, nil, err
	}
	devices, err := client.Devices(ctx)
	if err != nil {
		return nil, nil, err
	}
	stations, _ := client.Stations(ctx)
	slog.Debug("fetch", "plugin", "wireless", "devices", len(devices), "stations", len(stations))
	return devices, stations, nil
}

func decideWireless(samples []plugin.Message) plugin.Message {
	points := plugin.LatestPoints(samples)
	total := 0
	up := 0
	experienceSum := 0.0
	experienceCount := 0
	for _, point := range points {
		total++
		isUp := plugin.BoolField(point, "up")
		if isUp {
			up++
			if experience, ok := plugin.FloatField(point, "experience"); ok {
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
	result := plugin.Message{}
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
	result.Points = buildWirelessPoints(result.Score, up, total, meanExperience, points)
	return result
}

func buildWirelessPoints(score, up, total int, meanExperience float64, apPoints []plugin.Point) []plugin.Point {
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
