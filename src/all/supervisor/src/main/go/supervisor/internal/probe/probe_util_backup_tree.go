package probe

import (
	"os"
	"path/filepath"
	"regexp"
	"sort"
	"time"

	"supervisor/internal/config"
	"supervisor/internal/metric"
)

func backupRunRoot() string {
	if override := os.Getenv(config.BackupHomeEnvVar); override != "" {
		return filepath.Join(override, treeModule, treeBackupDirectory)
	}
	return filepath.Join(config.DirServiceHome, treeModule, treeBackupDirectory)
}

func backupRunPath(root, runID string) string { return filepath.Join(root, runID) }

func stageLogPath(runPath string, stage metric.BackupStage) string {
	return filepath.Join(stageDir(runPath, stage), treeLogLeaf)
}

func backupRuns(root string) []string {
	entries, err := os.ReadDir(root)
	if err != nil {
		return nil
	}
	var runs []string
	for _, entry := range entries {
		if entry.IsDir() && treeRunPattern.MatchString(entry.Name()) {
			runs = append(runs, entry.Name())
		}
	}
	sort.Strings(runs)
	return runs
}

func readBackupRun(root, dir string) *backupSnapshot {
	at, _ := time.ParseInLocation(backupTimestampFormat, dir, time.Local)
	snapshot := &backupSnapshot{dir: dir, at: at, stages: map[metric.BackupStage]*backupSummary{}, services: map[string]bool{}}
	runPath := backupRunPath(root, dir)
	snapshot.host = readBackupSummary(statusPath(runPath))
	staged, _ := filepath.Glob(filepath.Join(runPath, treeStageDirectory, "*", treeStatusLeaf))
	snapshot.staged = len(staged)
	for _, path := range staged {
		if document := readBackupSummary(path); document != nil {
			snapshot.stages[metric.BackupStage(filepath.Base(filepath.Dir(path)))] = document
		}
	}
	snapshot.tertiary = snapshot.stages[metric.BackupStageTertiary]
	for _, stage := range backupStages {
		if document := snapshot.stages[stage]; document != nil && document.Trigger != "" {
			snapshot.trigger = document.Trigger
			break
		}
	}
	documents, _ := filepath.Glob(filepath.Join(serviceRoot(runPath), "*", treeStatusLeaf))
	for _, path := range documents {
		if document := readBackupSummary(path); document != nil {
			snapshot.services[filepath.Base(filepath.Dir(path))] = document.SuccessBool
		}
	}
	return snapshot
}

func backupHomeRoot() string {
	if override := os.Getenv(config.BackupHomeEnvVar); override != "" {
		return override
	}
	return config.DirServiceHome
}

func serviceHomeDir(service string) string {
	return filepath.Join(backupHomeRoot(), service, treeBackupDirectory)
}

func lockPath(root string) string { return filepath.Join(root, treeLockLeaf) }

func runLogPath(runPath string) string { return filepath.Join(runPath, treeRunLogLeaf) }

func statusPath(runPath string) string { return filepath.Join(runPath, treeStatusLeaf) }

func stageDir(runPath string, stage metric.BackupStage) string {
	return filepath.Join(runPath, treeStageDirectory, string(stage))
}

func stageStatusPath(runPath string, stage metric.BackupStage) string {
	return filepath.Join(stageDir(runPath, stage), treeStatusLeaf)
}

func scrubStatusPath(runPath string) string {
	return filepath.Join(stageDir(runPath, metric.BackupStageTertiary), treeScrubLeaf)
}

func serviceRoot(runPath string) string {
	return filepath.Join(stageDir(runPath, metric.BackupStagePrimary), treeServiceDirectory)
}

func serviceDir(runPath, service string) string {
	return filepath.Join(serviceRoot(runPath), service)
}

func serviceStatusPath(runPath, service string) string {
	return filepath.Join(serviceDir(runPath, service), treeStatusLeaf)
}

func serviceLogPath(runPath, service string) string {
	return filepath.Join(serviceDir(runPath, service), treeLogLeaf)
}

type backupSnapshot struct {
	dir       string
	at        time.Time
	staged    int
	running   bool
	abandoned bool
	trigger   string
	host      *backupSummary
	tertiary  *backupSummary
	stages    map[metric.BackupStage]*backupSummary
	services  map[string]bool
}

func (s *backupSnapshot) age() time.Duration {
	if s == nil || s.at.IsZero() {
		return backupStaleWindow * 100
	}
	return config.SinceIncludingSuspend(s.at)
}

const (
	treeModule           = "supervisor"
	treeBackupDirectory  = "backup"
	treeStageDirectory   = "stage"
	treeServiceDirectory = "service"

	treeStatusLeaf = "status.json"
	treeScrubLeaf  = "scrub.json"
	treeLogLeaf    = "output.log"
	treeLockLeaf   = ".lock"
	treeRunLogLeaf = "run.log"
)

var treeRunPattern = regexp.MustCompile(`^\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}$`)
