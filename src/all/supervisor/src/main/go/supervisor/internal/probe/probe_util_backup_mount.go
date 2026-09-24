package probe

import (
	"context"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"sync"
	"syscall"
	"time"

	"supervisor/internal/config"
	"supervisor/internal/scribe"
)

func fstabEntries() [][2]string {
	data, err := os.ReadFile(backupFstabPath)
	if err != nil {
		return nil
	}
	var entries [][2]string
	for line := range strings.SplitSeq(string(data), "\n") {
		trimmed := strings.TrimSpace(line)
		if trimmed == "" || strings.HasPrefix(trimmed, "#") {
			continue
		}
		fields := strings.Fields(trimmed)
		if len(fields) < 2 {
			continue
		}
		entries = append(entries, [2]string{fields[0], fields[1]})
	}
	return entries
}

func declaredSpec(target string) string {
	for _, entry := range fstabEntries() {
		if entry[1] == target {
			return entry[0]
		}
	}
	return ""
}

func declaredDevice(target string) (string, bool) {
	spec := declaredSpec(target)
	if spec == "" {
		return "", false
	}
	var device string
	switch {
	case strings.HasPrefix(spec, "PARTLABEL="):
		device, _ = filepath.EvalSymlinks(filepath.Join("/dev/disk/by-partlabel", strings.TrimPrefix(spec, "PARTLABEL=")))
	case strings.HasPrefix(spec, "PARTUUID="):
		device, _ = filepath.EvalSymlinks(filepath.Join("/dev/disk/by-partuuid", strings.TrimPrefix(spec, "PARTUUID=")))
	case strings.HasPrefix(spec, "UUID="):
		device, _ = filepath.EvalSymlinks(filepath.Join("/dev/disk/by-uuid", strings.TrimPrefix(spec, "UUID=")))
	case strings.HasPrefix(spec, "LABEL="):
		device, _ = filepath.EvalSymlinks(filepath.Join("/dev/disk/by-label", strings.TrimPrefix(spec, "LABEL=")))
	case strings.HasPrefix(spec, "//"):
		device = spec
	case strings.HasPrefix(spec, "/"):
		device, _ = filepath.EvalSymlinks(spec)
	default:
		device = spec
	}
	if device == "" {
		return "", false
	}
	if strings.HasPrefix(device, "/dev/") {
		if info, err := os.Stat(device); err != nil || info.Mode()&os.ModeDevice == 0 {
			return "", false
		}
	}
	return device, true
}

func sourcedDevice(ctx context.Context, target string) (string, bool) {
	out, code, abandoned := bounded(ctx, stageBoundedWait, "findmnt", "-M", target, "-n", "-o", "SOURCE")
	if abandoned || code != 0 {
		return "", false
	}
	lines := strings.Split(strings.TrimSpace(out), "\n")
	if len(lines) == 0 {
		return "", false
	}
	source := strings.TrimSpace(lines[len(lines)-1])
	if source == "" {
		return "", false
	}
	if strings.HasPrefix(source, "//") {
		return source, true
	}
	if strings.HasPrefix(source, "/") {
		bare, _, _ := strings.Cut(source, "[")
		resolved, err := filepath.EvalSymlinks(strings.TrimSpace(bare))
		if err != nil {
			return "", false
		}
		return resolved, true
	}
	return source, true
}

func verified(ctx context.Context, target string) bool {
	declared, ok := declaredDevice(target)
	if !ok {
		return false
	}
	sourced, ok := sourcedDevice(ctx, target)
	if !ok {
		return false
	}
	return declared == sourced
}

func alive(ctx context.Context, target string) bool {
	device, ok := declaredDevice(target)
	if !ok {
		return true
	}
	if !strings.HasPrefix(device, "/dev/") {
		return true
	}
	if _, code, abandoned := bounded(ctx, backupAliveWait, "dd", "if="+device, "of=/dev/null", "bs=4096", "count=1", "iflag=direct"); abandoned || code != 0 {
		return false
	}
	if !mountpointCheck(ctx, target) {
		return true
	}
	out, code, _ := stageExec(ctx, "findmnt", "-M", target, "-n", "-o", "OPTIONS")
	if code != 0 {
		return true
	}
	options := "," + strings.TrimSpace(out) + ","
	return !strings.Contains(options, ",ro,")
}

