package engine

import (
	"reflect"
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

func TestEngineImplSpace_ClassifyDrive(t *testing.T) {
	cases := []struct {
		name          string
		mountpoint    string
		drives        []string
		wantClass     string
		wantMatched   bool
		expectedError bool
	}{
		{name: "default root", mountpoint: "/", drives: DefaultDrives, wantClass: ClassRoot, wantMatched: true},
		{name: "default share", mountpoint: "/share/10", drives: DefaultDrives, wantClass: ClassShare, wantMatched: true},
		{name: "default backup", mountpoint: "/backup", drives: DefaultDrives, wantClass: ClassBackup, wantMatched: true},
		{name: "shares only set excludes root", mountpoint: "/", drives: []string{"/share/*"}, wantMatched: false},
		{name: "shares only set matches a share", mountpoint: "/share/10", drives: []string{"/share/*"}, wantClass: ClassShare, wantMatched: true},
		{name: "a home path glob", mountpoint: "/Users/rue/Desktop/share/10", drives: []string{"/Users/rue/Desktop/share/*"}, wantClass: ClassShare, wantMatched: true},
		{name: "first match wins", mountpoint: "/share/10", drives: []string{"/share/10", "/share/*"}, wantClass: ClassShare, wantMatched: true},
		{name: "no pattern matches", mountpoint: "/proc", drives: DefaultDrives, wantMatched: false},
		{name: "anchored pattern does not prefix match", mountpoint: "/share/10", drives: []string{"/share/1"}, wantMatched: false},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			class, matched := ClassifyDrive(c.mountpoint, c.drives)
			if matched != c.wantMatched {
				t.Fatalf("matched: got %v want %v", matched, c.wantMatched)
			}
			if matched && class != c.wantClass {
				t.Errorf("class: got %v want %v", class, c.wantClass)
			}
		})
	}
}
