package probe

import (
	"context"
	"io"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"supervisor/internal/config"
	"supervisor/internal/scribe"
)

func TestProbeUtilBackupMount_BtrfsUUIDAgainstCapturedFilesystemShow(t *testing.T) {
	tests := []struct {
		name          string
		fixture       string
		code          int
		abandoned     bool
		expectedUUID  string
		expectedFound bool
		expectedWedge bool
	}{
		{name: "mounted_backup", fixture: "btrfs/filesystem-show-mounted-backup.txt", expectedUUID: "", expectedFound: true},
		{name: "single_device", fixture: "btrfs/filesystem-show-single-device.txt", expectedFound: true},
		{name: "unidentified_falls_through_to_df", fixture: "btrfs/filesystem-show-unmounted.txt", code: 1},
		{name: "abandoned_wedges_the_path", fixture: "btrfs/filesystem-show-unmounted.txt", abandoned: true, expectedWedge: true},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			btrfsUnidentified.Clear()
			output := fixtureStages(t, testCase.fixture)
			target := "/backup/" + testCase.name
			stageStreamReturns(t, output, testCase.code, testCase.abandoned)
			uuid, found, wedged := btrfsUUID(t.Context(), scribe.SubjectNone, target)
			if found != testCase.expectedFound {
				t.Fatalf("btrfsUUID() found = %v, want %v", found, testCase.expectedFound)
			}
			if wedged != testCase.expectedWedge {
				t.Errorf("btrfsUUID() wedged = %v, want %v", wedged, testCase.expectedWedge)
			}
			if found && uuid == "" {
				t.Errorf("btrfsUUID() returned found with an empty uuid")
			}
			if found && !strings.Contains(output, uuid) {
				t.Errorf("btrfsUUID() = %q, which the fixture does not carry", uuid)
			}
		})
	}
}

func TestProbeUtilBackupMount_AnUnidentifiedPathIsAskedOfBtrfsOnlyOnce(t *testing.T) {
	btrfsUnidentified.Clear()
	calls := 0
	original := stageStream
	t.Cleanup(func() { stageStream = original })
	stageStream = func(_ context.Context, _ io.Writer, _ string, _ ...string) (string, int, bool) {
		calls++
		return "ERROR: not a valid btrfs filesystem", 1, false
	}
	for range 3 {
		if _, found, wedged := btrfsUUID(t.Context(), scribe.SubjectNone, "/backup"); found || wedged {
			t.Fatalf("btrfsUUID() found = %v wedged = %v, want neither", found, wedged)
		}
	}
	if calls != 1 {
		t.Errorf("btrfs was shelled out to [%d] times, want [1] for the rest of the run", calls)
	}
}

func TestProbeUtilBackupMount_FstabIsParsedOnceIntoSpecsAndMountpoints(t *testing.T) {
	root := t.TempDir()
	path := filepath.Join(root, "fstab")
	body := "# a comment\n\nPARTLABEL=backup_02  /backup  btrfs  noauto  0 2\n" +
		"UUID=abc  /share/10  ext4  defaults  0 2\n" +
		"//nas/media  /share/40  cifs  noauto  0 0\n" +
		"broken-line-with-one-field\n"
	if err := os.WriteFile(path, []byte(body), 0644); err != nil {
		t.Fatalf("write fstab: %v", err)
	}
	original := backupFstabPath
	t.Cleanup(func() { backupFstabPath = original })
	backupFstabPath = path

	entries := fstabEntries()
	if len(entries) != 3 {
		t.Fatalf("fstabEntries() = %d entries, want 3 with the comment, blank and short lines dropped", len(entries))
	}
	if got := backupTargets(); len(got) != 1 || got[0] != "/backup" {
		t.Errorf("backupTargets() = %v, want [/backup]", got)
	}
	if got := backupShares(); len(got) != 2 || got[0] != "/share/10" || got[1] != "/share/40" {
		t.Errorf("backupShares() = %v, want [/share/10 /share/40]", got)
	}
}

func TestProbeUtilBackupMount_ShareMountPatternTakesOnlyDigitedShares(t *testing.T) {
	tests := map[string]bool{
		"/share/10": true, "/share/40": true, "/share/1": true,
		"/share/": false, "/share/10a": false, "/shared/10": false, "/backup": false, "/share/10/media": false,
	}
	for mountpoint, expected := range tests {
		if got := shareMountPattern(mountpoint); got != expected {
			t.Errorf("shareMountPattern(%q) = %v, want %v", mountpoint, got, expected)
		}
	}
}

