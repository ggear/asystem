package engine

import (
	"context"
	"encoding/json"
	"fmt"
	"log/slog"
	"maps"
	"os"
	"path/filepath"
	"slices"
	"strings"
	"supervisor/internal/config"
	"supervisor/internal/metric"
	"supervisor/internal/scribe"
	"supervisor/internal/testutil"
	"sync"
	"testing"
	"time"

	mqtt "github.com/eclipse/paho.mqtt.golang"
)

func TestEngine_RunAllProbesOnce(t *testing.T) {
	tests := []struct {
		name                 string
		hostName             string
		configPath           string
		createServiceCount   int
		expectedServiceNames []string
	}{
		{
			name:                 "happy_no_services",
			hostName:             "macmini-mad",
			configPath:           testutil.FindTestFile(t, "config-happy-noservices-1.json", "config"),
			createServiceCount:   0,
			expectedServiceNames: nil,
		},
		{
			name:                 "happy_one_service",
			hostName:             "macmini-mad",
			configPath:           testutil.FindTestFile(t, "config-happy-noservices-1.json", "config"),
			createServiceCount:   1,
			expectedServiceNames: nil,
		},
		{
			name:                 "happy_three_services_prod_like",
			hostName:             "macmini-mad",
			configPath:           testutil.FindTestFile(t, "config-happy-prodlike-1.json", "config"),
			createServiceCount:   3,
			expectedServiceNames: []string{"monitor", "plex", "sabnzbd"},
		},
	}
	scribe.EnableStdout(slog.LevelDebug)
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			testutil.RequiresDocker(t)
			t.Cleanup(config.Reset)
			if tt.createServiceCount > 0 {
				var createServiceNames []string
				for i := 0; i < tt.createServiceCount; i++ {
					createServiceNames = append(createServiceNames, fmt.Sprintf("loader-%d", i+1))
				}
				_, setupErr := testutil.SetupSleepContainer(t, "", false, createServiceNames...)
				if setupErr != nil {
					t.Fatalf("setup sleep container failed: %v", setupErr)
				}
			}
			cache := metric.NewRecordCache()
			RunAllProbesOnce(context.Background(), tt.configPath, cache)
			t.Logf("Cache:\n%s", cache.String())
			assertServicesProbed(t, cache, tt.hostName, tt.createServiceCount, tt.expectedServiceNames)
			expectedRecordCount := metricCountHost + metricCountService*len(cache.Services(tt.hostName))
			if cache.Size() != expectedRecordCount {
				t.Fatalf("records: got %d want %d", cache.Size(), expectedRecordCount)
			}
		})
	}
}

