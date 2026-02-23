package cmd

import (
	"fmt"
	"os"
	"strconv"
	"supervisor/internal/config"
	"supervisor/internal/probe"
	"time"

	"github.com/spf13/cobra"
)

func Execute() {
	if err := rootCmd.Execute(); err != nil {
		_, _ = fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}

func init() {
	rootCmd.PersistentFlags().BoolP("version", "v", false, "display version information and exit")
	rootCmd.Flags().SortFlags = false
	rootCmd.PersistentFlags().SortFlags = false
	rootCmd.InheritedFlags().SortFlags = false
}

var rootCmd = &cobra.Command{
	Short:         rootDescription,
	Long:          rootDescription,
	SilenceUsage:  true,
	SilenceErrors: true,
	RunE: func(cmd *cobra.Command, args []string) error {
		showVersion, _ := cmd.Flags().GetBool("version")
		if showVersion {
			if c, err := config.Load(config.DefaultConfigPath); err != nil {
				return err
			} else {
				fmt.Println(c.Version())
			}
			os.Exit(0)
		}
		if len(args) == 0 {
			return cmd.Help()
		}
		return nil
	},
}

func makePeriods(pollPeriod, pulseFactor, trendPeriod, cachePeriod, snapshotPeriod string) (probe.Periods, error) {
	toDuration := func(raw string, unit time.Duration, name string) (int, error) {
		d, err := time.ParseDuration(raw)
		if err != nil {
			return 0, fmt.Errorf("invalid %s period: %w", name, err)
		}
		if d < 0 {
			return 0, fmt.Errorf("invalid %s period: must be >= 0", name)
		}
		if d%unit != 0 {
			return 0, fmt.Errorf("invalid %s period: must be a whole number of %s", name, unit)
		}
		return int(d / unit), nil
	}
	pollSecs, err := toDuration(pollPeriod, time.Second, "poll")
	if err != nil {
		return probe.Periods{}, err
	}
	pulseFactorInt, err := strconv.Atoi(pulseFactor)
	if err != nil {
		return probe.Periods{}, fmt.Errorf("invalid pulse factor: %w", err)
	}
	if pulseFactorInt < 0 {
		return probe.Periods{}, fmt.Errorf("invalid pulse factor: must be >= 0")
	}
	pulseSecs := pulseFactorInt * pollSecs
	trendHours, err := toDuration(trendPeriod, time.Hour, "trend")
	if err != nil {
		return probe.Periods{}, err
	}
	cacheHours, err := toDuration(cachePeriod, time.Hour, "cache")
	if err != nil {
		return probe.Periods{}, err
	}
	snapshotMins, err := toDuration(snapshotPeriod, time.Minute, "snapshot")
	if err != nil {
		return probe.Periods{}, err
	}
	return probe.Periods{
		PollSecs:     pollSecs,
		PulseSecs:    pulseSecs,
		TrendHours:   trendHours,
		CacheHours:   cacheHours,
		SnapshotMins: snapshotMins,
	}, nil
}

const rootDescription = "Run supervisor processes"
