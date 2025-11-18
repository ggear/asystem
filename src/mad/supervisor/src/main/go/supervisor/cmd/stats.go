package cmd

import (
	"fmt"
	"time"

	"github.com/spf13/cobra"
)

type statsOptions struct {
	mode       string
	format     string
	pollPeriod string
	noStream   bool
}

func newStatsCmd() *cobra.Command {
	opts := &statsOptions{}

	cmd := &cobra.Command{
		Use:     "stats [OPTIONS]",
		Aliases: []string{"atop"},
		Short:   "Show real-time system statistics",
		RunE: func(cmd *cobra.Command, args []string) error {
			return runStats(opts)
		},
	}

	cmd.Flags().StringVarP(&opts.mode, "mode", "m", "poll", "Method to retrieve stats: 'poll' or 'cache'")
	cmd.Flags().StringVarP(&opts.format, "format", "f", "auto", "Display format: 'auto', 'compact', or 'relaxed'")
	cmd.Flags().StringVarP(&opts.pollPeriod, "poll-period", "p", "1s", "Polling interval (default: '1s')")
	cmd.Flags().BoolVarP(&opts.noStream, "no-stream", "n", false, "Disable continuous streaming")

	return cmd
}

func runStats(opts *statsOptions) error {
	fmt.Printf("Mode: %s | Format: %s | Poll: %s | Stream: %v\n",
		opts.mode, opts.format, opts.pollPeriod, !opts.noStream)

	if opts.mode == "cache" {
		fmt.Println("Retrieving stats from cache...")
		return nil
	}

	d, err := time.ParseDuration(opts.pollPeriod)
	if err != nil {
		return fmt.Errorf("invalid poll period: %w", err)
	}

	for {
		fmt.Printf("→ CPU: 12%%  MEM: 73%%  DISK: 54%%\n")
		if opts.noStream {
			break
		}
		time.Sleep(d)
	}
	return nil
}

func init() {
	rootCmd.AddCommand(newStatsCmd())
}
