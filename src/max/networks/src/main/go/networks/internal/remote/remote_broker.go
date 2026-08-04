package remote

import (
	"errors"
	"fmt"
	"networks/internal/scribe"
	"strings"
	"time"

	mqtt "github.com/eclipse/paho.mqtt.golang"
)

const (
	brokerStatusTopic     = "networks/status"
	brokerDataTopicPrefix = "networks/data/"
	brokerCommandFilter   = "networks/command/#"
	brokerCommandPrefix   = "networks/command"
	brokerStatusOnline    = "online"
	brokerStatusOffline   = "offline"
	brokerPublishTimeout  = 2 * time.Second
	brokerConnectTimeout  = 6 * time.Second
)

type Broker struct {
	client mqtt.Client
}

func DataTopic(name string) string { return brokerDataTopicPrefix + name }

func NewBroker(address, token string, onCommand func(name string, payload []byte)) (*Broker, error) {
	if address == "" {
		return nil, errors.New("broker address is empty")
	}
	if onCommand == nil {
		return nil, errors.New("broker command handler is nil")
	}
	brokerURL := fmt.Sprintf("tcp://%s", address)
	options := mqtt.NewClientOptions().
		AddBroker(brokerURL).
		SetClientID(fmt.Sprintf("networks-publisher-%d", time.Now().UnixNano())).
		SetCleanSession(true).
		SetConnectTimeout(5 * time.Second).
		SetAutoReconnect(true).
		SetConnectRetry(true).
		SetMaxReconnectInterval(30 * time.Second).
		SetPassword(token).
		SetOnConnectHandler(func(client mqtt.Client) {
			if err := waitForBrokerToken(client.Publish(brokerStatusTopic, 1, true, brokerStatusOnline)); err != nil {
				scribe.LogWarn(scribe.Global, "publishing online status to broker [%s] failed [%v]", address, err)
			}
			commandToken := client.Subscribe(brokerCommandFilter, 1, func(_ mqtt.Client, msg mqtt.Message) {
				topic := msg.Topic()
				if !strings.HasPrefix(topic, brokerCommandPrefix+"/") {
					return
				}
				onCommand(strings.TrimPrefix(topic, brokerCommandPrefix+"/"), msg.Payload())
			})
			if err := waitForBrokerToken(commandToken); err != nil {
				scribe.LogWarn(scribe.Global, "subscribing to broker commands [%s] failed [%v]", address, err)
			}
			scribe.LogInfo(scribe.Global, "connected to broker [%s]", address)
		}).
		SetConnectionLostHandler(func(_ mqtt.Client, err error) {
			scribe.LogWarn(scribe.Global, "disconnected from broker [%s] [%v]", address, err)
		}).
		SetReconnectingHandler(func(_ mqtt.Client, _ *mqtt.ClientOptions) {
			scribe.LogInfo(scribe.Global, "reconnecting to broker [%s]", address)
		})
	if token != "" {
		options.SetUsername("networks")
	}
	options.SetWill(brokerStatusTopic, brokerStatusOffline, 1, true)
	client := mqtt.NewClient(options)
	tk := client.Connect()
	if !tk.WaitTimeout(brokerConnectTimeout) {
		scribe.LogInfo(scribe.Global, "connecting to broker [%s]", address)
	} else if tk.Error() != nil {
		return nil, fmt.Errorf("connect failed [%s] [%w]", brokerURL, tk.Error())
	}
	return &Broker{client: client}, nil
}

func (b *Broker) Publish(topic string, payload []byte) {
	b.client.Publish(topic, 0, true, payload).WaitTimeout(brokerPublishTimeout)
}

func (b *Broker) Close() error {
	tk := b.client.Publish(brokerStatusTopic, 1, true, brokerStatusOffline)
	err := waitForBrokerToken(tk)
	b.client.Disconnect(2500)
	return err
}

func waitForBrokerToken(token mqtt.Token) error {
	if !token.WaitTimeout(brokerPublishTimeout) {
		return errors.New("broker operation timed out")
	}
	return token.Error()
}
