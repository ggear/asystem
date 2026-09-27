package engine

import (
	"strings"

	"github.com/shirou/gopsutil/v4/disk"
)

func HasLocalShares() bool {
	partitions, err := disk.Partitions(false)
	if err != nil {
		return false
	}
	for _, partition := range partitions {
		if strings.HasPrefix(partition.Mountpoint, "/share/") {
			return true
		}
	}
	return false
}
