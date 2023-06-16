package pkg

import (
	"fmt"
	mqtt "github.com/eclipse/paho.mqtt.golang"
	"github.com/sirupsen/logrus"
	"log"
	"math"
	"math/rand"
	"os"
	"strings"
	"time"
)

var (
	DISABLE_MQTT     = false
	DISABLE_INFLUXDB = false
)

type Telemetry struct {
	client mqtt.Client
}

func ConfigLog(level logrus.Level) {
	formatter := new(logrus.TextFormatter)
	formatter.TimestampFormat = "2006/01/02 15:04:05"
	formatter.PadLevelText = true
	formatter.ForceColors = true
	formatter.FullTimestamp = true
	logrus.SetFormatter(formatter)
	logrus.SetLevel(level)
	if level == logrus.TraceLevel {
		logMQTT := log.New(os.Stdout, "TRACE  [", log.Ldate|log.Ltime)
		mqtt.DEBUG = logMQTT
		mqtt.WARN = logMQTT
		mqtt.ERROR = logMQTT
		mqtt.CRITICAL = logMQTT
	}
}

func OpenMQTTClient(cliendID string, subsribeHandlers []func(client mqtt.Client)) mqtt.Client {
	clientID := cliendID[:int(math.Min(float64(len(cliendID)), 10))]
	brokerURL := fmt.Sprintf("mqtt://%v:%v", os.Getenv("VERNEMQ_IP"), os.Getenv("VERNEMQ_PORT"))
	options := mqtt.NewClientOptions()
	options.AddBroker(brokerURL)
	options.SetClientID(fmt.Sprintf("%v-%.6f", cliendID, rand.Float64()))
	options.SetKeepAlive(10 * time.Minute)
	options.SetPingTimeout(10 * time.Second)
	options.SetAutoReconnect(true)
	options.SetConnectRetry(true)
	options.SetMaxReconnectInterval(3 * time.Minute)
	options.SetOnConnectHandler(func(client mqtt.Client) {
		for _, subscribeHandler := range subsribeHandlers {
			subscribeHandler(client)
		}
	})
	options.SetReconnectingHandler(func(client mqtt.Client, options *mqtt.ClientOptions) {
		options.SetClientID(fmt.Sprintf("%v-%.6f", clientID, rand.Float64()))
	})
	client := mqtt.NewClient(options)
	if token := client.Connect(); token.Wait() && token.Error() != nil {
		logrus.Errorf("Failed to connect to MQTT broker at [%v] with error [%v]", brokerURL, token.Error())
		panic(token.Error())
	}
	logrus.Debugf("Connected to MQTT broker at [%v]", brokerURL)
	return client
}

func CloseMQTTClient(client mqtt.Client) {
	if client != nil && client.IsConnected() {
		client.Disconnect(250)
		logrus.Debug("Disconnected from MQTT broker")
	}
}

func SwitchListener(client mqtt.Client, switched func(state string)) {
	topic := "network/telemetry-refresh"
	if token := client.Subscribe(topic+"/set", 1, func(client mqtt.Client, message mqtt.Message) {
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

func New() *Telemetry {
	return &Telemetry{}
}

func (telemetry *Telemetry) Open(subsribeHandlers ...func(client mqtt.Client)) (*Telemetry, error) {
	if !DISABLE_MQTT {
		telemetry.Close()
		telemetry.client = OpenMQTTClient("network", subsribeHandlers)
	}
	return telemetry, nil
}

func (telemetry *Telemetry) Close() {
	if !DISABLE_MQTT {
		CloseMQTTClient(telemetry.client)
	}
}
