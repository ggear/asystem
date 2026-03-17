package cmd

import (
	"context"
	"fmt"
	"log/slog"
	"os"
	"strings"
	"supervisor/internal/config"
	"supervisor/internal/display"
	"supervisor/internal/metric"
	"supervisor/internal/scribe"
	"time"
	"unicode"

	"github.com/spf13/cobra"
	"golang.org/x/term"
)

type watchOptions struct {
	mode            string
	format          string
	symbols         string
	pollPeriod      string
	pulseFactor     string
	trendPeriod     string
	cachePeriod     string
	snapshotPeriod  string
	heartbeatFactor string
	refreshPeriod   string
	consoleWidth    int
	consoleHeight   int
	json            bool
}

// noinspection DuplicatedCode
func newWatchCmd() *cobra.Command {
	opts := &watchOptions{}
	cmd := &cobra.Command{
		Use:     "watch",
		Aliases: []string{"atop", "atops"},
		Short:   watchDescription,
		Long:    watchDescription,
		RunE: func(cmd *cobra.Command, args []string) error {
			configPath, _ := cmd.Flags().GetString("config")
			err := executeWatch(configPath, opts)
			if err != nil {
				return fmt.Errorf("error: %w", err)
			}
			return nil
		},
	}
	cmd.Flags().StringVarP(&opts.mode, "mode", "m", "local", "watch host selection and retrieval method: local, remote or remote[:HOST[,HOST...]]")
	cmd.Flags().StringVarP(&opts.format, "format", "f", "auto", "output format based on grid cell width: auto, compact or relaxed")
	cmd.Flags().StringVarP(&opts.symbols, "symbols", "s", "auto", "define output character set: auto, ascii or unicode")
	cmd.Flags().StringVarP(&opts.pollPeriod, "poll-period", "P", "1s", "period for adding fast moving metric samples into a pulse window, ignored by slow moving metrics, uses unit suffixes [s, m, h]. (default: 1s)")
	cmd.Flags().StringVarP(&opts.pulseFactor, "pulse-factor", "F", "5", "factor applied to polling period to size pulse window, defining metric sample aggregation publish period for all metrics (default: 5)")
	cmd.Flags().StringVarP(&opts.heartbeatFactor, "heartbeat-factor", "B", "60", "factor applied to pulse to time heart beat, period by which metrics are published even if they have not changed (default: 60)")
	cmd.Flags().StringVarP(&opts.trendPeriod, "trend-period", "T", "24h", "period to size trend window, published with pulse factor * poll period, ignored by non-trend tracked metrics, uses unit suffixes [s, m, h] (default: 24h)")
	cmd.Flags().StringVarP(&opts.cachePeriod, "cache-period", "C", "24h", "period to cache metric sample for, ignored by fast moving metrics, uses unit suffixes [s, m, h] (default: 24h)")
	cmd.Flags().StringVarP(&opts.snapshotPeriod, "snapshot-period", "S", "5m", "period for publishing a metric snapshot, uses unit suffixes [s, m, h] (default: 5m)")
	cmd.Flags().StringVarP(&opts.refreshPeriod, "refresh-period", "R", "15m", "period for performing a full screen refresh, uses unit suffixes [s, m, h] (default: 15m)")
	cmd.Flags().IntVarP(&opts.consoleWidth, "console-width", "W", -1, "override the console width with the specified value")
	cmd.Flags().IntVarP(&opts.consoleHeight, "console-height", "H", -1, "override the console height with the specified value")
	cmd.Flags().BoolVarP(&opts.json, "json", "J", false, "output JSON instead of the default text format. Assumes local mode, respects poll and bin period options and ignores all formating options")
	cmd.Flags().SortFlags = false
	cobra.AddTemplateFunc("join", strings.Join)
	cobra.AddTemplateFunc("trimLeadingWhitespaces", func(value string) string {
		return strings.TrimLeftFunc(value, unicode.IsSpace)
	})
	cmd.SetUsageTemplate(watchUsageTemplate)
	return cmd
}

