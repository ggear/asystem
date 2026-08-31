package probe

import (
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strconv"
	"strings"
	"supervisor/internal/config"
	"supervisor/internal/metric"
	"supervisor/internal/scribe"
	"sync"
	"syscall"
	"time"
)

func init() {
	scribe.Attribute(scribe.SourceProbeMounts,
		metric.MetricHostUsedHomeSpace,
		metric.MetricHostUsedShareSpace,
		metric.MetricHostUsedBackupSpace,
		metric.MetricHostFailedShares,
		metric.MetricHostLifeUsedDrives,
		metric.MetricHostFailedDrives)
}

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
	answered   bool
	reason     string
}

type mountSnapshot struct {
	taken  time.Time
	read   time.Time
	table  error
	mounts []mountUsage
	drives []driveWear
	shares int
	locals int
	failed int
	unread int
}

type mountSet struct {
	root       string
	window     time.Duration
	mutex      sync.Mutex
	current    *mountSnapshot
	refreshing bool
	physicals  map[string]string
	identities map[string]*driveIdentity
	inflight   map[string]bool
	statfs     func(path string) (uint64, uint64, error)
	smart      func(node string, kinds []string) (smartReport, error)
}

func loadMounts(root string, window time.Duration) *mountSet {
	mountCacheMu.RLock()
	cached, found := mountCache[root]
	mountCacheMu.RUnlock()
	if !found {
		mountCacheMu.Lock()
		if cached, found = mountCache[root]; !found {
			cached = &mountSet{
				root:       mountBase(root),
				physicals:  map[string]string{},
				identities: map[string]*driveIdentity{},
				inflight:   map[string]bool{},
				statfs:     mountStatfs,
				smart:      driveSmart,
			}
			mountCache[root] = cached
		}
		mountCacheMu.Unlock()
	}
	cached.mutex.Lock()
	cached.window = window
	cached.mutex.Unlock()
	cached.request(window)
	return cached
}

func resetMounts() {
	mountCacheMu.Lock()
	defer mountCacheMu.Unlock()
	clear(mountCache)
}

func (s *mountSet) request(window time.Duration) {
	s.mutex.Lock()
	if s.current != nil && s.current.failed > 0 && mountRetry < window {
		window = mountRetry
	}
	stale := s.current == nil || config.SinceIncludingSuspend(s.current.taken) >= window
	if !stale || s.refreshing {
		s.mutex.Unlock()
		return
	}
	s.refreshing = true
	s.mutex.Unlock()
	go func() {
		refreshStart := time.Now()
		defer func() {
			failure := recover()
			if failure == nil {
				return
			}
			s.mutex.Lock()
			s.refreshing = false
			s.mutex.Unlock()
			scribe.Log(scribe.SourceProbeMounts, scribe.SubjectNone, scribe.ActionSample).Errorf("panicked", refreshStart, "[%v] refreshing [%s], keeping the previous snapshot", failure, filepath.Join(s.root, mountTablePath))
		}()
		taken := s.collect()
		s.mutex.Lock()
		s.current = taken
		s.refreshing = false
		s.mutex.Unlock()
	}()
}

func (s *mountSet) snapshot() (*mountSnapshot, error) {
	s.mutex.Lock()
	defer s.mutex.Unlock()
	if s.current == nil {
		return nil, errProbeWarmingUp
	}
	return s.current, nil
}

func (s *mountSet) usedHomeSpace() (int8, derivation, error) {
	taken, err := s.snapshot()
	if err != nil {
		return 0, derivation{}, err
	}
	if taken.table != nil {
		return 0, derivation{}, fmt.Errorf("no home filesystem read, mount table [%s] unreadable with [%v] [%w]",
			filepath.Join(s.root, mountTablePath), taken.table, errEnvironment)
	}
	systems := 0
	var home *mountUsage
	for index, mount := range taken.mounts {
		if mount.share {
			continue
		}
		systems++
		if !mountHolds(mount.mountpoint, mountHomeRoot) {
			continue
		}
		if home == nil || len(mount.mountpoint) > len(home.mountpoint) {
			home = &taken.mounts[index]
		}
	}
	if home == nil {
		return 0, derivation{}, fmt.Errorf("no home filesystem found holding [%s] of [%d] classed system and [%d] mounts scanned from [%s] [%w]",
			mountHomeRoot, systems, len(taken.mounts), filepath.Join(s.root, mountTablePath), errEnvironment)
	}
	if !home.measured || home.total == 0 {
		return 0, derivation{}, fmt.Errorf("no home filesystem measured of [%s] holding [%s], failures [%s] [%w]",
			home.mountpoint, mountHomeRoot, mountReasons(taken.mounts, false), errEnvironment)
	}
	used := float64(home.used) / float64(home.total) * 100.0
	return percentValue(used), derivedf(scribe.ActionSample, "computed [%3d] pct used home, used [%d] MiB of total [%d] MiB on [%s] holding [%s] of [%d] filesystems, snapshot taken [%s] ago",
		percentValue(used), home.used/bytesPerMiB, home.total/bytesPerMiB, home.mountpoint, mountHomeRoot, systems, config.SinceIncludingSuspend(taken.taken).Truncate(time.Second)), nil
}

