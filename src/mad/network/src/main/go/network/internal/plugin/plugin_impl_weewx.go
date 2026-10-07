package plugin

import (
	"context"
	"encoding/json"
	"fmt"
	"math"
	"strconv"
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
	weewxSignalTopic = "weewx/weatherstation_coms_signal_quality"
	weewxCollectWait = 2 * time.Second
	weewxConnectWait = 5 * time.Second
	weewxFreshWindow = time.Hour
	weewxFitMin      = 50.0
	weewxConsoleName = "weatherstation"
)

var (
	weewxConsole = schema.Declare("weewx/console", "weather station console link health, one row per console", aggregateCadence).Entities(weewxConsoleName)
	weewxName    = weewxConsole.Subject("console", "name of the weather station console")
	weewxFresh   = weewxConsole.Bool("fresh", "console reported a pulse inside the freshness window")
	weewxQuality = weewxConsole.Float("quality_pct", "%", "console coms signal quality")
)

type weewxReading struct {
	quality    float64
	hasQuality bool
	fresh      bool
}

type weewxPlugin struct {
	probe func(ctx context.Context) (quality float64, hasQuality bool, fresh bool, err error)
	state *StateTracker
}

func newWeewxPlugin() *weewxPlugin {
	return &weewxPlugin{probe: probeWeewx, state: NewStateTracker(StateOn)}
}

func (p *weewxPlugin) Name() string { return "weewx" }

func (p *weewxPlugin) Mode() Mode { return ModeSnapshot }

func (p *weewxPlugin) Poll(ctx context.Context) (Sample, error) {
	quality, hasQuality, fresh, err := p.probe(ctx)
	if err != nil {
		return Sample{}, err
	}
	scribe.LogDebug("weewx", "polled quality [%v] has_quality [%v] fresh [%v]", quality, hasQuality, fresh)
	return Sample{Readings: weewxReading{quality: quality, hasQuality: hasQuality, fresh: fresh}}, nil
}

func (p *weewxPlugin) Aggregate(samples []Sample) (Aggregate, error) {
	return diagnoseWeewx(samples), nil
}

func (p *weewxPlugin) Command(context.Context, State) error {
	return nil
}

func (p *weewxPlugin) State() *StateTracker { return p.state }

func probeWeewx(ctx context.Context) (float64, bool, bool, error) {
	cfg := config.Load()
	broker := cfg.Broker()
	if broker == "" {
		return 0, false, false, fmt.Errorf("broker address is empty")
	}
	opts := mqtt.NewClientOptions().
		AddBroker("tcp://" + broker).
		SetClientID(fmt.Sprintf("network-weewx-%d", time.Now().UnixNano())).
		SetCleanSession(true).
		SetConnectTimeout(weewxConnectWait)
	if token := cfg.BrokerToken(); token != "" {
		opts.SetUsername("network").SetPassword(token)
	}
	var mu sync.Mutex
	var signal, status []byte
	client := mqtt.NewClient(opts)
	token := client.Connect()
	if !token.WaitTimeout(weewxConnectWait) || token.Error() != nil {
		return 0, false, false, fmt.Errorf("connect failed [%s] [%w]", broker, token.Error())
	}
	defer client.Disconnect(250)
	signalToken := client.Subscribe(weewxSignalTopic, 0, func(_ mqtt.Client, msg mqtt.Message) {
		mu.Lock()
		signal = append([]byte(nil), msg.Payload()...)
		mu.Unlock()
	})
	if err := remote.SubscribeGranted(signalToken, weewxConnectWait); err != nil {
		return 0, false, false, fmt.Errorf("subscribe failed [%s] [%w]", weewxSignalTopic, err)
	}
	statusTopic := "supervisor/" + cfg.WeewxHost() + "/data/service/weewx"
	statusToken := client.Subscribe(statusTopic, 0, func(_ mqtt.Client, msg mqtt.Message) {
		mu.Lock()
		status = append([]byte(nil), msg.Payload()...)
		mu.Unlock()
	})
	if err := remote.SubscribeGranted(statusToken, weewxConnectWait); err != nil {
		return 0, false, false, fmt.Errorf("subscribe failed [%s] [%w]", statusTopic, err)
	}
	select {
	case <-ctx.Done():
	case <-time.After(weewxCollectWait):
	}
	mu.Lock()
	defer mu.Unlock()
	quality, hasQuality, fresh := readWeewx(signal, status, time.Now())
	scribe.LogDebug("weewx", "probed status_topic [%s] signal_bytes [%d] status_bytes [%d] quality [%v] fresh [%v]", statusTopic, len(signal), len(status), quality, fresh)
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

func diagnoseWeewx(samples []Sample) Aggregate {
	reading := latestReading[weewxReading](samples)
	quality := math.Round(reading.quality)
	score := clamp(int(quality))
	result := Aggregate{}
	switch {
	case !reading.fresh:
		result = Diagnose(StatusDead, 0, "STALE: weather station not reporting or last update older than one hour")
	case !reading.hasQuality:
		result = Diagnose(StatusDead, 0, "NO_DATA: no retained weather station signal quality on broker")
	case quality >= weewxFitMin:
		result = Diagnose(StatusFit, score, fmt.Sprintf("HEALTHY: weather station signal quality %.0f%%", quality))
	default:
		result = Diagnose(StatusSick, score, fmt.Sprintf("WEAK_SIGNAL: weather station signal quality %.0f%%", quality))
	}
	result.Points = reportWeewx(reading)
	return result
}

func reportWeewx(reading weewxReading) []schema.Point {
	point := []schema.Value{
		weewxName.Of(weewxConsoleName),
		weewxFresh.Of(reading.fresh),
	}
	if reading.hasQuality {
		point = append(point, weewxQuality.Of(round(reading.quality, 0)))
	}
	return []schema.Point{weewxConsole.Point(point...)}
}

func init() {
	register(newWeewxPlugin())
}
