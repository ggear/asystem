package probe

import (
	"archive/tar"
	"archive/zip"
	"bytes"
	"compress/gzip"
	"context"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"supervisor/internal/metric"
)

func TestBackupEngineManifest_Render(t *testing.T) {
	tests := []struct {
		name     string
		manifest backupManifest
		expected string
	}{
		{
			"happy_empty_evidence_and_units",
			backupManifest{Kind: "full", Verdict: "success", SourceVersion: "10.200.1"},
			"{\n  \"kind\": \"full\",\n  \"parent\": \"\",\n  \"source_version\": \"10.200.1\",\n  \"verdict\": \"success\",\n  \"accepted\": false,\n  \"baseline\": \"\",\n  \"evidence\": [\n  ],\n  \"fingerprint\": {\n  }\n}\n",
		},
		{
			"happy_evidence_and_units_escaped",
			backupManifest{
				Kind: "delta", Parent: "p", Verdict: "regressed", Baseline: "b", Evidence: []string{`a "q"`, "b"},
				Fingerprint: []fingerprintUnit{{`x\y`, 1}, {"z", 2}},
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

func TestBackupEngineManifest_Accept(t *testing.T) {
	root := t.TempDir()
	writeManifest := func(manifest backupManifest) {
		t.Helper()
		if err := writeBackupManifest(root, "2026-11-01_01-00-00", manifest); err != nil {
			t.Fatal(err)
		}
	}
	tests := []struct {
		name          string
		run           string
		expectedState string
		expectedError bool
	}{
		{"happy_regressed_becomes_success", "2026-11-01_01-00-00", metric.BackupStateSuccess, false},
		{"sad_no_manifest", "2026-11-02_01-00-00", "", true},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			writeManifest(backupManifest{Kind: "full", Verdict: metric.BackupStateRegressed, Evidence: []string{"gone"}})
			err := acceptBackupRun(root, testCase.run)
			if (err != nil) != testCase.expectedError {
				t.Fatalf("acceptBackupRun: got error %v want error %t", err, testCase.expectedError)
			}
			if testCase.expectedError {
				return
			}
			manifest, _ := readBackupManifest(root, testCase.run)
			if manifest.Verdict != testCase.expectedState || !manifest.Accepted {
				t.Fatalf("acceptBackupRun: got verdict [%s] accepted [%t] want [%s] true", manifest.Verdict, manifest.Accepted, testCase.expectedState)
			}
		})
	}
}

func TestBackupEngineGuard_Regression(t *testing.T) {
	baseline := backupManifest{Fingerprint: []fingerprintUnit{{"a", 100}, {"b", 100}}}
	tests := []struct {
		name             string
		current          []fingerprintUnit
		baselineRun      string
		shrink           int
		expectedVerdict  string
		expectedEvidence int
	}{
		{"happy_no_baseline", nil, "", 20, metric.BackupStateSuccess, 0},
		{"happy_unchanged", []fingerprintUnit{{"a", 100}, {"b", 100}}, "r", 20, metric.BackupStateSuccess, 0},
		{"happy_grown", []fingerprintUnit{{"a", 300}, {"b", 100}}, "r", 20, metric.BackupStateSuccess, 0},
		{"happy_shrink_within_threshold", []fingerprintUnit{{"a", 100}, {"b", 81}}, "r", 20, metric.BackupStateSuccess, 0},
		{"sad_shrink_beyond_threshold", []fingerprintUnit{{"a", 100}, {"b", 50}}, "r", 20, metric.BackupStateRegressed, 1},
		{"happy_shrink_guard_disabled", []fingerprintUnit{{"a", 100}, {"b", 1}}, "r", 0, metric.BackupStateSuccess, 0},
		{"sad_unit_missing", []fingerprintUnit{{"a", 100}}, "r", 0, metric.BackupStateRegressed, 2},
		{"sad_everything_missing", nil, "r", 20, metric.BackupStateRegressed, 3},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			actual := backupRegression(testCase.current, baseline, testCase.baselineRun, testCase.shrink)
			if actual.verdict != testCase.expectedVerdict || len(actual.evidence) != testCase.expectedEvidence {
				t.Fatalf("backupRegression: got %v want verdict [%s] evidence [%d]", actual, testCase.expectedVerdict, testCase.expectedEvidence)
			}
		})
	}
}

