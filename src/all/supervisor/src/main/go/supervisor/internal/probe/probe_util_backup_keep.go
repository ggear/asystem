package probe

import (
	"context"
	"fmt"
	"os"
	"path/filepath"
	"slices"
	"strings"
	"time"

	"supervisor/internal/metric"
	"supervisor/internal/scribe"
)

func pruneBackupRuns(ctx context.Context, subject scribe.Subject, dir string, policy backupKeepPolicy) {
	if policy.window <= 0 && policy.daily+policy.weekly+policy.monthly <= 0 {
		scribe.Log(scribe.SourceBackup, subject, scribe.ActionRemove).Warnf("excluded", time.Now(),
			"[%s] is not pruned, the config declares no retention window so only the newest runs would be kept", dir)
		return
	}
	runs := readBackupKeepRuns(dir)
	kept := backupKeepSet(runs, policy, time.Now())
	var doomed []string
	for _, run := range runs {
		if !kept[run.name] {
			doomed = append(doomed, run.name)
		}
	}
	if len(doomed) == 0 {
		return
	}
	if limit := len(runs) / 2; len(doomed) > limit {
		scribe.Log(scribe.SourceBackup, subject, scribe.ActionRemove).Warnf("faulting", time.Now(),
			"[%s] holds [%d] of [%d] runs outside the keep set, so only the oldest [%d] are pruned this pass", dir, len(doomed), len(runs), limit)
		doomed = doomed[:limit]
	}
	for _, name := range doomed {
		path := filepath.Join(dir, name)
		_, code, abandoned := bounded(ctx, stageBoundedWait, "btrfs", "subvolume", "delete", path)
		if abandoned || code != 0 {
			if err := os.RemoveAll(path); err != nil {
				scribe.Log(scribe.SourceBackup, subject, scribe.ActionRemove).Warnf("faulting", time.Now(), "[%s] could not be pruned from [%s] with [%v]", name, dir, err)
				continue
			}
		}
		scribe.Log(scribe.SourceBackup, subject, scribe.ActionRemove).Infof("expunged", time.Now(), "[%s] pruned from [%s] outside the keep set", name, dir)
	}
}

func readBackupKeepRuns(dir string) []backupKeepRun {
	var runs []backupKeepRun
	for _, name := range backupRuns(dir) {
		at, _ := time.ParseInLocation(backupTimestampFormat, name, time.Local)
		runDir := filepath.Join(dir, name)
		run := backupKeepRun{name: name, at: at, full: backupRunHolds(runDir, backupFullSuffix+".") || !backupRunHolds(runDir, backupDeltaSuffix+".")}
		if manifest, found := readBackupManifest(dir, name); found {
			run.parent, run.verdict, run.accepted, run.software = manifest.Parent, manifest.Verdict, manifest.Accepted, manifest.SourceSoftware
		}
		if drill, found := readSecondaryDrill(dir, name); found {
			run.drilled, run.judged = drill.Verdict != metric.BackupStateFailure, true
		}
		runs = append(runs, run)
	}
	return runs
}

func backupKeepSet(runs []backupKeepRun, policy backupKeepPolicy, now time.Time) map[string]bool {
	kept := map[string]bool{}
	if len(runs) == 0 {
		return kept
	}
	ordered := slices.Clone(runs)
	slices.SortFunc(ordered, func(left, right backupKeepRun) int { return strings.Compare(left.name, right.name) })
	newest := len(ordered) - 1
	if policy.window > 0 {
		for _, run := range ordered {
			if !run.at.Before(now.Add(-policy.window)) {
				kept[run.name] = true
			}
		}
	}
	daySeen := map[string]bool{}
	for index := newest; index >= 0 && policy.daily > 0; index-- {
		day := ordered[index].name[:10]
		if !daySeen[day] && len(daySeen) >= policy.daily {
			break
		}
		daySeen[day] = true
		kept[ordered[index].name] = true
	}
	tiers := []struct {
		seen, tried map[string]bool
		quota       int
		bucket      func(backupKeepRun) string
	}{
		{map[string]bool{}, map[string]bool{}, policy.weekly, backupWeekBucket},
		{map[string]bool{}, map[string]bool{}, policy.monthly, backupMonthBucket},
	}
	for index := newest; index >= 0; index-- {
		run := ordered[index]
		if !run.full {
			continue
		}
		for _, tier := range tiers {
			bucket := tier.bucket(run)
			if tier.seen[bucket] || tier.tried[bucket] || len(tier.seen) >= tier.quota {
				continue
			}
			tier.tried[bucket] = true
			kept[run.name] = true
			if run.drilled || !policy.gated {
				tier.seen[bucket] = true
			}
		}
	}
	kept[ordered[newest].name] = true
	for index := newest; index >= 0; index-- {
		if ordered[index].full {
			kept[ordered[index].name] = true
			break
		}
	}
	anchor := func() int {
		if ordered[newest].verdict != metric.BackupStateRegressed || ordered[newest].accepted {
			return -1
		}
		for index := newest - 1; index >= 0; index-- {
			if ordered[index].verdict == metric.BackupStateSuccess {
				return index
			}
		}
		return -1
	}()
	for index := anchor; index >= 0; index-- {
		kept[ordered[index].name] = true
		if ordered[index].full {
			break
		}
	}
	present := map[string]bool{}
	for _, run := range ordered {
		present[run.name] = true
	}
	for index := newest; index >= 0; index-- {
		run := ordered[index]
		if !kept[run.name] || run.full {
			continue
		}
		parent := run.parent
		if parent == "" && index > 0 {
			parent = ordered[index-1].name
		}
		if present[parent] {
			kept[parent] = true
		}
	}
	return kept
}

func backupWeekBucket(run backupKeepRun) string {
	year, week := run.at.ISOWeek()
	return fmt.Sprintf("%04d-%02d", year, week)
}

func backupMonthBucket(run backupKeepRun) string { return run.name[:7] }

type backupKeepPolicy struct {
	window  time.Duration
	daily   int
	weekly  int
	monthly int
	gated   bool
}

type backupKeepRun struct {
	name     string
	at       time.Time
	full     bool
	parent   string
	verdict  string
	accepted bool
	drilled  bool
	judged   bool
	software string
}
