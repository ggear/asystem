package cmd

import (
	"context"
	"fmt"
	"io"
	"os"
	"os/signal"
	"syscall"
	"time"

	"supervisor/internal/config"
	"supervisor/internal/engine"
	"supervisor/internal/metric"
	"supervisor/internal/scribe"

	"github.com/spf13/cobra"
	"github.com/spf13/pflag"
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
	cmd.PersistentFlags().SortFlags = false
	cmd.Flags().SortFlags = false
	for _, verb := range backupVerbs {
		cmd.AddCommand(newBackupVerbCmd(verb, opts))
	}
	for _, verb := range backupModuleVerbs {
		cmd.AddCommand(newBackupModuleCmd(verb))
	}
	return cmd
}

func newBackupModuleCmd(verb backupModuleVerb) *cobra.Command {
	request := &engine.BackupModuleRequest{}
	cmd := &cobra.Command{
		Use:    verb.use,
		Short:  verb.short,
		Hidden: verb.hidden,
		Args:   cobra.ExactArgs(verb.arguments),
		RunE: func(_ *cobra.Command, args []string) error {
			ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
			defer stop()
			request.Arguments = args
			if code := verb.run(ctx, *request, os.Stdout, os.Stderr); code != 0 {
				return exitError(code)
			}
			return nil
		},
	}
	verb.flags(cmd.Flags(), request)
	cmd.Flags().SortFlags = false
	if len(verb.advanced) > 0 {
		addAdvancedFlags(cmd, verb.advanced)
	}
	return cmd
}

