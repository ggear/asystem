package main

import (
	"flag"
	"fmt"
	"os"

	"network/internal/config"
	"network/internal/plugins"
	"network/internal/schema"
)

func main() {
	cadence := flag.String("aggregate-period", config.DefaultAggregatePeriod,
		"cadence declared for every relation, matching the running service --aggregate-period")
	flag.Parse()
	database := plugins.Schema().WithCadence(*cadence)
	if reflectErr := schema.Reflect(os.Stdout, "network", database, plugins.BrokerSchema()); reflectErr != nil {
		_, reflectWriteErr := fmt.Fprintf(os.Stderr, "reflect failed [%v]\n", reflectErr)
		if reflectWriteErr != nil {
			return
		}
		os.Exit(1)
	}
}
