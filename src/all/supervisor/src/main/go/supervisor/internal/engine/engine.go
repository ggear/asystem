package engine

import (
	"context"
	"encoding/json"
	"errors"
	"sort"
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
		scribe.Log(scribe.SourceEngine, scribe.SubjectNone, scribe.ActionStart).Errorf("faulting", createStart, "[%s] loop with [%v]", loopListeningProbes, err)
		return
	}
	runStart := time.Now()
	if err := probe.RunPoll(ctx, nil); err != nil && !errors.Is(err, context.Canceled) && !errors.Is(err, context.DeadlineExceeded) {
		scribe.Log(scribe.SourceEngine, scribe.SubjectNone, scribe.ActionStop).Errorf("faulting", runStart, "[%s] loop with [%v]", loopListeningProbes, err)
	}
}

// RunListeningStreamLoop subscribes to the broker and writes the metrics every other host publishes into the display cache.
// It is the watch side of the service, and the lifecycle contract below is the reference for both sides.
//
// On connect:
//  1. Forget the host status, the subscribed topics and any pending reconcile, none of which survive a new session.
//  2. Subscribe to every topic the cache already holds, in one packet.
//  3. Subscribe to service discovery and to host status, tracking both so a refused subscribe is retried by the resync.
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
//  4. Restore either wildcard subscription the connect failed to establish, without which nothing is ever discovered.
//  5. Revive a client paho has abandoned, being a session neither connected nor reconnecting.
//  6. Resubscribe everything after five silent ticks, being a session the broker acknowledged but never feeds.
//  7. Report the traffic and the census, being the two lines that make a steady state auditable without a debugger.
//
// Notes:
//   - The reconcile cutoff is the connect for the first transition and the transition itself later, because the retained
//     flood is queued ahead of the retained status and would otherwise read as a host that had gone silent.
//   - A reconcile is only ever scheduled beside a redelivery, whether forced by a resubscribe or already in flight from
//     the connect. Without one, a service that simply had nothing to publish inside the grace would be reaped alive.
//   - Discovery proves a host alive exactly as data does, so a service that appears while its host is wrongly offline
//     registers immediately instead of waiting for the next heartbeat to carry its name again.
//   - A reconcile that would reap every service of a host holds them once instead, resubscribes the host and reschedules,
//     because nothing refreshing at all is evidence the redelivery was lost rather than that every service departed.
//   - Reaping is keyed by service name, never by slot, so a service that moves slot between scheduling and running is safe.
//   - A subscribe is refused either by its token failing or by a SUBACK return code above the maximum QoS, which paho
//     reports through Result rather than through Error, so both are read and both roll their topics back out of the map.
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
	var subscribedMu sync.Mutex
	subscribed := make(map[string]metric.RecordGUID)
	var wildcardMu sync.Mutex
	wildcards := make(map[string]struct{})
	var reconcileMu sync.Mutex
	reconciles := make(map[string]hostReconcile)
	connected := config.NowIncludingSuspend()
	reconcileDelay := max(time.Duration(2*periods.PulseMillis)*time.Millisecond, reconcileGrace)
	scheduleReconcile := func(hostName string, fromConnect bool) {
		reconcileMu.Lock()
		pending := reconciles[hostName]
		pending.host = hostName
		pending.retried = false
		pending.started = config.NowIncludingSuspend()
		if fromConnect {
			pending.started = connected
		}
		pending.deadline = time.Now().Add(reconcileDelay)
		reconciles[hostName] = pending
		reconcileMu.Unlock()
	}
	removeService := func(guid metric.RecordGUID) {
		if guid.ServiceName == metric.ServiceNameUnset {
			return
		}
		removeStart := time.Now()
		cache.Evict(guid.Host, guid.ServiceName)
		if cache.Delete(guid.Host, guid.ServiceName) {
			scribe.Log(scribe.SourceEngine, scribe.SubjectService(guid.ServiceName), scribe.ActionRemove).Infof("removals", removeStart, "[%s] removed; empty payload", guid.Host)
		}
	}
	var resubscribeHost func(client mqtt.Client, hostName string) int
	var resubscribeAll func(client mqtt.Client) (int, int)
	proveOnline := func(client mqtt.Client, hostName string, value metric.ValueData) bool {
		if assertHostOnline(hostName) {
			return true
		}
		if value.Pulse == nil || value.Timestamp <= hostOfflineAt(hostName) {
			return false
		}
		reviveStart := time.Now()
		storeHostStatus(hostName, true)
		scheduleReconcile(hostName, false)
		topics := resubscribeHost(client, hostName)
		scribe.Log(scribe.SourceEngine, scribe.SubjectHost(hostName), scribe.ActionConnect).Infof("observed", reviveStart, "[online] resub [%2d], retry [%2d]s", topics, int64(reconcileDelay.Seconds()))
		return true
	}
	onData := func(client mqtt.Client, msg mqtt.Message) {
		subscribedMu.Lock()
		guid, known := subscribed[msg.Topic()]
		subscribedMu.Unlock()
		if !known {
			dropCount.Add(1)
			return
		}
		online := assertHostOnline(guid.Host)
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
			scribe.Log(scribe.SourceEngine, scribe.SubjectTopic(msg.Topic()), scribe.ActionSubscribe).Errorf("received", streamStart, "[unmarshal] [%v]", err)
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
		subscribedMu.Lock()
		for _, b := range bindings {
			if _, exists := subscribed[b.Topic]; exists {
				continue
			}
			subscribed[b.Topic] = b.GUID
			filters[b.Topic] = 0
		}
		subscribedMu.Unlock()
		if len(filters) == 0 {
			return 0
		}
		subscribeStart := time.Now()
		token := client.SubscribeMultiple(filters, onData)
		go func() {
			refused, reason := subscribeRefused(token, filters)
			if len(refused) == 0 {
				return
			}
			subscribedMu.Lock()
			for _, topic := range refused {
				delete(subscribed, topic)
			}
			subscribedMu.Unlock()
			scribe.Log(scribe.SourceEngine, scribe.SubjectNone, scribe.ActionSubscribe).Errorf("rollback", subscribeStart, "[%2d]/[%2d] topics refused: %s", len(refused), len(filters), reason)
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
		subscribedMu.Lock()
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
		subscribedMu.Unlock()
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
		subscribedMu.Lock()
		for _, b := range bindings {
			delete(subscribed, b.Topic)
			topics = append(topics, b.Topic)
		}
		subscribedMu.Unlock()
		if len(topics) > 0 {
			client.Unsubscribe(topics...)
		}
		return subscribeTopics(client, bindings)
	}
	onDiscovery := func(client mqtt.Client, msg mqtt.Message) {
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
			scribe.Log(scribe.SourceEngine, scribe.SubjectService(serviceName), scribe.ActionRegister).Infof("register", registerStart, "[%s] [%3d] topics added", hostName, len(bindings))
		}
		value.Timestamp = time.Now().Unix()
		record := metric.NewRecord(value)
		cache.Store(metric.NewServiceRecordGUID(metric.MetricServiceName, hostName, serviceName), &record)
	}
	onStatus := func(client mqtt.Client, msg mqtt.Message) {
		tokens := strings.Split(msg.Topic(), "/")
		if len(tokens) < 3 || tokens[1] == "" {
			return
		}
		hostName := tokens[1]
		statusStart := time.Now()
		payload := strings.TrimSpace(string(msg.Payload()))
		rxCount.Add(1)
		hostStatusMu.RLock()
		wasOnline, known := hostStatus[hostName]
		hostStatusMu.RUnlock()
		switch payload {
		case hostStatusOnline:
			storeHostStatus(hostName, true)
			if known && wasOnline {
				scribe.Log(scribe.SourceEngine, scribe.SubjectHost(hostName), scribe.ActionCensus).Debugf("observed", statusStart, "[online], with heartbeat [no-op]")
				return
			}
			reconcileMu.Lock()
			_, restarted := reconciles[hostName]
			reconcileMu.Unlock()
			trigger := "connect"
			topics := 0
			if restarted {
				trigger = "restart"
			}
			scheduleReconcile(hostName, !restarted)
			if restarted {
				topics = resubscribeHost(client, hostName)
			}
			scribe.Log(scribe.SourceEngine, scribe.SubjectHost(hostName), scribe.ActionConnect).Infof("observed", statusStart, "[online], triggered by [%s]", trigger)
			scribe.Log(scribe.SourceEngine, scribe.SubjectHost(hostName), scribe.ActionConnect).Infof("observed", statusStart, "[%3d] topics, reconcile [%4d] s", topics, int64(reconcileDelay.Seconds()))
		case hostStatusOffline, "":
			storeHostStatus(hostName, false)
			if known && !wasOnline {
				scribe.Log(scribe.SourceEngine, scribe.SubjectHost(hostName), scribe.ActionCensus).Debugf("observed", statusStart, "[offline] with heartbeat [no-op]")
				return
			}
			evicted := cache.Services(hostName)
			for _, svc := range evicted {
				cache.Evict(hostName, svc)
			}
			reconcileMu.Lock()
			pending := reconciles[hostName]
			pending.deadline = time.Time{}
			reconciles[hostName] = pending
			reconcileMu.Unlock()
			for _, id := range metric.GetIDsByKind([]metric.MetricKind{metric.MetricKindHost}) {
				record := metric.NewRecord(metric.NewNilValue())
				cache.Store(metric.NewRecordGUID(id, hostName), &record)
			}
			scribe.Log(scribe.SourceEngine, scribe.SubjectHost(hostName), scribe.ActionDisconnect).Warnf("observed", statusStart, "[offline] evicted [%3d] services", len(evicted))
		default:
			scribe.Log(scribe.SourceEngine, scribe.SubjectHost(hostName), scribe.ActionSubscribe).Errorf("observed", statusStart, "[%s] unknown payload", payload)
		}
	}
	wildcardHandlers := map[string]mqtt.MessageHandler{
		topicDiscovery: onDiscovery,
		topicStatus:    onStatus,
	}
	subscribeWildcards := func(client mqtt.Client) int {
		var pending []string
		wildcardMu.Lock()
		for topic := range wildcardHandlers {
			if _, exists := wildcards[topic]; exists {
				continue
			}
			wildcards[topic] = struct{}{}
			pending = append(pending, topic)
		}
		wildcardMu.Unlock()
		sort.Strings(pending)
		for _, topic := range pending {
			subscribeStart := time.Now()
			token := client.Subscribe(topic, 1, wildcardHandlers[topic])
			go func(topic string, token mqtt.Token) {
				refused, reason := subscribeRefused(token, map[string]byte{topic: 1})
				if len(refused) == 0 {
					return
				}
				wildcardMu.Lock()
				delete(wildcards, topic)
				wildcardMu.Unlock()
				scribe.Log(scribe.SourceEngine, scribe.SubjectTopic(topic), scribe.ActionSubscribe).Errorf("rollback", subscribeStart, "[%s] wildcard refused: %s", topic, reason)
			}(topic, token)
		}
		return len(pending)
	}
	resubscribeAll = func(client mqtt.Client) (int, int) {
		subscribedMu.Lock()
		clear(subscribed)
		subscribedMu.Unlock()
		wildcardMu.Lock()
		clear(wildcards)
		wildcardMu.Unlock()
		return subscribeTopics(client, cache.Topics()), subscribeWildcards(client)
	}
	onConnect := func(client mqtt.Client) {
		connectStart := time.Now()
		hostStatusMu.Lock()
		clear(hostStatus)
		clear(hostOffline)
		hostStatusMu.Unlock()
		subscribedMu.Lock()
		clear(subscribed)
		subscribedMu.Unlock()
		wildcardMu.Lock()
		clear(wildcards)
		wildcardMu.Unlock()
		reconcileMu.Lock()
		clear(reconciles)
		connected = config.NowIncludingSuspend()
		reconcileMu.Unlock()
		topics := subscribeTopics(client, cache.Topics())
		listens := subscribeWildcards(client)
		cache.Refresh()
		scribe.Log(scribe.SourceEngine, scribe.SubjectHost(""), scribe.ActionSubscribe).Infof("attached", connectStart, "[%4d] topics, [%5d] wildcards", topics, listens)
		scribe.Log(scribe.SourceEngine, scribe.SubjectHost(""), scribe.ActionSubscribe).Infof("retained", connectStart, "[%6d] hosts, [%6d] records", len(cache.Hosts()), cache.Size())
	}
	clientStart := time.Now()
	client, err := brokerConnect(configPath, onConnect, "", "")
	if err != nil {
		scribe.Log(scribe.SourceEngine, scribe.SubjectNone, scribe.ActionStop).Errorf("faulting", clientStart, "[%s] loop: [%v]", loopListeningStream, err)
		return
	}
	defer client.Disconnect(250)
	cache.SubscribeWake(&watchWakeListener{onWake: func(frozen time.Duration) { brokerRevive(ctx, client, frozen) }})
	cache.SubscribeAttach(&watchAttachListener{onAttach: func() {
		attachStart := time.Now()
		if added, dropped := resyncTopics(client); added > 0 || dropped > 0 {
			scribe.Log(scribe.SourceEngine, scribe.SubjectHost(""), scribe.ActionSubscribe).Infof("attached", attachStart, "[%3d] subscribed, [%3d] removals", added, dropped)
		}
	}})
	cache.SubscribeDeletes(&watchDeletesListener{
		client: client,
		onDelete: func(topic string) {
			subscribedMu.Lock()
			delete(subscribed, topic)
			subscribedMu.Unlock()
		},
	})
	purgeInterval := time.Duration(max(periods.PulseMillis+1000, 2000)) * time.Millisecond
	silent := 0
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
			reconcileMu.Lock()
			for hostName, pending := range reconciles {
				if pending.deadline.IsZero() || now.Before(pending.deadline) {
					continue
				}
				due = append(due, pending)
				pending.deadline = time.Time{}
				reconciles[hostName] = pending
			}
			reconcileMu.Unlock()
			for _, pending := range due {
				reconcileStart := time.Now()
				services := cache.ServicesBefore(pending.host, pending.started.Unix())
				if len(services) > 0 && len(services) == len(cache.Services(pending.host)) && !pending.retried {
					reconcileMu.Lock()
					pending.retried = true
					pending.deadline = time.Now().Add(reconcileDelay)
					reconciles[pending.host] = pending
					reconcileMu.Unlock()
					topics := resubscribeHost(client, pending.host)
					scribe.Log(scribe.SourceEngine, scribe.SubjectHost(pending.host), scribe.ActionReconcile).Warnf("deferred", reconcileStart, "[%3d] services after [%7d] s", len(services), int64(config.SinceIncludingSuspend(pending.started).Seconds()))
					scribe.Log(scribe.SourceEngine, scribe.SubjectHost(pending.host), scribe.ActionReconcile).Warnf("deferred", reconcileStart, "[%5d] topics resubbed on retry", topics)
					continue
				}
				for _, service := range services {
					cache.Evict(pending.host, service)
					cache.Delete(pending.host, service)
				}
				if len(services) == 0 {
					scribe.Log(scribe.SourceEngine, scribe.SubjectHost(pending.host), scribe.ActionReconcile).Debugf("reclaims", reconcileStart, "[  0] services, after [%6d] s", int64(config.SinceIncludingSuspend(pending.started).Seconds()))
					continue
				}
				cache.Refresh()
				scribe.Log(scribe.SourceEngine, scribe.SubjectHost(pending.host), scribe.ActionReconcile).Infof("reclaims", reconcileStart, "[%2d] evicted after [%4d] s: %s", len(services), int64(config.SinceIncludingSuspend(pending.started).Seconds()), strings.Join(services, ","))
			}
			resyncStart := time.Now()
			if added, dropped := resyncTopics(client); added > 0 || dropped > 0 {
				scribe.Log(scribe.SourceEngine, scribe.SubjectHost(""), scribe.ActionSubscribe).Infof("resynced", resyncStart, "[%3d] subscribed, [%3d] removals", added, dropped)
			}
			if restored := subscribeWildcards(client); restored > 0 {
				scribe.Log(scribe.SourceEngine, scribe.SubjectHost(""), scribe.ActionSubscribe).Warnf("restored", resyncStart, "[%2d] wildcards restored @ resync", restored)
			}
			if !client.IsConnected() {
				scribe.Log(scribe.SourceEngine, scribe.SubjectNone, scribe.ActionConnect).Warnf("liveness", purgeStart, "[false] disconnected; revive now")
				brokerRevive(ctx, client, 0)
			}
			rx := rxCount.Swap(0)
			drops := dropCount.Swap(0)
			rate := int64(0)
			if secs := int64(purgeInterval.Seconds()); secs > 0 {
				rate = rx / secs
			}
			subscribedMu.Lock()
			attached := len(subscribed)
			subscribedMu.Unlock()
			if rx == 0 && attached > 0 && client.IsConnectionOpen() {
				silent++
			} else {
				silent = 0
			}
			if silent >= silenceTickCount {
				silent = 0
				silenceStart := time.Now()
				restored, listens := resubscribeAll(client)
				scribe.Log(scribe.SourceEngine, scribe.SubjectHost(""), scribe.ActionDisconnect).Warnf("received", silenceStart, "[%3d] msgs over [%3d] idle ticks", rx, silenceTickCount)
				scribe.Log(scribe.SourceEngine, scribe.SubjectHost(""), scribe.ActionDisconnect).Warnf("restored", silenceStart, "[%4d] topics [%3d]+[%2d] restored", attached, restored, listens)
			}
			scribe.Log(scribe.SourceEngine, scribe.SubjectHost(""), scribe.ActionReconcile).Debugf("received", purgeStart, "[%3d] messages [%4d] messages/s", rx, rate)
			scribe.Log(scribe.SourceEngine, scribe.SubjectHost(""), scribe.ActionReconcile).Debugf("removals", purgeStart, "[%3d] evictions, [%3d] deletions", evicted, deleted)
			scribe.Log(scribe.SourceEngine, scribe.SubjectHost(""), scribe.ActionReconcile).Debugf("unlisted", purgeStart, "[%3d] drops, [%3d] subscriptions", drops, attached)
			censusStart := time.Now()
			online := 0
			services := 0
			for hostName := range cache.Hosts() {
				if assertHostOnline(hostName) {
					online++
				}
				services += len(cache.Services(hostName))
			}
			reconcileMu.Lock()
			pending := 0
			for _, reconcile := range reconciles {
				if !reconcile.deadline.IsZero() {
					pending++
				}
			}
			reconcileMu.Unlock()
			scribe.Log(scribe.SourceEngine, scribe.SubjectHost(""), scribe.ActionCensus).Debugf("reported", censusStart, "[%3d] hosts up, [%2d] reconciling", online, pending)
			scribe.Log(scribe.SourceEngine, scribe.SubjectHost(""), scribe.ActionCensus).Debugf("reported", censusStart, "[%3d] services, at [%3d] records", services, cache.Size())
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
		CacheMins:    0,
		SnapshotMins: 0,
	}
	createStart := time.Now()
	if err := probe.Create(configPath, cache, periods); err != nil {
		scribe.Log(scribe.SourceEngine, scribe.SubjectNone, scribe.ActionStart).Errorf("faulting", createStart, "[%s] loop with [%v]", loopAllProbesOnce, err)
		return
	}
	timeout := time.Duration(3*periods.PulseMillis) * time.Millisecond
	ctx, cancel := context.WithTimeout(ctx, timeout)
	defer cancel()
	runStart := time.Now()
	err := probe.RunPoll(ctx, nil)
	if err != nil && !errors.Is(err, context.DeadlineExceeded) {
		scribe.Log(scribe.SourceEngine, scribe.SubjectNone, scribe.ActionStop).Errorf("faulting", runStart, "[%s] loop with [%v]", loopAllProbesOnce, err)
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
		scribe.Log(scribe.SourceEngine, scribe.SubjectNone, scribe.ActionStart).Errorf("faulting", createStart, "[%s] loop with [%v]", loopAllProbesPublish, err)
		return
	}
	hostName := config.Load(configPath).Host()
	statusTopic := "supervisor/" + hostName + "/status"
	serviceNameTopic := "supervisor/" + hostName + "/data/service/+/name"
	commandTopic := "supervisor/+/command/service/+"
	var hasConnected atomic.Bool
	var forceRepublish atomic.Bool
	onConnect := func(client mqtt.Client) {
		names := client.Subscribe(serviceNameTopic, 1, func(_ mqtt.Client, msg mqtt.Message) {
			var value metric.ValueData
			if err := json.Unmarshal(msg.Payload(), &value); err != nil || value.Pulse == nil {
				return
			}
			if serviceName := value.Pulse.ValueString; serviceName != "" {
				registerStart := time.Now()
				if bindings := cache.RegisterService(hostName, serviceName, true); len(bindings) > 0 {
					scribe.Log(scribe.SourceEngine, scribe.SubjectService(serviceName), scribe.ActionRegister).Infof("register", registerStart, "[%s] host, rediscovered [%d] topics", hostName, len(bindings))
				}
			}
		})
		commands := client.Subscribe(commandTopic, 1, func(_ mqtt.Client, msg mqtt.Message) {
			commandStart := time.Now()
			tokens := strings.Split(msg.Topic(), "/")
			if len(tokens) < 5 || tokens[1] == "" || tokens[4] == "" {
				return
			}

			// TODO: Implement command handling

			scribe.Log(scribe.SourceEngine, scribe.SubjectService(tokens[4]), scribe.ActionSubscribe).Debugf("observed", commandStart, "[%s] host, command [%s]", tokens[1], string(msg.Payload()))
		})
		subscribeStart := time.Now()
		for topic, token := range map[string]mqtt.Token{serviceNameTopic: names, commandTopic: commands} {
			if refused, reason := subscribeRefused(token, map[string]byte{topic: 1}); len(refused) > 0 {
				scribe.Log(scribe.SourceEngine, scribe.SubjectTopic(topic), scribe.ActionSubscribe).Errorf("rollback", subscribeStart, "[%s] topic, %s, rediscovery and commands lost", topic, reason)
			}
		}
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
			scribe.Log(scribe.SourceEngine, scribe.SubjectHost(hostName), scribe.ActionConnect).Infof("observed", reconnectStart, "[online] re-asserted, read [%s], republish [%v]", seen, forceRepublish.Load())
		}
	}
	clientStart := time.Now()
	client, err := brokerConnect(configPath, onConnect, statusTopic, hostStatusOffline)
	if err != nil {
		scribe.Log(scribe.SourceEngine, scribe.SubjectNone, scribe.ActionStop).Errorf("faulting", clientStart, "[%s] loop with [%v]", loopAllProbesPublish, err)
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
		scribe.Log(scribe.SourceEngine, scribe.SubjectHost(hostName), scribe.ActionStop).Infof("shutdown", shutdownStart, "[%s] status, tombstoned [%d] topics", hostStatusOffline, tombstoned)
	}()
	cache.SubscribeDeletes(&serveDeletesListener{client: client})
	var db *databaseClient
	if config.Load(configPath).Database() != "" {
		var dbErr error
		databaseStart := time.Now()
		db, dbErr = databaseConnect(ctx, configPath)
		if dbErr != nil {
			scribe.Log(scribe.SourceEngine, scribe.SubjectNone, scribe.ActionStop).Errorf("faulting", databaseStart, "[%s] loop with [%v]", loopAllProbesPublish, dbErr)
		} else {
			defer db.close()
		}
	}
	batch := newDatabaseBatch()
	var toDelete []serviceKey
	deleted := make(map[serviceKey]bool)
	publishStart := time.Now()
	go probe.RunCycle(ctx)
	err = probe.RunPoll(ctx, func(isHeartbeat bool) {
		pulseStart := time.Now()
		publishLabel := "pulse"
		if isHeartbeat {
			publishLabel = "heartbeat"
		}
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
		collected := 0
		txBytes := 0
		batch.reset()
		toDelete = toDelete[:0]
		clear(deleted)
		process := func(guid metric.RecordGUID, record *metric.Record) {
			processStart := time.Now()
			collected++
			if record.Topic != "" {
				if record.Value.Pulse != nil {
					if payload, jsonErr := json.Marshal(record.Value); jsonErr == nil {
						client.Publish(record.Topic, 0, true, payload)
						txBytes += len(payload)
						scribe.Log(scribe.SourceEngine, scribe.SubjectTopic(record.Topic), scribe.ActionPublish).Debugf("retained", processStart, "[%4d] bytes at qos [0]", len(payload))
					} else {
						scribe.Log(scribe.SourceEngine, scribe.SubjectTopic(record.Topic), scribe.ActionPublish).Errorf("faulting", processStart, "[marshal] failed with [%v]", jsonErr)
					}
				} else if guid.ServiceName != metric.ServiceNameUnset && !strings.HasPrefix(guid.ServiceName, metric.ServiceNameSchema) {
					if payload, jsonErr := json.Marshal(record.Value); jsonErr == nil {
						client.Publish(record.Topic, 0, true, payload)
						txBytes += len(payload)
					}
					client.Publish(record.Topic, 0, true, "")
					scribe.Log(scribe.SourceEngine, scribe.SubjectTopic(record.Topic), scribe.ActionPublish).Debugf("removals", processStart, "[qos 0] cleared with an empty payload")
					toDelete = append(toDelete, serviceKey{host: guid.Host, service: guid.ServiceName})
				}
			}
			batch.add(guid, record)
		}
		if isHeartbeat {
			client.Publish(statusTopic, 1, true, hostStatusOnline)
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
		lineBytes := batch.render(strconv.FormatInt(time.Now().UnixNano(), 10))
		if lineBytes > 0 && db != nil {
			db.write(ctx, batch.protocol.Bytes())
		}
		scribe.Log(scribe.SourceEngine, scribe.SubjectHost(hostName), scribe.ActionCensus).Infof("gathered", pulseStart, "[%3d] metrics, sent [%5d] b, kept [%5d] b, [%s]",
			collected, txBytes, lineBytes, publishLabel)
	})
	if err != nil && !errors.Is(err, context.Canceled) && !errors.Is(err, context.DeadlineExceeded) {
		scribe.Log(scribe.SourceEngine, scribe.SubjectNone, scribe.ActionStop).Errorf("faulting", publishStart, "[%s] loop with [%v]", loopAllProbesPublish, err)
	}
}

