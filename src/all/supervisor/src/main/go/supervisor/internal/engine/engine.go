package engine

import (
	"context"
	"encoding/json"
	"errors"
	"strconv"
	"strings"
	"supervisor/internal/config"
	"supervisor/internal/metric"
	"supervisor/internal/probe"
	"supervisor/internal/scribe"
	"sync"
	"sync/atomic"
	"time"

	mqtt "github.com/eclipse/paho.mqtt.golang"
)

// RunListeningProbesLoop runs local probes and writes directly to the display cache.
//
// Flow:
//  1. Seed a nil record for every listener ID and for its dependencies.
//  2. Create the probes, filtered to those metrics.
//  3. Run until the context ends.
//
// Notes:
//   - The cache is shared with the display.
//   - Stale probe state is dropped by syncStatsFields, and prevCPUStats by active container ID.
//   - A missing service is evicted to nil then deleted, which re-indexes the service slots.
//   - No Purge is needed here, because local probes track staleness themselves.
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
	createStart := time.Now()
	if err := probe.Create(configPath, cache, periods); err != nil {
		scribe.Engine("state", "probes").Error("create", createStart, "listening probes loop failed with [%v]", err)
		return
	}
	runStart := time.Now()
	if err := probe.Run(ctx, nil); err != nil && !errors.Is(err, context.Canceled) && !errors.Is(err, context.DeadlineExceeded) {
		scribe.Engine("state", "probes").Error("run", runStart, "listening probes loop failed with [%v]", err)
	}
}

