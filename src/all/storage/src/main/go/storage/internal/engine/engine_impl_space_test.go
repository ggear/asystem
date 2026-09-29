package engine

import (
	"bytes"
	"context"
	"encoding/json"
	"go/ast"
	"go/parser"
	"go/token"
	"os"
	"path/filepath"
	"reflect"
	"regexp"
	"sort"
	"storage/internal/config"
	"strconv"
	"strings"
	"testing"
)

func TestEngineImplSpace_FoldRoot(t *testing.T) {
	cases := []struct {
		name          string
		members       []RootMember
		wantSize      uint64
		wantUsed      uint64
		wantFolded    *Folded
		expectedError bool
	}{
		{
			name: "mad one pool under three subvolumes",
			members: []RootMember{
				{Mount: "/", Identity: "/dev/nvme0n1p6", TotalBytes: 424047280128, AvailBytes: 333116919808},
				{Mount: "/home", Identity: "/dev/nvme0n1p6", TotalBytes: 424047280128, AvailBytes: 333116919808},
				{Mount: "/var", Identity: "/dev/nvme0n1p6", TotalBytes: 424047280128, AvailBytes: 333116919808},
			},
			wantSize:   424047280128,
			wantUsed:   424047280128 - 333116919808,
			wantFolded: &Folded{Identity: "/dev/nvme0n1p6", Mounts: []string{"/", "/home", "/var"}},
		},
		{
			name: "may four distinct volumes",
			members: []RootMember{
				{Mount: "/", Identity: "/dev/mapper/vg-root", TotalBytes: 100, AvailBytes: 40},
				{Mount: "/home", Identity: "/dev/mapper/vg-home", TotalBytes: 200, AvailBytes: 50},
				{Mount: "/tmp", Identity: "/dev/mapper/vg-tmp", TotalBytes: 10, AvailBytes: 5},
				{Mount: "/var", Identity: "/dev/mapper/vg-var", TotalBytes: 30, AvailBytes: 10},
			},
			wantSize:   340,
			wantUsed:   (100 - 40) + (200 - 50) + (10 - 5) + (30 - 10),
			wantFolded: nil,
		},
		{
			name:       "jen single partition",
			members:    []RootMember{{Mount: "/", Identity: "LABEL=RASPIROOT", TotalBytes: 220000, AvailBytes: 110000}},
			wantSize:   220000,
			wantUsed:   110000,
			wantFolded: nil,
		},
		{
			name: "a bind mount shares its target's identity",
			members: []RootMember{
				{Mount: "/", Identity: "/dev/sda1", TotalBytes: 1000, AvailBytes: 600},
				{Mount: "/srv/bind", Identity: "/dev/sda1", TotalBytes: 1000, AvailBytes: 600},
			},
			wantSize:   1000,
			wantUsed:   400,
			wantFolded: &Folded{Identity: "/dev/sda1", Mounts: []string{"/", "/srv/bind"}},
		},
		{
			name: "an unidentifiable mount is counted once",
			members: []RootMember{
				{Mount: "/", Identity: "/dev/sda1", TotalBytes: 1000, AvailBytes: 600},
				{Mount: "/mnt/mystery", Identity: "", TotalBytes: 500, AvailBytes: 100},
			},
			wantSize:   1500,
			wantUsed:   400 + 400,
			wantFolded: nil,
		},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			figures, folded := FoldRoot(c.members)
			if figures.SizeBytes != c.wantSize {
				t.Errorf("size: got %v want %v", figures.SizeBytes, c.wantSize)
			}
			if figures.UsedBytes != c.wantUsed {
				t.Errorf("used: got %v want %v", figures.UsedBytes, c.wantUsed)
			}
			if figures.FreeBytes != figures.SizeBytes-figures.UsedBytes {
				t.Errorf("free does not equal size-used: got %v", figures.FreeBytes)
			}
			if !reflect.DeepEqual(folded, c.wantFolded) {
				t.Errorf("folded: got %+v want %+v", folded, c.wantFolded)
			}
		})
	}
}

