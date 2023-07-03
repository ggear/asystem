package main

import (
	mqtt "github.com/eclipse/paho.mqtt.golang"
	"github.com/ggear/asystem/tree/master/src/meg/network/src/main/go/pkg"
	"github.com/joho/godotenv"
	"github.com/sirupsen/logrus"
	"testing"
)

func init() {
	pkg.ConfigLog(logrus.TraceLevel)
	godotenv.Load("../../../../.env")
}

func TestMQTTConnection(t *testing.T) {
	client := pkg.OpenMQTTClient("sys_test", []func(client mqtt.Client){})
	pkg.CloseMQTTClient(client)
}
