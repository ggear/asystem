package plugins

import (
	"context"
	"encoding/json"
	"fmt"
	"log/slog"
	"math"
	"strconv"
	"strings"
	"sync"
	"time"

	"networks/internal/config"
	"networks/internal/plugin"

	mqtt "github.com/eclipse/paho.mqtt.golang"
)

const (
	weewxSignalTopic = "weewx/weatherstation_coms_signal_quality"
	weewxStatusTopic = "supervisor/raspbpi-jen/data/service/weewx"
	weewxCollectWait = 2 * time.Second
	weewxConnectWait = 5 * time.Second
	weewxFreshWindow = time.Hour
	signalFitMin     = 50.0
)

type weewxPlugin struct {
	probe func(ctx context.Context) (quality float64, hasQuality bool, fresh bool, err error)
}

func newWeewxPlugin() *weewxPlugin {
	return &weewxPlugin{probe: probeWeewx}
}

func (p *weewxPlugin) Name() string { return "weewx" }

func (p *weewxPlugin) SampleMode() plugin.SampleMode { return plugin.Snapshot }

func (p *weewxPlugin) Poll(ctx context.Context) (plugin.Sample, error) {
	quality, hasQuality, fresh, err := p.probe(ctx)
	if err != nil {
		return plugin.Sample{}, err
	}
	signal := plugin.Null("signal_quality_pct")
	if hasQuality {
		signal = plugin.Float("signal_quality_pct", plugin.Round(quality, 1))
	}
	point := plugin.NewPoint([]plugin.Tag{{Key: "scope", Value: "weatherstation"}}, signal, plugin.Bool("fresh", fresh))
	return plugin.Sample{Points: []plugin.Point{point}}, nil
}

func (p *weewxPlugin) Aggregate(samples []plugin.Sample) (plugin.Aggregate, error) {
	return diagnoseWeewx(samples), nil
}

func probeWeewx(ctx context.Context) (float64, bool, bool, error) {
	cfg := config.Load()
	broker := cfg.Broker()
	if broker == "" {
		return 0, false, false, fmt.Errorf("broker address is empty")
	}
	opts := mqtt.NewClientOptions().
		AddBroker("tcp://" + broker).
		SetClientID(fmt.Sprintf("networks-weewx-%d", time.Now().UnixNano())).
		SetCleanSession(true).
		SetConnectTimeout(weewxConnectWait)
	if token := cfg.BrokerToken(); token != "" {
		opts.SetUsername("networks").SetPassword(token)
	}
	var mu sync.Mutex
	var signal, status []byte
	client := mqtt.NewClient(opts)
	token := client.Connect()
	if !token.WaitTimeout(weewxConnectWait) || token.Error() != nil {
		return 0, false, false, fmt.Errorf("connect failed [%s] [%w]", broker, token.Error())
	}
	defer client.Disconnect(250)
	client.Subscribe(weewxSignalTopic, 0, func(_ mqtt.Client, msg mqtt.Message) {
		mu.Lock()
		signal = append([]byte(nil), msg.Payload()...)
		mu.Unlock()
	})
	client.Subscribe(weewxStatusTopic, 0, func(_ mqtt.Client, msg mqtt.Message) {
		mu.Lock()
		status = append([]byte(nil), msg.Payload()...)
		mu.Unlock()
	})
	select {
	case <-ctx.Done():
	case <-time.After(weewxCollectWait):
	}
	mu.Lock()
	defer mu.Unlock()
	quality, hasQuality, fresh := readWeewx(signal, status, time.Now())
	slog.Debug("probe", "plugin", "weewx", "signal", hasQuality, "fresh", fresh, "quality", quality)
	return quality, hasQuality, fresh, nil
}

func readWeewx(signal, status []byte, now time.Time) (quality float64, hasQuality bool, fresh bool) {
	if trimmed := strings.TrimSpace(string(signal)); trimmed != "" {
		if value, err := strconv.ParseFloat(trimmed, 64); err == nil {
			quality = value
			hasQuality = true
		}
	}
	var parsed struct {
		Timestamp int64 `json:"timestamp"`
		Pulse     struct {
			OK bool `json:"ok"`
		} `json:"pulse"`
	}
	if err := json.Unmarshal(status, &parsed); err == nil && parsed.Pulse.OK && parsed.Timestamp != 0 {
		age := now.Sub(time.Unix(parsed.Timestamp, 0))
		fresh = age >= 0 && age <= weewxFreshWindow
	}
	return quality, hasQuality, fresh
}

func diagnoseWeewx(samples []plugin.Sample) plugin.Aggregate {
	points := plugin.LatestPoints(samples)
	fresh := false
	quality := 0.0
	hasQuality := false
	for _, point := range points {
		if value, ok := point.Bool("fresh"); ok {
			fresh = value
		}
		if value, ok := point.Float("signal_quality_pct"); ok {
			quality = value
			hasQuality = true
		}
	}
	score := plugin.Clamp(int(math.Round(quality)))
	result := plugin.Aggregate{}
	switch {
	case !fresh:
		result = plugin.Diagnose(plugin.StatusDead, 0, "STALE", "weather station not reporting or last update older than one hour")
	case !hasQuality:
		result = plugin.Diagnose(plugin.StatusDead, 0, "NO_DATA", "no retained weather station signal quality on broker")
	case quality >= signalFitMin:
		result = plugin.Diagnose(plugin.StatusFit, score, "HEALTHY", fmt.Sprintf("weather station signal quality %.0f%%", quality))
	default:
		result = plugin.Diagnose(plugin.StatusSick, score, "WEAK_SIGNAL", fmt.Sprintf("weather station signal quality %.0f%%", quality))
	}
	result.Points = reportWeewx(result.Score, points)
	return result
}

func reportWeewx(score int, stationPoints []plugin.Point) []plugin.Point {
	summary := plugin.NewPoint([]plugin.Tag{{Key: "scope", Value: "summary"}}, plugin.Int("score", int64(score)))
	return plugin.PrependSummaryPoints(summary, stationPoints)
}

func init() {
	plugin.Register(newWeewxPlugin())
}
