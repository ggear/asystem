package engine

import (
	"context"
	"fmt"
	"regexp"
	"slices"
	"sort"
	"storage/internal/config"
	"strings"
	"time"

	"github.com/shirou/gopsutil/v4/disk"
)

func Collect(loaded *config.Config, filters []string, requested string) ([]HostDoc, string, error) {
	mode := requested
	if mode == ModeAuto {
		mode = ModeRemote
		if partitions, err := disk.Partitions(false); err == nil {
			for _, partition := range partitions {
				if strings.HasPrefix(partition.Mountpoint, shareNamespace) {
					mode = ModeLocal
					break
				}
			}
		}
	}
	switch mode {
	case ModeLocal:
		mounts, err := collectLocal(loaded, filters)
		if err != nil {
			return nil, mode, err
		}
		return []HostDoc{{
			Index:   loaded.Index(),
			Label:   loaded.Label(),
			Name:    loaded.Name(),
			Version: loaded.Version(),
			State:   HostStateMeasured,
			Mounts:  mounts,
		}}, mode, nil
	case ModeRemote:
		hosts := collectRemote(loaded, filters)
		if len(hosts) == 0 {
			return nil, mode, fmt.Errorf("no hosts declared [%s]", loaded.Name())
		}
		return hosts, mode, nil
	default:
		return nil, mode, fmt.Errorf("invalid mode [%s]", requested)
	}
}

func Claims(filters []string, mountpoint, class string) bool {
	claimed, matched := classifyMount(mountpoint, filters)
	return matched && claimed == class
}

func collectLocal(loaded *config.Config, filters []string) ([]MountDoc, error) {
	partitions, err := disk.Partitions(false)
	if err != nil {
		return nil, fmt.Errorf("list partitions failed [%w]", err)
	}
	var readings []reading
	for _, partition := range partitions {
		mount := canonicalMount(partition.Mountpoint)
		class, ok := selected(loaded, filters, mount, partition.Fstype)
		if !ok {
			continue
		}
		usage, err := boundedUsage(partition.Mountpoint)
		if err != nil {
			readings = append(readings, reading{mount: mount, class: class, err: err})
			continue
		}
		readings = append(readings, reading{
			mount:    mount,
			class:    class,
			identity: identityKey(partition.Device),
			fstype:   partition.Fstype,
			device:   partition.Device,
			total:    usage.Total,
			avail:    usage.Free,
		})
	}
	return assemble(loaded, filters, readings, backupMounts(loaded, filters)), nil
}

func selected(loaded *config.Config, filters []string, mountpoint, fstype string) (class string, ok bool) {
	if pseudoFsTypes[fstype] {
		return "", false
	}
	class, matched := classifyMount(mountpoint, filters)
	if !matched || class == ClassBackup {
		return "", false
	}
	if class == ClassRoot {
		return class, !excludedRoot(mountpoint) && !networkFsTypes[fstype]
	}
	return class, !loaded.ServedElsewhere(mountpoint)
}