func TestBackupEngineGuard_Baseline(t *testing.T) {
	root := t.TempDir()
	for run, verdict := range map[string]string{"2026-11-01_01-00-00": metric.BackupStateSuccess, "2026-11-02_01-00-00": metric.BackupStateRegressed, "2026-11-03_01-00-00": metric.BackupStateSuccess} {
		if err := writeBackupManifest(root, run, backupManifest{Kind: "full", Verdict: verdict, Fingerprint: []fingerprintUnit{{"a", 1}}}); err != nil {
			t.Fatal(err)
		}
	}
	if err := writeBackupManifest(root, "2026-11-04_01-00-00", backupManifest{Kind: "full", Verdict: metric.BackupStateSuccess}); err != nil {
		t.Fatal(err)
	}
	tests := []struct {
		name     string
		run      string
		expected string
	}{
		{"happy_newest_earlier_success_with_units", "2026-11-05_01-00-00", "2026-11-03_01-00-00"},
		{"happy_skips_regressed", "2026-11-03_01-00-00", "2026-11-01_01-00-00"},
		{"happy_none_before", "2026-11-01_01-00-00", ""},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			if actual := backupBaseline(root, testCase.run); actual != testCase.expected {
				t.Fatalf("backupBaseline: got [%s] want [%s]", actual, testCase.expected)
			}
		})
	}
}

func TestBackupEngineFingerprint_Archives(t *testing.T) {
	dir := t.TempDir()
	tarball := filepath.Join(dir, "files.tar.gz")
	writeTarball(t, tarball, map[string]string{"data/bank/a.csv": "12345", "data/bank/b.csv": "123", "data/history.json": "12", "loose/x": "1", "top.txt": "1234"})
	zipped := filepath.Join(dir, "files.zip")
	writeZip(t, zipped, map[string]string{"one.json": "123", "two.json": "12"})
	dump := filepath.Join(dir, "dump.sql.gz")
	writeGzip(t, dump, "\\connect hass\n\nCOPY public.states (a, b) FROM stdin;\n1\t2\n3\t4\n\\.\nCOPY public.empty (a) FROM stdin;\n\\.\n-- Current Database: `mysql`\nCREATE TABLE a;\nINSERT 1;\n")
	tests := []struct {
		name          string
		path          string
		includes      []string
		expected      string
		expectedError bool
	}{
		{"happy_tarball_includes_and_first_component", tarball, []string{"data/bank", "data/history.json"}, "data/bank 8\ndata/history.json 2\nloose 1\ntop.txt 4\n", false},
		{"happy_tarball_without_includes_groups_by_first_component", tarball, nil, "data 10\nloose 1\ntop.txt 4\n", false},
		{"happy_zip_bytes_per_entry", zipped, nil, "one.json 3\ntwo.json 2\n", false},
		{"happy_sql_dump_rows_and_bytes", dump, nil, "hass.public.empty 0\nhass.public.states 2\nmysql 26\n", false},
		{"happy_unknown_extension", filepath.Join(dir, "x.bin"), nil, "", false},
		{"sad_missing_tarball", filepath.Join(dir, "gone.tar.gz"), nil, "", true},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			units, err := fingerprintBackupArchive(testCase.path, testCase.includes)
			if (err != nil) != testCase.expectedError {
				t.Fatalf("fingerprintBackupArchive: got error %v want error %t", err, testCase.expectedError)
			}
			if actual := fingerprintLines(units); actual != testCase.expected {
				t.Fatalf("fingerprintBackupArchive: got %q want %q", actual, testCase.expected)
			}
		})
	}
}

func TestBackupEngineFingerprint_ParseLines(t *testing.T) {
	tests := []struct {
		name     string
		text     string
		expected string
	}{
		{"happy_sorted_and_trimmed", "b/2026-01-01 5\n\na/2026-01-01 7\n", "a/2026-01-01 7\nb/2026-01-01 5\n"},
		{"happy_unit_with_spaces", "my unit 4\n", "my unit 4\n"},
		{"happy_garbage_dropped", "nonsense\nx notanumber\n", ""},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			if actual := fingerprintLines(parseFingerprintLines(testCase.text)); actual != testCase.expected {
				t.Fatalf("parseFingerprintLines: got %q want %q", actual, testCase.expected)
			}
		})
	}
}

func TestBackupEngineFiles_Unmatched(t *testing.T) {
	dir := t.TempDir()
	for _, path := range []string{"keep/a", "keep/deep/b", "skip/c", "stray.txt", "backup/old", "cache/tmp.bak-1", "nested/inner/stray"} {
		full := filepath.Join(dir, path)
		if err := os.MkdirAll(filepath.Dir(full), 0o755); err != nil {
			t.Fatal(err)
		}
		if err := os.WriteFile(full, []byte("x"), 0o644); err != nil {
			t.Fatal(err)
		}
	}
	tests := []struct {
		name     string
		includes []string
		excludes []string
		expected []string
	}{
		{"happy_everything_declared", []string{"keep", "skip", "stray.txt", "cache", "nested"}, nil, nil},
		{"happy_stray_reported", []string{"keep"}, []string{"skip"}, []string{"cache", "nested", "stray.txt"}},
		{"happy_glob_exclude", []string{"keep", "stray.txt", "nested"}, []string{"skip", "cache/*.bak-*"}, nil},
		{"happy_nested_include_covers_parent", []string{"keep", "skip", "stray.txt", "cache", "nested/inner"}, nil, nil},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			actual := backupUnmatched(dir, testCase.includes, testCase.excludes)
			if strings.Join(actual, " ") != strings.Join(testCase.expected, " ") {
				t.Fatalf("backupUnmatched: got %v want %v", actual, testCase.expected)
			}
		})
	}
}