func TestEngineImplSpace_ClassifyMount(t *testing.T) {
	cases := []struct {
		name          string
		mountpoint    string
		filters       []string
		wantClass     string
		wantMatched   bool
		expectedError bool
	}{
		{name: "default root", mountpoint: "/", filters: DefaultFilters, wantClass: ClassRoot, wantMatched: true},
		{name: "default share", mountpoint: "/share/10", filters: DefaultFilters, wantClass: ClassShare, wantMatched: true},
		{name: "default backup", mountpoint: "/backup", filters: DefaultFilters, wantClass: ClassBackup, wantMatched: true},
		{name: "shares only set excludes root", mountpoint: "/", filters: []string{"/share/*"}, wantMatched: false},
		{name: "shares only set matches a share", mountpoint: "/share/10", filters: []string{"/share/*"}, wantClass: ClassShare, wantMatched: true},
		{name: "a home path glob", mountpoint: "/Users/rue/Desktop/share/10", filters: []string{"/Users/rue/Desktop/share/*"}, wantClass: ClassShare, wantMatched: true},
		{name: "first match wins", mountpoint: "/share/10", filters: []string{"/share/10", "/share/*"}, wantClass: ClassShare, wantMatched: true},
		{name: "an unclaimed mount joins the root amalgam", mountpoint: "/home", filters: DefaultFilters, wantClass: ClassRoot, wantMatched: true},
		{name: "a filters set with no root pattern claims nothing else", mountpoint: "/home", filters: []string{"/share/*"}, wantMatched: false},
		{name: "a partial level does not prefix match", mountpoint: "/share/10", filters: []string{"/share/1"}, wantMatched: false},
		{name: "a whole level above claims the mounts below it", mountpoint: "/share/10", filters: []string{"/share"}, wantClass: ClassShare, wantMatched: true},
		{name: "a trailing star spanning levels", mountpoint: "/share/10", filters: []string{"/share*"}, wantClass: ClassShare, wantMatched: true},
		{name: "a share pattern still wins over the root amalgam", mountpoint: "/share/10", filters: DefaultFilters, wantClass: ClassShare, wantMatched: true},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			class, matched := ClassifyMount(c.mountpoint, c.filters)
			if matched != c.wantMatched {
				t.Fatalf("matched: got %v want %v", matched, c.wantMatched)
			}
			if matched && class != c.wantClass {
				t.Errorf("class: got %v want %v", class, c.wantClass)
			}
		})
	}
}

func TestEngineImplSpace_Selected(t *testing.T) {
	cases := []struct {
		name          string
		mountpoint    string
		fstype        string
		filters       []string
		wantClass     string
		wantSelected  bool
		expectedError bool
	}{
		{name: "the root filesystem", mountpoint: "/", fstype: "btrfs", filters: DefaultFilters, wantClass: ClassRoot, wantSelected: true},
		{name: "a subvolume of the root pool", mountpoint: "/home", fstype: "btrfs", filters: DefaultFilters, wantClass: ClassRoot, wantSelected: true},
		{name: "a pseudo filesystem", mountpoint: "/proc", fstype: "proc", filters: DefaultFilters},
		{name: "a boot partition", mountpoint: "/boot", fstype: "ext4", filters: DefaultFilters},
		{name: "an efi partition below boot", mountpoint: "/boot/efi", fstype: "vfat", filters: DefaultFilters},
		{name: "a share this host serves", mountpoint: "/share/10", fstype: "ext4", filters: DefaultFilters, wantClass: ClassShare, wantSelected: true},
		{name: "a share another host serves", mountpoint: "/share/20", fstype: "cifs", filters: DefaultFilters},
		{name: "the backup mount is never measured live", mountpoint: "/backup", fstype: "btrfs", filters: DefaultFilters},
		{name: "an unclaimed local mount joins the root amalgam", mountpoint: "/mnt/spare", fstype: "ext4", filters: DefaultFilters, wantClass: ClassRoot, wantSelected: true},
		{name: "an unclaimed network mount is not local storage", mountpoint: "/Users/rue/Desktop/share/20", fstype: "smbfs", filters: DefaultFilters},
		{name: "a network mount a share pattern claims is still a share", mountpoint: "/share/10", fstype: "cifs", filters: DefaultFilters, wantClass: ClassShare, wantSelected: true},
		{name: "an unclaimed mount with no root pattern in the set", mountpoint: "/mnt/spare", fstype: "ext4", filters: []string{"/share/*"}},
		{name: "an undeclared mount outside the share namespace", mountpoint: "/Users/rue/Desktop/share/20", fstype: "smbfs", filters: []string{"/Users/rue/Desktop/share/*"}, wantClass: ClassShare, wantSelected: true},
	}
	cfg := fixtureConfig(t)
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			class, ok := selected(cfg, c.filters, c.mountpoint, c.fstype)
			if ok != c.wantSelected {
				t.Fatalf("selected: got %v want %v", ok, c.wantSelected)
			}
			if ok && class != c.wantClass {
				t.Errorf("class: got %v want %v", class, c.wantClass)
			}
		})
	}
}

