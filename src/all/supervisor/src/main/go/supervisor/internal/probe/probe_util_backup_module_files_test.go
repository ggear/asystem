package probe

import (
	"io"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"testing"
)

func TestProbeUtilBackupModuleFiles_UnmatchedModuleEntries(t *testing.T) {
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
		{"everything_declared", []string{"keep", "skip", "stray.txt", "cache", "nested"}, nil, nil},
		{"stray_reported", []string{"keep"}, []string{"skip"}, []string{"cache", "nested", "stray.txt"}},
		{"glob_exclude", []string{"keep", "stray.txt", "nested"}, []string{"skip", "cache/*.bak-*"}, nil},
		{"nested_include_covers_parent", []string{"keep", "skip", "stray.txt", "cache", "nested/inner"}, nil, nil},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			actual := unmatchedModuleEntries(dir, testCase.includes, testCase.excludes)
			if strings.Join(actual, " ") != strings.Join(testCase.expected, " ") {
				t.Fatalf("unmatchedModuleEntries: got %v want %v", actual, testCase.expected)
			}
		})
	}
}

func TestProbeUtilBackupModuleFiles_NameModuleArtefact(t *testing.T) {
	source := filepath.Join(t.TempDir(), "mod", "10.1")
	root := filepath.Join(filepath.Dir(source), treeBackupDirectory)
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
		{"full", "2026-11-02_01-00-00", "_full", "tar.gz", "2026-11-02_01-00-00/mod_at_2026-11-02_01-00-00_from_10.1_full.tar.gz", false},
		{"delta_with_parent", "2026-11-02_01-00-00", "_delta", "tar.gz", "2026-11-02_01-00-00/mod_at_2026-11-02_01-00-00_from_10.1_delta.tar.gz", false},
		{"delta_without_parent", "2026-10-31_01-00-00", "_delta", "tar.gz", "", true},
		{"missing_suffix", "2026-11-02_01-00-00", "", "tar.gz", "", true},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			request := BackupModuleRequest{Run: testCase.run, State: t.TempDir()}
			actual, err := nameModuleArtefact(request, "mod", source, root, testCase.suffix, testCase.extension)
			if (err != nil) != testCase.expectedError {
				t.Fatalf("nameModuleArtefact: got error %v want error %t", err, testCase.expectedError)
			}
			if !testCase.expectedError && actual != filepath.Join(root, testCase.expected) {
				t.Fatalf("nameModuleArtefact: got [%s] want [%s]", actual, filepath.Join(root, testCase.expected))
			}
		})
	}
}

func TestProbeUtilBackupModuleFiles_BackupModuleFiles(t *testing.T) {
	if _, err := exec.LookPath("tar"); err != nil {
		t.Skip("no tar")
	}
	tests := []struct {
		name             string
		includes         []string
		expectedCode     int
		expectedUnits    string
		expectedIncludes string
	}{
		{"declared paths are archived and their includes recorded", []string{"keep", "top.txt"}, 0, "keep 3\ntop.txt 1\n", "keep\ntop.txt\n"},
		{"an absent include fails and leaves no archive", []string{"keep", "gone"}, 1, "", ""},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			source, state := filepath.Join(t.TempDir(), "mod", "1.0"), t.TempDir()
			for path, content := range map[string]string{"keep/a": "12", "keep/b": "3", "top.txt": "4"} {
				if err := os.MkdirAll(filepath.Dir(filepath.Join(source, path)), 0o755); err != nil {
					t.Fatal(err)
				}
				if err := os.WriteFile(filepath.Join(source, path), []byte(content), 0o644); err != nil {
					t.Fatal(err)
				}
			}
			t.Setenv("COPYFILE_DISABLE", "1")
			request := BackupModuleRequest{Arguments: []string{"mod"}, Source: source, Run: "2026-11-02_01-00-00", State: state, Root: ".", Includes: testCase.includes}
			code := BackupModuleFiles(t.Context(), request, io.Discard, io.Discard)
			var actual string
			temporary := filepath.Join(filepath.Dir(source), treeBackupDirectory, request.Run, "mod_at_"+request.Run+"_from_1.0_full.tar.gz.tmp")
			if os.Rename(temporary, strings.TrimSuffix(temporary, ".tmp")) == nil {
				units, _ := fingerprintBackupArtefact(strings.TrimSuffix(temporary, ".tmp"), testCase.includes)
				actual = fingerprintText(units)
			}
			includes, _ := os.ReadFile(filepath.Join(state, moduleIncludesLeaf))
			if code != testCase.expectedCode || actual != testCase.expectedUnits || string(includes) != testCase.expectedIncludes {
				t.Errorf("BackupModuleFiles() = code [%d] units %q includes %q, want [%d] %q %q", code, actual, includes, testCase.expectedCode, testCase.expectedUnits, testCase.expectedIncludes)
			}
		})
	}
}