func TestBackupEngineFiles_Target(t *testing.T) {
	source := filepath.Join(t.TempDir(), "mod", "10.1")
	root := filepath.Join(filepath.Dir(source), "backup")
	if err := os.MkdirAll(filepath.Join(root, "2026-11-01_01-00-00"), 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(root, "2026-11-01_01-00-00", "mod_at_2026-11-01_01-00-00_from_10.1_full.tar.gz"), []byte("x"), 0o644); err != nil {
		t.Fatal(err)
	}
	tests := []struct {
		name          string
		run           string
		suffix        string
		extension     string
		expected      string
		expectedError bool
	}{
		{"happy_full", "2026-11-02_01-00-00", "_full", "tar.gz", "2026-11-02_01-00-00/mod_at_2026-11-02_01-00-00_from_10.1_full.tar.gz", false},
		{"happy_delta_with_parent", "2026-11-02_01-00-00", "_delta", "tar.gz", "2026-11-02_01-00-00/mod_at_2026-11-02_01-00-00_from_10.1_delta.tar.gz", false},
		{"sad_delta_without_parent", "2026-10-31_01-00-00", "_delta", "tar.gz", "", true},
		{"sad_missing_suffix", "2026-11-02_01-00-00", "", "tar.gz", "", true},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			request := backupFilesRequest{module: "mod", source: source, run: testCase.run, state: t.TempDir()}
			actual, err := backupEngineNamed(request, testCase.suffix, testCase.extension)
			if (err != nil) != testCase.expectedError {
				t.Fatalf("backupEngineNamed: got error %v want error %t", err, testCase.expectedError)
			}
			if !testCase.expectedError && actual != filepath.Join(root, testCase.expected) {
				t.Fatalf("backupEngineNamed: got [%s] want [%s]", actual, filepath.Join(root, testCase.expected))
			}
		})
	}
}

func TestBackupEngineHooks_Defined(t *testing.T) {
	if _, err := exec.LookPath("bash"); err != nil {
		t.Skip("no bash")
	}
	script := filepath.Join(t.TempDir(), "backup.sh")
	if err := os.WriteFile(script, []byte("backup_completed() { :; }\nbackup_fingerprinted() { :; }\n"), 0o755); err != nil {
		t.Fatal(err)
	}
	actual := backupHooks{script: script}.defined(context.Background())
	expected := map[string]bool{backupHookCompleted: true, backupHookFingerprint: true}
	if len(actual) != len(expected) || !actual[backupHookCompleted] || !actual[backupHookFingerprint] || actual[backupHookPrunedStore] {
		t.Fatalf("defined: got %v want %v", actual, expected)
	}
}

