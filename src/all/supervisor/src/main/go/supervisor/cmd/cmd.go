package cmd

import (
	"encoding/json"
	"fmt"
	"log/slog"
	"os"
	"regexp"
	"sort"
	"strconv"
	"strings"
	"supervisor/internal/config"
	"supervisor/internal/scribe"
	"time"

	"github.com/spf13/cobra"
	"github.com/spf13/pflag"
)

func Execute() {
	if err := rootCmd.Execute(); err != nil {
		_, err := fmt.Fprintln(os.Stderr, err)
		if err != nil {
			return
		}
		os.Exit(1)
	}
}

func init() {
	cobra.AddTemplateFunc("bracketed", bracketed)
	cobra.AddTemplateFunc("vocabularies", vocabularies)
	rootCmd.SetUsageTemplate(usageTemplate)
	rootCmd.PersistentFlags().BoolP("version", "v", false, "display version information and exit")
	rootCmd.PersistentFlags().StringP("config", "c", config.DefaultConfigPath, "path to config file")
	rootCmd.Flags().SortFlags = false
	rootCmd.PersistentFlags().SortFlags = false
	rootCmd.InheritedFlags().SortFlags = false
}

func addAdvancedFlags(cmd *cobra.Command, advanced []string) {
	cmd.Flags().Bool(helpAllFlag, false, "show every flag, including the advanced ones, and the log vocabularies")
	for _, name := range advanced {
		_ = cmd.Flags().MarkHidden(name)
	}
	cmd.PreRun = func(command *cobra.Command, _ []string) {
		if all, _ := command.Flags().GetBool(helpAllFlag); !all {
			return
		}
		for _, name := range advanced {
			if flag := command.Flags().Lookup(name); flag != nil {
				flag.Hidden = false
			}
		}
		_ = command.Help()
		os.Exit(0)
	}
}

func vocabularies() string {
	path := config.DefaultConfigPath
	if flag := rootCmd.PersistentFlags().Lookup("config"); flag != nil && flag.Value.String() != "" {
		path = flag.Value.String()
	}
	data, err := os.ReadFile(path)
	if err != nil {
		return scribe.Vocabularies(nil)
	}
	var document struct {
		Asystem struct {
			Schema []struct {
				Services []string `json:"services"`
			} `json:"schema"`
		} `json:"asystem"`
	}
	if json.Unmarshal(data, &document) != nil {
		return scribe.Vocabularies(nil)
	}
	seen := map[string]bool{}
	var modules []string
	for _, entry := range document.Asystem.Schema {
		for _, service := range entry.Services {
			if service == "" || seen[service] {
				continue
			}
			seen[service] = true
			modules = append(modules, service)
		}
	}
	sort.Strings(modules)
	return scribe.Vocabularies(modules)
}

func bracketed(flags *pflag.FlagSet) string {
	lines := strings.Split(strings.TrimRight(flags.FlagUsages(), "\n"), "\n")
	for index, line := range lines {
		lines[index] = defaultPattern.ReplaceAllString(line, "(default [$1])")
	}
	return strings.Join(lines, "\n")
}

const helpAllFlag = "help-all"

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

func makeLevel(logLevel string) (slog.Level, error) {
	switch strings.ToLower(strings.TrimSpace(logLevel)) {
	case "debug":
		return slog.LevelDebug, nil
	case "info":
		return slog.LevelInfo, nil
	case "warn":
		return slog.LevelWarn, nil
	case "error":
		return slog.LevelError, nil
	default:
		return slog.LevelInfo, fmt.Errorf("invalid log level [%s], must be one of [debug, info, warn, error]", logLevel)
	}
}

type logOptions struct {
	logLevel   string
	logSource  string
	logSubject string
	logAction  string
}

func addLogFlags(cmd *cobra.Command, opts *logOptions, level string) {
	cmd.Flags().StringVarP(&opts.logLevel, "log-level", "L", level, "log level [debug, info, warn, error]")
	cmd.Flags().StringVarP(&opts.logSource, "log-source", "O", "", "log filter source comma-separated prefixes (see below)")
	cmd.Flags().StringVarP(&opts.logSubject, "log-subject", "U", "", "log filter subject comma-separated prefixes (see below)")
	cmd.Flags().StringVarP(&opts.logAction, "log-action", "A", "", "log filter action comma-separated prefixes (see below)")
}

func setLogFilters(opts *logOptions) error {
	return scribe.SetFilters(opts.logSource, opts.logSubject, opts.logAction)
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
{{bracketed .InheritedFlags}}{{end}}{{with .Flags.Lookup "log-source"}}{{if not .Hidden}}

{{vocabularies}}{{end}}{{end}}{{if .HasHelpSubCommands}}

Additional help topics:{{range .Commands}}{{if .IsAdditionalHelpTopicCommand}}
  {{rpad .CommandPath .CommandPathPadding}} {{.Short}}{{end}}{{end}}{{end}}{{if .HasAvailableSubCommands}}

Use "{{.CommandPath}} [command] --help" for more information about a command.{{end}}
`
