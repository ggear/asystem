package cmd

import (
	"context"
	"fmt"
	"os"
	"path/filepath"
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

func init() {
	rootCmd.AddCommand(newWatchCmd())
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
	cmd.Flags().StringVarP(&opts.theme, "theme", "t", "auto", "colour theme: auto, dark or light")
	cmd.Flags().StringVarP(&opts.pollPeriod, "poll-period", "P", "1s", "period for adding fast moving metric samples into a pulse window, ignored by slow moving metrics, uses unit suffixes [s, m, h]")
	cmd.Flags().StringVarP(&opts.pulseFactor, "pulse-factor", "F", "5", "factor applied to polling period to size pulse window, defining metric sample aggregation publish period for all metrics")
	cmd.Flags().StringVarP(&opts.heartbeatFactor, "heartbeat-period", "B", "5m", "period by which metrics are published even if they have not changed, rounded up to nearest pulse boundary, uses unit suffixes [s, m, h]")
	cmd.Flags().StringVarP(&opts.trendPeriod, "trend-period", "T", config.DefaultTrendPeriod, "period to size trend window, published with pulse factor * poll period, ignored by non-trend tracked metrics, uses unit suffixes [s, m, h]")
	cmd.Flags().StringVarP(&opts.cachePeriod, "cache-period", "C", config.DefaultCachePeriod, "period to cache metric sample for, ignored by fast moving metrics, uses unit suffixes [s, m, h]")
	cmd.Flags().StringVarP(&opts.snapshotPeriod, "snapshot-period", "S", "5m", "period for publishing a metric snapshot, uses unit suffixes [s, m, h]")
	cmd.Flags().StringVarP(&opts.refreshPeriod, "refresh-period", "R", "15m", "period for performing a full screen refresh, uses unit suffixes [s, m, h]")
	cmd.Flags().IntVarP(&opts.consoleWidth, "console-width", "W", -1, "override the console width with the specified value")
	cmd.Flags().IntVarP(&opts.consoleHeight, "console-height", "H", -1, "override the console height with the specified value")
	addLogFlags(cmd, &opts.logOptions, "debug")
	cmd.Flags().SortFlags = false
	cobra.AddTemplateFunc("join", strings.Join)
	cobra.AddTemplateFunc("trimLeadingWhitespaces", func(value string) string {
		return strings.TrimLeftFunc(value, unicode.IsSpace)
	})
	addAdvancedFlags(cmd, watchAdvancedFlags)
	return cmd
}

func executeWatch(configPath string, opts *watchOptions) error {
	watchStart := time.Now()
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
	level, err := makeLevel(opts.logLevel)
	if err != nil {
		return err
	}
	scribe.Widen(configuredHosts(configPath), configuredServices(configPath))
	logBuffer, err := scribe.EnableBufferAndFile(level, "watch", scribe.BufferLines(height), 10, 3, 7)
	if err != nil {
		return fmt.Errorf("enable file logging: %w", err)
	}
	if err := setLogFilters(&opts.logOptions); err != nil {
		return err
	}
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
			for h := range strings.SplitSeq(inner, ",") {
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
	if len(hosts) > 9 {
		return fmt.Errorf("maximum of 9 hosts supported [%d] requested", len(hosts))
	}
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
	var useUnicode bool
	switch strings.ToLower(opts.symbols) {
	case "auto":
		useUnicode = !(os.Getenv("TERM") == "linux" || os.Getenv("TERM") == "dumb" || os.Getenv("NO_UTF8") != "")
	case "ascii":
		useUnicode = false
	case "unicode":
		useUnicode = true
	default:
		return fmt.Errorf("invalid watch symbols [%s]", opts.symbols)
	}
	var theme display.Theme
	switch strings.ToLower(opts.theme) {
	case "auto":
		switch {
		case strings.EqualFold(os.Getenv("TERM_PROGRAM"), "Apple_Terminal"):
			theme = display.ThemeLight
		case os.Getenv("SSH_CLIENT") != "" || os.Getenv("SSH_TTY") != "":
			theme = display.ThemeLight
		default:
			theme = display.ThemeDark
		}
	case "dark":
		theme = display.ThemeDark
	case "light":
		theme = display.ThemeLight
	default:
		return fmt.Errorf("invalid watch theme [%s]", opts.theme)
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
		hosts,
		periods,
		configPath,
		isRemote,
		useUnicode,
		format,
		width,
		height,
		opts.consoleWidth,
		opts.consoleHeight,
		refreshPeriod,
		display.NewTerminalFactory(theme),
		metric.NewRecordCache(),
		logBuffer,
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
	loaded := config.Load(configPath)
	scribe.Log(scribe.SourceCmdWatch, scribe.SubjectHost(loaded.Host()), scribe.ActionStart).Infof("identity", watchStart, "[%s] version", loaded.Version())
	scribe.Log(scribe.SourceCmdWatch, scribe.SubjectHost(loaded.Host()), scribe.ActionStart).Infof("resolved", watchStart, "[%s] config", filepath.Base(configPath))
	scribe.Log(scribe.SourceCmdWatch, scribe.SubjectHost(loaded.Host()), scribe.ActionStart).Infof("selected", watchStart, "[%s] mode", mode)
	scribe.Log(scribe.SourceCmdWatch, scribe.SubjectHost(loaded.Host()), scribe.ActionStart).Infof("watching", watchStart, "[%d] hosts", len(hosts))
	scribe.Log(scribe.SourceCmdWatch, scribe.SubjectHost(loaded.Host()), scribe.ActionStart).Infof("included", watchStart, "[%s] hosts", includedHosts(hosts, loaded.Hosts()))
	scribe.Log(scribe.SourceCmdWatch, scribe.SubjectHost(loaded.Host()), scribe.ActionStart).Infof("periodic", watchStart, "[%d] ms poll", periods.PollMillis)
	scribe.Log(scribe.SourceCmdWatch, scribe.SubjectHost(loaded.Host()), scribe.ActionStart).Infof("periodic", watchStart, "[%d] ms pulse", periods.PulseMillis)
	go d.Run(ctx)
	d.Draw(ctx, cancel)
	scribe.Log(scribe.SourceCmdWatch, scribe.SubjectHost(loaded.Host()), scribe.ActionStop).Infof("identity", watchStart, "[%s] version, exited gracefully", loaded.Version())
	return nil
}

func includedHosts(selected, configured []string) string {
	if len(configured) > 0 && len(selected) == len(configured) {
		known := make(map[string]bool, len(configured))
		for _, host := range configured {
			known[host] = true
		}
		matched := true
		for _, host := range selected {
			if !known[host] {
				matched = false
				break
			}
		}
		if matched {
			return "*"
		}
	}
	return strings.Join(selected, ",")
}

type watchOptions struct {
	mode            string
	format          string
	symbols         string
	theme           string
	pollPeriod      string
	pulseFactor     string
	trendPeriod     string
	cachePeriod     string
	snapshotPeriod  string
	heartbeatFactor string
	refreshPeriod   string
	consoleWidth    int
	consoleHeight   int
	logOptions
}

var watchAdvancedFlags = []string{
	"poll-period",
	"pulse-factor",
	"heartbeat-period",
	"trend-period",
	"cache-period",
	"snapshot-period",
	"refresh-period",
	"log-level",
	"log-source",
	"log-subject",
	"log-action",
}

const watchDescription = "Show real-time system stats"