func TestBackupEngineRun_Lifecycle(t *testing.T) {
	if _, err := exec.LookPath("bash"); err != nil {
		t.Skip("no bash")
	}
	script := func(dir, body string) string {
		path := filepath.Join(dir, "backup.sh")
		content := "backup_interrupted() { :; }\nbackup_completed() { echo completed >>\"" + dir + "/trail\"; }\n" + body + "\n"
		if err := os.WriteFile(path, []byte(content), 0o755); err != nil {
			t.Fatal(err)
		}
		return path
	}
	written := `backup_written() { local path="${BACKUP_STATE_DIR}/target"; local target="$(dirname "$BACKUP_SOURCE_DIR")/backup/${BACKUP_RUN_TIMESTAMP}/mod_at_${BACKUP_RUN_TIMESTAMP}_from_1.0_full.sql.gz"; mkdir -p "$(dirname "$target")"; echo "$target" >"$path"; printf '%s' "$BACKUP_PAYLOAD" | gzip >"$target.tmp"; }`
	tests := []struct {
		name             string
		body             string
		payload          string
		priorFingerprint []fingerprintUnit
		skipHours        string
		expectedCode     int
		expectedRuns     int
		expectedVerdict  string
	}{
		{"happy_first_backup_succeeds", written, "-- Current Database: `a`\nINSERT;\n", nil, "0", 0, 1, metric.BackupStateSuccess},
		{"happy_shrink_flagged_regressed", written, "-- Current Database: `a`\nI;\n", []fingerprintUnit{{"a", 1000}}, "0", 0, 2, metric.BackupStateRegressed},
		{"happy_throttled_run_is_skipped", written, "x", []fingerprintUnit{{"a", 1}}, "1000", 0, 1, ""},
		{"sad_failing_hook_leaves_no_run", `backup_written() { return 1; }`, "", nil, "0", 1, 0, ""},
		{"sad_nothing_named", `backup_written() { :; }`, "", nil, "0", 1, 0, ""},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			dir := t.TempDir()
			source := filepath.Join(dir, "mod", "1.0")
			if err := os.MkdirAll(source, 0o755); err != nil {
				t.Fatal(err)
			}
			root := filepath.Join(dir, "mod", "backup")
			if testCase.priorFingerprint != nil {
				recent := time.Now().Add(-2 * time.Hour).Format(backupTimestampFormat)
				if err := writeBackupManifest(root, recent, backupManifest{Kind: "full", Verdict: metric.BackupStateSuccess, Fingerprint: testCase.priorFingerprint}); err != nil {
					t.Fatal(err)
				}
				if err := os.WriteFile(filepath.Join(root, recent, "mod_at_"+recent+"_from_1.0_full.sql.gz"), []byte("x"), 0o644); err != nil {
					t.Fatal(err)
				}
			}
			t.Setenv("BACKUP_SOURCE_DIR", source)
			t.Setenv("BACKUP_PAYLOAD", testCase.payload)
			t.Setenv(backupLockHeldVariable, "")
			env := backupEngineEnv{module: "mod", source: source, script: script(dir, testCase.body), skipHours: mustAtoi(t, testCase.skipHours), shrink: 20, lockWait: 1, timeout: time.Minute, runStamp: time.Now().Format(backupTimestampFormat), sourceBase: "1.0"}
			var stdout, stderr bytes.Buffer
			if code := backupEngineRun(context.Background(), env, &stdout, &stderr); code != testCase.expectedCode {
				t.Fatalf("backupEngineRun: got code [%d] want [%d] stdout [%s] stderr [%s]", code, testCase.expectedCode, stdout.String(), stderr.String())
			}
			runs := backupRuns(root)
			if len(runs) != testCase.expectedRuns {
				t.Fatalf("backupEngineRun: got runs %v want [%d]", runs, testCase.expectedRuns)
			}
			if testCase.expectedVerdict == "" {
				return
			}
			manifest, found := readBackupManifest(root, runs[len(runs)-1])
			if !found || manifest.Verdict != testCase.expectedVerdict {
				t.Fatalf("backupEngineRun: got manifest %v found %t want verdict [%s]", manifest, found, testCase.expectedVerdict)
			}
		})
	}
}

func TestBackupEngineRealManifests(t *testing.T) {
	base := os.Getenv("BACKUP_REAL_FIXTURES")
	if base == "" {
		t.Skip("BACKUP_REAL_FIXTURES not set")
	}
	includes := map[string][]string{
		"letsencrypt":   {"letsencrypt/accounts", "letsencrypt/archive", "letsencrypt/live", "letsencrypt/renewal"},
		"wrangle":       {"data/bank", "data/history_adhoc.json", "data/history_daily.json", "data/history_raw.json"},
		"homeassistant": {".storage", "blueprints", "custom_templates"},
	}
	for module := range map[string]bool{"letsencrypt": true, "zigbee2mqtt": true, "homeassistant": true, "mariadb": true, "wrangle": true, "postgres": true} {
		t.Run(module, func(t *testing.T) {
			dir := filepath.Join(base, module)
			expected, err := os.ReadFile(filepath.Join(dir, ".meta", "manifest.json"))
			if err != nil {
				t.Fatal(err)
			}
			entries, _ := os.ReadDir(dir)
			var archive string
			for _, entry := range entries {
				if !entry.IsDir() {
					archive = filepath.Join(dir, entry.Name())
				}
			}
			units, err := fingerprintBackupArchive(archive, includes[module])
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

func mustAtoi(t *testing.T, text string) int {
	t.Helper()
	value := 0
	for _, digit := range text {
		value = value*10 + int(digit-'0')
	}
	return value
}

func writeGzip(t *testing.T, path, content string) {
	t.Helper()
	var buffer bytes.Buffer
	writer := gzip.NewWriter(&buffer)
	_, _ = writer.Write([]byte(content))
	_ = writer.Close()
	if err := os.WriteFile(path, buffer.Bytes(), 0o644); err != nil {
		t.Fatal(err)
	}
}

func writeTarball(t *testing.T, path string, files map[string]string) {
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

func writeZip(t *testing.T, path string, files map[string]string) {
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
