package engine

import (
	"slices"
	"strings"
)

type fstabEntry struct {
	Identifier string
	Mountpoint string
	FSType     string
	Options    []string
}

func parseFstab(contents string) []fstabEntry {
	var entries []fstabEntry
	for line := range strings.SplitSeq(contents, "\n") {
		line = strings.TrimSpace(line)
		if line == "" || strings.HasPrefix(line, "#") {
			continue
		}
		fields := strings.Fields(line)
		if len(fields) < 4 {
			continue
		}
		entries = append(entries, fstabEntry{
			Identifier: fields[0],
			Mountpoint: fields[1],
			FSType:     fields[2],
			Options:    strings.Split(fields[3], ","),
		})
	}
	return entries
}

func (e fstabEntry) hasOption(name string) bool {
	return slices.Contains(e.Options, name)
}

func (e fstabEntry) isCifs() bool {
	return e.FSType == "cifs"
}
