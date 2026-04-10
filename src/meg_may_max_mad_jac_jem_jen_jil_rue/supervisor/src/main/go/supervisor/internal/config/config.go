package config

import (
	"encoding/json"
	"fmt"
	"log/slog"
	"os"
	"regexp"
	"sort"
	"strings"
	"sync"
)

const defaultVersion = "10.100.1000-SNAPSHOT"

var DefaultConfigPath = "/var/lib/asystem/install/supervisor/latest/image/config.json"

type Periods struct {
	PollMillis    int
	PulseMillis   int
	TrendHours    int
	CacheHours    int
	SnapshotMins  int
	HeartbeatSecs int
}

var (
	configCache   = map[string]*Config{}
	configCacheMu sync.RWMutex
)

func Reset() {
	configCacheMu.Lock()
	defer configCacheMu.Unlock()
	clear(configCache)
}

func Load(path string) *Config {
	configCacheMu.RLock()
	if cached, ok := configCache[path]; ok {
		configCacheMu.RUnlock()
		return cached
	}
	configCacheMu.RUnlock()
	loaded := load(path)
	configCacheMu.Lock()
	configCache[path] = loaded
	configCacheMu.Unlock()
	return loaded
}

func load(path string) *Config {
	result := &Config{asystem: configData{Schema: []configServices{}}}
	if path == "" {
		slog.Warn("config: no path provided, using defaults")
	} else if data, err := os.ReadFile(path); err != nil {
		slog.Warn("config: file not found, using defaults", "path", path)
	} else {
		var raw struct{ Asystem configData }
		if err := json.Unmarshal(data, &raw); err != nil {
			slog.Warn("config: failed to parse, using defaults", "path", path, "error", err)
		} else {
			result.asystem = raw.Asystem
			if result.asystem.Schema == nil {
				result.asystem.Schema = []configServices{}
			}
			seenHosts := map[string]bool{}
			validSchema := make([]configServices, 0, len(result.asystem.Schema))
			for _, hostSchema := range result.asystem.Schema {
				if hostSchema.Host == "" {
					slog.Warn("config: empty host in schema, skipping")
					continue
				}
				if seenHosts[hostSchema.Host] {
					slog.Warn("config: duplicate host in schema, skipping", "host", hostSchema.Host)
					continue
				}
				seenHosts[hostSchema.Host] = true
				seenServices := map[string]bool{}
				validServices := make([]string, 0, len(hostSchema.Services))
				for _, service := range hostSchema.Services {
					if service == "" {
						slog.Warn("config: empty service, skipping", "host", hostSchema.Host)
						continue
					}
					if seenServices[service] {
						slog.Warn("config: duplicate service, skipping", "host", hostSchema.Host, "service", service)
						continue
					}
					seenServices[service] = true
					validServices = append(validServices, service)
				}
				sort.Strings(validServices)
				hostSchema.Services = validServices
				validSchema = append(validSchema, hostSchema)
			}
			sort.Slice(validSchema, func(i, j int) bool { return validSchema[i].Host < validSchema[j].Host })
			result.asystem.Schema = validSchema
		}
	}
	result.asystem.Version = resolve("version", "SERVICE_VERSION_ABSOLUTE", result.asystem.Version)
	result.asystem.Host = resolve("host", "SUPERVISOR_HOST", result.asystem.Host)
	result.asystem.Mount = resolve("mount", "SUPERVISOR_MOUNT", result.asystem.Mount)
	result.asystem.Broker.Host = resolve("broker_host", "VERNEMQ_SERVICE", result.asystem.Broker.Host)
	result.asystem.Broker.Port = resolve("broker_port", "VERNEMQ_API_PORT", result.asystem.Broker.Port)
	result.asystem.Database.Host = resolve("database_host", "INFLUXDB_SERVICE", result.asystem.Database.Host)
	result.asystem.Database.Port = resolve("database_port", "INFLUXDB_HTTP_PORT", result.asystem.Database.Port)
	return result
}

func (c *Config) Version() string {
	if c != nil && VersionPattern.MatchString(c.asystem.Version) {
		return c.asystem.Version
	}
	return defaultVersion
}

func (c *Config) Host() string {
	if c != nil && c.asystem.Host != "" {
		return c.asystem.Host
	}
	cachedHostOnceMu.Do(func() {
		hostName, err := os.Hostname()
		if err != nil {
			slog.Error("config: failed to get hostname", "error", err)
			return
		}
		cachedHostName = hostName
	})
	return cachedHostName
}

func (c *Config) Mount() string {
	if c == nil {
		return ""
	}
	return c.asystem.Mount
}

func (c *Config) Broker() string {
	if c == nil || c.asystem.Broker.Host == "" {
		return ""
	}
	if c.asystem.Broker.Port == "" {
		return c.asystem.Broker.Host
	}
	return fmt.Sprintf("%s:%s", c.asystem.Broker.Host, c.asystem.Broker.Port)
}

func (c *Config) Database() string {
	if c == nil || c.asystem.Database.Host == "" {
		return ""
	}
	if c.asystem.Database.Port == "" {
		return c.asystem.Database.Host
	}
	return fmt.Sprintf("%s:%s", c.asystem.Database.Host, c.asystem.Database.Port)
}

func (c *Config) Hosts() []string {
	if c == nil {
		return []string{}
	}
	hosts := make([]string, len(c.asystem.Schema))
	for i := range c.asystem.Schema {
		hosts[i] = c.asystem.Schema[i].Host
	}
	return hosts
}

func (c *Config) Services(host string) []string {
	if c == nil {
		return []string{}
	}
	for i := range c.asystem.Schema {
		services := &c.asystem.Schema[i]
		if services.Host == host {
			return append([]string(nil), services.Services...)
		}
	}
	return []string{}
}

func resolve(field, env, key string) string {
	if value := os.Getenv(env); value != "" {
		slog.Info("config", "status", "resolved", "env", "true", "file", "false", "name", field, "value", value)
		return value
	}
	if strings.HasPrefix(key, "$") {
		name := key[1:]
		if val := os.Getenv(name); val != "" {
			slog.Info("config", "status", "resolved", "env", "true", "file", "true", "name", field, "value", val)
			return val
		}
		slog.Warn("config", "status", "unresolved", "env", "true", "file", "true", "name", field, "value", "")
		return ""
	}
	if key != "" {
		slog.Info("config", "status", "resolved", "env", "false", "file", "true", "name", field, "value", key)
	} else {
		slog.Info("config", "status", "unresolved", "env", "false", "file", "true", "name", field, "value", key)
	}
	return key
}

var VersionPattern = regexp.MustCompile(`^\d{2}\.\d{3}\.\d{4}(-SNAPSHOT)?$`)

type Config struct{ asystem configData }

type configData struct {
	Version  string
	Host     string
	Mount    string `json:"mount"`
	Broker   configEndpoint
	Database configEndpoint
	Schema   []configServices
}

type configServices struct {
	Host     string
	Services []string
}

type configEndpoint struct {
	Host string
	Port string
}

var (
	cachedHostName   string
	cachedHostOnceMu sync.Once
)
