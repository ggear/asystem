package cmd

import (
	"fmt"
	"time"

	"github.com/spf13/cobra"
)

type runOptions struct {
	pollPeriod string
}

func newRunCmd() *cobra.Command {
	opts := &runOptions{}

	cmd := &cobra.Command{
		Use:   "run [OPTIONS]",
		Short: "Run the supervisor process to retrieve and publish stats from the system and perform supervisory duties",
		RunE: func(cmd *cobra.Command, args []string) error {
			return runSupervisor(opts)
		},
	}

	cmd.Flags().StringVarP(&opts.pollPeriod, "poll-period", "p", "1s",
		"Polling interval, uses unit suffixes [s, m, h] (default: \"1s\")")

	return cmd
}

func runSupervisor(opts *runOptions) error {
	d, err := time.ParseDuration(opts.pollPeriod)
	if err != nil {
		return fmt.Errorf("invalid poll period: %w", err)
	}

	fmt.Printf("Starting supervisor (poll interval: %s)\n", d)
	for {
		fmt.Println("→ Gathering system stats and supervising processes...")
		time.Sleep(d)
	}
}

func init() {
	rootCmd.AddCommand(newRunCmd())
}
