package plugins

import (
	"context"
	"encoding/json"
	"fmt"
	"log/slog"
	"math"
	"strings"
	"sync"
	"time"

	"networks/internal/config"
	"networks/internal/plugin"

	mqtt "github.com/eclipse/paho.mqtt.golang"
)

const (
	zigbeeBaseTopic = "zigbee2mqtt"
	collectDelay    = 2 * time.Second
	connectWait     = 5 * time.Second
	onlineFitRatio  = 0.95
	weakLQI         = 30
	maxLQI          = 255
)

type zigbeeDevice struct {
	name          string
	isCoordinator bool
	lqi           int
	hasLQI        bool
	available     bool
}

type bridgeDevice struct {
	FriendlyName string `json:"friendly_name"`
	Type         string `json:"type"`
}

type zigbeePlugin struct {
	probe func(ctx context.Context) (online bool, permitJoin bool, devices []zigbeeDevice, err error)
}

func newZigbeePlugin() *zigbeePlugin {
	return &zigbeePlugin{probe: probeZigbee}
}

func (p *zigbeePlugin) Name() string { return "zigbee" }

func (p *zigbeePlugin) SampleMode() plugin.SampleMode { return plugin.Snapshot }

func (p *zigbeePlugin) Poll(ctx context.Context) (plugin.Sample, error) {
	online, permit, devices, err := p.probe(ctx)
	if err != nil {
		return plugin.Sample{}, err
	}
	points := []plugin.Point{plugin.NewPoint([]plugin.Tag{{Key: "scope", Value: "bridge"}}, plugin.Bool("online", online), plugin.Bool("permit_join", permit))}
	for _, d := range devices {
		if d.isCoordinator {
			continue
		}
		tags := []plugin.Tag{{Key: "scope", Value: "device"}, {Key: "device", Value: d.name}}
		lqiField := plugin.Null("lqi")
		if d.hasLQI {
			lqiField = plugin.Int("lqi", int64(d.lqi))
		}
		points = append(points, plugin.NewPoint(tags, lqiField, plugin.Bool("available", d.available)))
	}
	return plugin.Sample{Points: points}, nil
}

func (p *zigbeePlugin) Aggregate(samples []plugin.Sample) (plugin.Aggregate, error) {
	return diagnoseZigbee(samples), nil
}

func probeZigbee(ctx context.Context) (bool, bool, []zigbeeDevice, error) {
	cfg := config.Load()
	broker := cfg.Broker()
	if broker == "" {
		return false, false, nil, fmt.Errorf("broker address is empty")
	}
	opts := mqtt.NewClientOptions().
		AddBroker("tcp://" + broker).
		SetClientID(fmt.Sprintf("networks-zigbee-%d", time.Now().UnixNano())).
		SetCleanSession(true).
		SetConnectTimeout(connectWait)
	if token := cfg.BrokerToken(); token != "" {
		opts.SetUsername("networks").SetPassword(token)
	}
	var mu sync.Mutex
	messages := map[string][]byte{}
	client := mqtt.NewClient(opts)
	handler := func(_ mqtt.Client, msg mqtt.Message) {
		mu.Lock()
		messages[msg.Topic()] = append([]byte(nil), msg.Payload()...)
		mu.Unlock()
	}
	token := client.Connect()
	if !token.WaitTimeout(connectWait) || token.Error() != nil {
		return false, false, nil, fmt.Errorf("connect failed [%s] [%w]", broker, token.Error())
	}
	defer client.Disconnect(250)
	client.Subscribe(zigbeeBaseTopic+"/#", 0, handler)
	select {
	case <-ctx.Done():
	case <-time.After(collectDelay):
	}
	mu.Lock()
	defer mu.Unlock()
	online, permit, devices := readZigbee(zigbeeBaseTopic, messages)
	slog.Debug("probe", "plugin", "zigbee", "online", online, "devices", len(devices))
	return online, permit, devices, nil
}

