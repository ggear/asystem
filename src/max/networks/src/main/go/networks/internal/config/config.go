package config

import (
	"fmt"
	"os"
	"sync"
)

const DefaultAggregatePeriod = "15m"

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
	unifiToken    string
	unifiHost     string
	weewxHost     string
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
	c := &Config{
		brokerHost:    os.Getenv("BROKER_HOST"),
		brokerPort:    os.Getenv("BROKER_PORT"),
		brokerToken:   os.Getenv("BROKER_TOKEN"),
		databaseHost:  os.Getenv("DATABASE_HOST"),
		databasePort:  os.Getenv("DATABASE_PORT"),
		databaseName:  os.Getenv("DATABASE_NAME"),
		databaseToken: os.Getenv("DATABASE_TOKEN"),
		unifiURL:      os.Getenv("UNIFI_URL"),
		unifiSite:     os.Getenv("UNIFI_SITE"),
		unifiUser:     os.Getenv("UNIFI_USER"),
		unifiToken:    os.Getenv("UNIFI_TOKEN"),
		unifiHost:     os.Getenv("UNIFI_HOST"),
		weewxHost:     os.Getenv("WEEWX_HOST_PROD"),
	}
	return c
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

func (c *Config) UnifiToken() string {
	if c == nil {
		return ""
	}
	return c.unifiToken
}

func (c *Config) UnifiHost() string {
	if c == nil {
		return ""
	}
	return c.unifiHost
}

func (c *Config) WeewxHost() string {
	if c == nil {
		return ""
	}
	return c.weewxHost
}
