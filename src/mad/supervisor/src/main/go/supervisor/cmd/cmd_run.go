package cmd

import (
	"fmt"
	"log/slog"
	"supervisor/internal/scribe"
	"time"

	"github.com/spf13/cobra"
)

type runOptions struct {
	pollPeriod     string
	binPeriod      string
	snapshotPeriod string
}

func newRunCmd() *cobra.Command {
	opts := &runOptions{}
	cmd := &cobra.Command{
		Use:   "run",
		Short: runDescription,
		Long:  runDescription,
		RunE: func(cmd *cobra.Command, args []string) error {
			err := executeRun(opts)
			if err != nil {
				return fmt.Errorf("error: %w", err)
			}
			return nil
		},
	}
	cmd.Flags().StringVarP(&opts.pollPeriod, "poll-period", "p", "1s", "polling period for caching individual metric raw values, with unit suffixes [s, m, h] (default: 1s)")
	cmd.Flags().StringVarP(&opts.binPeriod, "bin-period", "b", "5s", "bin period for analysing and publishing individual, calculated metric values, with unit suffixes [s, m, h] (default: 5s)")
	cmd.Flags().StringVarP(&opts.snapshotPeriod, "snapshot-period", "s", "5m", "snapshot period for publishing a complete set of calculated metric values, with unit suffixes [s, m, h] (default: 5m)")
	cmd.Flags().SortFlags = false
	return cmd
}

func executeRun(opts *runOptions) error {
	err := scribe.EnableFile(slog.LevelDebug, "run", 10, 3, 7)
	if err != nil {
		return err
	}
	pollDur, err := time.ParseDuration(opts.pollPeriod)
	if err != nil {
		return fmt.Errorf("invalid poll period: %w", err)
	}
	if _, err := time.ParseDuration(opts.binPeriod); err != nil {
		return fmt.Errorf("invalid bin period: %w", err)
	}
	if _, err := time.ParseDuration(opts.snapshotPeriod); err != nil {
		return fmt.Errorf("invalid snapshot period: %w", err)
	}
	fmt.Printf("Starting supervisor (poll interval: %s)\n", pollDur)
	return nil
}

func init() {
	rootCmd.AddCommand(newRunCmd())
}

const runDescription = "Run the supervisor process to collect and publish system statistics and perform supervisory duties"
