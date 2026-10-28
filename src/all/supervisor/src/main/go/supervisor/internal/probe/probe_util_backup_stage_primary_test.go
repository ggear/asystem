package probe

import (
	"fmt"
	"os"
	"path/filepath"
	"slices"
	"testing"
	"time"

	"supervisor/internal/config"
	"supervisor/internal/metric"
)

func loadedWithTimeout(t *testing.T, hours int) *config.Config {
	t.Helper()
	dir := t.TempDir()
	path := filepath.Join(dir, "config.json")
	body := fmt.Sprintf(`{"asystem":{"host":"testhost","backup":{"timeout_hours":%d}}}`, hours)
	if err := os.WriteFile(path, []byte(body), 0644); err != nil {
		t.Fatalf("write config: %v", err)
	}
	return config.Load(path)
}

func TestProbeUtilBackupStagePrimary_NewestBackupDirPicksTheLexicallyLatestEntry(t *testing.T) {
	root := t.TempDir()
	for _, name := range []string{"2025-01-01_00-00-00", "2026-09-22_01-00-00", "2024-12-31_00-00-00", "not-a-timestamp"} {
		if err := os.MkdirAll(filepath.Join(root, name), 0o755); err != nil {
			t.Fatalf("mkdir [%s]: %v", name, err)
		}
	}
	if err := os.WriteFile(filepath.Join(root, "2027-01-01_00-00-00"), []byte("not a directory"), 0o644); err != nil {
		t.Fatalf("write fixture file: %v", err)
	}
	expected := filepath.Join(root, "2026-09-22_01-00-00")
	if got := newestBackupDir(root); got != expected {
		t.Errorf("newestBackupDir() = %q, want %q", got, expected)
	}
}

func TestProbeUtilBackupStagePrimary_NewestBackupDirAgainstAnEmptyOrMissingRoot(t *testing.T) {
	if got := newestBackupDir(t.TempDir()); got != "" {
		t.Errorf("newestBackupDir() = %q, want empty against an empty root", got)
	}
	if got := newestBackupDir(filepath.Join(t.TempDir(), "missing")); got != "" {
		t.Errorf("newestBackupDir() = %q, want empty against a missing root", got)
	}
}

func TestProbeUtilBackupStagePrimary_StrandedBackups(t *testing.T) {
	tests := []struct {
		name     string
		dirs     []string
		files    []string
		enrolled []string
		expected []string
	}{
		{name: "enrolled_service_is_not_stranded", dirs: []string{"postgres/backup"}, enrolled: []string{"postgres"}},
		{name: "unenrolled_service_with_backups_is_stranded", dirs: []string{"influxdb3/backup", "letsencrypt/backup"},
			enrolled: []string{"letsencrypt"}, expected: []string{"influxdb3"}},
		{name: "supervisor_own_tree_is_never_stranded", dirs: []string{"supervisor/backup"}},
		{name: "service_without_a_backup_directory_is_ignored", dirs: []string{"grafana/latest"}},
		{name: "backup_file_rather_than_directory_is_ignored", dirs: []string{"plex"}, files: []string{"plex/backup"}},
		{name: "stranded_services_sort_by_name", dirs: []string{"zigbee2mqtt/backup", "mariadb/backup"},
			expected: []string{"mariadb", "zigbee2mqtt"}},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			home := t.TempDir()
			for _, dir := range testCase.dirs {
				if err := os.MkdirAll(filepath.Join(home, dir), 0o755); err != nil {
					t.Fatalf("mkdir [%s]: %v", dir, err)
				}
			}
			for _, file := range testCase.files {
				if err := os.WriteFile(filepath.Join(home, file), nil, 0o644); err != nil {
					t.Fatalf("write [%s]: %v", file, err)
				}
			}
			got := strandedBackups(home, testCase.enrolled)
			if fmt.Sprint(got) != fmt.Sprint(testCase.expected) {
				t.Errorf("strandedBackups() = %v, want %v", got, testCase.expected)
			}
		})
	}
	if got := strandedBackups(filepath.Join(t.TempDir(), "missing"), nil); got != nil {
		t.Errorf("strandedBackups() = %v, want nil against a missing home", got)
	}
}