func TestProbeUtilBackupMount_MeasureUsageFallsBackToCapturedDfWhenBtrfsCannotIdentify(t *testing.T) {
	btrfsUnidentified.Clear()
	showOutput := fixtureStages(t, "btrfs/filesystem-show-unmounted.txt")
	dfOutput := fixtureStages(t, "mounts/df-mounted-backup.txt")
	original := stageStream
	t.Cleanup(func() { stageStream = original })
	asked := false
	stageStream = func(_ context.Context, _ io.Writer, name string, _ ...string) (string, int, bool) {
		switch name {
		case "stat":
			return "btrfs\n", 0, false
		case "btrfs":
			asked = true
			return showOutput, 1, false
		}
		return dfOutput, 0, false
	}
	percent, usedMB, totalMB, ok := measureUsage(t.Context(), scribe.SubjectNone, "/backup")
	if !ok {
		t.Fatalf("measureUsage() ok = false, want the df fallback to answer")
	}
	if !asked {
		t.Errorf("measureUsage() never asked btrfs, want a btrfs filesystem tried before df")
	}
	if usedMB != 1072245374976/1048576 || totalMB != 4000785960960/1048576 {
		t.Errorf("measureUsage() used = %d total = %d, want the captured df figures", usedMB, totalMB)
	}
	if percent < 26 || percent > 27 {
		t.Errorf("measureUsage() percent = %.2f, want ~26.8 from the captured df", percent)
	}
}

func TestProbeUtilBackupMount_MeasureUsageNeverAsksBtrfsAboutAnotherFilesystem(t *testing.T) {
	for _, fsType := range []string{"ext2/ext3", "smb2"} {
		t.Run(fsType, func(t *testing.T) {
			btrfsUnidentified.Clear()
			original := stageStream
			t.Cleanup(func() { stageStream = original })
			stageStream = func(_ context.Context, _ io.Writer, name string, _ ...string) (string, int, bool) {
				switch name {
				case "stat":
					return fsType + "\n", 0, false
				case "btrfs":
					t.Fatalf("measureUsage() asked btrfs about a [%s] filesystem", fsType)
				case "df":
					return "used size\n1048576 2097152", 0, false
				}
				return "", 0, false
			}
			if _, _, totalMB, ok := measureUsage(t.Context(), scribe.SubjectNone, "/share/10"); !ok || totalMB != 2 {
				t.Errorf("measureUsage() = (total %d, ok %v), want the df reading", totalMB, ok)
			}
			if _, recorded := btrfsUnidentified.Load("/share/10"); recorded {
				t.Errorf("btrfsUnidentified records [/share/10], want a non-btrfs path never reported as unidentified")
			}
		})
	}
}

func TestProbeUtilBackupMount_MeasureUsageCannotAnswerWhenTheFilesystemIsWedged(t *testing.T) {
	btrfsUnidentified.Clear()
	stageStreamReturns(t, "", stageBoundedAbandoned, true)
	if _, _, _, ok := measureUsage(t.Context(), scribe.SubjectNone, "/backup"); ok {
		t.Errorf("measureUsage() ok = true, want a wedged filesystem to report no reading rather than a df guess")
	}
}

func stageStreamReturns(t *testing.T, output string, code int, abandoned bool) {
	t.Helper()
	original := stageStream
	t.Cleanup(func() { stageStream = original })
	stageStream = func(_ context.Context, _ io.Writer, _ string, _ ...string) (string, int, bool) {
		return output, code, abandoned
	}
}

func TestProbeUtilBackupMount_AliveProbesTheDeviceRatherThanAskingAboutIt(t *testing.T) {
	tests := []struct {
		name      string
		declared  bool
		readCode  int
		abandoned bool
		mounted   bool
		options   string
		expected  bool
	}{
		{name: "a_read_that_answers_on_an_unmounted_target", declared: true, options: "rw,relatime", expected: true},
		{name: "a_read_that_answers_on_a_read_write_mount", declared: true, mounted: true, options: "rw,relatime", expected: true},
		{name: "a_read_that_never_answers", declared: true, abandoned: true, expected: false},
		{name: "a_read_that_errors_at_once", declared: true, readCode: 1, expected: false},
		{name: "a_mount_forced_read_only", declared: true, mounted: true, options: "ro,relatime", expected: false},
		{name: "nothing_declared_is_inert_rather_than_dead", expected: true},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			root := t.TempDir()
			fstab := filepath.Join(root, "fstab")
			body := ""
			if testCase.declared {
				body = "/dev/null  /backup  btrfs  noauto  0 2\n"
			}
			if err := os.WriteFile(fstab, []byte(body), 0o644); err != nil {
				t.Fatalf("write fstab: %v", err)
			}
			original := backupFstabPath
			t.Cleanup(func() { backupFstabPath = original })
			backupFstabPath = fstab
			originalExec := stageStream
			t.Cleanup(func() { stageStream = originalExec })
			stageStream = func(_ context.Context, _ io.Writer, name string, args ...string) (string, int, bool) {
				switch name {
				case "dd":
					return "", testCase.readCode, testCase.abandoned
				case "mountpoint":
					if testCase.mounted {
						return "", 0, false
					}
					return "", 1, false
				case "findmnt":
					return testCase.options, 0, false
				}
				t.Fatalf("alive shelled out to an unexpected [%s %s]", name, strings.Join(args, " "))
				return "", 0, false
			}
			if got := alive(t.Context(), config.DirBackup); got != testCase.expected {
				t.Errorf("alive() = %v, want %v", got, testCase.expected)
			}
		})
	}
}

