package engine

import (
	"context"
	"encoding/json"
	"fmt"
	"log/slog"
	"os"
	"path/filepath"
	"supervisor/internal/config"
	"supervisor/internal/metric"
	"supervisor/internal/scribe"
	"supervisor/internal/testutil"
	"testing"
	"time"
)

func TestEngine_RunAllProbesOnce(t *testing.T) {
	tests := []struct {
		name                string
		hostName            string
		configPath          string
		createServiceCount  int
		expectedRecordCount int
	}{
		{
			name:                "happy_no_services",
			hostName:            "macmini-mad",
			configPath:          testutil.FindTestFile(t, "config-happy-noservices-1.json", "config"),
			createServiceCount:  0,
			expectedRecordCount: metricCountHost + metricCountService*0,
		},
		{
			name:                "happy_one_service",
			hostName:            "macmini-mad",
			configPath:          testutil.FindTestFile(t, "config-happy-noservices-1.json", "config"),
			createServiceCount:  1,
			expectedRecordCount: metricCountHost + metricCountService*1,
		},
		{
			name:                "happy_three_services_prod_like",
			hostName:            "macmini-mad",
			configPath:          testutil.FindTestFile(t, "config-happy-prodlike-1.json", "config"),
			createServiceCount:  3,
			expectedRecordCount: metricCountHost + metricCountService*6,
		},
	}
	scribe.EnableStdout(slog.LevelDebug)
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			testutil.RequiresDocker(t)
			orig := config.LocalHostName
			config.LocalHostName = func() string { return tt.hostName }
			t.Cleanup(func() { config.LocalHostName = orig })
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
			if cache.Size() != tt.expectedRecordCount {
				t.Fatalf("expected %d records, got %d", tt.expectedRecordCount, cache.Size())
			}
		})
	}
}

func TestEngine_RunListeningProbesLoop(t *testing.T) {
	tests := []struct {
		name                string
		hostName            string
		metricIds           []metric.ID
		serviceMetricIDs    []metric.ID
		configPath          string
		createServiceCount  int
		expectedRecordCount int
	}{
		{
			name:                "happy_no_services",
			hostName:            "macmini-mad",
			metricIds:           []metric.ID{metric.MetricHostUsedProcessor, metric.MetricHostUsedMemory},
			serviceMetricIDs:    []metric.ID{metric.MetricServiceUsedProcessor, metric.MetricServiceUsedMemory},
			configPath:          testutil.FindTestFile(t, "config-happy-noservices-1.json", "config"),
			createServiceCount:  0,
			expectedRecordCount: 2 + 2*0,
		},
		{
			name:                "happy_one_service",
			hostName:            "macmini-mad",
			metricIds:           []metric.ID{metric.MetricHostUsedProcessor, metric.MetricHostUsedMemory},
			serviceMetricIDs:    []metric.ID{metric.MetricServiceUsedProcessor, metric.MetricServiceUsedMemory},
			configPath:          testutil.FindTestFile(t, "config-happy-noservices-1.json", "config"),
			createServiceCount:  1,
			expectedRecordCount: 2 + 2*1,
		},
		{
			name:                "happy_three_services_prod_like",
			hostName:            "macmini-mad",
			metricIds:           []metric.ID{metric.MetricHostUsedProcessor, metric.MetricHostUsedMemory},
			serviceMetricIDs:    []metric.ID{metric.MetricServiceUsedProcessor, metric.MetricServiceUsedMemory},
			configPath:          testutil.FindTestFile(t, "config-happy-prodlike-1.json", "config"),
			createServiceCount:  3,
			expectedRecordCount: 2 + 2*6,
		},
	}
	scribe.EnableStdout(slog.LevelDebug)
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			testutil.RequiresDocker(t)
			orig := config.LocalHostName
			config.LocalHostName = func() string { return tt.hostName }
			t.Cleanup(func() { config.LocalHostName = orig })
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
				CacheHours:   0,
				SnapshotMins: 0,
			}
			timeout := time.Duration(4*periods.PollMillis) * time.Millisecond
			ctx, cancel := context.WithTimeout(context.Background(), timeout)
			defer cancel()
			RunListeningProbesLoop(ctx, tt.configPath, cache, periods)
			t.Logf("Cache:\n%s", cache.String())
			if cache.Size() != tt.expectedRecordCount {
				t.Fatalf("expected %d records, got %d", tt.expectedRecordCount, cache.Size())
			}
		})
	}
}

var (
	metricCountHost    = len(metric.GetIDs()) - metricCountService
	metricCountService = len(metric.GetIDsByKind([]metric.MetricKind{metric.MetricKindService}))
)

type mockUpdatesListener struct{}

func (m *mockUpdatesListener) MarkDirty() {}