func TestProbeUtilBackupStagePrimary_ParseBackupArtefact(t *testing.T) {
	tests := []struct {
		name            string
		file            string
		expectedKind    string
		expectedVersion string
	}{
		{name: "full_carries_no_version", file: "myservice_full.tar.gz", expectedKind: "full", expectedVersion: "unknown"},
		{name: "delta_version_cut_from_the_prefix", file: "myservice_2026-09-22_01-00-00_v3_delta.tar.gz", expectedKind: "delta", expectedVersion: "v3"},
		{name: "a_name_without_a_kind_suffix_is_not_the_artifact", file: "myservice_delta_from_v2.tar.gz", expectedKind: "unknown", expectedVersion: "unknown"},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			dir := filepath.Join(t.TempDir(), "2026-09-22_01-00-00")
			if err := os.MkdirAll(dir, 0o755); err != nil {
				t.Fatalf("mkdir: %v", err)
			}
			if err := os.WriteFile(filepath.Join(dir, testCase.file), []byte("x"), 0o644); err != nil {
				t.Fatalf("write artefact: %v", err)
			}
			kind, version := parseBackupArtefact("myservice", dir)
			if kind != testCase.expectedKind {
				t.Errorf("kind = %q, want %q", kind, testCase.expectedKind)
			}
			if version != testCase.expectedVersion {
				t.Errorf("version = %q, want %q", version, testCase.expectedVersion)
			}
		})
	}
}

func TestProbeUtilBackupStagePrimary_ParseBackupArtefactPicksTheLexicallyFirstFileAndIgnoresSubdirectories(t *testing.T) {
	dir := filepath.Join(t.TempDir(), "2026-09-22_01-00-00")
	if err := os.MkdirAll(filepath.Join(dir, "a-subdirectory"), 0o755); err != nil {
		t.Fatalf("mkdir subdir: %v", err)
	}
	for _, name := range []string{"z_full.tar.gz", "a_full.tar.gz"} {
		if err := os.WriteFile(filepath.Join(dir, name), []byte("x"), 0o644); err != nil {
			t.Fatalf("write [%s]: %v", name, err)
		}
	}
	kind, _ := parseBackupArtefact("myservice", dir)
	if kind != "full" {
		t.Errorf("kind = %q, want full picked from the lexicailly first file, ignoring the subdirectory", kind)
	}
}

func TestProbeUtilBackupStagePrimary_ParseBackupArtefactSkipsASidecarThatSortsFirst(t *testing.T) {
	dir := filepath.Join(t.TempDir(), "2026-09-22_01-00-00")
	if err := os.MkdirAll(dir, 0o755); err != nil {
		t.Fatalf("mkdir: %v", err)
	}
	for _, name := range []string{"drill.json", "manifest.json", "myservice_at_2026-09-22_01-00-00_from_v3_delta.tar.gz"} {
		if err := os.WriteFile(filepath.Join(dir, name), []byte("x"), 0o644); err != nil {
			t.Fatalf("write [%s]: %v", name, err)
		}
	}
	kind, version := parseBackupArtefact("myservice", dir)
	if kind != "delta" || version != "v3" {
		t.Errorf("parseBackupArtefact() = (%q, %q), want (delta, v3) read from the artifact and not a sidecar", kind, version)
	}
}

func TestProbeUtilBackupStagePrimary_ParseBackupArtefactAgainstAnEmptyDirectory(t *testing.T) {
	dir := t.TempDir()
	kind, version := parseBackupArtefact("myservice", dir)
	if kind != "unknown" || version != "unknown" {
		t.Errorf("parseBackupArtefact() = (%q, %q), want (unknown, unknown) against an empty directory", kind, version)
	}
}

func TestProbeUtilBackupStagePrimary_BackupIdentity(t *testing.T) {
	tests := []struct {
		newest   string
		expected string
	}{
		{newest: "", expected: "none"},
		{newest: "/home/asystem/plex/backup/2026-09-22_01-00-00", expected: "2026-09-22_01-00-00"},
	}
	for _, testCase := range tests {
		if got := backupIdentity(testCase.newest); got != testCase.expected {
			t.Errorf("backupIdentity(%q) = %q, want %q", testCase.newest, got, testCase.expected)
		}
	}
}

