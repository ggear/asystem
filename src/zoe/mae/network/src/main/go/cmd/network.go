package main

import (
	mqtt "github.com/eclipse/paho.mqtt.golang"
	"github.com/ggear/asystem/tree/master/module/mae/network/src/main/go/pkg"
	"github.com/sirupsen/logrus"
	"github.com/spf13/cobra"
	"math"
	"math/rand"
	"os"
	"os/signal"
	"syscall"
	"time"
)

const periodDefault = 15 * 60

var telemetry *pkg.Telemetry

var RootCmd = &cobra.Command{
	Use: "network",
	Run: func(cmd *cobra.Command, args []string) {
		period, _ := cmd.Flags().GetFloat64("period")
		if period == 0 {
			pkg.ConfigLog(logrus.DebugLevel)
			telemetry.Open()
			logrus.Info("Server is running once ... ")
		} else {
			pkg.ConfigLog(logrus.InfoLevel)
			telemetry.Open(func(client mqtt.Client) {
				pkg.SwitchListener(client, func(state string) {
					if state == "ON" {
						logrus.Info("Server is switched on to run ... ")
					}
				})
			})
			if period < 0 {
				period := time.Duration(math.Abs(period)) * time.Hour
				for {
					logrus.Infof("Server is waking up to sleep for another [%v] ... ", period)
					time.Sleep(period)
				}
			} else {
				for {
					period := time.Duration(rand.Float64()*period/2+period/2) * time.Second
					logrus.Infof("Server is waking up to run and then sleep for [%v] ... ", period)
					time.Sleep(period)
				}
			}
		}
	},
}

func init() {
	pkg.ConfigLog(logrus.InfoLevel)
	RootCmd.Flags().Float64P("period", "p", periodDefault,
		"network telemetry gather loop polling period:\n"+
			"if 0: run once, with debug statements and then exit, without responding to commands\n"+
			"if <0: wakeup and then return to sleep every abs(period) hours, responding to commands\n"+
			"if >0: wakeup and run within range [period/2, period] seconds, responding to commands",
	)
	telemetry = pkg.New()
}

func destroy() {
	telemetry.Close()
}

func main() {
	channel := make(chan os.Signal, 0)
	signal.Notify(channel, os.Interrupt, syscall.SIGTERM)
	go func() {
		<-channel
		destroy()
		os.Exit(1)
	}()
	code := 0
	if err := RootCmd.Execute(); err != nil {
		code = 2
		logrus.Error(err)
	}
	defer destroy()
	os.Exit(code)
}
