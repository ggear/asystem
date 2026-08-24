package cmd

import (
	"fmt"
	"os"
	"regexp"
	"strconv"
	"strings"
	"supervisor/internal/config"
	"time"

	"github.com/spf13/cobra"
	"github.com/spf13/pflag"
)

func Execute() {
	if err := rootCmd.Execute(); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}

func init() {
	cobra.AddTemplateFunc("bracketed", bracketed)
	rootCmd.SetUsageTemplate(usageTemplate)
	rootCmd.PersistentFlags().BoolP("version", "v", false, "display version information and exit")
	rootCmd.PersistentFlags().StringP("config", "c", config.DefaultConfigPath, "path to config file")
	rootCmd.Flags().SortFlags = false
	rootCmd.PersistentFlags().SortFlags = false
	rootCmd.InheritedFlags().SortFlags = false
}

func bracketed(flags *pflag.FlagSet) string {
	lines := strings.Split(strings.TrimRight(flags.FlagUsages(), "\n"), "\n")
	for index, line := range lines {
		lines[index] = defaultPattern.ReplaceAllString(line, "(default [$1])")
	}
	return strings.Join(lines, "\n")
}

var defaultPattern = regexp.MustCompile(`\(default "?(.*?)"?\)$`)

var rootCmd = &cobra.Command{
	Short:         rootDescription,
	Long:          rootDescription,
	SilenceUsage:  true,
	SilenceErrors: true,
	RunE: func(cmd *cobra.Command, args []string) error {
		showVersion, _ := cmd.Flags().GetBool("version")
		if showVersion {
			configPath, _ := cmd.Flags().GetString("config")
			fmt.Println(config.Load(configPath).Version())
			os.Exit(0)
		}
		if len(args) == 0 {
			return cmd.Help()
		}
		return nil
	},
}

func makePeriods(pollPeriod, pulseFactor, trendPeriod, cachePeriod, snapshotPeriod, heartbeatPeriod string) (config.Periods, error) {
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
	pollDuration, err := time.ParseDuration(pollPeriod)
	if err != nil {
		return config.Periods{}, fmt.Errorf("invalid poll period: %w", err)
	}
	if pollDuration <= 0 {
		return config.Periods{}, fmt.Errorf("invalid poll period: must be > 0")
	}
	pollMillis := int(pollDuration / time.Millisecond)
	pulseFactorInt, err := strconv.Atoi(pulseFactor)
	if err != nil {
		return config.Periods{}, fmt.Errorf("invalid pulse factor: %w", err)
	}
	if pulseFactorInt < 1 {
		return config.Periods{}, fmt.Errorf("invalid pulse factor: must be >= 1")
	}
	pulseMillis := pulseFactorInt * pollMillis
	trendHours, err := toDuration(trendPeriod, time.Hour, "trend")
	if err != nil {
		return config.Periods{}, err
	}
	cacheMins, err := toDuration(cachePeriod, time.Minute, "cache")
	if err != nil {
		return config.Periods{}, err
	}
	snapshotMins, err := toDuration(snapshotPeriod, time.Minute, "snapshot")
	if err != nil {
		return config.Periods{}, err
	}
	heartbeatDuration, err := time.ParseDuration(heartbeatPeriod)
	if err != nil {
		return config.Periods{}, fmt.Errorf("invalid heartbeat period: %w", err)
	}
	if heartbeatDuration <= 0 {
		return config.Periods{}, fmt.Errorf("invalid heartbeat period: must be > 0")
	}
	heartbeatMillis := int(heartbeatDuration / time.Millisecond)
	heartbeatSecs := (heartbeatMillis + pulseMillis - 1) / pulseMillis * pulseMillis / 1000
	return config.Periods{
		PollMillis:    pollMillis,
		PulseMillis:   pulseMillis,
		TrendHours:    trendHours,
		CacheMins:     cacheMins,
		SnapshotMins:  snapshotMins,
		HeartbeatSecs: heartbeatSecs,
	}, nil
}

const rootDescription = "Run supervisor processes"

const usageTemplate = `Usage:{{if .Runnable}}
  {{.UseLine}}{{end}}{{if .HasAvailableSubCommands}}
  {{.CommandPath}} [command]{{end}}{{if gt (len .Aliases) 0}}

Aliases:
  {{.NameAndAliases}}{{end}}{{if .HasExample}}

Examples:
{{.Example}}{{end}}{{if .HasAvailableSubCommands}}

Available Commands:{{range .Commands}}{{if (or .IsAvailableCommand (eq .Name "help"))}}
  {{rpad .Name .NamePadding }} {{.Short}}{{end}}{{end}}{{end}}{{if .HasAvailableLocalFlags}}

Flags:
{{bracketed .LocalFlags}}{{end}}{{if .HasAvailableInheritedFlags}}

Global Flags:
{{bracketed .InheritedFlags}}{{end}}{{if .HasHelpSubCommands}}

Additional help topics:{{range .Commands}}{{if .IsAdditionalHelpTopicCommand}}
  {{rpad .CommandPath .CommandPathPadding}} {{.Short}}{{end}}{{end}}{{end}}{{if .HasAvailableSubCommands}}

Use "{{.CommandPath}} [command] --help" for more information about a command.{{end}}
`
