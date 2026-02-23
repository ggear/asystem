package cmd

import (
	"fmt"
	"log/slog"
	"os"
	"strings"
	"supervisor/internal/config"
	"supervisor/internal/dashboard"
	"supervisor/internal/metric"
	"supervisor/internal/scribe"

	"github.com/spf13/cobra"
	"golang.org/x/term"
)

type statsOptions struct {
	mode           string
	format         string
	pollPeriod     string
	pulseFactor    string
	trendPeriod    string
	cachePeriod    string
	snapshotPeriod string
	consoleWidth   int
	consoleHeight  int
	json           bool
}

func newStatsCmd() *cobra.Command {
	opts := &statsOptions{}
	cmd := &cobra.Command{
		Use:     "stats",
		Aliases: []string{"atop", "atops"},
		Short:   statsDescription,
		Long:    statsDescription,
		RunE: func(cmd *cobra.Command, args []string) error {
			if cmd.CalledAs() == "atops" && opts.mode == "local" {
				c, err := config.Load(config.DefaultConfigPath)
				if err != nil {
					return err
				}
				opts.mode = fmt.Sprintf("remote[%s]", strings.Join(c.Hosts(), ","))
			}
			err := executeStats(opts)
			if err != nil {
				return fmt.Errorf("error: %w", err)
			}
			return nil
		},
	}
	cmd.Flags().StringVarP(&opts.mode, "mode", "m", "local", "stats host selection and retrieval method: local, remote, or remote[:HOST[,HOST...]]")
	cmd.Flags().StringVarP(&opts.format, "format", "f", "auto", "output format based on grid cell width: auto, compact, or relaxed")
	cmd.Flags().StringVarP(&opts.pollPeriod, "poll-period", "P", "1s", "period for adding fast moving metric samples into a pulse window, ignored by slow moving metrics, uses unit suffixes [s, m, h]. (default: 1s)")
	cmd.Flags().StringVarP(&opts.pulseFactor, "pulse-factor", "F", "5", "factor applied to polling period to size pulse window, defining metric sample aggregation publish period for all metrics (default: 5)")
	cmd.Flags().StringVarP(&opts.trendPeriod, "trend-period", "T", "24h", "period to size trend window, published with pulse factor * poll period, ignored by non-trend tracked metrics, uses unit suffixes [s, m, h] (default: 24h)")
	cmd.Flags().StringVarP(&opts.cachePeriod, "cache-period", "C", "24h", "period to cache metric sample for, ignored by fast moving metrics, uses unit suffixes [s, m, h] (default: 24h)")
	cmd.Flags().StringVarP(&opts.snapshotPeriod, "snapshot-period", "S", "5m", "period for publishing a metric snapshot, uses unit suffixes [s, m, h] (default: 5m)")
	cmd.Flags().IntVarP(&opts.consoleWidth, "console-width", "W", -1, "override the console width with the specified value")
	cmd.Flags().IntVarP(&opts.consoleHeight, "console-height", "H", -1, "override the console height with the specified value")
	cmd.Flags().BoolVarP(&opts.json, "json", "J", false, "output JSON instead of the default text format. Assumes local mode, respects poll and bin period options and ignores all formating options")
	cmd.Flags().SortFlags = false
	return cmd
}

func executeStats(opts *statsOptions) error {
	err := scribe.EnableFile(slog.LevelDebug, "stats", 10, 3, 7)
	if err != nil {
		return err
	}

	// TODO: START
	//  - Implement JSON

	mode := opts.mode
	var isRemote bool
	var hosts []string
	switch {
	case mode == "local":
	case mode == "remote":
		if c, err := config.Load(config.DefaultConfigPath); err != nil {
			return err
		} else {
			hosts = c.Hosts()
		}
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
		return fmt.Errorf("invalid stats mode [%s]", mode)
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
	format := dashboard.FormatAuto
	switch strings.ToLower(opts.format) {
	case "auto":
		format = dashboard.FormatAuto
	case "compact":
		format = dashboard.FormatCompact
	case "relaxed":
		format = dashboard.FormatRelaxed
	default:
		return fmt.Errorf("invalid stats format [%s]", opts.format)
	}
	periods, err := makePeriods(opts.pollPeriod, opts.pulseFactor, opts.trendPeriod, opts.cachePeriod, opts.snapshotPeriod)
	if err != nil {
		return err
	}
	d, err := dashboard.NewDashboard(
		metric.NewRecordCache(),
		dashboard.TerminalFactory,
		hosts,
		width,
		height,
		format,
		periods,
		isRemote,
	)
	if err != nil {
		return err
	}
	_, err = d.Compile()
	if err != nil {
		return err
	}
	err = d.Load()
	if err != nil {
		return err
	}
	err = d.Display()
	if err != nil {
		return err
	}
	err = d.Update()
	if err != nil {
		return err
	}
	return d.Close()
}

func init() {
	rootCmd.AddCommand(newStatsCmd())
}

const statsDescription = "Show real-time system stats"
