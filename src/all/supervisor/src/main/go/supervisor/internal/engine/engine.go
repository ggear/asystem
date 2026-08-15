package engine

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"log/slog"
	"sort"
	"strconv"
	"strings"
	"supervisor/internal/config"
	"supervisor/internal/metric"
	"supervisor/internal/probe"
	"supervisor/internal/schema"
	"sync"
	"sync/atomic"
	"time"

	mqtt "github.com/eclipse/paho.mqtt.golang"
)

// RunListeningProbesLoop runs local probes and writes directly to the display cache.
// Lifecycle: seeds nil records for listener IDs and their deps, then runs probes filtered to those metrics.
// Cache: shared with display. Probe stats cleaned by syncStatsFields; prevCPUStats pruned by active container ID.
// Cleanup: missing service → Evict (nil) + Delete removes nil records and reindexes. No Purge needed (local probes manage staleness directly).
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
		slog.Error("state", "engine", "probes", "phase", "create", "detail", fmt.Sprintf("listening probes loop create failed with [%v]", err))
		return
	}
	if err := probe.Run(ctx, nil); err != nil && !errors.Is(err, context.Canceled) && !errors.Is(err, context.DeadlineExceeded) {
		slog.Error("state", "engine", "probes", "phase", "run", "detail", fmt.Sprintf("listening probes loop run failed with [%v]", err))
	}
}

