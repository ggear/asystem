package main

import (
	mqtt "github.com/eclipse/paho.mqtt.golang"
	"github.com/ggear/asystem/tree/master/module/mae/network/src/main/go/pkg"
	"github.com/sirupsen/logrus"
	"github.com/spf13/cobra"
	"math"
	"math/rand"
	"os"
	"time"
)

const periodDefault = 15 * 60

var RootCmd = &cobra.Command{
	Use: "network",
	Run: func(cmd *cobra.Command, args []string) {
		period, _ := cmd.Flags().GetFloat64("period")
		telemetry, _ := pkg.New()
		if period == 0 {
			logrus.SetLevel(logrus.DebugLevel)
			telemetry.Connect()
			logrus.Info("Server is running once ... ")
		} else {
			telemetry.Connect(func(client mqtt.Client) {
				telemetry.SwitchListener(func(state string) {
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
				period := time.Duration(rand.Float64()*period/2+period/2) * time.Second
				for {
					logrus.Infof("Server is waking up to run and then sleep for [%v] ... ", period)
					time.Sleep(period)
				}
			}
		}
	},
}

func init() {
	customFormatter := new(logrus.TextFormatter)
	customFormatter.TimestampFormat = "2006-01-02 15:04:05"
	customFormatter.FullTimestamp = true
	logrus.SetFormatter(customFormatter)
	logrus.SetLevel(logrus.InfoLevel)
	RootCmd.Flags().Float64P("period", "p", periodDefault,
		"network telemetry gather loop polling period:\n"+
			"if 0: run once, with debug statements and then exit, without responding to commands\n"+
			"if <0: wakeup and then return to sleep every abs(period) hours, responding to commands\n"+
			"if >0: wakeup and run within range [period/2, period] seconds, responding to commands",
	)
}

func main() {
	if err := RootCmd.Execute(); err != nil {
		logrus.Error(err)
		os.Exit(1)
	}
}