func newBackupVerbCmd(verb backupVerb, opts *backupOptions) *cobra.Command {
	cmd := &cobra.Command{
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
	cmd.Flags().StringVarP(&opts.stage, "stage", "G", "", "execute one stage only [primary, secondary, tertiary]")
	cmd.Flags().BoolVarP(&opts.scrub, "scrub", "S", false, "scrub the backup disk, whatever the monthly window says")
	cmd.Flags().BoolVarP(&opts.quiet, "quiet", "Q", false, "drop the stdout copy of the log, keeping the run log and the log file")
	cmd.Flags().DurationVarP(&opts.timeout, "timeout-period", "T", 0, "deadline for the whole run, defaulting to the configured timeout, uses unit suffixes [s, m, h]")
	addLogFlags(cmd, &opts.logOptions, "info")
	cmd.Flags().SortFlags = false
	return cmd
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
		if enableErr := scribe.EnableBackupAndFile(level, backupCommandName, config.ResolvedVersion(request.Config),
			opts.quiet, logFileSizeMB, logFileBackups, logFileAgeDays); enableErr != nil {
			return fmt.Errorf("backup logging could not be enabled [%w]", enableErr)
		}
	case request.Command == engine.BackupCommandStart:
		if enableErr := scribe.EnableStdoutAndFile(level, backupCommandName, config.ResolvedVersion(request.Config),
			logFileSizeMB, logFileBackups, logFileAgeDays); enableErr != nil {
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
			"[%s] %v", request.Command, err)
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

type backupModuleVerb struct {
	run       func(context.Context, engine.BackupModuleRequest, io.Writer, io.Writer) int
	use       string
	short     string
	hidden    bool
	arguments int
	flags     func(*pflag.FlagSet, *engine.BackupModuleRequest)
	advanced  []string
}

var backupModuleVerbs = []backupModuleVerb{
	{run: engine.BackupModuleRun, use: "run <module>", short: "run one module's backup, the module's hooks supplied by --script", arguments: 1, flags: addBackupModuleRunFlags, advanced: []string{"script", "lock-period"}},
	{run: engine.BackupModuleAccept, use: "accept <module> <run>", short: "accept a regressed run, releasing its anchor", arguments: 2, flags: func(flags *pflag.FlagSet, request *engine.BackupModuleRequest) {
		addBackupModuleSourceFlag(flags, request)
	}},
	{run: engine.BackupModuleRestore, use: "restore <module>", short: "restore a module from a backup chain, the plan only without --force", arguments: 1, flags: addBackupModuleRestoreFlags, advanced: []string{"script", "lock-period"}},
	{run: engine.BackupModuleDrill, use: "drill <module>", short: "prove a backup chain restores without touching the live module", arguments: 1, flags: addBackupModuleRestoreFlags, advanced: []string{"script", "lock-period"}},
	{run: engine.BackupModuleMerge, use: "merge <module>", short: "put back the history a live module lost, keeping what it has written since", arguments: 1, flags: addBackupModuleRestoreFlags, advanced: []string{"script", "lock-period"}},
	{run: engine.BackupModuleTarget, use: "target <module> <suffix> <extension>", short: "name this run's backup file for a module hook", hidden: true, arguments: 3, flags: addBackupModuleHookFlags},
	{run: engine.BackupModuleFiles, use: "files <module>", short: "archive declared paths for a module hook", hidden: true, arguments: 1, flags: func(flags *pflag.FlagSet, request *engine.BackupModuleRequest) {
		addBackupModuleHookFlags(flags, request)
		flags.StringVar(&request.Root, "root", "", "the directory under the source holding the includes")
		flags.StringVar(&request.Live, "live", "", "atomic when the source may change while it is read")
		flags.StringArrayVar(&request.Includes, "include", nil, "a path to back up")
		flags.StringArrayVar(&request.Excludes, "exclude", nil, "a path or pattern deliberately not backed up")
	}},
	{run: engine.BackupModuleParent, use: "parent <module>", short: "print the full backup before this run for a module hook", hidden: true, arguments: 1, flags: addBackupModuleHookFlags},
	{run: engine.BackupModuleEpoch, use: "epoch <run>", short: "print the unix time of a run for a module hook", hidden: true, arguments: 1, flags: func(*pflag.FlagSet, *engine.BackupModuleRequest) {}},
	{run: engine.BackupModuleReport, use: "report <text>", short: "print a restore line in the report columns for a module hook", hidden: true, arguments: 1, flags: func(*pflag.FlagSet, *engine.BackupModuleRequest) {}},
	{run: engine.BackupModuleRestoreFiles, use: "restore-files <module>", short: "extract an archive over declared paths for a module hook", hidden: true, arguments: 1, flags: func(flags *pflag.FlagSet, request *engine.BackupModuleRequest) {
		addBackupModuleHookFlags(flags, request)
		flags.StringVar(&request.Target, "target", "", "the directory the archive is extracted into")
		flags.StringVar(&request.File, "file", "", "the archive")
		flags.StringVar(&request.Paths, "paths", "", "colon separated paths moved aside before the extract")
		flags.StringArrayVar(&request.Carry, "carry", nil, "a file name pattern carried back from the moved paths")
	}},
}

func addBackupModuleRunFlags(flags *pflag.FlagSet, request *engine.BackupModuleRequest) {
	addBackupModuleSourceFlag(flags, request)
	flags.StringVarP(&request.Script, "script", "x", "", "the module's backup.sh, sourced for its hooks")
	flags.DurationVarP(&request.SkipPeriod, "skip-period", "p", time.Hour, "skip the run when the newest backup is younger than this, zero to never skip, uses unit suffixes [s, m, h]")
	flags.DurationVarP(&request.TimeoutPeriod, "timeout-period", "T", 5*time.Hour, "the budget a backup waiting on its service allows before abandoning the run, uses unit suffixes [s, m, h]")
	flags.IntVarP(&request.ShrinkPercent, "shrink-percent", "z", 20, "the fall in a module's total that marks a run regressed, zero to disable")
	flags.DurationVarP(&request.LockPeriod, "lock-period", "k", backupModuleLockPeriod, "time to wait for another actor holding the module's lock, uses unit suffixes [s, m, h]")
	flags.BoolVarP(&request.ForceFull, "force-full", "F", false, "take a full backup where the module would take a delta")
	flags.BoolVarP(&request.NoRestart, "no-restart", "N", false, "leave the service stopped after the copy, for a caller that starts it itself")
}

func addBackupModuleRestoreFlags(flags *pflag.FlagSet, request *engine.BackupModuleRequest) {
	addBackupModuleSourceFlag(flags, request)
	flags.StringVarP(&request.Script, "script", "x", "", "the module's restore.sh, sourced for its hooks")
	flags.StringVarP(&request.Runs, "runs", "r", "", "a directory of runs searched alone")
	flags.StringVarP(&request.From, "from", "f", "", "the run to restore, defaulting to the newest not regressed")
	flags.StringVarP(&request.File, "file", "i", "", "an artefact path outright")
	flags.StringVarP(&request.Record, "record", "R", "", "the stage under whose .meta a drill writes its verdict [primary, secondary]")
	flags.DurationVarP(&request.LockPeriod, "lock-period", "k", backupModuleLockPeriod, "time to wait for another actor holding the module's lock, uses unit suffixes [s, m, h]")
	flags.BoolVarP(&request.Force, "force", "F", false, "apply the plan")
	flags.BoolVarP(&request.NoBackup, "no-backup", "n", false, "skip the safety backup before applying")
	flags.BoolVarP(&request.KeepScratch, "keep-scratch", "K", false, "leave the scratch copy behind")
}

func addBackupModuleHookFlags(flags *pflag.FlagSet, request *engine.BackupModuleRequest) {
	addBackupModuleSourceFlag(flags, request)
	flags.StringVar(&request.Run, "run", "", "this run's timestamp")
	flags.StringVar(&request.State, "state", "", "the run's state directory")
}

func addBackupModuleSourceFlag(flags *pflag.FlagSet, request *engine.BackupModuleRequest) {
	flags.StringVarP(&request.Source, "source", "s", "", "the module's source path, defaulting to its latest")
}

const (
	backupModuleLockPeriod = 5 * time.Minute
	backupCommandName      = "backup"
	backupDescription      = "Drive a backup run, or execute one stage of the scheduled run"
)
