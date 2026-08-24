package probe

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"sort"
	"strconv"
	"strings"
	"supervisor/internal/scribe"
	"sync"
	"syscall"
	"time"
)

type mountUsage struct {
	device     string
	mountpoint string
	fstype     string
	share      bool
	remote     bool
	total      uint64
	used       uint64
	measured   bool
	failed     bool
}

type driveWear struct {
	kernel  string
	model   string
	life    float64
	rated   bool
	errored bool
}

type mountSnapshot struct {
	taken  time.Time
	mounts []mountUsage
	drives []driveWear
	shares int
	locals int
	failed int
}

type driveIdentity struct {
	kernel     string
	node       string
	model      string
	rating     float64
	baseline   int64
	rated      bool
	identified bool
	warned     bool
}

type mountSet struct {
	root       string
	mu         sync.Mutex
	current    *mountSnapshot
	refreshing bool
	physicals  map[string]string
	identities map[string]*driveIdentity
	inflight   map[string]bool
	statfs     func(path string) (uint64, uint64, error)
	smart      func(node string) (smartReport, error)
}

func loadMounts(root string, window time.Duration) *mountSet {
	mountCacheMu.RLock()
	cached, found := mountCache[root]
	mountCacheMu.RUnlock()
	if !found {
		mountCacheMu.Lock()
		if cached, found = mountCache[root]; !found {
			cached = &mountSet{
				root:       root,
				physicals:  map[string]string{},
				identities: map[string]*driveIdentity{},
				inflight:   map[string]bool{},
				statfs:     mountStatfs,
				smart:      mountSmart,
			}
			mountCache[root] = cached
		}
		mountCacheMu.Unlock()
	}
	cached.request(window)
	return cached
}

func resetMounts() {
	mountCacheMu.Lock()
	defer mountCacheMu.Unlock()
	clear(mountCache)
}

func (s *mountSet) request(window time.Duration) {
	s.mu.Lock()
	if s.current != nil && s.current.failed > 0 && mountRetry < window {
		window = mountRetry
	}
	stale := s.current == nil || time.Since(s.current.taken) >= window
	if !stale || s.refreshing {
		s.mu.Unlock()
		return
	}
	s.refreshing = true
	s.mu.Unlock()
	go func() {
		refreshStart := time.Now()
		defer func() {
			failure := recover()
			if failure == nil {
				return
			}
			s.mu.Lock()
			s.refreshing = false
			s.mu.Unlock()
			scribe.Probe("state", "host").Error("mounts", refreshStart, "panicked [%v] refreshing, keeping the previous snapshot", failure)
		}()
		taken := s.collect()
		s.mu.Lock()
		s.current = taken
		s.refreshing = false
		s.mu.Unlock()
	}()
}

func (s *mountSet) snapshot() (*mountSnapshot, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	if s.current == nil {
		return nil, errProbeWarmingUp
	}
	return s.current, nil
}

func (s *mountSet) usedSystemSpace() (int8, error) {
	taken, err := s.snapshot()
	if err != nil {
		return 0, err
	}
	worst := 0.0
	found := false
	for _, mount := range taken.mounts {
		if mount.share || !mount.measured || mount.total == 0 {
			continue
		}
		used := float64(mount.used) / float64(mount.total) * 100.0
		if !found || used > worst {
			worst = used
		}
		found = true
	}
	if !found {
		return 0, errors.New("no system filesystems measured")
	}
	return int8Percent(worst), nil
}

func (s *mountSet) usedShareSpace() (int8, error) {
	taken, err := s.snapshot()
	if err != nil {
		return 0, err
	}
	if taken.locals == 0 {
		return 0, nil
	}
	total := uint64(0)
	used := uint64(0)
	for _, mount := range taken.mounts {
		if !mount.share || mount.remote || !mount.measured {
			continue
		}
		total += mount.total
		used += mount.used
	}
	if total == 0 {
		return 0, errors.New("no local shares measured")
	}
	return int8Percent(float64(used) / float64(total) * 100.0), nil
}

