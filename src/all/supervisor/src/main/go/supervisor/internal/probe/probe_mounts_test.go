package probe

import (
	"fmt"
	"os"
	"path/filepath"
	"slices"
	"strings"
	"testing"
	"time"
)

func TestProbeMounts_Classification(t *testing.T) {
	tests := []struct {
		name               string
		mounts             string
		expectedSystem     []string
		expectedShareLocal []string
		expectedRemote     []string
		expectedError      bool
	}{
		{
			name: "happy_mad_btrfs_subvolumes_dedupe_to_one",
			mounts: "/dev/nvme0n1p6 / btrfs rw 0 0\n" +
				"/dev/nvme0n1p6 /home btrfs rw 0 0\n" +
				"/dev/nvme0n1p6 /var btrfs rw 0 0\n" +
				"/dev/nvme0n1p5 /boot ext4 rw 0 0\n" +
				"/dev/nvme0n1p4 /boot/efi vfat rw 0 0\n" +
				"/dev/sdb1 /share/10 ext4 rw 0 0\n" +
				"systemd-1 /share/20 autofs rw 0 0\n" +
				"//macmini-max/share-20 /share/20 cifs rw 0 0\n" +
				"tmpfs /tmp tmpfs rw 0 0\n" +
				"overlay /var/lib/docker_nocow/overlay2/x/merged overlay rw 0 0\n" +
				"nsfs /run/docker/netns/default nsfs rw 0 0\n",
			expectedSystem:     []string{"/"},
			expectedShareLocal: []string{"/share/10"},
			expectedRemote:     []string{"/share/20"},
			expectedError:      false,
		},
		{
			name: "happy_max_logical_volumes_stay_separate",
			mounts: "/dev/mapper/fedora_macmini--max-root / ext4 rw 0 0\n" +
				"/dev/mapper/fedora_macmini--max-tmp /tmp ext4 rw 0 0\n" +
				"/dev/mapper/fedora_macmini--max-var /var ext4 rw 0 0\n" +
				"/dev/mapper/fedora_macmini--max-home /home ext4 rw 0 0\n" +
				"/dev/mapper/fedora_macmini--max-share_06 /share/20 ext4 rw 0 0\n" +
				"/dev/nvme0n1p2 /boot xfs rw 0 0\n",
			expectedSystem:     []string{"/", "/home", "/tmp", "/var"},
			expectedShareLocal: []string{"/share/20"},
			expectedRemote:     nil,
			expectedError:      false,
		},
		{
			name: "happy_jen_has_no_shares",
			mounts: "/dev/sda2 / ext4 rw 0 0\n" +
				"/dev/sda1 /boot/firmware vfat rw 0 0\n" +
				"ramfs /run/credentials/systemd-sysctl.service ramfs ro 0 0\n" +
				"fusectl /sys/fs/fuse/connections fusectl rw 0 0\n",
			expectedSystem:     []string{"/"},
			expectedShareLocal: nil,
			expectedRemote:     nil,
			expectedError:      false,
		},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			t.Cleanup(resetMounts)
			root := writeMountTree(t, testCase.mounts, "", nil)
			set := newMountFixture(t, root, nil, nil)
			var system, local, remote []string
			parsed, _ := set.parseMounts()
			for _, mount := range parsed {
				switch {
				case mount.remote:
					remote = append(remote, mount.mountpoint)
				case mount.share:
					local = append(local, mount.mountpoint)
				default:
					system = append(system, mount.mountpoint)
				}
			}
			assertMountpoints(t, "system", system, testCase.expectedSystem)
			assertMountpoints(t, "local", local, testCase.expectedShareLocal)
			assertMountpoints(t, "remote", remote, testCase.expectedRemote)
		})
	}
}