func diagnosed(ctx context.Context, target string) string {
	source, sourced := sourcedDevice(ctx, target)
	declared, wanted := declaredDevice(target)
	spec := declaredSpec(target)
	switch {
	case spec == "":
		return "is declared by no entry in [" + backupFstabPath + "]"
	case !wanted && !sourced:
		return "declares [" + spec + "] which has not enumerated, so its disk is powered down or unplugged"
	case !wanted:
		return "carries [" + source + "] while its declared [" + spec + "] has not enumerated"
	case !sourced:
		return "carries nothing rather than the declared [" + declared + "]"
	case source != declared:
		return "carries [" + source + "] rather than the declared [" + declared + "]"
	}
	if !alive(ctx, target) {
		return "carries [" + source + "] which is not answering reads, its device lost power or its link while mounted"
	}
	return "carries [" + source + "] and is answering normally"
}

func mountTarget(ctx context.Context, target string) error {
	if verified(ctx, target) {
		return nil
	}
	if _, ok := declaredDevice(target); !ok {
		return errMountUndeclared
	}
	scribe.Log(scribe.SourceBackup, scribe.SubjectNone, scribe.ActionStart).Infof("mounting", time.Now(), "[%s] mounting", target)
	_, code, abandoned := bounded(ctx, stageBoundedWait, "mount", target)
	if abandoned {
		return errMountAbandoned
	}
	if verified(ctx, target) {
		return nil
	}
	return fmt.Errorf("[%s] mount exited [%d] yet it does not carry the declared device", target, code)
}

func detachAll(ctx context.Context, homeRoot string) {
	for _, target := range backupTargets() {
		if !detachable(ctx, target, homeRoot) {
			continue
		}
		_, _, _ = bounded(ctx, stageBoundedWait, "sync", "-f", target)
		_, code, abandoned := bounded(ctx, stageBoundedWait, "umount", target)
		if abandoned {
			continue
		}
		if detachable(ctx, target, homeRoot) {
			if code == 0 {
				scribe.Log(scribe.SourceBackup, scribe.SubjectNone, scribe.ActionStop).Warnf("faulting", time.Now(),
					"[%s] unmount returned 0 yet it still reads as mounted, detaching forcibly and lazily", target)
			} else {
				scribe.Log(scribe.SourceBackup, scribe.SubjectNone, scribe.ActionStop).Warnf("faulting", time.Now(),
					"[%s] unmount failed, detaching forcibly and lazily", target)
			}
			_, _, _ = bounded(ctx, stageBoundedWait, "umount", "-f", "-l", target)
			if detachable(ctx, target, homeRoot) {
				scribe.Log(scribe.SourceBackup, scribe.SubjectNone, scribe.ActionStop).Warnf("faulting", time.Now(),
					"[%s] could not detach, it is still mounted and will need the disk powered back on", target)
			}
		}
	}
}

func detachable(ctx context.Context, target, homeRoot string) bool {
	if !mountpointCheck(ctx, target) {
		return false
	}
	if verified(ctx, target) {
		return true
	}
	targetDevice := deviceID(target)
	homeDevice := deviceID(homeRoot)
	return targetDevice != 0 && targetDevice != homeDevice
}

func mountpointCheck(ctx context.Context, target string) bool {
	_, code, abandoned := stageExec(ctx, "mountpoint", "-q", target)
	return !abandoned && code == 0
}

func deviceID(path string) uint64 {
	var stat syscall.Stat_t
	if err := syscall.Stat(path, &stat); err != nil {
		return 0
	}
	return uint64(stat.Dev)
}

func isLocalFilesystem(fstype string) bool {
	switch fstype {
	case "ext4", "xfs", "btrfs", "f2fs":
		return true
	default:
		return false
	}
}

func shareMountPattern(mountpoint string) bool {
	rest, ok := strings.CutPrefix(mountpoint, config.DirShare+"/")
	if !ok || rest == "" {
		return false
	}
	for _, digit := range rest {
		if digit < '0' || digit > '9' {
			return false
		}
	}
	return true
}

func backupTargets() []string {
	var targets []string
	for _, entry := range fstabEntries() {
		if entry[1] == config.DirBackup || strings.HasPrefix(entry[1], config.DirBackup+"/") {
			targets = append(targets, entry[1])
		}
	}
	return targets
}

func backupShares() []string {
	var mounts []string
	for _, entry := range fstabEntries() {
		if shareMountPattern(entry[1]) {
			mounts = append(mounts, entry[1])
		}
	}
	return mounts
}

func mountedLocalShares(ctx context.Context) []string {
	out, code, abandoned := bounded(ctx, stageBoundedWait, "findmnt", "-rn", "-o", "TARGET,SOURCE,FSTYPE")
	if abandoned || code != 0 {
		return nil
	}
	var mounts []string
	for line := range strings.SplitSeq(out, "\n") {
		fields := strings.Fields(line)
		if len(fields) < 3 {
			continue
		}
		mount, source, fstype := fields[0], fields[1], fields[2]
		if !shareMountPattern(mount) || !isLocalFilesystem(fstype) || !strings.HasPrefix(source, "/dev/") {
			continue
		}
		mounts = append(mounts, mount)
	}
	return mounts
}