func TestEngineImplSpace_ServedByLabel(t *testing.T) {
	cases := []struct {
		name       string
		fstype     string
		device     string
		wantServed string
	}{
		{name: "a macOS smbfs mount names its serving host", fstype: "smbfs", device: "//GUEST:@macmini-mad/share-10", wantServed: "mad"},
		{name: "a linux cifs mount names its serving host", fstype: "cifs", device: "//macmini-max/share-20", wantServed: "max"},
		{name: "an nfs mount names its serving host", fstype: "nfs", device: "macmini-may:/share/30", wantServed: "may"},
		{name: "a served host not in schema falls back to the dash suffix", fstype: "smbfs", device: "//GUEST:@raspbpi-jen/share-50", wantServed: "jen"},
		{name: "a directly attached share carries no served-by host", fstype: "ext4", device: "/dev/sda1"},
		{name: "a directly attached btrfs root carries no served-by host", fstype: "btrfs", device: "/dev/nvme0n1p6"},
	}
	cfg := fixtureConfig(t)
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			if got := servedByLabel(cfg, c.fstype, c.device); got != c.wantServed {
				t.Errorf("servedByLabel: got %q want %q", got, c.wantServed)
			}
		})
	}
}

func TestEngineImplSpace_Assemble(t *testing.T) {
	pool := func(mount string) reading {
		return reading{mount: mount, class: ClassRoot, identity: "/dev/nvme0n1p6", total: 1000, avail: 600}
	}
	share := func(mount string, total, avail uint64) reading {
		return reading{mount: mount, class: ClassShare, identity: "/dev/sda1", total: total, avail: avail}
	}
	space := func(size, used uint64) *SpaceFigures {
		return &SpaceFigures{SizeBytes: size, UsedBytes: used, FreeBytes: size - used}
	}
	backupDoc := MountDoc{Mount: "/backup", Label: "backup_06", Class: ClassBackup, State: MountStateMeasured, Space: space(2000, 500)}
	rootDoc := MountDoc{Mount: "/", Class: ClassRoot, State: MountStateMeasured, Space: space(1000, 400),
		Folded: &Folded{Identity: "/dev/nvme0n1p6", Mounts: []string{"/", "/home", "/var"}}}
	missing := MountDoc{Mount: "/share/11", Label: "share_09", Class: ClassShare, State: MountStateUnmounted,
		Error: "declared and not mounted [/share/11]"}
	cases := []struct {
		name          string
		filters       []string
		readings      []reading
		backup        []MountDoc
		want          []MountDoc
		expectedError bool
	}{
		{
			name:     "a server host, its own shares only, subtotal between the shares and backup",
			filters:  DefaultFilters,
			readings: []reading{pool("/"), pool("/home"), pool("/var"), share("/share/12", 400, 100), share("/share/10", 400, 300)},
			backup:   []MountDoc{backupDoc},
			want: []MountDoc{
				rootDoc,
				{Mount: "/share/10", Label: "share_08", Class: ClassShare, State: MountStateMeasured, Space: space(400, 100)},
				missing,
				{Mount: "/share/12", Label: "share_10", Class: ClassShare, State: MountStateMeasured, Space: space(400, 300)},
				{Mount: "/share", Class: ClassShare, State: MountStateMeasured, Space: space(800, 400)},
				backupDoc,
			},
		},
		{
			name:     "a glob below the share level carries no subtotal",
			filters:  []string{"/share/*"},
			readings: []reading{share("/share/10", 400, 300), share("/share/11", 400, 100), share("/share/12", 400, 100)},
			want: []MountDoc{
				{Mount: "/share/10", Label: "share_08", Class: ClassShare, State: MountStateMeasured, Space: space(400, 100)},
				{Mount: "/share/11", Label: "share_09", Class: ClassShare, State: MountStateMeasured, Space: space(400, 300)},
				{Mount: "/share/12", Label: "share_10", Class: ClassShare, State: MountStateMeasured, Space: space(400, 300)},
			},
		},
		{
			name:     "a filter naming one share carries no subtotal",
			filters:  []string{"/", "/share/10"},
			readings: []reading{pool("/"), share("/share/10", 400, 300)},
			want: []MountDoc{
				{Mount: "/", Class: ClassRoot, State: MountStateMeasured, Space: space(1000, 400)},
				{Mount: "/share/10", Label: "share_08", Class: ClassShare, State: MountStateMeasured, Space: space(400, 100)},
			},
		},
		{
			name:     "a filter naming the share level carries the subtotal alone",
			filters:  []string{"/share"},
			readings: []reading{share("/share/10", 400, 300), share("/share/11", 400, 100), share("/share/12", 400, 100)},
			want: []MountDoc{
				{Mount: "/share/10", Label: "share_08", Class: ClassShare, State: MountStateMeasured, Space: space(400, 100)},
				{Mount: "/share/11", Label: "share_09", Class: ClassShare, State: MountStateMeasured, Space: space(400, 300)},
				{Mount: "/share/12", Label: "share_10", Class: ClassShare, State: MountStateMeasured, Space: space(400, 300)},
				{Mount: "/share", Class: ClassShare, State: MountStateMeasured, Space: space(1200, 700)},
			},
		},
		{
			name:     "a faulted share keeps its place in the order and leaves the subtotal",
			filters:  DefaultFilters,
			readings: []reading{pool("/"), {mount: "/share/10", class: ClassShare, err: context.DeadlineExceeded}, share("/share/12", 400, 100)},
			backup:   []MountDoc{backupDoc},
			want: []MountDoc{
				{Mount: "/", Class: ClassRoot, State: MountStateMeasured, Space: space(1000, 400)},
				{Mount: "/share/10", Label: "share_08", Class: ClassShare, State: MountStateTimedout,
					Error: "statfs failed [/share/10] after [2s] [context deadline exceeded]"},
				missing,
				{Mount: "/share/12", Label: "share_10", Class: ClassShare, State: MountStateMeasured, Space: space(400, 300)},
				{Mount: "/share", Class: ClassShare, State: MountStateMeasured, Space: space(400, 300)},
				backupDoc,
			},
		},
		{
			name:     "a faulted root member sits directly below the root row",
			filters:  []string{"/"},
			readings: []reading{pool("/"), {mount: "/var", class: ClassRoot, err: context.DeadlineExceeded}},
			want: []MountDoc{
				{Mount: "/", Class: ClassRoot, State: MountStateMeasured, Space: space(1000, 400)},
				{Mount: "/var", Class: ClassRoot, State: MountStateTimedout,
					Error: "statfs failed [/var] after [2s] [context deadline exceeded]"},
			},
		},
	}
	cfg := fixtureConfig(t)
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			got := assemble(cfg, c.filters, c.readings, c.backup)
			if len(got) != len(c.want) {
				t.Fatalf("rows: got %d want %d, got %+v", len(got), len(c.want), got)
			}
			for i := range got {
				if !reflect.DeepEqual(got[i], c.want[i]) {
					t.Errorf("row %d: got %+v want %+v", i, got[i], c.want[i])
				}
			}
		})
	}
}

