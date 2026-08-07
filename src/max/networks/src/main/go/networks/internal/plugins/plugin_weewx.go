package plugins

import (
	"context"
	"encoding/json"
	"fmt"
	"math"
	"strconv"
	"strings"
	"sync"
	"time"

	"networks/internal/config"
	"networks/internal/plugin"
	"networks/internal/schema"
	"networks/internal/scribe"

	mqtt "github.com/eclipse/paho.mqtt.golang"
)

const (
	weewxSignalTopic = "weewx/weatherstation_coms_signal_quality"
	weewxCollectWait = 2 * time.Second
	weewxConnectWait = 5 * time.Second
	weewxFreshWindow = time.Hour
	signalFitMin     = 50.0
)

var (
	weewxConsole = schema.Declare("weewx/console", "the weather station console link and its health", aggregateCadence)
	weewxOK      = weewxConsole.Bool("ok", "console reporting a fresh pulse with usable signal quality")
	weewxScore   = weewxConsole.Int("score", "", "diagnosis score from 0 to 100")
)

type weewxReading struct {
	quality    float64
	hasQuality bool
	fresh      bool
}

type weewxPlugin struct {
	probe func(ctx context.Context) (quality float64, hasQuality bool, fresh bool, err error)
	state *plugin.StateTracker
}

func newWeewxPlugin() *weewxPlugin {
	return &weewxPlugin{probe: probeWeewx, state: plugin.NewStateTracker(plugin.StateOn)}
}

func (p *weewxPlugin) Name() string { return "weewx" }

func (p *weewxPlugin) Mode() plugin.Mode { return plugin.ModeSnapshot }

func (p *weewxPlugin) Poll(ctx context.Context) (plugin.Sample, error) {
	quality, hasQuality, fresh, err := p.probe(ctx)
	if err != nil {
		return plugin.Sample{}, err
	}
	scribe.LogDebug("weewx", "polled quality [%v] has_quality [%v] fresh [%v]", quality, hasQuality, fresh)
	return plugin.Sample{Readings: weewxReading{
		quality: plugin.Round(quality, 1), hasQuality: hasQuality, fresh: fresh}}, nil
}

func (p *weewxPlugin) Aggregate(samples []plugin.Sample) (plugin.Aggregate, error) {
	return diagnoseWeewx(samples), nil
}

func (p *weewxPlugin) Command(ctx context.Context, newState plugin.State) error {
	return nil
}

func (p *weewxPlugin) State() *plugin.StateTracker { return p.state }

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
	statusTopic := "supervisor/" + cfg.WeewxHost() + "/data/service/weewx"
	client.Subscribe(statusTopic, 0, func(_ mqtt.Client, msg mqtt.Message) {
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

func diagnoseWeewx(samples []plugin.Sample) plugin.Aggregate {
	reading := plugin.Latest[weewxReading](samples)
	fresh := reading.fresh
	quality := reading.quality
	hasQuality := reading.hasQuality
	score := plugin.Clamp(int(math.Round(quality)))
	result := plugin.Aggregate{}
	switch {
	case !fresh:
		result = plugin.Diagnose(plugin.StatusDead, 0, "STALE: weather station not reporting or last update older than one hour")
	case !hasQuality:
		result = plugin.Diagnose(plugin.StatusDead, 0, "NO_DATA: no retained weather station signal quality on broker")
	case quality >= signalFitMin:
		result = plugin.Diagnose(plugin.StatusFit, score, fmt.Sprintf("HEALTHY: weather station signal quality [%.0f%%]", quality))
	default:
		result = plugin.Diagnose(plugin.StatusSick, score, fmt.Sprintf("WEAK_SIGNAL: weather station signal quality [%.0f%%]", quality))
	}
	result.Points = reportWeewx(weewxStats{ok: result.OK, score: result.Score})
	return result
}

func reportWeewx(stats weewxStats) []schema.Point {
	return []schema.Point{weewxConsole.Point(
		weewxOK.Of(stats.ok),
		weewxScore.Of(int64(stats.score)))}
}

type weewxStats struct {
	ok    bool
	score int
}

func init() {
	plugin.Register(newWeewxPlugin())
}
