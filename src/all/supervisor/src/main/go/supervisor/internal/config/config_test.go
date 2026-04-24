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
		envVars       map[string]string
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
		{
			name:          "happy_envvar_set_expands_version",
			configPath:    testutil.FindTestFile(t, "config-happy-envvars-1.json", "config"),
			envVars:       map[string]string{"TEST_CFG_VERSION": "10.100.1234"},
			expected:      "10.100.1234",
			expectedError: false,
		},
		{
			name:          "happy_envvar_unset_defaults_version",
			configPath:    testutil.FindTestFile(t, "config-happy-envvars-1.json", "config"),
			expected:      defaultVersion,
			expectedError: false,
		},
		{
			name:          "happy_service_version_absolute_used_when_no_config",
			configPath:    "non-existent-file.json",
			envVars:       map[string]string{"SERVICE_VERSION_ABSOLUTE": "10.100.5678"},
			expected:      "10.100.5678",
			expectedError: false,
		},
		{
			name:          "happy_service_version_absolute_invalid_ignored",
			configPath:    "non-existent-file.json",
			envVars:       map[string]string{"SERVICE_VERSION_ABSOLUTE": "notaversion"},
			expected:      defaultVersion,
			expectedError: false,
		},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			t.Cleanup(Reset)
			for k, v := range testCase.envVars {
				t.Setenv(k, v)
			}
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
		envVars       map[string]string
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
		{
			name:          "happy_envvar_set_expands_host",
			configPath:    testutil.FindTestFile(t, "config-happy-envvars-1.json", "config"),
			envVars:       map[string]string{"TEST_CFG_HOST": "envexpanded-host"},
			expected:      "envexpanded-host",
			expectedError: false,
		},
		{
			name:          "happy_envvar_unset_falls_through_to_hostname",
			configPath:    testutil.FindTestFile(t, "config-happy-envvars-1.json", "config"),
			expected:      hostname,
			expectedError: false,
		},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			t.Cleanup(Reset)
			if testCase.envHost != "" {
				t.Setenv("SUPERVISOR_HOST", testCase.envHost)
			}
			for k, v := range testCase.envVars {
				t.Setenv(k, v)
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
		envMount      string
		envVars       map[string]string
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
			envMount:      "/env-host-fs",
			expected:      "/env-host-fs",
			expectedError: false,
		},
		{
			name:          "happy_env_takes_precedence_over_file",
			configPath:    testutil.FindTestFile(t, "config-happy-prodlike-1.json", "config"),
			envMount:      "/env-host-fs",
			expected:      "/env-host-fs",
			expectedError: false,
		},
		{
			name:          "happy_envvar_set_expands_mount",
			configPath:    testutil.FindTestFile(t, "config-happy-envvars-1.json", "config"),
			envVars:       map[string]string{"TEST_CFG_MOUNT": "/expanded-host-fs"},
			expected:      "/expanded-host-fs",
			expectedError: false,
		},
		{
			name:          "happy_envvar_unset_falls_through_to_supervisor_mount",
			configPath:    testutil.FindTestFile(t, "config-happy-envvars-1.json", "config"),
			envMount:      "/fallback-mount",
			expected:      "/fallback-mount",
			expectedError: false,
		},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			t.Cleanup(Reset)
			if testCase.envMount != "" {
				t.Setenv("SUPERVISOR_MOUNT", testCase.envMount)
			}
			for k, v := range testCase.envVars {
				t.Setenv(k, v)
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
		envVars       map[string]string
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
		{
			name:          "happy_envvar_set_expands_broker_host_and_port",
			configPath:    testutil.FindTestFile(t, "config-happy-envvars-1.json", "config"),
			envVars:       map[string]string{"TEST_CFG_BROKER_HOST": "expandedbroker.local", "TEST_CFG_BROKER_PORT": "9000"},
			expected:      "expandedbroker.local:9000",
			expectedError: false,
		},
		{
			name:          "happy_envvar_unset_falls_through_to_broker_env",
			configPath:    testutil.FindTestFile(t, "config-happy-envvars-1.json", "config"),
			envHost:       "fallbackbroker.local",
			envPort:       "8888",
			expected:      "fallbackbroker.local:8888",
			expectedError: false,
		},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			t.Cleanup(Reset)
			if testCase.envHost != "" {
				t.Setenv("BROKER_HOST", testCase.envHost)
			}
			if testCase.envPort != "" {
				t.Setenv("BROKER_PORT", testCase.envPort)
			}
			for k, v := range testCase.envVars {
				t.Setenv(k, v)
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
		envVars       map[string]string
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
		{
			name:          "happy_envvar_set_expands_database_host_and_port",
			configPath:    testutil.FindTestFile(t, "config-happy-envvars-1.json", "config"),
			envVars:       map[string]string{"TEST_CFG_DATABASE_HOST": "expandeddb.local", "TEST_CFG_DATABASE_PORT": "7777"},
			expected:      "expandeddb.local:7777",
			expectedError: false,
		},
		{
			name:          "happy_envvar_unset_falls_through_to_database_env",
			configPath:    testutil.FindTestFile(t, "config-happy-envvars-1.json", "config"),
			envHost:       "fallbackdb.local",
			envPort:       "6666",
			expected:      "fallbackdb.local:6666",
			expectedError: false,
		},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			t.Cleanup(Reset)
			if testCase.envHost != "" {
				t.Setenv("DATABASE_HOST", testCase.envHost)
			}
			if testCase.envPort != "" {
				t.Setenv("DATABASE_PORT", testCase.envPort)
			}
			for k, v := range testCase.envVars {
				t.Setenv(k, v)
			}
			config := Load(testCase.configPath)
			database := config.Database()
			if database != testCase.expected {
				t.Fatalf("Got database = %q, expected %q", database, testCase.expected)
			}
		})
	}
}