func fixtureConfig(t *testing.T) *config.Config {
	t.Helper()
	path := filepath.Join(t.TempDir(), "config.json")
	document := `{"asystem": {"version": "10.200.1725", "host": "macmini-mad", "schema": [{
	  "index": 1, "host": "macmini-mad", "label": "mad", "form_factor": "server",
	  "shares": [
	    {"mount": "/share/10", "label": "share_08", "served_by": "macmini-mad", "smb": "share-10"},
	    {"mount": "/share/11", "label": "share_09", "served_by": "macmini-mad", "smb": "share-11"},
	    {"mount": "/share/12", "label": "share_10", "served_by": "macmini-mad", "smb": "share-12"},
	    {"mount": "/share/20", "label": "share_06", "served_by": "macmini-max", "smb": "share-20"}],
	  "backup": {"mount": "/backup", "label": "backup_06"}}]}}`
	if err := os.WriteFile(path, []byte(document), 0o644); err != nil {
		t.Fatal(err)
	}
	t.Setenv("STORAGE_HOST", "macmini-mad")
	t.Setenv("SERVICE_VERSION_ABSOLUTE", "")
	return config.Load(path)
}

func TestEngineImplSpace_Amalgam(t *testing.T) {
	cases := []struct {
		name          string
		host          string
		table         string
		wantMounts    []string
		wantRoot      *SpaceFigures
		wantFolded    *Folded
		wantShare     *SpaceFigures
		expectedError bool
	}{
		{
			name:       "mad, one btrfs pool under three subvolumes",
			host:       "macmini-mad",
			table:      mountTableMad,
			wantMounts: []string{"/", "/share/10", "/share/11", "/share/12", "/share"},
			wantRoot:   &SpaceFigures{SizeBytes: 424047280128, UsedBytes: 93359001600, FreeBytes: 330688278528},
			wantFolded: &Folded{Identity: "/dev/nvme0n1p6", Mounts: []string{"/", "/home", "/var"}},
			wantShare:  &SpaceFigures{SizeBytes: 12087324065792, UsedBytes: 8282819182592, FreeBytes: 3804504883200},
		},
		{
			name:       "max, four LVM volumes summed",
			host:       "macmini-max",
			table:      mountTableMax,
			wantMounts: []string{"/", "/share/20", "/share/21", "/share"},
			wantRoot:   &SpaceFigures{SizeBytes: 411702140928, UsedBytes: 42772398080, FreeBytes: 368929742848},
			wantFolded: nil,
			wantShare:  &SpaceFigures{SizeBytes: 2015043792896, UsedBytes: 1067499720704, FreeBytes: 947544072192},
		},
		{
			name:       "may, four LVM volumes summed",
			host:       "macmini-may",
			table:      mountTableMay,
			wantMounts: []string{"/", "/share/30", "/share/31", "/share/32", "/share"},
			wantRoot:   &SpaceFigures{SizeBytes: 513225965568, UsedBytes: 51464810496, FreeBytes: 461761155072},
			wantFolded: nil,
			wantShare:  &SpaceFigures{SizeBytes: 7888025489408, UsedBytes: 4627851169792, FreeBytes: 3260174319616},
		},
		{
			name:       "meg, four LVM volumes summed",
			host:       "macmini-meg",
			table:      mountTableMeg,
			wantMounts: []string{"/", "/share/40", "/share/41", "/share/42", "/share"},
			wantRoot:   &SpaceFigures{SizeBytes: 513225965568, UsedBytes: 86157701120, FreeBytes: 427068264448},
			wantFolded: nil,
			wantShare:  &SpaceFigures{SizeBytes: 5817198292992, UsedBytes: 4456868724736, FreeBytes: 1360329568256},
		},
		{
			name:       "jen, a single ext4 partition and no share of its own",
			host:       "raspbpi-jen",
			table:      mountTableJen,
			wantMounts: []string{"/"},
			wantRoot:   &SpaceFigures{SizeBytes: 125644963840, UsedBytes: 16787578880, FreeBytes: 108857384960},
			wantFolded: nil,
			wantShare:  nil,
		},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			t.Setenv("STORAGE_HOST", c.host)
			t.Setenv("SERVICE_VERSION_ABSOLUTE", "")
			cfg := config.Load(filepath.Join("..", "..", "..", "..", "resources", "image", "config.json"))
			var readings []reading
			for line := range strings.SplitSeq(strings.TrimSpace(c.table), "\n") {
				fields := strings.Fields(line)
				if len(fields) != 5 {
					t.Fatalf("malformed fixture line [%s]", line)
				}
				class, ok := selected(cfg, DefaultFilters, fields[0], fields[1])
				if !ok {
					continue
				}
				size, err := strconv.ParseUint(fields[3], 10, 64)
				if err != nil {
					t.Fatal(err)
				}
				avail, err := strconv.ParseUint(fields[4], 10, 64)
				if err != nil {
					t.Fatal(err)
				}
				readings = append(readings, reading{mount: fields[0], class: class, identity: fields[2], total: size, avail: avail})
			}
			docs := assemble(cfg, DefaultFilters, readings, nil)
			var mounts []string
			var share *SpaceFigures
			for _, doc := range docs {
				mounts = append(mounts, doc.Mount)
				if doc.Mount == "/share" {
					share = doc.Space
				}
			}
			if !reflect.DeepEqual(mounts, c.wantMounts) {
				t.Fatalf("mounts: got %v want %v", mounts, c.wantMounts)
			}
			if !reflect.DeepEqual(docs[0].Space, c.wantRoot) {
				t.Errorf("root space: got %+v want %+v", docs[0].Space, c.wantRoot)
			}
			if !reflect.DeepEqual(docs[0].Folded, c.wantFolded) {
				t.Errorf("root folded: got %+v want %+v", docs[0].Folded, c.wantFolded)
			}
			if !reflect.DeepEqual(share, c.wantShare) {
				t.Errorf("share subtotal: got %+v want %+v", share, c.wantShare)
			}
		})
	}
}

