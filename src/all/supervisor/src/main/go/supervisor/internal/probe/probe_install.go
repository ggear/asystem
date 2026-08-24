package probe

import (
	"errors"
	"fmt"
	"hash/fnv"
	"os"
	"sort"
	"strings"
	"supervisor/internal/config"
	"supervisor/internal/scribe"
	"sync"
	"time"

	"github.com/docker/go-units"
	"go.yaml.in/yaml/v3"
)

type installReader struct {
	configPath string
	hostName   string
}

func newInstallReader(configPath, hostName string) installReader {
	return installReader{configPath: configPath, hostName: hostName}
}

func (r installReader) snapshot() *installSnapshot {
	return loadInstallTree(config.Load(r.configPath).Mount()).snapshot()
}

func (r installReader) allocation() (int64, error) {
	return r.snapshot().allocation(config.Load(r.configPath).Services(r.hostName))
}

type installService struct {
	serviceModule  bool
	version        string
	sleepEnabled   bool
	backupEnabled  bool
	maxMemoryBytes int64
}

type installSnapshot struct {
	services map[string]installService
}

type installTree struct {
	mount      string
	mu         sync.Mutex
	buffer     []byte
	cached     *installSnapshot
	stamp      uint64
	generation uint64
}

func loadInstallTree(mount string) *installTree {
	installTreeCacheMu.RLock()
	if cached, ok := installTreeCache[mount]; ok {
		installTreeCacheMu.RUnlock()
		return cached
	}
	installTreeCacheMu.RUnlock()
	installTreeCacheMu.Lock()
	defer installTreeCacheMu.Unlock()
	if cached, ok := installTreeCache[mount]; ok {
		return cached
	}
	created := &installTree{mount: mount, buffer: make([]byte, 0, installBufferBytes)}
	installTreeCache[mount] = created
	return created
}

func resetInstallTrees() {
	installTreeCacheMu.Lock()
	defer installTreeCacheMu.Unlock()
	clear(installTreeCache)
}

func (t *installTree) snapshot() *installSnapshot {
	t.mu.Lock()
	defer t.mu.Unlock()
	scanStart := time.Now()
	stamp := t.fingerprint()
	if t.cached != nil && stamp == t.stamp {
		return t.cached
	}
	t.stamp = stamp
	t.generation++
	t.cached = t.parse()
	scribe.Probe("state", "install").Debug("scan", scanStart, "parsed   [%d] services generation [%d]", len(t.cached.services), t.generation)
	return t.cached
}

func (s *installSnapshot) service(name string) (installService, bool) {
	if s == nil {
		return installService{}, false
	}
	entry, found := s.services[name]
	return entry, found
}

func (s *installSnapshot) names() []string {
	if s == nil {
		return nil
	}
	names := make([]string, 0, len(s.services))
	for name := range s.services {
		names = append(names, name)
	}
	sort.Strings(names)
	return names
}

func (s *installSnapshot) allocation(names []string) (int64, error) {
	if len(names) == 0 {
		return 0, errors.New("no services configured for the host")
	}
	total := int64(0)
	installed := 0
	for _, name := range names {
		entry, found := s.service(name)
		if !found || !entry.serviceModule {
			continue
		}
		installed++
		if entry.maxMemoryBytes <= 0 {
			continue
		}
		total += entry.maxMemoryBytes
	}
	if installed == 0 {
		return 0, fmt.Errorf("none of the [%d] configured services are installed as service modules under [%s]", len(names), installRoot)
	}
	return total, nil
}

func (t *installTree) bases() []string {
	if t.mount == "" {
		return []string{""}
	}
	return []string{t.mount, ""}
}

func (t *installTree) home(base, name string) string {
	latest := base + installRoot + "/" + name + "/" + installLatestLink
	if base == "" {
		return latest
	}
	target, err := os.Readlink(latest)
	if err != nil || !strings.HasPrefix(target, "/") {
		return latest
	}
	return base + target
}

func (t *installTree) fingerprint() uint64 {
	hash := fnv.New64a()
	stamp := make([]byte, 0, 16)
	for _, base := range t.bases() {
		root := base + installRoot
		entries, err := os.ReadDir(root)
		if err != nil {
			hash.Write([]byte(root))
			hash.Write(installAbsentMark)
			continue
		}
		for _, entry := range entries {
			for _, suffix := range []string{"/" + installLatestLink, "/" + installSleepMarker} {
				t.buffer = t.buffer[:0]
				t.buffer = append(t.buffer, root...)
				t.buffer = append(t.buffer, '/')
				t.buffer = append(t.buffer, entry.Name()...)
				t.buffer = append(t.buffer, suffix...)
				hash.Write(t.buffer)
				info, statErr := os.Lstat(string(t.buffer))
				if statErr != nil {
					hash.Write(installAbsentMark)
					continue
				}
				stamp = stamp[:0]
				stamp = installAppendInt64(stamp, info.ModTime().UnixNano())
				stamp = installAppendInt64(stamp, info.Size())
				hash.Write(stamp)
			}
		}
	}
	return hash.Sum64()
}

