package config

import (
	"reflect"
	"supervisor/internal/testutil"
	"testing"
)

func TestConfig_Version(t *testing.T) {
	tests := []struct {
		name          string
		configPath    string
		expected      string
		expectedError bool
	}{
		{
			name:          "happy_1",
			configPath:    testutil.FindTestFile(t, "config-valid-happy-1.json", "config"),
			expected:      "10.100.6792",
			expectedError: false,
		},
		{
			name:          "sad_a_missing_file_1",
			configPath:    "non-existent-file.json",
			expectedError: true,
		},
		{
			name:          "sad_corrupt_1",
			configPath:    testutil.FindTestFile(t, "config-invalid-corrupt-1.json", "config"),
			expectedError: true,
		},
		{
			name:          "sad_corrupt_2",
			configPath:    testutil.FindTestFile(t, "config-invalid-corrupt-2.json", "config"),
			expectedError: true,
		},
		{
			name:          "sad_corrupt_3",
			configPath:    testutil.FindTestFile(t, "config-invalid-corrupt-3.json", "config"),
			expectedError: true,
		},
		{
			name:          "sad_corrupt_4",
			configPath:    testutil.FindTestFile(t, "config-invalid-corrupt-4.json", "config"),
			expectedError: true,
		},
		{
			name:          "sad_corrupt_5",
			configPath:    testutil.FindTestFile(t, "config-invalid-corrupt-5.json", "config"),
			expectedError: true,
		},
		{
			name:          "sad_corrupt_6",
			configPath:    testutil.FindTestFile(t, "config-invalid-corrupt-6.json", "config"),
			expectedError: true,
		},
		{
			name:          "sad_corrupt_7",
			configPath:    testutil.FindTestFile(t, "config-invalid-corrupt-7.json", "config"),
			expectedError: true,
		},
		{
			name:          "sad_duplicate_host_1",
			configPath:    testutil.FindTestFile(t, "config-invalid-duplicate-host-1.json", "config"),
			expected:      "10.100.6792",
			expectedError: true,
		},
		{
			name:          "sad_duplicate_service_1",
			configPath:    testutil.FindTestFile(t, "config-invalid-duplicate-service-1.json", "config"),
			expected:      "10.100.6792",
			expectedError: true,
		},
		{
			name:          "sad_empty_host_1",
			configPath:    testutil.FindTestFile(t, "config-invalid-empty-host-1.json", "config"),
			expectedError: true,
		},
		{
			name:          "sad_empty_service_1",
			configPath:    testutil.FindTestFile(t, "config-invalid-empty-service-1.json", "config"),
			expectedError: true,
		},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			config, err := Load(testCase.configPath)
			if (err != nil) != testCase.expectedError {
				t.Fatalf("Got err = %v, expected error? %t", err, testCase.expectedError)
			}
			if err == nil {
				version := config.Version()
				if version != testCase.expected {
					t.Fatalf("Got version = %q, expected %q", version, testCase.expected)
				}
			}
		})
	}
}