// RunListeningStreamLoop subscribes to MQTT and writes remote metrics to the display cache.
// Lifecycle: seeds nil records for listener IDs (no deps), subscribes to data topics, service/name discovery, and host status.
// Cache: shared with display. Receives data published by RunAllProbesPublishLoop on remote hosts.
// Discovery: service/name messages trigger RegisterService which adds nil entries and returns new topic bindings to subscribe.
// Host online: unsubscribe+resubscribe forces broker to redeliver retained messages, restoring records. Unknown hosts default to online.
// Refresh: on connect, and after a reconcile that actually reaped, cache.Refresh() signals the display to redraw everything from the
// cache and re-register its update listeners, so a reconnect (laptop wake) cannot leave the screen stuck on nils waiting for a manual
// Ctrl-R and a reindexed slot cannot render its old occupant. It is not sent per host transition — one connect refreshes every host.
// Host offline->online transition (serve restart / reconnect): schedules a deferred reconcile rather than wiping the host, so surviving
// services keep their values on screen throughout. The first transition after a connect skips the resubscribe entirely, since onConnect
// has just subscribed every cached topic fresh and the broker is already redelivering; later transitions (a serve restart on a live
// connection) unsubscribe+resubscribe to force that redelivery. Either way the reconcile runs one grace period later and Evict+Deletes
// only the services that received nothing since the transition, which is exactly the set removed while this watch was not listening.
// Host offline: Evict (nil) all services (keeps slots for repopulation), store nil for host-kind metrics, drop from subscribed map.
// Cleanup: empty/nil payload → Evict (nil) + Delete. Purge evicts stale non-nil to nil (via hostLastSeen), then deletes stale nil service records and reindexes.
func RunListeningStreamLoop(ctx context.Context, configPath string, cache *metric.RecordCache, periods config.Periods) {
	for host, ids := range cache.ListenerIDs() {
		for _, id := range ids {
			record := metric.NewRecord(metric.NewNilValue())
			cache.Store(metric.NewServiceSchemaRecordGUID(id, host, 0), &record)
		}
	}
	var rxCount atomic.Int64
	var subscribedMutex sync.Mutex
	subscribed := make(map[string]metric.RecordGUID)
	var reconcileMutex sync.Mutex
	reconciles := make(map[string]hostReconcile)
	connected := time.Now()
	reconcileDelay := max(time.Duration(2*periods.PulseMillis)*time.Millisecond, reconcileGrace)
	onData := func(_ mqtt.Client, msg mqtt.Message) {
		subscribedMutex.Lock()
		guid, known := subscribed[msg.Topic()]
		subscribedMutex.Unlock()
		if !known || !isHostOnline(guid.Host) {
			return
		}
		rxCount.Add(1)
		if len(msg.Payload()) == 0 {
			cache.Evict(guid.Host, guid.ServiceName)
			cache.Delete(guid.Host, guid.ServiceName)
			return
		}
		var value metric.ValueData
		if err := json.Unmarshal(msg.Payload(), &value); err != nil {
			slog.Warn("state", "engine", "subscribe", "phase", "stream", "detail", fmt.Sprintf("unmarshal failed on [%s] with [%v]", msg.Topic(), err))
			return
		}
		if value.Pulse == nil {
			cache.Evict(guid.Host, guid.ServiceName)
			cache.Delete(guid.Host, guid.ServiceName)
			return
		}
		value.Timestamp = time.Now().Unix()
		record := metric.NewRecord(value)
		cache.Store(guid, &record)
	}
	subscribeTopics := func(client mqtt.Client, bindings []metric.TopicBinding) int {
		filters := make(map[string]byte, len(bindings))
		subscribedMutex.Lock()
		for _, b := range bindings {
			if _, exists := subscribed[b.Topic]; exists {
				continue
			}
			subscribed[b.Topic] = b.GUID
			filters[b.Topic] = 0
		}
		subscribedMutex.Unlock()
		if len(filters) > 0 {
			client.SubscribeMultiple(filters, onData)
		}
		return len(filters)
	}
	resubscribeHost := func(client mqtt.Client, hostName string) int {
		var bindings []metric.TopicBinding
		for _, b := range cache.Topics() {
			if b.GUID.Host == hostName {
				bindings = append(bindings, b)
			}
		}
		topics := make([]string, 0, len(bindings))
		subscribedMutex.Lock()
		for _, b := range bindings {
			delete(subscribed, b.Topic)
			topics = append(topics, b.Topic)
		}
		subscribedMutex.Unlock()
		if len(topics) > 0 {
			client.Unsubscribe(topics...)
		}
		return subscribeTopics(client, bindings)
	}
	onConnect := func(client mqtt.Client) {
		connectStart := time.Now()
		hostStatusMutex.Lock()
		clear(hostStatus)
		hostStatusMutex.Unlock()
		subscribedMutex.Lock()
		clear(subscribed)
		subscribedMutex.Unlock()
		reconcileMutex.Lock()
		clear(reconciles)
		connected = time.Now()
		reconcileMutex.Unlock()
		topics := subscribeTopics(client, cache.Topics())
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
			subscribeTopics(client, cache.RegisterService(hostName, serviceName, false))
			value.Timestamp = time.Now().Unix()
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
				hostStatusMutex.RLock()
				alreadyOnline := hostStatus[hostName]
				hostStatusMutex.RUnlock()
				storeHostStatus(hostName, true)
				reconcileMutex.Lock()
				pending, resubscribe := reconciles[hostName]
				pending.host = hostName
				if !alreadyOnline {
					pending.started = connected
					if resubscribe {
						pending.started = time.Now()
					}
					pending.deadline = time.Now().Add(reconcileDelay)
				}
				reconciles[hostName] = pending
				reconcileMutex.Unlock()
				topics := 0
				if resubscribe {
					topics = resubscribeHost(client, hostName)
				}
				slog.Info("state", "engine", "broker", "phase", "status", "duration", time.Since(statusStart), "detail", fmt.Sprintf("host [%s] status [%s] resubscribed [%d] topics reconcile [%v]", hostName, hostStatusOnline, topics, !alreadyOnline))
			case hostStatusOffline, "":
				statusStart := time.Now()
				storeHostStatus(hostName, false)
				evicted := cache.Services(hostName)
				for _, svc := range evicted {
					cache.Evict(hostName, svc)
				}
				hostPrefix := "supervisor/" + hostName + "/"
				subscribedMutex.Lock()
				for topic := range subscribed {
					if strings.HasPrefix(topic, hostPrefix) {
						delete(subscribed, topic)
					}
				}
				subscribedMutex.Unlock()
				reconcileMutex.Lock()
				pending := reconciles[hostName]
				pending.deadline = time.Time{}
				reconciles[hostName] = pending
				reconcileMutex.Unlock()
				for _, id := range metric.GetIDsByKind([]metric.MetricKind{metric.MetricKindHost}) {
					record := metric.NewRecord(metric.NewNilValue())
					cache.Store(metric.NewRecordGUID(id, hostName), &record)
				}
				slog.Warn("state", "engine", "broker", "phase", "status", "duration", time.Since(statusStart), "detail", fmt.Sprintf("host [%s] status [%s] evicted [%d] services", hostName, hostStatusOffline, len(evicted)))
			default:
				slog.Warn("state", "engine", "broker", "phase", "status", "detail", fmt.Sprintf("host [%s] unknown status payload [%s]", hostName, payload))
			}
		})
		cache.Refresh()
		slog.Info("state", "engine", "subscribe", "phase", "connect", "duration", time.Since(connectStart), "detail", fmt.Sprintf("subscribed [%d] topics", topics))
	}
	client, err := brokerConnect(configPath, onConnect, "", "")
	if err != nil {
		slog.Error("state", "engine", "subscribe", "phase", "connect", "detail", fmt.Sprintf("listening stream loop connect failed with [%v]", err))
		return
	}
	defer client.Disconnect(250)
	storeWakeHandler(func() { brokerRevive(ctx, client) })
	defer storeWakeHandler(nil)
	cache.SubscribeDeletes(&brokerDeletesListener{
		client: client,
		onDelete: func(topic string) {
			subscribedMutex.Lock()
			delete(subscribed, topic)
			subscribedMutex.Unlock()
		},
	})
	purgeInterval := time.Duration(max(periods.PulseMillis+1000, 2000)) * time.Millisecond
	purgeTicker := time.NewTicker(purgeInterval)
	defer purgeTicker.Stop()
	for {
		select {
		case <-ctx.Done():
			return
		case <-purgeTicker.C:
			purgeStart := time.Now()
			cache.Purge(periods.HeartbeatSecs + 10*periods.PulseMillis/1000)
			now := time.Now()
			var due []hostReconcile
			reconcileMutex.Lock()
			for hostName, pending := range reconciles {
				if pending.deadline.IsZero() || now.Before(pending.deadline) {
					continue
				}
				due = append(due, pending)
				pending.deadline = time.Time{}
				reconciles[hostName] = pending
			}
			reconcileMutex.Unlock()
			for _, pending := range due {
				reconcileStart := time.Now()
				services := cache.ServicesBefore(pending.host, pending.started.Unix())
				for _, service := range services {
					cache.Evict(pending.host, service)
					cache.Delete(pending.host, service)
				}
				if len(services) > 0 {
					cache.Refresh()
				}
				slog.Info("state", "engine", "subscribe", "phase", "reconcile", "duration", time.Since(reconcileStart), "detail", fmt.Sprintf("host [%s] reaped [%d] services after [%d] ms", pending.host, len(services), time.Since(pending.started).Milliseconds()))
			}
			rx := rxCount.Swap(0)
			rate := int64(0)
			if secs := int64(purgeInterval.Seconds()); secs > 0 {
				rate = rx / secs
			}
			slog.Debug("profiling", "engine", "subscribe", "phase", "purge", "duration", time.Since(purgeStart), "detail", fmt.Sprintf("received [%d] msgs at [%d] msg/s", rx, rate))
		}
	}
}