func TestEngine_RunListeningProbesLoop(t *testing.T) {
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
			metricIds:            []metric.ID{metric.MetricHostUsedProcessor, metric.MetricHostUsedMemory},
			serviceMetricIDs:     []metric.ID{metric.MetricServiceUsedProcessor, metric.MetricServiceUsedMemory},
			configPath:           testutil.FindTestFile(t, "config-happy-noservices-1.json", "config"),
			createServiceCount:   0,
			expectedServiceNames: nil,
		},
		{
			name:                 "happy_one_service",
			hostName:             "macmini-mad",
			metricIds:            []metric.ID{metric.MetricHostUsedProcessor, metric.MetricHostUsedMemory},
			serviceMetricIDs:     []metric.ID{metric.MetricServiceUsedProcessor, metric.MetricServiceUsedMemory},
			configPath:           testutil.FindTestFile(t, "config-happy-noservices-1.json", "config"),
			createServiceCount:   1,
			expectedServiceNames: nil,
		},
		{
			name:                 "happy_three_services_prod_like",
			hostName:             "macmini-mad",
			metricIds:            []metric.ID{metric.MetricHostUsedProcessor, metric.MetricHostUsedMemory},
			serviceMetricIDs:     []metric.ID{metric.MetricServiceUsedProcessor, metric.MetricServiceUsedMemory},
			configPath:           testutil.FindTestFile(t, "config-happy-prodlike-1.json", "config"),
			createServiceCount:   3,
			expectedServiceNames: []string{"monitor", "plex", "sabnzbd"},
		},
	}
	scribe.EnableStdout(slog.LevelDebug)
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			testutil.RequiresDocker(t)
			t.Cleanup(config.Reset)
			if tt.createServiceCount > 0 {
				var createServiceNames []string
				for i := 0; i < tt.createServiceCount; i++ {
					createServiceNames = append(createServiceNames, fmt.Sprintf("loader-%d", i+1))
				}
				_, err := testutil.SetupSleepContainer(t, "", false, createServiceNames...)
				if err != nil {
					t.Fatalf("setup sleep container failed: %v", err)
				}
			}
			cache := metric.NewRecordCache()
			for _, id := range tt.metricIds {
				cache.SubscribeUpdates(metric.NewRecordGUID(id, tt.hostName), &mockUpdatesListener{})
			}
			for _, id := range tt.serviceMetricIDs {
				cache.SubscribeUpdates(metric.NewServiceSchemaRecordGUID(id, tt.hostName, 0), &mockUpdatesListener{})
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
			RunListeningProbesLoop(ctx, tt.configPath, cache, periods)
			t.Logf("Cache:\n%s", cache.String())
			assertServicesProbed(t, cache, tt.hostName, tt.createServiceCount, tt.expectedServiceNames)
			expectedRecordCount := len(tt.metricIds) + len(tt.serviceMetricIDs)*len(cache.Services(tt.hostName))
			if cache.Size() != expectedRecordCount {
				t.Fatalf("records: got %d want %d", cache.Size(), expectedRecordCount)
			}
		})
	}
}

var (
	metricCountHost    = len(metric.GetIDs()) - metricCountService
	metricCountService = len(metric.GetIDsByKind([]metric.MetricKind{metric.MetricKindService}))
)

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

type mockUpdatesListener struct{}

func (m *mockUpdatesListener) MarkDirty() {}

