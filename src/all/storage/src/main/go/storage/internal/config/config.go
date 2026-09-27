package config

import (
	"encoding/json"
	"os"
	"regexp"
	"sort"
	"strings"
)

func Load(path string) *Config {
	result := &Config{}
	if path != "" {
		if data, err := os.ReadFile(path); err == nil {
			var raw struct{ Asystem configData }
			if json.Unmarshal(data, &raw) == nil {
				result.asystem = raw.Asystem
			}
		}
	}
	result.asystem.Version = resolve("SERVICE_VERSION_ABSOLUTE", result.asystem.Version)
	result.asystem.Host = resolve("STORAGE_HOST", result.asystem.Host)
	if result.asystem.Host == "" {
		if hostName, err := os.Hostname(); err == nil {
			result.asystem.Host = hostName
		}
	}
	return result
}

func (c *Config) Version() string {
	if c != nil && versionPattern.MatchString(c.asystem.Version) {
		return c.asystem.Version
	}
	return defaultVersion
}

func (c *Config) Name() string {
	if c == nil {
		return ""
	}
	return c.asystem.Host
}

func (c *Config) Label() string {
	if host := c.own(); host != nil {
		return host.Label
	}
	return ""
}

func (c *Config) Index() *int {
	if host := c.own(); host != nil {
		return host.Index
	}
	return nil
}

func (c *Config) Hosts() []HostEntry {
	if c == nil {
		return nil
	}
	hosts := append([]HostEntry(nil), c.asystem.Schema...)
	sort.Slice(hosts, func(i, j int) bool { return hosts[i].Label < hosts[j].Label })
	return hosts
}

func (c *Config) Shares() []ShareEntry {
	if host := c.own(); host != nil {
		return host.Shares
	}
	return nil
}

func (c *Config) Backup() *BackupEntry {
	if host := c.own(); host != nil {
		return host.Backup
	}
	return nil
}

func (c *Config) MountLabel(mount string) string {
	host := c.own()
	if host == nil {
		return ""
	}
	for _, share := range host.Shares {
		if share.Mount == mount {
			return share.Label
		}
	}
	if host.Backup != nil && host.Backup.Mount == mount {
		return host.Backup.Label
	}
	return ""
}

func (c *Config) ServedElsewhere(mount string) bool {
	host := c.own()
	if host == nil {
		return false
	}
	for _, share := range host.Shares {
		if share.Mount == mount {
			return share.ServedBy != "" && share.ServedBy != c.asystem.Host
		}
	}
	return false
}

func (c *Config) EstateShares() []ShareEntry {
	if c == nil {
		return nil
	}
	var shares []ShareEntry
	for _, host := range c.asystem.Schema {
		for _, share := range host.Shares {
			if share.ServedBy == host.Host {
				shares = append(shares, share)
			}
		}
	}
	sort.Slice(shares, func(i, j int) bool { return shares[i].Mount < shares[j].Mount })
	return shares
}

func (c *Config) own() *HostEntry {
	if c == nil {
		return nil
	}
	for i := range c.asystem.Schema {
		if c.asystem.Schema[i].Host == c.asystem.Host {
			return &c.asystem.Schema[i]
		}
	}
	return nil
}

func resolve(env, value string) string {
	if resolved := os.Getenv(env); resolved != "" {
		return resolved
	}
	if strings.HasPrefix(value, "$") {
		return os.Getenv(value[1:])
	}
	return value
}

type Config struct{ asystem configData }

type HostEntry struct {
	Index      *int
	Host       string
	Label      string
	FormFactor string `json:"form_factor"`
	OS         string
	Arch       string
	Shares     []ShareEntry
	Backup     *BackupEntry
}

type ShareEntry struct {
	Mount    string
	Label    string
	ServedBy string `json:"served_by"`
	Smb      string
}

type BackupEntry struct {
	Mount string
	Label string
}

type configData struct {
	Version string
	Host    string
	Schema  []HostEntry
}

const (
	DefaultConfigPath = "/var/lib/asystem/install/storage/latest/image/config.json"

	defaultVersion = "00.000.0000-SNAPSHOT"
)

var versionPattern = regexp.MustCompile(`^\d{2}\.\d{3}\.\d{4}(-SNAPSHOT)?$`)
