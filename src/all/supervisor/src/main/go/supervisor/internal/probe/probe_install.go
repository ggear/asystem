package probe

import (
	"fmt"
	"hash/fnv"
	"os"
	"sort"
	"strings"
	"supervisor/internal/config"
	"supervisor/internal/metric"
	"supervisor/internal/scribe"
	"sync"
	"time"

	"github.com/docker/go-units"
	"go.yaml.in/yaml/v3"
)

func init() {
	scribe.Attribute(scribe.SourceProbeInstall,
		metric.MetricHostAllocatedMemory,
		metric.MetricHostServicesMaxMemory,
		metric.MetricServiceMaxMemory,
		metric.MetricServiceVersion)
}

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

func (r installReader) allocation() (int64, int, error) {
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
	mutex      sync.Mutex
	buffer     []byte
	cached     *installSnapshot
	stamp      uint64
	generation uint64
}

func loadInstallTree(mount string) *installTree {
	installTreeCacheMutex.RLock()
	if cached, ok := installTreeCache[mount]; ok {
		installTreeCacheMutex.RUnlock()
		return cached
	}
	installTreeCacheMutex.RUnlock()
	installTreeCacheMutex.Lock()
	defer installTreeCacheMutex.Unlock()
	if cached, ok := installTreeCache[mount]; ok {
		return cached
	}
	created := &installTree{mount: mount, buffer: make([]byte, 0, installBufferBytes)}
	installTreeCache[mount] = created
	return created
}

func resetInstallTrees() {
	installTreeCacheMutex.Lock()
	defer installTreeCacheMutex.Unlock()
	clear(installTreeCache)
}