func (s *mountSet) usedShareSpace() (int8, derivation, error) {
	taken, err := s.snapshot()
	if err != nil {
		return 0, derivation{}, err
	}
	if taken.unread > 0 {
		return 0, derivation{}, fmt.Errorf("no share space read, [%d] of [%d] declared shares failed to answer a probe so the pool is unknown, failures [%s] [%w]",
			taken.unread, taken.shares, mountReasons(taken.mounts, true), errEnvironment)
	}
	if taken.locals == 0 {
		return 0, derivedInertf(scribe.ActionSample, "computed [  0] pct used share, host mounts no local share so the metric is inert and always ok"), nil
	}
	total := uint64(0)
	used := uint64(0)
	measured := 0
	for _, mount := range taken.mounts {
		if !mount.share || mount.remote || !mount.measured {
			continue
		}
		measured++
		total += mount.total
		used += mount.used
	}
	if total == 0 {
		return 0, derivation{}, fmt.Errorf("no local shares measured of [%d] mounted and [%d] declared, failures [%s] [%w]",
			taken.locals, taken.shares, mountReasons(taken.mounts, true), errEnvironment)
	}
	return percentValue(float64(used) / float64(total) * 100.0), derivedf(scribe.ActionSample, "computed [%3d] pct used share, used [%d] MiB of total [%d] MiB across [%d] measured of [%d] local shares",
		percentValue(float64(used)/float64(total)*100.0), used/bytesPerMiB, total/bytesPerMiB, measured, taken.locals), nil
}

func (s *mountSet) failedShares() (int8, derivation, error) {
	taken, err := s.snapshot()
	if err != nil {
		return 0, derivation{}, err
	}
	if taken.unread > 0 {
		return 0, derivation{}, fmt.Errorf("no share failures counted, [%d] of [%d] declared shares are mounted but failed to answer a probe, failures [%s] [%w]",
			taken.unread, taken.shares, mountReasons(taken.mounts, true), errEnvironment)
	}
	if taken.shares == 0 {
		return 0, derivedInertf(scribe.ActionSample, "computed [  0] pct failed share, fstab [%s] declares no share so the metric is inert and always ok",
			filepath.Join(s.root, mountFstabPath)), nil
	}
	return percentValue(float64(taken.failed) / float64(taken.shares) * 100.0), derivedf(scribe.ActionSample, "computed [%3d] pct failed share, failed [%d] of declared [%d] in [%s], failures [%s], ok only at [0] pct",
		percentValue(float64(taken.failed)/float64(taken.shares)*100.0), taken.failed, taken.shares, filepath.Join(s.root, mountFstabPath), mountReasons(taken.mounts, true)), nil
}

