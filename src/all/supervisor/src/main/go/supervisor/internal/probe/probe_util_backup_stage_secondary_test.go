package probe

import (
	"os"
	"os/exec"
	"path/filepath"
	"slices"
	"strings"
	"testing"

	"supervisor/internal/config"
	"supervisor/internal/metric"
)

func TestProbeUtilBackupStageSecondary_RsyncFieldAgainstCapturedTertiaryMirror(t *testing.T) {
	output := fixtureStages(t, "rsync/output-tertiary-mirror.log")
	tests := []struct {
		prefix   string
		expected int
	}{
		{"Number of files: ", 14827},
		{"Number of created files: ", 27},
		{"Number of deleted files: ", 21},
		{"Number of regular files transferred: ", 22},
		{"Total file size: ", 1123246170567},
		{"Total transferred file size: ", 1355617},
		{"Total bytes sent: ", 1949185},
	}
	for _, testCase := range tests {
		if got := rsyncField(output, testCase.prefix); got != testCase.expected {
			t.Errorf("rsyncField(%q) = %d, want %d", testCase.prefix, got, testCase.expected)
		}
	}
}

func TestProbeUtilBackupStageSecondary_RsyncFieldMissingPrefixIsZero(t *testing.T) {
	if got := rsyncField("some unrelated output\n", "Number of files: "); got != 0 {
		t.Errorf("rsyncField() = %d, want 0", got)
	}
}

func TestProbeUtilBackupStageSecondary_OnlyDigitsStripsCommasAndUnits(t *testing.T) {
	tests := map[string]string{
		"9.44M":     "944",
		"1,355,617": "1355617",
		"":          "0",
		"no-digits": "0",
		"22":        "22",
	}
	for input, expected := range tests {
		if got := onlyDigits(input); got != expected {
			t.Errorf("onlyDigits(%q) = %q, want %q", input, got, expected)
		}
	}
}

func TestProbeUtilBackupStageSecondary_PromotionTarget(t *testing.T) {
	tests := []struct {
		name     string
		service  string
		expected string
	}{
		{"a module lands directly under the share backup directory", "plex", "/share/10/backup/plex"},
		{"supervisor lands under its host so hosts sharing a share do not collide", treeModule, "/share/10/backup/supervisor/macmini-mad"},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			if actual := promotionTarget(testCase.service, "/share/10", "macmini-mad"); actual != testCase.expected {
				t.Errorf("promotionTarget() = %q, want %q", actual, testCase.expected)
			}
		})
	}
}

func TestProbeUtilBackupStageSecondary_GradedServices(t *testing.T) {
	tests := []struct {
		name     string
		graded   map[string]bool
		want     bool
		expected []string
	}{
		{"successful services are promoted in name order", map[string]bool{"plex": true, "mariadb": true, "wrangle": false}, true, []string{"mariadb", "plex"}},
		{"failed services are the complement", map[string]bool{"plex": true, "mariadb": true, "wrangle": false}, false, []string{"wrangle"}},
		{"no services grade as nothing", map[string]bool{}, true, nil},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			runPath := t.TempDir()
			for service, success := range testCase.graded {
				if err := os.MkdirAll(serviceDir(runPath, service), 0o755); err != nil {
					t.Fatal(err)
				}
				if err := writeAtomic(serviceStatusPath(runPath, service), serviceSummary{State: metric.BackupStateSuccess, SuccessBool: success}); err != nil {
					t.Fatal(err)
				}
			}
			if actual := gradedServices(serviceRoot(runPath), testCase.want); !slices.Equal(actual, testCase.expected) {
				t.Errorf("gradedServices() = %v, want %v", actual, testCase.expected)
			}
		})
	}
}

