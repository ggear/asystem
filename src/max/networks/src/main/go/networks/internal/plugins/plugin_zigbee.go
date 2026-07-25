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
	collectDelay   = 2 * time.Second
	connectWait    = 5 * time.Second
	onlineFitRatio = 0.95
	weakLQI        = 30
	maxLQI         = 255
)

type zigbeeDevice struct {
	name          string
	isCoordinator bool
	lqi           int
	hasLQI        bool
	available     bool
}

type zigbeePlugin struct {
	fetch func(ctx context.Context) (online bool, permitJoin bool, devices []zigbeeDevice, err error)
}

func newZigbeePlugin() *zigbeePlugin {
	return &zigbeePlugin{fetch: fetchZigbeeLive}
}

func (p *zigbeePlugin) Name() string { return "zigbee" }

func (p *zigbeePlugin) PollPhase() bool { return false }

func (p *zigbeePlugin) Poll(ctx context.Context) (plugin.Message, error) {
	online, permit, devices, err := p.fetch(ctx)
	if err != nil {
		return plugin.Message{}, err
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
	return plugin.Message{Points: points}, nil
}

func (p *zigbeePlugin) Aggregate(samples []plugin.Message) (plugin.Message, error) {
	return decideZigbee(samples), nil
}

func fetchZigbeeLive(ctx context.Context) (bool, bool, []zigbeeDevice, error) {
	cfg := config.Load()
	broker := cfg.Broker()
	if broker == "" {
		return false, false, nil, fmt.Errorf("broker address is empty")
	}
	base := cfg.ZigbeeTopic()
	opts := mqtt.NewClientOptions().
		AddBroker("tcp://" + broker).
		SetClientID(fmt.Sprintf("networks-zigbee-%d", time.Now().UnixNano())).
		SetCleanSession(true).
		SetConnectTimeout(connectWait)
	if token := cfg.BrokerToken(); token != "" {
		opts.SetUsername("networks").SetPassword(token)
	}
	var mu sync.Mutex
	stateRaw := ""
	permitJoin := false
	var deviceList []bridgeDevice
	lqi := map[string]int{}
	availability := map[string]bool{}
	client := mqtt.NewClient(opts)
	handler := func(_ mqtt.Client, msg mqtt.Message) {
		mu.Lock()
		defer mu.Unlock()
		topic := msg.Topic()
		payload := msg.Payload()
		switch {
		case topic == base+"/bridge/state":
			stateRaw = parseState(payload)
		case topic == base+"/bridge/info":
			permitJoin = parsePermitJoin(payload)
		case topic == base+"/bridge/devices":
			deviceList = parseDevices(payload)
		case strings.HasSuffix(topic, "/availability"):
			name := strings.TrimSuffix(strings.TrimPrefix(topic, base+"/"), "/availability")
			availability[name] = parseState(payload) == "online"
		case strings.HasPrefix(topic, base+"/bridge/"):
		case strings.HasPrefix(topic, base+"/"):
			name := strings.TrimPrefix(topic, base+"/")
			if value, ok := parseLinkQuality(payload); ok {
				lqi[name] = value
			}
		}
	}
	token := client.Connect()
	if !token.WaitTimeout(connectWait) || token.Error() != nil {
		return false, false, nil, fmt.Errorf("connect failed [%s] [%w]", broker, token.Error())
	}
	defer client.Disconnect(250)
	client.Subscribe(base+"/#", 0, handler)
	select {
	case <-ctx.Done():
	case <-time.After(collectDelay):
	}
	mu.Lock()
	defer mu.Unlock()
	devices := make([]zigbeeDevice, 0, len(deviceList))
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
	slog.Debug("fetch", "plugin", "zigbee", "online", stateRaw == "online", "devices", len(devices))
	return stateRaw == "online", permitJoin, devices, nil
}

type bridgeDevice struct {
	FriendlyName string `json:"friendly_name"`
	Type         string `json:"type"`
}

func parseState(payload []byte) string {
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

func parsePermitJoin(payload []byte) bool {
	var parsed struct {
		PermitJoin bool `json:"permit_join"`
	}
	json.Unmarshal(payload, &parsed)
	return parsed.PermitJoin
}

func parseDevices(payload []byte) []bridgeDevice {
	var devices []bridgeDevice
	json.Unmarshal(payload, &devices)
	return devices
}

func parseLinkQuality(payload []byte) (int, bool) {
	var parsed struct {
		LinkQuality *int `json:"linkquality"`
	}
	if err := json.Unmarshal(payload, &parsed); err != nil || parsed.LinkQuality == nil {
		return 0, false
	}
	return *parsed.LinkQuality, true
}

func decideZigbee(samples []plugin.Message) plugin.Message {
	points := plugin.LatestPoints(samples)
	bridgeOnline := false
	total := 0
	online := 0
	weak := 0
	minLQI := math.MaxInt64
	lqiSum := 0.0
	lqiCount := 0
	for _, point := range points {
		if plugin.TagValue(point, "scope") == "bridge" {
			bridgeOnline = plugin.BoolField(point, "online")
			continue
		}
		if plugin.TagValue(point, "scope") != "device" {
			continue
		}
		total++
		if plugin.BoolField(point, "available") {
			online++
		}
		if lqi, ok := plugin.IntField(point, "lqi"); ok {
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
	result := plugin.Message{}
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
	result.Points = buildZigbeePoints(result.Score, online, total, weak, int(minLQI), points)
	return result
}

func buildZigbeePoints(score, online, total, weak, minLQI int, devicePoints []plugin.Point) []plugin.Point {
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
