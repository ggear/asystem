package cmd

import (
	"fmt"
	"time"

	"supervisor/internal/config"
	"supervisor/internal/engine"
	"supervisor/internal/metric"
	"supervisor/internal/scribe"

	"github.com/spf13/cobra"
)

func init() {
	rootCmd.AddCommand(newBackupCmd())
}

func newBackupCmd() *cobra.Command {
	opts := &backupOptions{}
	cmd := &cobra.Command{
		Use:   backupCommandName + " [command]",
		Short: backupDescription,
		Long:  backupDescription,
	}
	cmd.PersistentFlags().StringVarP(&opts.stage, "stage", "G", "", "execute one stage only [primary, secondary, tertiary]")
	cmd.PersistentFlags().BoolVarP(&opts.scrub, "scrub", "S", false, "scrub the backup disk, whatever the monthly window says")
	cmd.PersistentFlags().BoolVarP(&opts.quiet, "quiet", "Q", false, "drop the stdout copy of the stage log, keeping the file")
	cmd.PersistentFlags().DurationVarP(&opts.timeout, "timeout-period", "T", 0, "deadline for the whole run, defaulting to the configured timeout, uses unit suffixes [s, m, h]")
	addLogFlags(cmd, &opts.logOptions, "info")
	cmd.PersistentFlags().SortFlags = false
	cmd.Flags().SortFlags = false
	for _, verb := range backupVerbs {
		cmd.AddCommand(newBackupVerbCmd(verb, opts))
	}
	return cmd
}

func newBackupVerbCmd(verb backupVerb, opts *backupOptions) *cobra.Command {
	return &cobra.Command{
		Use:   verb.use,
		Short: verb.short,
		Args:  cobra.MaximumNArgs(verb.arguments),
		RunE: func(cmd *cobra.Command, args []string) error {
			configPath, _ := cmd.Flags().GetString("config")
			request := engine.BackupRequest{
				Command: verb.command, Trigger: metric.BackupTriggerManual, Config: configPath,
				Timeout: opts.timeout, Scrub: opts.scrub,
			}
			if len(args) > 0 {
				request.Argument = args[0]
			}
			if opts.stage != "" {
				stage, err := engine.BackupStageOf(opts.stage)
				if err != nil {
					return err
				}
				request.Stage = stage
			}
			return executeBackup(request, opts)
		},
	}
}

func executeBackup(request engine.BackupRequest, opts *backupOptions) error {
	level, err := makeLevel(opts.logLevel)
	if err != nil {
		return err
	}
	request, err = engine.BackupPrepared(request)
	if err != nil {
		return err
	}
	switch {
	case request.Stage != "":
		closer, enableErr := scribe.EnableBackupAndFile(level, backupCommandName, config.ResolvedVersion(request.Config),
			engine.BackupStageLog(request), opts.quiet, logFileSizeMB, logFileBackups, logFileAgeDays)
		if enableErr != nil {
			return fmt.Errorf("backup logging could not be enabled [%w]", enableErr)
		}
		defer func() { _ = closer.Close() }()
	case request.Command == engine.BackupCommandStart:
		if enableErr := scribe.EnableStdoutAndFile(level, backupCommandName, config.ResolvedVersion(request.Config),
			engine.BackupRunLog(request), logFileSizeMB, logFileBackups, logFileAgeDays); enableErr != nil {
			return fmt.Errorf("file logging could not be enabled [%w]", enableErr)
		}
	default:
		scribe.EnableStdout(level)
	}
	if err := setLogFilters(&opts.logOptions); err != nil {
		return err
	}
	if err := engine.RunBackup(request); err != nil {
		scribe.Log(scribe.SourceBackup, scribe.SubjectNone, scribe.ActionStop).Errorf("faulting", time.Now(),
			"[%s] command did not complete cleanly, %v", request.Command, err)
		return errCommandReported
	}
	return nil
}

type backupOptions struct {
	stage   string
	quiet   bool
	scrub   bool
	timeout time.Duration
	logOptions
}

type backupVerb struct {
	command   engine.BackupCommand
	use       string
	short     string
	arguments int
}

var backupVerbs = []backupVerb{
	{command: engine.BackupCommandStart, use: "start [run-id]", short: "start a backup run, or resume the given run id", arguments: 1},
	{command: engine.BackupCommandStop, use: "stop [run-id]", short: "stop the active run, or the given run id", arguments: 1},
	{command: engine.BackupCommandTail, use: "tail [run-id]", short: "follow the newest, or the given, run's progress", arguments: 1},
	{command: engine.BackupCommandList, use: "list", short: "show the recent runs and their result"},
	{command: engine.BackupCommandAuto, use: "auto [on|off]", short: "query or set the reaper's power-management switch", arguments: 1},
	{command: engine.BackupCommandClean, use: "clean", short: "remove every run from the history and any unfinished scrub"},
}

const (
	backupCommandName = "backup"
	backupDescription = "Drive a backup run, or execute one stage of the scheduled run"
)
