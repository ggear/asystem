package probe

import (
	"archive/tar"
	"archive/zip"
	"bufio"
	"bytes"
	"compress/gzip"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"maps"
	"os"
	"path/filepath"
	"sort"
	"strings"

	"supervisor/internal/metric"
)

func judgeBackupRegression(current []backupFingerprintUnit, baseline backupManifest, baselineRun string, shrinkPercent int) backupRegressionVerdict {
	verdict := backupRegressionVerdict{verdict: metric.BackupStateSuccess}
	if baselineRun == "" {
		return verdict
	}
	have := map[string]int64{}
	for _, unit := range current {
		have[unit.name] = unit.count
	}
	var now, base int64
	absent, first := 0, ""
	for _, unit := range baseline.Fingerprint {
		base += unit.count
		count, present := have[unit.name]
		now += count
		if present {
			continue
		}
		absent++
		if first == "" {
			first = unit.name
		}
		if len(verdict.evidence) < backupEvidenceLimit {
			verdict.evidence = append(verdict.evidence, fmt.Sprintf("missing [%s] was [%d] against [%s]", unit.name, unit.count, baselineRun))
		}
	}
	var percent int64
	if base > 0 {
		percent = (base - now) * 100 / base
	}
	if absent > 0 || (shrinkPercent > 0 && percent > int64(shrinkPercent)) {
		verdict.verdict = metric.BackupStateRegressed
		suffix := ""
		if first != "" {
			suffix = fmt.Sprintf(", first [%s]", first)
		}
		verdict.evidence = append(verdict.evidence, fmt.Sprintf("regressed [%d] closed units missing against [%s], total [-%d]%% beyond [%d]%%%s", absent, baselineRun, percent, shrinkPercent, suffix))
	}
	return verdict
}

func renderBackupManifest(manifest backupManifest) string {
	quoted := func(text string) string {
		encoded, _ := json.Marshal(text)
		return string(encoded)
	}
	var out strings.Builder
	out.WriteString("{\n")
	fmt.Fprintf(&out, "  \"kind\": %s,\n", quoted(manifest.Kind))
	fmt.Fprintf(&out, "  \"parent\": %s,\n", quoted(manifest.Parent))
	fmt.Fprintf(&out, "  \"source_version\": %s,\n", quoted(manifest.SourceVersion))
	if manifest.SourceSoftware != "" {
		fmt.Fprintf(&out, "  \"source_software\": %s,\n", quoted(manifest.SourceSoftware))
	}
	fmt.Fprintf(&out, "  \"verdict\": %s,\n", quoted(manifest.Verdict))
	fmt.Fprintf(&out, "  \"accepted\": %t,\n", manifest.Accepted)
	fmt.Fprintf(&out, "  \"baseline\": %s,\n", quoted(manifest.Baseline))
	out.WriteString("  \"evidence\": [\n")
	for index, line := range manifest.Evidence {
		if index > 0 {
			out.WriteString(",\n")
		}
		fmt.Fprintf(&out, "    %s", quoted(line))
	}
	if len(manifest.Evidence) > 0 {
		out.WriteString("\n")
	}
	out.WriteString("  ],\n  \"fingerprint\": {\n")
	for index, unit := range manifest.Fingerprint {
		if index > 0 {
			out.WriteString(",\n")
		}
		fmt.Fprintf(&out, "    %s: %d", quoted(unit.name), unit.count)
	}
	if len(manifest.Fingerprint) > 0 {
		out.WriteString("\n")
	}
	out.WriteString("  }\n}\n")
	return out.String()
}

func writeBackupManifest(root, run string, manifest backupManifest) error {
	path := backupManifestPath(root, run)
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		return err
	}
	if err := os.WriteFile(path+".tmp", []byte(renderBackupManifest(manifest)), 0o644); err != nil {
		return err
	}
	return os.Rename(path+".tmp", path)
}

func readBackupManifest(root, run string) (backupManifest, bool) {
	data, err := os.ReadFile(backupManifestPath(root, run))
	if err != nil {
		return backupManifest{}, false
	}
	var decoded struct {
		Kind           string           `json:"kind"`
		Parent         string           `json:"parent"`
		SourceVersion  string           `json:"source_version"`
		SourceSoftware string           `json:"source_software"`
		Verdict        string           `json:"verdict"`
		Accepted       bool             `json:"accepted"`
		Baseline       string           `json:"baseline"`
		Evidence       []string         `json:"evidence"`
		Fingerprint    map[string]int64 `json:"fingerprint"`
	}
	if json.Unmarshal(data, &decoded) != nil {
		return backupManifest{}, false
	}
	return backupManifest{
		Kind: decoded.Kind, Parent: decoded.Parent, SourceVersion: decoded.SourceVersion, SourceSoftware: decoded.SourceSoftware, Verdict: decoded.Verdict,
		Accepted: decoded.Accepted, Baseline: decoded.Baseline, Evidence: decoded.Evidence, Fingerprint: sortBackupFingerprint(decoded.Fingerprint),
	}, true
}

