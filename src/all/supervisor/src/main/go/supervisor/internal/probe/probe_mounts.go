package probe

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"regexp"
	"slices"
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

type driveWear struct {
	kernel     string
	model      string
	reason     string
	life       float64
	rated      bool
	errored    bool
	unreadable bool
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

type driveIdentity struct {
	kernel     string
	node       string
	transport  string
	kinds      []string
	hardware   string
	excluded   string
	rotational bool
	removable  bool
	model      string
	rating     float64
	baseline   int64
	rated      bool
	identified bool
	warned     bool
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
	mountCacheMutex.RLock()
	cached, found := mountCache[root]
	mountCacheMutex.RUnlock()
	if !found {
		mountCacheMutex.Lock()
		if cached, found = mountCache[root]; !found {
			cached = &mountSet{
				root:       mountBase(root),
				physicals:  map[string]string{},
				identities: map[string]*driveIdentity{},
				inflight:   map[string]bool{},
				statfs:     mountStatfs,
				smart:      mountSmart,
			}
			mountCache[root] = cached
		}
		mountCacheMutex.Unlock()
	}
	cached.mutex.Lock()
	cached.window = window
	cached.mutex.Unlock()
	cached.request(window)
	return cached
}

func resetMounts() {
	mountCacheMutex.Lock()
	defer mountCacheMutex.Unlock()
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
			scribe.Log(scribe.SourceProbeMounts, scribe.SubjectNone, scribe.ActionSample).Error("panicked", refreshStart, "[%v] refreshing [%s], keeping the previous snapshot", failure, filepath.Join(s.root, mountTablePath))
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
	return int8Percent(used), derived(scribe.ActionSample, "computed [%3d] pct used home, used [%d] MiB of total [%d] MiB on [%s] holding [%s] of [%d] filesystems, snapshot taken [%s] ago",
		int8Percent(used), home.used/bytesPerMiB, home.total/bytesPerMiB, home.mountpoint, mountHomeRoot, systems, config.SinceIncludingSuspend(taken.taken).Truncate(time.Second)), nil
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
		return 0, derivedInert(scribe.ActionSample, "computed [  0] pct used share, host mounts no local share so the metric is inert and always ok"), nil
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
	return int8Percent(float64(used) / float64(total) * 100.0), derived(scribe.ActionSample, "computed [%3d] pct used share, used [%d] MiB of total [%d] MiB across [%d] measured of [%d] local shares",
		int8Percent(float64(used)/float64(total)*100.0), used/bytesPerMiB, total/bytesPerMiB, measured, taken.locals), nil
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
		return 0, derivedInert(scribe.ActionSample, "computed [  0] pct failed share, fstab [%s] declares no share so the metric is inert and always ok",
			filepath.Join(s.root, mountFstabPath)), nil
	}
	return int8Percent(float64(taken.failed) / float64(taken.shares) * 100.0), derived(scribe.ActionSample, "computed [%3d] pct failed share, failed [%d] of declared [%d] in [%s], failures [%s], ok only at [0] pct",
		int8Percent(float64(taken.failed)/float64(taken.shares)*100.0), taken.failed, taken.shares, filepath.Join(s.root, mountFstabPath), mountReasons(taken.mounts, true)), nil
}

