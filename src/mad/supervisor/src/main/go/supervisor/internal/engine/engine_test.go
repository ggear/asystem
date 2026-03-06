package engine

import (
	"fmt"
	"log/slog"
	"supervisor/internal/config"
	"supervisor/internal/metric"
	"supervisor/internal/scribe"
	"supervisor/internal/testutil"
	"testing"
)

func TestEngine_LoadAllProbesOnce(t *testing.T) {
	tests := []struct {
		name                string
		hostName            string
		configPath          string
		createServiceCount  int
		expectedRecordCount int
		expectedError       bool
	}{
		{
			name:                "happy_no_services",
			hostName:            "macmini-mad",
			configPath:          testutil.FindTestFile(t, "config-happy-noservices-1.json", "config"),
			createServiceCount:  0,
			expectedRecordCount: metricCountHost + metricCountService*0,
			expectedError:       false,
		},
		{
			name:                "happy_one_service",
			hostName:            "macmini-mad",
			configPath:          testutil.FindTestFile(t, "config-happy-noservices-1.json", "config"),
			createServiceCount:  1,
			expectedRecordCount: metricCountHost + metricCountService*1,
			expectedError:       false,
		},
		{
			name:                "happy_three_services_prod_like",
			hostName:            "macmini-mad",
			configPath:          testutil.FindTestFile(t, "config-happy-prodlike-1.json", "config"),
			createServiceCount:  3,
			expectedRecordCount: metricCountHost + metricCountService*6,
			expectedError:       false,
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
				var serviceNames []string
				for i := 0; i < tt.createServiceCount; i++ {
					serviceNames = append(serviceNames, fmt.Sprintf("loader-%d", i+1))
				}
				_, err := testutil.SetupSleepContainer(t, "", false, serviceNames...)
				if err != nil {
					t.Fatalf("setup sleep container failed: %v", err)
				}
			}
			cache := metric.NewRecordCache()
			err := LoadAllProbesOnce(tt.configPath, cache)
			t.Logf("Cache:\n%s", cache.String())
			if tt.expectedError {
				if err == nil {
					t.Fatalf("expected error but got nil")
				}
			} else if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
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
