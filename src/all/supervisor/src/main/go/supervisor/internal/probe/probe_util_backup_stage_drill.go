package probe

import (
	"bytes"
	"context"
	"os"
	"path/filepath"
	"slices"
	"strings"
	"time"

	"supervisor/internal/config"
	"supervisor/internal/metric"
	"supervisor/internal/scribe"
)

func drillSecondaryServices(ctx context.Context, loaded *config.Config, share, host, servicePath string, services []string) (drilled, failed int) {
	subject := scribe.SubjectStage(metric.BackupStageSecondary)
	for _, service := range services {
		script := filepath.Join(config.DirInstall, service, config.DirInstallLatestLink, restoreScriptLeaf)
		if service == treeModule || ctx.Err() != nil {
			continue
		}
		if _, err := os.Stat(script); err != nil {
			continue
		}
		target := promotionTarget(service, share, host)
		window := loaded.BackupWindowOf(service)
		runs := readBackupKeepRuns(target)
		for _, run := range backupDrillDue(runs, backupKeepPolicy{weekly: window.KeepWeekly, monthly: window.KeepMonthly}, time.Now()) {
			started := time.Now()
			var output bytes.Buffer
			code := BackupModuleDrill(ctx, BackupModuleRequest{
				Arguments: []string{service}, Script: script, Runs: target, From: run, Record: string(metric.BackupStageSecondary), LockPeriod: 5 * time.Minute,
			}, &output, &output)
			state := metric.BackupStateSuccess
			if code != 0 {
				state = metric.BackupStateFailure
			} else if drill, found := readSecondaryDrill(target, run); found {
				state = drill.Verdict
			}
			drilled++
			scribe.Log(scribe.SourceBackup, scribe.SubjectService(service), scribe.ActionStop).Infof("verified", started,
				"[%s] point [%s] restored as [%s] in [%d] s", service, run, state, int(time.Since(started).Seconds()))
			if code != 0 {
				fault := "the drill failed without naming a fault"
				for line := range strings.SplitSeq(output.String(), "\n") {
					if strings.HasPrefix(line, "❌") {
						fault = line
						break
					}
				}
				scribe.Log(scribe.SourceBackup, scribe.SubjectService(service), scribe.ActionStop).Warnf("faulting", started, "%s", fault)
			}
		}
		if backupDrillRetained(target) {
			flagBackupDrillFailed(filepath.Join(servicePath, service, treeStatusLeaf))
		}
		if backupDrillFailing(target) {
			failed++
			scribe.Log(scribe.SourceBackup, subject, scribe.ActionStop).Warnf("faulting", time.Now(), "[%s] newest drill failed and no later drill has passed", service)
		}
	}
	return drilled, failed
}

func reportReleaseDrills(service string) (failed int) {
	dir := serviceHomeDir(service)
	for _, run := range backupRuns(dir) {
		path := backupDrillPath(filepath.Join(dir, run), string(metric.BackupStagePrimary))
		drill, found := readBackupDrill(path)
		if !found {
			continue
		}
		failed = 0
		if drill.Verdict == metric.BackupStateFailure {
			failed = 1
		}
		if _, reported := os.Stat(path + drillReportedSuffix); reported == nil {
			continue
		}
		scribe.Log(scribe.SourceBackup, scribe.SubjectService(service), scribe.ActionStop).Infof("verified", time.Now(),
			"[%s] point [%s] release drill as [%s]", service, run, drill.Verdict)
		_ = os.WriteFile(path+drillReportedSuffix, nil, 0o644)
	}
	return failed
}

func backupDrillDue(runs []backupKeepRun, policy backupKeepPolicy, now time.Time) []string {
	current := backupKeepRun{name: now.Format(backupTimestampFormat), at: now}
	tiers := []struct {
		seen   map[string]bool
		quota  int
		bucket func(backupKeepRun) string
	}{
		{map[string]bool{}, policy.weekly, backupWeekBucket},
		{map[string]bool{}, policy.monthly, backupMonthBucket},
	}
	var due []string
	generations := map[string]bool{}
	for _, run := range runs {
		if run.software == "" || generations[run.software] {
			continue
		}
		generations[run.software] = true
		if run.full && !run.judged {
			due = append(due, run.name)
		}
	}
	for _, run := range slices.Backward(runs) {
		if !run.full {
			continue
		}
		for _, tier := range tiers {
			bucket := tier.bucket(run)
			if tier.seen[bucket] || len(tier.seen) >= tier.quota {
				continue
			}
			tier.seen[bucket] = true
			if bucket != tier.bucket(current) && !run.judged && !slices.Contains(due, run.name) {
				due = append(due, run.name)
			}
		}
	}
	slices.Sort(due)
	return due
}

func readSecondaryDrill(target, run string) (backupDrill, bool) {
	return readBackupDrill(backupDrillPath(filepath.Join(target, run), string(metric.BackupStageSecondary)))
}

func backupDrillFailing(target string) bool {
	for _, run := range slices.Backward(backupRuns(target)) {
		if drill, found := readSecondaryDrill(target, run); found {
			return backupDrillFailed(target, run, drill)
		}
	}
	return false
}

func backupDrillRetained(target string) bool {
	for _, run := range backupRuns(target) {
		if drill, found := readSecondaryDrill(target, run); found && backupDrillFailed(target, run, drill) {
			return true
		}
	}
	return false
}

func backupDrillFailed(target, run string, drill backupDrill) bool {
	manifest, read := readBackupManifest(target, run)
	return drill.Verdict == metric.BackupStateFailure && read && manifest.SourceSoftware != ""
}

func flagBackupDrillFailed(path string) {
	if document := readSummary[serviceSummary](path); document != nil {
		document.DrillFailedBool = true
		_ = writeAtomic(path, *document)
	}
}

const (
	restoreScriptLeaf   = "restore.sh"
	drillReportedSuffix = ".reported"
)
