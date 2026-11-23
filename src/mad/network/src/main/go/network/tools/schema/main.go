package main

import (
	"flag"
	"fmt"
	"os"

	"network/internal/config"
	"network/internal/plugin"
	"network/internal/schema"
)

func main() {
	cadence := flag.String("aggregate-period", config.DefaultAggregatePeriod,
		"cadence declared for every relation, matching the running service --aggregate-period")
	flag.Parse()
	database := plugin.Schema().WithCadence(*cadence)
	if err := schema.Reflect(os.Stdout, "network", database, plugin.BrokerSchema()); err != nil {
		_, _ = fmt.Fprintf(os.Stderr, "reflect failed [%v]\n", err)
		os.Exit(1)
	}
}
