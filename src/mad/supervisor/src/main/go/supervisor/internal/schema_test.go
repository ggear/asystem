package internal

import (
	"reflect"
	"supervisor/testutil"
	"testing"
)

func TestGetVersion(t *testing.T) {
	tests := []struct {
		name        string
		schemaPath  string
		expected    string
		expectError bool
	}{
		{
			name:        "non-existent file 1",
			schemaPath:  "non-existent-file.json",
			expected:    "",
			expectError: true,
		},
		{
			name:        "invalid corrupt 1",
			schemaPath:  testutil.GetSchemaPath("schema-invalid-corrupt-1.json"),
			expected:    "",
			expectError: true,
		},
		{
			name:        "invalid missing keys 1",
			schemaPath:  testutil.GetSchemaPath("schema-invalid-missing-keys-1.json"),
			expected:    "",
			expectError: true,
		},
		{
			name:        "invalid missing keys 2",
			schemaPath:  testutil.GetSchemaPath("schema-invalid-missing-keys-2.json"),
			expected:    "",
			expectError: true,
		},
		{
			name:        "invalid value format 1",
			schemaPath:  testutil.GetSchemaPath("schema-invalid-value-format-1.json"),
			expected:    "",
			expectError: true,
		},
		{
			name:        "invalid value format 2",
			schemaPath:  testutil.GetSchemaPath("schema-invalid-value-format-2.json"),
			expected:    "",
			expectError: true,
		},
		{
			name:        "invalid value format 3",
			schemaPath:  testutil.GetSchemaPath("schema-invalid-value-format-3.json"),
			expected:    "",
			expectError: true,
		},
		{
			name:        "invalid value format 4",
			schemaPath:  testutil.GetSchemaPath("schema-invalid-value-format-4.json"),
			expected:    "",
			expectError: true,
		},
		{
			name:        "valid 1",
			schemaPath:  testutil.GetSchemaPath("schema-valid-1.json"),
			expected:    "10.100.6792",
			expectError: false,
		},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			version, err := GetVersion(testCase.schemaPath)
			if (err != nil) != testCase.expectError || version != testCase.expected {
				t.Fatalf("GetVersion() = %v, %v; want %v, error? %v", version, err, testCase.expected, testCase.expectError)
			}
		})
	}
}

func TestGetServices(t *testing.T) {
	_, err := testutil.SetupTestContainer(t)
	if err != nil {
		t.Fatalf("Could not start container: %v", err)
	}
	tests := []struct {
		name        string
		hostname    string
		schemaPath  string
		expected    []string
		expectError bool
	}{
		{
			name:        "non-existent file 1",
			schemaPath:  "non-existent-file.json",
			expected:    nil,
			expectError: true,
		},
		{
			name:        "invalid corrupt 1",
			schemaPath:  testutil.GetSchemaPath("schema-invalid-corrupt-1.json"),
			expected:    nil,
			expectError: true,
		},
		{
			name:        "invalid missing keys 1",
			schemaPath:  testutil.GetSchemaPath("schema-invalid-missing-keys-1.json"),
			expected:    nil,
			expectError: true,
		},
		{
			name:        "invalid missing keys 2",
			schemaPath:  testutil.GetSchemaPath("schema-invalid-missing-keys-2.json"),
			expected:    nil,
			expectError: true,
		},
		{
			name:        "invalid value format 1",
			schemaPath:  testutil.GetSchemaPath("schema-invalid-value-format-1.json"),
			expected:    nil,
			expectError: true,
		},
		{
			name:        "invalid value format 2",
			schemaPath:  testutil.GetSchemaPath("schema-invalid-value-format-2.json"),
			expected:    nil,
			expectError: true,
		},
		{
			name:        "invalid value format 3",
			schemaPath:  testutil.GetSchemaPath("schema-invalid-value-format-3.json"),
			expected:    nil,
			expectError: true,
		},
		{
			name:        "invalid value format 4",
			schemaPath:  testutil.GetSchemaPath("schema-invalid-value-format-4.json"),
			expected:    nil,
			expectError: true,
		},
		{
			name:        "valid nil-host 1",
			schemaPath:  testutil.GetSchemaPath("schema-valid-1.json"),
			expected:    []string{},
			expectError: false,
		},
		{
			name:        "valid non-existent-host 1",
			hostname:    "non-existent-host",
			schemaPath:  testutil.GetSchemaPath("schema-valid-1.json"),
			expected:    []string{},
			expectError: false,
		},
		{
			name:        "valid macmini-mad 1",
			hostname:    "macmini-mad",
			schemaPath:  testutil.GetSchemaPath("schema-valid-1.json"),
			expected:    []string{"monitor", "plex", "sabnzbd", "sleep"},
			expectError: false,
		},
		{
			name:        "valid raspbpi-jen 1",
			hostname:    "raspbpi-jen",
			schemaPath:  testutil.GetSchemaPath("schema-valid-1.json"),
			expected:    []string{"monitor", "sleep", "weewx", "zigbee2mqtt"},
			expectError: false,
		},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			serviceSlice, err := GetServices(testCase.hostname, testCase.schemaPath)
			if (err != nil) != testCase.expectError || !reflect.DeepEqual(serviceSlice, testCase.expected) {
				t.Fatalf("GetServices() = %v, %v; want %v, error? %v", serviceSlice, err, testCase.expected, testCase.expectError)
			}
		})
	}
}
