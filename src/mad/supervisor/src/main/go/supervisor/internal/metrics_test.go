package internal

import (
	"supervisor/testutil"
	"testing"
)

func TestCacheRemoteMetrics(t *testing.T) {
	_, _, err := testutil.SetupBrokerService(t)
	if err != nil {
		t.Fatalf("Could not start container: %v", err)
	}
	tests := []struct {
		name        string
		expected    int
		expectError bool
	}{
		{
			name:        "test 1",
			expected:    0,
			expectError: false,
		},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			cache, err := CacheRemoteMetrics(nil)
			t.Logf("Metric Record Remote Cache:\n%s", cache)
			if (err != nil) != testCase.expectError || cache.Size() != testCase.expected {
				t.Fatalf("CacheRemoteMetrics() = len(%v), %v; want len(%v), error? %v", cache.Size(), err, testCase.expected, testCase.expectError)
			}
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
			schemaPath:  testutil.GetSchemaPath("schema-valid-1.json"),
			expected:    0,
			expectError: true,
		},
		{
			name:        "valid non-existent-host 1",
			hostname:    "non-existent-host",
			schemaPath:  testutil.GetSchemaPath("schema-valid-1.json"),
			expected:    18,
			expectError: false,
		},
		{
			name:        "valid macmini-mad 1",
			hostname:    "macmini-mad",
			schemaPath:  testutil.GetSchemaPath("schema-valid-1.json"),
			expected:    50,
			expectError: false,
		},
		{
			name:        "valid macmini-may 1",
			hostname:    "macmini-may",
			schemaPath:  testutil.GetSchemaPath("schema-valid-1.json"),
			expected:    90,
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