// RunAllProbesOnce runs all probes for a single pulse cycle then exits.
// Lifecycle: all probe metrics registered (not filtered). Runs with a 3x pulse timeout (3s default), no trend tracking, no onPulse callback.
// Cache: caller-owned, short-lived, discarded on return.
// Cleanup: none needed (cache is ephemeral).
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
		slog.Error("state", "engine", "probes", "phase", "create", "detail", fmt.Sprintf("all probes once create failed with [%v]", err))
		return
	}
	timeout := time.Duration(3*periods.PulseMillis) * time.Millisecond
	ctx, cancel := context.WithTimeout(ctx, timeout)
	defer cancel()
	err := probe.Run(ctx, nil)
	if err != nil && !errors.Is(err, context.DeadlineExceeded) {
		slog.Error("state", "engine", "probes", "phase", "run", "detail", fmt.Sprintf("all probes once run failed with [%v]", err))
	}
}

type lpKey struct {
	host    string
	service string
}

// RunAllProbesPublishLoop runs local probes and publishes metrics to MQTT and the database.
// Lifecycle: all probe metrics registered (not filtered). Subscribes to own service/name topic to discover services via retained messages.
// Self-healing: the service/name topic MUST be published RETAINED (see process below). After a non-graceful exit (SIGKILL/OOM) the
// deferred tombstone-all does not run, so a departed service's stale retained records linger on the broker. On restart the retained name
// is the only breadcrumb that lets this loop rediscover that service (RegisterService) so the per-pulse Cleanup below can evict+delete it
// and publish empty tombstones that clear the broker; without retention the orphan would never be reconciled. See supervisor/CLAUDE.md.
// Heartbeat: publishes online status + ALL records (not just dirty) + drains dirty. Non-heartbeat: publishes dirty records only.
// Line protocol: int/float metrics grouped per host+service for database writes.
// Cache: own instance, not shared with any display. Take drains dirty map each pulse.
// Shutdown: publishes offline status and empty payloads for all topics with retained messages.
// Cleanup: missing service → Evict (nil) + Delete removes nil records and publishes empty tombstones via deletesListener.
// Safety net: if a nil-pulse record survives to the pulse handler (e.g. MQTT interleave), it publishes nil JSON + empty tombstone then deletes locally.
func RunAllProbesPublishLoop(ctx context.Context, configPath string, cache *metric.RecordCache, periods config.Periods) {
	for _, id := range metric.GetIDs() {
		record := metric.NewRecord(metric.NewNilValue())
		cache.Store(metric.NewServiceSchemaRecordGUID(id, config.Load(configPath).Host(), 0), &record)
	}
	if err := probe.Create(configPath, cache, periods); err != nil {
		slog.Error("state", "engine", "publish", "phase", "create", "detail", fmt.Sprintf("publish loop create failed with [%v]", err))
		return
	}
	hostName := config.Load(configPath).Host()
	statusTopic := "supervisor/" + hostName + "/status"
	serviceNameTopic := "supervisor/" + hostName + "/data/service/+/name"
	commandTopic := "supervisor/+/command/service/+"
	var hasConnected atomic.Bool
	var forceRepublish atomic.Bool
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
		client.Subscribe(commandTopic, 1, func(_ mqtt.Client, msg mqtt.Message) {
			tokens := strings.Split(msg.Topic(), "/")
			if len(tokens) < 5 || tokens[1] == "" || tokens[4] == "" {
				return
			}

			// TODO: Implement command handling

			slog.Debug("command", "engine", "broker", "phase", "command", "detail", fmt.Sprintf("host [%s] service [%s] payload [%s]", tokens[1], tokens[4], string(msg.Payload())))
		})
		if hasConnected.Swap(true) {
			statusReadback := make(chan string, 1)
			client.Subscribe(statusTopic, 1, func(_ mqtt.Client, msg mqtt.Message) {
				select {
				case statusReadback <- strings.TrimSpace(string(msg.Payload())):
				default:
				}
			}).Wait()
			var seen string
			select {
			case seen = <-statusReadback:
			case <-time.After(2 * time.Second):
			}
			client.Unsubscribe(statusTopic)
			if seen != hostStatusOnline {
				forceRepublish.Store(true)
			}
		}
	}
	client, err := brokerConnect(configPath, onConnect, statusTopic, hostStatusOffline)
	if err != nil {
		slog.Error("state", "engine", "broker", "phase", "connect", "detail", fmt.Sprintf("publish loop broker connect failed with [%v]", err))
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
	var db *databaseClient
	if config.Load(configPath).Database() != "" {
		var dbErr error
		db, dbErr = databaseConnect(configPath)
		if dbErr != nil {
			slog.Error("state", "engine", "database", "phase", "connect", "detail", fmt.Sprintf("publish loop database connect failed with [%v]", dbErr))
		} else {
			defer db.close()
		}
	}
	var lineProtocol bytes.Buffer
	groups := make(map[lpKey]map[string]schema.Field)
	hostRelation := metric.HostRelation()
	serviceRelation := metric.ServiceRelation()
	var toDelete []lpKey
	deleted := make(map[lpKey]bool)
	err = probe.Run(ctx, func(isHeartbeat bool) {
		pulseStart := time.Now()
		if forceRepublish.Swap(false) && !isHeartbeat {
			client.Publish(statusTopic, 1, true, hostStatusOnline)
			cache.Records(func(_ metric.RecordGUID, record *metric.Record) {
				if record.Topic == "" || record.Value.Pulse == nil {
					return
				}
				if payload, jsonErr := json.Marshal(record.Value); jsonErr == nil {
					client.Publish(record.Topic, 0, true, payload)
				}
			})
		}
		txCount := 0
		txBytes := 0
		lineProtocol.Reset()
		clear(groups)
		toDelete = toDelete[:0]
		clear(deleted)
		addToGroup := func(key lpKey, field, suffix string, d *metric.ValueDataDetail) {
			fields := groups[key]
			if fields == nil {
				fields = map[string]schema.Field{}
				groups[key] = fields
			}
			fields[field+suffix] = schema.Field{Text: d.Value(), Flag: d.OK}
		}
		process := func(guid metric.RecordGUID, record *metric.Record) {
			if record.Topic != "" {
				if record.Value.Pulse != nil {
					if payload, jsonErr := json.Marshal(record.Value); jsonErr == nil {
						client.Publish(record.Topic, 0, true, payload)
						txCount++
						txBytes += len(payload)
					} else {
						slog.Warn("state", "engine", "publish", "phase", "marshal", "detail", fmt.Sprintf("marshal failed on [%s] with [%v]", record.Topic, jsonErr))
					}
				} else if guid.ServiceName != metric.ServiceNameUnset && !strings.HasPrefix(guid.ServiceName, metric.ServiceNameSchema) {
					if payload, jsonErr := json.Marshal(record.Value); jsonErr == nil {
						client.Publish(record.Topic, 0, true, payload)
						txCount++
						txBytes += len(payload)
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
		brokerStart := time.Now()
		if isHeartbeat {
			client.Publish(statusTopic, 1, true, hostStatusOnline)
			txCount++
			txBytes += len(hostStatusOnline)
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
		for _, k := range toDelete {
			if !deleted[k] {
				deleted[k] = true
				cache.Delete(k.host, k.service)
			}
		}
		brokerDuration := time.Since(brokerStart)
		ts := strconv.FormatInt(time.Now().UnixNano(), 10)
		order := make([]lpKey, 0, len(groups))
		for key := range groups {
			order = append(order, key)
		}
		sort.Slice(order, func(i, j int) bool {
			if order[i].host != order[j].host {
				return order[i].host < order[j].host
			}
			return order[i].service < order[j].service
		})
		for _, key := range order {
			relation := hostRelation
			tags := [][2]string{{"host", key.host}}
			if key.service != "" {
				relation = serviceRelation
				tags = append(tags, [2]string{"service", key.service})
			}
			schema.AppendLineProtocol(&lineProtocol, "supervisor", relation, tags, groups[key], ts)
		}
		lineBytes := lineProtocol.Len()
		dbStart := time.Now()
		if lineProtocol.Len() > 0 && db != nil {
			db.write(ctx, lineProtocol.Bytes())
		}
		dbDuration := time.Since(dbStart)
		phase := "pulse"
		if isHeartbeat {
			phase = "heartbeat"
		}
		slog.Debug("profiling", "engine", "broker", "phase", phase, "duration", brokerDuration, "detail", fmt.Sprintf("transmitted [%d] msgs", txCount))
		slog.Debug("profiling", "engine", "database", "phase", phase, "duration", dbDuration, "detail", fmt.Sprintf("transmitted [%d] bytes", lineBytes))
		slog.Debug("profiling", "engine", "publish", "phase", phase, "duration", time.Since(pulseStart), "detail", fmt.Sprintf("transmitted [%d] bytes", txBytes))
	})
	if err != nil && !errors.Is(err, context.Canceled) && !errors.Is(err, context.DeadlineExceeded) {
		slog.Error("state", "engine", "publish", "phase", "run", "detail", fmt.Sprintf("publish loop run failed with [%v]", err))
	}
}

// Wake is called by the display when it detects that this process has been suspended (a laptop sleep), which is the earliest
// signal that the broker session may be dead. Without it the stream loop waits on the keepalive to notice, and the screen holds
// values that stopped updating at suspend until then.
func Wake() {
	wakeMutex.RLock()
	handler := wakeHandler
	wakeMutex.RUnlock()
	if handler != nil {
		handler()
	}
}

type hostReconcile struct {
	host     string
	started  time.Time
	deadline time.Time
}

const (
	hostStatusOnline  = "online"
	hostStatusOffline = "offline"
)

var (
	reconcileGrace  = 10 * time.Second
	hostStatusMutex sync.RWMutex
	hostStatus      map[string]bool
	wakeMutex       sync.RWMutex
	wakeHandler     func()
)

func init() {
	hostStatus = make(map[string]bool)
}

func storeWakeHandler(handler func()) {
	wakeMutex.Lock()
	wakeHandler = handler
	wakeMutex.Unlock()
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