type watchDeletesListener struct {
	client   mqtt.Client
	onDelete func(topic string)
}

func (b *watchDeletesListener) MarkDelete(topic string) {
	deleteStart := time.Now()
	if b.onDelete != nil {
		b.onDelete(topic)
	}
	b.client.Unsubscribe(topic)
	scribe.Log(scribe.SourceEngine, scribe.SubjectTopic(topic), scribe.ActionRemove).Debugf("removals", deleteStart, "[%s] unsubscribed, dropped from the map", topic)
}

type watchAttachListener struct {
	onAttach func()
}

func (b *watchAttachListener) MarkAttach() {
	attachStart := time.Now()
	if b.onAttach == nil {
		scribe.Log(scribe.SourceEngine, scribe.SubjectNone, scribe.ActionSubscribe).Errorf("unusable", attachStart, "[attach] requested by the display with no resync bound, so newly rendered metrics stay unsubscribed")
		return
	}
	go b.onAttach()
}

type watchWakeListener struct {
	onWake func(time.Duration)
}

func (b *watchWakeListener) MarkWake(frozen time.Duration) {
	wakeStart := config.NowIncludingSuspend().Add(-frozen)
	if b.onWake == nil {
		scribe.Log(scribe.SourceEngine, scribe.SubjectNone, scribe.ActionConnect).Errorf("unusable", wakeStart, "[wake] requested by the stall detector with no revive bound, so nothing recovers the session")
		return
	}
	scribe.Log(scribe.SourceEngine, scribe.SubjectNone, scribe.ActionConnect).Infof("detected", wakeStart, "[wake] revive requested by the stall detector")
	b.onWake(frozen)
}