func (t *installTree) snapshot() *installSnapshot {
	t.mutex.Lock()
	defer t.mutex.Unlock()
	scanStart := time.Now()
	stamp := t.fingerprint()
	if t.cached != nil && stamp == t.stamp {
		return t.cached
	}
	t.stamp = stamp
	t.generation++
	t.cached = t.parse()
	scribe.Log(scribe.SourceProbeInstall, scribe.SubjectNone, scribe.ActionDiscover).Debug("snapshot", scanStart, "services [%d], generation [%d] under [%s]", len(t.cached.services), t.generation, t.mount+installRoot)
	t.cached.report(scanStart)
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

func (s *installSnapshot) allocation(names []string) (int64, int, error) {
	if len(names) == 0 {
		return 0, 0, fmt.Errorf("no memory ceiling summed, no services are configured for this host so the schema in the config file names none to read from [%s] [%w]", installRoot, errEnvironment)
	}
	total := int64(0)
	installed := 0
	var missing []string
	for _, name := range names {
		entry, found := s.service(name)
		if !found || !entry.serviceModule {
			missing = append(missing, name)
			continue
		}
		installed++
		if entry.maxMemoryBytes <= 0 {
			continue
		}
		total += entry.maxMemoryBytes
	}
	if installed == 0 {
		return 0, 0, fmt.Errorf("no memory ceiling summed, none of the [%d] configured services are installed as service modules under [%s], absent [%s]",
			len(names), installRoot, strings.Join(missing, ","))
	}
	return total, installed, nil
}

func (s *installSnapshot) report(scanStart time.Time) {
	names := make([]string, 0, len(s.services))
	for name := range s.services {
		names = append(names, name)
	}
	sort.Strings(names)
	for _, name := range names {
		entry := s.services[name]
		if !entry.serviceModule {
			scribe.Log(scribe.SourceProbeInstall, scribe.SubjectMetric(metric.MetricHostAllocatedMemory), scribe.ActionDiscover).Debug("examined", scanStart, "[%s] is a host module with no compose file, not counted in the allocation", name)
			continue
		}
		if entry.maxMemoryBytes <= 0 {
			scribe.Log(scribe.SourceProbeInstall, scribe.SubjectMetric(metric.MetricHostAllocatedMemory), scribe.ActionDiscover).Debug("examined", scanStart, "[%s] version [%s] declares no memory ceiling, contributing [0] MiB to the allocation", name, entry.version)
			continue
		}
		scribe.Log(scribe.SourceProbeInstall, scribe.SubjectMetric(metric.MetricHostAllocatedMemory), scribe.ActionDiscover).Debug("examined", scanStart, "[%s] version [%s] contributes [%5d] MiB to the allocation, sleeping [%v]", name, entry.version, entry.maxMemoryBytes/bytesPerMiB, entry.sleepEnabled)
	}
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
	writeHash := func(data []byte) {
		if _, err := hash.Write(data); err != nil {
			panic(fmt.Sprintf("write install fingerprint: %v", err))
		}
	}
	stamp := make([]byte, 0, 16)
	for _, base := range t.bases() {
		root := base + installRoot
		entries, err := os.ReadDir(root)
		if err != nil {
			writeHash([]byte(root))
			writeHash(installAbsentMark)
			continue
		}
		for _, entry := range entries {
			for _, suffix := range []string{"/" + installLatestLink, "/" + installSleepMarker} {
				t.buffer = t.buffer[:0]
				t.buffer = append(t.buffer, root...)
				t.buffer = append(t.buffer, '/')
				t.buffer = append(t.buffer, entry.Name()...)
				t.buffer = append(t.buffer, suffix...)
				writeHash(t.buffer)
				info, statErr := os.Lstat(string(t.buffer))
				if statErr != nil {
					writeHash(installAbsentMark)
					continue
				}
				stamp = stamp[:0]
				stamp = installAppendInt64(stamp, info.ModTime().UnixNano())
				stamp = installAppendInt64(stamp, info.Size())
				writeHash(stamp)
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
		scribe.Log(scribe.SourceProbeInstall, scribe.SubjectService(name), scribe.ActionDiscover).Warn("notfound", versionStart, "version not readable from [%s] with [%v]", path, err)
		return ""
	}
	for line := range strings.SplitSeq(string(data), "\n") {
		value, found := strings.CutPrefix(line, installVersionKey)
		if !found {
			continue
		}
		if !config.VersionPattern.MatchString(value) {
			scribe.Log(scribe.SourceProbeInstall, scribe.SubjectService(name), scribe.ActionDiscover).Warn("unusable", versionStart, "version [%s] from [%s] could not be parsed", value, path)
			return ""
		}
		return value
	}
	scribe.Log(scribe.SourceProbeInstall, scribe.SubjectService(name), scribe.ActionDiscover).Warn("notfound", versionStart, "version not declared in [%s]", path)
	return ""
}

func installMaxMemory(home, name string) int64 {
	memoryStart := time.Now()
	path := home + "/" + installComposeFile
	data, err := os.ReadFile(path)
	if err != nil {
		scribe.Log(scribe.SourceProbeInstall, scribe.SubjectService(name), scribe.ActionDiscover).Warn("notfound", memoryStart, "compose not readable from [%s] with [%v]", path, err)
		return 0
	}
	var compose installCompose
	if err := yaml.Unmarshal(data, &compose); err != nil {
		scribe.Log(scribe.SourceProbeInstall, scribe.SubjectService(name), scribe.ActionDiscover).Warn("unusable", memoryStart, "compose [%s] could not be parsed with [%v]", path, err)
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
			scribe.Log(scribe.SourceProbeInstall, scribe.SubjectService(name), scribe.ActionDiscover).Warn("notfound", memoryStart, "compose service [%s] declares no memory limit in [%s]", key, path)
			continue
		}
		limitBytes, limitErr := units.RAMInBytes(limit)
		if limitErr != nil {
			scribe.Log(scribe.SourceProbeInstall, scribe.SubjectService(name), scribe.ActionDiscover).Warn("unusable", memoryStart, "compose service [%s] memory [%s] in [%s] with [%v]", key, limit, path, limitErr)
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
	installRoot            = mountHomeRoot + "/install"
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
	installTreeCache      = map[string]*installTree{}
	installTreeCacheMutex sync.RWMutex
)
