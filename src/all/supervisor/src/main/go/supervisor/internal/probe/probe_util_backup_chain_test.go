package probe

import (
	"os"
	"path/filepath"
	"slices"
	"testing"

	"supervisor/internal/metric"
)

func TestProbeUtilBackupChain_RestoreChain(t *testing.T) {
	tests := []struct {
		name          string
		runs          map[string]string
		from          string
		expected      []string
		expectedError bool
	}{
		{"a full stands alone", map[string]string{"2026-11-01_01-00-00": "m_full.tar.gz"}, "2026-11-01_01-00-00", []string{"2026-11-01_01-00-00"}, false},
		{
			"a delta walks back to its full",
			map[string]string{"2026-11-01_01-00-00": "m_full.tar.gz", "2026-11-02_01-00-00": "m_delta.tar.gz", "2026-11-03_01-00-00": "m_delta.tar.gz"},
			"2026-11-03_01-00-00", []string{"2026-11-01_01-00-00", "2026-11-02_01-00-00", "2026-11-03_01-00-00"}, false,
		},
		{"a delta with nothing before it has no full", map[string]string{"2026-11-02_01-00-00": "m_delta.tar.gz"}, "2026-11-02_01-00-00", nil, true},
		{"an unknown run is refused", map[string]string{"2026-11-01_01-00-00": "m_full.tar.gz"}, "2026-11-09_01-00-00", nil, true},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			root := t.TempDir()
			for run, artefact := range test.runs {
				plantArtefact(t, root, run, artefact)
			}
			chain, err := restoreChain([]string{root}, test.from)
			var actual []string
			for _, link := range chain {
				actual = append(actual, link.run)
			}
			if (err != nil) != test.expectedError || !slices.Equal(actual, test.expected) {
				t.Errorf("chain: got %v and error [%v] want %v and error [%t]", actual, err, test.expected, test.expectedError)
			}
		})
	}
}

func TestProbeUtilBackupChain_RestoreDefaultRun(t *testing.T) {
	root := t.TempDir()
	plantArtefact(t, root, "2026-11-01_01-00-00", "m_full.tar.gz")
	plantArtefact(t, root, "2026-11-02_01-00-00", "m_full.tar.gz")
	plantBackupManifest(t, root, "2026-11-02_01-00-00", backupManifest{Kind: "full", Verdict: metric.BackupStateRegressed})
	if actual := restoreDefaultRun([]string{root}); actual != "2026-11-01_01-00-00" {
		t.Errorf("default run: got [%s] want the newest not regressed", actual)
	}
}

func TestProbeUtilBackupChain_RestoreIntact(t *testing.T) {
	tests := []struct {
		name          string
		file          string
		content       []byte
		expectedError bool
	}{
		{"whole gzip", "a.tar.gz", gzipped(t, "payload"), false},
		{"truncated gzip", "a.tar.gz", gzipped(t, "payload payload payload payload")[:12], true},
		{"corrupt gzip", "a.tar.gz", []byte("not gzip"), true},
		{"corrupt zip", "a.zip", []byte("not a zip"), true},
		{"unchecked kind", "a.txt", []byte("anything"), false},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			path := filepath.Join(t.TempDir(), test.file)
			if err := os.WriteFile(path, test.content, 0o644); err != nil {
				t.Fatal(err)
			}
			if err := restoreIntact(path); (err != nil) != test.expectedError {
				t.Errorf("intact: got error [%v] want error [%t]", err, test.expectedError)
			}
		})
	}
}

func TestProbeUtilBackupChain_ShortBackupUnits(t *testing.T) {
	unit := func(name string, count int64) backupFingerprintUnit {
		return backupFingerprintUnit{name: name, count: count}
	}
	tests := []struct {
		name     string
		want     []backupFingerprintUnit
		have     []backupFingerprintUnit
		expected int
	}{
		{"equal", []backupFingerprintUnit{unit("a", 5)}, []backupFingerprintUnit{unit("a", 5)}, 0},
		{"more is fine", []backupFingerprintUnit{unit("a", 5)}, []backupFingerprintUnit{unit("a", 9)}, 0},
		{"fewer is short", []backupFingerprintUnit{unit("a", 5)}, []backupFingerprintUnit{unit("a", 4)}, 1},
		{"absent is short", []backupFingerprintUnit{unit("a", 5), unit("b", 1)}, []backupFingerprintUnit{unit("a", 5)}, 1},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			if actual := shortBackupUnits(test.want, test.have); len(actual) != test.expected {
				t.Errorf("shorts: got %v want [%d]", actual, test.expected)
			}
		})
	}
}

func TestProbeUtilBackupChain_DifferingBackupUnits(t *testing.T) {
	unit := func(name string, count int64) backupFingerprintUnit {
		return backupFingerprintUnit{name: name, count: count}
	}
	staged := []backupFingerprintUnit{unit("a", 5), unit("b", 3), unit("c", 2)}
	live := []backupFingerprintUnit{unit("a", 5), unit("b", 9), unit("only-live", 1)}
	if actual := differingBackupUnits(staged, live); !slices.Equal(actual, []string{"b", "c"}) {
		t.Errorf("differing: got %v want units whose count differs or that live lacks, never live-only ones", actual)
	}
}

func plantArtefact(t *testing.T, root, run, artefact string) {
	t.Helper()
	if err := os.MkdirAll(filepath.Join(root, run), 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(root, run, artefact), gzipped(t, "x"), 0o644); err != nil {
		t.Fatal(err)
	}
}

func gzipped(t *testing.T, content string) []byte {
	t.Helper()
	path := filepath.Join(t.TempDir(), "g.gz")
	writeTestGzip(t, path, content)
	data, err := os.ReadFile(path)
	if err != nil {
		t.Fatal(err)
	}
	return data
}
