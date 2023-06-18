package main

import (
	"github.com/ggear/asystem/tree/master/module/meg/internet/src/main/go/pkg"
	"github.com/joho/godotenv"
	"github.com/sirupsen/logrus"
	"testing"
)

func init() {
	pkg.DISABLE_MQTT = true
	pkg.DISABLE_INFLUXDB = true
	pkg.ConfigLog(logrus.TraceLevel)
	godotenv.Load("../../../../.env")
}

func TestConnectionNoOp(t *testing.T) {
	telemetry := pkg.New()
	telemetry.Open()
	telemetry.Close()
}
