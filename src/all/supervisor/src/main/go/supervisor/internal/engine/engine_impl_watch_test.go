package engine

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"log/slog"
	"maps"
	"net"
	"os"
	"path/filepath"
	"strconv"
	"supervisor/internal/config"
	"supervisor/internal/metric"
	"supervisor/internal/scribe"
	"supervisor/internal/testutil"
	"sync"
	"testing"
	"time"

	mqtt "github.com/eclipse/paho.mqtt.golang"
)

func TestEngineImplWatch_RunListeningProbesLoop(t *testing.T) {
	tests := []struct {
		name                 string
		hostName             string
		metricIds            []metric.ID
		serviceMetricIDs     []metric.ID
		configPath           string
		createServiceCount   int
		expectedServiceNames []string
	}{
		{
			name:                 "happy_no_services",
			hostName:             "macmini-mad",
			metricIds:            []metric.ID{metric.MetricHostUsedProcessor, metric.MetricHostUsedMemory, metric.MetricHostUsedSwapSpace},
			serviceMetricIDs:     []metric.ID{metric.MetricServiceUsedProcessor, metric.MetricServiceUsedMemory},
			configPath:           testutil.FindTestFile(t, "config-happy-noservices-1.json", "config"),
			createServiceCount:   0,
			expectedServiceNames: nil,
		},
		{
			name:                 "happy_one_service",
			hostName:             "macmini-mad",
			metricIds:            []metric.ID{metric.MetricHostUsedProcessor, metric.MetricHostUsedMemory, metric.MetricHostUsedSwapSpace},
			serviceMetricIDs:     []metric.ID{metric.MetricServiceUsedProcessor, metric.MetricServiceUsedMemory},
			configPath:           testutil.FindTestFile(t, "config-happy-noservices-1.json", "config"),
			createServiceCount:   1,
			expectedServiceNames: nil,
		},
		{
			name:                 "happy_three_services_prod_like",
			hostName:             "macmini-mad",
			metricIds:            []metric.ID{metric.MetricHostUsedProcessor, metric.MetricHostUsedMemory, metric.MetricHostUsedSwapSpace},
			serviceMetricIDs:     []metric.ID{metric.MetricServiceUsedProcessor, metric.MetricServiceUsedMemory},
			configPath:           testutil.FindTestFile(t, "config-happy-prodlike-1.json", "config"),
			createServiceCount:   3,
			expectedServiceNames: []string{"monitor", "plex", "sabnzbd"},
		},
	}
	scribe.EnableStdout(slog.LevelDebug)
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			testutil.RequiresDocker(t)
			t.Cleanup(config.Reset)
			if testCase.createServiceCount > 0 {
				var createServiceNames []string
				for i := 0; i < testCase.createServiceCount; i++ {
					createServiceNames = append(createServiceNames, fmt.Sprintf("loader-%d", i+1))
				}
				_, err := testutil.SetupSleepContainer(t, "", false, createServiceNames...)
				if err != nil {
					t.Fatalf("setup sleep container failed: %v", err)
				}
			}
			cache := metric.NewRecordCache()
			for _, id := range testCase.metricIds {
				cache.SubscribeUpdates(metric.NewRecordGUID(id, testCase.hostName), &mockUpdatesListener{})
			}
			for _, id := range testCase.serviceMetricIDs {
				cache.SubscribeUpdates(metric.NewServiceSchemaRecordGUID(id, testCase.hostName, 0), &mockUpdatesListener{})
			}
			periods := config.Periods{
				PollMillis:   500,
				PulseMillis:  1000,
				TrendHours:   0,
				CacheMins:    0,
				SnapshotMins: 0,
			}
			timeout := time.Duration(4*periods.PollMillis) * time.Millisecond
			ctx, cancel := context.WithTimeout(context.Background(), timeout)
			defer cancel()
			RunListeningProbesLoop(ctx, testCase.configPath, cache, periods)
			t.Logf("Cache:\n%s", cache.String())
			assertServicesProbed(t, cache, testCase.hostName, testCase.createServiceCount, testCase.expectedServiceNames)
			expectedRecordCount := len(testCase.metricIds) + len(testCase.serviceMetricIDs)*len(cache.Services(testCase.hostName))
			if cache.Size() != expectedRecordCount {
				t.Fatalf("records: got %d want %d", cache.Size(), expectedRecordCount)
			}
		})
	}
}

type mockUpdatesListener struct{}