func TestProbeUtilBackupStagePrimary_ReadManifestVerdict(t *testing.T) {
	tests := []struct {
		name             string
		manifest         *string
		expectedVerdict  string
		expectedEvidence []string
	}{
		{name: "no_manifest_carries_no_verdict"},
		{name: "unreadable_manifest_carries_no_verdict", manifest: new("{")},
		{name: "regressed_with_evidence", manifest: new(`{"verdict":"regressed","evidence":["first","second"]}`), expectedVerdict: metric.BackupStateRegressed, expectedEvidence: []string{"first", "second"}},
		{name: "accepted_verdict_is_passed_through", manifest: new(`{"verdict":"accepted"}`), expectedVerdict: "accepted"},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			dir := t.TempDir()
			if testCase.manifest != nil {
				if err := os.MkdirAll(filepath.Join(dir, treeMetaDirectory), 0o755); err != nil {
					t.Fatalf("mkdir: %v", err)
				}
				if err := os.WriteFile(filepath.Join(dir, treeMetaDirectory, treeManifestLeaf), []byte(*testCase.manifest), 0o644); err != nil {
					t.Fatalf("write manifest: %v", err)
				}
			}
			verdict, evidence := readManifestVerdict(dir)
			if verdict != testCase.expectedVerdict {
				t.Errorf("verdict = %q, want %q", verdict, testCase.expectedVerdict)
			}
			if !slices.Equal(evidence, testCase.expectedEvidence) {
				t.Errorf("evidence = %v, want %v", evidence, testCase.expectedEvidence)
			}
		})
	}
}

func TestProbeUtilBackupStagePrimary_BackupOutcome(t *testing.T) {
	const previous, written = "/backup/2026-10-15_01-00-00", "/backup/2026-10-16_01-00-00"
	tests := []struct {
		name             string
		ok               bool
		previous         string
		newest           string
		expectedState    string
		expectedArtefact string
	}{
		{name: "success_writes_a_new_artefact", ok: true, previous: previous, newest: written, expectedState: metric.BackupStateSuccess, expectedArtefact: written},
		{name: "first_success_writes_the_first_artefact", ok: true, previous: "", newest: written, expectedState: metric.BackupStateSuccess, expectedArtefact: written},
		{name: "throttled_success_reuses_the_previous_artefact", ok: true, previous: previous, newest: previous, expectedState: metric.BackupStateSkipped, expectedArtefact: previous},
		{name: "failure_never_claims_the_previous_artefact", ok: false, previous: previous, newest: previous, expectedState: metric.BackupStateFailure, expectedArtefact: ""},
		{name: "failure_keeping_its_archive_reports_it", ok: false, previous: previous, newest: written, expectedState: metric.BackupStateFailure, expectedArtefact: written},
		{name: "failure_with_no_artefact_ever", ok: false, previous: "", newest: "", expectedState: metric.BackupStateFailure, expectedArtefact: ""},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			state, artefact := backupOutcome(testCase.ok, testCase.previous, testCase.newest)
			if state != testCase.expectedState || artefact != testCase.expectedArtefact {
				t.Errorf("backupOutcome() = (%q, %q), want (%q, %q)", state, artefact, testCase.expectedState, testCase.expectedArtefact)
			}
		})
	}
}

func TestProbeUtilBackupStagePrimary_ModuleSkipHoursHonoursTheOverrideEnvVar(t *testing.T) {
	tests := []struct {
		name     string
		override string
		expected int
	}{
		{name: "unset_falls_back_to_default", override: "", expected: moduleSkipHoursDefault},
		{name: "valid_override", override: "4", expected: 4},
		{name: "zero_is_a_valid_override", override: "0", expected: 0},
		{name: "negative_falls_back_to_default", override: "-1", expected: moduleSkipHoursDefault},
		{name: "unparseable_falls_back_to_default", override: "soon", expected: moduleSkipHoursDefault},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			t.Setenv(moduleSkipHoursVariable, testCase.override)
			if got := moduleSkipHours(); got != testCase.expected {
				t.Errorf("moduleSkipHours() = %d, want %d", got, testCase.expected)
			}
		})
	}
}

func TestProbeUtilBackupStagePrimary_ModuleTimeoutHoursPrefersTheRunDeadlineWhenItLeavesTimeToRun(t *testing.T) {
	loaded := loadedWithTimeout(t, 3)
	request := stageRequest{Expires: time.Now().Add(10*time.Hour + 50*time.Minute)}
	if got := moduleTimeoutHours(loaded, request); got != 10 {
		t.Errorf("moduleTimeoutHours() = %d, want 10 taken from the run deadline, not the configured default", got)
	}
}

func TestProbeUtilBackupStagePrimary_ModuleTimeoutHoursFallsBackToTheConfiguredDefault(t *testing.T) {
	tests := []struct {
		name    string
		expires time.Time
	}{
		{name: "no_deadline_set", expires: time.Time{}},
		{name: "deadline_already_passed", expires: time.Now().Add(-time.Hour)},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			loaded := loadedWithTimeout(t, 7)
			request := stageRequest{Expires: testCase.expires}
			if got := moduleTimeoutHours(loaded, request); got != 7 {
				t.Errorf("moduleTimeoutHours() = %d, want 7 taken from the configured default", got)
			}
		})
	}
}