func (s *mountSet) lifeUsedDrives() (int8, derivation, error) {
	taken, err := s.snapshot()
	if err != nil {
		return 0, derivation{}, err
	}
	worst := 0.0
	worstAt := ""
	rated := 0
	errored := 0
	for _, drive := range taken.drives {
		if drive.errored {
			errored++
		}
		if !drive.rated {
			continue
		}
		rated++
		if drive.life > worst {
			worst = drive.life
			worstAt = drive.kernel + "=" + drive.model
		}
	}
	if unreadable := mountUnreadable(taken.drives); len(unreadable) > 0 {
		return 0, derivation{}, fmt.Errorf("no drive wear read, [%d] of [%d] drives unreadable by smartctl [%s] [%w]",
			len(unreadable), len(taken.drives), strings.Join(unreadable, ", "), errEnvironment)
	}
	if rated == 0 {
		return 0, derivedInert(scribe.ActionSample, "computed [  0] pct life used, none of [%d] drives are rated and readable so the metric is inert and always ok, unrated [%s]",
			len(taken.drives), mountDrives(taken.drives)), nil
	}
	return int8Percent(worst), derived(scribe.ActionSample, "computed [%3d] pct life used, most worn of [%d] rated drives [%s], errored [%d] drives, unreadable [%d] drives, ok pulse at [<=90] pct trend at [<=80] pct and no new errors",
		int8Percent(worst), rated, worstAt, errored, len(mountUnreadable(taken.drives))), nil
}

func (s *mountSet) failedDrives() (int8, derivation, error) {
	taken, err := s.snapshot()
	if err != nil {
		return 0, derivation{}, err
	}
	if unreadable := mountUnreadable(taken.drives); len(unreadable) > 0 {
		return 0, derivation{}, fmt.Errorf("no drive errors read, [%d] of [%d] drives unreadable [%s] [%w]",
			len(unreadable), len(taken.drives), strings.Join(unreadable, ", "), errEnvironment)
	}
	if len(taken.drives) == 0 {
		return 0, derivedInert(scribe.ActionSample, "computed [  0] pct failed drive, host reports no drive so the metric is inert and always ok"), nil
	}
	errored := 0
	var failed []string
	for _, drive := range taken.drives {
		if drive.errored {
			errored++
			failed = append(failed, drive.kernel+"="+drive.model)
		}
	}
	return int8Percent(float64(errored) / float64(len(taken.drives)) * 100.0), derived(scribe.ActionSample, "computed [%3d] pct failed drive, errored [%d] of [%d] drives, ok only at [0] pct, failed [%s]",
		int8Percent(float64(errored)/float64(len(taken.drives))*100.0), errored, len(taken.drives), strings.Join(failed, ", ")), nil
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
			scribe.Log(scribe.SourceProbeMounts, scribe.SubjectMetric(mountFeeding(mounts[index])), scribe.ActionSample).Debug("examined", measureStart, "[%s] device [%s] fstype [%s] class [%s] not counted, failed with [%v]",
				mounts[index].mountpoint, mounts[index].device, mounts[index].fstype, mountClassOf(mounts[index]), err)
			continue
		}
		mounts[index].total = total
		mounts[index].used = used
		mounts[index].measured = true
		scribe.Log(scribe.SourceProbeMounts, scribe.SubjectMetric(mountFeeding(mounts[index])), scribe.ActionSample).Debug("examined", measureStart, "[%s] device [%s] fstype [%s] class [%s] used [%d] of [%d] MiB at [%3d] pct",
			mounts[index].mountpoint, mounts[index].device, mounts[index].fstype, mountClassOf(mounts[index]), used/bytesPerMiB, total/bytesPerMiB, int8Percent(mountShare(used, total)))
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
			scribe.Log(scribe.SourceProbeMounts, scribe.SubjectMetric(metric.MetricHostFailedShares), scribe.ActionSample).Debug("examined", absentStart, "[%s] declared in fstab, absent from the mount table and counted failed with [%v]", mountpoint, err)
			continue
		}
		scribe.Log(scribe.SourceProbeMounts, scribe.SubjectMetric(metric.MetricHostFailedShares), scribe.ActionSample).Debug("examined", absentStart, "[%s] declared in fstab, absent from the mount table but answered a probe so not counted failed", mountpoint)
	}
	taken.drives, taken.read = s.worn(mounts, collectStart)
	scribe.Log(scribe.SourceProbeMounts, scribe.SubjectNone, scribe.ActionSample).Debug("surveyed", collectStart, "mounts [%3d], system [%d], shares local [%d] declared [%d] failed [%d], drives [%d]",
		len(mounts), len(mounts)-taken.locals-mountRemotes(mounts), taken.locals, taken.shares, taken.failed, len(taken.drives))
	return taken
}