func TestProbeMounts_Usage(t *testing.T) {
	t.Cleanup(resetMounts)
	mounts := "/dev/nvme0n1p6 / btrfs rw 0 0\n" +
		"/dev/nvme0n1p5 /var ext4 rw 0 0\n" +
		"/dev/sdb1 /share/10 ext4 rw 0 0\n" +
		"/dev/sdc1 /share/11 ext4 rw 0 0\n"
	root := writeMountTree(t, mounts, "", nil)
	sizes := map[string][2]uint64{
		"/":         {1000, 48},
		"/var":      {1000, 380},
		"/share/10": {1000, 500},
		"/share/11": {3000, 300},
	}
	set := newMountFixture(t, root, sizes, nil)
	set.current = set.collect()
	system, _, err := set.usedHomeSpace()
	if err != nil {
		t.Fatalf("usedHomeSpace: unexpected error %v", err)
	}
	if system != 38 {
		t.Errorf("usedHomeSpace: got %d want %d", system, 38)
	}
	share, _, err := set.usedShareSpace()
	if err != nil {
		t.Fatalf("usedShareSpace: unexpected error %v", err)
	}
	if share != 20 {
		t.Errorf("usedShareSpace: got %d want %d", share, 20)
	}
}

func TestProbeMounts_HomeVolume(t *testing.T) {
	tests := []struct {
		name          string
		mounts        string
		sizes         map[string][2]uint64
		expectedValue int8
		expectedError bool
	}{
		{
			name: "happy_deepest_volume_holding_the_home_wins",
			mounts: "/dev/mapper/vg-root / ext4 rw 0 0\n" +
				"/dev/mapper/vg-var /var ext4 rw 0 0\n",
			sizes:         map[string][2]uint64{"/": {1000, 900}, "/var": {1000, 380}},
			expectedValue: 38,
			expectedError: false,
		},
		{
			name:          "happy_root_holds_the_home_when_nothing_deeper_is_mounted",
			mounts:        "/dev/nvme0n1p6 / btrfs rw 0 0\n",
			sizes:         map[string][2]uint64{"/": {1000, 140}},
			expectedValue: 14,
			expectedError: false,
		},
		{
			name:          "sad_unmeasurable_home_volume_errors",
			mounts:        "/dev/nvme0n1p6 / btrfs rw 0 0\n",
			sizes:         map[string][2]uint64{},
			expectedValue: 0,
			expectedError: true,
		},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			t.Cleanup(resetMounts)
			set := newMountFixture(t, writeMountTree(t, testCase.mounts, "", nil), testCase.sizes, nil)
			set.current = set.collect()
			value, _, err := set.usedHomeSpace()
			if testCase.expectedError != (err != nil) {
				t.Fatalf("error: got %v want error %v", err, testCase.expectedError)
			}
			if !testCase.expectedError && value != testCase.expectedValue {
				t.Errorf("value: got %d want %d", value, testCase.expectedValue)
			}
		})
	}
}

