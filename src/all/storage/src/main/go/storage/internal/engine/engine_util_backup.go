package engine

import (
	"encoding/json"
	"os"
	"path/filepath"
	"regexp"
	"sort"
	"storage/internal/config"
)

const (
	backupHomeEnvVar    = "BACKUP_HOME_ROOT"
	backupServiceHome   = "/home/asystem"
	backupTreeModule    = "supervisor"
	backupTreeDirectory = "backup"
	backupTertiaryLeaf  = "stage/tertiary/status.json"
)

var backupRunPattern = regexp.MustCompile(`^\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}$`)

type backupReading struct {
	RunID      string
	MeasuredTS string
	TotalBytes uint64
	UsedBytes  uint64
}

type tertiaryStatus struct {
	FinishedTS  string  `json:"finished_ts"`
	StartedTS   string  `json:"started_ts"`
	DiskTotalMB int     `json:"disk_total_mb"`
	DiskUsedMB  int     `json:"disk_used_mb"`
	DiskPerc    float64 `json:"disk_usage_perc"`
}

func newestBackupReading(root string) *backupReading {
	entries, err := os.ReadDir(root)
	if err != nil {
		return nil
	}
	var runs []string
	for _, entry := range entries {
		if entry.IsDir() && backupRunPattern.MatchString(entry.Name()) {
			runs = append(runs, entry.Name())
		}
	}
	sort.Sort(sort.Reverse(sort.StringSlice(runs)))
	for _, run := range runs {
		data, err := os.ReadFile(filepath.Join(root, run, backupTertiaryLeaf))
		if err != nil {
			continue
		}
		var status tertiaryStatus
		if json.Unmarshal(data, &status) != nil || status.DiskTotalMB <= 0 {
			continue
		}
		measured := status.FinishedTS
		if measured == "" {
			measured = status.StartedTS
		}
		totalBytes := uint64(status.DiskTotalMB) * 1024 * 1024
		usedBytes := uint64(status.DiskUsedMB) * 1024 * 1024
		return &backupReading{RunID: run, MeasuredTS: measured, TotalBytes: totalBytes, UsedBytes: usedBytes}
	}
	return nil
}

func backupRunRoot() string {
	if override := os.Getenv(backupHomeEnvVar); override != "" {
		return filepath.Join(override, backupTreeModule, backupTreeDirectory)
	}
	return filepath.Join(backupServiceHome, backupTreeModule, backupTreeDirectory)
}

func backupMounts(cfg *config.Config, drives []string) []MountDoc {
	backup := cfg.Backup()
	if backup == nil {
		return nil
	}
	if _, matched := ClassifyDrive(backup.Mount, drives); !matched {
		return nil
	}
	reading := newestBackupReading(backupRunRoot())
	if reading == nil {
		return nil
	}
	used := min(reading.UsedBytes, reading.TotalBytes)
	return []MountDoc{{
		Mount:  backup.Mount,
		Label:  backup.Label,
		Class:  ClassBackup,
		State:  MountStateMeasured,
		Space:  &SpaceFigures{SizeBytes: reading.TotalBytes, UsedBytes: used, FreeBytes: reading.TotalBytes - used},
		Backup: &BackupInfo{RunID: reading.RunID, MeasuredTS: reading.MeasuredTS},
	}}
}
