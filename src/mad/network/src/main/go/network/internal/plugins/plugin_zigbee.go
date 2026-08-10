package plugins

import (
	"context"
	"encoding/json"
	"fmt"
	"math"
	"strings"
	"sync"
	"time"

	"network/internal/config"
	"network/internal/plugin"
	"network/internal/schema"
	"network/internal/scribe"

	mqtt "github.com/eclipse/paho.mqtt.golang"
)

const (
	zigbeeBaseTopic = "zigbee"
	collectDelay    = 2 * time.Second
	connectWait     = 5 * time.Second
	onlineFitRatio  = 0.95
	weakLQI         = 30
	maxLQI          = 255
)

var (
	zigbeeDevice      = schema.Declare("zigbee/device", "mesh device state reported by the coordinator, one row per paired device", aggregateCadence)
	zigbeeName        = zigbeeDevice.Subject("device", "friendly name of the paired device")
	zigbeeAvailable   = zigbeeDevice.Bool("available", "device reporting available")
	zigbeeCoordinator = zigbeeDevice.Bool("coordinator", "device is the coordinator itself")
	zigbeeLQI         = zigbeeDevice.Int("lqi", "", "link quality reported for the device")
	zigbeeWeak        = zigbeeDevice.Bool("weak", "device link quality below the weak threshold")
)

type zigbeeSample struct {
	online  bool
	devices []zigbeeReading
}

type zigbeeReading struct {
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
	probe func(ctx context.Context) (online bool, permitJoin bool, devices []zigbeeReading, err error)
	state *plugin.StateTracker
}

func newZigbeePlugin() *zigbeePlugin {
	return &zigbeePlugin{probe: probeZigbee, state: plugin.NewStateTracker(plugin.StateOn)}
}

func (p *zigbeePlugin) Name() string { return "zigbee" }

func (p *zigbeePlugin) Mode() plugin.Mode { return plugin.ModeSnapshot }

func (p *zigbeePlugin) Poll(ctx context.Context) (plugin.Sample, error) {
	online, permit, devices, err := p.probe(ctx)
	if err != nil {
		return plugin.Sample{}, err
	}
	paired := make([]zigbeeReading, 0, len(devices))
	for _, d := range devices {
		if d.isCoordinator {
			continue
		}
		paired = append(paired, d)
	}
	scribe.LogDebug("zigbee", "polled online [%v] permit_join [%v] devices [%d]", online, permit, len(paired))
	return plugin.Sample{Readings: zigbeeSample{online: online, devices: paired}}, nil
}

func (p *zigbeePlugin) Aggregate(samples []plugin.Sample) (plugin.Aggregate, error) {
	return diagnoseZigbee(samples), nil
}

func (p *zigbeePlugin) Command(ctx context.Context, newState plugin.State) error {
	return nil
}

func (p *zigbeePlugin) State() *plugin.StateTracker { return p.state }

func probeZigbee(ctx context.Context) (bool, bool, []zigbeeReading, error) {
	cfg := config.Load()
	broker := cfg.Broker()
	if broker == "" {
		return false, false, nil, fmt.Errorf("broker address is empty")
	}
	opts := mqtt.NewClientOptions().
		AddBroker("tcp://" + broker).
		SetClientID(fmt.Sprintf("network-zigbee-%d", time.Now().UnixNano())).
		SetCleanSession(true).
		SetConnectTimeout(connectWait)
	if token := cfg.BrokerToken(); token != "" {
		opts.SetUsername("network").SetPassword(token)
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
	scribe.LogDebug("zigbee", "probed topics [%d] online [%v] devices [%d]", len(messages), online, len(devices))
	return online, permit, devices, nil
}

func readZigbee(base string, messages map[string][]byte) (online bool, permitJoin bool, devices []zigbeeReading) {
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
	devices = make([]zigbeeReading, 0, len(deviceList))
	for _, d := range deviceList {
		value, hasLQI := lqi[d.FriendlyName]
		devices = append(devices, zigbeeReading{
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
	sample := plugin.Latest[zigbeeSample](samples)
	bridgeOnline := sample.online
	total := 0
	online := 0
	weak := 0
	minLQI := math.MaxInt64
	lqiSum := 0.0
	lqiCount := 0
	for _, device := range sample.devices {
		total++
		if device.available {
			online++
		}
		if device.hasLQI {
			lqi := int64(device.lqi)
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
		result = plugin.Diagnose(plugin.StatusDead, 0, "COORDINATOR_DOWN: coordinator offline or no device reports across window")
		minLQI = 0
	case onlineRatio >= onlineFitRatio && weak == 0:
		result = plugin.Diagnose(plugin.StatusFit, score, "HEALTHY: coordinator online with healthy devices")
	case onlineRatio < onlineFitRatio:
		result = plugin.Diagnose(plugin.StatusSick, score, fmt.Sprintf("DEVICES_OFFLINE: only [%d] of [%d] devices online", online, total))
	default:
		result = plugin.Diagnose(plugin.StatusSick, score, fmt.Sprintf("WEAK_LINKS: [%d] devices with weak links with LQI less than [%d]", weak, int(minLQI)))
	}
	result.Points = reportZigbee(sample.devices)
	return result
}

func reportZigbee(devices []zigbeeReading) []schema.Point {
	points := make([]schema.Point, 0, len(devices))
	for _, device := range devices {
		point := []schema.Value{
			zigbeeName.Of(device.name),
			zigbeeAvailable.Of(device.available),
			zigbeeCoordinator.Of(device.isCoordinator),
		}
		if device.hasLQI {
			point = append(point,
				zigbeeLQI.Of(int64(device.lqi)),
				zigbeeWeak.Of(int64(device.lqi) < weakLQI))
		}
		points = append(points, zigbeeDevice.Point(point...))
	}
	return points
}

func init() {
	plugin.Register(newZigbeePlugin())
}
