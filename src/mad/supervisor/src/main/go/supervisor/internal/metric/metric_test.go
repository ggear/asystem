package metric

import (
	"supervisor/internal/testutil"
	"testing"
)

func TestMetric_CacheRemoteMetrics(t *testing.T) {
	_, client, err := testutil.SetupBrokerContainer(t)
	if err != nil {
		t.Fatalf("Got err = %v, expected nil", err)
	}
	tests := []struct {
		name          string
		configPath    string
		metrics       map[string][]Record
		expected      int
		expectedError bool
	}{
		{
			name:       "test_1",
			configPath: testutil.FindTestFile(t, "config-valid-happy-1.json", "config"),
			metrics: map[string][]Record{
				"host-1": {
					newMetricRecord("supervisor/host-1/host/depsCompute/used_processor", "true", "10", "%"),
					newMetricRecord("supervisor/host-1/host/storage/used_system_drive", "false", "100", "%"),
					newMetricRecord("supervisor/host-1/service/shortname/used_processor", "true", "50", "%"),
					newMetricRecord("supervisor/host-1/service/shortname/used_memory", "false", "100", "%"),
					newMetricRecord("supervisor/host-1/service/averyrealylongnamethatiscutoff/used_processor", "true,", "50", "%"),
					newMetricRecord("supervisor/host-1/service/averyrealylongnamethatiscutoff/used_memory", "false", "100", "%"),
				}},
			expected:      6,
			expectedError: false,
		},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			for host, metrics := range testCase.metrics {
				snapshot, err := MarshalSnapshot(testCase.configPath, metrics)
				if err != nil {
					t.Fatalf("Got err = %v, expected nil", err)
				}
				token := client.Publish("supervisor/"+host, 0, true, snapshot)
				token.Wait()
				if token.Error() != nil {
					t.Fatalf("Got token err = %v, expected nil", token.Error())
				}
			}
		})
	}
}

func TestMetric_CacheLocalMetrics(t *testing.T) {
	_, err := testutil.SetupSleepContainerWithHealth(t, "sleep")
	if err != nil {
		t.Fatalf("Got err = %v, expected nil", err)
	}
	tests := []struct {
		name          string
		hostname      string
		configPath    string
		expected      int
		expectedError bool
	}{
		{
			name:          "valid_non_existent_host_1",
			hostname:      "non-existent-host",
			configPath:    testutil.FindTestFile(t, "config-valid-happy-1.json", "config"),
			expected:      19,
			expectedError: false,
		},
		{
			name:          "valid_macmini_mad_1",
			hostname:      "macmini-mad",
			configPath:    testutil.FindTestFile(t, "config-valid-happy-1.json", "config"),
			expected:      46,
			expectedError: false,
		},
		{
			name:          "valid_macmini_may_1",
			hostname:      "macmini-may",
			configPath:    testutil.FindTestFile(t, "config-valid-happy-1.json", "config"),
			expected:      91,
			expectedError: false,
		},
		{
			name:          "non_existent_file_1",
			configPath:    "non-existent-file.json",
			expected:      0,
			expectedError: true,
		},
		{
			name:          "valid_nil_host_1",
			configPath:    testutil.FindTestFile(t, "config-valid-happy-1.json", "config"),
			expected:      0,
			expectedError: true,
		},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			cache, err := CacheLocalMetrics(testCase.hostname, testCase.configPath)
			t.Logf("ValueData Record Local Cache:\n%s", cache)
			if (err != nil) != testCase.expectedError {
				t.Fatalf("Got err = %v, expected error? %t", err, testCase.expectedError)
			}
			if cache.Size() != testCase.expected {
				t.Fatalf("Got cache size = %d, expected %d", cache.Size(), testCase.expected)
			}
		})
	}
}
