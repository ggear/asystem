package cmd

import (
	"fmt"

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
		Short:   "show real-time system statistics",
		RunE: func(cmd *cobra.Command, args []string) error {
			return executeStats(opts)
		},
	}
	cmd.Flags().StringVarP(&opts.mode, "mode", "m", "poll", "Method to retrieve stats: 'poll' or 'cache'")
	cmd.Flags().StringVarP(&opts.format, "format", "f", "auto", "Display format: 'auto', 'compact', or 'relaxed'")
	cmd.Flags().BoolVarP(&opts.noStream, "monochrome", "l", false, "Display in monochrome without ANSI escape colour coding sequences")
	cmd.Flags().StringVarP(&opts.pollPeriod, "poll-period", "p", "1s", "Polling interval (default: '1s')")
	cmd.Flags().BoolVarP(&opts.noStream, "no-stream", "n", false, "Disable continuous streaming")
	return cmd
}

func executeStats(opts *statsOptions) error {
	fmt.Printf("Mode: %s | Format: %s | Poll: %s | Stream: %v\n",
		opts.mode, opts.format, opts.pollPeriod, !opts.noStream)
	return nil
}

func init() {
	rootCmd.AddCommand(newStatsCmd())
}
