package cmd

import (
	"context"
	"fmt"
	"os"
	"os/signal"
	"strings"
	"syscall"
	"time"

	"networks/internal/config"
	"networks/internal/engine"
	"networks/internal/plugin"
	"networks/internal/scribe"

	_ "networks/internal/plugins"

	"github.com/spf13/cobra"
)

var (
	flagFilterPlugins   string
	flagPollPeriod      string
	flagAggregatePeriod string
	flagPublishData     bool
	flagDaemon          bool
	flagLogLevel        string
)

func Execute() {
	if err := rootCmd.Execute(); err != nil {
		if _, writeErr := fmt.Fprintln(os.Stderr, err); writeErr != nil {
			os.Exit(1)
		}
		os.Exit(1)
	}
}

func init() {
	rootCmd.Flags().StringVarP(&flagFilterPlugins, "filter-plugins", "f", "", "comma separated list restricting which plugins run (default: all)")
	rootCmd.Flags().StringVarP(&flagPollPeriod, "poll-period", "p", "5m", "fast poll cadence for poll-phase plugins, uses unit suffixes (s, m, h)")
	rootCmd.Flags().StringVarP(&flagAggregatePeriod, "aggregate-period", "a", config.DefaultAggregatePeriod, "window rolled up before a network diagnosis, must be a whole multiple of poll period, uses unit suffixes (s, m, h)")
	rootCmd.Flags().BoolVarP(&flagPublishData, "publish-data", "d", false, "publish aggregates to MQTT and InfluxDB when true, otherwise log only (ignored without --daemon, which logs only)")
	rootCmd.Flags().BoolVarP(&flagDaemon, "daemon", "D", false, "run continuously on the poll/aggregate loop when true, otherwise run a single log-only check at debug level and exit")
	rootCmd.Flags().StringVarP(&flagLogLevel, "log-level", "l", "info", "log level (debug, info, warn, error)")
	rootCmd.Flags().SortFlags = false
}

var rootCmd = &cobra.Command{
	Use:           "networks",
	Short:         "Diagnose network health and publish data",
	SilenceUsage:  true,
	SilenceErrors: true,
	Args:          cobra.NoArgs,
	RunE: func(cmd *cobra.Command, args []string) error {
		level, err := scribe.ParseLevel(flagLogLevel)
		if err != nil {
			return err
		}
		if !flagDaemon {
			level, _ = scribe.ParseLevel("debug")
			flagPublishData = false
		}
		scribe.EnableStdout(level)
		poll, aggregate, err := makePeriods(flagPollPeriod, flagAggregatePeriod)
		if err != nil {
			return err
		}
		var names []string
		if strings.TrimSpace(flagFilterPlugins) != "" {
			names = strings.Split(flagFilterPlugins, ",")
		}
		selected, err := plugin.Filter(names)
		if err != nil {
			return err
		}
		e := &engine.Engine{Plugins: selected, PollPeriod: poll, AggregatePeriod: aggregate, PublishData: flagPublishData, DaemonLoop: flagDaemon}
		if err := engine.Create(e); err != nil {
			return err
		}
		ctx, cancel := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
		defer cancel()
		if err := e.Run(ctx); err != nil && ctx.Err() == nil {
			return err
		}
		return nil
	},
}

func makePeriods(pollRaw, aggregateRaw string) (time.Duration, time.Duration, error) {
	poll, err := time.ParseDuration(pollRaw)
	if err != nil {
		return 0, 0, fmt.Errorf("invalid poll period [%w]", err)
	}
	if poll <= 0 {
		return 0, 0, fmt.Errorf("invalid poll period must be > 0")
	}
	aggregate, err := time.ParseDuration(aggregateRaw)
	if err != nil {
		return 0, 0, fmt.Errorf("invalid aggregate period [%w]", err)
	}
	if aggregate <= 0 {
		return 0, 0, fmt.Errorf("invalid aggregate period must be > 0")
	}
	if aggregate%poll != 0 {
		return 0, 0, fmt.Errorf("invalid aggregate period must be a whole multiple of poll period")
	}
	return poll, aggregate, nil
}
