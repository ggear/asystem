package schema

import (
	"reflect"
	"supervisor/testutil"
	"testing"
)

func TestSchema_Version(t *testing.T) {
	tests := []struct {
		name          string
		schemaPath    string
		expected      string
		expectedError bool
	}{
		{
			name:          "invalid_a_missing_file_1",
			schemaPath:    "non-existent-file.json",
			expectedError: true,
		},
		{
			name:          "invalid_corrupt_1",
			schemaPath:    testutil.SchemaPath(t, "schema-invalid-corrupt-1.json"),
			expectedError: true,
		},
		{
			name:          "invalid_corrupt_2",
			schemaPath:    testutil.SchemaPath(t, "schema-invalid-corrupt-2.json"),
			expectedError: true,
		},
		{
			name:          "invalid_corrupt_3",
			schemaPath:    testutil.SchemaPath(t, "schema-invalid-corrupt-3.json"),
			expectedError: true,
		},
		{
			name:          "invalid_corrupt_4",
			schemaPath:    testutil.SchemaPath(t, "schema-invalid-corrupt-4.json"),
			expectedError: true,
		},
		{
			name:          "invalid_corrupt_5",
			schemaPath:    testutil.SchemaPath(t, "schema-invalid-corrupt-5.json"),
			expectedError: true,
		},
		{
			name:          "invalid_corrupt_6",
			schemaPath:    testutil.SchemaPath(t, "schema-invalid-corrupt-6.json"),
			expectedError: true,
		},
		{
			name:          "invalid_corrupt_7",
			schemaPath:    testutil.SchemaPath(t, "schema-invalid-corrupt-7.json"),
			expectedError: true,
		},
		{
			name:          "invalid_duplicate_host_1",
			schemaPath:    testutil.SchemaPath(t, "schema-invalid-duplicate-host-1.json"),
			expected:      "10.100.6792",
			expectedError: true,
		},
		{
			name:          "invalid_duplicate_service_1",
			schemaPath:    testutil.SchemaPath(t, "schema-invalid-duplicate-service-1.json"),
			expected:      "10.100.6792",
			expectedError: true,
		},
		{
			name:          "invalid_empty_host_1",
			schemaPath:    testutil.SchemaPath(t, "schema-invalid-empty-host-1.json"),
			expectedError: true,
		},
		{
			name:          "invalid_empty_service_1",
			schemaPath:    testutil.SchemaPath(t, "schema-invalid-empty-service-1.json"),
			expectedError: true,
		},
		{
			name:          "valid_happy_1",
			schemaPath:    testutil.SchemaPath(t, "schema-valid-happy-1.json"),
			expected:      "10.100.6792",
			expectedError: false,
		},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			schema, err := Load(testCase.schemaPath)
			if (err != nil) != testCase.expectedError {
				t.Fatalf("Got err = %v, expected error? %t", err, testCase.expectedError)
			}
			if err == nil {
				version := schema.Version()
				if version != testCase.expected {
					t.Fatalf("Got version = %q, expected %q", version, testCase.expected)
				}
			}
		})
	}
}

