//go:build darwin

package engine

import (
	"os"
	"regexp"
	"strings"
)

func canonicalMount(mountpoint string) string {
	home, err := os.UserHomeDir()
	if err != nil {
		return mountpoint
	}
	rest, ok := strings.CutPrefix(mountpoint, home+"/Desktop"+shareMount+"/")
	if !ok || rest == "" || strings.Contains(rest, "/") {
		return mountpoint
	}
	return shareNamespace + rest
}

func identityKey(device string) string {
	if match := containerPattern.FindStringSubmatch(device); match != nil {
		return "/dev/" + match[1]
	}
	return device
}

var containerPattern = regexp.MustCompile(`^/dev/(disk\d+)s\d+`)
