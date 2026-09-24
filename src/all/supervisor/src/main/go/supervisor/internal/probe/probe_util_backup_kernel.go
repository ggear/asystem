package probe

import (
	"context"
	"regexp"
	"slices"
	"strings"
)

func kernelCursor(ctx context.Context) string {
	lines := kernelLines(ctx)
	if len(lines) == 0 {
		return ""
	}
	return lines[len(lines)-1]
}

func kernelSince(ctx context.Context, cursor string) []string {
	lines := kernelLines(ctx)
	if cursor == "" {
		return lines
	}
	for index, line := range slices.Backward(lines) {
		if line == cursor {
			return lines[index+1:]
		}
	}
	return lines
}

func kernelReplayed(lines []string) bool {
	return slices.ContainsFunc(lines, kernelReplayPattern.MatchString)
}

func kernelCorrupted(lines []string) []string {
	var paths []string
	for _, line := range lines {
		for _, match := range kernelPathPattern.FindAllStringSubmatch(line, -1) {
			path := strings.Map(func(letter rune) rune {
				if letter < ' ' {
					return -1
				}
				return letter
			}, match[1])
			if path != "" && !slices.Contains(paths, path) {
				paths = append(paths, path)
			}
		}
	}
	slices.Sort(paths)
	return paths
}

func kernelFaulted(lines []string) []string {
	var faults []string
	for _, line := range lines {
		if kernelFaultPattern.MatchString(line) {
			faults = append(faults, line)
		}
	}
	if len(faults) > kernelFaultsKept {
		faults = faults[len(faults)-kernelFaultsKept:]
	}
	return faults
}

func kernelLines(ctx context.Context) []string {
	out, code, abandoned := bounded(ctx, stageBoundedWait, "dmesg")
	if abandoned || code != 0 {
		return nil
	}
	trimmed := strings.TrimRight(out, "\n")
	if trimmed == "" {
		return nil
	}
	return strings.Split(trimmed, "\n")
}

var (
	kernelPathPattern   = regexp.MustCompile(`\(path: ([^)]+)\)`)
	kernelFaultPattern  = regexp.MustCompile(`(?i)btrfs.*(csum|checksum|unable to fixup)|usb.*(reset|disconnect)|i/o error|blk_update_request|tag#`)
	kernelReplayPattern = regexp.MustCompile(`(?i)btrfs.*(tree-log replay|has been changed)`)
)

const (
	kernelFaultsKept   = 500
	kernelCorruptNamed = 20
)