func assemble(loaded *config.Config, filters []string, readings []reading, backup []MountDoc) []MountDoc {
	var roots []rootMember
	var rootFaults, shares []MountDoc
	for _, measured := range readings {
		if measured.err != nil {
			fault := MountDoc{
				Mount: measured.mount,
				Label: loaded.MountLabel(measured.mount),
				Class: measured.class,
				State: MountStateTimedout,
				Error: fmt.Sprintf("statfs failed [%s] after [%s] [%v]", measured.mount, statfsTimeout, measured.err),
			}
			if measured.class == ClassRoot {
				rootFaults = append(rootFaults, fault)
			} else {
				shares = append(shares, fault)
			}
			continue
		}
		if measured.class == ClassRoot {
			roots = append(roots, rootMember{Mount: measured.mount, Identity: measured.identity, TotalBytes: measured.total, AvailBytes: measured.avail})
			continue
		}
		used := measured.total - min(measured.avail, measured.total)
		shares = append(shares, MountDoc{
			Mount:    measured.mount,
			Label:    loaded.MountLabel(measured.mount),
			Class:    measured.class,
			State:    MountStateMeasured,
			ServedBy: servedByLabel(loaded, measured.fstype, measured.device),
			Space:    &SpaceFigures{SizeBytes: measured.total, UsedBytes: used, FreeBytes: measured.total - used},
		})
	}
	mounted := map[string]bool{}
	for _, share := range shares {
		mounted[share.Mount] = true
	}
	for _, share := range loaded.Shares() {
		if mounted[share.Mount] || share.ServedBy != loaded.Name() {
			continue
		}
		if class, matched := classifyMount(share.Mount, filters); !matched || class != ClassShare {
			continue
		}
		shares = append(shares, MountDoc{
			Mount: share.Mount,
			Label: share.Label,
			Class: ClassShare,
			State: MountStateUnmounted,
			Error: fmt.Sprintf("declared and not mounted [%s]", share.Mount),
		})
	}
	sort.Slice(shares, func(i, j int) bool { return shares[i].Mount < shares[j].Mount })
	subtotal := func() []MountDoc {
		var size, used uint64
		measured := 0
		for _, share := range shares {
			if !share.Measured() {
				continue
			}
			measured++
			size += share.Space.SizeBytes
			used += share.Space.UsedBytes
		}
		if measured == 0 || !Claims(filters, shareMount, ClassShare) {
			return nil
		}
		return []MountDoc{{
			Mount: shareMount,
			Class: ClassShare,
			State: MountStateMeasured,
			Space: &SpaceFigures{SizeBytes: size, UsedBytes: used, FreeBytes: size - used},
		}}
	}
	var docs []MountDoc
	if len(roots) > 0 {
		figures, folded := foldRoot(roots)
		docs = append(docs, MountDoc{Mount: rootPattern, Class: ClassRoot, State: MountStateMeasured, Space: &figures, Folded: folded})
	}
	docs = append(docs, rootFaults...)
	docs = append(docs, shares...)
	docs = append(docs, subtotal()...)
	return append(docs, backup...)
}

func servedByLabel(loaded *config.Config, fstype, device string) string {
	if !networkFsTypes[fstype] {
		return ""
	}
	host := sourceHost(device)
	if host == "" {
		return ""
	}
	return loaded.HostLabel(host)
}

func sourceHost(device string) string {
	device = strings.TrimPrefix(device, "//")
	if at := strings.LastIndex(device, "@"); at != -1 {
		device = device[at+1:]
	}
	if slash := strings.Index(device, "/"); slash != -1 {
		device = device[:slash]
	}
	if colon := strings.Index(device, ":"); colon != -1 {
		device = device[:colon]
	}
	return device
}

func classifyMount(mountpoint string, filters []string) (class string, matched bool) {
	for _, pattern := range filters {
		if pattern == rootPattern || !matchGlob(pattern, mountpoint) {
			continue
		}
		if mountpoint == backupMount || strings.HasPrefix(mountpoint, backupMount+"/") {
			return ClassBackup, true
		}
		return ClassShare, true
	}
	if slices.Contains(filters, rootPattern) {
		return ClassRoot, true
	}
	return "", false
}