func TestProbeUtilBackupStageSecondary_AdoptedRun(t *testing.T) {
	tests := []struct {
		name             string
		runs             []string
		withServices     []string
		expected         string
		expectedAdoption bool
	}{
		{"the newest run that wrote services is adopted", []string{"2026-11-01_01-00-00", "2026-11-02_01-00-00", "2026-11-03_01-00-00"}, []string{"2026-11-01_01-00-00", "2026-11-02_01-00-00"}, "2026-11-02_01-00-00", true},
		{"no run wrote services so nothing is adopted", []string{"2026-11-01_01-00-00"}, nil, "", false},
		{"no runs at all", nil, nil, "", false},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			root := t.TempDir()
			for _, run := range testCase.runs {
				if err := os.MkdirAll(backupRunPath(root, run), 0o755); err != nil {
					t.Fatal(err)
				}
			}
			for _, run := range testCase.withServices {
				if err := os.MkdirAll(serviceRoot(backupRunPath(root, run)), 0o755); err != nil {
					t.Fatal(err)
				}
			}
			if actual, adopted := adoptedRun(root); actual != testCase.expected || adopted != testCase.expectedAdoption {
				t.Errorf("adoptedRun() = (%q, %t), want (%q, %t)", actual, adopted, testCase.expected, testCase.expectedAdoption)
			}
		})
	}
}

func TestProbeUtilBackupStageSecondary_ClearDirectory(t *testing.T) {
	tests := []struct {
		name     string
		files    []string
		expected int
	}{
		{"files and nested directories all go", []string{"a", "b/c", "b/d/e"}, 0},
		{"an empty directory stays empty", nil, 0},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			dir := t.TempDir()
			for _, file := range testCase.files {
				if err := os.MkdirAll(filepath.Dir(filepath.Join(dir, file)), 0o755); err != nil {
					t.Fatal(err)
				}
				if err := os.WriteFile(filepath.Join(dir, file), []byte("x"), 0o644); err != nil {
					t.Fatal(err)
				}
			}
			clearDirectory(dir)
			entries, err := os.ReadDir(dir)
			if err != nil || len(entries) != testCase.expected {
				t.Errorf("clearDirectory() left [%d] entries with error [%v], want [%d]", len(entries), err, testCase.expected)
			}
		})
	}
}

func TestProbeUtilBackupStageSecondary_PromoteOneService(t *testing.T) {
	if _, err := exec.LookPath("rsync"); err != nil {
		t.Skip("no rsync")
	}
	runs := []string{"2026-10-01_01-00-00", "2026-10-02_01-00-00", "2026-10-03_01-00-00", "2026-10-04_01-00-00", "2026-10-05_01-00-00"}
	tests := []struct {
		name          string
		configBody    string
		expected      []string
		expectedError bool
	}{
		{"only the keep set reaches the share", `{"asystem":{"backup":{"keep_daily":2,"keep_weekly":0,"keep_monthly":0,"retain_days":7}}}`, runs[3:], false},
		{"a module declaring no retention is copied whole", `{"asystem":{"backup":{}}}`, runs, false},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			home, share := t.TempDir(), t.TempDir()
			t.Setenv(config.BackupHomeEnvVar, home)
			source := serviceHomeDir("plex")
			for _, run := range runs {
				artefact := filepath.Join(source, run, "plex_at_"+run+"_from_1.0_full.tar.gz")
				if err := os.MkdirAll(filepath.Join(source, run, treeMetaDirectory), 0o755); err != nil {
					t.Fatal(err)
				}
				for _, path := range []string{artefact, filepath.Join(source, run, treeMetaDirectory, treeManifestLeaf), filepath.Join(source, treeLockLeaf)} {
					if err := os.WriteFile(path, []byte("x"), 0o644); err != nil {
						t.Fatal(err)
					}
				}
			}
			configPath := filepath.Join(t.TempDir(), "config.json")
			if err := os.WriteFile(configPath, []byte(testCase.configBody), 0o644); err != nil {
				t.Fatal(err)
			}
			err := promoteOneService(t.Context(), config.Load(configPath), share, "macmini-mad", "plex", 1, 1, &stageCounters{})
			target := promotionTarget("plex", share, "macmini-mad")
			actual := backupRuns(target)
			if (err != nil) != testCase.expectedError || !slices.Equal(actual, testCase.expected) {
				t.Fatalf("promoteOneService() = error [%v] and runs %v, want error [%t] and %v", err, actual, testCase.expectedError, testCase.expected)
			}
			for _, run := range actual {
				if _, statErr := os.Stat(filepath.Join(target, run, treeMetaDirectory, treeManifestLeaf)); statErr != nil {
					t.Errorf("promoteOneService() did not carry the manifest of [%s] [%v]", run, statErr)
				}
			}
			if _, statErr := os.Stat(filepath.Join(target, treeLockLeaf)); statErr == nil {
				t.Errorf("promoteOneService() copied the source lock into %s", strings.TrimPrefix(target, share))
			}
		})
	}
}