// RunListeningStreamLoop subscribes to the broker and writes the metrics every other host publishes into the display cache.
// It is the watch side of the service, and the lifecycle contract below is the reference for both sides.
//
// On connect:
//  1. Forget the host status, the subscribed topics and any pending reconcile, none of which survive a new session.
//  2. Subscribe to every topic the cache already holds, in one packet.
//  3. Subscribe to service discovery and to host status.
//  4. Refresh the display, so a reconnect cannot leave the screen on the nils it slept with.
//
// On a data message:
//  1. Ignore a topic the subscribed map does not hold, counting it as dropped.
//  2. Remove the service on an empty or nil pulse payload, being the tombstone a live host publishes when a service departs.
//  3. Revive an offline host when the payload was published after the offline, resubscribing it as a transition would.
//  4. Ignore anything else from an offline host, which is how a departing host's own tombstones are left unread.
//  5. Stamp and store everything else.
//
// On host status, gated on the prior status so each fires once per transition rather than once per heartbeat:
//   - online, first since the connect: schedule a reconcile against the connect, because the retained flood is already in flight.
//   - online, later: schedule a reconcile against now, and resubscribe the host to force the broker to redeliver it.
//   - online, unchanged: nothing, this is the heartbeat re-asserting a status already held.
//   - offline: evict every service to nil, store nil for the host metrics and cancel any pending reconcile, which keeps
//     the slots for repopulation and stops a reap firing against a host that has stopped answering.
//
// On the purge tick:
//  1. Evict the records of a silent host to nil, then delete a service whose records have stayed nil.
//  2. Run any reconcile whose grace has expired, removing only the services nothing has refreshed since its cutoff.
//  3. Resync the subscribed topics against the cache, subscribing what is missing and dropping what no longer exists.
//  4. Report the traffic and the census, being the two lines that make a steady state auditable without a debugger.
//
// Notes:
//   - The reconcile cutoff is the connect for the first transition and the transition itself later, because the retained
//     flood is queued ahead of the retained status and would otherwise read as a host that had gone silent.
//   - A reconcile is only ever scheduled beside a redelivery, whether forced by a resubscribe or already in flight from
//     the connect. Without one, a service that simply had nothing to publish inside the grace would be reaped alive.
//   - Discovery proves a host alive exactly as data does, so a service that appears while its host is wrongly offline
//     registers immediately instead of waiting for the next heartbeat to carry its name again.
//   - Reaping is keyed by service name, never by slot, so a service that moves slot between scheduling and running is safe.
//   - A subscribe that fails rolls its topics back out of the map, which the resync then retries.
//   - The display is refreshed on connect and after a reconcile that reaped, never per host and never per heartbeat.
//   - An unknown host counts as online, so a watch started before its first status message still renders.
func RunListeningStreamLoop(ctx context.Context, configPath string, cache *metric.RecordCache, periods config.Periods) {
	for host, ids := range cache.ListenerIDs() {
		for _, id := range ids {
			record := metric.NewRecord(metric.NewNilValue())
			cache.Store(metric.NewServiceSchemaRecordGUID(id, host, 0), &record)
		}
	}
	var rxCount atomic.Int64
	var dropCount atomic.Int64
	var subscribedMutex sync.Mutex
	subscribed := make(map[string]metric.RecordGUID)
	var reconcileMutex sync.Mutex
	reconciles := make(map[string]hostReconcile)
	connected := time.Now()
	reconcileDelay := max(time.Duration(2*periods.PulseMillis)*time.Millisecond, reconcileGrace)
	scheduleReconcile := func(hostName string, fromConnect bool) {
		reconcileMutex.Lock()
		pending := reconciles[hostName]
		pending.host = hostName
		pending.started = time.Now()
		if fromConnect {
			pending.started = connected
		}
		pending.deadline = time.Now().Add(reconcileDelay)
		reconciles[hostName] = pending
		reconcileMutex.Unlock()
	}
	removeService := func(guid metric.RecordGUID) {
		removeStart := time.Now()
		cache.Evict(guid.Host, guid.ServiceName)
		if cache.Delete(guid.Host, guid.ServiceName) {
			scribe.Engine("state", "subscribe").Info("tombstone", removeStart, "host [%s] service [%s] removed by an empty payload", guid.Host, guid.ServiceName)
		}
	}
	var resubscribeHost func(client mqtt.Client, hostName string) int
	proveOnline := func(client mqtt.Client, hostName string, value metric.ValueData) bool {
		if isHostOnline(hostName) {
			return true
		}
		if value.Pulse == nil || value.Timestamp <= hostOfflineAt(hostName) {
			return false
		}
		reviveStart := time.Now()
		storeHostStatus(hostName, true)
		scheduleReconcile(hostName, false)
		topics := resubscribeHost(client, hostName)
		scribe.Engine("state", "broker").Warn("revive", reviveStart, "host [%s] status [online] proven by data published after the offline resubscribed [%d] topics reconcile in [%d] ms", hostName, topics, reconcileDelay.Milliseconds())
		return true
	}
	onData := func(client mqtt.Client, msg mqtt.Message) {
		subscribedMutex.Lock()
		guid, known := subscribed[msg.Topic()]
		subscribedMutex.Unlock()
		if !known {
			dropCount.Add(1)
			return
		}
		online := isHostOnline(guid.Host)
		if len(msg.Payload()) == 0 {
			if !online {
				dropCount.Add(1)
				return
			}
			rxCount.Add(1)
			removeService(guid)
			return
		}
		var value metric.ValueData
		streamStart := time.Now()
		if err := json.Unmarshal(msg.Payload(), &value); err != nil {
			dropCount.Add(1)
			scribe.Engine("state", "subscribe").Error("stream", streamStart, "unmarshal failed on [%s] with [%v]", msg.Topic(), err)
			return
		}
		if !online && !proveOnline(client, guid.Host, value) {
			dropCount.Add(1)
			return
		}
		rxCount.Add(1)
		if value.Pulse == nil {
			removeService(guid)
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
		if len(filters) == 0 {
			return 0
		}
		subscribeStart := time.Now()
		token := client.SubscribeMultiple(filters, onData)
		go func() {
			if token.WaitTimeout(brokerTimeout) && token.Error() == nil {
				return
			}
			subscribedMutex.Lock()
			for topic := range filters {
				delete(subscribed, topic)
			}
			subscribedMutex.Unlock()
			scribe.Engine("state", "subscribe").Error("subscribe", subscribeStart, "dropped [%d] topics failed with [%v], retrying on the next resync", len(filters), token.Error())
		}()
		return len(filters)
	}
	resyncTopics := func(client mqtt.Client) (int, int) {
		bindings := cache.Topics()
		holds := make(map[string]struct{}, len(bindings))
		for _, b := range bindings {
			holds[b.Topic] = struct{}{}
		}
		var missing []metric.TopicBinding
		var stale []string
		subscribedMutex.Lock()
		for _, b := range bindings {
			if _, exists := subscribed[b.Topic]; !exists {
				missing = append(missing, b)
			}
		}
		for topic := range subscribed {
			if _, exists := holds[topic]; !exists {
				stale = append(stale, topic)
				delete(subscribed, topic)
			}
		}
		subscribedMutex.Unlock()
		if len(stale) > 0 {
			client.Unsubscribe(stale...)
		}
		return subscribeTopics(client, missing), len(stale)
	}
	resubscribeHost = func(client mqtt.Client, hostName string) int {
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
		clear(hostOffline)
		hostStatusMutex.Unlock()
		subscribedMutex.Lock()
		clear(subscribed)
		subscribedMutex.Unlock()
		reconcileMutex.Lock()
		clear(reconciles)
		connected = time.Now()
		reconcileMutex.Unlock()
		topics := subscribeTopics(client, cache.Topics())
		client.Subscribe("supervisor/+/data/service/+/name", 1, func(client mqtt.Client, msg mqtt.Message) {
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
			if !proveOnline(client, hostName, value) {
				dropCount.Add(1)
				return
			}
			rxCount.Add(1)
			registerStart := time.Now()
			if bindings := cache.RegisterService(hostName, serviceName, false); len(bindings) > 0 {
				subscribeTopics(client, bindings)
				scribe.Engine("state", "subscribe").Info("register", registerStart, "host [%s] service [%s] subscribed [%d] topics", hostName, serviceName, len(bindings))
			}
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
			statusStart := time.Now()
			payload := strings.TrimSpace(string(msg.Payload()))
			rxCount.Add(1)
			hostStatusMutex.RLock()
			wasOnline, known := hostStatus[hostName]
			hostStatusMutex.RUnlock()
			switch payload {
			case hostStatusOnline:
				storeHostStatus(hostName, true)
				if known && wasOnline {
					scribe.Engine("state", "broker").Debug("status", statusStart, "host [%s] status [online] heartbeat [no-op] already online with nothing to reconcile", hostName)
					return
				}
				reconcileMutex.Lock()
				_, restarted := reconciles[hostName]
				reconcileMutex.Unlock()
				trigger := "connect"
				topics := 0
				if restarted {
					trigger = "restart"
				}
				scheduleReconcile(hostName, !restarted)
				if restarted {
					topics = resubscribeHost(client, hostName)
				}
				scribe.Engine("state", "broker").Info("status", statusStart, "host [%s] status [online] trigger [%s] resubscribed [%d] topics reconcile in [%d] ms", hostName, trigger, topics, reconcileDelay.Milliseconds())
			case hostStatusOffline, "":
				storeHostStatus(hostName, false)
				if known && !wasOnline {
					scribe.Engine("state", "broker").Debug("status", statusStart, "host [%s] status [offline] heartbeat [no-op] already offline with nothing to evict", hostName)
					return
				}
				evicted := cache.Services(hostName)
				for _, svc := range evicted {
					cache.Evict(hostName, svc)
				}
				reconcileMutex.Lock()
				pending := reconciles[hostName]
				pending.deadline = time.Time{}
				reconciles[hostName] = pending
				reconcileMutex.Unlock()
				for _, id := range metric.GetIDsByKind([]metric.MetricKind{metric.MetricKindHost}) {
					record := metric.NewRecord(metric.NewNilValue())
					cache.Store(metric.NewRecordGUID(id, hostName), &record)
				}
				scribe.Engine("state", "broker").Warn("status", statusStart, "host [%s] status [offline] evicted [%d] services", hostName, len(evicted))
			default:
				scribe.Engine("state", "broker").Error("status", statusStart, "host [%s] unknown payload [%s]", hostName, payload)
			}
		})
		cache.Refresh()
		scribe.Engine("state", "subscribe").Info("connect", connectStart, "subscribed [%d] topics across [%d] hosts holding [%d] records", topics, len(cache.Hosts()), cache.Size())
	}
	clientStart := time.Now()
	client, err := brokerConnect(configPath, onConnect, "", "")
	if err != nil {
		scribe.Engine("state", "subscribe").Error("connect", clientStart, "listening stream loop failed with [%v]", err)
		return
	}
	defer client.Disconnect(250)
	cache.SubscribeWake(&brokerWakeListener{onWake: func() { brokerRevive(ctx, client) }})
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
			evicted, deleted := cache.Purge(periods.HeartbeatSecs + 10*periods.PulseMillis/1000)
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
				if len(services) == 0 {
					scribe.Engine("state", "subscribe").Debug("reconcile", reconcileStart, "host [%s] reaped [0] services after [%d] ms, every service refreshed itself", pending.host, time.Since(pending.started).Milliseconds())
					continue
				}
				cache.Refresh()
				scribe.Engine("state", "subscribe").Info("reconcile", reconcileStart, "host [%s] reaped [%d] services after [%d] ms [%s]", pending.host, len(services), time.Since(pending.started).Milliseconds(), strings.Join(services, ","))
			}
			resyncStart := time.Now()
			if added, dropped := resyncTopics(client); added > 0 || dropped > 0 {
				scribe.Engine("state", "subscribe").Info("resync", resyncStart, "subscribed [%d] topics unsubscribed [%d] topics to match the cache", added, dropped)
			}
			rx := rxCount.Swap(0)
			drops := dropCount.Swap(0)
			rate := int64(0)
			if secs := int64(purgeInterval.Seconds()); secs > 0 {
				rate = rx / secs
			}
			scribe.Engine("profiling", "subscribe").Debug("purge", purgeStart, "received [%d] msgs at [%d] msg/s dropped [%d] msgs evicted [%d] deleted [%d] records", rx, rate, drops, evicted, deleted)
			censusStart := time.Now()
			online := 0
			services := 0
			for hostName := range cache.Hosts() {
				if isHostOnline(hostName) {
					online++
				}
				services += len(cache.Services(hostName))
			}
			subscribedMutex.Lock()
			topics := len(subscribed)
			subscribedMutex.Unlock()
			reconcileMutex.Lock()
			pending := 0
			for _, reconcile := range reconciles {
				if !reconcile.deadline.IsZero() {
					pending++
				}
			}
			reconcileMutex.Unlock()
			scribe.Engine("profiling", "subscribe").Debug("census", censusStart, "hosts [%d] online [%d] services [%d] subscribed [%d] topics reconciling [%d] hosts holding [%d] records", len(cache.Hosts()), online, services, topics, pending, cache.Size())
		}
	}
}

