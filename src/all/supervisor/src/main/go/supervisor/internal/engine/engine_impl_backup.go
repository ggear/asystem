package engine

import (
	"context"
	"fmt"
	"os"
	"os/signal"
	"syscall"

	"supervisor/internal/metric"
	"supervisor/internal/probe"
)

func BackupStageOf(text string) (metric.BackupStage, error) { return probe.BackupStageOf(text) }

func BackupPrepared(request BackupRequest) (BackupRequest, error) {
	return probe.BackupPrepared(request)
}

func BackupStageLog(request BackupRequest) string { return probe.BackupStageLog(request) }

func BackupRunLog(request BackupRequest) string { return probe.BackupRunLog(request) }

func RunBackup(request BackupRequest) error {
	signals := make(chan os.Signal, 1)
	signal.Notify(signals, os.Interrupt, syscall.SIGTERM)
	defer signal.Stop(signals)
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	go func() {
		select {
		case <-signals:
			fmt.Println()
			cancel()
		case <-ctx.Done():
		}
	}()
	return probe.Backup(ctx, request)
}

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
