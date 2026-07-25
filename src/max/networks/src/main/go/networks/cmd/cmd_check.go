package cmd

import (
	"context"
	"fmt"
	"os"

	"networks/internal/engine"
	"networks/internal/plugin"
	"networks/internal/scribe"

	_ "networks/internal/plugins"

	"github.com/spf13/cobra"
)

func newCheckCmd() *cobra.Command {
	cmd := &cobra.Command{
		Use:   "check",
		Short: checkDescription,
		Long:  checkDescription,
		RunE: func(cmd *cobra.Command, args []string) error {
			if err := executeCheck(); err != nil {
				return fmt.Errorf("error [%w]", err)
			}
			return nil
		},
	}
	cmd.Flags().SortFlags = false
	return cmd
}

func executeCheck() error {
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
	e, err := engine.Create(engine.Options{Plugins: selected, PollPeriod: poll, AggregatePeriod: aggregate, PublishData: false})
	if err != nil {
		return err
	}
	for _, vitals := range e.Cycle(context.Background(), selected) {
		payload, err := vitals.MarshalJSON()
		if err != nil {
			return err
		}
		fmt.Fprintf(os.Stdout, "%s %s\n", vitals.Plugin, payload)
	}
	return nil
}

const checkDescription = "Run one aggregate cycle for the selected plugins, print vitals, and exit"
