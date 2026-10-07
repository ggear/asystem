package plugin

import (
	"context"
	"encoding/json"
	"fmt"
	"maps"
	"math"
	"slices"
	"strings"
	"sync"
	"time"

	"network/internal/config"
	"network/internal/remote"
	"network/internal/schema"
	"network/internal/scribe"

	mqtt "github.com/eclipse/paho.mqtt.golang"
)

const (
	zigbeeBaseTopic       = "zigbee"
	zigbeePollPeriod      = 5 * time.Minute
	zigbeeCatalogueAge    = 15 * time.Minute
	zigbeeCollectWait     = 2 * time.Second
	zigbeeConnectWait     = 5 * time.Second
	zigbeeStaleAfter      = 30 * time.Minute
	zigbeeWeakLQI         = 30
	zigbeeFullLQI         = 100.0
	zigbeeRouterWeakLQI   = 10.0
	zigbeeRouterSickBelow = 35.0
	zigbeeMeshSickBelow   = 50.0
	zigbeeRouterWeight    = 0.7
)

var (
	zigbeeRouters = []string{"Ada Desk Outlet", "Deck Fans Outlet", "Edwin Desk Outlet", "Kitchen Fan Outlet"}

	zigbeeDevice    = schema.Declare("zigbee/device", "mesh device state reported by the coordinator, one row per paired device", aggregateCadence)
	zigbeeName      = zigbeeDevice.Subject("device", "friendly name of the paired device")
	zigbeeAvailable = zigbeeDevice.Bool("available", "device reporting available")
	zigbeeLQI       = zigbeeDevice.Int("lqi", "", "median link quality across the window while available")
	zigbeeWeak      = zigbeeDevice.Bool("weak", "device median link quality below the weak threshold")
	zigbeeLastSeen  = zigbeeDevice.Int("last_seen_s", "s", "age of the device's latest report")

	zigbeeExperience     = schema.Declare("zigbee/experience", "mesh experience, one row per part of the mesh", aggregateCadence).Entities("router", "mesh")
	zigbeeExperienceName = zigbeeExperience.Subject("experience", "router is the always on outlets weighted by availability, mesh is every available device")
	zigbeeExperiencePct  = zigbeeExperience.Float("experience_pct", "%", "share of full link quality across that part of the mesh")
)

type zigbeeSample struct {
	online  bool
	devices []zigbeeReading
}

type zigbeeReading struct {
	name        string
	available   bool
	lqi         int
	hasLQI      bool
	lastSeen    time.Time
	hasLastSeen bool
}

type zigbeeBridgeDevice struct {
	FriendlyName string `json:"friendly_name"`
	Type         string `json:"type"`
}

type zigbeePlugin struct {
	probe      func(ctx context.Context, topics []string) (map[string][]byte, error)
	catalogue  []zigbeeBridgeDevice
	catalogued time.Time
	state      *StateTracker
}

func newZigbeePlugin() *zigbeePlugin {
	return &zigbeePlugin{probe: probeZigbee, state: NewStateTracker(StateOn)}
}

func (p *zigbeePlugin) Name() string { return "zigbee" }

func (p *zigbeePlugin) Mode() Mode { return ModeWindowed }

func (p *zigbeePlugin) PollPeriod() time.Duration { return zigbeePollPeriod }

func (p *zigbeePlugin) Poll(ctx context.Context) (Sample, error) {
	now := time.Now()
	topics := []string{zigbeeBaseTopic + "/bridge/state"}
	for _, device := range p.catalogue {
		topics = append(topics, zigbeeBaseTopic+"/"+device.FriendlyName, zigbeeBaseTopic+"/"+device.FriendlyName+"/availability")
	}
	if len(p.catalogue) == 0 {
		topics = append(topics, zigbeeBaseTopic+"/+", zigbeeBaseTopic+"/+/availability")
	}
	if len(p.catalogue) == 0 || now.Sub(p.catalogued) >= zigbeeCatalogueAge {
		topics = append(topics, zigbeeBaseTopic+"/bridge/devices")
	}
	messages, err := p.probe(ctx, topics)
	if err != nil {
		return Sample{}, err
	}
	sample, catalogue := readZigbee(zigbeeBaseTopic, messages, p.catalogue)
	if _, refreshed := messages[zigbeeBaseTopic+"/bridge/devices"]; refreshed {
		p.catalogue, p.catalogued = catalogue, now
	}
	scribe.LogDebug("zigbee", "polled topics [%d] online [%v] devices [%d]", len(messages), sample.online, len(sample.devices))
	return Sample{Timestamp: now, Readings: sample}, nil
}

func (p *zigbeePlugin) Aggregate(samples []Sample) (Aggregate, error) {
	return diagnoseZigbee(samples), nil
}

func (p *zigbeePlugin) Command(context.Context, State) error {
	return nil
}

