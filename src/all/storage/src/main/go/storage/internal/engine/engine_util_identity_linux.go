//go:build linux

package engine

func identityKey(device string) string {
	return device
}
