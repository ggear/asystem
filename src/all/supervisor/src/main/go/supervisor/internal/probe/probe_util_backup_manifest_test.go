package probe

import (
	"archive/tar"
	"archive/zip"
	"bytes"
	"compress/gzip"
	"context"
	"fmt"
	"os"
	"path/filepath"
	"slices"
	"testing"

	"supervisor/internal/metric"
)

func TestProbeUtilBackupManifest_Render(t *testing.T) {
	tests := []struct {
		name     string
		manifest backupManifest
		expected string
	}{
		{
			"empty_evidence_and_units",
			backupManifest{Kind: "full", Verdict: "success", SourceVersion: "10.200.1"},
			"{\n  \"kind\": \"full\",\n  \"parent\": \"\",\n  \"source_version\": \"10.200.1\",\n  \"verdict\": \"success\",\n  \"accepted\": false,\n  \"baseline\": \"\",\n  \"evidence\": [\n  ],\n  \"fingerprint\": {\n  }\n}\n",
		},
		{
			"software_recorded",
			backupManifest{Kind: "full", Verdict: "success", SourceVersion: "10.200.1", SourceSoftware: "18-2.30.2"},
			"{\n  \"kind\": \"full\",\n  \"parent\": \"\",\n  \"source_version\": \"10.200.1\",\n  \"source_software\": \"18-2.30.2\",\n  \"verdict\": \"success\",\n  \"accepted\": false,\n  \"baseline\": \"\",\n  \"evidence\": [\n  ],\n  \"fingerprint\": {\n  }\n}\n",
		},
		{
			"evidence_and_units_escaped",
			backupManifest{
				Kind: "delta", Parent: "p", Verdict: "regressed", Baseline: "b", Evidence: []string{`a "q"`, "b"},
				Fingerprint: []backupFingerprintUnit{{`x\y`, 1}, {"z", 2}},
			},
			"{\n  \"kind\": \"delta\",\n  \"parent\": \"p\",\n  \"source_version\": \"\",\n  \"verdict\": \"regressed\",\n  \"accepted\": false,\n  \"baseline\": \"b\",\n  \"evidence\": [\n    \"a \\\"q\\\"\",\n    \"b\"\n  ],\n  \"fingerprint\": {\n    \"x\\\\y\": 1,\n    \"z\": 2\n  }\n}\n",
		},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			if actual := renderBackupManifest(testCase.manifest); actual != testCase.expected {
				t.Fatalf("renderBackupManifest: got %q want %q", actual, testCase.expected)
			}
		})
	}
}

func TestProbeUtilBackupManifest_JudgeRegression(t *testing.T) {
	baseline := backupManifest{Fingerprint: []backupFingerprintUnit{{"a", 100}, {"b", 100}}}
	tests := []struct {
		name             string
		current          []backupFingerprintUnit
		baselineRun      string
		shrink           int
		expectedVerdict  string
		expectedEvidence int
	}{
		{"no_baseline", nil, "", 20, metric.BackupStateSuccess, 0},
		{"unchanged", []backupFingerprintUnit{{"a", 100}, {"b", 100}}, "r", 20, metric.BackupStateSuccess, 0},
		{"grown", []backupFingerprintUnit{{"a", 300}, {"b", 100}}, "r", 20, metric.BackupStateSuccess, 0},
		{"shrink_within_threshold", []backupFingerprintUnit{{"a", 100}, {"b", 81}}, "r", 20, metric.BackupStateSuccess, 0},
		{"shrink_beyond_threshold", []backupFingerprintUnit{{"a", 100}, {"b", 50}}, "r", 20, metric.BackupStateRegressed, 1},
		{"shrink_guard_disabled", []backupFingerprintUnit{{"a", 100}, {"b", 1}}, "r", 0, metric.BackupStateSuccess, 0},
		{"unit_missing", []backupFingerprintUnit{{"a", 100}}, "r", 0, metric.BackupStateRegressed, 2},
		{"everything_missing", nil, "r", 20, metric.BackupStateRegressed, 3},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			actual := judgeBackupRegression(testCase.current, baseline, testCase.baselineRun, testCase.shrink)
			if actual.verdict != testCase.expectedVerdict || len(actual.evidence) != testCase.expectedEvidence {
				t.Fatalf("judgeBackupRegression: got %v want verdict [%s] evidence [%d]", actual, testCase.expectedVerdict, testCase.expectedEvidence)
			}
		})
	}
}

