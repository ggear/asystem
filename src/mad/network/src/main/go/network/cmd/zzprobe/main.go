package main

import (
	"context"
	"fmt"
	"os"
	"time"

	"network/internal/remote"
)

func main() {
	gateway, err := remote.NewGateway(os.Getenv("UNIFI_URL"), os.Getenv("UNIFI_SITE"), os.Getenv("UNIFI_USER"), os.Getenv("UNIFI_TOKEN"))
	if err != nil {
		panic(err)
	}
	for round := range 2 {
		ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
		devices, err := gateway.Devices(ctx)
		cancel()
		if err != nil {
			panic(err)
		}
		fmt.Printf("round %d at %s\n", round, time.Now().Format(time.TimeOnly))
		for _, d := range devices {
			up := 0
			for _, p := range d.PortTable {
				if p.Up {
					up++
				}
			}
			first := ""
			for _, p := range d.PortTable {
				if p.Up {
					first = fmt.Sprintf("port %d speed %d rx %d tx %d", p.PortIdx, p.Speed, p.RxBytes, p.TxBytes)
					break
				}
			}
			fmt.Printf("  %-20s state %d last_seen %d ports %d up %d uplink speed %d rx %d tx %d first %s\n", d.Name, d.State, d.LastSeen, len(d.PortTable), up, d.Uplink.Speed, d.Uplink.RxBytes, d.Uplink.TxBytes, first)
		}
		if round == 0 {
			time.Sleep(60 * time.Second)
		}
	}
}
