//go:build linux

package engine

func canonicalMount(mountpoint string) string {
	return mountpoint
}
