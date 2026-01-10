package internal

import (
	"supervisor/testutil"
	"testing"
)

func TestCacheRemoteMetrics(t *testing.T) {
	_, client, err := testutil.SetupBrokerService(t)
	if err != nil {
		t.Fatalf("Could not start container: %v", err)
	}
	tests := []struct {
		name        string
		schemaPath  string
		metrics     map[string][]metricRecord
		expected    int
		expectError bool
	}{
		// TODO: Add tests, test against a serialisation - string/json?
		{
			name:       "test 1",
			schemaPath: testutil.GetSchemaPath(t, "schema-valid-1.json"),
			metrics: map[string][]metricRecord{"host-1": []metricRecord{
				{Topic: "supervisor/host-1/host/compute/used_processor", Value: metricValue{OK: true, Value: "10", Unit: "%"}},
				{Topic: "supervisor/host-1/host/storage/used_system_drive", Value: metricValue{OK: false, Value: "100", Unit: "%"}},
				{Topic: "supervisor/host-1/service/shortname/used_processor", Value: metricValue{OK: true, Value: "50", Unit: "%"}},
				{Topic: "supervisor/host-1/service/shortname/used_memory", Value: metricValue{OK: false, Value: "100", Unit: "%"}},
				{Topic: "supervisor/host-1/service/averyrealylongnamethatiscutoff/used_processor", Value: metricValue{OK: true, Value: "50", Unit: "%"}},
				{Topic: "supervisor/host-1/service/averyrealylongnamethatiscutoff/used_memory", Value: metricValue{OK: false, Value: "100", Unit: "%"}},
			}},
			expected:    6,
			expectError: false,
		},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			for host, metrics := range testCase.metrics {
				snapshot, err := MarshalSnapshot(testCase.schemaPath, metrics)
				if err != nil {
					t.Fatalf("MarshalSnapshot() failed: %v", err)
				}
				token := client.Publish("supervisor/"+host, 0, true, snapshot)
				token.Wait()
				if token.Error() != nil {
					t.Fatalf("Failed to publish MQTT message: %v", token.Error())
				}
			}

			//snapshotBytes, err := MarshalSnapshot(testCase.schemaPath, testCase.metrics["host-1"])
			//if err != nil {
			//	t.Fatalf("MarshalSnapshot() failed: %v", err)
			//}
			//
			//snapshot, err := UnmarshalSnapshot(snapshotBytes)
			//if err != nil {
			//	t.Fatalf("UnmarshalSnapshot() failed: %v", err)
			//}
			//cache, err := CacheRemoteMetrics(snapshot.Metrics)
			//
			//t.Logf("Metric Record Remote Cache:\n%s", cache)
			//if (err != nil) != testCase.expectError || cache.Size() != testCase.expected {
			//	t.Fatalf("CacheRemoteMetrics() = len(%v), %v; want len(%v), error? %v", cache.Size(), err, testCase.expected, testCase.expectError)
			//}
		})
	}
}

func TestCacheLocalMetrics(t *testing.T) {
	_, err := testutil.SetupSleepContainer(t)
	if err != nil {
		t.Fatalf("Could not start container: %v", err)
	}
	tests := []struct {
		name        string
		hostname    string
		schemaPath  string
		expected    int
		expectError bool
	}{
		{
			name:        "non-existent file 1",
			schemaPath:  "non-existent-file.json",
			expected:    0,
			expectError: true,
		},
		{
			name:        "valid nil-host 1",
			schemaPath:  testutil.GetSchemaPath(t, "schema-valid-1.json"),
			expected:    0,
			expectError: true,
		},
		{
			name:        "valid non-existent-host 1",
			hostname:    "non-existent-host",
			schemaPath:  testutil.GetSchemaPath(t, "schema-valid-1.json"),
			expected:    19,
			expectError: false,
		},
		{
			name:        "valid macmini-mad 1",
			hostname:    "macmini-mad",
			schemaPath:  testutil.GetSchemaPath(t, "schema-valid-1.json"),
			expected:    51,
			expectError: false,
		},
		{
			name:        "valid macmini-may 1",
			hostname:    "macmini-may",
			schemaPath:  testutil.GetSchemaPath(t, "schema-valid-1.json"),
			expected:    91,
			expectError: false,
		},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			cache, err := CacheLocalMetrics(testCase.hostname, testCase.schemaPath)
			t.Logf("Metric Record Local Cache:\n%s", cache)
			if (err != nil) != testCase.expectError || cache.Size() != testCase.expected {
				t.Fatalf("CacheLocalMetrics() = len(%v), %v; want len(%v), error? %v", cache.Size(), err, testCase.expected, testCase.expectError)
			}
		})
	}
}
