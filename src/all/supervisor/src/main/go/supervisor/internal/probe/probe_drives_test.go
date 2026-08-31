package probe

import (
	"fmt"
	"math"
	"os"
	"path/filepath"
	"slices"
	"testing"
	"time"
)

func TestProbeDrives_Physical(t *testing.T) {
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

func TestProbeDrives_Wear(t *testing.T) {
	tests := []struct {
		name          string
		report        smartReport
		reportErr     error
		second        *smartReport
		expectedLife  int8
		expectedOK    bool
		expectedFault bool
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
			name:          "sad_unreadable_drive_faults_rather_than_reading_zero_wear",
			reportErr:     fmt.Errorf("smart unavailable"),
			expectedLife:  0,
			expectedOK:    false,
			expectedFault: true,
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
			if (failedErr != nil) != testCase.expectedFault {
				t.Fatalf("failedDrives: got error %v want fault %v", failedErr, testCase.expectedFault)
			}
			if testCase.expectedFault {
				return
			}
			if (failed == 0) != testCase.expectedOK {
				t.Errorf("failedDrives: got %d pct want ok %v", failed, testCase.expectedOK)
			}
		})
	}
}

func TestProbeDrives_DriveKinds(t *testing.T) {
	tests := []struct {
		name          string
		physical      string
		expectedKinds []string
		expectedError bool
	}{
		{name: "happy nvme asks for the nvme protocol", physical: "nvme0", expectedKinds: []string{driveKindNVME}, expectedError: false},
		{name: "happy sata tries ata pass through then the bridges then scsi", physical: "sda", expectedKinds: []string{driveKindSAT, driveKindRealtek, driveKindJMicron, driveKindASMedia, driveKindSCSI}, expectedError: false},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			if got := driveKinds(testCase.physical); !slices.Equal(got, testCase.expectedKinds) {
				t.Errorf("kinds: got %v want %v", got, testCase.expectedKinds)
			}
		})
	}
}

func TestProbeDrives_DriveNamespace(t *testing.T) {
	root := t.TempDir()
	blocks := filepath.Join(root, driveBlockPath)
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

func TestProbeDrives_IgnoresFlashButNotSolidState(t *testing.T) {
	tests := []struct {
		name            string
		hardware        string
		expectedIgnored bool
		expectedError   bool
	}{
		{name: "happy_lexar_flash_drive_is_ignored", hardware: "Lexar USB Flash Drive", expectedIgnored: true, expectedError: false},
		{name: "happy_generic_flash_drive_is_ignored", hardware: "SanDisk Ultra Flash Drive", expectedIgnored: true, expectedError: false},
		{name: "happy_bridged_ssd_is_kept", hardware: "Realtek RTL9210B-CG", expectedIgnored: false, expectedError: false},
		{name: "happy_crucial_p3_is_kept", hardware: "CT4000P3 PSSD8", expectedIgnored: false, expectedError: false},
		{name: "happy_crucial_mx500_is_kept", hardware: "CT4000MX 500SSD1", expectedIgnored: false, expectedError: false},
		{name: "happy_apple_internal_is_kept", hardware: "APPLE SSD AP0512Z", expectedIgnored: false, expectedError: false},
		{name: "happy_unknown_hardware_is_kept", hardware: driveUnknownHardware, expectedIgnored: false, expectedError: false},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			if ignored := driveIgnoredPattern.MatchString(testCase.hardware); ignored != testCase.expectedIgnored {
				t.Errorf("ignored: got %v want %v for %q", ignored, testCase.expectedIgnored, testCase.hardware)
			}
		})
	}
}

func TestProbeDrives_HardwareFromInquiryFields(t *testing.T) {
	tests := []struct {
		name             string
		vendor           string
		model            string
		expectedHardware string
		expectedRated    bool
		expectedError    bool
	}{
		{name: "happy_nvme_carries_no_vendor", vendor: "", model: "CT2000P2SSD8                            ", expectedHardware: "CT2000P2SSD8", expectedRated: true, expectedError: false},
		{name: "happy_apple_nvme_carries_no_vendor", vendor: "", model: "APPLE SSD AP0512Z                       ", expectedHardware: "APPLE SSD AP0512Z", expectedRated: true, expectedError: false},
		{name: "happy_sata_vendor_placeholder_is_dropped", vendor: "ATA     ", model: "CT4000MX500SSD1 ", expectedHardware: "CT4000MX500SSD1", expectedRated: true, expectedError: false},
		{name: "happy_usb_model_spills_into_vendor", vendor: "CT4000P3", model: "PSSD8           ", expectedHardware: "CT4000P3PSSD8", expectedRated: true, expectedError: false},
		{name: "happy_usb_model_spills_across_both_fields", vendor: "CT480BX5", model: "00SSD1          ", expectedHardware: "CT480BX500SSD1", expectedRated: true, expectedError: false},
		{name: "happy_full_width_vendor_keeps_its_space", vendor: "KINGSTON", model: " SA400S37480G   ", expectedHardware: "KINGSTON SA400S37480G", expectedRated: true, expectedError: false},
		{name: "happy_bridge_reports_its_own_chip", vendor: "Realtek ", model: "RTL9210B-CG     ", expectedHardware: "Realtek RTL9210B-CG", expectedRated: false, expectedError: false},
		{name: "happy_flash_drive_names_its_vendor", vendor: "Lexar   ", model: "USB Flash Drive ", expectedHardware: "Lexar USB Flash Drive", expectedRated: false, expectedError: false},
		{name: "happy_absent_fields_are_unknown", vendor: "", model: "", expectedHardware: driveUnknownHardware, expectedRated: false, expectedError: false},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			hardware := driveHardware(testCase.vendor, testCase.model)
			if hardware != testCase.expectedHardware {
				t.Errorf("hardware: got %q want %q", hardware, testCase.expectedHardware)
			}
			if rated := driveRatings[hardware] > 0; rated != testCase.expectedRated {
				t.Errorf("rated: got %v want %v for %q", rated, testCase.expectedRated, hardware)
			}
		})
	}
}

