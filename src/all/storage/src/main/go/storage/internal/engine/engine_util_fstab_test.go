package engine

import (
	"reflect"
	"testing"
)

func TestEngineUtilFstab_ParseFstab(t *testing.T) {
	tests := []struct {
		name          string
		contents      string
		expected      []fstabEntry
		expectedError bool
	}{
		{
			name:     "a PARTLABEL entry",
			contents: "PARTLABEL=share_08 /share/10 ext4 noatime,nofail 0 2",
			expected: []fstabEntry{{Mountpoint: "/share/10", FSType: "ext4"}},
		},
		{
			name:     "a UUID entry",
			contents: "UUID=ff55f331-1d06-4a57-a65f-89e457b3a3d0 / btrfs subvol=root 0 1",
			expected: []fstabEntry{{Mountpoint: "/", FSType: "btrfs"}},
		},
		{
			name:     "a cifs source with its host and share name",
			contents: "//macmini-max/share-20 /share/20 cifs guest,nofail 0 0",
			expected: []fstabEntry{{Mountpoint: "/share/20", FSType: "cifs"}},
		},
		{
			name:     "nofail is a plain option",
			contents: "PARTLABEL=backup_06 /backup btrfs noatime,nofail 0 2",
			expected: []fstabEntry{{Mountpoint: "/backup", FSType: "btrfs"}},
		},
		{
			name:     "a comment line is skipped",
			contents: "#identifier mount type options dump pass",
			expected: nil,
		},
		{
			name:     "a short line is skipped",
			contents: "proc /proc proc",
			expected: nil,
		},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			got := parseFstab(testCase.contents)
			if !reflect.DeepEqual(got, testCase.expected) {
				t.Errorf("got %+v want %+v", got, testCase.expected)
			}
		})
	}
}
