package probe

import (
	"fmt"
	"io/fs"
	"os"
	"path/filepath"
	"slices"
	"strings"

	"supervisor/internal/metric"
)

func (s *restoreSession) drill() {
	var want []backupFingerprintUnit
	if manifest, read := s.manifest(); read {
		want = manifest.Fingerprint
	}
	if manifest, read := s.manifest(); read && !s.compatible(manifest) {
		s.report(fmt.Sprintf("drill     skipped, taken from software [%s] version [%s], now [%s] version [%s], integrity passed", manifest.SourceSoftware, manifest.SourceVersion, s.software, filepath.Base(s.source)))
		s.record(metric.BackupStateSkipped, "software differs")
		return
	}
	s.report(fmt.Sprintf("drill     chain of [%d] artifact(s), manifest holds [%d] unit(s)", len(s.chain), len(want)))
	if len(want) == 0 {
		s.report("the run has no manifest fingerprint, so only integrity and staging are proven")
	}
	s.swept()
	scratch, err := s.staged()
	failed := func(detail string, shorts []string) {
		s.fault(detail)
		for _, line := range shorts {
			s.report(line)
		}
		if !s.request.KeepScratch {
			s.tornDown(scratch)
		}
		s.record(metric.BackupStateFailure, detail)
	}
	if err != nil {
		scratch = s.scratchDir()
		failed(fmt.Sprintf("could not stage [%s] into scratch [%v]", s.run, err), nil)
		return
	}
	addressed := s.defined[moduleHookFingerprint]
	extracts := slices.ContainsFunc(s.chain, func(link restoreLink) bool {
		return strings.HasSuffix(link.file, ".tar.gz") || strings.HasSuffix(link.file, ".zip")
	})
	fingerprint := func() ([]backupFingerprintUnit, error) {
		if addressed {
			return s.fingerprinted(scratch)
		}
		if extracts {
			return fingerprintBackupScratch(scratch, want), nil
		}
		return want, nil
	}
	if !addressed {
		includes := make([]string, 0, len(want))
		for _, unit := range want {
			includes = append(includes, unit.name)
		}
		have, fingerprintErr := fingerprintBackupArtefact(s.chain[len(s.chain)-1].file, includes)
		if shorts := shortBackupUnits(want, have); fingerprintErr != nil || len(shorts) > 0 {
			failed("the artifact holds less than its manifest says", shorts)
			return
		}
	}
	before, err := fingerprint()
	if err != nil {
		failed(fmt.Sprintf("could not fingerprint scratch [%s] [%v]", scratch, err), nil)
		return
	}
	if shorts := shortBackupUnits(want, before); len(shorts) > 0 {
		failed("scratch holds less than the manifest says", shorts)
		return
	}
	if s.defined[restoreHookChecked] {
		if _, checkErr := s.hooked(restoreHookChecked, "", scratch); checkErr != nil {
			failed(fmt.Sprintf("the module check of scratch [%s] failed", scratch), nil)
			return
		}
	}
	if sealErr := s.sealed(scratch); sealErr != nil {
		failed(fmt.Sprintf("could not seal scratch [%s] read only", scratch), nil)
		return
	}
	after, err := fingerprint()
	if err != nil || !slices.Equal(s.settled(before), s.settled(after)) {
		failed("scratch changed after it was sealed", nil)
		return
	}
	if !s.request.KeepScratch {
		s.tornDown(scratch)
	}
	s.report("drill passed, every manifest unit is held and scratch is read only")
	s.record(metric.BackupStateSuccess, "drilled")
}

func (s *restoreSession) manifest() (backupManifest, bool) {
	dir, found := restoreRunDir(s.roots, s.run)
	if !found {
		return backupManifest{}, false
	}
	return readBackupManifest(filepath.Dir(dir), s.run)
}

func (s *restoreSession) compatible(manifest backupManifest) bool {
	if s.software == "" {
		sibling := moduleHooks{script: filepath.Join(filepath.Dir(s.request.Script), scriptLeaf), env: []string{"BACKUP_SOURCE_PATH=" + s.source}}
		s.software = versionedModule(s.ctx, sibling, s.stderr, filepath.Base(s.source))
	}
	return backupCompatible(manifest, s.software)
}

func fingerprintBackupScratch(scratch string, want []backupFingerprintUnit) []backupFingerprintUnit {
	counts := map[string]int64{}
	for _, unit := range want {
		path := filepath.Join(scratch, unit.name)
		if _, err := os.Lstat(path); err != nil {
			continue
		}
		var total int64
		_ = filepath.WalkDir(path, func(_ string, entry fs.DirEntry, err error) error {
			if info, infoErr := entry.Info(); err == nil && infoErr == nil && info.Mode().IsRegular() {
				total += info.Size()
			}
			return nil
		})
		counts[unit.name] = total
	}
	return sortBackupFingerprint(counts)
}