func TestEngineImplSpace_DocumentCommentMatchesTags(t *testing.T) {
	commented := commentedFieldNames(t)
	if len(commented) == 0 {
		t.Fatal("parsed no field names out of the Document doc comment, the parse itself is broken")
	}
	tagged := taggedFieldNames(
		Document{}, HostDoc{}, MountDoc{}, SpaceFigures{}, Folded{}, BackupInfo{},
	)
	if len(tagged) == 0 {
		t.Fatal("reflected no json tags, the reflection itself is broken")
	}
	assertSameSet(t, commented, tagged)
}

func TestEngineImplSpace_DocumentRoundTrip(t *testing.T) {
	index := 1
	want := Document{
		Version:   "10.200.1725",
		Mode:      "remote",
		StartedTS: "2026-09-25T02:14:07+08:00",
		DurationS: 3,
		Hosts: []HostDoc{
			{
				Index:   &index,
				Label:   "mad",
				Name:    "macmini-mad",
				Version: "10.200.1725",
				State:   HostStateMeasured,
				Mounts: []MountDoc{
					{
						Mount: "/",
						Class: ClassRoot,
						State: MountStateMeasured,
						Space: &SpaceFigures{
							SizeBytes: 424047280128,
							UsedBytes: 90930360320,
							FreeBytes: 333116919808,
						},
						Folded: &Folded{
							Identity: "/dev/nvme0n1p6",
							Mounts:   []string{"/", "/home", "/var"},
						},
					},
					{
						Mount: "/share/11",
						Label: "share_09",
						Class: ClassShare,
						State: MountStateUnmounted,
						Error: "declared and not mounted [/share/11]",
					},
					{
						Mount: "/backup",
						Label: "backup_06",
						Class: ClassBackup,
						State: MountStateMeasured,
						Space: &SpaceFigures{
							SizeBytes: 26388279066624,
							UsedBytes: 9895604649984,
							FreeBytes: 16492674416640,
						},
						Backup: &BackupInfo{
							RunID:      "2026-09-25_01-00-00",
							MeasuredTS: "2026-09-25T02:14:07+08:00",
						},
					},
				},
			},
			{
				Label: "max",
				Name:  "macmini-max",
				State: HostStateUnreachable,
				Error: "ssh dial failed [macmini-max]",
			},
		},
	}
	encoded, err := json.Marshal(want)
	if err != nil {
		t.Fatal(err)
	}
	var got Document
	if err := json.Unmarshal(encoded, &got); err != nil {
		t.Fatal(err)
	}
	if !reflect.DeepEqual(got, want) {
		t.Errorf("round trip: got %+v want %+v", got, want)
	}
	if index := bytes.Index(encoded, []byte(`"index"`)); index < 0 || index > bytes.Index(encoded, []byte(`"state"`)) {
		t.Errorf("identity fields must encode before state, got %s", encoded)
	}
}

