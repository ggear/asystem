//go:build darwin

package engine

import (
	"fmt"
	"os"
	"storage/internal/config"
	"strings"
)

func Mount(loaded *config.Config) []MountResult {
	home, err := os.UserHomeDir()
	if err != nil {
		return []MountResult{{Message: fmt.Sprintf("home directory unavailable [%v]", err), Failed: true}}
	}
	var results []MountResult
	for _, share := range loaded.EstateShares() {
		directory := home + "/Desktop" + shareMount + "/" + strings.TrimPrefix(share.Mount, shareNamespace)
		if boundedRun("test", "-d", directory+"/tmp") == nil {
			results = append(results, MountResult{Message: fmt.Sprintf("Share [%s] mounted already", directory)})
			continue
		}
		_ = boundedRun("diskutil", "unmount", "force", directory)
		if err := os.MkdirAll(directory, 0o755); err != nil {
			results = append(results, MountResult{Message: fmt.Sprintf("mkdir failed [%s] [%v]", directory, err), Failed: true})
			continue
		}
		samba := fmt.Sprintf("//GUEST:@%s/%s", share.ServedBy, share.SMB)
		if boundedRun("mount_smbfs", "-o", "soft,nodatacache", samba, directory) == nil {
			results = append(results, MountResult{Message: fmt.Sprintf("Share [%s] mounting ... done", directory)})
		} else {
			results = append(results, MountResult{Message: fmt.Sprintf("Share [%s] mounting ... failed", directory), Failed: true})
		}
	}
	return results
}
