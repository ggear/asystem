package cmd

import (
	"context"
	"fmt"
	"log/slog"
	"os"
	"os/signal"
	"supervisor/internal/config"
	"supervisor/internal/engine"
	"supervisor/internal/metric"
	"supervisor/internal/scribe"
	"syscall"
	"time"

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
	cmd.Flags().StringVarP(&opts.pollPeriod, "poll-period", "P", config.DefaultPollPeriod, "period for adding fast moving metric samples into a pulse window, ignored by slow moving metrics, uses unit suffixes [s, m, h]")
	cmd.Flags().StringVarP(&opts.pulseFactor, "pulse-factor", "F", config.DefaultPulseFactor, "factor applied to polling period to size pulse window, defining metric sample aggregation publish period for all metrics")
	cmd.Flags().StringVarP(&opts.heartbeatFactor, "heartbeat-period", "B", "5m", "period by which metrics are published even if they have not changed, rounded up to nearest pulse boundary, uses unit suffixes [s, m, h]")
	cmd.Flags().StringVarP(&opts.trendPeriod, "trend-period", "T", config.DefaultTrendPeriod, "period to size trend window, published with pulse factor * poll period, ignored by non-trend tracked metrics, uses unit suffixes [s, m, h]")
	cmd.Flags().StringVarP(&opts.cachePeriod, "cache-period", "C", "1h", "period to cache metric sample for, ignored by fast moving metrics, uses unit suffixes [s, m, h]")
	cmd.Flags().StringVarP(&opts.snapshotPeriod, "snapshot-period", "S", "5m", "period for publishing a metric snapshot, uses unit suffixes [s, m, h]")
	cmd.Flags().SortFlags = false
	return cmd
}

func executeServe(configPath string, opts *serveOptions) error {
	if err := scribe.EnableStdoutAndFile(slog.LevelDebug, "serve", 10, 3, 7); err != nil {
		return fmt.Errorf("enable file logging: %w", err)
	}
	periods, err := makePeriods(opts.pollPeriod, opts.pulseFactor, opts.trendPeriod, opts.cachePeriod, opts.snapshotPeriod, opts.heartbeatFactor)
	if err != nil {
		return err
	}
	ctx, cancel := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer cancel()
	serveStart := time.Now()
	loaded := config.Load(configPath)
	scribe.Engine("state", "serve").Info("start", serveStart, "version  [%s], host [%s], config [%s], configured [%d] services, poll [%d] ms, pulse [%d] ms, heartbeat [%d] s", loaded.Version(), loaded.Host(), configPath, len(loaded.Services(loaded.Host())), periods.PollMillis, periods.PulseMillis, periods.HeartbeatSecs)
	engine.RunAllProbesPublishLoop(ctx, configPath, metric.NewRecordCache(), periods)
	scribe.Engine("state", "serve").Info("stop", serveStart, "version  [%s], host [%s], exited gracefully", loaded.Version(), loaded.Host())
	return nil
}

func init() {
	rootCmd.AddCommand(newServeCmd())
}

const serveDescription = "Run the supervisor process to collect and publish system stats and perform supervisory duties"
