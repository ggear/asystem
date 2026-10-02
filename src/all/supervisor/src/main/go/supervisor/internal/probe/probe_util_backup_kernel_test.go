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

func TestProbeUtilBackupKernel_CorruptedNamesEachRootAndPathOnceSorted(t *testing.T) {
	lines := []string{
		"[ 812.1] BTRFS warning (device sdb1): checksum error at logical 123 on dev /dev/sdb1, physical 1, root 257, inode 300, offset 0, length 4096, links 1 (path: media/b.mkv)",
		"[ 812.2] BTRFS warning (device sdb1): checksum error at logical 456 on dev /dev/sdb1, physical 2, root 257, inode 301, offset 0, length 4096, links 1 (path: media/Film (2010)/film.mkv)",
		"[ 812.3] BTRFS warning (device sdb1): checksum error at logical 123 on dev /dev/sdb1, physical 1, root 258, inode 300, offset 0, length 4096, links 1 (path: media/b.mkv)",
		"[ 812.4] BTRFS warning (device sdb1): checksum error at logical 123 on dev /dev/sdb1, physical 1, root 257, inode 300, offset 4096, length 4096, links 1 (path: media/b.mkv)",
		"[ 812.5] BTRFS error (device sdb1): unable to fixup (regular) error at logical 123 on dev /dev/sdb1",
		"[ 812.6] BTRFS info (device sdb1): no error here",
	}
	expected := []kernelCorruption{
		{root: 257, path: "media/Film (2010)/film.mkv"},
		{root: 257, path: "media/b.mkv"},
		{root: 258, path: "media/b.mkv"},
	}
	if got := kernelCorrupted(lines); !slices.Equal(got, expected) {
		t.Errorf("kernelCorrupted() = %v, want %v", got, expected)
	}
}

func TestProbeUtilBackupKernel_CorruptedKeepsAPathWithNoRoot(t *testing.T) {
	got := kernelCorrupted([]string{"BTRFS warning: csum failed (path: share/10/me\x01dia/a.mkv)"})
	if len(got) != 1 || got[0] != (kernelCorruption{path: "share/10/media/a.mkv"}) {
		t.Errorf("kernelCorrupted() = %v, want the path at root [0] with its control characters dropped", got)
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