func TestConfig_BrokerToken(t *testing.T) {
	tests := []struct {
		name          string
		configPath    string
		envToken      string
		envVars       map[string]string
		expected      string
		expectedError bool
	}{
		{
			name:          "happy_production_like_1",
			configPath:    testutil.FindTestFile(t, "config-happy-prodlike-1.json", "config"),
			expected:      "prodtoken123",
			expectedError: false,
		},
		{
			name:          "happy_noschema_1",
			configPath:    testutil.FindTestFile(t, "config-happy-noschema-1.json", "config"),
			expected:      "noschematoken456",
			expectedError: false,
		},
		{
			name:          "happy_no_field_in_file_empty",
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
			name:          "happy_env_database_token_used",
			configPath:    "non-existent-file.json",
			envToken:      "envbrokertoken",
			expected:      "envbrokertoken",
			expectedError: false,
		},
		{
			name:          "happy_env_overrides_file_token",
			configPath:    testutil.FindTestFile(t, "config-happy-prodlike-1.json", "config"),
			envToken:      "envoverride",
			expected:      "envoverride",
			expectedError: false,
		},
		{
			name:          "happy_envvar_set_expands_token",
			configPath:    testutil.FindTestFile(t, "config-happy-envvars-1.json", "config"),
			envVars:       map[string]string{"TEST_CFG_BROKER_TOKEN": "expandedbrokertoken"},
			expected:      "expandedbrokertoken",
			expectedError: false,
		},
		{
			name:          "happy_envvar_unset_falls_through_to_database_token_env",
			configPath:    testutil.FindTestFile(t, "config-happy-envvars-1.json", "config"),
			envToken:      "fallbackbrokertoken",
			expected:      "fallbackbrokertoken",
			expectedError: false,
		},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			t.Cleanup(Reset)
			if testCase.envToken != "" {
				t.Setenv("DATABASE_TOKEN", testCase.envToken)
			}
			for k, v := range testCase.envVars {
				t.Setenv(k, v)
			}
			config := Load(testCase.configPath)
			token := config.BrokerToken()
			if token != testCase.expected {
				t.Fatalf("Got broker token = %q, expected %q", token, testCase.expected)
			}
		})
	}
}