func measureUsage(ctx context.Context, target string) (percent float64, usedMB, totalMB int, ok bool) {
	if !mountpointCheck(ctx, target) {
		return 0, 0, 0, false
	}
	uuid, found, wedged := btrfsUUID(ctx, target)
	if wedged {
		return 0, 0, 0, false
	}
	if found {
		total, used := btrfsSysfsUsage(uuid)
		if total > 0 {
			return float64(used) * 100 / float64(total), int(used / bytesPerMebibyte), int(total / bytesPerMebibyte), true
		}
	}
	out, code, abandoned := bounded(ctx, stageBoundedWait, "df", "--output=used,size", "-B1", target)
	if abandoned || code != 0 {
		return 0, 0, 0, false
	}
	lines := strings.Split(strings.TrimSpace(out), "\n")
	if len(lines) == 0 {
		return 0, 0, 0, false
	}
	fields := strings.Fields(lines[len(lines)-1])
	if len(fields) < 2 {
		return 0, 0, 0, false
	}
	used, _ := strconv.ParseInt(fields[0], 10, 64)
	total, _ := strconv.ParseInt(fields[1], 10, 64)
	if total <= 0 {
		return 0, 0, 0, false
	}
	return float64(used) * 100 / float64(total), int(used / bytesPerMebibyte), int(total / bytesPerMebibyte), true
}

func usedBytes(ctx context.Context, target string) int64 {
	out, code, abandoned := bounded(ctx, stageBoundedWait, "df", "--output=used", "-B1", target)
	if abandoned || code != 0 {
		return 0
	}
	lines := strings.Split(strings.TrimSpace(out), "\n")
	if len(lines) == 0 {
		return 0
	}
	fields := strings.Fields(lines[len(lines)-1])
	if len(fields) == 0 {
		return 0
	}
	value, _ := strconv.ParseInt(fields[0], 10, 64)
	return value
}

func btrfsUUID(ctx context.Context, target string) (uuid string, found, wedged bool) {
	if _, unidentified := btrfsUnidentified.Load(target); unidentified {
		return "", false, false
	}
	out, code, abandoned := bounded(ctx, stageBoundedWait, "btrfs", "filesystem", "show", target)
	if abandoned {
		scribe.Log(scribe.SourceBackup, scribe.SubjectNone, scribe.ActionCompute).Warnf("faulting", time.Now(),
			"[%s] btrfs filesystem show was abandoned, the filesystem is not answering", target)
		return "", false, true
	}
	if code != 0 {
		if _, loaded := btrfsUnidentified.LoadOrStore(target, true); !loaded {
			scribe.Log(scribe.SourceBackup, scribe.SubjectNone, scribe.ActionCompute).Infof("resolved", time.Now(),
				"[%s] btrfs cannot identify this path from in here, measuring it with df for the rest of this run", target)
		}
		return "", false, false
	}
	for line := range strings.SplitSeq(out, "\n") {
		if _, after, ok := strings.Cut(line, "uuid: "); ok {
			return strings.TrimSpace(after), true, false
		}
	}
	return "", false, false
}

func btrfsSysfsUsage(uuid string) (total, used int64) {
	devices, _ := filepath.Glob(filepath.Join(backupSysfsBtrfs, uuid, "devices", "*", "size"))
	for _, file := range devices {
		data, err := os.ReadFile(file)
		if err != nil {
			continue
		}
		if n, parseErr := strconv.ParseInt(strings.TrimSpace(string(data)), 10, 64); parseErr == nil {
			total += n * 512
		}
	}
	for _, allocation := range []string{"data", "metadata", "system"} {
		data, err := os.ReadFile(filepath.Join(backupSysfsBtrfs, uuid, "allocation", allocation, "bytes_used"))
		if err != nil {
			continue
		}
		if n, parseErr := strconv.ParseInt(strings.TrimSpace(string(data)), 10, 64); parseErr == nil {
			used += n
		}
	}
	return
}

var (
	errMountUndeclared = errors.New("[none] mount declared in fstab for this target, refusing to mount")
	errMountAbandoned  = errors.New("[abandoned] mount did not answer within its bound")

	btrfsUnidentified sync.Map

	backupFstabPath = "/etc/fstab"
)

const (
	backupAliveWait  = 10 * time.Second
	backupSysfsBtrfs = "/sys/fs/btrfs"
)