func executeWatch(configPath string, opts *watchOptions) error {

	// TODO: START
	//  - Implement JSON

	mode := opts.mode
	var isRemote bool
	var hosts []string
	switch {
	case mode == "local":
	case mode == "remote":
		isRemote = true
		hosts = config.Load(configPath).Hosts()
	case strings.HasPrefix(mode, "remote[") && strings.HasSuffix(mode, "]"):
		isRemote = true
		inner := mode[len("remote[") : len(mode)-1]
		if inner != "" {
			parts := strings.Split(inner, ",")
			for _, h := range parts {
				if h = strings.TrimSpace(h); h != "" {
					hosts = append(hosts, h)
				}
			}
		}
	default:
		return fmt.Errorf("invalid watch mode [%s]", mode)
	}
	if len(hosts) == 0 {
		hostname, err := os.Hostname()
		if err != nil {
			return fmt.Errorf("unable to determine local hostname: %w", err)
		}
		hosts = []string{hostname}
	}
	width, height, err := term.GetSize(int(os.Stdout.Fd()))
	if err != nil {
		return err
	}
	if opts.consoleWidth > 0 && opts.consoleWidth < width {
		width = opts.consoleWidth
	}
	if opts.consoleHeight > 0 && opts.consoleHeight < height {
		height = opts.consoleHeight
	}
	logBuffer := scribe.EnableBuffer(slog.LevelDebug, height)
	format := display.FormatAuto
	switch strings.ToLower(opts.format) {
	case "auto":
		format = display.FormatAuto
	case "compact":
		format = display.FormatCompact
	case "relaxed":
		format = display.FormatRelaxed
	default:
		return fmt.Errorf("invalid watch format [%s]", opts.format)
	}
	var symbols display.Symbols
	switch strings.ToLower(opts.symbols) {
	case "auto":
		if os.Getenv("TERM") == "linux" || os.Getenv("TERM") == "dumb" || os.Getenv("NO_UTF8") != "" {
			symbols = display.SymbolsASCII
		} else {
			symbols = display.SymbolsUnicode
		}
	case "ascii":
		symbols = display.SymbolsASCII
	case "unicode":
		symbols = display.SymbolsUnicode
	default:
		return fmt.Errorf("invalid watch symbols [%s]", opts.symbols)
	}
	periods, err := makePeriods(opts.pollPeriod, opts.pulseFactor, opts.trendPeriod, opts.cachePeriod, opts.snapshotPeriod, opts.heartbeatFactor)
	if err != nil {
		return err
	}
	refreshPeriod, err := time.ParseDuration(opts.refreshPeriod)
	if err != nil {
		return fmt.Errorf("invalid refresh period: %w", err)
	}
	if refreshPeriod <= 0 {
		return fmt.Errorf("invalid refresh period: must be > 0")
	}
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	d, err := display.NewDisplay(
		metric.NewRecordCache(),
		display.TerminalFactory,
		hosts,
		width,
		height,
		opts.consoleWidth,
		opts.consoleHeight,
		format,
		symbols,
		periods,
		isRemote,
		configPath,
		logBuffer,
		refreshPeriod,
	)
	if err != nil {
		return err
	}
	defer d.Close()
	_, err = d.Compile()
	if err != nil {
		return err
	}
	err = d.Load()
	if err != nil {
		return err
	}
	go d.Run(ctx)
	d.Draw(ctx, cancel)
	return nil
}

func init() {
	rootCmd.AddCommand(newWatchCmd())
}

const watchDescription = "Show real-time system stats"

const watchUsageTemplate = `Usage:
   {{trimLeadingWhitespaces .UseLine}}{{if gt (len .Aliases) 0}}

Aliases:
   {{join .Aliases ", "}}{{end}}{{if .HasExample}}

Examples:
{{.Example}}{{end}}{{if .HasAvailableSubCommands}}

Available Commands:
{{range .Commands}}{{if (or .IsAvailableCommand .IsHelpCommand)}}  {{rpad .Name .NamePadding }} {{.Short}}{{end}}{{end}}{{end}}{{if .HasAvailableLocalFlags}}

Flags:
{{.LocalFlags.FlagUsages | trimTrailingWhitespaces}}{{end}}{{if .HasAvailableInheritedFlags}}

Global Flags:
{{.InheritedFlags.FlagUsages | trimTrailingWhitespaces}}{{end}}{{if .HasHelpSubCommands}}

Additional help topics:
{{range .Commands}}{{if .IsHelpCommand}}  {{rpad .CommandPath .CommandPathPadding}} {{.Short}}{{end}}{{end}}{{end}}

`
