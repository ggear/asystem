package cmd

import (
	"context"
	"fmt"
	"log/slog"
	"os"
	"os/signal"
	"supervisor/internal/engine"
	"supervisor/internal/metric"
	"supervisor/internal/scribe"

	"github.com/spf13/cobra"
)

type serveOptions struct {
	pollPeriod      string
	pulseFactor     string
	trendPeriod     string
	cachePeriod     string
	snapshotPeriod  string
	heartbeatFactor string
}

// noinspection DuplicatedCode
func newServeCmd() *cobra.Command {
	opts := &serveOptions{}
	cmd := &cobra.Command{
		Use:   "serve",
		Short: serveDescription,
		Long:  serveDescription,
		RunE: func(cmd *cobra.Command, args []string) error {
			configPath, _ := cmd.Flags().GetString("config")
			err := executeServe(configPath, opts)
			if err != nil {
				return fmt.Errorf("error: %w", err)
			}
			return nil
		},
	}
	cmd.Flags().StringVarP(&opts.pollPeriod, "poll-period", "P", "1s", "period for adding fast moving metric samples into a pulse window, ignored by slow moving metrics, uses unit suffixes [s, m, h]. (default: 1s)")
	cmd.Flags().StringVarP(&opts.pulseFactor, "pulse-factor", "F", "5", "factor applied to polling period to size pulse window, defining metric sample aggregation publish period for all metrics (default: 5)")
	cmd.Flags().StringVarP(&opts.heartbeatFactor, "heartbeat-factor", "B", "60", "factor applied to pulse to time heart beat, period by which metrics are published even if they have not changed (default: 60)")
	cmd.Flags().StringVarP(&opts.trendPeriod, "trend-period", "T", "24h", "period to size trend window, published with pulse factor * poll period, ignored by non-trend tracked metrics, uses unit suffixes [s, m, h] (default: 24h)")
	cmd.Flags().StringVarP(&opts.cachePeriod, "cache-period", "C", "24h", "period to cache metric sample for, ignored by fast moving metrics, uses unit suffixes [s, m, h] (default: 24h)")
	cmd.Flags().StringVarP(&opts.snapshotPeriod, "snapshot-period", "S", "5m", "period for publishing a metric snapshot, uses unit suffixes [s, m, h] (default: 5m)")
	cmd.Flags().SortFlags = false
	return cmd
}

func executeServe(configPath string, opts *serveOptions) error {
	scribe.EnableStdout(slog.LevelDebug)
	periods, err := makePeriods(opts.pollPeriod, opts.pulseFactor, opts.trendPeriod, opts.cachePeriod, opts.snapshotPeriod, opts.heartbeatFactor)
	if err != nil {
		return err
	}
	ctx, cancel := signal.NotifyContext(context.Background(), os.Interrupt)
	defer cancel()
	engine.RunAllProbesPublishLoop(ctx, configPath, metric.NewRecordCache(), periods)
	return nil
}

func init() {
	rootCmd.AddCommand(newServeCmd())
}

const serveDescription = "Run the supervisor process to collect and publish system stats and perform supervisory duties"