func TestProbeUtilBackupMount_UsageIsOnlyMeasuredWhileTheTargetIsMounted(t *testing.T) {
	tests := []struct {
		name          string
		mounted       bool
		expectedKnown bool
		expectedTotal int
	}{
		{name: "a_mounted_target_is_measured", mounted: true, expectedKnown: true, expectedTotal: 2},
		{name: "an_unmounted_target_reports_nothing", mounted: false},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			btrfsUnidentified.Clear()
			original := stageStream
			t.Cleanup(func() { stageStream = original })
			stageStream = func(_ context.Context, _ io.Writer, name string, _ ...string) (string, int, bool) {
				switch name {
				case "mountpoint":
					if testCase.mounted {
						return "", 0, false
					}
					return "", 1, false
				case "df":
					return "used size\n1048576 2097152", 0, false
				default:
					return "ERROR: not a valid btrfs filesystem", 1, false
				}
			}
			percent, usedMB, totalMB, ok := measureUsage(t.Context(), scribe.SubjectNone, "/backup")
			if ok != testCase.expectedKnown {
				t.Fatalf("measureUsage() ok = %v, want %v, an unmounted path measures whatever lies under it", ok, testCase.expectedKnown)
			}
			if ok && (totalMB != testCase.expectedTotal || usedMB != 1 || percent != 50) {
				t.Errorf("measureUsage() = (%v, %d, %d), want (50, 1, %d)", percent, usedMB, totalMB, testCase.expectedTotal)
			}
		})
	}
}

func TestProbeUtilBackupMount_ABindOfAHostDirectoryIsNeverDetachedAsADisk(t *testing.T) {
	tests := []struct {
		name     string
		mounted  bool
		fsroot   string
		code     int
		expected bool
	}{
		{name: "the_containers_own_bind_of_the_host_directory", mounted: true, fsroot: "/backup", expected: false},
		{name: "a_btrfs_subvolume_bind_of_the_host_directory", mounted: true, fsroot: "/root/backup", expected: false},
		{name: "an_undeclared_disk_mounted_at_its_top_level", mounted: true, fsroot: "/", expected: true},
		{name: "a_disk_stacked_over_the_bind_reads_its_top_mount", mounted: true, fsroot: "/backup\n/", expected: true},
		{name: "an_unanswered_findmnt_falls_back_to_the_device", mounted: true, code: 1, expected: true},
		{name: "nothing_mounted_has_nothing_to_detach", fsroot: "/", expected: false},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			fstab := filepath.Join(t.TempDir(), "fstab")
			if err := os.WriteFile(fstab, nil, 0o644); err != nil {
				t.Fatalf("write fstab: %v", err)
			}
			originalFstab, originalStream := backupFstabPath, stageStream
			t.Cleanup(func() { backupFstabPath, stageStream = originalFstab, originalStream })
			backupFstabPath = fstab
			stageStream = func(_ context.Context, _ io.Writer, name string, args ...string) (string, int, bool) {
				key := name + " " + strings.Join(args, " ")
				switch {
				case name == "mountpoint":
					if testCase.mounted {
						return "", 0, false
					}
					return "", 1, false
				case strings.HasSuffix(key, "-o FSROOT"):
					return testCase.fsroot, testCase.code, false
				}
				t.Fatalf("detachable shelled out to an unexpected [%s]", key)
				return "", 0, false
			}
			if got := detachable(t.Context(), t.TempDir(), "/dev"); got != testCase.expected {
				t.Errorf("detachable() = %v, want %v", got, testCase.expected)
			}
		})
	}
}