func TestProbeMounts_FailedShares(t *testing.T) {
	tests := []struct {
		name           string
		mounts         string
		fstab          string
		hung           []string
		hollow         []string
		content        []string
		expectedFailed int8
		expectedError  bool
	}{
		{
			name:           "happy_no_shares_declared_reads_zero",
			mounts:         "/dev/sda2 / ext4 rw 0 0\n",
			fstab:          "LABEL=RASPIROOT / ext4 rw 0 1\n",
			expectedFailed: 0,
			expectedError:  false,
		},
		{
			name:   "happy_all_declared_shares_mounted",
			mounts: "/dev/sdb1 /share/10 ext4 rw 0 0\n//macmini-max/share-20 /share/20 cifs rw 0 0\n",
			fstab: "PARTLABEL=share_08 /share/10 ext4 noatime 0 2\n" +
				"//macmini-max/share-20 /share/20 cifs guest,nofail,x-systemd.automount 0 0\n",
			expectedFailed: 0,
			expectedError:  false,
		},
		{
			name:   "happy_unmounted_automount_that_answers_the_touch_is_not_failed",
			mounts: "/dev/sdb1 /share/10 ext4 rw 0 0\n",
			fstab: "PARTLABEL=share_08 /share/10 ext4 noatime 0 2\n" +
				"//macmini-max/share-20 /share/20 cifs guest,nofail,x-systemd.automount 0 0\n",
			content:        []string{"/share/20"},
			expectedFailed: 0,
			expectedError:  false,
		},
		{
			name:   "sad_unmounted_share_that_will_not_answer_is_failed",
			mounts: "/dev/sdb1 /share/10 ext4 rw 0 0\n",
			fstab: "PARTLABEL=share_08 /share/10 ext4 noatime 0 2\n" +
				"//macmini-max/share-20 /share/20 cifs guest,nofail,x-systemd.automount 0 0\n",
			expectedFailed: 50,
			expectedError:  false,
		},
		{
			name:   "sad_hung_share_is_failed_and_excluded_from_usage",
			mounts: "/dev/sdb1 /share/10 ext4 rw 0 0\n//macmini-max/share-20 /share/20 cifs rw 0 0\n",
			fstab: "PARTLABEL=share_08 /share/10 ext4 noatime 0 2\n" +
				"//macmini-max/share-20 /share/20 cifs guest,nofail,x-systemd.automount 0 0\n",
			hung:           []string{"/share/20"},
			expectedFailed: 50,
			expectedError:  false,
		},
		{
			name:   "sad_mounted_share_without_its_content_directory_is_failed",
			mounts: "/dev/sdb1 /share/10 ext4 rw 0 0\n//macmini-max/share-20 /share/20 cifs rw 0 0\n",
			fstab: "PARTLABEL=share_08 /share/10 ext4 noatime 0 2\n" +
				"//macmini-max/share-20 /share/20 cifs guest,nofail,x-systemd.automount 0 0\n",
			hollow:         []string{"/share/20"},
			expectedFailed: 50,
			expectedError:  false,
		},
		{
			name:   "happy_noauto_declaration_is_never_expected",
			mounts: "/dev/sdb1 /share/10 ext4 rw 0 0\n",
			fstab: "PARTLABEL=share_08 /share/10 ext4 noatime 0 2\n" +
				"PARTLABEL=backup_04 /share/99 ext4 noatime,errors=remount-ro,noauto 0 2\n",
			expectedFailed: 0,
			expectedError:  false,
		},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			t.Cleanup(resetMounts)
			root := writeMountTree(t, testCase.mounts, testCase.fstab, nil)
			for _, mountpoint := range testCase.content {
				if err := os.MkdirAll(filepath.Join(root, mountpoint, mountContentDir), 0o755); err != nil {
					t.Fatalf("mkdir share content failed: %v", err)
				}
			}
			for _, mountpoint := range testCase.hollow {
				if err := os.RemoveAll(filepath.Join(root, mountpoint, mountContentDir)); err != nil {
					t.Fatalf("remove share content failed: %v", err)
				}
			}
			sizes := map[string][2]uint64{"/share/10": {1000, 100}, "/share/20": {1000, 100}}
			set := newMountFixture(t, root, sizes, testCase.hung)
			set.current = set.collect()
			failed, _, err := set.failedShares()
			if err != nil {
				t.Fatalf("failedShares: unexpected error %v", err)
			}
			if failed != testCase.expectedFailed {
				t.Errorf("failedShares: got %d want %d", failed, testCase.expectedFailed)
			}
		})
	}
}

func TestProbeMounts_Physical(t *testing.T) {
	tests := []struct {
		name             string
		device           string
		expectedPhysical string
		expectedError    bool
	}{
		{
			name:             "happy_nvme_partition_resolves_to_its_controller",
			device:           "/dev/nvme0n1p6",
			expectedPhysical: "nvme0",
			expectedError:    false,
		},
		{
			name:             "happy_nvme_namespace_resolves_to_its_controller",
			device:           "/dev/nvme0n2",
			expectedPhysical: "nvme0",
			expectedError:    false,
		},
		{
			name:             "happy_sata_partition_resolves_to_its_disk",
			device:           "/dev/sda1",
			expectedPhysical: "sda",
			expectedError:    false,
		},
		{
			name:             "happy_mapper_resolves_through_slaves_to_the_controller",
			device:           "/dev/mapper/fedora_macmini--max-root",
			expectedPhysical: "nvme0",
			expectedError:    false,
		},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			t.Cleanup(resetMounts)
			root := writeMountTree(t, "", "", nil)
			writeBlockTree(t, root)
			set := newMountFixture(t, root, nil, nil)
			if physical := set.physical(testCase.device); physical != testCase.expectedPhysical {
				t.Errorf("physical: got %q want %q", physical, testCase.expectedPhysical)
			}
		})
	}
}

