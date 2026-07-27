package cmd

import (
	"fmt"
	"os"
	"strings"
	"time"

	"github.com/spf13/cobra"
)

var (
	flagFilterPlugins   string
	flagPollPeriod      string
	flagAggregatePeriod string
	flagPublishData     bool
	flagLogLevel        string
)

func Execute() {
	if err := rootCmd.Execute(); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}

func init() {
	rootCmd.PersistentFlags().StringVarP(&flagFilterPlugins, "filter-plugins", "f", "", "comma separated list restricting which plugins run (default: all)")
	rootCmd.PersistentFlags().StringVarP(&flagPollPeriod, "poll-period", "p", "5m", "fast poll cadence for poll-phase plugins, uses unit suffixes [s, m, h]")
	rootCmd.PersistentFlags().StringVarP(&flagAggregatePeriod, "aggregate-period", "a", "15m", "window rolled up before a status decision, must be a whole multiple of poll period, uses unit suffixes [s, m, h]")
	rootCmd.PersistentFlags().BoolVarP(&flagPublishData, "publish-data", "d", false, "publish aggregates to MQTT and InfluxDB when true, otherwise log only")
	rootCmd.PersistentFlags().StringVarP(&flagLogLevel, "log-level", "l", "info", "log level [debug, info, warn, error]")
	rootCmd.Flags().SortFlags = false
	rootCmd.PersistentFlags().SortFlags = false
	rootCmd.InheritedFlags().SortFlags = false
	rootCmd.AddCommand(newServeCmd())
	rootCmd.AddCommand(newCheckCmd())
}

var rootCmd = &cobra.Command{
	Use:           "networks",
	Short:         rootDescription,
	Long:          rootDescription,
	SilenceUsage:  true,
	SilenceErrors: true,
	RunE: func(cmd *cobra.Command, args []string) error {
		if len(args) == 0 {
			return cmd.Help()
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

func pluginNames() []string {
	if strings.TrimSpace(flagFilterPlugins) == "" {
		return nil
	}
	return strings.Split(flagFilterPlugins, ",")
}

const rootDescription = "Monitor network health and publish status"