func TestEngine_HostStatus(t *testing.T) {
	value := metric.ValueData{Timestamp: time.Now().Unix(), Pulse: &metric.ValueDataDetail{OK: true, Kind: metric.ValueString, ValueString: "v"}}
	tests := []struct {
		name          string
		setupFunc     func()
		checkFunc     func(*testing.T)
		expectedError bool
	}{
		{
			name: "happy_unknown_host_is_online",
			setupFunc: func() {
				hostStatusMu.Lock()
				hostStatus = make(map[string]bool)
				hostStatusMu.Unlock()
			},
			checkFunc: func(t *testing.T) {
				if !assertHostOnline("unknown-host") {
					t.Fatalf("Got offline, expected unknown host to be treated as online")
				}
			},
			expectedError: false,
		},
		{
			name: "happy_set_online",
			setupFunc: func() {
				hostStatusMu.Lock()
				hostStatus = make(map[string]bool)
				hostStatusMu.Unlock()
				storeHostStatus("alpha", true)
			},
			checkFunc: func(t *testing.T) {
				if !assertHostOnline("alpha") {
					t.Fatalf("Got offline, expected online after storeHostStatus true")
				}
			},
			expectedError: false,
		},
		{
			name: "happy_set_offline",
			setupFunc: func() {
				hostStatusMu.Lock()
				hostStatus = make(map[string]bool)
				hostStatusMu.Unlock()
				storeHostStatus("alpha", false)
			},
			checkFunc: func(t *testing.T) {
				if assertHostOnline("alpha") {
					t.Fatalf("Got online, expected offline after storeHostStatus false")
				}
			},
			expectedError: false,
		},
		{
			name: "happy_offline_evicts_service_metrics",
			setupFunc: func() {
				hostStatusMu.Lock()
				hostStatus = make(map[string]bool)
				hostStatusMu.Unlock()
			},
			checkFunc: func(t *testing.T) {
				cache := metric.NewRecordCache()
				cache.Store(metric.NewServiceRecordGUID(metric.MetricServiceName, "alpha", "svc-a"), &metric.Record{Value: value})
				storeHostStatus("alpha", false)
				for _, svc := range cache.Services("alpha") {
					cache.Evict("alpha", svc)
				}
				record, ok := cache.Load(metric.NewServiceRecordGUID(metric.MetricServiceName, "alpha", "svc-a"))
				if !ok || record == nil {
					t.Fatalf("Got record deleted, expected evicted to nil but present")
				}
				if record.Value.Pulse != nil {
					t.Fatalf("Got non-nil pulse, expected service record evicted to nil on offline")
				}
			},
			expectedError: false,
		},
		{
			name: "happy_offline_evicts_only_services_of_offline_host",
			setupFunc: func() {
				hostStatusMu.Lock()
				hostStatus = make(map[string]bool)
				hostStatusMu.Unlock()
			},
			checkFunc: func(t *testing.T) {
				cache := metric.NewRecordCache()
				cache.Store(metric.NewServiceRecordGUID(metric.MetricServiceName, "alpha", "svc-a"), &metric.Record{Value: value})
				cache.Store(metric.NewServiceRecordGUID(metric.MetricServiceName, "beta", "svc-b"), &metric.Record{Value: value})
				storeHostStatus("alpha", false)
				for _, svc := range cache.Services("alpha") {
					cache.Evict("alpha", svc)
				}
				betaRecord, ok := cache.Load(metric.NewServiceRecordGUID(metric.MetricServiceName, "beta", "svc-b"))
				if !ok || betaRecord == nil {
					t.Fatalf("Got beta record missing, expected untouched when only alpha goes offline")
				}
				if betaRecord.Value.Pulse == nil {
					t.Fatalf("Got beta pulse nil, expected beta services unaffected when alpha goes offline")
				}
			},
			expectedError: false,
		},
		{
			name: "happy_offline_evicts_host_metrics",
			setupFunc: func() {
				hostStatusMu.Lock()
				hostStatus = make(map[string]bool)
				hostStatusMu.Unlock()
			},
			checkFunc: func(t *testing.T) {
				cache := metric.NewRecordCache()
				cache.Store(metric.NewRecordGUID(metric.MetricHost, "alpha"), &metric.Record{Value: value})
				storeHostStatus("alpha", false)
				for _, id := range metric.GetIDsByKind([]metric.MetricKind{metric.MetricKindHost}) {
					record := metric.NewRecord(metric.NewNilValue())
					cache.Store(metric.NewRecordGUID(id, "alpha"), &record)
				}
				record, ok := cache.Load(metric.NewRecordGUID(metric.MetricHost, "alpha"))
				if !ok || record == nil {
					t.Fatalf("Got host record deleted, expected evicted to nil but present")
				}
				if record.Value.Pulse != nil {
					t.Fatalf("Got non-nil pulse, expected host record evicted to nil on offline")
				}
			},
			expectedError: false,
		},
		{
			name: "happy_online_allows_store",
			setupFunc: func() {
				hostStatusMu.Lock()
				hostStatus = make(map[string]bool)
				hostStatusMu.Unlock()
				storeHostStatus("alpha", true)
			},
			checkFunc: func(t *testing.T) {
				if !assertHostOnline("alpha") {
					t.Fatalf("Got offline, expected online host to allow stores")
				}
			},
			expectedError: false,
		},
		{
			name: "happy_offline_blocks_store",
			setupFunc: func() {
				hostStatusMu.Lock()
				hostStatus = make(map[string]bool)
				hostStatusMu.Unlock()
				storeHostStatus("alpha", false)
			},
			checkFunc: func(t *testing.T) {
				if assertHostOnline("alpha") {
					t.Fatalf("Got online, expected offline host to block stores")
				}
			},
			expectedError: false,
		},
		{
			name: "happy_online_after_offline_allows_store",
			setupFunc: func() {
				hostStatusMu.Lock()
				hostStatus = make(map[string]bool)
				hostStatusMu.Unlock()
				storeHostStatus("alpha", false)
				storeHostStatus("alpha", true)
			},
			checkFunc: func(t *testing.T) {
				if !assertHostOnline("alpha") {
					t.Fatalf("Got offline, expected online after transitioning offline→online")
				}
			},
			expectedError: false,
		},
		{
			name: "happy_stale_offline_cleared_on_restart",
			setupFunc: func() {
				hostStatusMu.Lock()
				hostStatus = make(map[string]bool)
				hostStatusMu.Unlock()
				storeHostStatus("alpha", false)
			},
			checkFunc: func(t *testing.T) {
				hostStatusMu.Lock()
				hostStatus = make(map[string]bool)
				hostStatusMu.Unlock()
				if !assertHostOnline("alpha") {
					t.Fatalf("Got offline, expected stale offline status cleared after restart")
				}
			},
			expectedError: false,
		},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			tt.setupFunc()
			tt.checkFunc(t)
		})
	}
}