func TestProbeDrives_DriveLifeTakesTheHigher(t *testing.T) {
	tests := []struct {
		name          string
		written       float64
		rating        float64
		estimate      float64
		estimated     bool
		expectedLife  float64
		expectedError bool
	}{
		{name: "happy_mad_lexar_computed_beats_the_drive", written: 26.4 * bytesPerTB, rating: 3000, estimate: 0, estimated: true, expectedLife: 0.88, expectedError: false},
		{name: "happy_mad_crucial_computed_beats_the_drive", written: 3.6 * bytesPerTB, rating: 800, estimate: 0, estimated: true, expectedLife: 0.45, expectedError: false},
		{name: "happy_drive_estimate_beats_the_computed", written: 26.4 * bytesPerTB, rating: 3000, estimate: 12, estimated: true, expectedLife: 12, expectedError: false},
		{name: "happy_no_estimate_keeps_the_computed", written: 500 * bytesPerTB, rating: 1000, estimate: 0, estimated: false, expectedLife: 50, expectedError: false},
		{name: "happy_unwritten_drive_reads_zero", written: 0, rating: 1000, estimate: 0, estimated: false, expectedLife: 0, expectedError: false},
		{name: "happy_unrated_drive_falls_back_to_the_estimate", written: 26.4 * bytesPerTB, rating: 0, estimate: 7, estimated: true, expectedLife: 7, expectedError: false},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			computed := driveComputed(testCase.written, testCase.rating)
			if life := driveLife(computed, testCase.estimate, testCase.estimated); math.Abs(life-testCase.expectedLife) > 0.01 {
				t.Errorf("life: got %.2f want %.2f", life, testCase.expectedLife)
			}
		})
	}
}

func TestProbeDrives_DrivesHonourTheCacheWindow(t *testing.T) {
	tests := []struct {
		name          string
		window        time.Duration
		remount       string
		expectedReads int
		expectedError bool
	}{
		{name: "happy_unchanged_drives_within_the_window_are_reused", window: time.Hour, remount: "", expectedReads: 1, expectedError: false},
		{name: "happy_expired_window_re_reads", window: time.Nanosecond, remount: "", expectedReads: 2, expectedError: false},
		{name: "happy_a_new_drive_re_reads_within_the_window", window: time.Hour, remount: "/dev/sdc1 /share/12 ext4 rw 0 0\n", expectedReads: 2, expectedError: false},
	}
	for _, testCase := range tests {
		t.Cleanup(resetMounts)
		t.Run(testCase.name, func(t *testing.T) {
			mounts := "/dev/nvme0n1p6 / btrfs rw 0 0\n/dev/sdb1 /share/10 ext4 rw 0 0\n"
			root := writeMountTree(t, mounts, "", nil)
			set := newMountFixture(t, root, map[string][2]uint64{"/": {1000, 100}, "/share/10": {1000, 100}, "/share/12": {1000, 100}}, nil)
			set.window = testCase.window
			set.physicals["/dev/nvme0n1p6"] = "nvme0"
			set.physicals["/dev/sdb1"] = "sdb"
			set.physicals["/dev/sdc1"] = "sdc"
			reads := 0
			set.smart = func(string, []string) (smartReport, error) {
				reads++
				return smartReport{data: true, model: "CT4000P3PSSD8", supported: true, written: bytesPerTB}, nil
			}
			set.current = set.collect()
			if testCase.remount != "" {
				writeMountFile(t, filepath.Join(root, mountTablePath), mountTableAt(root, mounts+testCase.remount))
				if err := os.MkdirAll(filepath.Join(root, "/share/12", mountContentDir), 0o755); err != nil {
					t.Fatalf("remount content: got %v want nil", err)
				}
			}
			before := reads
			set.current = set.collect()
			if got := len(set.current.drives); got == 0 {
				t.Fatalf("drives: got %d want at least one", got)
			}
			passes := 1
			if reads > before {
				passes = 2
			}
			if passes != testCase.expectedReads {
				t.Errorf("reads: got %d passes want %d, smart called [%d] times", passes, testCase.expectedReads, reads)
			}
		})
	}
}