func (s *mountSet) failedShares() (int8, error) {
	taken, err := s.snapshot()
	if err != nil {
		return 0, err
	}
	if taken.shares == 0 {
		return 0, nil
	}
	return int8Percent(float64(taken.failed) / float64(taken.shares) * 100.0), nil
}

func (s *mountSet) lifeUsedDrives() (int8, error) {
	taken, err := s.snapshot()
	if err != nil {
		return 0, err
	}
	worst := 0.0
	rated := 0
	for _, drive := range taken.drives {
		if !drive.rated {
			continue
		}
		rated++
		if drive.life > worst {
			worst = drive.life
		}
	}
	if rated == 0 {
		return 0, nil
	}
	return int8Percent(worst), nil
}

func (s *mountSet) drivesErrored() bool {
	taken, err := s.snapshot()
	if err != nil {
		return false
	}
	for _, drive := range taken.drives {
		if drive.errored {
			return true
		}
	}
	return false
}

func (s *mountSet) collect() *mountSnapshot {
	collectStart := time.Now()
	taken := &mountSnapshot{taken: time.Now()}
	mounts := s.parseMounts()
	expected := s.parseFstab()
	for index := range mounts {
		total, used, err := s.measure(mounts[index].mountpoint, mounts[index].share)
		if err != nil {
			mounts[index].failed = true
			continue
		}
		mounts[index].total = total
		mounts[index].used = used
		mounts[index].measured = true
	}
	mounted := map[string]mountUsage{}
	for index := range mounts {
		mounted[mounts[index].mountpoint] = mounts[index]
	}
	taken.mounts = mounts
	taken.shares = len(expected)
	for _, mount := range mounts {
		if mount.share && !mount.remote {
			taken.locals++
		}
	}
	for _, mountpoint := range expected {
		mount, live := mounted[mountpoint]
		if live {
			if mount.failed {
				taken.failed++
			}
			continue
		}
		if _, _, err := s.measure(mountpoint, true); err != nil {
			taken.failed++
		}
	}
	taken.drives = s.wear(mounts)
	scribe.Probe("state", "host").Debug("mounts", collectStart, "scanned  [%d] mounts, shares [%d], failed [%d], drives [%d]",
		len(mounts), taken.shares, taken.failed, len(taken.drives))
	return taken
}

func (s *mountSet) parseMounts() []mountUsage {
	parseStart := time.Now()
	data, err := os.ReadFile(filepath.Join(s.root, mountTablePath))
	if err != nil {
		scribe.Probe("state", "host").Warn("mounts", parseStart, "unreadable [%s] mount table with [%v], reporting no filesystems",
			filepath.Join(s.root, mountTablePath), err)
		return nil
	}
	devices := map[string]string{}
	var mounts []mountUsage
	for _, line := range strings.Split(string(data), "\n") {
		fields := strings.Fields(line)
		if len(fields) < 3 {
			continue
		}
		device, mountpoint, fstype := fields[0], mountUnescape(fields[1]), fields[2]
		share, remote, keep := mountClass(fstype, mountpoint)
		if !keep {
			continue
		}
		if !share {
			if seen, found := devices[device]; found && len(seen) <= len(mountpoint) {
				continue
			}
			devices[device] = mountpoint
		}
		mounts = append(mounts, mountUsage{device: device, mountpoint: mountpoint, fstype: fstype, share: share, remote: remote})
	}
	deduped := mounts[:0]
	for _, mount := range mounts {
		if !mount.share && devices[mount.device] != mount.mountpoint {
			continue
		}
		deduped = append(deduped, mount)
	}
	sort.Slice(deduped, func(first, second int) bool { return deduped[first].mountpoint < deduped[second].mountpoint })
	return deduped
}

func (s *mountSet) parseFstab() []string {
	data, err := os.ReadFile(filepath.Join(s.root, mountFstabPath))
	if err != nil {
		return nil
	}
	var expected []string
	for _, line := range strings.Split(string(data), "\n") {
		if trimmed := strings.TrimSpace(line); trimmed == "" || strings.HasPrefix(trimmed, "#") {
			continue
		}
		fields := strings.Fields(line)
		if len(fields) < 4 {
			continue
		}
		mountpoint := mountUnescape(fields[1])
		if !strings.HasPrefix(mountpoint, mountShareRoot+"/") {
			continue
		}
		if slices := strings.Split(fields[3], ","); mountOptioned(slices, mountNoAuto) {
			continue
		}
		expected = append(expected, mountpoint)
	}
	sort.Strings(expected)
	return expected
}