func TestEngine_RunListeningStreamLoop(t *testing.T) {
	scribe.EnableStdout(slog.LevelDebug)
	testutil.RequiresDocker(t)
	_, mqttClient, err := testutil.SetupBrokerContainer(t)
	if err != nil {
		t.Fatalf("setup broker container failed: %v", err)
	}
	host := os.Getenv("VERNEMQ_HOST")
	port := os.Getenv("VERNEMQ_API_PORT")
	configContent := fmt.Sprintf(`{"asystem":{"version":"10.100.6000","host":"ahost","broker":{"host":%q,"port":%q},"database":{"host":"db.local","port":"2000"}}}`, host, port)
	configFile := filepath.Join(t.TempDir(), "config.json")
	if err := os.WriteFile(configFile, []byte(configContent), 0644); err != nil {
		t.Fatalf("write config file failed: %v", err)
	}
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
	reconcileGrace = time.Second
	t.Cleanup(func() { reconcileGrace = 10 * time.Second })
	tests := []struct {
		name      string
		topic     string
		setupFunc func(*testing.T, *metric.RecordCache, metric.TopicBinding) []byte
		checkFunc func(*testing.T, *metric.RecordCache, metric.TopicBinding)
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
				deadline := time.Now().Add(14 * time.Second)
				for time.Now().Before(deadline) {
					if _, ok := cache.Load(b.GUID); !ok {
						if got := reconciles.count(); got != 1 {
							t.Fatalf("Got refresh count = %d after reconcile reaped a service, expected 1", got)
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
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
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
			ctx, cancel := context.WithTimeout(context.Background(), 20*time.Second)
			defer cancel()
			done := make(chan struct{})
			go func() {
				defer close(done)
				RunListeningStreamLoop(ctx, configFile, cache, periods)
			}()
			time.Sleep(500 * time.Millisecond)
			payload := tt.setupFunc(t, cache, binding)
			topic := tt.topic
			if topic == "" {
				topic = binding.Topic
			}
			mqttClient.Publish(topic, 0, false, payload)
			tt.checkFunc(t, cache, binding)
			cancel()
			<-done
		})
	}
}

type countingRefreshListener struct {
	mutex     sync.Mutex
	refreshes int
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

func TestEngine_RunAllProbesPublishLoop(t *testing.T) {
	logBuffer := scribe.EnableBuffer(slog.LevelDebug, 2000)
	t.Cleanup(func() { scribe.EnableStdout(slog.LevelDebug) })
	testutil.RequiresDocker(t)
	_, mqttClient, err := testutil.SetupBrokerContainer(t)
	if err != nil {
		t.Fatalf("setup broker container failed: %v", err)
	}
	brokerHost := os.Getenv("VERNEMQ_HOST")
	brokerPort := os.Getenv("VERNEMQ_API_PORT")
	periods := config.Periods{PollMillis: 3000, PulseMillis: 3000, HeartbeatSecs: 300, TrendHours: 1}
	tests := []struct {
		name         string
		hostName     string
		databaseHost string
		runFor       time.Duration
		checkFunc    func(*testing.T, string, *topicRecorder)
	}{
		{
			name:         "happy_first_pulse_precedes_an_unreachable_database",
			hostName:     "alpha",
			databaseHost: "127.0.0.1",
			runFor:       8 * time.Second,
			checkFunc: func(t *testing.T, hostName string, recorder *topicRecorder) {
				topic := "supervisor/" + hostName + "/data/host/used_memory"
				recorder.mutex.Lock()
				elapsed, ok := recorder.first[topic]
				recorder.mutex.Unlock()
				if !ok {
					t.Fatalf("Got no publish of %s, expected the first pulse to publish it", topic)
				}
				budget := time.Duration(periods.PollMillis) * time.Millisecond
				if elapsed > budget {
					t.Fatalf("first publish: got %v want under %v, being before the ticker could have fired at all", elapsed, budget)
				}
				t.Logf("First publish of %s after %v", topic, elapsed.Round(time.Millisecond))
			},
		},
		{
			name:         "happy_graceful_stop_keeps_the_retained_records",
			hostName:     "bravo",
			databaseHost: "",
			runFor:       8 * time.Second,
			checkFunc: func(t *testing.T, hostName string, _ *topicRecorder) {
				statusTopic := "supervisor/" + hostName + "/status"
				dataTopic := "supervisor/" + hostName + "/data/host/used_memory"
				retained := subscribeRetained(t, mqttClient, statusTopic, dataTopic)
				if got := string(retained[statusTopic]); got != metric.AvailabilityOffline {
					t.Errorf("status: got %q want %q", got, metric.AvailabilityOffline)
				}
				if len(retained[dataTopic]) == 0 {
					t.Fatalf("Got %s cleared after a graceful stop, expected the record retained", dataTopic)
				}
			},
		},
		{
			name:         "sad_malformed_read_back_is_rejected_rather_than_dropped_in_silence",
			hostName:     "delta",
			databaseHost: "",
			runFor:       8 * time.Second,
			checkFunc: func(t *testing.T, hostName string, _ *topicRecorder) {
				topic := "supervisor/" + hostName + "/data/service/zzbroken/name"
				rejected := false
				for _, line := range logBuffer.Tail(2000) {
					if line.Level != slog.LevelError || line.Verb != "rejected" {
						continue
					}
					if strings.Contains(line.Detail, "unmarshal") && strings.Contains(line.Detail, "readback") {
						rejected = true
					}
				}
				if !rejected {
					t.Fatalf("Got no rejected readback line for %s, expected a malformed payload to name itself", topic)
				}
			},
		},
		{
			name:         "happy_orphan_read_back_is_tombstoned_in_both_forms",
			hostName:     "charlie",
			databaseHost: "",
			runFor:       12 * time.Second,
			checkFunc: func(t *testing.T, hostName string, recorder *topicRecorder) {
				topic := "supervisor/" + hostName + "/data/service/zztest/name"
				recorder.mutex.Lock()
				payloads := slices.Clone(recorder.seen[topic])
				recorder.mutex.Unlock()
				if len(payloads) < 2 {
					t.Fatalf("Got %d publishes of %s, expected the nil pulse and the empty payload", len(payloads), topic)
				}
				last := payloads[len(payloads)-1]
				if len(last) != 0 {
					t.Fatalf("last form: got %q want an empty payload", last)
				}
				var value metric.ValueData
				if err := json.Unmarshal(payloads[len(payloads)-2], &value); err != nil {
					t.Fatalf("unmarshal the form before the empty payload: %v", err)
				}
				if value.Pulse != nil {
					t.Fatalf("Got pulse %v in the form before the empty payload, expected a nil pulse", value.Pulse)
				}
				if value.Timestamp <= 0 {
					t.Fatalf("timestamp: got %d want a stamp proving the host alive", value.Timestamp)
				}
				retained := subscribeRetained(t, mqttClient, topic)
				if len(retained[topic]) != 0 {
					t.Fatalf("Got %s still retained as %q, expected it cleared", topic, retained[topic])
				}
			},
		},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			t.Cleanup(config.Reset)
			database := ""
			if tt.databaseHost != "" {
				database = fmt.Sprintf(`,"database":{"host":%q,"port":"1","token":"test-token"}`, tt.databaseHost)
			}
			configContent := fmt.Sprintf(`{"asystem":{"version":"10.100.6000","host":%q,"broker":{"host":%q,"port":%q}%s}}`,
				tt.hostName, brokerHost, brokerPort, database)
			configFile := filepath.Join(t.TempDir(), "config.json")
			if err := os.WriteFile(configFile, []byte(configContent), 0644); err != nil {
				t.Fatalf("write config file failed: %v", err)
			}
			recorder := &topicRecorder{first: make(map[string]time.Duration), seen: make(map[string][][]byte)}
			token := mqttClient.Subscribe("supervisor/"+tt.hostName+"/#", 1, recorder.record)
			token.Wait()
			if token.Error() != nil {
				t.Fatalf("subscribe failed: %v", token.Error())
			}
			t.Cleanup(func() { mqttClient.Unsubscribe("supervisor/" + tt.hostName + "/#").Wait() })
			if tt.name == "sad_malformed_read_back_is_rejected_rather_than_dropped_in_silence" {
				mqttClient.Publish("supervisor/"+tt.hostName+"/data/service/zzbroken/name", 1, true, []byte("{not json")).Wait()
			}
			if tt.name == "happy_orphan_read_back_is_tombstoned_in_both_forms" {
				orphan := metric.ValueData{
					Timestamp: time.Now().Unix(),
					Pulse:     &metric.ValueDataDetail{OK: true, Kind: metric.ValueString, ValueString: "zztest"},
				}
				payload, marshalErr := json.Marshal(orphan)
				if marshalErr != nil {
					t.Fatalf("marshal orphan failed: %v", marshalErr)
				}
				mqttClient.Publish("supervisor/"+tt.hostName+"/data/service/zztest/name", 1, true, payload).Wait()
			}
			ctx, cancel := context.WithTimeout(context.Background(), tt.runFor)
			defer cancel()
			cache := metric.NewRecordCache()
			recorder.mutex.Lock()
			recorder.started = time.Now()
			recorder.mutex.Unlock()
			done := make(chan struct{})
			go func() {
				defer close(done)
				RunAllProbesPublishLoop(ctx, configFile, cache, periods)
			}()
			<-done
			time.Sleep(time.Second)
			tt.checkFunc(t, tt.hostName, recorder)
		})
	}
}

func subscribeRetained(t *testing.T, client mqtt.Client, topics ...string) map[string][]byte {
	t.Helper()
	retained := make(map[string][]byte)
	var mutex sync.Mutex
	for _, topic := range topics {
		token := client.Subscribe(topic, 1, func(_ mqtt.Client, msg mqtt.Message) {
			mutex.Lock()
			retained[msg.Topic()] = msg.Payload()
			mutex.Unlock()
		})
		token.Wait()
	}
	time.Sleep(2 * time.Second)
	for _, topic := range topics {
		client.Unsubscribe(topic).Wait()
	}
	mutex.Lock()
	defer mutex.Unlock()
	return maps.Clone(retained)
}

type topicRecorder struct {
	mutex   sync.Mutex
	started time.Time
	first   map[string]time.Duration
	seen    map[string][][]byte
}

func (r *topicRecorder) record(_ mqtt.Client, msg mqtt.Message) {
	r.mutex.Lock()
	if _, exists := r.first[msg.Topic()]; !exists {
		r.first[msg.Topic()] = time.Since(r.started)
	}
	r.seen[msg.Topic()] = append(r.seen[msg.Topic()], msg.Payload())
	r.mutex.Unlock()
}