func foldRoot(members []rootMember) (SpaceFigures, *Folded) {
	if len(members) == 0 {
		return SpaceFigures{}, nil
	}
	type fold struct {
		identity string
		mounts   []string
		total    uint64
		avail    uint64
	}
	order := make([]string, 0, len(members))
	folds := map[string]*fold{}
	for _, member := range members {
		key := member.Identity
		if key == "" {
			key = "mount:" + member.Mount
		}
		existing, ok := folds[key]
		if !ok {
			existing = &fold{identity: member.Identity, total: member.TotalBytes, avail: member.AvailBytes}
			folds[key] = existing
			order = append(order, key)
		}
		existing.mounts = append(existing.mounts, member.Mount)
	}
	var sizeSum, usedSum uint64
	var biggest *fold
	for _, key := range order {
		current := folds[key]
		sizeSum += current.total
		usedSum += current.total - min(current.avail, current.total)
		if len(current.mounts) > 1 && (biggest == nil || len(current.mounts) > len(biggest.mounts)) {
			biggest = current
		}
	}
	figures := SpaceFigures{SizeBytes: sizeSum, UsedBytes: usedSum, FreeBytes: sizeSum - usedSum}
	if biggest == nil {
		return figures, nil
	}
	mounts := append([]string(nil), biggest.mounts...)
	sort.Strings(mounts)
	return figures, &Folded{Identity: biggest.identity, Mounts: mounts}
}

func matchGlob(pattern, candidate string) bool {
	escaped := strings.ReplaceAll(regexp.QuoteMeta(pattern), `\*`, ".*")
	expression, err := regexp.Compile("^" + escaped + "(/.*)?$")
	if err != nil {
		return false
	}
	return expression.MatchString(candidate)
}

func excludedRoot(mountpoint string) bool {
	for _, prefix := range excludedRootPrefixes {
		if mountpoint == prefix || strings.HasPrefix(mountpoint, prefix+"/") {
			return true
		}
	}
	return false
}

func boundedUsage(mountpoint string) (*disk.UsageStat, error) {
	ctx, cancel := context.WithTimeout(context.Background(), statfsTimeout)
	defer cancel()
	result := make(chan *disk.UsageStat, 1)
	failure := make(chan error, 1)
	go func() {
		usage, err := disk.Usage(mountpoint)
		if err != nil {
			failure <- err
			return
		}
		result <- usage
	}()
	select {
	case usage := <-result:
		return usage, nil
	case err := <-failure:
		return nil, err
	case <-ctx.Done():
		return nil, ctx.Err()
	}
}

// Document is the wire format storage space prints with --json and the format one host sends
// another in remote mode. It has three levels:
//
//	envelope  one document per invocation, whichever mode produced it
//	host      one block per host, local mode carries exactly one
//	mount     one measured or faulted mountpoint inside a host's block
//
//	"version":     "<text>",     ENVELOPE  This binary's own version
//	"mode":        "<mode>",     ENVELOPE  local or remote
//	"started_ts":  "<rfc3339>",  ENVELOPE
//	"duration_s":  <number>,     ENVELOPE
//	"hosts": [{
//	    "index":    <number>,    HOST      Absent on a host that owns no share
//	    "label":    "<text>",    HOST      The estate label, e.g. mad
//	    "name":     "<text>",    HOST      The machine-label hostname, e.g. macmini-mad
//	    "version":  "<text>",    HOST      That host's own version, for the skew check
//	    "state":    "<state>",   HOST      measured or unreachable
//	    "error":    "<text>",    HOST      Present exactly when state is not measured
//	    "mounts": [{
//	        "mount":   "<text>",   MOUNT   The mountpoint, or a synthetic subtotal/grand-total row
//	        "label":   "<text>",   MOUNT   The declared PARTLABEL, absent when the spec is a UUID
//	        "class":   "<class>",  MOUNT   root, share or backup
//	        "state":   "<state>",  MOUNT   measured, unmounted or timedout
//	        "error":   "<text>",   MOUNT   Present exactly when state is not measured
//	        "served_by": "<text>", MOUNT   The label of the host actually behind a network-mounted
//	                               share (e.g. a samba client's own mount); absent for a directly
//	                               attached mount, which is behind the host block's own label
//	        "space": {             MOUNT   Absent when state is not measured
//	            "size_bytes": <number>,
//	            "used_bytes": <number>,
//	            "free_bytes": <number>
//	        },
//	        "folded": {            MOUNT   Rides on the root row alone
//	            "identity": "<text>",
//	            "mounts": ["<text>", ...]
//	        },
//	        "backup": {            MOUNT   Rides on the backup row alone
//	            "run_id":      "<text>",
//	            "measured_ts": "<rfc3339>"
//	        }
//	    }]
//	}]
//
// Ownership: storage space writes it, engine_util_remote.go's fan-out reads another host's copy of
// it, and the repo's own storage on another host is the only other reader.
type Document struct {
	Version   string    `json:"version"`
	Mode      string    `json:"mode"`
	StartedTS string    `json:"started_ts"`
	DurationS int       `json:"duration_s"`
	Hosts     []HostDoc `json:"hosts"`
}

