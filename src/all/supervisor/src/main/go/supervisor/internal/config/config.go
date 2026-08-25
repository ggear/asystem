package config

import (
	"encoding/json"
	"fmt"
	"os"
	"regexp"
	"sort"
	"strings"
	"supervisor/internal/scribe"
	"sync"
	"time"
)

const defaultVersion = "10.100.1000-SNAPSHOT"

const (
	DefaultPollPeriod  = "3s"
	DefaultPulseFactor = "2"
	DefaultTrendPeriod = "24h"
	DefaultCachePeriod = "1h"
)

func TrendWindow(trendHours int) time.Duration {
	if trendHours > 0 {
		return time.Duration(trendHours) * time.Hour
	}
	return defaultTrendWindow
}

func CacheWindow(cacheMins int) time.Duration {
	if cacheMins > 0 {
		return time.Duration(cacheMins) * time.Minute
	}
	return defaultCacheWindow
}

var DefaultConfigPath = "/var/lib/asystem/install/supervisor/latest/image/config.json"

type Periods struct {
	PollMillis    int
	PulseMillis   int
	TrendHours    int
	CacheMins     int
	SnapshotMins  int
	HeartbeatSecs int
}

var (
	configCache      = map[string]*Config{}
	configCacheMutex sync.RWMutex
)

func Reset() {
	configCacheMutex.Lock()
	defer configCacheMutex.Unlock()
	clear(configCache)
}

func Load(path string) *Config {
	configCacheMutex.RLock()
	if cached, ok := configCache[path]; ok {
		configCacheMutex.RUnlock()
		return cached
	}
	configCacheMutex.RUnlock()
	loaded := load(path)
	configCacheMutex.Lock()
	configCache[path] = loaded
	configCacheMutex.Unlock()
	return loaded
}