func TestEngineImplWatch_RunListeningStreamLoop(t *testing.T) {
	scribe.EnableStdout(slog.LevelDebug)
	testutil.RequiresDocker(t)
	_, mqttClient, err := testutil.SetupBrokerContainer(t)
	if err != nil {
		t.Fatalf("setup broker container failed: %v", err)
	}
	configFile := writeWatchConfig(t, os.Getenv("VERNEMQ_HOST"), os.Getenv("VERNEMQ_API_PORT"))
	nonNilValue := metric.ValueData{
		Timestamp: time.Now().Unix(),
		Pulse:     &metric.ValueDataDetail{OK: true, Kind: metric.ValueString, ValueString: "svc-a"},
	}
	nonNilPayload, err := json.Marshal(nonNilValue)
	if err != nil {
		t.Fatalf("marshal non-nil value failed: %v", err)
	}
	refreshes := &countingRefreshListener{}
	reconciles := &countingRefreshListener{}
	var sizeBeforeOffline, topicsBeforeOffline int
	reconcileGrace = time.Second
	t.Cleanup(func() { reconcileGrace = 10 * time.Second })
	tests := []struct {
		name         string
		topic        string
		silentMillis int
		setupFunc    func(*testing.T, *metric.RecordCache, metric.TopicBinding) []byte
		checkFunc    func(*testing.T, *metric.RecordCache, metric.TopicBinding)
	}{
		{
			name: "happy_nil_mqtt_value_deletes_service",
			setupFunc: func(_ *testing.T, _ *metric.RecordCache, _ metric.TopicBinding) []byte {
				return []byte(`{}`)
			},
			checkFunc: func(t *testing.T, cache *metric.RecordCache, b metric.TopicBinding) {
				deadline := time.Now().Add(3 * time.Second)
				for time.Now().Before(deadline) {
					_, ok := cache.Load(b.GUID)
					if !ok {
						return
					}
					time.Sleep(50 * time.Millisecond)
				}
				t.Fatalf("Got record still present after nil publish, expected service deleted")
			},
		},
		{
			name: "happy_failed_mqtt_value_keeps_service",
			setupFunc: func(t *testing.T, cache *metric.RecordCache, _ metric.TopicBinding) []byte {
				sibling := nonNilValue
				sibling.Timestamp = time.Now().Unix()
				sibling.Pulse = &metric.ValueDataDetail{OK: true, Kind: metric.ValueString, ValueString: "svc-b"}
				cache.Store(metric.NewServiceRecordGUID(metric.MetricServiceName, "alpha", "svc-b"), &metric.Record{Value: sibling})
				failed := nonNilValue
				failed.Timestamp = time.Now().Unix()
				failed.Failed = true
				failed.Pulse = &metric.ValueDataDetail{OK: false, Kind: metric.ValueInt, ValueInt: 42}
				payload, marshalErr := json.Marshal(failed)
				if marshalErr != nil {
					t.Fatalf("marshal failed value failed: %v", marshalErr)
				}
				return payload
			},
			checkFunc: func(t *testing.T, cache *metric.RecordCache, b metric.TopicBinding) {
				time.Sleep(4 * time.Second)
				record, ok := cache.Load(b.GUID)
				if !ok || record == nil {
					t.Fatalf("Got record removed after a failed publish, expected the service kept")
				}
				if !record.Value.Failed || record.Value.Pulse == nil {
					t.Fatalf("Got failed = %v pulse = %v, expected a failed record keeping its pulse", record.Value.Failed, record.Value.Pulse)
				}
				sibling, siblingOK := cache.LoadByID(metric.MetricServiceName, "alpha", 1)
				if !siblingOK || sibling == nil || sibling.Value.Pulse == nil || sibling.Value.Pulse.ValueString != "svc-b" {
					t.Fatalf("Got slot 1 = %v, expected svc-b to keep its service index across a failure", sibling)
				}
				mqttClient.Publish(b.Topic, 0, false, []byte(`{}`))
				deadline := time.Now().Add(3 * time.Second)
				for time.Now().Before(deadline) {
					if _, present := cache.Load(b.GUID); !present {
						return
					}
					time.Sleep(50 * time.Millisecond)
				}
				t.Fatalf("Got record still present after a nil publish following a failure, expected service deleted")
			},
		},
		{
			name: "happy_non_nil_mqtt_value_stores_evicted_service",
			setupFunc: func(_ *testing.T, cache *metric.RecordCache, b metric.TopicBinding) []byte {
				cache.Evict(b.GUID.Host, b.GUID.ServiceName)
				return nonNilPayload
			},
			checkFunc: func(t *testing.T, cache *metric.RecordCache, b metric.TopicBinding) {
				deadline := time.Now().Add(3 * time.Second)
				for time.Now().Before(deadline) {
					record, ok := cache.Load(b.GUID)
					if ok && record != nil && record.Value.Pulse != nil {
						return
					}
					time.Sleep(50 * time.Millisecond)
				}
				t.Fatalf("Got nil pulse after non-nil publish, expected evicted service record restored")
			},
		},
		{
			name:  "happy_online_status_does_not_refresh_per_transition",
			topic: "supervisor/alpha/status",
			setupFunc: func(_ *testing.T, cache *metric.RecordCache, _ metric.TopicBinding) []byte {
				cache.SubscribeRefresh(refreshes)
				return []byte(metric.AvailabilityOnline)
			},
			checkFunc: func(t *testing.T, _ *metric.RecordCache, _ metric.TopicBinding) {
				time.Sleep(time.Second)
				mqttClient.Publish("supervisor/alpha/status", 1, false, []byte(metric.AvailabilityOnline))
				time.Sleep(time.Second)
				if got := refreshes.count(); got != 0 {
					t.Fatalf("Got refresh count = %d after online transition and heartbeat, expected 0 — refresh is connect scoped", got)
				}
			},
		},
		{
			name: "happy_reconcile_keeps_service_delivered_before_transition",
			setupFunc: func(_ *testing.T, _ *metric.RecordCache, _ metric.TopicBinding) []byte {
				return nonNilPayload
			},
			checkFunc: func(t *testing.T, cache *metric.RecordCache, b metric.TopicBinding) {
				time.Sleep(time.Second)
				mqttClient.Publish("supervisor/alpha/status", 1, false, []byte(metric.AvailabilityOnline))
				time.Sleep(4 * time.Second)
				if _, ok := cache.Load(b.GUID); !ok {
					t.Fatalf("Got record reaped, expected service delivered after connect but before the transition to survive")
				}
			},
		},
		{
			name:  "happy_reconcile_holds_the_whole_service_set_once",
			topic: "supervisor/alpha/status",
			setupFunc: func(_ *testing.T, cache *metric.RecordCache, b metric.TopicBinding) []byte {
				stale := nonNilValue
				stale.Timestamp = time.Now().Add(-time.Hour).Unix()
				cache.Store(b.GUID, &metric.Record{Value: stale})
				return []byte(metric.AvailabilityOnline)
			},
			checkFunc: func(t *testing.T, cache *metric.RecordCache, b metric.TopicBinding) {
				time.Sleep(3 * time.Second)
				if _, ok := cache.Load(b.GUID); !ok {
					t.Fatalf("Got record reaped on the first reconcile, expected the whole service set held for a resubscribe")
				}
			},
		},
		{
			name:  "happy_reconcile_reaps_service_absent_since_transition",
			topic: "supervisor/alpha/status",
			setupFunc: func(_ *testing.T, cache *metric.RecordCache, b metric.TopicBinding) []byte {
				cache.SubscribeRefresh(reconciles)
				stale := nonNilValue
				stale.Timestamp = time.Now().Add(-time.Hour).Unix()
				cache.Store(b.GUID, &metric.Record{Value: stale})
				return []byte(metric.AvailabilityOnline)
			},
			checkFunc: func(t *testing.T, cache *metric.RecordCache, b metric.TopicBinding) {
				deadline := time.Now().Add(30 * time.Second)
				for time.Now().Before(deadline) {
					if _, ok := cache.Load(b.GUID); !ok {
						if got := reconciles.count(); got < 1 {
							t.Fatalf("Got refresh count = %d after reconcile reaped a service, expected the reap to refresh", got)
						}
						return
					}
					time.Sleep(50 * time.Millisecond)
				}
				t.Fatalf("Got record still present after reconcile grace, expected service absent since the transition reaped on the retry")
			},
		},
		{
			name: "happy_online_heartbeat_does_not_resubscribe",
			setupFunc: func(_ *testing.T, _ *metric.RecordCache, _ metric.TopicBinding) []byte {
				return nonNilPayload
			},
			checkFunc: func(t *testing.T, cache *metric.RecordCache, b metric.TopicBinding) {
				mqttClient.Publish(b.Topic, 0, true, nonNilPayload)
				defer mqttClient.Publish(b.Topic, 0, true, []byte{})
				time.Sleep(500 * time.Millisecond)
				mqttClient.Publish("supervisor/alpha/status", 1, false, []byte(metric.AvailabilityOnline))
				time.Sleep(2 * time.Second)
				cache.Evict(b.GUID.Host, b.GUID.ServiceName)
				mqttClient.Publish("supervisor/alpha/status", 1, false, []byte(metric.AvailabilityOnline))
				time.Sleep(2 * time.Second)
				record, ok := cache.Load(b.GUID)
				if !ok {
					t.Fatalf("Got record deleted after a heartbeat, expected the evicted record left alone")
				}
				if record != nil && record.Value.Pulse != nil {
					t.Fatalf("Got record repopulated after a heartbeat, expected no redelivery without a status transition")
				}
			},
		},
		{
			name:  "happy_offline_adds_no_records_for_metrics_never_held",
			topic: "supervisor/alpha/status",
			setupFunc: func(_ *testing.T, cache *metric.RecordCache, _ metric.TopicBinding) []byte {
				sizeBeforeOffline, topicsBeforeOffline = cache.Size(), len(cache.Topics())
				return []byte(metric.AvailabilityOffline)
			},
			checkFunc: func(t *testing.T, cache *metric.RecordCache, _ metric.TopicBinding) {
				time.Sleep(1500 * time.Millisecond)
				if got := cache.Size(); got != sizeBeforeOffline {
					t.Fatalf("Got [%d] records after the offline, expected [%d] as before", got, sizeBeforeOffline)
				}
				if got := len(cache.Topics()); got != topicsBeforeOffline {
					t.Fatalf("Got [%d] topics after the offline, expected [%d] as before", got, topicsBeforeOffline)
				}
			},
		},
		{
			name:  "happy_offline_host_revived_by_later_data",
			topic: "supervisor/alpha/status",
			setupFunc: func(_ *testing.T, _ *metric.RecordCache, _ metric.TopicBinding) []byte {
				return []byte(metric.AvailabilityOffline)
			},
			checkFunc: func(t *testing.T, cache *metric.RecordCache, b metric.TopicBinding) {
				time.Sleep(time.Second)
				fresh := nonNilValue
				fresh.Timestamp = time.Now().Unix()
				payload, marshalErr := json.Marshal(fresh)
				if marshalErr != nil {
					t.Fatalf("marshal fresh value failed: %v", marshalErr)
				}
				mqttClient.Publish(b.Topic, 0, false, payload)
				deadline := time.Now().Add(3 * time.Second)
				for time.Now().Before(deadline) {
					record, ok := cache.Load(b.GUID)
					if ok && record != nil && record.Value.Pulse != nil {
						return
					}
					time.Sleep(50 * time.Millisecond)
				}
				t.Fatalf("Got nil pulse after data published later than the offline, expected the host revived and the record stored")
			},
		},
		{
			name:  "happy_revived_host_follows_later_updates",
			topic: "supervisor/alpha/status",
			setupFunc: func(_ *testing.T, _ *metric.RecordCache, _ metric.TopicBinding) []byte {
				return []byte(metric.AvailabilityOffline)
			},
			checkFunc: func(t *testing.T, cache *metric.RecordCache, b metric.TopicBinding) {
				publish := func(ok bool) {
					value := nonNilValue
					value.Timestamp = time.Now().Unix()
					value.Pulse = &metric.ValueDataDetail{OK: ok, Kind: metric.ValueString, ValueString: "svc-a"}
					payload, marshalErr := json.Marshal(value)
					if marshalErr != nil {
						t.Fatalf("marshal value failed: %v", marshalErr)
					}
					mqttClient.Publish(b.Topic, 0, true, payload)
				}
				defer mqttClient.Publish(b.Topic, 0, true, []byte{})
				await := func(expected bool) bool {
					deadline := time.Now().Add(5 * time.Second)
					for time.Now().Before(deadline) {
						record, ok := cache.Load(b.GUID)
						if ok && record != nil && record.Value.Pulse != nil && record.Value.Pulse.OK == expected {
							return true
						}
						time.Sleep(50 * time.Millisecond)
					}
					return false
				}
				time.Sleep(time.Second)
				publish(false)
				if !await(false) {
					t.Fatalf("Got no unhealthy record after the host was revived, expected the first fresh value stored")
				}
				time.Sleep(time.Second)
				publish(true)
				if !await(true) {
					t.Fatalf("Got a record still unhealthy after a later healthy publish, expected the revived host to follow updates")
				}
			},
		},
		{
			name:         "happy_silent_online_host_is_blanked_then_revived_by_later_data",
			topic:        "supervisor/alpha/status",
			silentMillis: 3000,
			setupFunc: func(_ *testing.T, _ *metric.RecordCache, _ metric.TopicBinding) []byte {
				return []byte(metric.AvailabilityOnline)
			},
			checkFunc: func(t *testing.T, cache *metric.RecordCache, b metric.TopicBinding) {
				await := func(present bool, within time.Duration) bool {
					deadline := time.Now().Add(within)
					for time.Now().Before(deadline) {
						record, ok := cache.Load(b.GUID)
						if ok && (record != nil && record.Value.Pulse != nil) == present {
							return true
						}
						time.Sleep(50 * time.Millisecond)
					}
					return false
				}
				if !await(false, 8*time.Second) {
					t.Fatalf("Got a record still shown for a host online but silent, expected it blanked")
				}
				time.Sleep(1100 * time.Millisecond)
				fresh := nonNilValue
				fresh.Timestamp = time.Now().Unix()
				payload, marshalErr := json.Marshal(fresh)
				if marshalErr != nil {
					t.Fatalf("marshal fresh value failed: %v", marshalErr)
				}
				mqttClient.Publish(b.Topic, 0, false, payload)
				if !await(true, 3*time.Second) {
					t.Fatalf("Got no record after the silent host published again, expected it revived")
				}
			},
		},
		{
			name:  "sad_offline_host_ignores_earlier_data",
			topic: "supervisor/alpha/status",
			setupFunc: func(_ *testing.T, _ *metric.RecordCache, _ metric.TopicBinding) []byte {
				return []byte(metric.AvailabilityOffline)
			},
			checkFunc: func(t *testing.T, cache *metric.RecordCache, b metric.TopicBinding) {
				time.Sleep(time.Second)
				stale := nonNilValue
				stale.Timestamp = time.Now().Add(-time.Hour).Unix()
				payload, marshalErr := json.Marshal(stale)
				if marshalErr != nil {
					t.Fatalf("marshal stale value failed: %v", marshalErr)
				}
				mqttClient.Publish(b.Topic, 0, false, payload)
				time.Sleep(2 * time.Second)
				record, ok := cache.Load(b.GUID)
				if ok && record != nil && record.Value.Pulse != nil {
					t.Fatalf("Got record stored from data published before the offline, expected the offline host left evicted")
				}
			},
		},
	}
	periods := config.Periods{PulseMillis: 1000, HeartbeatSecs: 30}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			cache := metric.NewRecordCache()
			cache.Store(
				metric.NewServiceRecordGUID(metric.MetricServiceName, "alpha", "svc-a"),
				&metric.Record{Value: nonNilValue},
			)
			topics := cache.Topics()
			if len(topics) == 0 {
				t.Fatalf("Got no topics after store, expected at least one")
			}
			var binding metric.TopicBinding
			for _, b := range topics {
				if b.GUID.Host == "alpha" && b.GUID.ServiceName == "svc-a" {
					binding = b
					break
				}
			}
			if binding.Topic == "" {
				t.Fatalf("Got no binding for svc-a, expected topic to be set after store")
			}
			caseTiming := periods
			caseTiming.SilentMillis = 600_000
			if testCase.silentMillis > 0 {
				caseTiming.SilentMillis = testCase.silentMillis
			}
			ctx, cancel := context.WithTimeout(context.Background(), 60*time.Second)
			defer cancel()
			done := make(chan struct{})
			attached := &countingRefreshListener{}
			cache.SubscribeRefresh(attached)
			go func() {
				defer close(done)
				RunListeningStreamLoop(ctx, configFile, cache, caseTiming)
			}()
			for attachDeadline := time.Now().Add(15 * time.Second); attached.count() == 0; {
				if !time.Now().Before(attachDeadline) {
					t.Fatalf("Got no refresh from the stream loop, expected it to attach and refresh on connect")
				}
				time.Sleep(10 * time.Millisecond)
			}
			time.Sleep(500 * time.Millisecond)
			payload := testCase.setupFunc(t, cache, binding)
			topic := testCase.topic
			if topic == "" {
				topic = binding.Topic
			}
			mqttClient.Publish(topic, 0, false, payload)
			testCase.checkFunc(t, cache, binding)
			cancel()
			<-done
		})
	}
}

