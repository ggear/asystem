package probe

import (
	"archive/tar"
	"archive/zip"
	"bufio"
	"compress/gzip"
	"fmt"
	"io"
	"maps"
	"os"
	"strings"
)

func fingerprintBackupArchive(path string, includes []string) ([]fingerprintUnit, error) {
	switch {
	case strings.HasSuffix(path, ".sql.gz"):
		return fingerprintSQLDump(path)
	case strings.HasSuffix(path, ".tar.gz"):
		return fingerprintTarball(path, includes)
	case strings.HasSuffix(path, ".zip"):
		return fingerprintZip(path)
	}
	return nil, nil
}

func fingerprintTarball(path string, includes []string) ([]fingerprintUnit, error) {
	file, err := os.Open(path)
	if err != nil {
		return nil, err
	}
	defer func() { _ = file.Close() }()
	unzipped, err := gzip.NewReader(file)
	if err != nil {
		return nil, err
	}
	reader := tar.NewReader(unzipped)
	counts := map[string]int64{}
	for {
		header, nextErr := reader.Next()
		if nextErr == io.EOF {
			break
		}
		if nextErr != nil {
			return nil, nextErr
		}
		name := strings.TrimPrefix(header.Name, "./")
		if header.Typeflag == tar.TypeDir || name == "" {
			continue
		}
		counts[tarballUnit(name, includes)] += header.Size
	}
	return sortedFingerprint(counts), nil
}

func tarballUnit(name string, includes []string) string {
	for _, include := range includes {
		if include != "" && (name == include || strings.HasPrefix(name, include+"/")) {
			return include
		}
	}
	unit, _, _ := strings.Cut(name, "/")
	return unit
}

func fingerprintZip(path string) ([]fingerprintUnit, error) {
	archive, err := zip.OpenReader(path)
	if err != nil {
		return nil, err
	}
	defer func() { _ = archive.Close() }()
	counts := map[string]int64{}
	for _, entry := range archive.File {
		if entry.Name != "" {
			counts[entry.Name] += int64(entry.UncompressedSize64)
		}
	}
	return sortedFingerprint(counts), nil
}

func fingerprintSQLDump(path string) ([]fingerprintUnit, error) {
	file, err := os.Open(path)
	if err != nil {
		return nil, err
	}
	defer func() { _ = file.Close() }()
	unzipped, err := gzip.NewReader(file)
	if err != nil {
		return nil, err
	}
	reader := bufio.NewReaderSize(unzipped, 1<<20)
	rows, bytes := map[string]int64{}, map[string]int64{}
	database, current, unit, inCopy := "", "", "", false
	for {
		line, readErr := readWholeLine(reader)
		if line != "" || readErr == nil {
			fields := strings.Fields(line)
			switch {
			case strings.HasPrefix(line, `\connect `):
				if len(fields) > 1 {
					database = strings.ReplaceAll(fields[1], `"`, "")
				}
			case strings.HasPrefix(line, "-- Current Database: "):
				if len(fields) > 3 {
					current = strings.ReplaceAll(fields[3], "`", "")
				}
			case strings.HasPrefix(line, "COPY ") && len(fields) > 1:
				unit, inCopy = database+"."+fields[1], true
				rows[unit] += 0
			case line == `\.`:
				inCopy = false
			case inCopy:
				rows[unit]++
			case current != "":
				bytes[current] += int64(len(line)) + 1
			}
		}
		if readErr != nil {
			if readErr == io.EOF {
				break
			}
			return nil, readErr
		}
	}
	maps.Copy(rows, bytes)
	return sortedFingerprint(rows), nil
}

func readWholeLine(reader *bufio.Reader) (string, error) {
	var line []byte
	for {
		chunk, isPrefix, err := reader.ReadLine()
		line = append(line, chunk...)
		if err != nil {
			return string(line), err
		}
		if !isPrefix {
			return string(line), nil
		}
	}
}

func fingerprintLines(units []fingerprintUnit) string {
	var out strings.Builder
	for _, unit := range units {
		fmt.Fprintf(&out, "%s %d\n", unit.name, unit.count)
	}
	return out.String()
}

func parseFingerprintLines(text string) []fingerprintUnit {
	counts := map[string]int64{}
	for line := range strings.SplitSeq(text, "\n") {
		cut := strings.LastIndex(line, " ")
		if cut <= 0 {
			continue
		}
		var count int64
		if _, err := fmt.Sscanf(line[cut+1:], "%d", &count); err == nil {
			counts[line[:cut]] = count
		}
	}
	return sortedFingerprint(counts)
}