func TestEngineImplSpace_DocumentDecodesUnknownAndMissingFields(t *testing.T) {
	var got Document
	if err := json.Unmarshal([]byte(`{"version":"10.200.1725","surprise":true,"hosts":[{"label":"mad","state":"measured","mounts":[{"mount":"/","class":"root","state":"measured","surprise":{"nested":1}}]}]}`), &got); err != nil {
		t.Fatal(err)
	}
	if got.Mode != "" || got.DurationS != 0 {
		t.Errorf("absent fields: got mode %q duration %d want the zero values", got.Mode, got.DurationS)
	}
	if len(got.Hosts) != 1 || got.Hosts[0].Index != nil {
		t.Fatalf("hosts: got %+v want one host with no index", got.Hosts)
	}
	if len(got.Hosts[0].Mounts) != 1 || got.Hosts[0].Mounts[0].Space != nil {
		t.Errorf("mounts: got %+v want one mount with no space", got.Hosts[0].Mounts)
	}
}

func commentedFieldNames(t *testing.T) map[string]bool {
	t.Helper()
	fileSet := token.NewFileSet()
	file, err := parser.ParseFile(fileSet, "engine_impl_space.go", nil, parser.ParseComments)
	if err != nil {
		t.Fatal(err)
	}
	names := map[string]bool{}
	fieldPattern := regexp.MustCompile(`"(\w+)":`)
	for _, decl := range file.Decls {
		genDecl, ok := decl.(*ast.GenDecl)
		if !ok || genDecl.Doc == nil {
			continue
		}
		for _, spec := range genDecl.Specs {
			typeSpec, ok := spec.(*ast.TypeSpec)
			if !ok || typeSpec.Name.Name != "Document" {
				continue
			}
			for _, match := range fieldPattern.FindAllStringSubmatch(genDecl.Doc.Text(), -1) {
				names[match[1]] = true
			}
		}
	}
	return names
}

func taggedFieldNames(values ...any) map[string]bool {
	names := map[string]bool{}
	for _, value := range values {
		typ := reflect.TypeOf(value)
		for field := range typ.Fields() {
			tag := field.Tag.Get("json")
			if tag == "" {
				continue
			}
			for j, c := range tag {
				if c == ',' {
					tag = tag[:j]
					break
				}
			}
			names[tag] = true
		}
	}
	return names
}

func assertSameSet(t *testing.T, a, b map[string]bool) {
	t.Helper()
	var onlyInA, onlyInB []string
	for name := range a {
		if !b[name] {
			onlyInA = append(onlyInA, name)
		}
	}
	for name := range b {
		if !a[name] {
			onlyInB = append(onlyInB, name)
		}
	}
	sort.Strings(onlyInA)
	sort.Strings(onlyInB)
	if len(onlyInA) > 0 {
		t.Errorf("doc comment names fields absent from the struct tags: %v", onlyInA)
	}
	if len(onlyInB) > 0 {
		t.Errorf("struct tags carry fields the doc comment does not name: %v", onlyInB)
	}
}