type countingRefreshListener struct {
	mutex     sync.Mutex
	refreshes int
}

func TestEngineImplWatch_Idle(t *testing.T) {
	tests := []struct {
		name         string
		rx           int64
		attached     int
		open         bool
		anyOnline    bool
		expectedIdle bool
	}{
		{name: "nothing_received_with_a_host_online_is_idle", attached: 5, open: true, anyOnline: true, expectedIdle: true},
		{name: "traffic_received_is_not_idle", rx: 3, attached: 5, open: true, anyOnline: true},
		{name: "nothing_subscribed_is_not_idle", open: true, anyOnline: true},
		{name: "a_connection_not_open_is_not_idle", attached: 5, anyOnline: true},
		{name: "every_host_offline_is_not_idle", attached: 5, open: true},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			if got := watchIdle(testCase.rx, testCase.attached, testCase.open, testCase.anyOnline); got != testCase.expectedIdle {
				t.Fatalf("idle: got %v want %v", got, testCase.expectedIdle)
			}
		})
	}
}

type severableListener struct {
	net.Listener
	mutex       sync.Mutex
	connections []net.Conn
}

func TestEngineImplWatch_BrokerLost(t *testing.T) {
	tests := []struct {
		name        string
		serve       func(net.Listener)
		lose        func(*severableListener)
		expectedMax time.Duration
	}{
		{name: "a_closed_connection_blanks_at_once", serve: serveFakeBroker, lose: (*severableListener).sever, expectedMax: 5 * time.Second},
		{name: "a_broker_gone_silent_blanks_within_the_watch_keepalive", serve: serveMuteBroker, lose: func(*severableListener) {}, expectedMax: 9 * time.Second},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			inner, err := net.Listen("tcp", "127.0.0.1:0")
			if err != nil {
				t.Fatalf("listen failed with [%v]", err)
			}
			listener := &severableListener{Listener: inner}
			t.Cleanup(listener.sever)
			go testCase.serve(listener)
			configFile := writeWatchConfig(t, "127.0.0.1", strconv.Itoa(inner.Addr().(*net.TCPAddr).Port))
			cache := metric.NewRecordCache()
			guid := metric.NewServiceRecordGUID(metric.MetricServiceName, "alpha", "svc-a")
			held := metric.ValueData{Timestamp: time.Now().Unix(), Pulse: &metric.ValueDataDetail{OK: true, Kind: metric.ValueString, ValueString: "svc-a"}}
			cache.Store(guid, &metric.Record{Value: held})
			attached := &countingRefreshListener{}
			cache.SubscribeRefresh(attached)
			ctx, cancel := context.WithCancel(context.Background())
			done := make(chan struct{})
			go func() {
				defer close(done)
				RunListeningStreamLoop(ctx, configFile, cache, config.Periods{PulseMillis: 1000, HeartbeatSecs: 30, SilentMillis: 600_000})
			}()
			t.Cleanup(func() {
				cancel()
				<-done
			})
			for deadline := time.Now().Add(15 * time.Second); attached.count() == 0; time.Sleep(10 * time.Millisecond) {
				if !time.Now().Before(deadline) {
					t.Fatalf("Got no refresh from the stream loop, expected it to attach")
				}
			}
			if record, ok := cache.Load(guid); !ok || record == nil || record.Value.Pulse == nil {
				t.Fatalf("Got no held record before the broker was lost, expected the stored value")
			}
			testCase.lose(listener)
			for deadline := time.Now().Add(testCase.expectedMax); time.Now().Before(deadline); time.Sleep(50 * time.Millisecond) {
				if record, ok := cache.Load(guid); ok && (record == nil || record.Value.Pulse == nil) {
					return
				}
			}
			t.Fatalf("Got a record still shown after the broker was lost, expected every metric blanked")
		})
	}
}

