package remote

import (
	"errors"
	"fmt"
	"maps"
	"network/internal/scribe"
	"strings"
	"sync"
	"time"

	mqtt "github.com/eclipse/paho.mqtt.golang"
)

const (
	brokerStatusTopic       = "network/status"
	brokerDataTopicPrefix   = "network/data/"
	brokerCommandFilter     = "network/command/#"
	brokerCommandPrefix     = "network/command"
	brokerStatusOnline      = "online"
	brokerStatusOffline     = "offline"
	brokerPublishTimeout    = 2 * time.Second
	brokerSubscribeQosMax   = 2
	brokerSubscribeAttempts = 5
	brokerSubscribeBackoff  = 2 * time.Second
	brokerConnectTimeout    = 6 * time.Second
)

type Broker struct {
	client   mqtt.Client
	address  string
	mu       sync.Mutex
	retained map[string][]byte
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
	broker := &Broker{address: address, retained: make(map[string][]byte)}
	options := mqtt.NewClientOptions().
		AddBroker(brokerURL).
		SetClientID(fmt.Sprintf("network-publisher-%d", time.Now().UnixNano())).
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
			broker.republish(client)
			commandHandler := func(_ mqtt.Client, msg mqtt.Message) {
				topic := msg.Topic()
				if !strings.HasPrefix(topic, brokerCommandPrefix+"/") {
					return
				}
				onCommand(strings.TrimPrefix(topic, brokerCommandPrefix+"/"), msg.Payload())
			}
			for attempt := 1; ; attempt++ {
				err := SubscribeGranted(client.Subscribe(brokerCommandFilter, 1, commandHandler), brokerPublishTimeout)
				if err == nil {
					break
				}
				if attempt >= brokerSubscribeAttempts {
					scribe.LogWarn(scribe.Global, "subscribing to broker commands [%s] failed [%v] after [%d] attempts, commands are lost until the next reconnect", address, err, attempt)
					break
				}
				scribe.LogWarn(scribe.Global, "subscribing to broker commands [%s] failed [%v] on attempt [%d], retrying after [%d] ms", address, err, attempt, brokerSubscribeBackoff.Milliseconds())
				time.Sleep(brokerSubscribeBackoff)
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
		options.SetUsername("network")
	}
	options.SetWill(brokerStatusTopic, brokerStatusOffline, 1, true)
	client := mqtt.NewClient(options)
	broker.client = client
	tk := client.Connect()
	if !tk.WaitTimeout(brokerConnectTimeout) {
		scribe.LogInfo(scribe.Global, "connecting to broker [%s]", address)
	} else if tk.Error() != nil {
		return nil, fmt.Errorf("connect failed [%s] [%w]", brokerURL, tk.Error())
	}
	return broker, nil
}

func (b *Broker) PublishStatus() error {
	return waitForBrokerToken(b.client.Publish(brokerStatusTopic, 1, true, brokerStatusOnline))
}

func (b *Broker) Publish(topic string, payload []byte) {
	b.mu.Lock()
	b.retained[topic] = append([]byte(nil), payload...)
	b.mu.Unlock()
	b.client.Publish(topic, 0, true, payload).WaitTimeout(brokerPublishTimeout)
}

func (b *Broker) Close() error {
	tk := b.client.Publish(brokerStatusTopic, 1, true, brokerStatusOffline)
	err := waitForBrokerToken(tk)
	b.client.Disconnect(2500)
	return err
}

func SubscribeGranted(token mqtt.Token, timeout time.Duration) error {
	if !token.WaitTimeout(timeout) {
		return errors.New("broker subscribe timed out")
	}
	if err := token.Error(); err != nil {
		return err
	}
	granted, ok := token.(*mqtt.SubscribeToken)
	if !ok {
		return nil
	}
	for topic, code := range granted.Result() {
		if code > brokerSubscribeQosMax {
			return fmt.Errorf("broker refused topic [%s] with code [%d]", topic, code)
		}
	}
	return nil
}

func (b *Broker) republish(client mqtt.Client) {
	b.mu.Lock()
	replay := make(map[string][]byte, len(b.retained))
	maps.Copy(replay, b.retained)
	b.mu.Unlock()
	if len(replay) == 0 {
		return
	}
	for topic, payload := range replay {
		if err := waitForBrokerToken(client.Publish(topic, 0, true, payload)); err != nil {
			scribe.LogWarn(scribe.Global, "republishing retained topic [%s] to broker [%s] failed [%v]", topic, b.address, err)
		}
	}
	scribe.LogInfo(scribe.Global, "republished [%d] retained topic(s) to broker [%s]", len(replay), b.address)
}

func waitForBrokerToken(token mqtt.Token) error {
	if !token.WaitTimeout(brokerPublishTimeout) {
		return errors.New("broker operation timed out")
	}
	return token.Error()
}
