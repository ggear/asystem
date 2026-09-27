//go:build darwin

package engine

import (
	"fmt"
	"os"
	"storage/internal/config"
	"strings"
)

func Mount(cfg *config.Config) []MountResult {
	home, err := os.UserHomeDir()
	if err != nil {
		return []MountResult{{Message: fmt.Sprintf("home directory unavailable [%v]", err), Failed: true}}
	}
	var results []MountResult
	for _, share := range cfg.EstateShares() {
		index := strings.TrimPrefix(share.Mount, "/share/")
		dir := fmt.Sprintf("%s/Desktop/share/%s", home, index)
		samba := fmt.Sprintf("//GUEST:@%s/%s", share.ServedBy, share.Smb)
		if err := os.MkdirAll(dir, 0o755); err != nil {
			results = append(results, MountResult{Message: fmt.Sprintf("mkdir failed [%s] [%v]", dir, err), Failed: true})
			continue
		}
		if _, err := os.Stat(dir + "/tmp"); err == nil {
			results = append(results, MountResult{Message: fmt.Sprintf("Mount [%s] already", dir)})
			continue
		}
		_ = boundedRun("diskutil", "unmount", "force", dir)
		if boundedRun("mount_smbfs", "-o", "soft,nodatacache", samba, dir) == nil {
			results = append(results, MountResult{Message: fmt.Sprintf("Mounting [%s] ... done", samba)})
		} else {
			results = append(results, MountResult{Message: fmt.Sprintf("Mounting [%s] ... failed", samba), Failed: true})
		}
	}
	return results
}