func TestEngineImplWatch_StaleRetained(t *testing.T) {
	testutil.RequiresDocker(t)
	_, mqttClient, err := testutil.SetupBrokerContainer(t)
	if err != nil {
		t.Fatalf("setup broker container failed: %v", err)
	}
	configFile := writeWatchConfig(t, os.Getenv("VERNEMQ_HOST"), os.Getenv("VERNEMQ_API_PORT"))
	tests := []struct {
		name          string
		age           time.Duration
		expectedShown bool
	}{
		{name: "a_retained_value_hours_old_is_blanked_without_waiting_for_the_window", age: 2 * time.Hour},
		{name: "a_retained_value_just_published_stays_shown", age: time.Second, expectedShown: true},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			cache := metric.NewRecordCache()
			guid := metric.NewServiceRecordGUID(metric.MetricServiceName, "alpha", "svc-a")
			cache.Store(guid, &metric.Record{Value: metric.ValueData{Timestamp: time.Now().Unix(), Pulse: &metric.ValueDataDetail{OK: true, Kind: metric.ValueString, ValueString: "svc-a"}}})
			var binding metric.TopicBinding
			for _, b := range cache.Topics() {
				if b.GUID.Host == "alpha" && b.GUID.ServiceName == "svc-a" {
					binding = b
				}
			}
			if binding.Topic == "" {
				t.Fatalf("Got no binding for svc-a, expected topic to be set after store")
			}
			payload, marshalErr := json.Marshal(metric.ValueData{Timestamp: time.Now().Add(-testCase.age).Unix(), Pulse: &metric.ValueDataDetail{OK: true, Kind: metric.ValueString, ValueString: "svc-a"}})
			if marshalErr != nil {
				t.Fatalf("marshal value failed: %v", marshalErr)
			}
			mqttClient.Publish(binding.Topic, 1, true, payload).Wait()
			t.Cleanup(func() { mqttClient.Publish(binding.Topic, 1, true, []byte{}).Wait() })
			var holdMutex sync.Mutex
			var holdUntil time.Time
			cache.SubscribeHold(holdRecorder(func(until time.Time) {
				holdMutex.Lock()
				defer holdMutex.Unlock()
				holdUntil = until
			}))
			held := func() time.Time {
				holdMutex.Lock()
				defer holdMutex.Unlock()
				return holdUntil
			}
			ctx, cancel := context.WithCancel(context.Background())
			done := make(chan struct{})
			go func() {
				defer close(done)
				RunListeningStreamLoop(ctx, configFile, cache, config.Periods{PulseMillis: 10_000, HeartbeatSecs: 300})
			}()
			t.Cleanup(func() {
				cancel()
				<-done
			})
			for heldDeadline := time.Now().Add(3 * time.Second); held().IsZero() && time.Now().Before(heldDeadline); time.Sleep(5 * time.Millisecond) {
			}
			if held().IsZero() {
				t.Fatalf("Got no paint hold after the connect, expected the display held while the retained flood is judged")
			}
			time.Sleep(time.Until(held()))
			atPaint, _ := cache.Load(binding.GUID)
			if shownAtPaint := atPaint != nil && atPaint.Value.Pulse != nil; shownAtPaint != testCase.expectedShown {
				t.Fatalf("shown when painting resumed: got %v want %v", shownAtPaint, testCase.expectedShown)
			}
			deadline := time.Now().Add(4 * time.Second)
			blanked := false
			for time.Now().Before(deadline) && !blanked {
				time.Sleep(100 * time.Millisecond)
				record, ok := cache.Load(binding.GUID)
				blanked = ok && (record == nil || record.Value.Pulse == nil)
			}
			if blanked == testCase.expectedShown {
				t.Fatalf("blanked: got %v want %v", blanked, !testCase.expectedShown)
			}
		})
	}
}