func (p *zigbeePlugin) State() *StateTracker { return p.state }

func probeZigbee(ctx context.Context, topics []string) (map[string][]byte, error) {
	cfg := config.Load()
	broker := cfg.Broker()
	if broker == "" {
		return nil, fmt.Errorf("broker address is empty")
	}
	opts := mqtt.NewClientOptions().
		AddBroker("tcp://" + broker).
		SetClientID(fmt.Sprintf("network-zigbee-%d", time.Now().UnixNano())).
		SetCleanSession(true).
		SetConnectTimeout(zigbeeConnectWait)
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
	if !token.WaitTimeout(zigbeeConnectWait) || token.Error() != nil {
		return nil, fmt.Errorf("connect failed [%s] [%w]", broker, token.Error())
	}
	defer client.Disconnect(250)
	filters := make(map[string]byte, len(topics))
	for _, topic := range topics {
		filters[topic] = 0
	}
	if err := remote.SubscribeGranted(client.SubscribeMultiple(filters, handler), zigbeeConnectWait); err != nil {
		return nil, fmt.Errorf("subscribe failed [%s] [%w]", strings.Join(topics, ", "), err)
	}
	select {
	case <-ctx.Done():
	case <-time.After(zigbeeCollectWait):
	}
	mu.Lock()
	defer mu.Unlock()
	scribe.LogDebug("zigbee", "probed topics [%d]", len(messages))
	return maps.Clone(messages), nil
}

func readZigbee(base string, messages map[string][]byte, catalogue []zigbeeBridgeDevice) (zigbeeSample, []zigbeeBridgeDevice) {
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
	var sample zigbeeSample
	type report struct {
		lqi         int
		hasLQI      bool
		lastSeen    time.Time
		hasLastSeen bool
	}
	reports := map[string]report{}
	availability := map[string]bool{}
	for topic, payload := range messages {
		switch {
		case topic == base+"/bridge/state":
			sample.online = decodeState(payload) == "online"
		case topic == base+"/bridge/devices":
			var refreshed []zigbeeBridgeDevice
			if err := json.Unmarshal(payload, &refreshed); err == nil {
				catalogue = refreshed
			}
		case strings.HasSuffix(topic, "/availability"):
			name := strings.TrimSuffix(strings.TrimPrefix(topic, base+"/"), "/availability")
			availability[name] = decodeState(payload) == "online"
		case strings.HasPrefix(topic, base+"/bridge/"):
		case strings.HasPrefix(topic, base+"/"):
			var parsed struct {
				LinkQuality *int            `json:"linkquality"`
				LastSeen    json.RawMessage `json:"last_seen"`
			}
			if err := json.Unmarshal(payload, &parsed); err != nil {
				continue
			}
			var r report
			if parsed.LinkQuality != nil {
				r.lqi, r.hasLQI = *parsed.LinkQuality, true
			}
			var stamp string
			var epoch int64
			if json.Unmarshal(parsed.LastSeen, &stamp) == nil {
				if seen, err := time.Parse(time.RFC3339, stamp); err == nil {
					r.lastSeen, r.hasLastSeen = seen, true
				}
			} else if json.Unmarshal(parsed.LastSeen, &epoch) == nil && epoch > 0 {
				r.lastSeen, r.hasLastSeen = time.UnixMilli(epoch), true
			}
			reports[strings.TrimPrefix(topic, base+"/")] = r
		}
	}
	for _, d := range catalogue {
		if strings.EqualFold(d.Type, "Coordinator") {
			continue
		}
		r := reports[d.FriendlyName]
		sample.devices = append(sample.devices, zigbeeReading{
			name:        d.FriendlyName,
			available:   availability[d.FriendlyName],
			lqi:         r.lqi,
			hasLQI:      r.hasLQI,
			lastSeen:    r.lastSeen,
			hasLastSeen: r.hasLastSeen,
		})
	}
	return sample, catalogue
}