func (s *mountSet) measure(mountpoint string, share bool) (uint64, uint64, error) {
	type measurement struct {
		total uint64
		used  uint64
		err   error
	}
	s.mu.Lock()
	outstanding := s.inflight[mountpoint]
	if !outstanding {
		s.inflight[mountpoint] = true
	}
	s.mu.Unlock()
	if outstanding {
		return 0, 0, fmt.Errorf("mount [%s] has not answered a probe still outstanding", mountpoint)
	}
	done := make(chan measurement, 1)
	go func() {
		defer func() {
			s.mu.Lock()
			delete(s.inflight, mountpoint)
			s.mu.Unlock()
			if failure := recover(); failure != nil {
				done <- measurement{err: fmt.Errorf("mount [%s] panicked with [%v]", mountpoint, failure)}
			}
		}()
		total, used, err := s.statfs(filepath.Join(s.root, mountpoint))
		if err == nil && share {
			err = s.content(mountpoint)
		}
		done <- measurement{total: total, used: used, err: err}
	}()
	select {
	case taken := <-done:
		return taken.total, taken.used, taken.err
	case <-time.After(mountDeadline):
		return 0, 0, fmt.Errorf("mount [%s] did not answer within [%d] ms", mountpoint, mountDeadline.Milliseconds())
	}
}

func (s *mountSet) content(mountpoint string) error {
	entry, err := os.Stat(filepath.Join(s.root, mountpoint, mountContentDir))
	if err != nil {
		return fmt.Errorf("share [%s] holds no [%s] directory with [%w]", mountpoint, mountContentDir, err)
	}
	if !entry.IsDir() {
		return fmt.Errorf("share [%s] holds a [%s] that is not a directory", mountpoint, mountContentDir)
	}
	return nil
}

func (s *mountSet) wear(mounts []mountUsage) []driveWear {
	seen := map[string]bool{}
	var drives []driveWear
	for _, mount := range mounts {
		if mount.remote || !strings.HasPrefix(mount.device, "/dev/") {
			continue
		}
		physical := s.physical(mount.device)
		if physical == "" || seen[physical] {
			continue
		}
		seen[physical] = true
		drives = append(drives, s.reading(physical))
	}
	sort.Slice(drives, func(first, second int) bool { return drives[first].kernel < drives[second].kernel })
	return drives
}

func (s *mountSet) physical(device string) string {
	s.mu.Lock()
	cached, found := s.physicals[device]
	s.mu.Unlock()
	if found {
		return cached
	}
	resolved := s.resolve(strings.TrimPrefix(device, "/dev/"), 0)
	s.mu.Lock()
	s.physicals[device] = resolved
	s.mu.Unlock()
	return resolved
}

func (s *mountSet) resolve(kernel string, depth int) string {
	if kernel == "" || depth > mountResolveMax {
		return ""
	}
	if strings.HasPrefix(kernel, "mapper/") {
		return s.resolve(s.mapper(strings.TrimPrefix(kernel, "mapper/")), depth+1)
	}
	block := filepath.Join(s.root, mountBlockPath, kernel)
	target, err := os.Readlink(block)
	if err != nil {
		return ""
	}
	if slaves, err := os.ReadDir(filepath.Join(block, "slaves")); err == nil && len(slaves) > 0 {
		return s.resolve(slaves[0].Name(), depth+1)
	}
	if _, err := os.Stat(filepath.Join(block, "partition")); err == nil {
		return s.resolve(filepath.Base(filepath.Dir(target)), depth+1)
	}
	if controller := mountController(target); controller != "" {
		return controller
	}
	return kernel
}

