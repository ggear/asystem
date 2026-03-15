package config

import (
	"encoding/json"
	"fmt"
	"log/slog"
	"os"
	"regexp"
	"sort"
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
		slog.Debug("config: no path provided, using defaults")
		return result
	}
	data, err := os.ReadFile(path)
	if err != nil {
		slog.Debug("config: file not found, using defaults", "path", path)
		return result
	}
	var raw struct{ Asystem configData }
	if err := json.Unmarshal(data, &raw); err != nil {
		slog.Warn("config: failed to parse, using defaults", "path", path, "error", err)
		return result
	}
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
		hostSchema.Services = validServices
		validSchema = append(validSchema, hostSchema)
	}
	result.asystem.Schema = validSchema
	return result
}

func (s *Config) Version() string {
	if s != nil && VersionPattern.MatchString(s.asystem.Version) {
		return s.asystem.Version
	}
	return defaultVersion
}

func (s *Config) Host() string {
	if s != nil && s.asystem.Host != "" {
		return s.asystem.Host
	}
	if supervisorHost := os.Getenv("SUPERVISOR_HOST"); supervisorHost != "" {
		return supervisorHost
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

var (
	cachedHostName  string
	cachedHostOnceMu sync.Once
)

func (s *Config) Broker() string {
	var brokerHost, brokerPort string
	if s != nil {
		brokerHost = s.asystem.Broker.Host
		brokerPort = s.asystem.Broker.Port
	}
	if brokerHost == "" {
		brokerHost = os.Getenv("VERNEMQ_HOST")
	}
	if brokerPort == "" {
		brokerPort = os.Getenv("VERNEMQ_API_PORT")
	}
	if brokerHost == "" {
		return ""
	}
	if brokerPort == "" {
		return brokerHost
	}
	return fmt.Sprintf("%s:%s", brokerHost, brokerPort)
}

func (s *Config) Database() string {
	var databaseHost, databasePort string
	if s != nil {
		databaseHost = s.asystem.Database.Host
		databasePort = s.asystem.Database.Port
	}
	if databaseHost == "" {
		databaseHost = os.Getenv("INFLUXDB_HOST")
	}
	if databasePort == "" {
		databasePort = os.Getenv("INFLUXDB_HTTP_PORT")
	}
	if databaseHost == "" {
		return ""
	}
	if databasePort == "" {
		return databaseHost
	}
	return fmt.Sprintf("%s:%s", databaseHost, databasePort)
}

func (s *Config) Hosts() []string {
	if s == nil {
		return []string{}
	}
	hosts := make([]string, len(s.asystem.Schema))
	for i := range s.asystem.Schema {
		hosts[i] = s.asystem.Schema[i].Host
	}
	sort.Strings(hosts)
	return hosts
}

func (s *Config) Services(host string) []string {
	if s == nil {
		return []string{}
	}
	for i := range s.asystem.Schema {
		services := &s.asystem.Schema[i]
		if services.Host == host {
			servicesCopy := append([]string(nil), services.Services...)
			sort.Strings(servicesCopy)
			return servicesCopy
		}
	}
	return []string{}
}

var VersionPattern = regexp.MustCompile(`^\d{2}\.\d{3}\.\d{4}(-SNAPSHOT)?$`)

type Config struct{ asystem configData }

type configData struct {
	Version  string
	Host     string
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
