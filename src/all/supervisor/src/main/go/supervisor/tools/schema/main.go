package main

import (
	"flag"
	"fmt"
	"os"
	"strconv"

	"supervisor/internal/config"
	"supervisor/internal/metric"
	"supervisor/internal/schema"
)

func main() {
	pollPeriod := flag.String("poll-period", config.DefaultPollPeriod,
		"poll period of the running service, sized with the pulse factor into the declared cadence")
	pulseFactor := flag.String("pulse-factor", config.DefaultPulseFactor,
		"pulse factor of the running service, sizing the poll period into the declared cadence")
	flag.Parse()
	factor, err := strconv.Atoi(*pulseFactor)
	if err != nil {
		fmt.Fprintf(os.Stderr, "invalid pulse factor [%s] [%v]\n", *pulseFactor, err)
		os.Exit(1)
	}
	cadence := metric.Cadence(*pollPeriod, factor)
	database := schema.Database(metric.Relations(nil, nil, cadence))
	if err := schema.Reflect(os.Stdout, "supervisor", database, schema.Broker{Payload: metric.Payloads(), Topic: metric.Topics()}); err != nil {
		fmt.Fprintf(os.Stderr, "reflect failed [%v]\n", err)
		os.Exit(1)
	}
}