func TestConfig_DatabaseToken(t *testing.T) {
	tests := []struct {
		name          string
		configPath    string
		envToken      string
		envVars       map[string]string
		expected      string
		expectedError bool
	}{
		{
			name:          "happy_production_like_1",
			configPath:    testutil.FindTestFile(t, "config-happy-prodlike-1.json", "config"),
			expected:      "prodtoken123",
			expectedError: false,
		},
		{
			name:          "happy_noschema_1",
			configPath:    testutil.FindTestFile(t, "config-happy-noschema-1.json", "config"),
			expected:      "noschematoken456",
			expectedError: false,
		},
		{
			name:          "happy_no_field_in_file_empty",
			configPath:    testutil.FindTestFile(t, "config-sad-no-database-port-1.json", "config"),
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
			name:          "happy_env_database_token_used",
			configPath:    "non-existent-file.json",
			envToken:      "envtoken",
			expected:      "envtoken",
			expectedError: false,
		},
		{
			name:          "happy_env_overrides_file_token",
			configPath:    testutil.FindTestFile(t, "config-happy-prodlike-1.json", "config"),
			envToken:      "envoverride",
			expected:      "envoverride",
			expectedError: false,
		},
		{
			name:          "happy_envvar_set_expands_token",
			configPath:    testutil.FindTestFile(t, "config-happy-envvars-1.json", "config"),
			envVars:       map[string]string{"TEST_CFG_DATABASE_TOKEN": "expandedtoken"},
			expected:      "expandedtoken",
			expectedError: false,
		},
		{
			name:          "happy_envvar_unset_falls_through_to_database_token_env",
			configPath:    testutil.FindTestFile(t, "config-happy-envvars-1.json", "config"),
			envToken:      "fallbacktoken",
			expected:      "fallbacktoken",
			expectedError: false,
		},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			t.Cleanup(Reset)
			if testCase.envToken != "" {
				t.Setenv("DATABASE_TOKEN", testCase.envToken)
			}
			for k, v := range testCase.envVars {
				t.Setenv(k, v)
			}
			config := Load(testCase.configPath)
			token := config.DatabaseToken()
			if token != testCase.expected {
				t.Fatalf("Got token = %q, expected %q", token, testCase.expected)
			}
		})
	}
}

func TestConfig_DatabaseName(t *testing.T) {
	tests := []struct {
		name          string
		configPath    string
		envName       string
		envVars       map[string]string
		expected      string
		expectedError bool
	}{
		{
			name:          "happy_production_like_1",
			configPath:    testutil.FindTestFile(t, "config-happy-prodlike-1.json", "config"),
			expected:      "supervisor",
			expectedError: false,
		},
		{
			name:          "happy_no_field_in_file_defaults_supervisor",
			configPath:    testutil.FindTestFile(t, "config-sad-no-database-port-1.json", "config"),
			expected:      "supervisor",
			expectedError: false,
		},
		{
			name:          "happy_missing_file_defaults_supervisor",
			configPath:    "non-existent-file.json",
			expected:      "supervisor",
			expectedError: false,
		},
		{
			name:          "happy_corrupt_file_defaults_supervisor",
			configPath:    testutil.FindTestFile(t, "config-sad-corrupt-1.json", "config"),
			expected:      "supervisor",
			expectedError: false,
		},
		{
			name:          "happy_env_database_name_used",
			configPath:    "non-existent-file.json",
			envName:       "envdbname",
			expected:      "envdbname",
			expectedError: false,
		},
		{
			name:          "happy_env_overrides_file_name",
			configPath:    testutil.FindTestFile(t, "config-happy-prodlike-1.json", "config"),
			envName:       "envdboverride",
			expected:      "envdboverride",
			expectedError: false,
		},
		{
			name:          "happy_envvar_set_expands_name",
			configPath:    testutil.FindTestFile(t, "config-happy-envvars-1.json", "config"),
			envVars:       map[string]string{"TEST_CFG_DATABASE_NAME": "expandeddbname"},
			expected:      "expandeddbname",
			expectedError: false,
		},
		{
			name:          "happy_envvar_unset_falls_through_to_database_name_env",
			configPath:    testutil.FindTestFile(t, "config-happy-envvars-1.json", "config"),
			envName:       "fallbackdbname",
			expected:      "fallbackdbname",
			expectedError: false,
		},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			t.Cleanup(Reset)
			if testCase.envName != "" {
				t.Setenv("DATABASE_NAME", testCase.envName)
			}
			for k, v := range testCase.envVars {
				t.Setenv(k, v)
			}
			config := Load(testCase.configPath)
			dbName := config.DatabaseName()
			if dbName != testCase.expected {
				t.Fatalf("Got database name = %q, expected %q", dbName, testCase.expected)
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