func (s *mountSet) mapper(name string) string {
	entries, err := os.ReadDir(filepath.Join(s.root, mountBlockPath))
	if err != nil {
		return ""
	}
	for _, entry := range entries {
		if !strings.HasPrefix(entry.Name(), "dm-") {
			continue
		}
		data, err := os.ReadFile(filepath.Join(s.root, mountBlockPath, entry.Name(), "dm", "name"))
		if err != nil {
			continue
		}
		if strings.TrimSpace(string(data)) == name {
			return entry.Name()
		}
	}
	return ""
}

func (s *mountSet) reading(physical string) driveWear {
	identity := s.identity(physical)
	readingStart := time.Now()
	report, err := s.smart(identity.node)
	if err != nil {
		if !identity.warned {
			identity.warned = true
			scribe.Probe("state", "host").Warn("drives", readingStart, "unreadable [%s] drive with [%v], excluding from wear", physical, err)
		}
		return driveWear{kernel: physical, model: identity.model}
	}
	s.identify(identity, report, readingStart)
	wear := driveWear{kernel: physical, model: identity.model, rated: identity.rated}
	if report.errors > identity.baseline {
		wear.errored = true
	}
	if identity.rated && report.written > 0 {
		wear.life = report.written / (identity.rating * bytesPerTB) * 100.0
	}
	return wear
}

func (s *mountSet) identify(identity *driveIdentity, report smartReport, identifyStart time.Time) {
	if identity.identified {
		return
	}
	identity.identified = true
	identity.model = report.model
	identity.baseline = report.errors
	switch {
	case !report.supported:
		scribe.Probe("state", "host").Warn("drives", identifyStart, "unsupported [%s] drive reports no smart support, excluding from wear", identity.kernel)
	case driveRatings[report.model] > 0:
		identity.rating = driveRatings[report.model]
		identity.rated = true
	default:
		scribe.Probe("state", "host").Warn("drives", identifyStart, "unrated [%s] drive model [%s] absent from the ratings, excluding from wear", identity.kernel, report.model)
	}
}

func (s *mountSet) identity(physical string) *driveIdentity {
	s.mu.Lock()
	defer s.mu.Unlock()
	if cached, found := s.identities[physical]; found {
		return cached
	}
	identity := &driveIdentity{kernel: physical, node: filepath.Join(s.root, "dev", physical)}
	s.identities[physical] = identity
	return identity
}

type smartReport struct {
	model     string
	written   float64
	errors    int64
	supported bool
}

func mountSmart(node string) (smartReport, error) {
	ctx, cancel := context.WithTimeout(context.Background(), mountDeadline)
	defer cancel()
	output, err := exec.CommandContext(ctx, mountSmartCommand, "--json", "-a", node).Output()
	if len(output) == 0 {
		if err == nil {
			err = errors.New("smart returned no output")
		}
		return smartReport{}, err
	}
	var decoded struct {
		ModelName    string `json:"model_name"`
		SmartSupport struct {
			Available bool `json:"available"`
		} `json:"smart_support"`
		NvmeLog struct {
			DataUnitsWritten float64 `json:"data_units_written"`
			ErrorLogEntries  int64   `json:"num_err_log_entries"`
		} `json:"nvme_smart_health_information_log"`
		AtaAttributes struct {
			Table []struct {
				ID   int    `json:"id"`
				Name string `json:"name"`
				Raw  struct {
					Value float64 `json:"value"`
				} `json:"raw"`
			} `json:"table"`
		} `json:"ata_smart_attributes"`
	}
	if err := json.Unmarshal(output, &decoded); err != nil {
		return smartReport{}, fmt.Errorf("smart output not parseable with [%w]", err)
	}
	report := smartReport{model: strings.TrimSpace(decoded.ModelName)}
	report.supported = report.model != ""
	if decoded.NvmeLog.DataUnitsWritten > 0 {
		report.written = decoded.NvmeLog.DataUnitsWritten * bytesPerDataUnit
		report.errors = decoded.NvmeLog.ErrorLogEntries
		return report, nil
	}
	for _, attribute := range decoded.AtaAttributes.Table {
		switch attribute.ID {
		case driveAttributeErrors:
			report.errors = int64(attribute.Raw.Value)
		case driveAttributeWritten, driveAttributeWrittenAlt:
			if written := driveWritten(attribute.ID, attribute.Name, attribute.Raw.Value); written > 0 && (report.written == 0 || attribute.ID == driveAttributeWritten) {
				report.written = written
			}
		}
	}
	if len(decoded.AtaAttributes.Table) == 0 && decoded.NvmeLog.DataUnitsWritten == 0 {
		report.supported = false
	}
	return report, nil
}

