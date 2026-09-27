//go:build linux

package engine

import (
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
			results = append(results, MountResult{Mountpoint: entry.Mountpoint, Message: fmt.Sprintf("Mount [%s] already", entry.Mountpoint)})
			continue
		}
		if entry.isCifs() {
			_ = exec.Command("ls", entry.Mountpoint).Run()
		} else {
			_ = exec.Command("mount", entry.Mountpoint).Run()
		}
		if mountActive(entry.Mountpoint) {
			results = append(results, MountResult{Mountpoint: entry.Mountpoint, Message: fmt.Sprintf("Mounting [%s] ... done", entry.Mountpoint)})
		} else {
			results = append(results, MountResult{Mountpoint: entry.Mountpoint, Message: fmt.Sprintf("Mounting [%s] ... failed", entry.Mountpoint), Failed: true})
		}
	}
	return results
}

func mountActive(mountpoint string) bool {
	output, err := exec.Command("mount").Output()
	if err != nil || !strings.Contains(string(output), " on "+mountpoint+" ") {
		return false
	}
	return exec.Command("ls", mountpoint).Run() == nil
}
