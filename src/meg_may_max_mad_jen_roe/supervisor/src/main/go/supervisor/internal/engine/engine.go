package engine

import (
	"context"
	"encoding/json"
	"errors"
	"log/slog"
	"strings"
	"supervisor/internal/config"
	"supervisor/internal/metric"
	"supervisor/internal/probe"
	"sync"
	"time"

	mqtt "github.com/eclipse/paho.mqtt.golang"
)

// DONE:
//  - Indexer to ignore Shadows
//  - Update Size() to ignore schema
//  - Remove index from newCacheMetricTask
//  - Make sure display reconciles ServiceIndexSchema to ServiceIndex for GUID on lookup
//  - Add probe profile debug logs
//  - Add config services, test
//  - Make sure Evict to only work on non __SCHEMA services, to only evict from specific host and service name, to set value to nil
//  - Delete to only work on non __SCHEMA services, to only delete from specific host and service name, to only delete if value is nil
//  - Implement cache Purge func and routine for stream, Evict and Delete across entire cache.
// TODO:
//  - Purge invoked as a goroutine for stream, procedurally for probes in execute
//  - Implement all Load funcs and test cases
//  - drawValue to ~ out if necessary
//  - Implement display update tests
//  - Validate hot path is fast, validate dont recompute tags/topics

func RunAllProbesOnce(ctx context.Context, configPath string, cache *metric.RecordCache) {
	hostName := config.LocalHostName()
	if hostName == "" {
		slog.Error("cannot resolve local host name")
		return
	}
	for _, id := range metric.GetIDs() {
		record := metric.NewRecord(metric.NewNilValue())
		cache.Store(metric.NewServiceSchemaRecordGUID(id, hostName, 0), &record)
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

func RunListeningStreamLoop(ctx context.Context, configPath string, cache *metric.RecordCache, periods config.Periods) {
	streamHostStatusMu.Lock()
	streamHostStatus = make(map[string]bool)
	streamHostStatusMu.Unlock()
	for host, ids := range cache.ListenerIDs() {
		for _, id := range ids {
			record := metric.NewRecord(metric.NewNilValue())
			cache.Store(metric.NewServiceSchemaRecordGUID(id, host, 0), &record)
		}
	}
	onConnect := func(client mqtt.Client) {
		subscribe := func(b metric.TopicBinding) {
			guid := b.GUID
			client.Subscribe(b.Topic, 0, func(_ mqtt.Client, msg mqtt.Message) {
				if !hostIsOnline(guid.Host) {
					return
				}
				var value metric.ValueData
				if err := json.Unmarshal(msg.Payload(), &value); err != nil {
					slog.Debug("stream: unmarshal failed", "topic", msg.Topic(), "error", err)
					return
				}
				if value.Pulse == nil {
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
			if !hostIsOnline(hostName) {
				return
			}
			for _, b := range cache.RegisterService(hostName, serviceName) {
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
			switch payload {
			case hostStatusOnline:
				setHostStatus(hostName, true)
			case hostStatusOffline:
				setHostStatus(hostName, false)
				for svc := range cache.Services() {
					cache.Evict(hostName, svc)
				}
				for _, id := range metric.GetIDsByKind([]metric.MetricKind{metric.MetricKindHost}) {
					record := metric.NewRecord(metric.NewNilValue())
					cache.Store(metric.NewRecordGUID(id, hostName), &record)
				}
			default:
				slog.Debug("stream: unknown status payload", "host", hostName, "payload", payload)
			}
		})
	}
	client, err := brokerConnect(configPath, onConnect)
	if err != nil {
		slog.Error("run listening stream loop", "error", err)
		return
	}
	defer client.Disconnect(250)
	cache.SubscribeDeletes(&brokerDeletesListener{client: client})
	purgeTicker := time.NewTicker(time.Duration(max(periods.PulseMillis+1000, 2000)) * time.Millisecond)
	defer purgeTicker.Stop()
	for {
		select {
		case <-ctx.Done():
			return
		case <-purgeTicker.C:
			cache.Purge(periods.HeartbeatSecs + 10)
		}
	}
}

func RunAllProbesPublishLoop(ctx context.Context, cache *metric.RecordCache, periods config.Periods) {
	_ = periods
	// TODO:
	//  - Loop over all metrics and load into cache
	//  - Start probes, writing to cache per metric (necessary for deps, not for JSON/LineProto),
	//                  writing async cache.publishStream by value (JSON) per metric,
	//                  writing line protocol to reused buffer per metric,
	//                  writing async cache.publishHistory by value (ValueString LineProto) at the end fo cycle
}

const (
	hostStatusOnline  = "online"
	hostStatusOffline = "offline"
)

var (
	streamHostStatusMu sync.RWMutex
	streamHostStatus   = make(map[string]bool)
)

func hostIsOnline(hostName string) bool {
	streamHostStatusMu.RLock()
	online, known := streamHostStatus[hostName]
	streamHostStatusMu.RUnlock()
	return !known || online
}

func setHostStatus(hostName string, online bool) {
	streamHostStatusMu.Lock()
	streamHostStatus[hostName] = online
	streamHostStatusMu.Unlock()
}
