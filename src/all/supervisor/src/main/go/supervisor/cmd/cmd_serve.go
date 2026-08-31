package cmd

import (
	"context"
	"fmt"
	"os"
	"os/signal"
	"path/filepath"
	"supervisor/internal/config"
	"supervisor/internal/engine"
	"supervisor/internal/metric"
	"supervisor/internal/scribe"
	"syscall"
	"time"

	"github.com/spf13/cobra"
)

func init() {
	rootCmd.AddCommand(newServeCmd())
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
	cmd.Flags().StringVarP(&opts.cachePeriod, "cache-period", "C", config.DefaultCachePeriod, "period to cache metric sample for, ignored by fast moving metrics, uses unit suffixes [s, m, h]")
	cmd.Flags().StringVarP(&opts.snapshotPeriod, "snapshot-period", "S", "5m", "period for publishing a metric snapshot, uses unit suffixes [s, m, h]")
	addLogFlags(cmd, &opts.logOptions, "info")
	cmd.Flags().SortFlags = false
	return cmd
}

func executeServe(configPath string, opts *serveOptions) error {
	level, err := makeLevel(opts.logLevel)
	if err != nil {
		return err
	}
	scribe.Widen(configuredHosts(configPath), configuredServices(configPath))
	if err := scribe.EnableStdoutAndFile(level, "serve", 10, 3, 7); err != nil {
		return fmt.Errorf("enable file logging: %w", err)
	}
	if err := setLogFilters(&opts.logOptions); err != nil {
		return err
	}
	periods, err := makePeriods(opts.pollPeriod, opts.pulseFactor, opts.trendPeriod, opts.cachePeriod, opts.snapshotPeriod, opts.heartbeatFactor)
	if err != nil {
		return err
	}
	ctx, cancel := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer cancel()
	serveStart := time.Now()
	loaded := config.Load(configPath)
	scribe.Log(scribe.SourceCmdServe, scribe.SubjectHost(loaded.Host()), scribe.ActionStart).Info("identity", serveStart, "[%s] version", loaded.Version())
	scribe.Log(scribe.SourceCmdServe, scribe.SubjectHost(loaded.Host()), scribe.ActionStart).Info("resolved", serveStart, "[%s] config", filepath.Base(configPath))
	scribe.Log(scribe.SourceCmdServe, scribe.SubjectHost(loaded.Host()), scribe.ActionStart).Info("watching", serveStart, "[%d] services", len(loaded.Services(loaded.Host())))
	scribe.Log(scribe.SourceCmdServe, scribe.SubjectHost(loaded.Host()), scribe.ActionStart).Info("periodic", serveStart, "[%d] ms poll", periods.PollMillis)
	scribe.Log(scribe.SourceCmdServe, scribe.SubjectHost(loaded.Host()), scribe.ActionStart).Info("periodic", serveStart, "[%d] ms pulse", periods.PulseMillis)
	scribe.Log(scribe.SourceCmdServe, scribe.SubjectHost(loaded.Host()), scribe.ActionStart).Info("periodic", serveStart, "[%d] s heartbeat", periods.HeartbeatSecs)
	cache := metric.NewRecordCache()
	engine.RunAllProbesPublishLoop(ctx, configPath, cache, periods)
	scribe.Log(scribe.SourceCmdServe, scribe.SubjectHost(loaded.Host()), scribe.ActionStop).Info("identity", serveStart, "[%s] version, exited gracefully", loaded.Version())
	return nil
}

type serveOptions struct {
	pollPeriod      string
	pulseFactor     string
	trendPeriod     string
	cachePeriod     string
	snapshotPeriod  string
	heartbeatFactor string
	logOptions
}

const serveDescription = "Run the supervisor process to collect and publish system stats and perform supervisory duties"