func readZigbee(base string, messages map[string][]byte) (online bool, permitJoin bool, devices []zigbeeDevice) {
	decodeState := func(payload []byte) string {
		trimmed := strings.TrimSpace(string(payload))
		if strings.HasPrefix(trimmed, "{") {
			var parsed struct {
				State string `json:"state"`
			}
			if err := json.Unmarshal(payload, &parsed); err == nil {
				return parsed.State
			}
		}
		return trimmed
	}
	stateRaw := ""
	var deviceList []bridgeDevice
	lqi := map[string]int{}
	availability := map[string]bool{}
	for topic, payload := range messages {
		switch {
		case topic == base+"/bridge/state":
			stateRaw = decodeState(payload)
		case topic == base+"/bridge/info":
			var info struct {
				PermitJoin bool `json:"permit_join"`
			}
			json.Unmarshal(payload, &info)
			permitJoin = info.PermitJoin
		case topic == base+"/bridge/devices":
			json.Unmarshal(payload, &deviceList)
		case strings.HasSuffix(topic, "/availability"):
			name := strings.TrimSuffix(strings.TrimPrefix(topic, base+"/"), "/availability")
			availability[name] = decodeState(payload) == "online"
		case strings.HasPrefix(topic, base+"/bridge/"):
		case strings.HasPrefix(topic, base+"/"):
			name := strings.TrimPrefix(topic, base+"/")
			var reading struct {
				LinkQuality *int `json:"linkquality"`
			}
			if err := json.Unmarshal(payload, &reading); err == nil && reading.LinkQuality != nil {
				lqi[name] = *reading.LinkQuality
			}
		}
	}
	devices = make([]zigbeeDevice, 0, len(deviceList))
	for _, d := range deviceList {
		value, hasLQI := lqi[d.FriendlyName]
		devices = append(devices, zigbeeDevice{
			name:          d.FriendlyName,
			isCoordinator: strings.EqualFold(d.Type, "Coordinator"),
			lqi:           value,
			hasLQI:        hasLQI,
			available:     availability[d.FriendlyName],
		})
	}
	return stateRaw == "online", permitJoin, devices
}

func diagnoseZigbee(samples []plugin.Sample) plugin.Aggregate {
	points := plugin.LatestPoints(samples)
	bridgeOnline := false
	total := 0
	online := 0
	weak := 0
	minLQI := math.MaxInt64
	lqiSum := 0.0
	lqiCount := 0
	for _, point := range points {
		scope, _ := point.Tag("scope")
		if scope == "bridge" {
			bridgeOnline, _ = point.Bool("online")
			continue
		}
		if scope != "device" {
			continue
		}
		total++
		if available, _ := point.Bool("available"); available {
			online++
		}
		if lqi, ok := point.Int("lqi"); ok {
			lqiSum += float64(lqi)
			lqiCount++
			if int(lqi) < minLQI {
				minLQI = int(lqi)
			}
			if lqi < weakLQI {
				weak++
			}
		}
	}
	if lqiCount == 0 {
		minLQI = 0
	}
	onlineRatio := 0.0
	if total > 0 {
		onlineRatio = float64(online) / float64(total)
	}
	lqiPercent := 0.0
	if lqiCount > 0 {
		lqiPercent = (lqiSum / float64(lqiCount)) / maxLQI * 100
	}
	score := plugin.Clamp(int(math.Round(0.7*onlineRatio*100 + 0.3*lqiPercent)))
	result := plugin.Aggregate{}
	switch {
	case !bridgeOnline || total == 0:
		result = plugin.Diagnose(plugin.StatusDead, 0, "COORDINATOR_DOWN", "coordinator offline or no device reports across window")
		minLQI = 0
	case onlineRatio >= onlineFitRatio && weak == 0:
		result = plugin.Diagnose(plugin.StatusFit, score, "HEALTHY", "coordinator online with healthy devices")
	case onlineRatio < onlineFitRatio:
		result = plugin.Diagnose(plugin.StatusSick, score, "DEVICES_OFFLINE", fmt.Sprintf("%d/%d devices online", online, total))
	default:
		result = plugin.Diagnose(plugin.StatusSick, score, "WEAK_LINKS", fmt.Sprintf("%d devices with weak links (min lqi %d)", weak, int(minLQI)))
	}
	result.Points = reportZigbee(result.Score, online, total, weak, int(minLQI), points)
	return result
}

func reportZigbee(score, online, total, weak, minLQI int, devicePoints []plugin.Point) []plugin.Point {
	summary := plugin.NewPoint([]plugin.Tag{{Key: "scope", Value: "summary"}},
		plugin.Int("score", int64(score)),
		plugin.Int("devices_online", int64(online)),
		plugin.Int("devices_total", int64(total)),
		plugin.Int("weak_link_count", int64(weak)),
		plugin.Int("min_lqi", int64(minLQI)))
	return plugin.PrependSummaryPoints(summary, devicePoints)
}

func init() {
	plugin.Register(newZigbeePlugin())
}
