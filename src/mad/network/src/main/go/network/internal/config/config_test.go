package config

import (
	"testing"
)

func TestConfig_Resolution(t *testing.T) {
	tests := []struct {
		name                 string
		envVars              map[string]string
		expectedBroker       string
		expectedDatabase     string
		expectedDatabaseName string
		expectedSite         string
	}{
		{
			name: "full_resolution",
			envVars: map[string]string{
				"BROKER_HOST":   "vernemq",
				"BROKER_PORT":   "1883",
				"DATABASE_HOST": "influx",
				"DATABASE_PORT": "8181",
				"DATABASE_NAME": "netdb",
				"UNIFI_SITE":    "home",
			},
			expectedBroker:       "vernemq:1883",
			expectedDatabase:     "influx:8181",
			expectedDatabaseName: "netdb",
			expectedSite:         "home",
		},
		{
			name:                 "defaults_when_unset",
			envVars:              map[string]string{},
			expectedBroker:       "",
			expectedDatabase:     "",
			expectedDatabaseName: "network",
			expectedSite:         "default",
		},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			for _, key := range []string{"BROKER_HOST", "BROKER_PORT", "DATABASE_HOST", "DATABASE_PORT", "DATABASE_NAME", "UNIFI_SITE"} {
				t.Setenv(key, testCase.envVars[key])
			}
			t.Cleanup(reset)
			reset()
			loaded := Load()
			if got := loaded.Broker(); got != testCase.expectedBroker {
				t.Errorf("Broker: got %q want %q", got, testCase.expectedBroker)
			}
			if got := loaded.Database(); got != testCase.expectedDatabase {
				t.Errorf("Database: got %q want %q", got, testCase.expectedDatabase)
			}
			if got := loaded.DatabaseName(); got != testCase.expectedDatabaseName {
				t.Errorf("DatabaseName: got %q want %q", got, testCase.expectedDatabaseName)
			}
			if got := loaded.UnifiSite(); got != testCase.expectedSite {
				t.Errorf("UnifiSite: got %q want %q", got, testCase.expectedSite)
			}
		})
	}
}

func reset() {
	cachedMu.Lock()
	defer cachedMu.Unlock()
	cached = nil
}