func diagnoseZigbee(samples []Sample) Aggregate {
	window := allReadings[zigbeeSample](samples)
	var latest zigbeeSample
	var at time.Time
	polled := false
	for _, sample := range slices.Backward(samples) {
		if reading, ok := sample.Readings.(zigbeeSample); ok {
			latest, at, polled = reading, sample.Timestamp, true
			break
		}
	}
	medians := map[string]float64{}
	history := map[string][]float64{}
	for _, sample := range window {
		for _, device := range sample.devices {
			if device.available && device.hasLQI {
				history[device.name] = append(history[device.name], float64(device.lqi))
			}
		}
	}
	for name, values := range history {
		slices.Sort(values)
		middle := len(values) / 2
		medians[name] = values[middle]
		if len(values)%2 == 0 {
			medians[name] = (values[middle-1] + values[middle]) / 2
		}
	}
	byName := make(map[string]zigbeeReading, len(latest.devices))
	var newest time.Time
	for _, device := range latest.devices {
		byName[device.name] = device
		if device.hasLastSeen && device.lastSeen.After(newest) {
			newest = device.lastSeen
		}
	}
	var offline, weak []string
	routerSum, routerCount, alive := 0.0, 0, false
	for _, name := range zigbeeRouters {
		device, found := byName[name]
		if !found || !device.available {
			offline = append(offline, name)
			routerCount++
			continue
		}
		if !device.hasLQI || device.lqi > 0 {
			alive = true
		}
		median, known := medians[name]
		if !known {
			continue
		}
		routerSum += math.Min(median, zigbeeFullLQI)
		routerCount++
		if median < zigbeeRouterWeakLQI {
			weak = append(weak, name)
		}
	}
	router := zigbeeFullLQI
	if routerCount > 0 {
		router = routerSum / float64(routerCount)
	}
	meshSum, meshCount := 0.0, 0
	for _, device := range latest.devices {
		if median, ok := medians[device.name]; ok && device.available {
			meshSum += math.Min(median, zigbeeFullLQI)
			meshCount++
		}
	}
	mesh := 0.0
	if meshCount > 0 {
		mesh = meshSum / float64(meshCount)
	}
	score := clamp(int(math.Round(router * (zigbeeRouterWeight + (1-zigbeeRouterWeight)*mesh/100))))
	routerShown, meshShown := math.Round(router), math.Round(mesh)
	result := Aggregate{}
	switch {
	case !polled:
		result = Diagnose(StatusDead, 0, "NO_DATA: no zigbee poll succeeded across window")
	case !latest.online || len(latest.devices) == 0:
		result = Diagnose(StatusDead, 0, "COORDINATOR_DOWN: coordinator offline or no device reports")
	case !newest.IsZero() && at.Sub(newest) > zigbeeStaleAfter:
		result = Diagnose(StatusDead, 0, fmt.Sprintf("BRIDGE_STALE: newest device report is %s old", at.Sub(newest).Round(time.Minute)))
	case !alive:
		result = Diagnose(StatusDead, 0, fmt.Sprintf("ROUTERS_DOWN: none of %d routers available with any link quality", len(zigbeeRouters)))
	case len(offline) > 0:
		result = Diagnose(StatusSick, score, fmt.Sprintf("ROUTERS_OFFLINE: only %d of %d routers available (%s offline)", len(zigbeeRouters)-len(offline), len(zigbeeRouters), strings.Join(offline, ", ")))
	case len(weak) > 0:
		result = Diagnose(StatusSick, score, fmt.Sprintf("WEAK_ROUTERS: routers with median link quality below %.0f (%s)", zigbeeRouterWeakLQI, strings.Join(weak, ", ")))
	case routerShown < zigbeeRouterSickBelow:
		result = Diagnose(StatusSick, score, fmt.Sprintf("WEAK_ROUTERS: router score %.0f%% below %.0f%%", routerShown, zigbeeRouterSickBelow))
	case meshShown < zigbeeMeshSickBelow:
		result = Diagnose(StatusSick, score, fmt.Sprintf("WEAK_MESH: mesh score %.0f%% below %.0f%% across %d available devices", meshShown, zigbeeMeshSickBelow, meshCount))
	default:
		result = Diagnose(StatusFit, score, fmt.Sprintf("HEALTHY: router score %.0f%% mesh score %.0f%% across %d available devices", routerShown, meshShown, meshCount))
	}
	result.Points = reportZigbee(latest, at, medians, router, mesh)
	return result
}

func reportZigbee(latest zigbeeSample, at time.Time, medians map[string]float64, router, mesh float64) []schema.Point {
	points := make([]schema.Point, 0, len(latest.devices)+2)
	for _, device := range latest.devices {
		point := []schema.Value{
			zigbeeName.Of(device.name),
			zigbeeAvailable.Of(device.available),
		}
		if median, ok := medians[device.name]; ok && device.available {
			point = append(point,
				zigbeeLQI.Of(int64(math.Round(median))),
				zigbeeWeak.Of(median < zigbeeWeakLQI))
		}
		if device.hasLastSeen {
			point = append(point, zigbeeLastSeen.Of(int64(math.Max(0, at.Sub(device.lastSeen).Seconds()))))
		}
		points = append(points, zigbeeDevice.Point(point...))
	}
	if len(latest.devices) > 0 {
		points = append(points,
			zigbeeExperience.Point(zigbeeExperienceName.Of("router"), zigbeeExperiencePct.Of(round(router, 0))),
			zigbeeExperience.Point(zigbeeExperienceName.Of("mesh"), zigbeeExperiencePct.Of(round(mesh, 0))))
	}
	return points
}

func init() {
	register(newZigbeePlugin())
}
