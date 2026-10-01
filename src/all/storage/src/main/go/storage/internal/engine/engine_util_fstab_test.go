package engine

import (
	"reflect"
	"testing"
)

func TestEngineUtilFstab_ParseFstab(t *testing.T) {
	cases := []struct {
		name          string
		contents      string
		want          []fstabEntry
		expectedError bool
	}{
		{
			name:     "a PARTLABEL entry",
			contents: "PARTLABEL=share_08 /share/10 ext4 noatime,nofail 0 2",
			want:     []fstabEntry{{Identifier: "PARTLABEL=share_08", Mountpoint: "/share/10", FSType: "ext4", Options: []string{"noatime", "nofail"}}},
		},
		{
			name:     "a UUID entry",
			contents: "UUID=ff55f331-1d06-4a57-a65f-89e457b3a3d0 / btrfs subvol=root 0 1",
			want:     []fstabEntry{{Identifier: "UUID=ff55f331-1d06-4a57-a65f-89e457b3a3d0", Mountpoint: "/", FSType: "btrfs", Options: []string{"subvol=root"}}},
		},
		{
			name:     "a cifs source with its host and share name",
			contents: "//macmini-max/share-20 /share/20 cifs guest,nofail 0 0",
			want:     []fstabEntry{{Identifier: "//macmini-max/share-20", Mountpoint: "/share/20", FSType: "cifs", Options: []string{"guest", "nofail"}}},
		},
		{
			name:     "nofail is a plain option",
			contents: "PARTLABEL=backup_06 /backup btrfs noatime,nofail 0 2",
			want:     []fstabEntry{{Identifier: "PARTLABEL=backup_06", Mountpoint: "/backup", FSType: "btrfs", Options: []string{"noatime", "nofail"}}},
		},
		{
			name:     "a comment line is skipped",
			contents: "#identifier mount type options dump pass",
			want:     nil,
		},
		{
			name:     "a short line is skipped",
			contents: "proc /proc proc",
			want:     nil,
		},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			got := parseFstab(c.contents)
			if !reflect.DeepEqual(got, c.want) {
				t.Errorf("got %+v want %+v", got, c.want)
			}
		})
	}
}
