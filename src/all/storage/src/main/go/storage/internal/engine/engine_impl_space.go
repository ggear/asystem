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

func Collect(cfg *config.Config, filters []string, requested string) ([]HostDoc, string, error) {
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
		return []HostDoc{{
			Index:   cfg.Index(),
			Label:   cfg.Label(),
			Name:    cfg.Name(),
			Version: cfg.Version(),
			State:   HostStateMeasured,
			Mounts:  collectLocal(cfg, filters),
		}}, mode, nil
	case ModeRemote:
		hosts := collectRemote(cfg, filters)
		if len(hosts) == 0 {
			return nil, mode, fmt.Errorf("no hosts declared [%s]", cfg.Name())
		}
		return hosts, mode, nil
	default:
		return nil, mode, fmt.Errorf("invalid mode [%s]", requested)
	}
}

func collectLocal(cfg *config.Config, filters []string) []MountDoc {
	partitions, err := disk.Partitions(false)
	if err != nil {
		return nil
	}
	var readings []reading
	for _, partition := range partitions {
		class, ok := selected(cfg, filters, partition.Mountpoint, partition.Fstype)
		if !ok {
			continue
		}
		usage, err := boundedUsage(partition.Mountpoint)
		if err != nil {
			readings = append(readings, reading{mount: partition.Mountpoint, class: class, err: err})
			continue
		}
		readings = append(readings, reading{
			mount:    partition.Mountpoint,
			class:    class,
			identity: identityKey(partition.Device),
			total:    usage.Total,
			avail:    usage.Free,
		})
	}
	return assemble(cfg, filters, readings, backupMounts(cfg, filters))
}

func selected(cfg *config.Config, filters []string, mountpoint, fstype string) (class string, ok bool) {
	if pseudoFsTypes[fstype] {
		return "", false
	}
	class, matched := ClassifyMount(mountpoint, filters)
	if !matched || class == ClassBackup {
		return "", false
	}
	if class == ClassRoot {
		return class, !excludedRoot(mountpoint) && !networkFsTypes[fstype]
	}
	return class, !cfg.ServedElsewhere(mountpoint)
}

func assemble(cfg *config.Config, filters []string, readings []reading, backup []MountDoc) []MountDoc {
	var roots []RootMember
	var rootFaults, shares []MountDoc
	for _, r := range readings {
		if r.err != nil {
			doc := MountDoc{
				Mount: r.mount,
				Label: cfg.MountLabel(r.mount),
				Class: r.class,
				State: MountStateTimedout,
				Error: fmt.Sprintf("statfs failed [%s] after [%s] [%v]", r.mount, statfsTimeout, r.err),
			}
			if r.class == ClassRoot {
				rootFaults = append(rootFaults, doc)
			} else {
				shares = append(shares, doc)
			}
			continue
		}
		if r.class == ClassRoot {
			roots = append(roots, RootMember{Mount: r.mount, Identity: r.identity, TotalBytes: r.total, AvailBytes: r.avail})
			continue
		}
		used := r.total - min(r.avail, r.total)
		shares = append(shares, MountDoc{
			Mount: r.mount,
			Label: cfg.MountLabel(r.mount),
			Class: r.class,
			State: MountStateMeasured,
			Space: &SpaceFigures{SizeBytes: r.total, UsedBytes: used, FreeBytes: r.total - used},
		})
	}
	mounted := map[string]bool{}
	for _, share := range shares {
		mounted[share.Mount] = true
	}
	for _, share := range cfg.Shares() {
		if mounted[share.Mount] || share.ServedBy != cfg.Name() {
			continue
		}
		if class, matched := ClassifyMount(share.Mount, filters); !matched || class != ClassShare {
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
	classes := 0
	for _, populated := range []bool{len(roots)+len(rootFaults) > 0, len(shares) > 0, len(backup) > 0} {
		if populated {
			classes++
		}
	}
	subtotal := func() []MountDoc {
		var size, used uint64
		measured := 0
		for _, share := range shares {
			if share.State != MountStateMeasured {
				continue
			}
			measured++
			size += share.Space.SizeBytes
			used += share.Space.UsedBytes
		}
		if Filtered(filters) || classes < 2 || measured == 0 {
			return nil
		}
		return []MountDoc{{
			Mount: "/share",
			Class: ClassShare,
			State: MountStateMeasured,
			Space: &SpaceFigures{SizeBytes: size, UsedBytes: used, FreeBytes: size - used},
		}}
	}
	var docs []MountDoc
	if len(roots) > 0 {
		figures, folded := FoldRoot(roots)
		docs = append(docs, MountDoc{Mount: "/", Class: ClassRoot, State: MountStateMeasured, Space: &figures, Folded: folded})
	}
	docs = append(docs, rootFaults...)
	docs = append(docs, shares...)
	docs = append(docs, subtotal()...)
	return append(docs, backup...)
}

func ClassifyMount(mountpoint string, filters []string) (class string, matched bool) {
	for _, pattern := range filters {
		if pattern == rootPattern || !matchGlob(pattern, mountpoint) {
			continue
		}
		if strings.HasSuffix(pattern, "/backup") {
			return ClassBackup, true
		}
		return ClassShare, true
	}
	if slices.Contains(filters, rootPattern) {
		return ClassRoot, true
	}
	return "", false
}

func Filtered(filters []string) bool {
	return !slices.Equal(filters, DefaultFilters)
}

func FoldRoot(members []RootMember) (SpaceFigures, *Folded) {
	if len(members) == 0 {
		return SpaceFigures{}, nil
	}
	type group struct {
		identity string
		mounts   []string
		total    uint64
		avail    uint64
		seeded   bool
	}
	order := make([]string, 0, len(members))
	groups := map[string]*group{}
	for _, m := range members {
		key := m.Identity
		if key == "" {
			key = "mount:" + m.Mount
		}
		g, ok := groups[key]
		if !ok {
			g = &group{identity: m.Identity}
			groups[key] = g
			order = append(order, key)
		}
		g.mounts = append(g.mounts, m.Mount)
		if !g.seeded {
			g.total = m.TotalBytes
			g.avail = m.AvailBytes
			g.seeded = true
		}
	}
	var sizeSum, usedSum uint64
	var biggest *group
	for _, key := range order {
		g := groups[key]
		used := g.total - min(g.avail, g.total)
		sizeSum += g.total
		usedSum += used
		if len(g.mounts) > 1 && (biggest == nil || len(g.mounts) > len(biggest.mounts)) {
			biggest = g
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
	re, err := regexp.Compile("^" + escaped + "$")
	if err != nil {
		return false
	}
	return re.MatchString(candidate)
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
	errs := make(chan error, 1)
	go func() {
		usage, err := disk.Usage(mountpoint)
		if err != nil {
			errs <- err
			return
		}
		result <- usage
	}()
	select {
	case usage := <-result:
		return usage, nil
	case err := <-errs:
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
	Mount  string        `json:"mount"`
	Label  string        `json:"label,omitempty"`
	Class  string        `json:"class"`
	State  string        `json:"state"`
	Error  string        `json:"error,omitempty"`
	Space  *SpaceFigures `json:"space,omitempty"`
	Folded *Folded       `json:"folded,omitempty"`
	Backup *BackupInfo   `json:"backup,omitempty"`
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
	total    uint64
	avail    uint64
	err      error
}

type RootMember struct {
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
	rootPattern    = "/"

	statfsTimeout = 2 * time.Second
)

var DefaultFilters = []string{"/", "/share/*", "/backup"}

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
