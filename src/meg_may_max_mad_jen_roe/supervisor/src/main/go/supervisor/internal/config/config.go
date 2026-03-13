package config

import (
	"encoding/json"
	"errors"
	"fmt"
	"log/slog"
	"os"
	"regexp"
	"sort"
	"sync"
)

var DefaultConfigPath = "/var/lib/asystem/install/supervisor/latest/image/config.json"

type Periods struct {
	PollMillis    int
	PulseMillis   int
	TrendHours    int
	CacheHours    int
	SnapshotMins  int
	HeartbeatSecs int
}

func Load(path string) (*Config, error) {
	if path == "" {
		return nil, errors.New("config path is required")
	}
	return load(path)
}

func load(path string) (*Config, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, fmt.Errorf("read config file [%s]: %w", path, err)
	}
	var raw struct{ Asystem configData }
	if err := json.Unmarshal(data, &raw); err != nil {
		return nil, fmt.Errorf("unmarshal config: %w", err)
	}
	config := Config{asystem: raw.Asystem}
	if !VersionPattern.MatchString(config.asystem.Version) {
		return nil, fmt.Errorf("invalid version [%s]", config.asystem.Version)
	}
	seenHosts := map[string]bool{}
	for i := range config.asystem.Schema {
		hostServices := &config.asystem.Schema[i]
		if hostServices.Host == "" {
			return nil, errors.New("empty host name")
		}
		if seenHosts[hostServices.Host] {
			return nil, fmt.Errorf("duplicate host [%s]", hostServices.Host)
		}
		seenHosts[hostServices.Host] = true
		seenServices := map[string]bool{}
		for _, service := range hostServices.Services {
			if service == "" {
				return nil, fmt.Errorf("empty service for host [%s]", hostServices.Host)
			}
			if seenServices[service] {
				return nil, fmt.Errorf("duplicate service [%s] on host [%s]", service, hostServices.Host)
			}
			seenServices[service] = true
		}
	}
	if config.asystem.Broker.Host == "" {
		return nil, errors.New("broker host is required")
	}
	if config.asystem.Broker.Port == "" {
		return nil, errors.New("broker port is required")
	}
	if config.asystem.Database.Host == "" {
		return nil, errors.New("database host is required")
	}
	if config.asystem.Database.Port == "" {
		return nil, errors.New("database port is required")
	}
	return &config, nil
}

func (s *Config) Version() string { return s.asystem.Version }

func (s *Config) Broker() string {
	host := s.asystem.Broker.Host
	port := s.asystem.Broker.Port
	if host == "" {
		return ""
	}
	if port == "" {
		return host
	}
	return fmt.Sprintf("%s:%s", host, port)
}

func (s *Config) Database() string {
	host := s.asystem.Database.Host
	port := s.asystem.Database.Port
	if host == "" {
		return ""
	}
	if port == "" {
		return host
	}
	return fmt.Sprintf("%s:%s", host, port)
}

func (s *Config) Hosts() []string {
	hosts := make([]string, len(s.asystem.Schema))
	for i := range s.asystem.Schema {
		hosts[i] = s.asystem.Schema[i].Host
	}
	sort.Strings(hosts)
	return hosts
}

func (s *Config) Services(host string) []string {
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

var LocalHostName = func() string {
	cachedHostOnce.Do(func() {
		hostName, err := os.Hostname()
		if err != nil {
			slog.Error("failed to get hostname", "error", err)
			return
		}
		cachedHostName = hostName
	})
	return cachedHostName
}

type Config struct{ asystem configData }

type configData struct {
	Version  string
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

var VersionPattern = regexp.MustCompile(`^\d{2}\.\d{3}\.\d{4}(-SNAPSHOT)?$`)

var cachedHostName string
var cachedHostOnce sync.Once