func TestProbeUtilBackupManifest_FingerprintArtefacts(t *testing.T) {
	dir := t.TempDir()
	tarball := filepath.Join(dir, "files.tar.gz")
	writeTestTarball(t, tarball, map[string]string{"data/bank/a.csv": "12345", "data/bank/b.csv": "123", "data/history.json": "12", "loose/x": "1", "top.txt": "1234"})
	zipped := filepath.Join(dir, "files.zip")
	writeTestZip(t, zipped, map[string]string{"one.json": "123", "two.json": "12"})
	dump := filepath.Join(dir, "dump.sql.gz")
	writeTestGzip(t, dump, "\\connect hass\n\nCOPY public.states (a, b) FROM stdin;\n1\t2\n3\t4\n\\.\nCOPY public.empty (a) FROM stdin;\n\\.\n-- Current Database: `mysql`\nCREATE TABLE a;\nINSERT 1;\n")
	tests := []struct {
		name          string
		path          string
		includes      []string
		expected      string
		expectedError bool
	}{
		{"tarball_includes_and_first_component", tarball, []string{"data/bank", "data/history.json"}, "data/bank 8\ndata/history.json 2\nloose 1\ntop.txt 4\n", false},
		{"tarball_without_includes_groups_by_first_component", tarball, nil, "data 10\nloose 1\ntop.txt 4\n", false},
		{"zip_bytes_per_entry", zipped, nil, "one.json 3\ntwo.json 2\n", false},
		{"sql_dump_rows_and_bytes", dump, nil, "hass.public.empty 0\nhass.public.states 2\nmysql 26\n", false},
		{"unknown_extension", filepath.Join(dir, "x.bin"), nil, "", false},
		{"missing_tarball", filepath.Join(dir, "gone.tar.gz"), nil, "", true},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			units, err := fingerprintBackupArtefact(testCase.path, testCase.includes)
			if (err != nil) != testCase.expectedError {
				t.Fatalf("fingerprintBackupArtefact: got error %v want error %t", err, testCase.expectedError)
			}
			if actual := fingerprintText(units); actual != testCase.expected {
				t.Fatalf("fingerprintBackupArtefact: got %q want %q", actual, testCase.expected)
			}
		})
	}
}

func TestProbeUtilBackupManifest_ParseFingerprint(t *testing.T) {
	tests := []struct {
		name     string
		text     string
		expected string
	}{
		{"sorted_and_trimmed", "b/2026-01-01 5\n\na/2026-01-01 7\n", "a/2026-01-01 7\nb/2026-01-01 5\n"},
		{"unit_with_spaces", "my unit 4\n", "my unit 4\n"},
		{"garbage_dropped", "nonsense\nx notanumber\n", ""},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			if actual := fingerprintText(parseBackupFingerprint(testCase.text)); actual != testCase.expected {
				t.Fatalf("parseBackupFingerprint: got %q want %q", actual, testCase.expected)
			}
		})
	}
}

func TestProbeUtilBackupManifest_ReadBackupManifest(t *testing.T) {
	const run = "2026-11-01_01-00-00"
	tests := []struct {
		name             string
		manifest         *string
		expectedFound    bool
		expectedVerdict  string
		expectedEvidence []string
	}{
		{name: "no_manifest_carries_no_verdict"},
		{name: "unreadable_manifest_carries_no_verdict", manifest: new("{")},
		{name: "regressed_with_evidence", manifest: new(`{"verdict":"regressed","evidence":["first","second"]}`), expectedFound: true, expectedVerdict: metric.BackupStateRegressed, expectedEvidence: []string{"first", "second"}},
		{name: "accepted_verdict_is_passed_through", manifest: new(`{"verdict":"accepted"}`), expectedFound: true, expectedVerdict: "accepted"},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			root := t.TempDir()
			if testCase.manifest != nil {
				path := backupManifestPath(root, run)
				if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
					t.Fatalf("mkdir: %v", err)
				}
				if err := os.WriteFile(path, []byte(*testCase.manifest), 0o644); err != nil {
					t.Fatalf("write manifest: %v", err)
				}
			}
			manifest, found := readBackupManifest(root, run)
			if found != testCase.expectedFound || manifest.Verdict != testCase.expectedVerdict || !slices.Equal(manifest.Evidence, testCase.expectedEvidence) {
				t.Errorf("readBackupManifest() = (%q, %v, %t), want (%q, %v, %t)", manifest.Verdict, manifest.Evidence, found, testCase.expectedVerdict, testCase.expectedEvidence, testCase.expectedFound)
			}
		})
	}
}

func TestProbeUtilBackupManifest_RealManifests(t *testing.T) {
	base := os.Getenv("BACKUP_REAL_FIXTURES")
	if base == "" {
		t.Skip("BACKUP_REAL_FIXTURES not set")
	}
	includes := map[string][]string{
		"letsencrypt":   {"letsencrypt/accounts", "letsencrypt/archive", "letsencrypt/live", "letsencrypt/renewal"},
		"wrangle":       {"data/bank", "data/history_adhoc.json", "data/history_daily.json", "data/history_raw.json"},
		"homeassistant": {".storage", "blueprints", "custom_templates"},
	}
	for _, module := range []string{"letsencrypt", "zigbee2mqtt", "homeassistant", "mariadb", "wrangle", "postgres"} {
		t.Run(module, func(t *testing.T) {
			dir := filepath.Join(base, module)
			expected, err := os.ReadFile(filepath.Join(dir, treeMetaDirectory, treeManifestLeaf))
			if err != nil {
				t.Fatal(err)
			}
			entries, _ := os.ReadDir(dir)
			var artefact string
			for _, entry := range entries {
				if !entry.IsDir() {
					artefact = filepath.Join(dir, entry.Name())
				}
			}
			units, err := fingerprintBackupArtefact(artefact, includes[module])
			if err != nil {
				t.Fatal(err)
			}
			recorded, _ := readBackupManifest(base, module)
			recorded.Fingerprint = units
			if actual := renderBackupManifest(recorded); actual != string(expected) {
				t.Fatalf("manifest differs from the bash-written one\nwant:\n%s\ngot:\n%s", expected, actual)
			}
		})
	}
}

