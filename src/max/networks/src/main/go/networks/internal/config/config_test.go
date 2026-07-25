package config

import (
	"os"
	"testing"
)

func TestConfig_Resolution(t *testing.T) {
	tests := []struct {
		name             string
		envVars          map[string]string
		expectedBroker   string
		expectedDatabase string
		expectedDBName   string
		expectedSite     string
		expectedVersion  string
		expectedError    bool
	}{
		{
			name:             "full_resolution",
			envVars:          map[string]string{"BROKER_HOST": "vernemq", "BROKER_PORT": "1883", "DATABASE_HOST": "influx", "DATABASE_PORT": "8181", "DATABASE_NAME": "netdb", "UNIFI_SITE": "home", "SERVICE_VERSION_ABSOLUTE": "10.200.1234"},
			expectedBroker:   "vernemq:1883",
			expectedDatabase: "influx:8181",
			expectedDBName:   "netdb",
			expectedSite:     "home",
			expectedVersion:  "10.200.1234",
			expectedError:    false,
		},
		{
			name:             "defaults_when_unset",
			envVars:          map[string]string{},
			expectedBroker:   "",
			expectedDatabase: "",
			expectedDBName:   "networks",
			expectedSite:     "default",
			expectedVersion:  defaultVersion,
			expectedError:    false,
		},
		{
			name:             "invalid_version_falls_back",
			envVars:          map[string]string{"SERVICE_VERSION_ABSOLUTE": "not-a-version"},
			expectedBroker:   "",
			expectedDatabase: "",
			expectedDBName:   "networks",
			expectedSite:     "default",
			expectedVersion:  defaultVersion,
			expectedError:    false,
		},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			for _, key := range []string{"BROKER_HOST", "BROKER_PORT", "DATABASE_HOST", "DATABASE_PORT", "DATABASE_NAME", "UNIFI_SITE", "SERVICE_VERSION_ABSOLUTE"} {
				os.Unsetenv(key)
			}
			for key, value := range test.envVars {
				os.Setenv(key, value)
			}
			Reset()
			c := Load()
			if got := c.Broker(); got != test.expectedBroker {
				t.Errorf("Broker: got %q want %q", got, test.expectedBroker)
			}
			if got := c.Database(); got != test.expectedDatabase {
				t.Errorf("Database: got %q want %q", got, test.expectedDatabase)
			}
			if got := c.DatabaseName(); got != test.expectedDBName {
				t.Errorf("DatabaseName: got %q want %q", got, test.expectedDBName)
			}
			if got := c.UnifiSite(); got != test.expectedSite {
				t.Errorf("UnifiSite: got %q want %q", got, test.expectedSite)
			}
			if got := c.Version(); got != test.expectedVersion {
				t.Errorf("Version: got %q want %q", got, test.expectedVersion)
			}
		})
	}
	for _, key := range []string{"BROKER_HOST", "BROKER_PORT", "DATABASE_HOST", "DATABASE_PORT", "DATABASE_NAME", "UNIFI_SITE", "SERVICE_VERSION_ABSOLUTE"} {
		os.Unsetenv(key)
	}
	Reset()
}