func TestSchema_Hosts(t *testing.T) {
	tests := []struct {
		name          string
		schemaPath    string
		expected      []string
		expectedError bool
	}{
		{
			name:          "invalid_a_missing_file_1",
			schemaPath:    "non-existent-file.json",
			expectedError: true,
		},
		{
			name:          "invalid_corrupt_1",
			schemaPath:    testutil.SchemaPath(t, "schema-invalid-corrupt-1.json"),
			expectedError: true,
		},
		{
			name:          "invalid_corrupt_2",
			schemaPath:    testutil.SchemaPath(t, "schema-invalid-corrupt-2.json"),
			expectedError: true,
		},
		{
			name:          "invalid_corrupt_3",
			schemaPath:    testutil.SchemaPath(t, "schema-invalid-corrupt-3.json"),
			expectedError: true,
		},
		{
			name:          "invalid_duplicate_host_1",
			schemaPath:    testutil.SchemaPath(t, "schema-invalid-duplicate-host-1.json"),
			expected:      []string{"macmini-mad"},
			expectedError: true,
		},
		{
			name:          "invalid_duplicate_service_1",
			schemaPath:    testutil.SchemaPath(t, "schema-invalid-duplicate-service-1.json"),
			expected:      []string{"macmini-mad"},
			expectedError: true,
		},
		{
			name:          "invalid_empty_host_1",
			schemaPath:    testutil.SchemaPath(t, "schema-invalid-empty-host-1.json"),
			expectedError: true,
		},
		{
			name:          "invalid_empty_service_1",
			schemaPath:    testutil.SchemaPath(t, "schema-invalid-empty-service-1.json"),
			expectedError: true,
		},
		{
			name:          "valid_happy_1",
			schemaPath:    testutil.SchemaPath(t, "schema-valid-happy-1.json"),
			expected:      []string{"macmini-mad", "macmini-max", "macmini-may", "macmini-meg", "raspbpi-jen"},
			expectedError: false,
		},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			schema, err := Load(testCase.schemaPath)
			if (err != nil) != testCase.expectedError {
				t.Fatalf("Got err = %v, expected error? %t", err, testCase.expectedError)
			}
			if err == nil {
				hosts := schema.Hosts()
				if !reflect.DeepEqual(hosts, testCase.expected) {
					t.Fatalf("Got hosts = %v, expected %v", hosts, testCase.expected)
				}
			}
		})
	}
}

func TestSchema_Services(t *testing.T) {
	tests := []struct {
		name          string
		hostName      string
		schemaPath    string
		expected      []string
		expectedError bool
	}{
		{
			name:          "invalid_a_missing_file_1",
			schemaPath:    "non-existent-file.json",
			expectedError: true,
		},
		{
			name:          "invalid_corrupt_1",
			schemaPath:    testutil.SchemaPath(t, "schema-invalid-corrupt-1.json"),
			expectedError: true,
		},
		{
			name:          "invalid_duplicate_host_1",
			hostName:      "macmini-mad",
			schemaPath:    testutil.SchemaPath(t, "schema-invalid-duplicate-host-1.json"),
			expected:      []string{"monitor", "rhasspy"},
			expectedError: true,
		},
		{
			name:          "invalid_duplicate_service_1",
			hostName:      "macmini-mad",
			schemaPath:    testutil.SchemaPath(t, "schema-invalid-duplicate-service-1.json"),
			expected:      []string{"monitor"},
			expectedError: true,
		},
		{
			name:          "invalid_empty_host_1",
			hostName:      "macmini-mad",
			schemaPath:    testutil.SchemaPath(t, "schema-invalid-empty-host-1.json"),
			expected:      []string{},
			expectedError: true,
		},
		{
			name:          "invalid_empty_service_1",
			hostName:      "macmini-mad",
			schemaPath:    testutil.SchemaPath(t, "schema-invalid-empty-service-1.json"),
			expected:      []string{},
			expectedError: true,
		},
		{
			name:          "valid_macmini_mad_1",
			hostName:      "macmini-mad",
			schemaPath:    testutil.SchemaPath(t, "schema-valid-happy-1.json"),
			expected:      []string{"monitor", "plex", "sabnzbd"},
			expectedError: false,
		},
		{
			name:          "valid_non_existent_host_1",
			hostName:      "non-existent-host",
			schemaPath:    testutil.SchemaPath(t, "schema-valid-happy-1.json"),
			expected:      []string{},
			expectedError: false,
		},
		{
			name:          "valid_raspbpi_jen_1",
			hostName:      "raspbpi-jen",
			schemaPath:    testutil.SchemaPath(t, "schema-valid-happy-1.json"),
			expected:      []string{"monitor", "weewx", "zigbee2mqtt"},
			expectedError: false,
		},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			schema, err := Load(testCase.schemaPath)
			if (err != nil) != testCase.expectedError {
				t.Fatalf("Got err = %v, expected error? %t", err, testCase.expectedError)
			}
			if err == nil {
				services := schema.Services(testCase.hostName)
				if !reflect.DeepEqual(services, testCase.expected) {
					t.Fatalf("Got services = %v, expected %v", services, testCase.expected)
				}
			}
		})
	}
}