func (s *mountSet) parseMounts() ([]mountUsage, error) {
	parseStart := time.Now()
	data, err := os.ReadFile(filepath.Join(s.root, mountTablePath))
	if err != nil {
		scribe.Log(scribe.SourceProbeMounts, scribe.SubjectNone, scribe.ActionSample).Warn("noaccess", parseStart, "mount table [%s] with [%v], reporting no filesystems", filepath.Join(s.root, mountTablePath), err)
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
	scribe.Log(scribe.SourceProbeMounts, scribe.SubjectNone, scribe.ActionSample).Debug("examined", parseStart, "lines [%3d], kept [%d] as [%s], dropped [%d] as [%s]",
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

func (s *mountSet) worn(mounts []mountUsage, collectStart time.Time) ([]driveWear, time.Time) {
	physicals := s.attached(mounts)
	s.mutex.Lock()
	previous, window := s.current, s.window
	s.mutex.Unlock()
	if previous != nil && config.SinceIncludingSuspend(previous.read) < window && slices.Equal(physicals, mountKernels(previous.drives)) {
		scribe.Log(scribe.SourceProbeMounts, scribe.SubjectMetric(metric.MetricHostLifeUsedDrives), scribe.ActionSample).Debug("retained", collectStart, "[%d] drive readings aged [%s] within [%s], not re-read", len(previous.drives), config.SinceIncludingSuspend(previous.read).Truncate(time.Second), window)
		return previous.drives, previous.read
	}
	drives := make([]driveWear, 0, len(physicals))
	for _, physical := range physicals {
		drives = append(drives, s.reading(physical))
	}
	return drives, config.NowIncludingSuspend()
}

func (s *mountSet) attached(mounts []mountUsage) []string {
	seen := map[string]bool{}
	var physicals []string
	for _, mount := range mounts {
		if mount.remote || !strings.HasPrefix(mount.device, "/dev/") {
			continue
		}
		physical := s.physical(mount.device)
		if physical == "" || seen[physical] {
			continue
		}
		seen[physical] = true
		physicals = append(physicals, physical)
	}
	sort.Strings(physicals)
	return physicals
}

func mountKernels(drives []driveWear) []string {
	kernels := make([]string, 0, len(drives))
	for _, drive := range drives {
		kernels = append(kernels, drive.kernel)
	}
	return kernels
}

func (s *mountSet) physical(device string) string {
	s.mutex.Lock()
	cached, found := s.physicals[device]
	s.mutex.Unlock()
	if found {
		return cached
	}
	resolved := s.resolve(strings.TrimPrefix(device, "/dev/"), 0)
	s.mutex.Lock()
	s.physicals[device] = resolved
	s.mutex.Unlock()
	return resolved
}

func (s *mountSet) resolve(kernel string, depth int) string {
	if kernel == "" || depth > mountResolveMax {
		return ""
	}
	if after, ok := strings.CutPrefix(kernel, "mapper/"); ok {
		return s.resolve(s.mapper(after), depth+1)
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

func mountUnreadable(drives []driveWear) []string {
	var unreadable []string
	for _, drive := range drives {
		if drive.unreadable {
			unreadable = append(unreadable, drive.kernel+"="+drive.reason)
		}
	}
	sort.Strings(unreadable)
	return unreadable
}

func (s *mountSet) namespace(physical string) string {
	if !driveController.MatchString(physical) {
		return physical
	}
	entries, err := os.ReadDir(filepath.Join(s.root, mountBlockPath))
	if err != nil {
		return physical + driveNamespaceFirst
	}
	names := make([]string, 0, len(entries))
	for _, entry := range entries {
		if driveNamespace.MatchString(entry.Name()) && strings.HasPrefix(entry.Name(), physical+"n") {
			names = append(names, entry.Name())
		}
	}
	if len(names) == 0 {
		return physical + driveNamespaceFirst
	}
	sort.Strings(names)
	return names[0]
}

func driveKinds(physical string) []string {
	if strings.HasPrefix(physical, drivePrefixNVME) {
		return []string{driveKindNVME}
	}
	return []string{driveKindSAT, driveKindRealtek, driveKindJMicron, driveKindASMedia, driveKindSCSI}
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
	if driveIgnoring(identity.hardware) {
		if !identity.warned {
			identity.warned = true
			scribe.Log(scribe.SourceProbeMounts, scribe.SubjectMetric(metric.MetricHostLifeUsedDrives), scribe.ActionSample).Info("excluded", readingStart, "[%s] at [%s] over [%s] as [%s] is declared not solid state, no wear rating applies so it is not counted in wear", physical, identity.node, identity.transport, identity.hardware)
		}
		scribe.Log(scribe.SourceProbeMounts, scribe.SubjectMetric(metric.MetricHostLifeUsedDrives), scribe.ActionSample).Debug("examined", readingStart, "[%s] not considered, declared not solid state, as [%s] over [%s]", physical, identity.hardware, identity.transport)
		return driveWear{kernel: physical}
	}
	report, err := s.smart(identity.node, identity.kinds)
	if err != nil {
		if !identity.warned {
			identity.warned = true
			scribe.Log(scribe.SourceProbeMounts, scribe.SubjectMetric(metric.MetricHostLifeUsedDrives), scribe.ActionSample).Warn("excluded", readingStart, "[%s] unreadable at [%s] over [%s] as [%s] with rotational [%v] removable [%v], not counted in wear, with [%v]", physical, identity.node, identity.transport, identity.hardware, identity.rotational, identity.removable, err)
		}
		scribe.Log(scribe.SourceProbeMounts, scribe.SubjectMetric(metric.MetricHostLifeUsedDrives), scribe.ActionSample).Debug("examined", readingStart, "[%s] not considered, unreadable by smartctl, as [%s] over [%s]", physical, identity.hardware, identity.transport)
		return driveWear{kernel: physical, model: identity.model, unreadable: true, reason: err.Error()}
	}
	s.identify(identity, report, readingStart)
	wear := driveWear{kernel: physical, model: identity.model, rated: identity.rated}
	if report.errors > identity.baseline {
		wear.errored = true
	}
	scribe.Log(scribe.SourceProbeMounts, scribe.SubjectMetric(metric.MetricHostFailedDrives), scribe.ActionSample).Debug("examined", readingStart, "[%s] errors [%d] baseline [%d] increased [%v], as [%s]", physical, report.errors, identity.baseline, wear.errored, identity.named())
	if !identity.rated {
		scribe.Log(scribe.SourceProbeMounts, scribe.SubjectMetric(metric.MetricHostLifeUsedDrives), scribe.ActionSample).Debug("examined", readingStart, "[%s] not considered, %s, as [%s]", physical, identity.excluded, identity.named())
		return wear
	}
	computed := driveComputed(report.written, identity.rating)
	wear.life = driveLife(computed, report.estimate, report.estimated)
	estimate := "none"
	if report.estimated {
		estimate = fmt.Sprintf("%.1f", report.estimate)
	}
	scribe.Log(scribe.SourceProbeMounts, scribe.SubjectMetric(metric.MetricHostLifeUsedDrives), scribe.ActionSample).Debug("examined", readingStart, "[%s] life [%3d] pct, computed [%.1f] drive [%s] pct, written [%.1f] of [%.0f] TB, as [%s]", physical, int8Percent(wear.life), computed, estimate, report.written/bytesPerTB, identity.rating, identity.named())
	return wear
}

func driveComputed(written, rating float64) float64 {
	if written <= 0 || rating <= 0 {
		return 0
	}
	return written / (rating * bytesPerTB) * 100.0
}

func driveLife(computed, estimate float64, estimated bool) float64 {
	if estimated && estimate > computed {
		return estimate
	}
	return computed
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
		identity.excluded = "reports no smart support"
		scribe.Log(scribe.SourceProbeMounts, scribe.SubjectMetric(metric.MetricHostLifeUsedDrives), scribe.ActionSample).Info("excluded", identifyStart, "[%s] at [%s] reports no smart support with [%s], not counted in wear", identity.kernel, identity.node, report.reason)
	case driveRatings[report.model] > 0:
		identity.rating = driveRatings[report.model]
		identity.rated = true
	default:
		identity.excluded = "model absent from the ratings"
		scribe.Log(scribe.SourceProbeMounts, scribe.SubjectMetric(metric.MetricHostLifeUsedDrives), scribe.ActionSample).Info("unlisted", identifyStart, "[%s] model [%s] absent from the ratings, not counted in wear", identity.kernel, report.model)
	}
}

func (s *mountSet) topology(physical string) (bool, bool, string, string) {
	rotational := s.flagged(physical, mountRotationalPath)
	removable := s.flagged(physical, mountRemovablePath)
	transport := driveTransportInternal
	if target, err := os.Readlink(filepath.Join(s.root, mountBlockPath, physical)); err == nil {
		for segment := range strings.SplitSeq(target, "/") {
			if strings.HasPrefix(segment, driveTransportUSB) {
				transport = driveTransportUSB
				break
			}
		}
	}
	hardware := driveHardware(s.described(physical, mountVendorPath), s.described(physical, mountModelPath))
	return rotational, removable, transport, hardware
}

func (s *mountSet) described(physical, path string) string {
	data, err := os.ReadFile(filepath.Join(s.root, mountBlockPath, physical, path))
	if err != nil {
		return ""
	}
	return strings.TrimRight(string(data), "\n")
}

func driveHardware(vendor, model string) string {
	spilled := len(vendor) == driveVendorWidth && !strings.HasSuffix(vendor, " ") && !strings.HasPrefix(model, " ")
	vendor = strings.TrimSpace(vendor)
	model = strings.TrimSpace(model)
	switch {
	case spilled:
		return vendor + model
	case vendor == "" || vendor == driveVendorPlaceholder:
		if model == "" {
			return mountUnknownHardware
		}
		return model
	case model == "":
		return vendor
	default:
		return vendor + " " + model
	}
}

func (s *mountSet) flagged(physical, path string) bool {
	data, err := os.ReadFile(filepath.Join(s.root, mountBlockPath, physical, path))
	if err != nil {
		return false
	}
	return strings.TrimSpace(string(data)) == mountFlagSet
}

func (i *driveIdentity) named() string {
	if i.model != "" {
		return i.model
	}
	return i.hardware
}

func (s *mountSet) identity(physical string) *driveIdentity {
	s.mutex.Lock()
	defer s.mutex.Unlock()
	if cached, found := s.identities[physical]; found {
		return cached
	}
	topologyStart := time.Now()
	identity := &driveIdentity{kernel: physical, node: filepath.Join(s.root, "dev", s.namespace(physical)), kinds: driveKinds(physical)}
	identity.rotational, identity.removable, identity.transport, identity.hardware = s.topology(physical)
	s.identities[physical] = identity
	scribe.Log(scribe.SourceProbeMounts, scribe.SubjectMetric(metric.MetricHostLifeUsedDrives), scribe.ActionDiscover).Debug("topology", topologyStart, "[%s] as [%s] over [%s], rotational [%v] removable [%v], node [%s], probing as [%s]",
		physical, identity.hardware, identity.transport, identity.rotational, identity.removable, identity.node, strings.Join(identity.kinds, ","))
	return identity
}

type smartReport struct {
	data      bool
	estimated bool
	estimate  float64
	model     string
	reason    string
	written   float64
	errors    int64
	supported bool
}

func mountSmart(node string, kinds []string) (smartReport, error) {
	tried := map[string][]string{}
	var reasons []string
	var barren *smartReport
	for _, kind := range kinds {
		report, err := mountSmartKind(node, kind)
		if err == nil {
			if report.data {
				return report, nil
			}
			if barren == nil {
				barren = &report
			}
			continue
		}
		failure := smartFailure{}
		if !errors.As(err, &failure) {
			failure = smartFailure{kind: kind, reason: err.Error()}
		}
		if _, seen := tried[failure.reason]; !seen {
			reasons = append(reasons, failure.reason)
		}
		tried[failure.reason] = append(tried[failure.reason], failure.kind)
	}
	if barren != nil {
		return *barren, nil
	}
	folded := make([]string, 0, len(reasons))
	for _, reason := range reasons {
		folded = append(folded, fmt.Sprintf("%s as [%s]", reason, strings.Join(tried[reason], "] or [")))
	}
	return smartReport{}, errors.New(strings.Join(folded, ", "))
}

type smartFailure struct {
	kind   string
	reason string
}

func (e smartFailure) Error() string {
	return fmt.Sprintf("%s as [%s]", e.reason, e.kind)
}

func mountSmartKind(node, kind string) (smartReport, error) {
	ctx, cancel := context.WithTimeout(context.Background(), mountDeadline)
	defer cancel()
	output, err := exec.CommandContext(ctx, mountSmartCommand, "--json", "-d", kind, "-a", node).Output()
	if len(output) == 0 {
		if err == nil {
			return smartReport{}, smartFailure{kind: kind, reason: "returned no output"}
		}
		return smartReport{}, smartFailure{kind: kind, reason: fmt.Sprintf("failed with [%v]", err)}
	}
	var decoded struct {
		ModelName string `json:"model_name"`
		Smartctl  struct {
			ExitStatus int `json:"exit_status"`
			Messages   []struct {
				String string `json:"string"`
			} `json:"messages"`
		} `json:"smartctl"`
		SmartSupport struct {
			Available bool `json:"available"`
		} `json:"smart_support"`
		NvmeLog struct {
			DataUnitsWritten float64 `json:"data_units_written"`
			ErrorLogEntries  int64   `json:"num_err_log_entries"`
			PercentageUsed   float64 `json:"percentage_used"`
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
		return smartReport{}, smartFailure{kind: kind, reason: fmt.Sprintf("returned output that is not parseable with [%v]", err)}
	}
	if decoded.Smartctl.ExitStatus&smartExitUnreadable != 0 {
		return smartReport{}, smartFailure{kind: kind, reason: fmt.Sprintf("could not open the node with status [%d] and [%s]", decoded.Smartctl.ExitStatus, smartMessages(decoded.Smartctl.Messages))}
	}
	report := smartReport{model: strings.TrimSpace(decoded.ModelName)}
	report.supported = decoded.SmartSupport.Available || report.model != ""
	if decoded.NvmeLog.DataUnitsWritten > 0 {
		report.data = true
		report.written = decoded.NvmeLog.DataUnitsWritten * bytesPerDataUnit
		report.errors = decoded.NvmeLog.ErrorLogEntries
		report.estimated = true
		report.estimate = decoded.NvmeLog.PercentageUsed
		return report, nil
	}
	report.data = len(decoded.AtaAttributes.Table) > 0
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
		if decoded.Smartctl.ExitStatus != 0 || len(decoded.Smartctl.Messages) > 0 {
			return smartReport{}, smartFailure{kind: kind, reason: fmt.Sprintf("read no data with status [%d] and [%s]", decoded.Smartctl.ExitStatus, smartMessages(decoded.Smartctl.Messages))}
		}
		report.supported = false
	}
	return report, nil
}

func smartMessages(messages []struct {
	String string `json:"string"`
}) string {
	texts := make([]string, 0, len(messages))
	for _, message := range messages {
		if text := strings.TrimSpace(message.String); text != "" {
			texts = append(texts, text)
		}
	}
	if len(texts) == 0 {
		return "no message"
	}
	return strings.Join(texts, ", ")
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
		return 0, 0, fmt.Errorf("statfs of [%s] failed with [%w]", path, err)
	}
	size := uint64(stat.Bsize)
	total := stat.Blocks * size
	used := (stat.Blocks - stat.Bfree) * size
	return total, used, nil
}

func mountDrives(drives []driveWear) string {
	if len(drives) == 0 {
		return "none"
	}
	named := make([]string, 0, len(drives))
	for _, drive := range drives {
		model := drive.model
		if model == "" {
			model = "unreadable"
		}
		named = append(named, drive.kernel+"="+model)
	}
	return strings.Join(named, " ")
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

func mountClassOf(mount mountUsage) string {
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
		summarised = append(summarised, fmt.Sprintf("%s=%s/%s", mount.mountpoint, mount.fstype, strings.ReplaceAll(mountClassOf(mount), " ", "-")))
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
			scribe.Log(scribe.SourceProbeMounts, scribe.SubjectNone, scribe.ActionDiscover).Info("resolved", baseStart,
				"mount table [%s] read outside the container, configured root [%s] holds none", table, root)
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
	mountRotationalPath      = "queue/rotational"
	mountRemovablePath       = "removable"
	mountVendorPath          = "device/vendor"
	mountModelPath           = "device/model"
	mountUnknownHardware     = "unknown hardware"
	driveVendorWidth         = 8
	driveVendorPlaceholder   = "ATA"
	mountFlagSet             = "1"
	driveTransportUSB        = "usb"
	driveTransportInternal   = "internal"
	mountShareRoot           = "/share"
	mountHomeRoot            = "/var/lib/asystem"
	mountOutsideRoot         = "outside-root"
	mountContentDir          = "media"
	mountBootRoot            = "/boot"
	mountNoAuto              = "noauto"
	mountSmartCommand        = "smartctl"
	smartExitUnreadable      = 0b11
	drivePrefixNVME          = "nvme"
	driveNamespaceFirst      = "n1"
	driveKindNVME            = "nvme"
	driveKindSAT             = "sat"
	driveKindRealtek         = "sntrealtek"
	driveKindJMicron         = "sntjmicron"
	driveKindASMedia         = "sntasmedia"
	driveKindSCSI            = "scsi"
	mountDeadline            = 5 * time.Second
	mountRetry               = time.Minute
	mountResolveMax          = 8
	mountReasonsMax          = 3
	bytesPerSector           = 512.0
	bytesPerDataUnit         = 512000.0
	bytesPerGiB              = 1073741824.0
	bytesPerTB               = 1000000000000.0
	driveAttributeErrors     = 1
	driveAttributeWritten    = 241
	driveAttributeWrittenAlt = 246
)

func driveIgnoring(hardware string) bool {
	lowered := strings.ToLower(hardware)
	for _, ignored := range driveIgnored {
		if strings.Contains(lowered, ignored) {
			return true
		}
	}
	return false
}

var driveIgnored = []string{"flash drive"}

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

var mountBareRoot = "/"

var mountLocalTypes = map[string]bool{"ext4": true, "xfs": true, "btrfs": true, "f2fs": true, "vfat": true}

var mountRemoteTypes = map[string]bool{"cifs": true, "nfs": true, "nfs4": true, "smb3": true}

var (
	mountCache      = map[string]*mountSet{}
	mountCacheMutex sync.RWMutex
)

var (
	driveController = regexp.MustCompile(`^nvme[0-9]+$`)
	driveNamespace  = regexp.MustCompile(`^nvme[0-9]+n[0-9]+$`)
)
