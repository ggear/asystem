package probe

import (
	"archive/zip"
	"compress/gzip"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"slices"
	"sort"
	"strings"

	"supervisor/internal/metric"
)

func restoreChain(roots []string, run string) ([]restoreLink, error) {
	var reversed []restoreLink
	for {
		dir, found := restoreRunDir(roots, run)
		if !found {
			return nil, fmt.Errorf("no backup run [%s] under %v", run, roots)
		}
		file, found := restoreArtefact(dir)
		if !found {
			return nil, fmt.Errorf("no artifact in run [%s]", run)
		}
		reversed = append(reversed, restoreLink{run: run, file: file})
		if backupArtefactKind(filepath.Base(file)) != backupKindDelta {
			break
		}
		previous := previousBackupRun(roots, run)
		if previous == "" {
			return nil, fmt.Errorf("delta run [%s] has no run before it to hang off, so its chain has no full", run)
		}
		run = previous
	}
	slices.Reverse(reversed)
	return reversed, nil
}

func previousBackupRun(roots []string, run string) string {
	for _, candidate := range slices.Backward(restoreRuns(roots)) {
		if candidate >= run {
			continue
		}
		if dir, found := restoreRunDir(roots, candidate); found {
			if _, holds := restoreArtefact(dir); holds {
				return candidate
			}
		}
	}
	return ""
}

func restoreDefaultRun(roots []string) string {
	for _, run := range slices.Backward(restoreRuns(roots)) {
		dir, found := restoreRunDir(roots, run)
		if !found {
			continue
		}
		if _, holds := restoreArtefact(dir); !holds {
			continue
		}
		if manifest, read := readBackupManifest(filepath.Dir(dir), run); read && manifest.Verdict == metric.BackupStateRegressed {
			continue
		}
		return run
	}
	return ""
}

func restoreRunDir(roots []string, run string) (string, bool) {
	for _, root := range roots {
		dir := filepath.Join(root, run)
		if info, err := os.Stat(dir); err == nil && info.IsDir() {
			return dir, true
		}
	}
	return "", false
}

func restoreRuns(roots []string) []string {
	var runs []string
	for _, root := range roots {
		runs = append(runs, backupRuns(root)...)
	}
	sort.Strings(runs)
	return slices.Compact(runs)
}

func restoreArtefact(dir string) (string, bool) {
	entries, err := os.ReadDir(dir)
	if err != nil {
		return "", false
	}
	for _, entry := range entries {
		if !entry.IsDir() && backupArtefactKind(entry.Name()) != "" {
			return filepath.Join(dir, entry.Name()), true
		}
	}
	return "", false
}

func restoreIntact(path string) error {
	switch {
	case strings.HasSuffix(path, ".gz"):
		file, err := os.Open(path)
		if err != nil {
			return err
		}
		defer func() { _ = file.Close() }()
		unzipped, err := gzip.NewReader(file)
		if err != nil {
			return err
		}
		_, err = io.Copy(io.Discard, unzipped)
		return err
	case strings.HasSuffix(path, ".zip"):
		archive, err := zip.OpenReader(path)
		if err != nil {
			return err
		}
		defer func() { _ = archive.Close() }()
		for _, entry := range archive.File {
			opened, openErr := entry.Open()
			if openErr != nil {
				return openErr
			}
			_, copyErr := io.Copy(io.Discard, opened)
			_ = opened.Close()
			if copyErr != nil {
				return copyErr
			}
		}
	}
	return nil
}

func shortBackupUnits(want, have []backupFingerprintUnit) []string {
	held := map[string]int64{}
	for _, unit := range have {
		held[unit.name] = unit.count
	}
	var shorts []string
	for _, unit := range want {
		if count, present := held[unit.name]; !present || count < unit.count {
			shorts = append(shorts, fmt.Sprintf("short [%s] wants [%d] holds [%d]", unit.name, unit.count, count))
		}
	}
	return shorts
}

func differingBackupUnits(staged, live []backupFingerprintUnit) []string {
	held := map[string]int64{}
	for _, unit := range live {
		held[unit.name] = unit.count
	}
	var differing []string
	for _, unit := range staged {
		if count, present := held[unit.name]; !present || count != unit.count {
			differing = append(differing, unit.name)
		}
	}
	return differing
}

func readBackupDrill(path string) (backupDrill, bool) {
	drill := readSummary[backupDrill](path)
	if drill == nil {
		return backupDrill{}, false
	}
	return *drill, true
}

func backupDrillPath(dir, stage string) string {
	return filepath.Join(dir, treeMetaDirectory, stage, treeDrillLeaf)
}

type restoreLink struct {
	run  string
	file string
}

type backupDrill struct {
	Verdict string `json:"verdict"`
	Run     string `json:"run"`
	Detail  string `json:"detail"`
}
