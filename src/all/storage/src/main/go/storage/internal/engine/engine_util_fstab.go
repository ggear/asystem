package engine

import "strings"

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
		entries = append(entries, fstabEntry{Mountpoint: fields[1], FSType: fields[2]})
	}
	return entries
}

type fstabEntry struct {
	Mountpoint string
	FSType     string
}
