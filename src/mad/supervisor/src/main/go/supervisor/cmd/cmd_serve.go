package cmd

import (
	"fmt"
	"log/slog"
	"supervisor/internal/scribe"

	"github.com/spf13/cobra"
)

type serveOptions struct {
	pollPeriod     string
	pulseFactor    string
	trendPeriod    string
	cachePeriod    string
	snapshotPeriod string
}

// noinspection DuplicatedCode
func newServeCmd() *cobra.Command {
	opts := &serveOptions{}
	cmd := &cobra.Command{
		Use:   "serve",
		Short: serveDescription,
		Long:  serveDescription,
		RunE: func(cmd *cobra.Command, args []string) error {
			err := executeServe(opts)
			if err != nil {
				return fmt.Errorf("error: %w", err)
			}
			return nil
		},
	}
	cmd.Flags().StringVarP(&opts.pollPeriod, "poll-period", "P", "1s", "period for adding fast moving metric samples into a pulse window, ignored by slow moving metrics, uses unit suffixes [s, m, h]. (default: 1s)")
	cmd.Flags().StringVarP(&opts.pulseFactor, "pulse-factor", "F", "5", "factor applied to polling period to size pulse window, defining metric sample aggregation publish period for all metrics (default: 5)")
	cmd.Flags().StringVarP(&opts.trendPeriod, "trend-period", "T", "24h", "period to size trend window, published with pulse factor * poll period, ignored by non-trend tracked metrics, uses unit suffixes [s, m, h] (default: 24h)")
	cmd.Flags().StringVarP(&opts.cachePeriod, "cache-period", "C", "24h", "period to cache metric sample for, ignored by fast moving metrics, uses unit suffixes [s, m, h] (default: 24h)")
	cmd.Flags().StringVarP(&opts.snapshotPeriod, "snapshot-period", "S", "5m", "period for publishing a metric snapshot, uses unit suffixes [s, m, h] (default: 5m)")
	cmd.Flags().SortFlags = false
	return cmd
}

func executeServe(opts *serveOptions) error {
	err := scribe.EnableFile(slog.LevelDebug, "serve", 10, 3, 7)
	if err != nil {
		return err
	}

	// TODO: START
	_, err = makePeriods(opts.pollPeriod, opts.pulseFactor, opts.trendPeriod, opts.cachePeriod, opts.snapshotPeriod)
	// TODO: END

	return nil
}

func init() {
	rootCmd.AddCommand(newServeCmd())
}

const serveDescription = "Run the supervisor process to collect and publish system stats and perform supervisory duties"
