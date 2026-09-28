//go:build darwin

package engine

import (
	"os"
	"strings"
)

func canonicalMount(mountpoint string) string {
	home, err := os.UserHomeDir()
	if err != nil {
		return mountpoint
	}
	rest, ok := strings.CutPrefix(mountpoint, home+"/Desktop/share/")
	if !ok || rest == "" || strings.Contains(rest, "/") {
		return mountpoint
	}
	return "/share/" + rest
}
