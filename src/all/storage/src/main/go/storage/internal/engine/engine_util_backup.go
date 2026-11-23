package engine

import (
	"encoding/json"
	"os"
	"path/filepath"
	"regexp"
	"sort"
	"storage/internal/config"
)

func backupMounts(loaded *config.Config, filters []string) []MountDoc {
	backup := loaded.Backup()
	if backup == nil {
		return nil
	}
	if class, matched := classifyMount(backup.Mount, filters); !matched || class != ClassBackup {
		return nil
	}
	measured := newestBackupReading(filepath.Join(backupTreeServiceHome, backupTreeModule, backupTreeBackupDirectory))
	if measured == nil {
		return nil
	}
	used := min(measured.UsedBytes, measured.TotalBytes)
	return []MountDoc{{
		Mount:  backup.Mount,
		Label:  backup.Label,
		Class:  ClassBackup,
		State:  MountStateMeasured,
		Space:  &SpaceFigures{SizeBytes: measured.TotalBytes, UsedBytes: used, FreeBytes: measured.TotalBytes - used},
		Backup: &BackupInfo{RunID: measured.RunID, MeasuredTS: measured.MeasuredTS},
	}}
}

func newestBackupReading(root string) *backupReading {
	entries, err := os.ReadDir(root)
	if err != nil {
		return nil
	}
	var runs []string
	for _, entry := range entries {
		if entry.IsDir() && backupTreeRunPattern.MatchString(entry.Name()) {
			runs = append(runs, entry.Name())
		}
	}
	sort.Sort(sort.Reverse(sort.StringSlice(runs)))
	for _, run := range runs {
		data, err := os.ReadFile(filepath.Join(root, run, backupTreeStageDirectory, backupTreeStageTertiary, backupTreeStatusLeaf))
		if err != nil {
			continue
		}
		var status backupTertiaryStatus
		if json.Unmarshal(data, &status) != nil || status.DiskTotalMiB <= 0 {
			continue
		}
		measuredTS := status.FinishedTS
		if measuredTS == "" {
			measuredTS = status.StartedTS
		}
		return &backupReading{
			RunID:      run,
			MeasuredTS: measuredTS,
			TotalBytes: uint64(status.DiskTotalMiB) * bytesPerMebibyte,
			UsedBytes:  uint64(status.DiskUsedMiB) * bytesPerMebibyte,
		}
	}
	return nil
}

type backupReading struct {
	RunID      string
	MeasuredTS string
	TotalBytes uint64
	UsedBytes  uint64
}

type backupTertiaryStatus struct {
	FinishedTS   string `json:"finished_ts"`
	StartedTS    string `json:"started_ts"`
	DiskTotalMiB int    `json:"disk_total_mb"`
	DiskUsedMiB  int    `json:"disk_used_mb"`
}

// The backup tree and its stage status document are owned by supervisor: config.DirServiceHome,
// the tree* constants in probe_util_backup_tree.go, metric.BackupStageTertiary and the backupSummary
// json tags. Each backupTree* constant mirrors the supervisor constant of the same suffix, and a test
// here parses supervisor's source and fails on any drift.
const (
	backupTreeServiceHome     = "/home/asystem"
	backupTreeModule          = "supervisor"
	backupTreeBackupDirectory = "backup"
	backupTreeStageDirectory  = "stage"
	backupTreeStageTertiary   = "tertiary"
	backupTreeStatusLeaf      = "status.json"

	bytesPerMebibyte = 1024 * 1024
)

var backupTreeRunPattern = regexp.MustCompile(`^\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}$`)