func driveWritten(id int, name string, raw float64) float64 {
	if id == driveAttributeWrittenAlt && strings.Contains(strings.ToLower(name), "erase") {
		return 0
	}
	if strings.Contains(strings.ToLower(name), "gib") {
		return raw * bytesPerGiB
	}
	return raw * bytesPerSector
}

func mountStatfs(path string) (uint64, uint64, error) {
	var stat syscall.Statfs_t
	if err := syscall.Statfs(path, &stat); err != nil {
		return 0, 0, err
	}
	size := uint64(stat.Bsize)
	total := stat.Blocks * size
	used := (stat.Blocks - stat.Bfree) * size
	return total, used, nil
}

func mountClass(fstype, mountpoint string) (bool, bool, bool) {
	if mountRemoteTypes[fstype] {
		return true, true, strings.HasPrefix(mountpoint, mountShareRoot+"/")
	}
	if !mountLocalTypes[fstype] {
		return false, false, false
	}
	if strings.HasPrefix(mountpoint, mountShareRoot+"/") {
		return true, false, true
	}
	if mountpoint == mountBootRoot || strings.HasPrefix(mountpoint, mountBootRoot+"/") {
		return false, false, false
	}
	return false, false, true
}

func mountController(target string) string {
	segments := strings.Split(target, "/")
	for index, segment := range segments {
		if segment == "nvme" && index+1 < len(segments) {
			return segments[index+1]
		}
	}
	return ""
}

func mountOptioned(options []string, wanted string) bool {
	for _, option := range options {
		if strings.TrimSpace(option) == wanted {
			return true
		}
	}
	return false
}

func mountUnescape(field string) string {
	if !strings.Contains(field, "\\") {
		return field
	}
	unquoted, err := strconv.Unquote("\"" + field + "\"")
	if err != nil {
		return field
	}
	return unquoted
}

func int8Percent(value float64) int8 {
	if value < 0 {
		return 0
	}
	if value > 100 {
		return 100
	}
	return int8(value + 0.5)
}

const (
	mountTablePath           = "proc/mounts"
	mountFstabPath           = "etc/fstab"
	mountBlockPath           = "sys/class/block"
	mountShareRoot           = "/share"
	mountContentDir          = "media"
	mountBootRoot            = "/boot"
	mountNoAuto              = "noauto"
	mountSmartCommand        = "smartctl"
	mountDeadline            = 5 * time.Second
	mountRetry               = time.Minute
	mountResolveMax          = 8
	bytesPerSector           = 512.0
	bytesPerDataUnit         = 512000.0
	bytesPerGiB              = 1073741824.0
	bytesPerTB               = 1000000000000.0
	driveAttributeErrors     = 1
	driveAttributeWritten    = 241
	driveAttributeWrittenAlt = 246
)

var driveRatings = map[string]float64{
	"Lexar SSD NM790 4TB":   3000,
	"CT4000MX500SSD1":       1000,
	"CT4000P3PSSD8":         800,
	"CT2000MX500SSD1":       700,
	"Lexar SSD NQ710 2TB":   680,
	"CT2000P2SSD8":          600,
	"CT1000MX500SSD1":       360,
	"APPLE SSD AP0512Z":     300,
	"CT500MX500SSD1":        180,
	"KINGSTON SA400S37480G": 160,
	"CT480BX500SSD1":        120,
	"ST2000LM007-1R8174":    0,
}

var mountLocalTypes = map[string]bool{"ext4": true, "xfs": true, "btrfs": true, "f2fs": true, "vfat": true}

var mountRemoteTypes = map[string]bool{"cifs": true, "nfs": true, "nfs4": true, "smb3": true}

var (
	mountCache   = map[string]*mountSet{}
	mountCacheMu sync.RWMutex
)