func (t *installTree) parse() *installSnapshot {
	snapshot := &installSnapshot{services: map[string]installService{}}
	for _, base := range t.bases() {
		root := base + installRoot
		entries, err := os.ReadDir(root)
		if err != nil {
			continue
		}
		for _, entry := range entries {
			name := entry.Name()
			if !entry.IsDir() || strings.HasPrefix(name, ".") {
				continue
			}
			if _, found := snapshot.services[name]; found {
				continue
			}
			home := t.home(base, name)
			installed := installService{}
			installed.sleepEnabled = installSleepEnabled(root, name)
			installed.backupEnabled = installBackupEnabled(home)
			installed.version = installVersion(home, name)
			installed.serviceModule = installServiceModule(home)
			if installed.serviceModule {
				installed.maxMemoryBytes = installMaxMemory(home, name)
			}
			snapshot.services[name] = installed
		}
	}
	return snapshot
}

func installSleepEnabled(root, name string) bool {
	_, err := os.Lstat(root + "/" + name + "/" + installSleepMarker)
	return err == nil
}

func installServiceModule(home string) bool {
	_, err := os.Lstat(home + "/" + installComposeFile)
	return err == nil
}

func installBackupEnabled(home string) bool {
	_, err := os.Lstat(home + "/" + installBackupScript)
	return err == nil
}

func installVersion(home, name string) string {
	versionStart := time.Now()
	path := home + "/" + installEnvironmentFile
	data, err := os.ReadFile(path)
	if err != nil {
		scribe.Probe("state", "install").Error("version", versionStart, "missing  [%s] version not readable from [%s] with [%v]", name, path, err)
		return ""
	}
	for _, line := range strings.Split(string(data), "\n") {
		value, found := strings.CutPrefix(line, installVersionKey)
		if !found {
			continue
		}
		if !config.VersionPattern.MatchString(value) {
			scribe.Probe("state", "install").Error("version", versionStart, "invalid  [%s] version [%s] from [%s] could not be parsed", name, value, path)
			return ""
		}
		return value
	}
	scribe.Probe("state", "install").Error("version", versionStart, "missing  [%s] version not declared in [%s]", name, path)
	return ""
}

func installMaxMemory(home, name string) int64 {
	memoryStart := time.Now()
	path := home + "/" + installComposeFile
	data, err := os.ReadFile(path)
	if err != nil {
		scribe.Probe("state", "install").Error("memory", memoryStart, "missing  [%s] compose not readable from [%s] with [%v]", name, path, err)
		return 0
	}
	var compose installCompose
	if err := yaml.Unmarshal(data, &compose); err != nil {
		scribe.Probe("state", "install").Error("memory", memoryStart, "invalid  [%s] compose [%s] could not be parsed with [%v]", name, path, err)
		return 0
	}
	keys := make([]string, 0, len(compose.Services))
	for key := range compose.Services {
		keys = append(keys, key)
	}
	sort.Strings(keys)
	total := int64(0)
	for _, key := range keys {
		composed := compose.Services[key]
		if strings.Trim(composed.Restart, "'\"") == installRestartNever {
			continue
		}
		limit := composed.Deploy.Resources.Limits.Memory
		if limit == "" {
			scribe.Probe("state", "install").Error("memory", memoryStart, "missing  [%s] service [%s] declares no memory limit in [%s]", name, key, path)
			continue
		}
		limitBytes, limitErr := units.RAMInBytes(limit)
		if limitErr != nil {
			scribe.Probe("state", "install").Error("memory", memoryStart, "invalid  [%s] service [%s] memory [%s] in [%s] with [%v]", name, key, limit, path, limitErr)
			continue
		}
		total += limitBytes
	}
	return total
}

func installAppendInt64(target []byte, value int64) []byte {
	for shift := 0; shift < 64; shift += 8 {
		target = append(target, byte(value>>shift))
	}
	return target
}

type installCompose struct {
	Services map[string]installComposeService `yaml:"services"`
}

type installComposeService struct {
	Restart string `yaml:"restart"`
	Deploy  struct {
		Resources struct {
			Limits struct {
				Memory string `yaml:"memory"`
			} `yaml:"limits"`
		} `yaml:"resources"`
	} `yaml:"deploy"`
}

const (
	installRoot            = "/var/lib/asystem/install"
	installLatestLink      = "latest"
	installSleepMarker     = ".sleep"
	installEnvironmentFile = ".env"
	installBackupScript    = "backup.sh"
	installComposeFile     = "docker-compose.yml"
	installVersionKey      = "SERVICE_VERSION_ABSOLUTE="
	installRestartNever    = "no"
	installBufferBytes     = 256
)

var installAbsentMark = []byte{0xff}

var (
	installTreeCache   = map[string]*installTree{}
	installTreeCacheMu sync.RWMutex
)