func TestProbeMounts_Wear(t *testing.T) {
	tests := []struct {
		name          string
		report        smartReport
		reportErr     error
		second        *smartReport
		expectedLife  int8
		expectedOK    bool
		expectedError bool
	}{
		{
			name:          "happy_nvme_written_against_its_rating",
			report:        smartReport{model: "APPLE SSD AP0512Z", written: 41583499 * bytesPerDataUnit, supported: true},
			expectedLife:  7,
			expectedOK:    true,
			expectedError: false,
		},
		{
			name:          "happy_sata_lbas_written_against_its_rating",
			report:        smartReport{model: "CT480BX500SSD1", written: 42053531430 * bytesPerSector, supported: true},
			expectedLife:  18,
			expectedOK:    true,
			expectedError: false,
		},
		{
			name:          "happy_high_but_unchanging_error_count_stays_ok",
			report:        smartReport{model: "CT2000P2SSD8", written: 61141491 * bytesPerDataUnit, errors: 96, supported: true},
			expectedLife:  5,
			expectedOK:    true,
			expectedError: false,
		},
		{
			name:          "sad_error_count_rising_by_one_is_not_ok",
			report:        smartReport{model: "CT2000P2SSD8", written: 61141491 * bytesPerDataUnit, errors: 96, supported: true},
			second:        &smartReport{model: "CT2000P2SSD8", written: 61141491 * bytesPerDataUnit, errors: 97, supported: true},
			expectedLife:  5,
			expectedOK:    false,
			expectedError: false,
		},
		{
			name:          "happy_drive_with_no_smart_support_is_excluded",
			report:        smartReport{supported: false},
			expectedLife:  0,
			expectedOK:    true,
			expectedError: false,
		},
		{
			name:          "happy_unrated_model_is_excluded",
			report:        smartReport{model: "SOME UNKNOWN SSD", written: 1000 * bytesPerDataUnit, supported: true},
			expectedLife:  0,
			expectedOK:    true,
			expectedError: false,
		},
		{
			name:          "sad_unreadable_drive_faults_rather_than_reading_zero",
			reportErr:     fmt.Errorf("smart unavailable"),
			expectedLife:  0,
			expectedOK:    false,
			expectedError: true,
		},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			t.Cleanup(resetMounts)
			root := writeMountTree(t, "/dev/sda1 /share/10 ext4 rw 0 0\n", "", nil)
			writeBlockTree(t, root)
			set := newMountFixture(t, root, map[string][2]uint64{"/share/10": {1000, 100}}, nil)
			reports := testCase.report
			set.smart = func(string, []string) (smartReport, error) { return reports, testCase.reportErr }
			set.current = set.collect()
			if testCase.second != nil {
				reports = *testCase.second
				set.current = set.collect()
			}
			life, _, err := set.lifeUsedDrives()
			if testCase.expectedError {
				if err == nil {
					t.Fatalf("lifeUsedDrives: expected error but got nil")
				}
				return
			}
			if err != nil {
				t.Fatalf("lifeUsedDrives: unexpected error %v", err)
			}
			if life != testCase.expectedLife {
				t.Errorf("lifeUsedDrives: got %d want %d", life, testCase.expectedLife)
			}
			failed, _, failedErr := set.failedDrives()
			if failedErr != nil {
				t.Fatalf("failedDrives: unexpected error %v", failedErr)
			}
			if (failed == 0) != testCase.expectedOK {
				t.Errorf("failedDrives: got %d pct want ok %v", failed, testCase.expectedOK)
			}
		})
	}
}

func TestProbeMounts_RefreshPanicIsContained(t *testing.T) {
	t.Cleanup(resetMounts)
	root := writeMountTree(t, "/dev/sda2 / ext4 rw 0 0\n", "", nil)
	set := newMountFixture(t, root, map[string][2]uint64{"/": {1000, 100}}, nil)
	set.current = set.collect()
	set.statfs = func(string) (uint64, uint64, error) { panic("statfs exploded") }
	set.request(0)
	deadline := time.Now().Add(3 * time.Second)
	for time.Now().Before(deadline) {
		set.mutex.Lock()
		refreshing := set.refreshing
		set.mutex.Unlock()
		if !refreshing {
			break
		}
		time.Sleep(10 * time.Millisecond)
	}
	set.mutex.Lock()
	refreshing := set.refreshing
	set.mutex.Unlock()
	if refreshing {
		t.Fatalf("Got the refresher still marked running after a panic, expected it released")
	}
	if _, _, err := set.usedHomeSpace(); err == nil {
		t.Fatalf("usedHomeSpace: expected the panicking mount to read not ok rather than crash the process")
	}
}

