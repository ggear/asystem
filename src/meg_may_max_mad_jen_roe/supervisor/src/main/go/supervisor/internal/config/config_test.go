package config

import (
	"os"
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
			name:          "happy_production_like_1",
			configPath:    testutil.FindTestFile(t, "config-happy-prodlike-1.json", "config"),
			expected:      "10.100.6792",
			expectedError: false,
		},
		{
			name:          "happy_noschema_1",
			configPath:    testutil.FindTestFile(t, "config-happy-noschema-1.json", "config"),
			expected:      "10.100.6792",
			expectedError: false,
		},
		{
			name:          "happy_noservices_1",
			configPath:    testutil.FindTestFile(t, "config-happy-noservices-1.json", "config"),
			expected:      "10.100.6792",
			expectedError: false,
		},
		{
			name:          "happy_missing_file_defaults_version",
			configPath:    "non-existent-file.json",
			expected:      defaultVersion,
			expectedError: false,
		},
		{
			name:          "happy_corrupt_invalid_json_defaults_version",
			configPath:    testutil.FindTestFile(t, "config-sad-corrupt-1.json", "config"),
			expected:      defaultVersion,
			expectedError: false,
		},
		{
			name:          "happy_corrupt_empty_obj_defaults_version",
			configPath:    testutil.FindTestFile(t, "config-sad-corrupt-2.json", "config"),
			expected:      defaultVersion,
			expectedError: false,
		},
		{
			name:          "happy_corrupt_empty_asystem_defaults_version",
			configPath:    testutil.FindTestFile(t, "config-sad-corrupt-3.json", "config"),
			expected:      defaultVersion,
			expectedError: false,
		},
		{
			name:          "happy_corrupt_snapshot_version_preserved",
			configPath:    testutil.FindTestFile(t, "config-sad-corrupt-4.json", "config"),
			expected:      "10.100.6792-SNAPSHOT",
			expectedError: false,
		},
		{
			name:          "happy_corrupt_invalid_semver_defaults_version",
			configPath:    testutil.FindTestFile(t, "config-sad-corrupt-5.json", "config"),
			expected:      defaultVersion,
			expectedError: false,
		},
		{
			name:          "happy_corrupt_array_version_defaults_version",
			configPath:    testutil.FindTestFile(t, "config-sad-corrupt-6.json", "config"),
			expected:      defaultVersion,
			expectedError: false,
		},
		{
			name:          "happy_corrupt_empty_version_defaults_version",
			configPath:    testutil.FindTestFile(t, "config-sad-corrupt-7.json", "config"),
			expected:      defaultVersion,
			expectedError: false,
		},
		{
			name:          "happy_duplicate_host_version_preserved",
			configPath:    testutil.FindTestFile(t, "config-sad-duplicate-host-1.json", "config"),
			expected:      "10.100.6792",
			expectedError: false,
		},
		{
			name:          "happy_duplicate_service_version_preserved",
			configPath:    testutil.FindTestFile(t, "config-sad-duplicate-service-1.json", "config"),
			expected:      "10.100.6792",
			expectedError: false,
		},
		{
			name:          "happy_empty_schema_host_version_preserved",
			configPath:    testutil.FindTestFile(t, "config-sad-empty-host-1.json", "config"),
			expected:      "10.100.6792",
			expectedError: false,
		},
		{
			name:          "happy_empty_schema_service_version_preserved",
			configPath:    testutil.FindTestFile(t, "config-sad-empty-service-1.json", "config"),
			expected:      "10.100.6792",
			expectedError: false,
		},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			t.Cleanup(Reset)
			config := Load(testCase.configPath)
			if testCase.expectedError {
				t.Fatalf("Got no error, expected error for %s", testCase.name)
			}
			version := config.Version()
			if version != testCase.expected {
				t.Fatalf("Got version = %q, expected %q", version, testCase.expected)
			}
		})
	}
}