func TestConfig_Hosts(t *testing.T) {
	tests := []struct {
		name          string
		configPath    string
		expected      []string
		expectedError bool
	}{
		{
			name:          "happy_1",
			configPath:    testutil.FindTestFile(t, "config-valid-happy-1.json", "config"),
			expected:      []string{"macmini-mad", "macmini-max", "macmini-may", "macmini-meg", "raspbpi-jen"},
			expectedError: false,
		},
		{
			name:          "sad_a_missing_file_1",
			configPath:    "non-existent-file.json",
			expectedError: true,
		},
		{
			name:          "sad_corrupt_1",
			configPath:    testutil.FindTestFile(t, "config-invalid-corrupt-1.json", "config"),
			expectedError: true,
		},
		{
			name:          "sad_corrupt_2",
			configPath:    testutil.FindTestFile(t, "config-invalid-corrupt-2.json", "config"),
			expectedError: true,
		},
		{
			name:          "sad_corrupt_3",
			configPath:    testutil.FindTestFile(t, "config-invalid-corrupt-3.json", "config"),
			expectedError: true,
		},
		{
			name:          "sad_duplicate_host_1",
			configPath:    testutil.FindTestFile(t, "config-invalid-duplicate-host-1.json", "config"),
			expected:      []string{"macmini-mad"},
			expectedError: true,
		},
		{
			name:          "sad_duplicate_service_1",
			configPath:    testutil.FindTestFile(t, "config-invalid-duplicate-service-1.json", "config"),
			expected:      []string{"macmini-mad"},
			expectedError: true,
		},
		{
			name:          "sad_empty_host_1",
			configPath:    testutil.FindTestFile(t, "config-invalid-empty-host-1.json", "config"),
			expectedError: true,
		},
		{
			name:          "sad_empty_service_1",
			configPath:    testutil.FindTestFile(t, "config-invalid-empty-service-1.json", "config"),
			expectedError: true,
		},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			config, err := Load(testCase.configPath)
			if (err != nil) != testCase.expectedError {
				t.Fatalf("Got err = %v, expected error? %t", err, testCase.expectedError)
			}
			if err == nil {
				hosts := config.Hosts()
				if !reflect.DeepEqual(hosts, testCase.expected) {
					t.Fatalf("Got hosts = %v, expected %v", hosts, testCase.expected)
				}
			}
		})
	}
}

func TestConfig_Services(t *testing.T) {
	tests := []struct {
		name          string
		hostName      string
		configPath    string
		expected      []string
		expectedError bool
	}{
		{
			name:          "happy_macmini_mad_1",
			hostName:      "macmini-mad",
			configPath:    testutil.FindTestFile(t, "config-valid-happy-1.json", "config"),
			expected:      []string{"monitor", "plex", "sabnzbd"},
			expectedError: false,
		},
		{
			name:          "happy_non_existent_host_1",
			hostName:      "non-existent-host",
			configPath:    testutil.FindTestFile(t, "config-valid-happy-1.json", "config"),
			expected:      []string{},
			expectedError: false,
		},
		{
			name:          "happy_raspbpi_jen_1",
			hostName:      "raspbpi-jen",
			configPath:    testutil.FindTestFile(t, "config-valid-happy-1.json", "config"),
			expected:      []string{"monitor", "weewx", "zigbee2mqtt"},
			expectedError: false,
		},
		{
			name:          "sad_a_missing_file_1",
			configPath:    "non-existent-file.json",
			expectedError: true,
		},
		{
			name:          "sad_corrupt_1",
			configPath:    testutil.FindTestFile(t, "config-invalid-corrupt-1.json", "config"),
			expectedError: true,
		},
		{
			name:          "sad_duplicate_host_1",
			hostName:      "macmini-mad",
			configPath:    testutil.FindTestFile(t, "config-invalid-duplicate-host-1.json", "config"),
			expected:      []string{"monitor", "rhasspy"},
			expectedError: true,
		},
		{
			name:          "sad_duplicate_service_1",
			hostName:      "macmini-mad",
			configPath:    testutil.FindTestFile(t, "config-invalid-duplicate-service-1.json", "config"),
			expected:      []string{"monitor"},
			expectedError: true,
		},
		{
			name:          "sad_empty_host_1",
			hostName:      "macmini-mad",
			configPath:    testutil.FindTestFile(t, "config-invalid-empty-host-1.json", "config"),
			expected:      []string{},
			expectedError: true,
		},
		{
			name:          "sad_empty_service_1",
			hostName:      "macmini-mad",
			configPath:    testutil.FindTestFile(t, "config-invalid-empty-service-1.json", "config"),
			expected:      []string{},
			expectedError: true,
		},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			config, err := Load(testCase.configPath)
			if (err != nil) != testCase.expectedError {
				t.Fatalf("Got err = %v, expected error? %t", err, testCase.expectedError)
			}
			if err == nil {
				services := config.Services(testCase.hostName)
				if !reflect.DeepEqual(services, testCase.expected) {
					t.Fatalf("Got services = %v, expected %v", services, testCase.expected)
				}
			}
		})
	}
}