func TestProbeMounts_RetriesFasterWhileAShareIsFailed(t *testing.T) {
	tests := []struct {
		name            string
		failed          int
		taken           time.Duration
		expectedRefresh bool
	}{
		{
			name:            "happy_healthy_snapshot_waits_for_the_cache_period",
			failed:          0,
			taken:           2 * time.Minute,
			expectedRefresh: false,
		},
		{
			name:            "happy_failed_share_retries_on_the_retry_period",
			failed:          1,
			taken:           2 * time.Minute,
			expectedRefresh: true,
		},
		{
			name:            "happy_failed_share_inside_the_retry_period_waits",
			failed:          1,
			taken:           10 * time.Second,
			expectedRefresh: false,
		},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			t.Cleanup(resetMounts)
			root := writeMountTree(t, "/dev/sda2 / ext4 rw 0 0\n", "", nil)
			set := newMountFixture(t, root, map[string][2]uint64{"/": {1000, 100}}, nil)
			set.current = &mountSnapshot{taken: time.Now().Add(-testCase.taken), failed: testCase.failed, shares: testCase.failed}
			set.request(time.Hour)
			set.mutex.Lock()
			refreshing := set.refreshing
			set.mutex.Unlock()
			if refreshing != testCase.expectedRefresh {
				t.Errorf("request: got refreshing %v want %v", refreshing, testCase.expectedRefresh)
			}
		})
	}
}

func TestProbeMounts_WarmingUp(t *testing.T) {
	t.Cleanup(resetMounts)
	root := writeMountTree(t, "/dev/sda2 / ext4 rw 0 0\n", "", nil)
	set := newMountFixture(t, root, nil, nil)
	if _, _, err := set.usedHomeSpace(); err == nil {
		t.Fatalf("usedHomeSpace: expected the warming up error before the first snapshot")
	}
}

func TestProbeMounts_UnreadableMountTable(t *testing.T) {
	t.Cleanup(resetMounts)
	root := t.TempDir()
	set := newMountFixture(t, root, nil, nil)
	set.current = set.collect()
	if _, _, err := set.usedHomeSpace(); err == nil {
		t.Fatalf("usedHomeSpace: expected an error when the mount table cannot be read")
	}
}

func mountTableAt(root, mounts string) string {
	var lines []string
	for line := range strings.SplitSeq(mounts, "\n") {
		fields := strings.Fields(line)
		if len(fields) < 3 {
			lines = append(lines, line)
			continue
		}
		fields[1] = filepath.Join(root, fields[1])
		lines = append(lines, strings.Join(fields, " "))
	}
	return strings.Join(lines, "\n")
}

func newMountFixture(t *testing.T, root string, sizes map[string][2]uint64, hung []string) *mountSet {
	t.Helper()
	hanging := map[string]bool{}
	for _, mountpoint := range hung {
		hanging[filepath.Join(root, mountpoint)] = true
	}
	set := &mountSet{
		root:       root,
		physicals:  map[string]string{},
		identities: map[string]*driveIdentity{},
		inflight:   map[string]bool{},
		smart:      func(string, []string) (smartReport, error) { return smartReport{}, fmt.Errorf("no smart in fixtures") },
	}
	set.statfs = func(path string) (uint64, uint64, error) {
		if hanging[path] {
			return 0, 0, fmt.Errorf("mount hung")
		}
		mountpoint := strings.TrimPrefix(path, root)
		if mountpoint == "" {
			mountpoint = "/"
		}
		size, found := sizes[mountpoint]
		if !found {
			return 0, 0, fmt.Errorf("no fixture for [%s]", path)
		}
		return size[0], size[1], nil
	}
	return set
}

