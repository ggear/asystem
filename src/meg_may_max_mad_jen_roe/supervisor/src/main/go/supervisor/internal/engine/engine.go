package engine

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"log/slog"
	"strconv"
	"strings"
	"supervisor/internal/config"
	"supervisor/internal/metric"
	"supervisor/internal/probe"
	"sync"
	"sync/atomic"
	"time"

	mqtt "github.com/eclipse/paho.mqtt.golang"
)

// RunListeningProbesLoop runs local probes and writes directly to the display cache.
// Lifecycle: probes filtered to metrics with cache listeners (display boxes) plus their deps.
// Cache: shared with display. Probe stats cleaned by syncStatsFields; prevCPUStats pruned by active container ID.
// Cleanup: missing service → Evict (nil). No Delete or Purge — nil records retained for stable display indices.
func RunListeningProbesLoop(ctx context.Context, configPath string, cache *metric.RecordCache, periods config.Periods) {
	for host, ids := range cache.ListenerIDs() {
		for _, id := range ids {
			record := metric.NewRecord(metric.NewNilValue())
			cache.Store(metric.NewServiceSchemaRecordGUID(id, host, 0), &record)
			for _, depID := range metric.GetIDDeps(id) {
				record := metric.NewRecord(metric.NewNilValue())
				cache.Store(metric.NewServiceSchemaRecordGUID(depID, host, 0), &record)
			}
		}
	}
	if err := probe.Create(configPath, cache, periods); err != nil {
		slog.Error("run listening probes loop: create failed", "error", err)
		return
	}
	if err := probe.Run(ctx, nil); err != nil && !errors.Is(err, context.Canceled) && !errors.Is(err, context.DeadlineExceeded) {
		slog.Error("run listening probes loop: run failed", "error", err)
	}
}