type holdRecorder func(until time.Time)

type unusedUpdates struct{}

func TestEngineImplWatch_LivenessMetricIsAlwaysSubscribed(t *testing.T) {
	tests := []struct {
		name          string
		shown         metric.ID
		expectedTopic bool
	}{
		{name: "a_layout_without_up_time_still_subscribes_it", shown: metric.MetricHostUsedMemory, expectedTopic: true},
		{name: "a_layout_with_up_time_subscribes_it_once", shown: metric.MetricHostUpTime, expectedTopic: true},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			cache := metric.NewRecordCache()
			cache.SubscribeUpdates(metric.NewRecordGUID(testCase.shown, "alpha"), unusedUpdates{})
			ctx, cancel := context.WithCancel(context.Background())
			done := make(chan struct{})
			go func() {
				defer close(done)
				RunListeningStreamLoop(ctx, writeWatchConfig(t, "127.0.0.1", "1"), cache, config.Periods{PulseMillis: 1000, HeartbeatSecs: 30})
			}()
			t.Cleanup(func() {
				cancel()
				<-done
			})
			upTimes := 0
			for deadline := time.Now().Add(3 * time.Second); time.Now().Before(deadline) && upTimes == 0; time.Sleep(10 * time.Millisecond) {
				for _, binding := range cache.Topics() {
					if binding.GUID.ID == metric.MetricHostUpTime && binding.GUID.Host == "alpha" {
						upTimes++
					}
				}
			}
			if (upTimes == 1) != testCase.expectedTopic {
				t.Fatalf("up_time topics for alpha: got %d want one [%v]", upTimes, testCase.expectedTopic)
			}
		})
	}
}

