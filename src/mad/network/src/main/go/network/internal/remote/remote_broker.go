package remote

import (
	"context"
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
	BrokerStatusOnline      = "online"
	BrokerStatusOffline     = "offline"
	brokerPublishTimeout    = 2 * time.Second
	brokerSubscribeQosMax   = 2
	brokerSubscribeAttempts = 5
	brokerSubscribeBackoff  = 2 * time.Second
	brokerConnectTimeout    = 6 * time.Second
	brokerCollectConnect    = 5 * time.Second
	brokerCollectWait       = 2 * time.Second
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
			if err := waitForBrokerToken(client.Publish(brokerStatusTopic, 1, true, BrokerStatusOnline)); err != nil {
				scribe.LogWarn(scribe.Global, "publishing online status to broker [%s] failed [%v]", address, err)
			}
			broker.republish(client)
			commandHandler := func(_ mqtt.Client, message mqtt.Message) {
				topic := message.Topic()
				if !strings.HasPrefix(topic, brokerCommandPrefix+"/") {
					return
				}
				onCommand(strings.TrimPrefix(topic, brokerCommandPrefix+"/"), message.Payload())
			}
			for attempt := 1; ; attempt++ {
				err := subscribeGranted(client.Subscribe(brokerCommandFilter, 1, commandHandler), brokerPublishTimeout)
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
	options.SetWill(brokerStatusTopic, BrokerStatusOffline, 1, true)
	client := mqtt.NewClient(options)
	broker.client = client
	connectToken := client.Connect()
	if !connectToken.WaitTimeout(brokerConnectTimeout) {
		scribe.LogInfo(scribe.Global, "connecting to broker [%s]", address)
	} else if connectToken.Error() != nil {
		return nil, fmt.Errorf("connect failed [%s] [%w]", brokerURL, connectToken.Error())
	}
	return broker, nil
}

func CollectMessages(ctx context.Context, address, token, client string, topics []string) (map[string][]byte, error) {
	if address == "" {
		return nil, errors.New("broker address is empty")
	}
	options := mqtt.NewClientOptions().
		AddBroker("tcp://" + address).
		SetClientID(fmt.Sprintf("network-%s-%d", client, time.Now().UnixNano())).
		SetCleanSession(true).
		SetConnectTimeout(brokerCollectConnect)
	if token != "" {
		options.SetUsername("network").SetPassword(token)
	}
	var messagesMu sync.Mutex
	messages := map[string][]byte{}
	collector := mqtt.NewClient(options)
	connectToken := collector.Connect()
	if !connectToken.WaitTimeout(brokerCollectConnect) || connectToken.Error() != nil {
		return nil, fmt.Errorf("connect failed [%s] [%w]", address, connectToken.Error())
	}
	defer collector.Disconnect(250)
	filters := make(map[string]byte, len(topics))
	for _, topic := range topics {
		filters[topic] = 0
	}
	handler := func(_ mqtt.Client, message mqtt.Message) {
		messagesMu.Lock()
		messages[message.Topic()] = append([]byte(nil), message.Payload()...)
		messagesMu.Unlock()
	}
	if err := subscribeGranted(collector.SubscribeMultiple(filters, handler), brokerCollectConnect); err != nil {
		return nil, fmt.Errorf("subscribe failed [%s] [%w]", strings.Join(topics, ", "), err)
	}
	select {
	case <-ctx.Done():
	case <-time.After(brokerCollectWait):
	}
	messagesMu.Lock()
	defer messagesMu.Unlock()
	return maps.Clone(messages), nil
}

func (b *Broker) PublishStatus() error {
	return waitForBrokerToken(b.client.Publish(brokerStatusTopic, 1, true, BrokerStatusOnline))
}

func (b *Broker) Publish(topic string, payload []byte) error {
	b.mu.Lock()
	b.retained[topic] = append([]byte(nil), payload...)
	b.mu.Unlock()
	return waitForBrokerToken(b.client.Publish(topic, 0, true, payload))
}

func (b *Broker) Close() error {
	err := waitForBrokerToken(b.client.Publish(brokerStatusTopic, 1, true, BrokerStatusOffline))
	b.client.Disconnect(2500)
	return err
}

func subscribeGranted(token mqtt.Token, timeout time.Duration) error {
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
