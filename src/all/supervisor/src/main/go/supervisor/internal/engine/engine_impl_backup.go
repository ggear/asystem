package engine

import (
	"context"

	"supervisor/internal/metric"
	"supervisor/internal/probe"
)

func BackupStageOf(text string) (metric.BackupStage, error) { return probe.BackupStageOf(text) }

func BackupPrepared(request BackupRequest) (BackupRequest, error) {
	return probe.BackupPrepared(request)
}

func BackupStageLog(request BackupRequest) string { return probe.BackupStageLog(request) }

func RunBackup(request BackupRequest) error { return probe.Backup(context.Background(), request) }

type (
	BackupCommand = probe.BackupCommand
	BackupRequest = probe.BackupRequest
)

const (
	BackupCommandStart = probe.BackupCommandStart
	BackupCommandStop  = probe.BackupCommandStop
	BackupCommandTail  = probe.BackupCommandTail
	BackupCommandList  = probe.BackupCommandList
	BackupCommandAuto  = probe.BackupCommandAuto
)