// RunListeningStreamLoop subscribes to MQTT and writes remote metrics to the display cache.
// Lifecycle: probes filtered to metrics with cache listeners (display boxes). RegisterService adds entries for new services.
// Cache: shared with display. Receives data from RunAllProbesPublishLoop on remote hosts.
// Cleanup: empty/nil payload or host offline → Evict (nil). Purge evicts stale non-nil to nil. No Delete — nil records retained for stable display indices.
func RunListeningStreamLoop(ctx context.Context, configPath string, cache *metric.RecordCache, periods config.Periods) {
	for host, ids := range cache.ListenerIDs() {
		for _, id := range ids {
			record := metric.NewRecord(metric.NewNilValue())
			cache.Store(metric.NewServiceSchemaRecordGUID(id, host, 0), &record)
		}
	}
	var rxCount atomic.Int64
	onConnect := func(client mqtt.Client) {
		hostStatusMutex.Lock()
		clear(hostStatus)
		hostStatusMutex.Unlock()
		var subscribedMu sync.Mutex
		subscribed := make(map[string]struct{})
		subscribe := func(b metric.TopicBinding) {
			subscribedMu.Lock()
			_, exists := subscribed[b.Topic]
			if !exists {
				subscribed[b.Topic] = struct{}{}
			}
			subscribedMu.Unlock()
			if exists {
				return
			}
			guid := b.GUID
			client.Subscribe(b.Topic, 0, func(_ mqtt.Client, msg mqtt.Message) {
				if !isHostOnline(guid.Host) {
					return
				}
				rxCount.Add(1)
				if len(msg.Payload()) == 0 {
					cache.Evict(guid.Host, guid.ServiceName)
					return
				}
				var value metric.ValueData
				if err := json.Unmarshal(msg.Payload(), &value); err != nil {
					slog.Warn("stream unmarshal failed", "topic", msg.Topic(), "error", err)
					return
				}
				if value.Pulse == nil {
					cache.Evict(guid.Host, guid.ServiceName)
					return
				}
				record := metric.NewRecord(value)
				cache.Store(guid, &record)
			})
		}
		for _, b := range cache.Topics() {
			subscribe(b)
		}
		client.Subscribe("supervisor/+/data/service/+/name", 1, func(_ mqtt.Client, msg mqtt.Message) {
			var value metric.ValueData
			if err := json.Unmarshal(msg.Payload(), &value); err != nil || value.Pulse == nil {
				return
			}
			serviceName := value.Pulse.ValueString
			if serviceName == "" {
				return
			}
			tokens := strings.Split(msg.Topic(), "/")
			if len(tokens) < 6 || tokens[1] == "" {
				return
			}
			hostName := tokens[1]
			if !isHostOnline(hostName) {
				return
			}
			rxCount.Add(1)
			for _, b := range cache.RegisterService(hostName, serviceName, false) {
				subscribe(b)
			}
			record := metric.NewRecord(value)
			cache.Store(metric.NewServiceRecordGUID(metric.MetricServiceName, hostName, serviceName), &record)
		})
		client.Subscribe("supervisor/+/status", 1, func(_ mqtt.Client, msg mqtt.Message) {
			tokens := strings.Split(msg.Topic(), "/")
			if len(tokens) < 3 || tokens[1] == "" {
				return
			}
			hostName := tokens[1]
			payload := strings.TrimSpace(string(msg.Payload()))
			rxCount.Add(1)
			switch payload {
			case hostStatusOnline:
				statusStart := time.Now()
				storeHostStatus(hostName, true)
				for _, b := range cache.Topics() {
					if b.GUID.Host != hostName {
						continue
					}
					subscribedMu.Lock()
					delete(subscribed, b.Topic)
					subscribedMu.Unlock()
					client.Unsubscribe(b.Topic)
					subscribe(b)
				}
				slog.Info("state", "engine", "broker", "phase", "status", "duration", time.Since(statusStart).Truncate(time.Millisecond), "host", hostName, "status", hostStatusOnline)
			case hostStatusOffline, "":
				statusStart := time.Now()
				storeHostStatus(hostName, false)
				for _, svc := range cache.Services(hostName) {
					cache.Evict(hostName, svc)
				}
				hostPrefix := "supervisor/" + hostName + "/"
				subscribedMu.Lock()
				for topic := range subscribed {
					if strings.HasPrefix(topic, hostPrefix) {
						delete(subscribed, topic)
					}
				}
				subscribedMu.Unlock()
				for _, id := range metric.GetIDsByKind([]metric.MetricKind{metric.MetricKindHost}) {
					record := metric.NewRecord(metric.NewNilValue())
					cache.Store(metric.NewRecordGUID(id, hostName), &record)
				}
				slog.Warn("state", "engine", "broker", "phase", "status", "duration", time.Since(statusStart).Truncate(time.Millisecond), "host", hostName, "status", hostStatusOffline)
			default:
				slog.Warn("stream unknown status payload", "host", hostName, "payload", payload)
			}
		})
	}
	client, err := brokerConnect(configPath, onConnect, "", "")
	if err != nil {
		slog.Error("run listening stream loop", "error", err)
		return
	}
	defer client.Disconnect(250)
	cache.SubscribeDeletes(&brokerDeletesListener{client: client})
	purgeInterval := time.Duration(max(periods.PulseMillis+1000, 2000)) * time.Millisecond
	purgeTicker := time.NewTicker(purgeInterval)
	defer purgeTicker.Stop()
	for {
		select {
		case <-ctx.Done():
			return
		case <-purgeTicker.C:
			purgeStart := time.Now()
			cache.Purge(periods.HeartbeatSecs + 10)
			rx := rxCount.Swap(0)
			rate := int64(0)
			if secs := int64(purgeInterval.Seconds()); secs > 0 {
				rate = rx / secs
			}
			slog.Debug("profiling", "engine", "subscribe", "phase", "purge", "duration", time.Since(purgeStart).Truncate(time.Millisecond), "received", fmt.Sprintf("%dmsg", rx), "rate", fmt.Sprintf("%dmsg/s", rate))
		}
	}
}

