package engine

import (
	"context"
	"encoding/json"
	"errors"
	"slices"
	"strconv"
	"strings"
	"supervisor/internal/config"
	"supervisor/internal/metric"
	"supervisor/internal/probe"
	"supervisor/internal/scribe"
	"sync/atomic"
	"time"

	mqtt "github.com/eclipse/paho.mqtt.golang"
)

type serviceKey struct {
	host    string
	service string
}

// RunAllProbesPublishLoop runs every probe locally and publishes what they collect to the broker and to the database.
// It is the serve side of the service, and RunListeningStreamLoop above holds the other half of the lifecycle contract.
//
// On connect:
//  1. Subscribe to this host's own retained service names, and register each one, which is how a service survives a crash.
//     Every arm of that handler reports, because a silent return made an absent line mean four different things at once.
//  2. Subscribe to the command topic.
//  3. On a reconnect, read the retained status back, and re-assert it online, forcing a full republish when it had lapsed.
//
// On each pulse:
//  1. Publish the online status and every record on a heartbeat, or only the records that changed otherwise.
//  2. Publish a record holding a pulse to its own retained topic.
//  3. Publish a record holding none as nil, then as an empty payload at qos 1, then delete it, which tombstones it.
//  4. Group the numeric metrics by host and service, and write them to the database as line protocol.
//
// On shutdown, which a signal reaches but a kill does not:
//  1. Publish the offline status, which is what the last will would otherwise have published, and nothing else.
//
// Notes:
//   - The retained set is deliberately left behind on the way out, because it is the only breadcrumb the next process
//     has. Tombstoning it here reached no watch, since the offline status is acknowledged first and every watch drops
//     what an offline host publishes, and it deleted the very names the readback above reads. See supervisor/CLAUDE.md.
//   - The service name topic must be retained for the same reason after a kill, which publishes nothing at all, so both
//     exits now recover the same way: the next process rediscovers the service from that name, finds it absent from
//     docker, and removes it, which is what finally clears the broker.
//   - The cache belongs to this loop alone, and Take drains the changed set each pulse, sorted, so a pulse is reproducible.
//   - The database connects on its own goroutine, so an unreachable one delays no probe, and the pulse reads it atomically.
//   - A service that leaves docker or the config is evicted to nil then deleted, and the deletes listener publishes the
//     same two forms at qos 1, so a departure carries a timestamp that proves the host alive and cannot be lost in transit.
//   - A record reaching the pulse without a pulse value is tombstoned there too, covering an interleave with the removal above.
func RunAllProbesPublishLoop(ctx context.Context, configPath string, cache *metric.RecordCache, periods config.Periods) {
	for _, id := range metric.GetIDs() {
		record := metric.NewRecord(metric.NewNilValue())
		cache.Store(metric.NewServiceSchemaRecordGUID(id, metric.GetIDHost(id, config.Load(configPath).Host()), 0), &record)
	}
	createStart := time.Now()
	if err := probe.Create(configPath, cache, periods); err != nil {
		scribe.Log(scribe.SourceEngine, scribe.SubjectNone, scribe.ActionStart).Errorf("faulting", createStart, "[%s] loop with [%v]", loopAllProbesPublish, err)
		return
	}
	hostName := config.Load(configPath).Host()
	statusTopic := "supervisor/" + hostName + "/status"
	serviceNameTopic := "supervisor/" + hostName + "/data/service/+/name"
	commandTopic := "supervisor/+/command/+/+"
	var hasConnected atomic.Bool
	var forceRepublish atomic.Bool
	onConnect := func(client mqtt.Client) {
		names := client.Subscribe(serviceNameTopic, 1, func(_ mqtt.Client, msg mqtt.Message) {
			readbackStart := time.Now()
			topic := scribe.SubjectTopic(msg.Topic())
			if len(msg.Payload()) == 0 {
				scribe.Log(scribe.SourceEngine, topic, scribe.ActionRegister).Infof("excluded", readbackStart, "[empty] readback, tombstoned before")
				return
			}
			var value metric.ValueData
			if err := json.Unmarshal(msg.Payload(), &value); err != nil {
				scribe.Log(scribe.SourceEngine, topic, scribe.ActionRegister).Errorf("rejected", readbackStart, "[unmarshal] readback failed with [%v]", err)
				return
			}
			if value.Pulse == nil {
				scribe.Log(scribe.SourceEngine, topic, scribe.ActionRegister).Infof("excluded", readbackStart, "[nil] readback pulse, departing now")
				return
			}
			serviceName := value.Pulse.ValueString
			if serviceName == "" {
				scribe.Log(scribe.SourceEngine, topic, scribe.ActionRegister).Errorf("rejected", readbackStart, "[empty] readback carries no service")
				return
			}
			bindings := cache.RegisterService(hostName, serviceName, true)
			if len(bindings) == 0 {
				scribe.Log(scribe.SourceEngine, scribe.SubjectService(serviceName), scribe.ActionRegister).Infof("register", readbackStart, "[%s] host, rediscovered [  0] topics", hostName)
				return
			}
			scribe.Log(scribe.SourceEngine, scribe.SubjectService(serviceName), scribe.ActionRegister).Infof("register", readbackStart, "[%s] host, rediscovered [%3d] topics", hostName, len(bindings))
		})
		onCommand := func(_ mqtt.Client, msg mqtt.Message) {
			commandStart := time.Now()
			tokens := strings.Split(msg.Topic(), "/")
			if msg.Topic() != metric.TopicAllCommand && (len(tokens) < 5 || tokens[1] == "" || tokens[3] == "" || tokens[4] == "") {
				scribe.Log(scribe.SourceEngine, scribe.SubjectTopic(msg.Topic()), scribe.ActionSubscribe).Errorf("rejected", commandStart, "[malformed] topic of [%2d] levels", len(tokens))
				return
			}
			var subject scribe.Subject
			switch tokens[3] {
			case metric.EntityCluster:
				if leading, _ := probe.Leading(metric.LeaderDutySentinel); !leading {
					scribe.Log(scribe.SourceEngine, scribe.SubjectMetric(metric.MetricCluster), scribe.ActionSubscribe).Debugf("deferred", commandStart, "[%s] command left to the holder of duty [%s]", string(msg.Payload()), metric.LeaderDutySentinel)
					return
				}
				subject = scribe.SubjectMetric(metric.MetricCluster)
			case metric.EntityService:
				subject = scribe.SubjectService(tokens[4])
			case metric.EntityHost:
				subject = scribe.SubjectHost(tokens[1])
			default:
				scribe.Log(scribe.SourceEngine, scribe.SubjectTopic(msg.Topic()), scribe.ActionSubscribe).Errorf("rejected", commandStart, "[%s] scope, only [%s], [%s] and [%s] are commanded", tokens[3], metric.EntityCluster, metric.EntityHost, metric.EntityService)
				return
			}

			// TODO: Implement command handling

			scribe.Log(scribe.SourceEngine, subject, scribe.ActionSubscribe).Debugf("observed", commandStart, "[%s] host, [%s] scope, command [%s]", tokens[1], tokens[3], string(msg.Payload()))
		}
		commands := client.Subscribe(commandTopic, 1, onCommand)
		cluster := client.Subscribe(metric.TopicAllCommand, 1, onCommand)
		subscribeStart := time.Now()
		for topic, token := range map[string]mqtt.Token{serviceNameTopic: names, commandTopic: commands, metric.TopicAllCommand: cluster} {
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
			if seen != metric.AvailabilityOnline {
				forceRepublish.Store(true)
			}
			client.Publish(statusTopic, 1, true, metric.AvailabilityOnline).WaitTimeout(brokerTimeout)
			scribe.Log(scribe.SourceEngine, scribe.SubjectHost(hostName), scribe.ActionConnect).Infof("observed", reconnectStart, "[online] re-asserted, read [%s], republish [%v]", seen, forceRepublish.Load())
		}
	}
	clientStart := time.Now()
	client, err := brokerConnect(configPath, onConnect, statusTopic, metric.AvailabilityOffline)
	if err != nil {
		scribe.Log(scribe.SourceEngine, scribe.SubjectNone, scribe.ActionStop).Errorf("faulting", clientStart, "[%s] loop with [%v]", loopAllProbesPublish, err)
		return
	}
	defer func() {
		shutdownStart := time.Now()
		probe.Resign()
		client.Publish(statusTopic, 1, true, metric.AvailabilityOffline).WaitTimeout(2 * time.Second)
		client.Disconnect(2500)
		scribe.Log(scribe.SourceEngine, scribe.SubjectHost(hostName), scribe.ActionStop).Infof("shutdown", shutdownStart, "[%s] status, retained [%3d] records", metric.AvailabilityOffline, cache.Size())
	}()
	cache.SubscribeDeletes(&serveDeletesListener{client: client})
	var db atomic.Pointer[databaseClient]
	defer func() {
		if connected := db.Swap(nil); connected != nil {
			connected.close()
		}
	}()
	if config.Load(configPath).Database() != "" {
		databaseStart := time.Now()
		go func() {
			connected, dbErr := databaseConnect(ctx, configPath)
			if dbErr != nil {
				scribe.Log(scribe.SourceEngine, scribe.SubjectNone, scribe.ActionConnect).Errorf("faulting", databaseStart, "[%s] loop with [%v]", loopAllProbesPublish, dbErr)
				return
			}
			if ctx.Err() != nil {
				connected.close()
				return
			}
			db.Store(connected)
		}()
	}
	batch := newDatabaseBatch()
	clusterEpoch := int64(0)
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
		leading, epoch := probe.Leading(metric.LeaderDutySentinel)
		published := func(guid metric.RecordGUID) bool {
			return metric.GetIDKind(guid.ID) != metric.MetricKindCluster || leading
		}
		if forceRepublish.Swap(false) && !isHeartbeat {
			client.Publish(statusTopic, 1, true, metric.AvailabilityOnline)
			cache.Records(func(guid metric.RecordGUID, record *metric.Record) {
				if record.Topic == "" || record.Value.Pulse == nil || !published(guid) {
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
			if !published(guid) {
				return
			}
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
						client.Publish(record.Topic, 1, true, payload)
						txBytes += len(payload)
					}
					client.Publish(record.Topic, 1, true, "")
					scribe.Log(scribe.SourceEngine, scribe.SubjectTopic(record.Topic), scribe.ActionPublish).Debugf("removals", processStart, "[qos 1] nil then empty payload")
					toDelete = append(toDelete, serviceKey{host: guid.Host, service: guid.ServiceName})
				}
			}
			batch.add(guid, record)
		}
		if isHeartbeat {
			client.Publish(statusTopic, 1, true, metric.AvailabilityOnline)
			txBytes += len(metric.AvailabilityOnline)
			cache.Records(func(guid metric.RecordGUID, record *metric.Record) {
				process(guid, record)
			})
			cache.Take()
		} else {
			taken := cache.Take()
			for _, guid := range taken {
				record, ok := cache.Load(guid)
				if !ok {
					continue
				}
				process(guid, record)
			}
			if leading && epoch != clusterEpoch {
				for _, id := range metric.GetIDsByKind([]metric.MetricKind{metric.MetricKindCluster}) {
					guid := metric.NewRecordGUID(id, metric.HostAll)
					if record, ok := cache.Load(guid); ok && !slices.ContainsFunc(taken, func(took metric.RecordGUID) bool { return took.ID == id && took.Host == metric.HostAll }) {
						process(guid, record)
					}
				}
			}
		}
		if leading && epoch != clusterEpoch {
			clusterEpoch = epoch
			scribe.Log(scribe.SourceEngine, scribe.SubjectMetric(metric.MetricCluster), scribe.ActionPublish).Infof("assigned", pulseStart, "[%d] epoch leads the cluster, publishing its records", epoch)
		} else if !leading && clusterEpoch != 0 {
			clusterEpoch = 0
			scribe.Log(scribe.SourceEngine, scribe.SubjectMetric(metric.MetricCluster), scribe.ActionPublish).Infof("released", pulseStart, "[%s] no longer leads the cluster, withholding its records", hostName)
		}
		for _, k := range toDelete {
			if !deleted[k] {
				deleted[k] = true
				cache.Delete(k.host, k.service)
			}
		}
		lineBytes := batch.render(strconv.FormatInt(time.Now().UnixNano(), 10))
		if connected := db.Load(); lineBytes > 0 && connected != nil {
			connected.write(ctx, batch.protocol.Bytes())
		}
		scribe.Log(scribe.SourceEngine, scribe.SubjectHost(hostName), scribe.ActionCensus).Infof("gathered", pulseStart, "[%3d] metrics, sent [%5d] bytes, kept [%5d] bytes, [%s]",
			collected, txBytes, lineBytes, publishLabel)
	})
	if err != nil && !errors.Is(err, context.Canceled) && !errors.Is(err, context.DeadlineExceeded) {
		scribe.Log(scribe.SourceEngine, scribe.SubjectNone, scribe.ActionStop).Errorf("faulting", publishStart, "[%s] loop with [%v]", loopAllProbesPublish, err)
	}
}

type serveDeletesListener struct {
	client mqtt.Client
}

func (b *serveDeletesListener) MarkDelete(topic string) {
	deleteStart := time.Now()
	if payload, err := json.Marshal(metric.NewNilValue()); err == nil {
		b.client.Publish(topic, 1, true, payload)
	} else {
		scribe.Log(scribe.SourceEngine, scribe.SubjectTopic(topic), scribe.ActionRemove).Errorf("faulting", deleteStart, "[marshal] nil failed with [%v]", err)
	}
	b.client.Publish(topic, 1, true, "")
	scribe.Log(scribe.SourceEngine, scribe.SubjectTopic(topic), scribe.ActionRemove).Debugf("removals", deleteStart, "[%s] tombstoned, nil then empty", topic)
}

const (
	loopAllProbesPublish = "all probes publish"
)
