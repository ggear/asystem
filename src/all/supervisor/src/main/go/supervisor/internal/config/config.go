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

type Periods struct {
	PollMillis    int
	PulseMillis   int
	TrendHours    int
	CacheMins     int
	SnapshotMins  int
	HeartbeatSecs int
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

func Reset() {
	configCacheMu.Lock()
	defer configCacheMu.Unlock()
	clear(configCache)
}

func (c *Config) Version() string {
	if c != nil && DefaultVersionPattern.MatchString(c.asystem.Version) {
		return c.asystem.Version
	}
	return DefaultVersion
}

func (c *Config) Host() string {
	if c != nil && c.asystem.Host != "" {
		return c.asystem.Host
	}
	cachedHostOnce.Do(func() {
		hostnameStart := time.Now()
		hostName, err := os.Hostname()
		if err != nil {
			scribe.Log(scribe.SourceConfig, scribe.SubjectHost(""), scribe.ActionResolve).Errorf("faulting", hostnameStart, "[unknown] hostname, lookup failed with [%v]", err)
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

func (c *Config) HostIndex(host string) (int, bool) {
	if c == nil {
		return 0, false
	}
	for i := range c.asystem.Schema {
		if c.asystem.Schema[i].Host == host && c.asystem.Schema[i].Index != nil {
			return *c.asystem.Schema[i].Index, true
		}
	}
	return 0, false
}

func (c *Config) BackupCommandTopic() string {
	if c == nil {
		return ""
	}
	return c.asystem.Backup.CommandTopic
}

func (c *Config) BackupTimeoutHours() int {
	if c == nil {
		return 0
	}
	return c.asystem.Backup.TimeoutHours
}

func (c *Config) BackupStateTopic() string {
	if c == nil {
		return ""
	}
	return c.asystem.Backup.StateTopic
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

func TrendWindow(trendHours int) time.Duration {
	if trendHours > 0 {
		return time.Duration(trendHours) * time.Hour
	}
	return DefaultTrendWindow
}

func NowIncludingSuspend() time.Time {
	return time.Now().Round(0)
}

func SinceIncludingSuspend(instant time.Time) time.Duration {
	return time.Since(instant.Round(0))
}

func CacheWindow(cacheMins int) time.Duration {
	if cacheMins > 0 {
		return time.Duration(cacheMins) * time.Minute
	}
	return DefaultCacheWindow
}

func load(path string) *Config {
	loadStart := time.Now()
	result := &Config{asystem: configData{Schema: []configServices{}}}
	if path == "" {
		scribe.Log(scribe.SourceConfig, scribe.SubjectNone, scribe.ActionResolve).Warnf("defaults", loadStart, "[none] config path provided")
	} else if data, err := os.ReadFile(path); err != nil {
		scribe.Log(scribe.SourceConfig, scribe.SubjectNone, scribe.ActionResolve).Warnf("defaults", loadStart, "[%s] config file not found", path)
	} else {
		var raw struct{ Asystem configData }
		if err := json.Unmarshal(data, &raw); err != nil {
			scribe.Log(scribe.SourceConfig, scribe.SubjectNone, scribe.ActionResolve).Warnf("defaults", loadStart, "[%s] config file parse failed with [%v]", path, err)
		} else {
			result.asystem = raw.Asystem
			if result.asystem.Schema == nil {
				result.asystem.Schema = []configServices{}
			}
			seenHosts := map[string]bool{}
			validSchema := make([]configServices, 0, len(result.asystem.Schema))
			for _, hostSchema := range result.asystem.Schema {
				if hostSchema.Host == "" {
					scribe.Log(scribe.SourceConfig, scribe.SubjectNone, scribe.ActionResolve).Warnf("rejected", loadStart, "[empty] schema host, skipping")
					continue
				}
				if seenHosts[hostSchema.Host] {
					scribe.Log(scribe.SourceConfig, scribe.SubjectHost(hostSchema.Host), scribe.ActionResolve).Warnf("rejected", loadStart, "[duplicate] schema host, skipping")
					continue
				}
				seenHosts[hostSchema.Host] = true
				seenServices := map[string]bool{}
				validServices := make([]string, 0, len(hostSchema.Services))
				for _, service := range hostSchema.Services {
					if service == "" {
						scribe.Log(scribe.SourceConfig, scribe.SubjectHost(hostSchema.Host), scribe.ActionResolve).Warnf("rejected", loadStart, "[empty] service, skipping")
						continue
					}
					if seenServices[service] {
						scribe.Log(scribe.SourceConfig, scribe.SubjectService(service), scribe.ActionResolve).Warnf("rejected", loadStart, "[duplicate] service on host [%s], skipping", hostSchema.Host)
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

func resolve(field, env, key string) string {
	resolveStart := time.Now()
	logger := scribe.Log(scribe.SourceConfig, scribe.SubjectNone, scribe.ActionResolve)
	named := strings.ReplaceAll(field, "_", " ")
	if value := os.Getenv(env); value != "" {
		logger.Infof("resolved", resolveStart, "[%s] %s [env]", mask(field, value), named)
		return value
	}
	if strings.HasPrefix(key, "$") {
		name := key[1:]
		if val := os.Getenv(name); val != "" {
			logger.Infof("resolved", resolveStart, "[%s] %s [env/file]", mask(field, val), named)
			return val
		}
		logger.Warnf("unfilled", resolveStart, "[unset] %s in [env/file]", named)
		return ""
	}
	if key != "" {
		logger.Infof("resolved", resolveStart, "[%s] %s [file]", mask(field, key), named)
	} else {
		logger.Infof("unfilled", resolveStart, "[unset] %s in [env/file]", named)
	}
	return key
}

func mask(field, value string) string {
	if value != "" && strings.HasSuffix(field, "_token") {
		return "***"
	}
	return value
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

type Config struct{ asystem configData }

type configData struct {
	Version  string
	Host     string
	Mount    string `json:"mount"`
	Broker   configEndpoint
	Database configDatabaseEndpoint
	Schema   []configServices
	Backup   configBackup
}

type configBackup struct {
	CommandTopic string `json:"command_topic"`
	StateTopic   string `json:"state_topic"`
	TimeoutHours int    `json:"timeout_hours"`
}

type configServices struct {
	Host     string
	Index    *int
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

const (
	DefaultPollPeriod  = "3s"
	DefaultPulseFactor = "2"
	DefaultTrendPeriod = "24h"
	DefaultCachePeriod = "1h"
	DefaultVersion     = "00.000.0000-SNAPSHOT"
	DefaultConfigPath  = "/var/lib/asystem/install/supervisor/latest/image/config.json"
)

var (
	DefaultTrendWindow    = parsedTrendPeriod()
	DefaultCacheWindow    = parsedCachePeriod()
	DefaultVersionPattern = regexp.MustCompile(`^\d{2}\.\d{3}\.\d{4}(-SNAPSHOT)?$`)
)

var (
	configCacheMu  sync.RWMutex
	cachedHostOnce sync.Once
	cachedHostName string
	configCache    = map[string]*Config{}
)