func load(path string) *Config {
	loadStart := time.Now()
	result := &Config{asystem: configData{Schema: []configServices{}}}
	if path == "" {
		scribe.Log(scribe.SourceConfig, scribe.SubjectNone, scribe.ActionResolve).Warn("defaults", loadStart, "[config] no path provided")
	} else if data, err := os.ReadFile(path); err != nil {
		scribe.Log(scribe.SourceConfig, scribe.SubjectPath(path), scribe.ActionResolve).Warn("defaults", loadStart, "[%s] file not found", path)
	} else {
		var raw struct{ Asystem configData }
		if err := json.Unmarshal(data, &raw); err != nil {
			scribe.Log(scribe.SourceConfig, scribe.SubjectPath(path), scribe.ActionResolve).Warn("defaults", loadStart, "[%s] parse failed with [%v]", path, err)
		} else {
			result.asystem = raw.Asystem
			if result.asystem.Schema == nil {
				result.asystem.Schema = []configServices{}
			}
			seenHosts := map[string]bool{}
			validSchema := make([]configServices, 0, len(result.asystem.Schema))
			for _, hostSchema := range result.asystem.Schema {
				if hostSchema.Host == "" {
					scribe.Log(scribe.SourceConfig, scribe.SubjectNone, scribe.ActionResolve).Warn("rejected", loadStart, "[host] empty, skipping")
					continue
				}
				if seenHosts[hostSchema.Host] {
					scribe.Log(scribe.SourceConfig, scribe.SubjectHost(hostSchema.Host), scribe.ActionResolve).Warn("rejected", loadStart, "duplicate host, skipping")
					continue
				}
				seenHosts[hostSchema.Host] = true
				seenServices := map[string]bool{}
				validServices := make([]string, 0, len(hostSchema.Services))
				for _, service := range hostSchema.Services {
					if service == "" {
						scribe.Log(scribe.SourceConfig, scribe.SubjectHost(hostSchema.Host), scribe.ActionResolve).Warn("rejected", loadStart, "empty service, skipping")
						continue
					}
					if seenServices[service] {
						scribe.Log(scribe.SourceConfig, scribe.SubjectHost(hostSchema.Host), scribe.ActionResolve).Warn("rejected", loadStart, "duplicate service [%s], skipping", service)
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
	result.asystem.Broker.Host = resolve("broker_host", "BROKER_HOST", result.asystem.Broker.Host)
	result.asystem.Broker.Port = resolve("broker_port", "BROKER_PORT", result.asystem.Broker.Port)
	result.asystem.Broker.Token = resolve("broker_token", "BROKER_TOKEN", result.asystem.Broker.Token)
	result.asystem.Database.Host = resolve("database_host", "DATABASE_HOST", result.asystem.Database.Host)
	result.asystem.Database.Port = resolve("database_port", "DATABASE_PORT", result.asystem.Database.Port)
	result.asystem.Database.Name = resolve("database_name", "DATABASE_NAME", result.asystem.Database.Name)
	result.asystem.Database.Token = resolve("database_token", "DATABASE_TOKEN", result.asystem.Database.Token)
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
		hostnameStart := time.Now()
		hostName, err := os.Hostname()
		if err != nil {
			scribe.Log(scribe.SourceConfig, scribe.SubjectNone, scribe.ActionResolve).Error("faulting", hostnameStart, "[%v] hostname lookup", err)
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

func (c *Config) BrokerToken() string {
	if c == nil {
		return ""
	}
	return c.asystem.Broker.Token
}

func (c *Config) DatabaseToken() string {
	if c == nil {
		return ""
	}
	return c.asystem.Database.Token
}

func (c *Config) DatabaseName() string {
	if c == nil || c.asystem.Database.Name == "" {
		return "supervisor"
	}
	return c.asystem.Database.Name
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
	resolveStart := time.Now()
	logger := scribe.Log(scribe.SourceConfig, scribe.SubjectField(field), scribe.ActionResolve)
	if value := os.Getenv(env); value != "" {
		logger.Info("resolved", resolveStart, "value [%s] from [env]", mask(field, value))
		return value
	}
	if strings.HasPrefix(key, "$") {
		name := key[1:]
		if val := os.Getenv(name); val != "" {
			logger.Info("resolved", resolveStart, "value [%s] from [env] referenced by [file]", mask(field, val))
			return val
		}
		logger.Warn("unfilled", resolveStart, "referenced by [file] but unset in [env]")
		return ""
	}
	if key != "" {
		logger.Info("resolved", resolveStart, "value [%s] from [file]", mask(field, key))
	} else {
		logger.Info("unfilled", resolveStart, "unset in [env] and [file]")
	}
	return key
}

func mask(field, value string) string {
	if value != "" && strings.HasSuffix(field, "_token") {
		return "***"
	}
	return value
}

var VersionPattern = regexp.MustCompile(`^\d{2}\.\d{3}\.\d{4}(-SNAPSHOT)?$`)

type Config struct{ asystem configData }

type configData struct {
	Version  string
	Host     string
	Mount    string `json:"mount"`
	Broker   configEndpoint
	Database configDatabaseEndpoint
	Schema   []configServices
}

type configServices struct {
	Host     string
	Services []string
}

type configEndpoint struct {
	Host  string
	Port  string
	Token string
}

type configDatabaseEndpoint struct {
	Host  string
	Port  string
	Name  string
	Token string
}

func parsedTrendPeriod() time.Duration {
	parsed, err := time.ParseDuration(DefaultTrendPeriod)
	if err != nil {
		panic(fmt.Sprintf("invalid default trend period [%s] with [%v]", DefaultTrendPeriod, err))
	}
	return parsed
}

func parsedCachePeriod() time.Duration {
	parsed, err := time.ParseDuration(DefaultCachePeriod)
	if err != nil {
		panic(fmt.Sprintf("invalid default cache period [%s] with [%v]", DefaultCachePeriod, err))
	}
	return parsed
}

var (
	defaultTrendWindow = parsedTrendPeriod()
	defaultCacheWindow = parsedCachePeriod()
	cachedHostName     string
	cachedHostOnceMu   sync.Once
)