func fingerprintText(units []backupFingerprintUnit) string {
	var text string
	for _, unit := range units {
		text += fmt.Sprintf("%s %d\n", unit.name, unit.count)
	}
	return text
}

func plantBackupManifest(t *testing.T, root, run string, manifest backupManifest) {
	t.Helper()
	path := backupManifestPath(root, run)
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(path, []byte(renderBackupManifest(manifest)), 0o644); err != nil {
		t.Fatal(err)
	}
}

func writeTestGzip(t *testing.T, path, content string) {
	t.Helper()
	var buffer bytes.Buffer
	writer := gzip.NewWriter(&buffer)
	_, _ = writer.Write([]byte(content))
	_ = writer.Close()
	if err := os.WriteFile(path, buffer.Bytes(), 0o644); err != nil {
		t.Fatal(err)
	}
}

func writeTestTarball(t *testing.T, path string, files map[string]string) {
	t.Helper()
	var buffer bytes.Buffer
	zipped := gzip.NewWriter(&buffer)
	archive := tar.NewWriter(zipped)
	for name, content := range files {
		_ = archive.WriteHeader(&tar.Header{Name: name, Mode: 0o644, Size: int64(len(content)), Typeflag: tar.TypeReg})
		_, _ = archive.Write([]byte(content))
	}
	_ = archive.WriteHeader(&tar.Header{Name: "data/", Mode: 0o755, Typeflag: tar.TypeDir})
	_ = archive.Close()
	_ = zipped.Close()
	if err := os.WriteFile(path, buffer.Bytes(), 0o644); err != nil {
		t.Fatal(err)
	}
}

func writeTestZip(t *testing.T, path string, files map[string]string) {
	t.Helper()
	var buffer bytes.Buffer
	archive := zip.NewWriter(&buffer)
	for name, content := range files {
		writer, _ := archive.Create(name)
		_, _ = writer.Write([]byte(content))
	}
	_ = archive.Close()
	if err := os.WriteFile(path, buffer.Bytes(), 0o644); err != nil {
		t.Fatal(err)
	}
}

func TestProbeUtilBackupManifest_VersionedModule(t *testing.T) {
	tests := []struct {
		name     string
		script   string
		expected string
	}{
		{"the hook output is recorded", "backup_versioned() { printf '18-2.30\\nextra\\n'; }", "18-2.30"},
		{"no hook falls back to the version", ":", "9.9"},
		{"an empty hook falls back to the version", "backup_versioned() { :; }", "9.9"},
		{"a failing hook falls back to the version", "backup_versioned() { echo 18; return 1; }", "9.9"},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			script := filepath.Join(t.TempDir(), "backup.sh")
			if err := os.WriteFile(script, []byte(test.script+"\n"), 0o644); err != nil {
				t.Fatal(err)
			}
			var stderr bytes.Buffer
			if actual := versionedModule(context.Background(), moduleHooks{script: script}, &stderr, "9.9"); actual != test.expected {
				t.Errorf("software: got [%s] want [%s]", actual, test.expected)
			}
		})
	}
}

func TestProbeUtilBackupManifest_RenderRoundTripsAwkwardText(t *testing.T) {
	tests := []struct {
		name     string
		manifest backupManifest
	}{
		{"newlines and tabs in evidence", backupManifest{Kind: "full", Verdict: metric.BackupStateRegressed, Evidence: []string{"missing [a\nb] was [1]\tagainst [x]"}}},
		{"quotes and backslashes in a unit name", backupManifest{Kind: "full", Verdict: metric.BackupStateSuccess, Fingerprint: []backupFingerprintUnit{{name: `dir\"odd"`, count: 3}}}},
		{"unicode and control characters", backupManifest{Kind: "delta", Parent: "p", Verdict: metric.BackupStateSuccess, SourceSoftware: "18-2.30 x", Fingerprint: []backupFingerprintUnit{{name: "café\x01", count: 9}}}},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			root := t.TempDir()
			if err := writeBackupManifest(root, "2026-11-01_01-00-00", testCase.manifest); err != nil {
				t.Fatal(err)
			}
			read, found := readBackupManifest(root, "2026-11-01_01-00-00")
			if !found || read.Kind != testCase.manifest.Kind || read.SourceSoftware != testCase.manifest.SourceSoftware ||
				!slices.Equal(read.Evidence, testCase.manifest.Evidence) || !slices.Equal(read.Fingerprint, testCase.manifest.Fingerprint) {
				t.Errorf("round trip: got [%+v] found [%t] want [%+v]", read, found, testCase.manifest)
			}
		})
	}
}