type HostDoc struct {
	Index   *int       `json:"index,omitempty"`
	Label   string     `json:"label"`
	Name    string     `json:"name"`
	Version string     `json:"version,omitempty"`
	State   string     `json:"state"`
	Error   string     `json:"error,omitempty"`
	Mounts  []MountDoc `json:"mounts,omitempty"`
}

type MountDoc struct {
	Mount    string        `json:"mount"`
	Label    string        `json:"label,omitempty"`
	Class    string        `json:"class"`
	State    string        `json:"state"`
	Error    string        `json:"error,omitempty"`
	ServedBy string        `json:"served_by,omitempty"`
	Space    *SpaceFigures `json:"space,omitempty"`
	Folded   *Folded       `json:"folded,omitempty"`
	Backup   *BackupInfo   `json:"backup,omitempty"`
}

func (m MountDoc) Measured() bool {
	return m.State == MountStateMeasured && m.Space != nil
}

type SpaceFigures struct {
	SizeBytes uint64 `json:"size_bytes"`
	UsedBytes uint64 `json:"used_bytes"`
	FreeBytes uint64 `json:"free_bytes"`
}

type Folded struct {
	Identity string   `json:"identity"`
	Mounts   []string `json:"mounts"`
}

type BackupInfo struct {
	RunID      string `json:"run_id"`
	MeasuredTS string `json:"measured_ts"`
}

type reading struct {
	mount    string
	class    string
	identity string
	fstype   string
	device   string
	total    uint64
	avail    uint64
	err      error
}

type rootMember struct {
	Mount      string
	Identity   string
	TotalBytes uint64
	AvailBytes uint64
}

const (
	ClassRoot   = "root"
	ClassShare  = "share"
	ClassBackup = "backup"

	MountStateMeasured  = "measured"
	MountStateUnmounted = "unmounted"
	MountStateTimedout  = "timedout"

	HostStateMeasured    = "measured"
	HostStateUnreachable = "unreachable"

	ModeAuto   = "auto"
	ModeLocal  = "local"
	ModeRemote = "remote"

	shareNamespace = "/share/"
	shareMount     = "/share"
	backupMount    = "/backup"
	rootPattern    = "/"

	statfsTimeout = 2 * time.Second
)

var DefaultFilters = []string{rootPattern, "/share*", backupMount}

var excludedRootPrefixes = []string{"/boot", "/efi", "/System/Volumes", "/Volumes"}

var networkFsTypes = map[string]bool{
	"smbfs": true, "cifs": true, "nfs": true, "nfs4": true,
	"afpfs": true, "webdav": true, "sshfs": true, "ftp": true,
}

var pseudoFsTypes = map[string]bool{
	"proc": true, "sysfs": true, "cgroup": true, "cgroup2": true,
	"devtmpfs": true, "overlay": true, "squashfs": true, "tmpfs": true,
	"devfs": true, "autofs": true, "devpts": true, "ramfs": true,
	"securityfs": true, "efivarfs": true, "configfs": true, "debugfs": true,
	"tracefs": true, "pstore": true, "bpf": true, "fusectl": true,
	"mqueue": true, "hugetlbfs": true, "nsfs": true, "binfmt_misc": true,
	"rpc_pipefs": true, "selinuxfs": true, "fuse.portal": true,
}
