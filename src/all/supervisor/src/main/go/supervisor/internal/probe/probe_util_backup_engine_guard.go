package probe

import (
	"fmt"
	"slices"

	"supervisor/internal/metric"
)

const backupEvidenceLimit = 20

type backupVerdict struct {
	verdict  string
	evidence []string
}

func backupBaseline(root, run string) string {
	names := backupRuns(root)
	for _, name := range slices.Backward(names) {
		if name >= run {
			continue
		}
		if manifest, found := readBackupManifest(root, name); found && manifest.Verdict == metric.BackupStateSuccess && len(manifest.Fingerprint) > 0 {
			return name
		}
	}
	return ""
}

func backupRegression(current []fingerprintUnit, baseline backupManifest, baselineRun string, shrinkPercent int) backupVerdict {
	verdict := backupVerdict{verdict: metric.BackupStateSuccess}
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