func parseBackupFingerprint(text string) []backupFingerprintUnit {
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
	return sortBackupFingerprint(counts)
}

func fingerprintBackupArtefact(path string, includes []string) ([]backupFingerprintUnit, error) {
	switch {
	case strings.HasSuffix(path, ".sql.gz"):
		return fingerprintSQL(path)
	case strings.HasSuffix(path, ".tar.gz"):
		return fingerprintTar(path, includes)
	case strings.HasSuffix(path, ".zip"):
		return fingerprintZip(path)
	}
	return nil, nil
}

func fingerprintTar(path string, includes []string) ([]backupFingerprintUnit, error) {
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
		unit, _, _ := strings.Cut(name, "/")
		for _, include := range includes {
			if include != "" && (name == include || strings.HasPrefix(name, include+"/")) {
				unit = include
				break
			}
		}
		counts[unit] += header.Size
	}
	return sortBackupFingerprint(counts), nil
}

func fingerprintZip(path string) ([]backupFingerprintUnit, error) {
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
	return sortBackupFingerprint(counts), nil
}

func fingerprintSQL(path string) ([]backupFingerprintUnit, error) {
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
	wholeLine := func() (string, error) {
		var line []byte
		for {
			chunk, isPrefix, readErr := reader.ReadLine()
			line = append(line, chunk...)
			if readErr != nil || !isPrefix {
				return string(line), readErr
			}
		}
	}
	rows, sizes := map[string]int64{}, map[string]int64{}
	database, current, unit, inCopy := "", "", "", false
	for {
		line, readErr := wholeLine()
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
				sizes[current] += int64(len(line)) + 1
			}
		}
		if readErr != nil {
			if readErr == io.EOF {
				break
			}
			return nil, readErr
		}
	}
	maps.Copy(rows, sizes)
	return sortBackupFingerprint(rows), nil
}

func sortBackupFingerprint(counts map[string]int64) []backupFingerprintUnit {
	units := make([]backupFingerprintUnit, 0, len(counts))
	for name, count := range counts {
		units = append(units, backupFingerprintUnit{name: name, count: count})
	}
	sort.Slice(units, func(left, right int) bool {
		return fmt.Sprintf("%s %d", units[left].name, units[left].count) < fmt.Sprintf("%s %d", units[right].name, units[right].count)
	})
	return units
}

func backupManifestPath(root, run string) string {
	return filepath.Join(root, run, treeMetaDirectory, treeManifestLeaf)
}

type backupManifest struct {
	Kind           string
	Parent         string
	SourceVersion  string
	SourceSoftware string
	Verdict        string
	Accepted       bool
	Baseline       string
	Evidence       []string
	Fingerprint    []backupFingerprintUnit
}

type backupFingerprintUnit struct {
	name  string
	count int64
}

type backupRegressionVerdict struct {
	verdict  string
	evidence []string
}

func backupCompatible(point backupManifest, software string) bool {
	return point.SourceSoftware != "" && point.SourceSoftware == software
}

func versionedModule(ctx context.Context, hooks moduleHooks, stderr io.Writer, version string) string {
	declared, _ := hooks.command(ctx, "declare", "-F", moduleHookVersioned).Output()
	if !strings.Contains(string(declared), moduleHookVersioned) {
		return version
	}
	versionCtx, cancel := context.WithTimeout(ctx, moduleToolWait)
	defer cancel()
	command := hooks.command(versionCtx, moduleHookVersioned)
	var output bytes.Buffer
	command.Stdout, command.Stderr = &output, stderr
	err := command.Run()
	software := strings.TrimSpace(output.String())
	if err != nil || software == "" {
		fmt.Fprintf(stderr, "Backup hook [%s] gave no software version [%v], falling back to the module version\n", moduleHookVersioned, err)
		return version
	}
	return strings.SplitN(software, "\n", 2)[0]
}

const backupEvidenceLimit = 20