func TestConfig_Host(t *testing.T) {
	hostname, err := os.Hostname()
	if err != nil {
		t.Fatalf("os.Hostname failed: %v", err)
	}
	tests := []struct {
		name          string
		configPath    string
		envHost       string
		expected      string
		expectedError bool
	}{
		{
			name:          "happy_production_like_1",
			configPath:    testutil.FindTestFile(t, "config-happy-prodlike-1.json", "config"),
			expected:      "macmini-mad",
			expectedError: false,
		},
		{
			name:          "happy_noschema_1",
			configPath:    testutil.FindTestFile(t, "config-happy-noschema-1.json", "config"),
			expected:      "ahost",
			expectedError: false,
		},
		{
			name:          "happy_noservices_1",
			configPath:    testutil.FindTestFile(t, "config-happy-noservices-1.json", "config"),
			expected:      "macmini-mad",
			expectedError: false,
		},
		{
			name:          "happy_no_host_field_defaults_to_hostname",
			configPath:    testutil.FindTestFile(t, "config-sad-no-host-1.json", "config"),
			expected:      hostname,
			expectedError: false,
		},
		{
			name:          "happy_missing_file_defaults_to_hostname",
			configPath:    "non-existent-file.json",
			expected:      hostname,
			expectedError: false,
		},
		{
			name:          "happy_corrupt_file_defaults_to_hostname",
			configPath:    testutil.FindTestFile(t, "config-sad-corrupt-1.json", "config"),
			expected:      hostname,
			expectedError: false,
		},
		{
			name:          "happy_env_supervisor_host_overrides_hostname",
			configPath:    "non-existent-file.json",
			envHost:       "envhost",
			expected:      "envhost",
			expectedError: false,
		},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			t.Cleanup(Reset)
			if testCase.envHost != "" {
				t.Setenv("SUPERVISOR_HOST", testCase.envHost)
			}
			config := Load(testCase.configPath)
			host := config.Host()
			if host != testCase.expected {
				t.Fatalf("Got host = %q, expected %q", host, testCase.expected)
			}
		})
	}
}

func TestConfig_Mount(t *testing.T) {
	tests := []struct {
		name          string
		configPath    string
		envMount     string
		expected      string
		expectedError bool
	}{
		{
			name:          "happy_production_like_1",
			configPath:    testutil.FindTestFile(t, "config-happy-prodlike-1.json", "config"),
			expected:      "/host-fs",
			expectedError: false,
		},
		{
			name:          "happy_no_field_missing_file_empty",
			configPath:    "non-existent-file.json",
			expected:      "",
			expectedError: false,
		},
		{
			name:          "happy_no_field_in_file_empty",
			configPath:    testutil.FindTestFile(t, "config-happy-noschema-1.json", "config"),
			expected:      "",
			expectedError: false,
		},
		{
			name:          "happy_env_supervisor_mount_used",
			configPath:    "non-existent-file.json",
			envMount:     "/env-host-fs",
			expected:      "/env-host-fs",
			expectedError: false,
		},
		{
			name:          "happy_file_takes_precedence_over_env",
			configPath:    testutil.FindTestFile(t, "config-happy-prodlike-1.json", "config"),
			envMount:     "/env-host-fs",
			expected:      "/host-fs",
			expectedError: false,
		},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			t.Cleanup(Reset)
			if testCase.envMount != "" {
				t.Setenv("SUPERVISOR_MOUNT", testCase.envMount)
			}
			config := Load(testCase.configPath)
			mount := config.Mount()
			if mount != testCase.expected {
				t.Fatalf("Got mount = %q, expected %q", mount, testCase.expected)
			}
		})
	}
}

func TestConfig_Broker(t *testing.T) {
	tests := []struct {
		name          string
		configPath    string
		envHost       string
		envPort       string
		expected      string
		expectedError bool
	}{
		{
			name:          "happy_production_like_1",
			configPath:    testutil.FindTestFile(t, "config-happy-prodlike-1.json", "config"),
			expected:      "vernemq.local.janeandgraham.com:1000",
			expectedError: false,
		},
		{
			name:          "happy_noschema_1",
			configPath:    testutil.FindTestFile(t, "config-happy-noschema-1.json", "config"),
			expected:      "vernemq.local.janeandgraham.com:1000",
			expectedError: false,
		},
		{
			name:          "happy_noservices_1",
			configPath:    testutil.FindTestFile(t, "config-happy-noservices-1.json", "config"),
			expected:      "vernemq.local.janeandgraham.com:1000",
			expectedError: false,
		},
		{
			name:          "happy_no_port_in_file_uses_host_only",
			configPath:    testutil.FindTestFile(t, "config-sad-no-broker-port-1.json", "config"),
			expected:      "vernemq.local.janeandgraham.com",
			expectedError: false,
		},
		{
			name:          "happy_no_broker_in_file_empty",
			configPath:    testutil.FindTestFile(t, "config-sad-no-broker-1.json", "config"),
			expected:      "",
			expectedError: false,
		},
		{
			name:          "happy_missing_file_empty",
			configPath:    "non-existent-file.json",
			expected:      "",
			expectedError: false,
		},
		{
			name:          "happy_corrupt_file_empty",
			configPath:    testutil.FindTestFile(t, "config-sad-corrupt-1.json", "config"),
			expected:      "",
			expectedError: false,
		},
		{
			name:          "happy_env_fallback_host_and_port",
			configPath:    "non-existent-file.json",
			envHost:       "envbroker.local",
			envPort:       "9999",
			expected:      "envbroker.local:9999",
			expectedError: false,
		},
		{
			name:          "happy_env_fallback_host_only",
			configPath:    "non-existent-file.json",
			envHost:       "envbroker.local",
			expected:      "envbroker.local",
			expectedError: false,
		},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			t.Cleanup(Reset)
			if testCase.envHost != "" {
				t.Setenv("VERNEMQ_HOST", testCase.envHost)
			}
			if testCase.envPort != "" {
				t.Setenv("VERNEMQ_API_PORT", testCase.envPort)
			}
			config := Load(testCase.configPath)
			broker := config.Broker()
			if broker != testCase.expected {
				t.Fatalf("Got broker = %q, expected %q", broker, testCase.expected)
			}
		})
	}
}

