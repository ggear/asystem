package main

import (
	"flag"
	"fmt"
	"os"

	"networks/internal/config"
	"networks/internal/plugins"
	"networks/internal/schema"
)

func main() {
	cadence := flag.String("aggregate-period", config.DefaultAggregatePeriod,
		"cadence declared for every relation, matching the running service --aggregate-period")
	flag.Parse()
	database := plugins.Schema().WithCadence(*cadence)
	if err := schema.Reflect(os.Stdout, "networks", database, plugins.BrokerSchema()); err != nil {
		fmt.Fprintf(os.Stderr, "reflect failed [%v]\n", err)
		os.Exit(1)
	}
}
