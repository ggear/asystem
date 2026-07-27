package cmd

import (
	"context"
	"fmt"
	"os"
	"os/signal"

	"networks/internal/engine"
	"networks/internal/plugin"
	"networks/internal/scribe"

	_ "networks/internal/plugins"

	"github.com/spf13/cobra"
)

func newServeCmd() *cobra.Command {
	cmd := &cobra.Command{
		Use:   "serve",
		Short: serveDescription,
		Long:  serveDescription,
		RunE: func(cmd *cobra.Command, args []string) error {
			if err := executeServe(); err != nil {
				return fmt.Errorf("error [%w]", err)
			}
			return nil
		},
	}
	cmd.Flags().SortFlags = false
	return cmd
}

func executeServe() error {
	level, err := scribe.ParseLevel(flagLogLevel)
	if err != nil {
		return err
	}
	scribe.EnableStdout(level)
	poll, aggregate, err := makePeriods(flagPollPeriod, flagAggregatePeriod)
	if err != nil {
		return err
	}
	selected, err := plugin.Filter(pluginNames())
	if err != nil {
		return err
	}
	e, err := engine.Create(engine.Options{Plugins: selected, PollPeriod: poll, AggregatePeriod: aggregate, PublishData: flagPublishData})
	if err != nil {
		return err
	}
	ctx, cancel := signal.NotifyContext(context.Background(), os.Interrupt)
	defer cancel()
	if err := e.Run(ctx); err != nil && ctx.Err() == nil {
		return err
	}
	return nil
}

const serveDescription = "Run the network health monitor daemon, polling plugins and publishing aggregates"
