package config

import (
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"regexp"
	"sort"
)

const DefaultConfigPath = "/root/install/supervisor/latest/image/config.json"

type Config struct{ Asystem configData }

func Load(path string) (*Config, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, fmt.Errorf("read config file [%s]: %w", path, err)
	}
	var config Config
	if err := json.Unmarshal(data, &config); err != nil {
		return nil, fmt.Errorf("unmarshal config: %w", err)
	}
	if !versionPattern.MatchString(config.Asystem.Version) {
		return nil, fmt.Errorf("invalid version [%s]", config.Asystem.Version)
	}
	seenHosts := map[string]bool{}
	for i := range config.Asystem.Services {
		hostServices := &config.Asystem.Services[i]
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
	return &config, nil
}

func (s *Config) Version() string { return s.Asystem.Version }

func (s *Config) Broker() string {
	host := s.Asystem.Broker.Host
	port := s.Asystem.Broker.Port
	if host == "" {
		return ""
	}
	if port == "" {
		return host
	}
	return fmt.Sprintf("%s:%s", host, port)
}

func (s *Config) Database() string {
	host := s.Asystem.Database.Host
	port := s.Asystem.Database.Port
	if host == "" {
		return ""
	}
	if port == "" {
		return host
	}
	return fmt.Sprintf("%s:%s", host, port)
}

func (s *Config) Hosts() []string {
	hosts := make([]string, len(s.Asystem.Services))
	for i := range s.Asystem.Services {
		hosts[i] = s.Asystem.Services[i].Host
	}
	sort.Strings(hosts)
	return hosts
}

func (s *Config) Services(host string) []string {
	for i := range s.Asystem.Services {
		services := &s.Asystem.Services[i]
		if services.Host == host {
			servicesCopy := append([]string(nil), services.Services...)
			sort.Strings(servicesCopy)
			return servicesCopy
		}
	}
	return []string{}
}

var versionPattern = regexp.MustCompile(`^\d{2}\.\d{3}\.\d{4}$`)

type configData struct {
	Version  string
	Broker   configEndpoint
	Database configEndpoint
	Services []configServices
}

type configServices struct {
	Host     string
	Services []string
}

type configEndpoint struct {
	Host string
	Port string
}