func TestProbeMounts_BaseFallsBackOutsideTheContainer(t *testing.T) {
	tests := []struct {
		name        string
		rootedTable bool
		bareTable   bool
		expectedTop bool
	}{
		{name: "happy_configured_root_wins_when_it_holds_a_table", rootedTable: true, bareTable: true, expectedTop: true},
		{name: "happy_bare_root_is_used_when_the_root_holds_none", rootedTable: false, bareTable: true, expectedTop: false},
		{name: "sad_configured_root_is_kept_when_neither_holds_one", rootedTable: false, bareTable: false, expectedTop: true},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			root, bare := t.TempDir(), t.TempDir()
			if testCase.rootedTable {
				writeMountFile(t, filepath.Join(root, mountTablePath), "/dev/sda1 / ext4 rw 0 0\n")
			}
			if testCase.bareTable {
				writeMountFile(t, filepath.Join(bare, mountTablePath), "/dev/sda1 / ext4 rw 0 0\n")
			}
			previous := mountBareRoot
			mountBareRoot = bare
			t.Cleanup(func() { mountBareRoot = previous })
			expected := bare
			if testCase.expectedTop {
				expected = root
			}
			if got := mountBase(root); got != expected {
				t.Errorf("base: got %q want %q", got, expected)
			}
		})
	}
}

func TestProbeMounts_ContainerMountsAreDropped(t *testing.T) {
	t.Cleanup(resetMounts)
	root := t.TempDir()
	writeMountFile(t, filepath.Join(root, mountTablePath),
		"overlay / overlay rw 0 0\n"+
			"/dev/nvme0n1p6 /etc/hosts btrfs rw 0 0\n"+
			"/dev/nvme0n1p6 /etc/resolv.conf btrfs rw 0 0\n"+
			"/dev/nvme0n1p6 "+root+" btrfs rw 0 0\n"+
			"/dev/nvme0n1p5 "+filepath.Join(root, "/boot")+" ext4 rw 0 0\n"+
			"/dev/sdb1 "+filepath.Join(root, "/share/10")+" ext4 rw 0 0\n")
	set := newMountFixture(t, root, nil, nil)
	var kept []string
	parsed, _ := set.parseMounts()
	for _, mount := range parsed {
		kept = append(kept, mount.mountpoint)
	}
	expected := []string{"/", "/share/10"}
	if strings.Join(kept, ",") != strings.Join(expected, ",") {
		t.Errorf("mountpoints: got %v want %v", kept, expected)
	}
}

func writeMountTree(t *testing.T, mounts, fstab string, extra map[string]string) string {
	t.Helper()
	root := t.TempDir()
	if mounts != "" {
		writeMountFile(t, filepath.Join(root, mountTablePath), mountTableAt(root, mounts))
		for line := range strings.SplitSeq(mounts, "\n") {
			fields := strings.Fields(line)
			if len(fields) < 3 || !strings.HasPrefix(fields[1], mountShareRoot+"/") || fields[2] == "autofs" {
				continue
			}
			if err := os.MkdirAll(filepath.Join(root, fields[1], mountContentDir), 0o755); err != nil {
				t.Fatalf("mkdir share content failed: %v", err)
			}
		}
	}
	if fstab != "" {
		writeMountFile(t, filepath.Join(root, mountFstabPath), fstab)
	}
	for path, content := range extra {
		writeMountFile(t, filepath.Join(root, path), content)
	}
	return root
}

