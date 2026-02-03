package metric

import (
	"supervisor/testutil"
	"testing"
)

func TestMetric_CacheRemoteMetrics(t *testing.T) {
	_, client, err := testutil.SetupBrokerService(t)
	if err != nil {
		t.Fatalf("Got err = %v, expected nil", err)
	}
	tests := []struct {
		name          string
		schemaPath    string
		metrics       map[string][]Record
		expected      int
		expectedError bool
	}{
		{
			name:       "test_1",
			schemaPath: testutil.SchemaPath(t, "schema-valid-happy-1.json"),
			metrics: map[string][]Record{
				"host-1": {
					newMetricRecord("supervisor/host-1/host/compute/used_processor", "true", "10", "%"),
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
				snapshot, err := MarshalSnapshot(testCase.schemaPath, metrics)
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
	_, err := testutil.SetupSleepContainerWithHealth(t, []string{"sleep"})
	if err != nil {
		t.Fatalf("Got err = %v, expected nil", err)
	}
	tests := []struct {
		name          string
		hostname      string
		schemaPath    string
		expected      int
		expectedError bool
	}{
		{
			name:          "non_existent_file_1",
			schemaPath:    "non-existent-file.json",
			expected:      0,
			expectedError: true,
		},
		{
			name:          "valid_nil_host_1",
			schemaPath:    testutil.SchemaPath(t, "schema-valid-happy-1.json"),
			expected:      0,
			expectedError: true,
		},
		{
			name:          "valid_non_existent_host_1",
			hostname:      "non-existent-host",
			schemaPath:    testutil.SchemaPath(t, "schema-valid-happy-1.json"),
			expected:      19,
			expectedError: false,
		},
		{
			name:          "valid_macmini_mad_1",
			hostname:      "macmini-mad",
			schemaPath:    testutil.SchemaPath(t, "schema-valid-happy-1.json"),
			expected:      46,
			expectedError: false,
		},
		{
			name:          "valid_macmini_may_1",
			hostname:      "macmini-may",
			schemaPath:    testutil.SchemaPath(t, "schema-valid-happy-1.json"),
			expected:      91,
			expectedError: false,
		},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			cache, err := CacheLocalMetrics(testCase.hostname, testCase.schemaPath)
			t.Logf("Metric Record Local Cache:\n%s", cache)
			if (err != nil) != testCase.expectedError {
				t.Fatalf("Got err = %v, expected error? %t", err, testCase.expectedError)
			}
			if cache.Size() != testCase.expected {
				t.Fatalf("Got cache size = %d, expected %d", cache.Size(), testCase.expected)
			}
		})
	}
}
