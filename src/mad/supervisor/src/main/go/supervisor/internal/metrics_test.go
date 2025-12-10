package internal

import (
	"supervisor/testutil"
	"testing"
)

func TestCacheMetrics(t *testing.T) {
	_, err := testutil.SetupTestContainer(t)
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
			metricCache, err := CacheMetrics(testCase.hostname, testCase.schemaPath)
			t.Logf("Metric Record Cache:\n%s", metricCache)
			if (err != nil) != testCase.expectError || metricCache.Size() != testCase.expected {
				t.Fatalf("CacheMetrics() = len(%v), %v; want len(%v), error? %v", metricCache.Size(), err, testCase.expected, testCase.expectError)
			}
		})
	}
}