func (s *mountSet) collect() *mountSnapshot {
	collectStart := time.Now()
	taken := &mountSnapshot{taken: config.NowIncludingSuspend()}
	mounts, tableErr := s.parseMounts()
	taken.table = tableErr
	expected := s.parseFstab()
	for index := range mounts {
		measureStart := time.Now()
		total, used, err := s.measure(mounts[index].mountpoint, mounts[index].share)
		if err != nil {
			mounts[index].failed = true
			mounts[index].answered = errors.Is(err, errMountContent)
			mounts[index].reason = err.Error()
			scribe.Log(scribe.SourceProbeMounts, scribe.SubjectMetric(mountFeeding(mounts[index])), scribe.ActionSample).Debugf("examined", measureStart, "[%s] device [%s] fstype [%s] class [%s] not counted, failed with [%v]",
				mounts[index].mountpoint, mounts[index].device, mounts[index].fstype, mountClassLabel(mounts[index]), err)
			continue
		}
		mounts[index].total = total
		mounts[index].used = used
		mounts[index].measured = true
		scribe.Log(scribe.SourceProbeMounts, scribe.SubjectMetric(mountFeeding(mounts[index])), scribe.ActionSample).Debugf("examined", measureStart, "[%s] device [%s] fstype [%s] class [%s] used [%3d] of [%3d] MiB at [%3d] pct",
			mounts[index].mountpoint, mounts[index].device, mounts[index].fstype, mountClassLabel(mounts[index]), used/bytesPerMiB, total/bytesPerMiB, percentValue(mountShare(used, total)))
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
				if !mount.answered {
					taken.unread++
				}
			}
			continue
		}
		absentStart := time.Now()
		if _, _, err := s.measure(mountpoint, true); err != nil {
			taken.failed++
			scribe.Log(scribe.SourceProbeMounts, scribe.SubjectMetric(metric.MetricHostFailedShares), scribe.ActionSample).Debugf("examined", absentStart, "[%s] declared in fstab, absent from the mount table and counted failed with [%v]", mountpoint, err)
			continue
		}
		scribe.Log(scribe.SourceProbeMounts, scribe.SubjectMetric(metric.MetricHostFailedShares), scribe.ActionSample).Debugf("examined", absentStart, "[%s] declared in fstab, absent from the mount table but answered a probe so not counted failed", mountpoint)
	}
	taken.drives, taken.read = s.worn(mounts, collectStart)
	scribe.Log(scribe.SourceProbeMounts, scribe.SubjectNone, scribe.ActionSample).Debugf("surveyed", collectStart, "[%3d] mounts, system [%3d], shares local [%3d] declared [%3d] failed [%3d], drives [%3d]",
		len(mounts), len(mounts)-taken.locals-mountRemotes(mounts), taken.locals, taken.shares, taken.failed, len(taken.drives))
	return taken
}

