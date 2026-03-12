package engine

import (
	"context"
	"fmt"
	"log/slog"
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