func TestConfig_Database(t *testing.T) {
	tests := []struct {
		name          string
		configPath    string
		envHost       string
		envPort       string
		expected      string
		expectedError bool
	}{
		{
			name:          "happy_production_like_1",
			configPath:    testutil.FindTestFile(t, "config-happy-prodlike-1.json", "config"),
			expected:      "influxdb.local.janeandgraham.com:2000",
			expectedError: false,
		},
		{
			name:          "happy_noschema_1",
			configPath:    testutil.FindTestFile(t, "config-happy-noschema-1.json", "config"),
			expected:      "influxdb.local.janeandgraham.com:2000",
			expectedError: false,
		},
		{
			name:          "happy_noservices_1",
			configPath:    testutil.FindTestFile(t, "config-happy-noservices-1.json", "config"),
			expected:      "influxdb.local.janeandgraham.com:2000",
			expectedError: false,
		},
		{
			name:          "happy_no_port_in_file_uses_host_only",
			configPath:    testutil.FindTestFile(t, "config-sad-no-database-port-1.json", "config"),
			expected:      "influxdb.local.janeandgraham.com",
			expectedError: false,
		},
		{
			name:          "happy_no_database_in_file_empty",
			configPath:    testutil.FindTestFile(t, "config-sad-no-database-1.json", "config"),
			expected:      "",
			expectedError: false,
		},
		{
			name:          "happy_missing_file_empty",
			configPath:    "non-existent-file.json",
			expected:      "",
			expectedError: false,
		},
		{
			name:          "happy_corrupt_file_empty",
			configPath:    testutil.FindTestFile(t, "config-sad-corrupt-1.json", "config"),
			expected:      "",
			expectedError: false,
		},
		{
			name:          "happy_env_fallback_host_and_port",
			configPath:    "non-existent-file.json",
			envHost:       "envdb.local",
			envPort:       "8086",
			expected:      "envdb.local:8086",
			expectedError: false,
		},
		{
			name:          "happy_env_fallback_host_only",
			configPath:    "non-existent-file.json",
			envHost:       "envdb.local",
			expected:      "envdb.local",
			expectedError: false,
		},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			t.Cleanup(Reset)
			if testCase.envHost != "" {
				t.Setenv("INFLUXDB_HOST", testCase.envHost)
			}
			if testCase.envPort != "" {
				t.Setenv("INFLUXDB_HTTP_PORT", testCase.envPort)
			}
			config := Load(testCase.configPath)
			database := config.Database()
			if database != testCase.expected {
				t.Fatalf("Got database = %q, expected %q", database, testCase.expected)
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
			name:          "happy_production_like_1",
			configPath:    testutil.FindTestFile(t, "config-happy-prodlike-1.json", "config"),
			expected:      []string{"macmini-mad", "macmini-max", "macmini-may", "macmini-meg", "raspbpi-jen"},
			expectedError: false,
		},
		{
			name:          "happy_noschema_1",
			configPath:    testutil.FindTestFile(t, "config-happy-noschema-1.json", "config"),
			expected:      []string{},
			expectedError: false,
		},
		{
			name:          "happy_noservices_1",
			configPath:    testutil.FindTestFile(t, "config-happy-noservices-1.json", "config"),
			expected:      []string{"macmini-mad"},
			expectedError: false,
		},
		{
			name:          "happy_missing_file_empty",
			configPath:    "non-existent-file.json",
			expected:      []string{},
			expectedError: false,
		},
		{
			name:          "happy_corrupt_file_empty",
			configPath:    testutil.FindTestFile(t, "config-sad-corrupt-1.json", "config"),
			expected:      []string{},
			expectedError: false,
		},
		{
			name:          "happy_corrupt_2_empty",
			configPath:    testutil.FindTestFile(t, "config-sad-corrupt-2.json", "config"),
			expected:      []string{},
			expectedError: false,
		},
		{
			name:          "happy_corrupt_3_empty",
			configPath:    testutil.FindTestFile(t, "config-sad-corrupt-3.json", "config"),
			expected:      []string{},
			expectedError: false,
		},
		{
			name:          "happy_duplicate_host_first_kept",
			configPath:    testutil.FindTestFile(t, "config-sad-duplicate-host-1.json", "config"),
			expected:      []string{"macmini-mad"},
			expectedError: false,
		},
		{
			name:          "happy_duplicate_service_host_kept",
			configPath:    testutil.FindTestFile(t, "config-sad-duplicate-service-1.json", "config"),
			expected:      []string{"macmini-mad"},
			expectedError: false,
		},
		{
			name:          "happy_empty_schema_host_skipped",
			configPath:    testutil.FindTestFile(t, "config-sad-empty-host-1.json", "config"),
			expected:      []string{},
			expectedError: false,
		},
		{
			name:          "happy_empty_service_host_kept",
			configPath:    testutil.FindTestFile(t, "config-sad-empty-service-1.json", "config"),
			expected:      []string{"macmini-mad"},
			expectedError: false,
		},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			t.Cleanup(Reset)
			config := Load(testCase.configPath)
			hosts := config.Hosts()
			if !reflect.DeepEqual(hosts, testCase.expected) {
				t.Fatalf("Got hosts = %v, expected %v", hosts, testCase.expected)
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
			name:          "happy_production_like_macmini_mad_1",
			hostName:      "macmini-mad",
			configPath:    testutil.FindTestFile(t, "config-happy-prodlike-1.json", "config"),
			expected:      []string{"monitor", "plex", "sabnzbd"},
			expectedError: false,
		},
		{
			name:          "happy_production_like_non_existent_host_1",
			hostName:      "non-existent-host",
			configPath:    testutil.FindTestFile(t, "config-happy-prodlike-1.json", "config"),
			expected:      []string{},
			expectedError: false,
		},
		{
			name:          "happy_production_like_raspbpi_jen_1",
			hostName:      "raspbpi-jen",
			configPath:    testutil.FindTestFile(t, "config-happy-prodlike-1.json", "config"),
			expected:      []string{"monitor", "weewx", "zigbee2mqtt"},
			expectedError: false,
		},
		{
			name:          "happy_noschema_macmini_mad_1",
			hostName:      "macmini-mad",
			configPath:    testutil.FindTestFile(t, "config-happy-noschema-1.json", "config"),
			expected:      []string{},
			expectedError: false,
		},
		{
			name:          "happy_noservices_macmini_mad_1",
			hostName:      "macmini-mad",
			configPath:    testutil.FindTestFile(t, "config-happy-noservices-1.json", "config"),
			expected:      nil,
			expectedError: false,
		},
		{
			name:          "happy_missing_file_empty",
			configPath:    "non-existent-file.json",
			expected:      []string{},
			expectedError: false,
		},
		{
			name:          "happy_corrupt_file_empty",
			configPath:    testutil.FindTestFile(t, "config-sad-corrupt-1.json", "config"),
			expected:      []string{},
			expectedError: false,
		},
		{
			name:          "happy_duplicate_host_first_kept",
			hostName:      "macmini-mad",
			configPath:    testutil.FindTestFile(t, "config-sad-duplicate-host-1.json", "config"),
			expected:      []string{"monitor", "rhasspy"},
			expectedError: false,
		},
		{
			name:          "happy_duplicate_service_deduped",
			hostName:      "macmini-mad",
			configPath:    testutil.FindTestFile(t, "config-sad-duplicate-service-1.json", "config"),
			expected:      []string{"monitor"},
			expectedError: false,
		},
		{
			name:          "happy_empty_schema_host_skipped",
			hostName:      "macmini-mad",
			configPath:    testutil.FindTestFile(t, "config-sad-empty-host-1.json", "config"),
			expected:      []string{},
			expectedError: false,
		},
		{
			name:          "happy_empty_service_skipped",
			hostName:      "macmini-mad",
			configPath:    testutil.FindTestFile(t, "config-sad-empty-service-1.json", "config"),
			expected:      []string{"monitor"},
			expectedError: false,
		},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			t.Cleanup(Reset)
			config := Load(testCase.configPath)
			services := config.Services(testCase.hostName)
			if !reflect.DeepEqual(services, testCase.expected) {
				t.Fatalf("Got services = %v, expected %v", services, testCase.expected)
			}
		})
	}
}