type serveDeletesListener struct {
	client mqtt.Client
}

func (b *serveDeletesListener) MarkDelete(topic string) {
	deleteStart := time.Now()
	b.client.Publish(topic, 0, true, "")
	scribe.Log(scribe.SourceEngine, scribe.SubjectTopic(topic), scribe.ActionRemove).Debugf("removals", deleteStart, "[%s] tombstoned, empty retained payload", topic)
}

type hostReconcile struct {
	host     string
	started  time.Time
	deadline time.Time
	retried  bool
}

func assertHostOnline(hostName string) bool {
	hostStatusMu.RLock()
	online, known := hostStatus[hostName]
	hostStatusMu.RUnlock()
	return !known || online
}

func storeHostStatus(hostName string, online bool) {
	hostStatusMu.Lock()
	if !online {
		hostOffline[hostName] = time.Now().Unix()
	}
	hostStatus[hostName] = online
	hostStatusMu.Unlock()
}

func hostOfflineAt(hostName string) int64 {
	hostStatusMu.RLock()
	at := hostOffline[hostName]
	hostStatusMu.RUnlock()
	return at
}

func init() {
	hostStatus = make(map[string]bool)
	hostOffline = make(map[string]int64)
}

const (
	topicStatus    = "supervisor/+/status"
	topicDiscovery = "supervisor/+/data/service/+/name"

	loopListeningProbes  = "listening probes"
	loopListeningStream  = "listening stream"
	loopAllProbesOnce    = "all probes once"
	loopAllProbesPublish = "all probes publish"

	hostStatusOnline  = "online"
	hostStatusOffline = "offline"

	silenceTickCount = 5
)

var (
	hostStatusMu sync.RWMutex
	hostStatus   map[string]bool
	hostOffline  map[string]int64

	reconcileGrace = 10 * time.Second
)
