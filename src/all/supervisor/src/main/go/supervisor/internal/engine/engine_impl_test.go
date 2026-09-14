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
)

func TestEngineImpl_RunAllProbesOnce(t *testing.T) {
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