// RunAllProbesOnce runs all probes for a single pulse cycle then exits.
// Lifecycle: all probe metrics registered (not filtered). Runs with a 3x pulse timeout, no trend tracking.
// Cache: caller-owned, short-lived, discarded on return.
// Cleanup: none needed.
func RunAllProbesOnce(ctx context.Context, configPath string, cache *metric.RecordCache) {
	for _, id := range metric.GetIDs() {
		record := metric.NewRecord(metric.NewNilValue())
		cache.Store(metric.NewServiceSchemaRecordGUID(id, config.Load(configPath).Host(), 0), &record)
	}
	periods := config.Periods{
		PollMillis:   500,
		PulseMillis:  1000,
		TrendHours:   0,
		CacheHours:   0,
		SnapshotMins: 0,
	}
	if err := probe.Create(configPath, cache, periods); err != nil {
		slog.Error("run all probes once: create failed", "error", err)
		return
	}
	timeout := time.Duration(3*periods.PulseMillis) * time.Millisecond
	ctx, cancel := context.WithTimeout(ctx, timeout)
	defer cancel()
	err := probe.Run(ctx, nil)
	if err != nil && !errors.Is(err, context.DeadlineExceeded) {
		slog.Error("run all probes once: run failed", "error", err)
	}
}

type lpKey struct {
	host    string
	service string
}

