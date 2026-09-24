package probe

import (
	"slices"
	"testing"
)

func TestProbeUtilBackupKernel_ReplayedDetectsAnUncleanMountOnly(t *testing.T) {
	tests := []struct {
		name     string
		lines    []string
		expected bool
	}{
		{name: "tree_log_replay", lines: []string{"BTRFS info (device sdb1): start tree-log replay"}, expected: true},
		{name: "changed_since_last_mount", lines: []string{"BTRFS warning (device sdb1): dev /dev/sdb1 has been changed"}, expected: true},
		{name: "an_ordinary_mount", lines: []string{"BTRFS info (device sdb1): using free space tree", "BTRFS info (device sdb1): enabling ssd optimizations"}, expected: false},
		{name: "nothing_logged", lines: nil, expected: false},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			if got := kernelReplayed(testCase.lines); got != testCase.expected {
				t.Errorf("kernelReplayed() = %v, want %v", got, testCase.expected)
			}
		})
	}
}

func TestProbeUtilBackupKernel_CorruptedNamesEachPathOnceSorted(t *testing.T) {
	lines := []string{
		"BTRFS warning (device sdb1): checksum error at logical 123 on dev /dev/sdb1, physical 1 (path: share/10/media/b.mkv)",
		"BTRFS warning (device sdb1): checksum error at logical 456 on dev /dev/sdb1, physical 2 (path: share/10/media/a.mkv)",
		"BTRFS warning (device sdb1): checksum error at logical 789 on dev /dev/sdb1, physical 3 (path: share/10/media/b.mkv)",
		"BTRFS info (device sdb1): no error here",
	}
	expected := []string{"share/10/media/a.mkv", "share/10/media/b.mkv"}
	if got := kernelCorrupted(lines); !slices.Equal(got, expected) {
		t.Errorf("kernelCorrupted() = %v, want %v", got, expected)
	}
}

func TestProbeUtilBackupKernel_CorruptedStripsControlCharactersFromAPath(t *testing.T) {
	got := kernelCorrupted([]string{"BTRFS warning: csum failed (path: share/10/me\x01dia/a.mkv)"})
	if len(got) != 1 || got[0] != "share/10/media/a.mkv" {
		t.Errorf("kernelCorrupted() = %v, want the path with its control characters dropped", got)
	}
}

func TestProbeUtilBackupKernel_FaultedKeepsOnlyDiskFaultsAndTheNewestOnes(t *testing.T) {
	lines := []string{
		"BTRFS warning (device sdb1): csum failed root 5",
		"usb 2-1: USB disconnect, device number 4",
		"blk_update_request: I/O error, dev sdb, sector 1234",
		"systemd[1]: Started something entirely unrelated",
	}
	got := kernelFaulted(lines)
	if len(got) != 3 || slices.Contains(got, lines[3]) {
		t.Errorf("kernelFaulted() = %v, want the three disk faults alone", got)
	}
	var many []string
	for range kernelFaultsKept + 10 {
		many = append(many, "blk_update_request: I/O error, dev sdb, sector 1")
	}
	if got := kernelFaulted(many); len(got) != kernelFaultsKept {
		t.Errorf("kernelFaulted() kept %d lines, want the newest %d", len(got), kernelFaultsKept)
	}
}
