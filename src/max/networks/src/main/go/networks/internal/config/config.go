package config

import (
	"fmt"
	"log/slog"
	"os"
	"strings"
	"sync"
)

type Config struct {
	brokerHost    string
	brokerPort    string
	brokerToken   string
	databaseHost  string
	databasePort  string
	databaseName  string
	databaseToken string
	unifiURL      string
	unifiSite     string
	unifiUser     string
	unifiPassword string
}

var (
	cached   *Config
	cachedMu sync.RWMutex
)

func Reset() {
	cachedMu.Lock()
	defer cachedMu.Unlock()
	cached = nil
}

func Load() *Config {
	cachedMu.RLock()
	if cached != nil {
		defer cachedMu.RUnlock()
		return cached
	}
	cachedMu.RUnlock()
	cachedMu.Lock()
	defer cachedMu.Unlock()
	if cached == nil {
		cached = load()
	}
	return cached
}

func load() *Config {
	return &Config{
		brokerHost:    resolve("broker_host", "BROKER_HOST"),
		brokerPort:    resolve("broker_port", "BROKER_PORT"),
		brokerToken:   resolve("broker_token", "BROKER_TOKEN"),
		databaseHost:  resolve("database_host", "DATABASE_HOST"),
		databasePort:  resolve("database_port", "DATABASE_PORT"),
		databaseName:  resolve("database_name", "DATABASE_NAME"),
		databaseToken: resolve("database_token", "DATABASE_TOKEN"),
		unifiURL:      resolve("unifi_url", "UNIFI_URL"),
		unifiSite:     resolve("unifi_site", "UNIFI_SITE"),
		unifiUser:     resolve("unifi_user", "UNIFI_USER"),
		unifiPassword: resolve("unifi_password", "UNIFI_PASSWORD"),
	}
}

func (c *Config) Broker() string {
	if c == nil || c.brokerHost == "" {
		return ""
	}
	if c.brokerPort == "" {
		return c.brokerHost
	}
	return fmt.Sprintf("%s:%s", c.brokerHost, c.brokerPort)
}

func (c *Config) BrokerToken() string {
	if c == nil {
		return ""
	}
	return c.brokerToken
}

func (c *Config) Database() string {
	if c == nil || c.databaseHost == "" {
		return ""
	}
	if c.databasePort == "" {
		return c.databaseHost
	}
	return fmt.Sprintf("%s:%s", c.databaseHost, c.databasePort)
}

func (c *Config) DatabaseToken() string {
	if c == nil {
		return ""
	}
	return c.databaseToken
}

func (c *Config) DatabaseName() string {
	if c == nil || c.databaseName == "" {
		return "networks"
	}
	return c.databaseName
}

func (c *Config) UnifiURL() string {
	if c == nil {
		return ""
	}
	return c.unifiURL
}

func (c *Config) UnifiSite() string {
	if c == nil || c.unifiSite == "" {
		return "default"
	}
	return c.unifiSite
}

func (c *Config) UnifiUser() string {
	if c == nil {
		return ""
	}
	return c.unifiUser
}

func (c *Config) UnifiPassword() string {
	if c == nil {
		return ""
	}
	return c.unifiPassword
}

func resolve(field, env string) string {
	value := os.Getenv(env)
	if value != "" {
		slog.Info("config", "status", "resolved", "name", field, "value", mask(field, value))
		return value
	}
	slog.Warn("config", "status", "unresolved", "name", field, "value", "")
	return ""
}

func mask(field, value string) string {
	if value != "" && (strings.HasSuffix(field, "_token") || strings.HasSuffix(field, "_password")) {
		return "***"
	}
	return value
}