func TestEngine_HostStatus(t *testing.T) {
	value := metric.ValueData{Timestamp: time.Now().Unix(), Pulse: &metric.ValueDataDetail{OK: true, Kind: metric.ValueString, ValueString: "v"}}
	tests := []struct {
		name           string
		setupFunc      func()
		checkFunc      func(*testing.T)
		expectedError  bool
	}{
		{
			name: "happy_unknown_host_is_online",
			setupFunc: func() {
				hostStatusMutex.Lock()
				hostStatus = make(map[string]bool)
				hostStatusMutex.Unlock()
			},
			checkFunc: func(t *testing.T) {
				if !isHostOnline("unknown-host") {
					t.Fatalf("Got offline, expected unknown host to be treated as online")
				}
			},
			expectedError: false,
		},
		{
			name: "happy_set_online",
			setupFunc: func() {
				hostStatusMutex.Lock()
				hostStatus = make(map[string]bool)
				hostStatusMutex.Unlock()
				storeHostStatus("alpha", true)
			},
			checkFunc: func(t *testing.T) {
				if !isHostOnline("alpha") {
					t.Fatalf("Got offline, expected online after storeHostStatus true")
				}
			},
			expectedError: false,
		},
		{
			name: "happy_set_offline",
			setupFunc: func() {
				hostStatusMutex.Lock()
				hostStatus = make(map[string]bool)
				hostStatusMutex.Unlock()
				storeHostStatus("alpha", false)
			},
			checkFunc: func(t *testing.T) {
				if isHostOnline("alpha") {
					t.Fatalf("Got online, expected offline after storeHostStatus false")
				}
			},
			expectedError: false,
		},
		{
			name: "happy_offline_evicts_service_metrics",
			setupFunc: func() {
				hostStatusMutex.Lock()
				hostStatus = make(map[string]bool)
				hostStatusMutex.Unlock()
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
				hostStatusMutex.Lock()
				hostStatus = make(map[string]bool)
				hostStatusMutex.Unlock()
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
				hostStatusMutex.Lock()
				hostStatus = make(map[string]bool)
				hostStatusMutex.Unlock()
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
				hostStatusMutex.Lock()
				hostStatus = make(map[string]bool)
				hostStatusMutex.Unlock()
				storeHostStatus("alpha", true)
			},
			checkFunc: func(t *testing.T) {
				if !isHostOnline("alpha") {
					t.Fatalf("Got offline, expected online host to allow stores")
				}
			},
			expectedError: false,
		},
		{
			name: "happy_offline_blocks_store",
			setupFunc: func() {
				hostStatusMutex.Lock()
				hostStatus = make(map[string]bool)
				hostStatusMutex.Unlock()
				storeHostStatus("alpha", false)
			},
			checkFunc: func(t *testing.T) {
				if isHostOnline("alpha") {
					t.Fatalf("Got online, expected offline host to block stores")
				}
			},
			expectedError: false,
		},
		{
			name: "happy_online_after_offline_allows_store",
			setupFunc: func() {
				hostStatusMutex.Lock()
				hostStatus = make(map[string]bool)
				hostStatusMutex.Unlock()
				storeHostStatus("alpha", false)
				storeHostStatus("alpha", true)
			},
			checkFunc: func(t *testing.T) {
				if !isHostOnline("alpha") {
					t.Fatalf("Got offline, expected online after transitioning offline→online")
				}
			},
			expectedError: false,
		},
		{
			name: "happy_stale_offline_cleared_on_restart",
			setupFunc: func() {
				hostStatusMutex.Lock()
				hostStatus = make(map[string]bool)
				hostStatusMutex.Unlock()
				storeHostStatus("alpha", false)
			},
			checkFunc: func(t *testing.T) {
				hostStatusMutex.Lock()
				hostStatus = make(map[string]bool)
				hostStatusMutex.Unlock()
				if !isHostOnline("alpha") {
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
	configContent := fmt.Sprintf(`{"asystem":{"version":"10.100.6000","broker":{"host":%q,"port":%q},"database":{"host":"db.local","port":"2000"}}}`, host, port)
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
	tests := []struct {
		name      string
		setupFunc func(*testing.T, *metric.RecordCache, metric.TopicBinding) []byte
		checkFunc func(*testing.T, *metric.RecordCache, metric.TopicBinding)
	}{
		{
			name: "happy_nil_mqtt_value_evicts_service",
			setupFunc: func(_ *testing.T, _ *metric.RecordCache, _ metric.TopicBinding) []byte {
				return []byte(`{}`)
			},
			checkFunc: func(t *testing.T, cache *metric.RecordCache, b metric.TopicBinding) {
				deadline := time.Now().Add(3 * time.Second)
				for time.Now().Before(deadline) {
					record, ok := cache.Load(b.GUID)
					if ok && record != nil && record.Value.Pulse == nil {
						return
					}
					time.Sleep(50 * time.Millisecond)
				}
				t.Fatalf("Got non-nil pulse after nil publish, expected service evicted to nil")
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
			ctx, cancel := context.WithTimeout(context.Background(), 8*time.Second)
			defer cancel()
			done := make(chan struct{})
			go func() {
				defer close(done)
				RunListeningStreamLoop(ctx, configFile, cache, periods)
			}()
			time.Sleep(500 * time.Millisecond)
			payload := tt.setupFunc(t, cache, binding)
			mqttClient.Publish(binding.Topic, 0, false, payload)
			tt.checkFunc(t, cache, binding)
			cancel()
			<-done
		})
	}
}
