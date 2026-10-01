//go:build darwin

package engine

import "regexp"

func identityKey(device string) string {
	if m := containerPattern.FindStringSubmatch(device); m != nil {
		return "/dev/" + m[1]
	}
	return device
}

var containerPattern = regexp.MustCompile(`^/dev/(disk\d+)s\d+`)