func TestEngineImplWatch_DrillConverges(t *testing.T) {
	tests := []struct {
		name        string
		outage      time.Duration
		flushRetain bool
		hostsFirst  bool
		staggers    map[string]time.Duration
		recoverIn   time.Duration
	}{
		{name: "retained_flushed_hosts_back_after_the_watch", outage: 6 * time.Second, flushRetain: true, staggers: map[string]time.Duration{"meg": 0, "max": 2 * time.Second, "jen": time.Second}, recoverIn: 3 * time.Second},
		{name: "retained_flushed_hosts_back_before_the_watch", outage: 6 * time.Second, flushRetain: true, hostsFirst: true, staggers: map[string]time.Duration{"meg": 0, "max": 2 * time.Second, "jen": time.Second}, recoverIn: 3 * time.Second},
		{name: "watch_link_lost_retained_kept", outage: 6 * time.Second, flushRetain: false, staggers: map[string]time.Duration{"meg": 0, "max": 0, "jen": 0}, recoverIn: 2 * time.Second},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			_, _, err := testutil.SetupBrokerContainer(t)
			if err != nil {
				t.Fatalf("broker setup failed with [%v]", err)
			}
			brokerAddr := net.JoinHostPort(os.Getenv("VERNEMQ_HOST"), os.Getenv("VERNEMQ_API_PORT"))
			proxy := newGateProxy(t, brokerAddr)
			periods := config.Periods{PulseMillis: 1000, HeartbeatSecs: 4}
			hosts := []string{"meg", "max", "jen"}
			fleet := map[string]*drillServe{}
			for _, host := range hosts {
				fleet[host] = newDrillServe(t, brokerAddr, host, periods)
			}
			fleet["jen"].service = "zigbee2mqtt"
			fleet["meg"].set(drillShares, drillValue(true, 0))
			fleet["max"].set(drillShares, drillValue(true, 0))
			fleet["jen"].set(drillShares, drillValue(true, 0))
			fleet["jen"].set(drillMemory, drillValue(true, 30))
			for _, host := range hosts {
				fleet[host].start()
			}
			cache := metric.NewRecordCache()
			painted := map[string]*countingUpdates{}
			for _, host := range hosts {
				painted[host] = &countingUpdates{}
				cache.SubscribeUpdates(metric.NewRecordGUID(metric.MetricHostFailedShares, host), painted[host])
			}
			memoryPainted := &countingUpdates{}
			cache.SubscribeUpdates(metric.NewServiceSchemaRecordGUID(metric.MetricServiceUsedMemory, "jen", 0), memoryPainted)
			ctx, cancel := context.WithCancel(context.Background())
			done := make(chan struct{})
			go func() {
				defer close(done)
				RunListeningStreamLoop(ctx, writeWatchConfig(t, "127.0.0.1", strconv.Itoa(proxy.port())), cache, periods)
			}()
			t.Cleanup(func() {
				cancel()
				<-done
			})
			shown := func() map[string]string {
				view := map[string]string{}
				for _, host := range hosts {
					view[host+"/shares"] = drillShown(cache.Load(metric.NewRecordGUID(metric.MetricHostFailedShares, host)))
				}
				view["jen/memory"] = drillShown(cache.LoadByID(metric.MetricServiceUsedMemory, "jen", 0))
				return view
			}
			expected := func() map[string]string {
				return map[string]string{"meg/shares": fleet["meg"].shown(drillShares), "max/shares": fleet["max"].shown(drillShares), "jen/shares": fleet["jen"].shown(drillShares), "jen/memory": fleet["jen"].shown(drillMemory)}
			}
			awaitConverged := func(stage string, within time.Duration) {
				t.Helper()
				deadline := time.Now().Add(within)
				for {
					got, want := shown(), expected()
					if maps.Equal(got, want) {
						t.Logf("stage [%s] converged %v", stage, got)
						return
					}
					if time.Now().After(deadline) {
						t.Fatalf("stage [%s] not converged after [%v]: got %v want %v", stage, within, got, want)
					}
					time.Sleep(100 * time.Millisecond)
				}
			}
			awaitConverged("steady", 15*time.Second)
			proxy.block()
			for _, host := range hosts {
				fleet[host].stop()
			}
			if testCase.flushRetain {
				for _, host := range hosts {
					fleet[host].flush()
				}
			}
			fleet["meg"].set(drillShares, drillValue(false, 73))
			fleet["max"].set(drillShares, drillValue(false, 27))
			fleet["jen"].set(drillMemory, drillValue(false, 95))
			time.Sleep(testCase.outage)
			restored := time.Now()
			if !testCase.hostsFirst {
				proxy.unblock()
			}
			var waiting sync.WaitGroup
			for _, host := range hosts {
				waiting.Add(1)
				go func(host string) {
					defer waiting.Done()
					time.Sleep(testCase.staggers[host])
					fleet[host].start()
				}(host)
			}
			waiting.Wait()
			if testCase.hostsFirst {
				proxy.unblock()
			}
			time.Sleep(time.Until(restored.Add(testCase.recoverIn)))
			fleet["meg"].set(drillShares, drillValue(true, 0))
			time.Sleep(time.Second)
			fleet["max"].set(drillShares, drillValue(true, 0))
			fleet["jen"].set(drillMemory, drillValue(true, 31))
			awaitConverged("recovered", 4*time.Duration(periods.HeartbeatSecs)*time.Second)
			for host, listener := range painted {
				if listener.count() == 0 {
					t.Errorf("painted [%s]: got no dirty mark, expected the box repainted", host)
				}
			}
		})
	}
}