func (s *mountSet) parseMounts() ([]mountUsage, error) {
	parseStart := time.Now()
	data, err := os.ReadFile(filepath.Join(s.root, mountTablePath))
	if err != nil {
		scribe.Log(scribe.SourceProbeMounts, scribe.SubjectNone, scribe.ActionSample).Warnf("noaccess", parseStart, "[%s] mount table with [%v], reporting no filesystems", filepath.Join(s.root, mountTablePath), err)
		return nil, err
	}
	devices := map[string]string{}
	dropped := map[string]int{}
	lines := 0
	var mounts []mountUsage
	for line := range strings.SplitSeq(string(data), "\n") {
		fields := strings.Fields(line)
		if len(fields) < 3 {
			continue
		}
		lines++
		device, fstype := fields[0], fields[2]
		mountpoint, hosted := s.hosted(mountUnescape(fields[1]))
		if !hosted {
			dropped[mountOutsideRoot]++
			continue
		}
		share, remote, keep := mountClass(fstype, mountpoint)
		if !keep {
			dropped[fstype]++
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
	scribe.Log(scribe.SourceProbeMounts, scribe.SubjectNone, scribe.ActionSample).Debugf("examined", parseStart, "[%3d] lines, kept [%3d] as [%s], dropped [%3d] as [%s]",
		lines, len(deduped), mountSummary(deduped), lines-len(deduped), mountDropped(dropped))
	return deduped, nil
}

func (s *mountSet) hosted(mountpoint string) (string, bool) {
	if s.root == "" || s.root == mountBareRoot {
		return mountpoint, true
	}
	if mountpoint == s.root {
		return "/", true
	}
	if strings.HasPrefix(mountpoint, s.root+"/") {
		return strings.TrimPrefix(mountpoint, s.root), true
	}
	return "", false
}

func (s *mountSet) parseFstab() []string {
	data, err := os.ReadFile(filepath.Join(s.root, mountFstabPath))
	if err != nil {
		return nil
	}
	var expected []string
	for line := range strings.SplitSeq(string(data), "\n") {
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
	s.mutex.Lock()
	outstanding := s.inflight[mountpoint]
	if !outstanding {
		s.inflight[mountpoint] = true
	}
	s.mutex.Unlock()
	if outstanding {
		return 0, 0, fmt.Errorf("mount [%s] not measured, a probe started on an earlier refresh has still not returned", mountpoint)
	}
	done := make(chan measurement, 1)
	go func() {
		defer func() {
			s.mutex.Lock()
			delete(s.inflight, mountpoint)
			s.mutex.Unlock()
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
		return 0, 0, fmt.Errorf("mount [%s] not measured, statfs did not answer within [%d] ms which is what a wedged mount looks like", mountpoint, mountDeadline.Milliseconds())
	}
}

func (s *mountSet) content(mountpoint string) error {
	entry, err := os.Stat(filepath.Join(s.root, mountpoint, mountContentDir))
	if err != nil {
		return fmt.Errorf("share [%s] holds no [%s] directory with [%v] [%w]", mountpoint, mountContentDir, err, errMountContent)
	}
	if !entry.IsDir() {
		return fmt.Errorf("share [%s] holds a [%s] that is not a directory [%w]", mountpoint, mountContentDir, errMountContent)
	}
	return nil
}

func mountFeeding(mount mountUsage) metric.ID {
	switch {
	case !mount.share:
		return metric.MetricHostUsedHomeSpace
	case mount.remote:
		return metric.MetricHostFailedShares
	default:
		return metric.MetricHostUsedShareSpace
	}
}

func mountShare(used, total uint64) float64 {
	if total == 0 {
		return 0
	}
	return float64(used) / float64(total) * 100.0
}

func mountStatfs(path string) (uint64, uint64, error) {
	var stat syscall.Statfs_t
	if err := syscall.Statfs(path, &stat); err != nil {
		return 0, 0, fmt.Errorf("statfs of [%s] failed with [%w]", path, err)
	}
	size := uint64(stat.Bsize)
	total := stat.Blocks * size
	used := (stat.Blocks - stat.Bfree) * size
	return total, used, nil
}

func mountReasons(mounts []mountUsage, share bool) string {
	reasons := make([]string, 0, len(mounts))
	for _, mount := range mounts {
		if mount.share != share || mount.measured {
			continue
		}
		reason := mount.reason
		if reason == "" {
			reason = fmt.Sprintf("mount [%s] reported [%d] total bytes", mount.mountpoint, mount.total)
		}
		reasons = append(reasons, reason)
		if len(reasons) == mountReasonsMax {
			break
		}
	}
	if len(reasons) == 0 {
		return "none"
	}
	return strings.Join(reasons, ", ")
}

func mountClassLabel(mount mountUsage) string {
	switch {
	case mount.share && mount.remote:
		return "share remote"
	case mount.share:
		return "share local"
	default:
		return "system"
	}
}

func mountSummary(mounts []mountUsage) string {
	summarised := make([]string, 0, len(mounts))
	for _, mount := range mounts {
		summarised = append(summarised, fmt.Sprintf("%s=%s/%s", mount.mountpoint, mount.fstype, strings.ReplaceAll(mountClassLabel(mount), " ", "-")))
	}
	if len(summarised) == 0 {
		return "none"
	}
	return strings.Join(summarised, " ")
}

func mountDropped(dropped map[string]int) string {
	if len(dropped) == 0 {
		return "none"
	}
	fstypes := make([]string, 0, len(dropped))
	for fstype := range dropped {
		fstypes = append(fstypes, fstype)
	}
	sort.Strings(fstypes)
	summarised := make([]string, 0, len(fstypes))
	for _, fstype := range fstypes {
		summarised = append(summarised, fmt.Sprintf("%s=%d", fstype, dropped[fstype]))
	}
	return strings.Join(summarised, " ")
}

func mountRemotes(mounts []mountUsage) int {
	remotes := 0
	for _, mount := range mounts {
		if mount.remote {
			remotes++
		}
	}
	return remotes
}

func mountBase(root string) string {
	baseStart := time.Now()
	for _, base := range []string{root, mountBareRoot} {
		if base == "" {
			continue
		}
		table := filepath.Join(base, mountTablePath)
		if _, err := os.Stat(table); err != nil {
			continue
		}
		if base != root {
			scribe.Log(scribe.SourceProbeMounts, scribe.SubjectNone, scribe.ActionDiscover).Infof("resolved", baseStart,
				"[%s] mount table read outside the container, configured root [%s] holds none", table, root)
		}
		return base
	}
	return root
}

func mountHolds(mountpoint, path string) bool {
	if mountpoint == "/" {
		return true
	}
	return path == mountpoint || strings.HasPrefix(path, mountpoint+"/")
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

const (
	mountTablePath   = "proc/mounts"
	mountFstabPath   = "etc/fstab"
	mountShareRoot   = "/share"
	mountHomeRoot    = "/var/lib/asystem"
	mountOutsideRoot = "outside-root"
	mountContentDir  = "media"
	mountBootRoot    = "/boot"
	mountNoAuto      = "noauto"
	mountDeadline    = 5 * time.Second
	mountRetry       = time.Minute
	mountReasonsMax  = 3
)

var (
	mountBareRoot    = "/"
	mountLocalTypes  = map[string]bool{"ext4": true, "xfs": true, "btrfs": true, "f2fs": true, "vfat": true}
	mountRemoteTypes = map[string]bool{"cifs": true, "nfs": true, "nfs4": true, "smb3": true}

	mountCache   = map[string]*mountSet{}
	mountCacheMu sync.RWMutex
)
