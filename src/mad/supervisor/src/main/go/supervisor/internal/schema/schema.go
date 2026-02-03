package schema

import (
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"regexp"
	"sort"
)

const DefaultPath = "/root/install/supervisor/latest/image/schema.json"

var versionPattern = regexp.MustCompile(`^\d{2}\.\d{3}\.\d{4}$`)

type Schema struct{ Asystem schemaData }

type schemaData struct {
	Version  string
	Services []schemaHostServices
}

type schemaHostServices struct {
	Host     string
	Services []string
}

func Load(path string) (*Schema, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, fmt.Errorf("read schema file [%s]: %w", path, err)
	}
	var schema Schema
	if err := json.Unmarshal(data, &schema); err != nil {
		return nil, fmt.Errorf("unmarshal schema: %w", err)
	}
	if !versionPattern.MatchString(schema.Asystem.Version) {
		return nil, fmt.Errorf("invalid version [%s]", schema.Asystem.Version)
	}
	seenHosts := map[string]bool{}
	for i := range schema.Asystem.Services {
		hostServices := &schema.Asystem.Services[i]
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
	return &schema, nil
}

func (s *Schema) Version() string { return s.Asystem.Version }

func (s *Schema) Hosts() []string {
	hosts := make([]string, len(s.Asystem.Services))
	for i := range s.Asystem.Services {
		hosts[i] = s.Asystem.Services[i].Host
	}
	sort.Strings(hosts)
	return hosts
}

func (s *Schema) Services(host string) []string {
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