func (m *mockUpdatesListener) MarkDirty() {}

func assertServicesProbed(t *testing.T, cache *metric.RecordCache, hostName string, createdCount int, configured []string) {
	t.Helper()
	probed := make(map[string]bool)
	for _, name := range cache.Services(hostName) {
		probed[name] = true
	}
	expected := append([]string{}, configured...)
	for i := range createdCount {
		expected = append(expected, fmt.Sprintf("sleep-loader-%d", i+1))
	}
	for _, name := range expected {
		if !probed[name] {
			t.Fatalf("services: got %v want service %s", cache.Services(hostName), name)
		}
	}
}

func (l *countingRefreshListener) MarkRefresh() {
	l.mutex.Lock()
	l.refreshes++
	l.mutex.Unlock()
}

func (l *countingRefreshListener) count() int {
	l.mutex.Lock()
	defer l.mutex.Unlock()
	return l.refreshes
}

func (l *severableListener) Accept() (net.Conn, error) {
	connection, err := l.Listener.Accept()
	if err == nil {
		l.mutex.Lock()
		l.connections = append(l.connections, connection)
		l.mutex.Unlock()
	}
	return connection, err
}

func (l *severableListener) sever() {
	_ = l.Listener.Close()
	l.mutex.Lock()
	defer l.mutex.Unlock()
	for _, connection := range l.connections {
		_ = connection.Close()
	}
}

func serveMuteBroker(listener net.Listener) {
	for {
		connection, err := listener.Accept()
		if err != nil {
			return
		}
		go func() {
			defer func() { _ = connection.Close() }()
			buffer := make([]byte, 4096)
			if _, err := connection.Read(buffer); err != nil {
				return
			}
			_, _ = connection.Write([]byte{0x20, 0x02, 0x00, 0x00})
			for {
				if _, err := connection.Read(buffer); err != nil {
					return
				}
			}
		}()
	}
}

func writeWatchConfig(t *testing.T, brokerHost, brokerPort string) string {
	t.Helper()
	configFile := filepath.Join(t.TempDir(), "config.json")
	content := fmt.Sprintf(`{"asystem":{"version":"10.100.6000","host":"ahost","broker":{"host":%q,"port":%q},"database":{"host":"db.local","port":"2000"}}}`, brokerHost, brokerPort)
	if err := os.WriteFile(configFile, []byte(content), 0644); err != nil {
		t.Fatalf("write config file failed: %v", err)
	}
	return configFile
}

func (r holdRecorder) MarkHold(until time.Time) { r(until) }

func (unusedUpdates) MarkDirty() {}

const (
	drillShares = "data/host/failed_shares"
	drillMemory = "data/service/zigbee2mqtt/used_memory"
)

func drillValue(ok bool, value int8) metric.ValueData {
	return metric.ValueData{Pulse: &metric.ValueDataDetail{Kind: metric.ValueInt, OK: ok, ValueInt: value}, Trend: &metric.ValueDataDetail{Kind: metric.ValueInt, OK: true, ValueInt: 0}}
}

func drillShown(record *metric.Record, found bool) string {
	if !found || record == nil || record.Value.Pulse == nil {
		return "blank"
	}
	return fmt.Sprintf("%v/%d", record.Value.Pulse.OK, record.Value.Pulse.ValueInt)
}

type countingUpdates struct {
	mutex sync.Mutex
	marks int
}

func (c *countingUpdates) MarkDirty() {
	c.mutex.Lock()
	c.marks++
	c.mutex.Unlock()
}

func (c *countingUpdates) count() int {
	c.mutex.Lock()
	defer c.mutex.Unlock()
	return c.marks
}

type drillServe struct {
	t         *testing.T
	broker    string
	host      string
	service   string
	periods   config.Periods
	mutex     sync.Mutex
	values    map[string]metric.ValueData
	published map[string]metric.ValueData
	client    mqtt.Client
	cancel    context.CancelFunc
	done      chan struct{}
}

func newDrillServe(t *testing.T, broker, host string, periods config.Periods) *drillServe {
	s := &drillServe{t: t, broker: broker, host: host, periods: periods, values: map[string]metric.ValueData{}}
	t.Cleanup(s.stop)
	return s
}

