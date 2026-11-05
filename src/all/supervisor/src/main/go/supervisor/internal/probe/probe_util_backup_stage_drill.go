package probe

import (
	"bytes"
	"context"
	"fmt"
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
			} else if drill, found := readBackupDrill(backupDrillPath(filepath.Join(target, run), string(metric.BackupStageSecondary))); found {
				state = drill.Verdict
			}
			drilled++
			scribe.Log(scribe.SourceBackup, scribe.SubjectService(service), scribe.ActionStop).Infof("verified", started,
				"[%s] point [%s] restored as [%s] in [%d] s", service, run, state, int(time.Since(started).Seconds()))
			if code != 0 {
				scribe.Log(scribe.SourceBackup, scribe.SubjectService(service), scribe.ActionStop).Warnf("faulting", started, "%s", firstDrillFault(output.String()))
			}
		}
		if backupDrillRetained(target) {
			demoteBackupService(filepath.Join(servicePath, service, treeStatusLeaf))
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
	nowYear, nowWeek := now.ISOWeek()
	currentWeek, currentMonth := fmt.Sprintf("%04d-%02d", nowYear, nowWeek), now.Format("2006-01")
	tiers := []struct {
		seen    map[string]bool
		quota   int
		current string
		bucket  func(backupKeepRun) string
	}{
		{map[string]bool{}, policy.weekly, currentWeek, func(run backupKeepRun) string {
			year, week := run.at.ISOWeek()
			return fmt.Sprintf("%04d-%02d", year, week)
		}},
		{map[string]bool{}, policy.monthly, currentMonth, func(run backupKeepRun) string { return run.name[:7] }},
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
			if bucket != tier.current && !run.judged && !slices.Contains(due, run.name) {
				due = append(due, run.name)
			}
		}
	}
	slices.Sort(due)
	return due
}

func backupDrillFailing(target string) bool {
	for _, run := range slices.Backward(backupRuns(target)) {
		if drill, found := readBackupDrill(backupDrillPath(filepath.Join(target, run), string(metric.BackupStageSecondary))); found {
			return drill.Verdict == metric.BackupStateFailure
		}
	}
	return false
}

func backupDrillRetained(target string) bool {
	for _, run := range backupRuns(target) {
		if drill, found := readBackupDrill(backupDrillPath(filepath.Join(target, run), string(metric.BackupStageSecondary))); found && drill.Verdict == metric.BackupStateFailure {
			return true
		}
	}
	return false
}

func demoteBackupService(path string) {
	document := readBackupSummary(path)
	if document == nil || !document.SuccessBool {
		return
	}
	document.SuccessBool = false
	_ = writeAtomic(path, *document)
}

func firstDrillFault(output string) string {
	for line := range strings.SplitSeq(output, "\n") {
		if strings.HasPrefix(line, "❌") {
			return line
		}
	}
	return "the drill failed without naming a fault"
}

const (
	restoreScriptLeaf   = "restore.sh"
	drillReportedSuffix = ".reported"
)