// RunAllProbesOnce runs every probe for a single pulse cycle, then exits.
//
// Flow:
//  1. Seed a nil record for every metric ID.
//  2. Create the probes with every metric registered, and with no trend tracking.
//  3. Run once, under a timeout of three pulses, being 3s by default.
//
// Notes:
//   - The cache belongs to the caller and is discarded on return, so nothing here needs removing.
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
	createStart := time.Now()
	if err := probe.Create(configPath, cache, periods); err != nil {
		scribe.Engine("state", "probes").Error("create", createStart, "all probes once failed with [%v]", err)
		return
	}
	timeout := time.Duration(3*periods.PulseMillis) * time.Millisecond
	ctx, cancel := context.WithTimeout(ctx, timeout)
	defer cancel()
	runStart := time.Now()
	err := probe.Run(ctx, nil)
	if err != nil && !errors.Is(err, context.DeadlineExceeded) {
		scribe.Engine("state", "probes").Error("run", runStart, "all probes once failed with [%v]", err)
	}
}

type serviceKey struct {
	host    string
	service string
}

// RunAllProbesPublishLoop runs every probe locally and publishes what they collect to the broker and to the database.
// It is the serve side of the service, and RunListeningStreamLoop above holds the other half of the lifecycle contract.
//
// On connect:
//  1. Subscribe to this host's own retained service names, and register each one, which is how a service survives a crash.
//  2. Subscribe to the command topic.
//  3. On a reconnect, read the retained status back, and re-assert it online, forcing a full republish when it had lapsed.
//
// On each pulse:
//  1. Publish the online status and every record on a heartbeat, or only the records that changed otherwise.
//  2. Publish a record holding a pulse to its own retained topic.
//  3. Publish a record holding none as nil, then as an empty payload, then delete it, which tombstones it on the broker.
//  4. Group the numeric metrics by host and service, and write them to the database as line protocol.
//
// On shutdown, which a signal reaches but a kill does not:
//  1. Publish the offline status, which is what the last will would otherwise have published.
//  2. Publish an empty payload for every retained topic.
//
// Notes:
//   - The service name topic must be retained, being the only breadcrumb a crash leaves behind. Nothing publishes the
//     tombstones after a kill, so the next process rediscovers the service from that name, finds it absent from docker,
//     and removes it, which is what finally clears the broker. See supervisor/CLAUDE.md.
//   - The cache belongs to this loop alone, and Take drains the changed set each pulse.
//   - A service that leaves docker or the config is evicted to nil then deleted, and the deletes listener empties its topics.
//   - A record reaching the pulse without a pulse value is tombstoned there too, covering an interleave with the removal above.
func RunAllProbesPublishLoop(ctx context.Context, configPath string, cache *metric.RecordCache, periods config.Periods) {
	for _, id := range metric.GetIDs() {
		record := metric.NewRecord(metric.NewNilValue())
		cache.Store(metric.NewServiceSchemaRecordGUID(id, config.Load(configPath).Host(), 0), &record)
	}
	createStart := time.Now()
	if err := probe.Create(configPath, cache, periods); err != nil {
		scribe.Engine("state", "publish").Error("create", createStart, "publish loop failed with [%v]", err)
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
				registerStart := time.Now()
				if bindings := cache.RegisterService(hostName, serviceName, true); len(bindings) > 0 {
					scribe.Engine("state", "publish").Info("register", registerStart, "host [%s] service [%s] rediscovered [%d] topics", hostName, serviceName, len(bindings))
				}
			}
		})
		client.Subscribe(commandTopic, 1, func(_ mqtt.Client, msg mqtt.Message) {
			commandStart := time.Now()
			tokens := strings.Split(msg.Topic(), "/")
			if len(tokens) < 5 || tokens[1] == "" || tokens[4] == "" {
				return
			}

			// TODO: Implement command handling

			scribe.Engine("command", "broker").Debug("command", commandStart, "host [%s] service [%s] payload [%s]", tokens[1], tokens[4], string(msg.Payload()))
		})
		if hasConnected.Swap(true) {
			reconnectStart := time.Now()
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
			client.Publish(statusTopic, 1, true, hostStatusOnline).WaitTimeout(brokerTimeout)
			scribe.Engine("state", "publish").Info("reconnect", reconnectStart, "host [%s] status [online] re-asserted after reading back [%s] republish [%v]", hostName, seen, forceRepublish.Load())
		}
	}
	clientStart := time.Now()
	client, err := brokerConnect(configPath, onConnect, statusTopic, hostStatusOffline)
	if err != nil {
		scribe.Engine("state", "broker").Error("connect", clientStart, "publish loop failed with [%v]", err)
		return
	}
	defer func() {
		shutdownStart := time.Now()
		client.Publish(statusTopic, 1, true, hostStatusOffline).WaitTimeout(2 * time.Second)
		tombstoned := 0
		cache.Records(func(_ metric.RecordGUID, record *metric.Record) {
			if record.Topic != "" {
				client.Publish(record.Topic, 0, true, "")
				tombstoned++
			}
		})
		client.Disconnect(2500)
		scribe.Engine("state", "broker").Info("shutdown", shutdownStart, "host [%s] status [%s] tombstoned [%d] topics", hostName, hostStatusOffline, tombstoned)
	}()
	cache.SubscribeDeletes(&brokerPublishDeletesListener{client: client})
	var db *databaseClient
	if config.Load(configPath).Database() != "" {
		var dbErr error
		databaseStart := time.Now()
		db, dbErr = databaseConnect(configPath)
		if dbErr != nil {
			scribe.Engine("state", "database").Error("connect", databaseStart, "publish loop failed with [%v]", dbErr)
		} else {
			defer db.close()
		}
	}
	batch := newDatabaseBatch()
	var toDelete []serviceKey
	deleted := make(map[serviceKey]bool)
	publishStart := time.Now()
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
		batch.reset()
		toDelete = toDelete[:0]
		clear(deleted)
		process := func(guid metric.RecordGUID, record *metric.Record) {
			processStart := time.Now()
			if record.Topic != "" {
				if record.Value.Pulse != nil {
					if payload, jsonErr := json.Marshal(record.Value); jsonErr == nil {
						client.Publish(record.Topic, 0, true, payload)
						txCount++
						txBytes += len(payload)
					} else {
						scribe.Engine("state", "publish").Warn("marshal", processStart, "failed on [%s] with [%v]", record.Topic, jsonErr)
					}
				} else if guid.ServiceName != metric.ServiceNameUnset && !strings.HasPrefix(guid.ServiceName, metric.ServiceNameSchema) {
					if payload, jsonErr := json.Marshal(record.Value); jsonErr == nil {
						client.Publish(record.Topic, 0, true, payload)
						txCount++
						txBytes += len(payload)
					}
					client.Publish(record.Topic, 0, true, "")
					txCount++
					toDelete = append(toDelete, serviceKey{host: guid.Host, service: guid.ServiceName})
				}
			}
			batch.add(guid, record)
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
		lineBytes := batch.render(strconv.FormatInt(time.Now().UnixNano(), 10))
		dbStart := time.Now()
		if lineBytes > 0 && db != nil {
			db.write(ctx, batch.protocol.Bytes())
		}
		dbDuration := time.Since(dbStart)
		phase := "pulse"
		if isHeartbeat {
			phase = "heartbeat"
		}
		scribe.Engine("profiling", "publish").Debug(phase, pulseStart, "broker [%d] msgs [%d] bytes in [%d] ms database [%d] bytes in [%d] ms", txCount, txBytes, brokerDuration.Milliseconds(), lineBytes, dbDuration.Milliseconds())
	})
	if err != nil && !errors.Is(err, context.Canceled) && !errors.Is(err, context.DeadlineExceeded) {
		scribe.Engine("state", "publish").Error("run", publishStart, "publish loop failed with [%v]", err)
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
	hostOffline     map[string]int64
)

func init() {
	hostStatus = make(map[string]bool)
	hostOffline = make(map[string]int64)
}

func isHostOnline(hostName string) bool {
	hostStatusMutex.RLock()
	online, known := hostStatus[hostName]
	hostStatusMutex.RUnlock()
	return !known || online
}

func storeHostStatus(hostName string, online bool) {
	hostStatusMutex.Lock()
	if !online {
		hostOffline[hostName] = time.Now().Unix()
	}
	hostStatus[hostName] = online
	hostStatusMutex.Unlock()
}

func hostOfflineAt(hostName string) int64 {
	hostStatusMutex.RLock()
	at := hostOffline[hostName]
	hostStatusMutex.RUnlock()
	return at
}