func (s *drillServe) set(leaf string, value metric.ValueData) {
	s.mutex.Lock()
	s.values[leaf] = value
	s.mutex.Unlock()
}

func (s *drillServe) shown(leaf string) string {
	s.mutex.Lock()
	defer s.mutex.Unlock()
	value := s.values[leaf]
	return drillShown(&metric.Record{Value: value}, true)
}

func (s *drillServe) topic(leaf string) string {
	return "supervisor/" + s.host + "/" + leaf
}

func (s *drillServe) start() {
	options := mqtt.NewClientOptions().AddBroker("tcp://"+s.broker).SetClientID(fmt.Sprintf("drill-%s-%d", s.host, time.Now().UnixNano())).SetCleanSession(true).SetWill(s.topic("status"), metric.AvailabilityOffline, 1, true)
	client := mqtt.NewClient(options)
	if token := client.Connect(); !token.WaitTimeout(5*time.Second) || token.Error() != nil {
		s.t.Errorf("serve [%s] connect failed [%v]", s.host, token.Error())
		return
	}
	ctx, cancel := context.WithCancel(context.Background())
	s.mutex.Lock()
	s.client, s.cancel, s.done, s.published = client, cancel, make(chan struct{}), map[string]metric.ValueData{}
	done := s.done
	s.mutex.Unlock()
	go func() {
		defer close(done)
		pulse := time.NewTicker(time.Duration(s.periods.PulseMillis) * time.Millisecond)
		defer pulse.Stop()
		beat := 0
		heartbeatEvery := s.periods.HeartbeatSecs * 1000 / s.periods.PulseMillis
		for {
			s.publish(client, beat%heartbeatEvery == 0, beat)
			beat++
			select {
			case <-ctx.Done():
				return
			case <-pulse.C:
			}
		}
	}()
}

func (s *drillServe) publish(client mqtt.Client, heartbeat bool, beat int) {
	send := func(topic string, value metric.ValueData) {
		value.Timestamp = time.Now().Unix()
		payload, _ := json.Marshal(value)
		client.Publish(topic, 0, true, payload)
	}
	if heartbeat {
		client.Publish(s.topic("status"), 1, true, metric.AvailabilityOnline)
	}
	send(s.topic("data/host/up_time"), metric.ValueData{Pulse: &metric.ValueDataDetail{Kind: metric.ValueFloat, OK: true, ValueFloat: float64(beat)}})
	if s.service != "" {
		name := metric.ValueData{Pulse: &metric.ValueDataDetail{Kind: metric.ValueString, OK: true, ValueString: s.service}}
		if heartbeat {
			send(s.topic("data/service/"+s.service+"/name"), name)
		}
	}
	s.mutex.Lock()
	var due []string
	for leaf, value := range s.values {
		if last, sent := s.published[leaf]; heartbeat || !sent || !last.Equal(&value) {
			due = append(due, leaf)
			s.published[leaf] = value
		}
	}
	values := maps.Clone(s.values)
	s.mutex.Unlock()
	for _, leaf := range due {
		send(s.topic(leaf), values[leaf])
	}
}

func (s *drillServe) stop() {
	s.mutex.Lock()
	client, cancel, done := s.client, s.cancel, s.done
	s.client, s.cancel = nil, nil
	s.mutex.Unlock()
	if cancel == nil {
		return
	}
	cancel()
	<-done
	client.Disconnect(0)
}

func (s *drillServe) flush() {
	client := mqtt.NewClient(mqtt.NewClientOptions().AddBroker("tcp://" + s.broker).SetClientID(fmt.Sprintf("drill-flush-%s-%d", s.host, time.Now().UnixNano())))
	if token := client.Connect(); !token.WaitTimeout(5*time.Second) || token.Error() != nil {
		s.t.Errorf("flush [%s] connect failed [%v]", s.host, token.Error())
		return
	}
	defer client.Disconnect(250)
	leaves := []string{"status", "data/host/up_time", drillShares}
	if s.service != "" {
		leaves = append(leaves, "data/service/"+s.service+"/name", drillMemory)
	}
	for _, leaf := range leaves {
		client.Publish(s.topic(leaf), 1, true, []byte{}).WaitTimeout(2 * time.Second)
	}
}

type gateProxy struct {
	listener net.Listener
	target   string
	mutex    sync.Mutex
	blocked  bool
	conns    []net.Conn
}

func newGateProxy(t *testing.T, target string) *gateProxy {
	listener, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		t.Fatalf("proxy listen failed [%v]", err)
	}
	p := &gateProxy{listener: listener, target: target}
	t.Cleanup(func() {
		_ = listener.Close()
		p.block()
	})
	go func() {
		for {
			inbound, err := listener.Accept()
			if err != nil {
				return
			}
			p.mutex.Lock()
			blocked := p.blocked
			p.mutex.Unlock()
			if blocked {
				_ = inbound.Close()
				continue
			}
			outbound, err := net.Dial("tcp", target)
			if err != nil {
				_ = inbound.Close()
				continue
			}
			p.mutex.Lock()
			p.conns = append(p.conns, inbound, outbound)
			p.mutex.Unlock()
			go func() { _, _ = io.Copy(outbound, inbound); _ = outbound.Close() }()
			go func() { _, _ = io.Copy(inbound, outbound); _ = inbound.Close() }()
		}
	}()
	return p
}

func (p *gateProxy) port() int {
	return p.listener.Addr().(*net.TCPAddr).Port
}

func (p *gateProxy) block() {
	p.mutex.Lock()
	defer p.mutex.Unlock()
	p.blocked = true
	for _, conn := range p.conns {
		_ = conn.Close()
	}
	p.conns = nil
}

func (p *gateProxy) unblock() {
	p.mutex.Lock()
	p.blocked = false
	p.mutex.Unlock()
}
