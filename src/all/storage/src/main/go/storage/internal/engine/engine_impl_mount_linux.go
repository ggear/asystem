//go:build linux

package engine

import (
	"context"
	"fmt"
	"os"
	"os/exec"
	"storage/internal/config"
	"strings"
)

const liveFstabPath = "/etc/fstab"

func Mount(_ *config.Config) []MountResult {
	contents, err := os.ReadFile(liveFstabPath)
	if err != nil {
		return []MountResult{{Message: fmt.Sprintf("read fstab failed [%s] [%v]", liveFstabPath, err), Failed: true}}
	}
	var results []MountResult
	for _, entry := range parseFstab(string(contents)) {
		if !strings.HasPrefix(entry.Mountpoint, "/share/") {
			continue
		}
		if mountActive(entry.Mountpoint) {
			results = append(results, MountResult{Message: fmt.Sprintf("Share [%s] mounted already", entry.Mountpoint)})
			continue
		}
		if entry.isCifs() {
			_ = boundedRun("ls", entry.Mountpoint)
		} else {
			_ = boundedRun("mount", entry.Mountpoint)
		}
		if mountActive(entry.Mountpoint) {
			results = append(results, MountResult{Message: fmt.Sprintf("Share [%s] mounting ... done", entry.Mountpoint)})
		} else {
			results = append(results, MountResult{Message: fmt.Sprintf("Share [%s] mounting ... failed", entry.Mountpoint), Failed: true})
		}
	}
	return results
}

func mountActive(mountpoint string) bool {
	ctx, cancel := context.WithTimeout(context.Background(), mountTimeout)
	defer cancel()
	output, err := exec.CommandContext(ctx, "mount").Output()
	if err != nil || !strings.Contains(string(output), " on "+mountpoint+" ") {
		return false
	}
	return boundedRun("ls", mountpoint) == nil
}