// RunAllProbesPublishLoop runs local probes and publishes metrics to MQTT and the database.
// Lifecycle: all probe metrics registered (not filtered). Probes poll each tick; onPulse publishes to MQTT. On shutdown, publishes offline status and empty payloads to clear retained topics.
// Cache: own instance, not shared with any display. Take drains dirty map each pulse.
// Cleanup: missing service → Evict (nil) → next pulse publishes nil + empty tombstone → Delete removes nil records. Delete is safe here (no display indices to destabilise).
func RunAllProbesPublishLoop(ctx context.Context, configPath string, cache *metric.RecordCache, periods config.Periods) {
	for _, id := range metric.GetIDs() {
		record := metric.NewRecord(metric.NewNilValue())
		cache.Store(metric.NewServiceSchemaRecordGUID(id, config.Load(configPath).Host(), 0), &record)
	}
	if err := probe.Create(configPath, cache, periods); err != nil {
		slog.Error("run all probes publish loop: create failed", "error", err)
		return
	}
	hostName := config.Load(configPath).Host()
	statusTopic := "supervisor/" + hostName + "/status"
	serviceNameTopic := "supervisor/" + hostName + "/data/service/+/name"
	onConnect := func(client mqtt.Client) {
		client.Subscribe(serviceNameTopic, 1, func(_ mqtt.Client, msg mqtt.Message) {
			var value metric.ValueData
			if err := json.Unmarshal(msg.Payload(), &value); err != nil || value.Pulse == nil {
				return
			}
			if serviceName := value.Pulse.ValueString; serviceName != "" {
				cache.RegisterService(hostName, serviceName, true)
			}
		})
	}
	client, err := brokerConnect(configPath, onConnect, statusTopic, hostStatusOffline)
	if err != nil {
		slog.Error("run all probes publish loop: broker connect failed", "error", err)
		return
	}
	defer func() {
		client.Publish(statusTopic, 1, true, hostStatusOffline).WaitTimeout(2 * time.Second)
		cache.Records(func(_ metric.RecordGUID, record *metric.Record) {
			if record.Topic != "" {
				client.Publish(record.Topic, 0, true, "")
			}
		})
		client.Disconnect(2500)
	}()
	cache.SubscribeDeletes(&brokerPublishDeletesListener{client: client})
	var lineProtocol strings.Builder
	err = probe.Run(ctx, func(isHeartbeat bool) {
		pulseStart := time.Now()
		txCount := 0
		lineProtocol.Reset()
		groups := make(map[lpKey]*strings.Builder)
		var toDelete []lpKey
		addToGroup := func(key lpKey, field, suffix string, d *metric.ValueDataDetail) {
			if d.Kind != metric.ValueInt && d.Kind != metric.ValueFloat {
				return
			}
			b := groups[key]
			if b == nil {
				b = new(strings.Builder)
				groups[key] = b
			} else {
				b.WriteByte(',')
			}
			b.WriteString(field)
			b.WriteString(suffix)
			b.WriteByte('=')
			b.WriteString(d.Value())
			if d.Kind == metric.ValueInt {
				b.WriteByte('i')
			}
		}
		process := func(guid metric.RecordGUID, record *metric.Record) {
			if record.Topic != "" {
				if record.Value.Pulse != nil {
					if payload, jsonErr := json.Marshal(record.Value); jsonErr == nil {
						client.Publish(record.Topic, 0, true, payload)
						txCount++
					} else {
						slog.Warn("publish marshal failed", "topic", record.Topic, "error", jsonErr)
					}
				} else if guid.ServiceName != metric.ServiceNameUnset && !strings.HasPrefix(guid.ServiceName, metric.ServiceNameSchema) {
					if payload, jsonErr := json.Marshal(record.Value); jsonErr == nil {
						client.Publish(record.Topic, 0, true, payload)
						txCount++
					}
					client.Publish(record.Topic, 0, true, "")
					txCount++
					toDelete = append(toDelete, lpKey{host: guid.Host, service: guid.ServiceName})
				}
			}
			if record.Value.Pulse == nil || len(record.Tags) == 0 {
				return
			}
			field, ok := record.Tags["metric"]
			if !ok {
				return
			}
			key := lpKey{host: guid.Host, service: guid.ServiceName}
			addToGroup(key, field, "", record.Value.Pulse)
			if record.Value.Trend != nil {
				addToGroup(key, field, "_trend", record.Value.Trend)
			}
		}
		if isHeartbeat {
			client.Publish(statusTopic, 1, true, hostStatusOnline)
			txCount++
			cache.Records(func(guid metric.RecordGUID, record *metric.Record) {
				process(guid, record)
			})
			cache.Take()
		} else {
			for _, guid := range cache.Take() {
				record, ok := cache.Load(guid)
				if !ok {
					continue
				}
				process(guid, record)
			}
		}
		deleted := make(map[lpKey]bool)
		for _, k := range toDelete {
			if !deleted[k] {
				deleted[k] = true
				cache.Delete(k.host, k.service)
			}
		}
		ts := strconv.FormatInt(time.Now().UnixNano(), 10)
		for key, b := range groups {
			lineProtocol.WriteString("supervisor,host=")
			lineProtocol.WriteString(key.host)
			if key.service != "" {
				lineProtocol.WriteString(",service=")
				lineProtocol.WriteString(key.service)
			}
			lineProtocol.WriteByte(' ')
			lineProtocol.WriteString(b.String())
			lineProtocol.WriteByte(' ')
			lineProtocol.WriteString(ts)
			lineProtocol.WriteByte('\n')
		}

		// TODO: Publish to database
		if lineProtocol.Len() > 0 {
		}

		phase := "pulse"
		if isHeartbeat {
			phase = "heartbeat"
		}
		slog.Debug("profiling", "engine", "publish", "phase", phase, "duration", time.Since(pulseStart).Truncate(time.Millisecond), "transmit", fmt.Sprintf("%dmsg", txCount))
	})
	if err != nil && !errors.Is(err, context.Canceled) && !errors.Is(err, context.DeadlineExceeded) {
		slog.Error("run all probes publish loop: run failed", "error", err)
	}
}

const (
	hostStatusOnline  = "online"
	hostStatusOffline = "offline"
)

var (
	hostStatusMutex sync.RWMutex
	hostStatus      map[string]bool
)

func init() {
	hostStatus = make(map[string]bool)
}

func isHostOnline(hostName string) bool {
	hostStatusMutex.RLock()
	online, known := hostStatus[hostName]
	hostStatusMutex.RUnlock()
	return !known || online
}

func storeHostStatus(hostName string, online bool) {
	hostStatusMutex.Lock()
	hostStatus[hostName] = online
	hostStatusMutex.Unlock()
}
