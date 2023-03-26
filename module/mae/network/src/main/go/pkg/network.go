package pkg

import (
	"fmt"
	mqtt "github.com/eclipse/paho.mqtt.golang"
	"github.com/sirupsen/logrus"
	"math/rand"
	"strings"
	"time"
)

type Telemetry struct {
	client mqtt.Client
}

func New() (*Telemetry, error) {
	return &Telemetry{}, nil
}

func GetMqttClient(subsribeHandlers []func(client mqtt.Client)) mqtt.Client {
	options := mqtt.NewClientOptions()
	options.AddBroker("mqtt://10.0.6.11:32404")
	options.SetClientID(fmt.Sprintf("network-%.6f", rand.Float64()))
	options.SetKeepAlive(10 * time.Minute)
	options.SetPingTimeout(10 * time.Second)
	options.SetAutoReconnect(true)
	options.SetConnectRetry(true)
	options.SetMaxReconnectInterval(3 * time.Minute)
	options.SetOnConnectHandler(func(client mqtt.Client) {
		for _, subsribeHandler := range subsribeHandlers {
			subsribeHandler(client)
		}
	})
	options.SetReconnectingHandler(func(client mqtt.Client, options *mqtt.ClientOptions) {
		options.SetClientID(fmt.Sprintf("network-%.6f", rand.Float64()))
	})
	client := mqtt.NewClient(options)
	if token := client.Connect(); token.Wait() && token.Error() != nil {
		logrus.Error(token.Error())
		panic(token.Error())
	}
	return client
}

func (telemetry *Telemetry) Connect(subsribeHandlers ...func(client mqtt.Client)) (*Telemetry, error) {
	telemetry.Disconnect()
	telemetry.client = GetMqttClient(subsribeHandlers)
	return telemetry, nil
}

func (telemetry *Telemetry) Disconnect() {
	if telemetry.client != nil && telemetry.client.IsConnected() {
		telemetry.client.Disconnect(250)
	}
}

func (telemetry *Telemetry) SwitchListener(switched func(state string)) {
	topic := "network/telemetry-refresh"
	if token := telemetry.client.Subscribe(topic+"/set", 1, func(client mqtt.Client, message mqtt.Message) {
		state := "OFF"
		if strings.ToUpper(string(message.Payload())) == "ON" {
			state = "ON"
		}
		if token := client.Publish(topic, 1, true, `{ "state": "`+state+`" }`); token.Wait() && token.Error() != nil {
			logrus.Error(token.Error())
		}
		switched(state)
		if state == "ON" {
			if token := client.Publish(topic, 1, true, `{ "state": "OFF" }`); token.Wait() && token.Error() != nil {
				logrus.Error(token.Error())
			}
		}
	}); token.Wait() && token.Error() != nil {
		logrus.Error(token.Error())
	}
}

func GetStatus(message string) string {
	return fmt.Sprintf("%s", message)
}
