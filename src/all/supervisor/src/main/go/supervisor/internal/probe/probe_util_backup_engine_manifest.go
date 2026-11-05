package probe

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strings"

	"supervisor/internal/metric"
)

type backupManifest struct {
	Kind          string
	Parent        string
	SourceVersion string
	Verdict       string
	Accepted      bool
	Baseline      string
	Evidence      []string
	Fingerprint   []fingerprintUnit
}

type fingerprintUnit struct {
	name  string
	count int64
}

func renderBackupManifest(manifest backupManifest) string {
	var out strings.Builder
	out.WriteString("{\n")
	fmt.Fprintf(&out, "  \"kind\": \"%s\",\n", manifest.Kind)
	fmt.Fprintf(&out, "  \"parent\": \"%s\",\n", manifest.Parent)
	fmt.Fprintf(&out, "  \"source_version\": \"%s\",\n", manifestText(manifest.SourceVersion))
	fmt.Fprintf(&out, "  \"verdict\": \"%s\",\n", manifest.Verdict)
	fmt.Fprintf(&out, "  \"accepted\": %t,\n", manifest.Accepted)
	fmt.Fprintf(&out, "  \"baseline\": \"%s\",\n", manifest.Baseline)
	out.WriteString("  \"evidence\": [\n")
	for index, line := range manifest.Evidence {
		if index > 0 {
			out.WriteString(",\n")
		}
		fmt.Fprintf(&out, "    \"%s\"", manifestText(line))
	}
	if len(manifest.Evidence) > 0 {
		out.WriteString("\n")
	}
	out.WriteString("  ],\n  \"fingerprint\": {\n")
	for index, unit := range manifest.Fingerprint {
		if index > 0 {
			out.WriteString(",\n")
		}
		fmt.Fprintf(&out, "    \"%s\": %d", manifestText(unit.name), unit.count)
	}
	if len(manifest.Fingerprint) > 0 {
		out.WriteString("\n")
	}
	out.WriteString("  }\n}\n")
	return out.String()
}

func manifestText(text string) string {
	return strings.ReplaceAll(strings.ReplaceAll(text, `\`, `\\`), `"`, `\"`)
}

func sortedFingerprint(counts map[string]int64) []fingerprintUnit {
	units := make([]fingerprintUnit, 0, len(counts))
	for name, count := range counts {
		units = append(units, fingerprintUnit{name: name, count: count})
	}
	sort.Slice(units, func(left, right int) bool {
		return fmt.Sprintf("%s %d", units[left].name, units[left].count) < fmt.Sprintf("%s %d", units[right].name, units[right].count)
	})
	return units
}

func manifestPath(root, run string) string {
	return filepath.Join(root, run, treeMetaDirectory, treeManifestLeaf)
}

func readBackupManifest(root, run string) (backupManifest, bool) {
	data, err := os.ReadFile(manifestPath(root, run))
	if err != nil {
		return backupManifest{}, false
	}
	var decoded struct {
		Kind          string           `json:"kind"`
		Parent        string           `json:"parent"`
		SourceVersion string           `json:"source_version"`
		Verdict       string           `json:"verdict"`
		Accepted      bool             `json:"accepted"`
		Baseline      string           `json:"baseline"`
		Evidence      []string         `json:"evidence"`
		Fingerprint   map[string]int64 `json:"fingerprint"`
	}
	if json.Unmarshal(data, &decoded) != nil {
		return backupManifest{}, false
	}
	return backupManifest{
		Kind: decoded.Kind, Parent: decoded.Parent, SourceVersion: decoded.SourceVersion, Verdict: decoded.Verdict,
		Accepted: decoded.Accepted, Baseline: decoded.Baseline, Evidence: decoded.Evidence, Fingerprint: sortedFingerprint(decoded.Fingerprint),
	}, true
}

func writeBackupManifest(root, run string, manifest backupManifest) error {
	path := manifestPath(root, run)
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		return err
	}
	if err := os.WriteFile(path+".tmp", []byte(renderBackupManifest(manifest)), 0o644); err != nil {
		return err
	}
	return os.Rename(path+".tmp", path)
}

func acceptBackupRun(root, run string) error {
	path := manifestPath(root, run)
	data, err := os.ReadFile(path)
	if err != nil {
		return fmt.Errorf("no manifest for run [%s] under [%s]", run, root)
	}
	lines := strings.Split(string(data), "\n")
	for index, line := range lines {
		switch {
		case strings.HasPrefix(line, `  "verdict": "`) && strings.HasSuffix(line, `",`):
			lines[index] = fmt.Sprintf(`  "verdict": "%s",`, metric.BackupStateSuccess)
		case line == `  "accepted": false,`:
			lines[index] = `  "accepted": true,`
		}
	}
	if err := os.WriteFile(path+".tmp", []byte(strings.Join(lines, "\n")), 0o644); err != nil {
		return err
	}
	return os.Rename(path+".tmp", path)
}