func writeBlockTree(t *testing.T, root string) {
	t.Helper()
	devices := filepath.Join(root, "devices")
	nvme := filepath.Join(devices, "pci0000:00", "nvme", "nvme0", "nvme0n1")
	sata := filepath.Join(devices, "pci0000:00", "ata1", "block", "sda")
	for _, dir := range []string{filepath.Join(nvme, "nvme0n1p6"), filepath.Join(nvme, "nvme0n1p3"), filepath.Join(sata, "sda1")} {
		if err := os.MkdirAll(dir, 0o755); err != nil {
			t.Fatalf("mkdir %s failed: %v", dir, err)
		}
	}
	block := filepath.Join(root, mountBlockPath)
	if err := os.MkdirAll(block, 0o755); err != nil {
		t.Fatalf("mkdir %s failed: %v", block, err)
	}
	links := map[string]string{
		"nvme0n1":   nvme,
		"nvme0n1p6": filepath.Join(nvme, "nvme0n1p6"),
		"nvme0n1p3": filepath.Join(nvme, "nvme0n1p3"),
		"nvme0n2":   filepath.Join(devices, "pci0000:00", "nvme", "nvme0", "nvme0n2"),
		"sda":       sata,
		"sda1":      filepath.Join(sata, "sda1"),
		"dm-0":      filepath.Join(devices, "virtual", "block", "dm-0"),
	}
	if err := os.MkdirAll(links["nvme0n2"], 0o755); err != nil {
		t.Fatalf("mkdir nvme0n2 failed: %v", err)
	}
	if err := os.MkdirAll(links["dm-0"], 0o755); err != nil {
		t.Fatalf("mkdir dm-0 failed: %v", err)
	}
	for name, target := range links {
		if err := os.Symlink(target, filepath.Join(block, name)); err != nil {
			t.Fatalf("symlink %s failed: %v", name, err)
		}
	}
	writeMountFile(t, filepath.Join(block, "nvme0n1p6", "partition"), "6\n")
	writeMountFile(t, filepath.Join(block, "nvme0n1p3", "partition"), "3\n")
	writeMountFile(t, filepath.Join(block, "sda1", "partition"), "1\n")
	writeMountFile(t, filepath.Join(block, "dm-0", "dm", "name"), "fedora_macmini--max-root\n")
	writeMountFile(t, filepath.Join(block, "dm-0", "slaves", "nvme0n1p3", "keep"), "")
}

func writeMountFile(t *testing.T, path, content string) {
	t.Helper()
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		t.Fatalf("mkdir %s failed: %v", filepath.Dir(path), err)
	}
	if err := os.WriteFile(path, []byte(content), 0o644); err != nil {
		t.Fatalf("write %s failed: %v", path, err)
	}
}

func assertMountpoints(t *testing.T, label string, got, want []string) {
	t.Helper()
	if len(got) != len(want) {
		t.Fatalf("%s: got %v want %v", label, got, want)
	}
	for index := range got {
		if got[index] != want[index] {
			t.Fatalf("%s: got %v want %v", label, got, want)
		}
	}
}

func TestProbeMounts_DriveKinds(t *testing.T) {
	tests := []struct {
		name          string
		physical      string
		expectedKinds []string
		expectedError bool
	}{
		{name: "happy nvme asks for the nvme protocol", physical: "nvme0", expectedKinds: []string{driveKindNVME}, expectedError: false},
		{name: "happy sata tries ata pass through then scsi", physical: "sda", expectedKinds: []string{driveKindSAT, driveKindSCSI}, expectedError: false},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			if got := driveKinds(testCase.physical); !slices.Equal(got, testCase.expectedKinds) {
				t.Errorf("kinds: got %v want %v", got, testCase.expectedKinds)
			}
		})
	}
}

func TestProbeMounts_DriveNamespace(t *testing.T) {
	root := t.TempDir()
	blocks := filepath.Join(root, mountBlockPath)
	if err := os.MkdirAll(blocks, 0o755); err != nil {
		t.Fatalf("mkdir: %v", err)
	}
	for _, name := range []string{"nvme0n2", "nvme0n1", "nvme1n1", "sda"} {
		if err := os.MkdirAll(filepath.Join(blocks, name), 0o755); err != nil {
			t.Fatalf("mkdir %s: %v", name, err)
		}
	}
	tests := []struct {
		name          string
		physical      string
		expectedNode  string
		expectedError bool
	}{
		{name: "happy controller resolves to its lowest namespace", physical: "nvme0", expectedNode: "nvme0n1", expectedError: false},
		{name: "happy namespace is left alone", physical: "nvme0n2", expectedNode: "nvme0n2", expectedError: false},
		{name: "happy sata is left alone", physical: "sda", expectedNode: "sda", expectedError: false},
		{name: "sad unknown controller falls back to its first namespace", physical: "nvme9", expectedNode: "nvme9n1", expectedError: false},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			set := &mountSet{root: root}
			if got := set.namespace(testCase.physical); got != testCase.expectedNode {
				t.Errorf("namespace: got %q want %q", got, testCase.expectedNode)
			}
		})
	}
}
