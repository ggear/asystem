package engine

import (
	"errors"
	"fmt"
	"log/slog"
	"networks/internal/config"
	"networks/internal/plugin"
	"time"

	mqtt "github.com/eclipse/paho.mqtt.golang"
)

const (
	brokerStatusTopic      = "networks/status"
	brokerDataTopicPrefix  = "networks/data/"
	brokerCommandSubscribe = "networks/command/#"
	brokerCommandPrefix    = "networks/command"
	brokerResultTopic      = "networks/command/result"
	brokerStatusOnline     = "online"
	brokerStatusOffline    = "offline"
	brokerPublishTimeout   = 2 * time.Second
	brokerConnectTimeout   = 6 * time.Second
)

type brokerClient struct {
	client mqtt.Client
}

func (e *Engine) connectBroker() error {
	onConnect := func(client mqtt.Client) {
		client.Publish(brokerStatusTopic, 1, true, brokerStatusOnline)
		client.Subscribe(brokerCommandSubscribe, 1, e.onCommandMessage)
	}
	client, err := brokerConnect(onConnect, brokerStatusTopic, brokerStatusOffline)
	if err != nil {
		return err
	}
	e.broker = &brokerClient{client: client}
	return nil
}

func brokerConnect(onConnect func(mqtt.Client), willTopic, willPayload string) (mqtt.Client, error) {
	broker := config.Load().Broker()
	if broker == "" {
		return nil, errors.New("broker address is empty")
	}
	brokerURL := fmt.Sprintf("tcp://%s", broker)
	opts := mqtt.NewClientOptions().
		AddBroker(brokerURL).
		SetClientID(fmt.Sprintf("networks-publisher-%d", time.Now().UnixNano())).
		SetCleanSession(true).
		SetConnectTimeout(5 * time.Second).
		SetAutoReconnect(true).
		SetConnectRetry(true).
		SetMaxReconnectInterval(30 * time.Second).
		SetPassword(config.Load().BrokerToken()).
		SetOnConnectHandler(func(client mqtt.Client) {
			connectStart := time.Now()
			if onConnect != nil {
				onConnect(client)
			}
			slog.Info("state", "engine", "broker", "phase", "connect", "duration", time.Since(connectStart).Truncate(time.Millisecond))
		}).
		SetConnectionLostHandler(func(_ mqtt.Client, err error) {
			slog.Warn("state", "engine", "broker", "phase", "disconnect", "broker", brokerURL, "error", err)
		}).
		SetReconnectingHandler(func(_ mqtt.Client, _ *mqtt.ClientOptions) {
			slog.Warn("state", "engine", "broker", "phase", "reconnect", "broker", brokerURL)
		})
	if config.Load().BrokerToken() != "" {
		opts.SetUsername("networks")
	}
	opts.SetWill(willTopic, willPayload, 1, true)
	client := mqtt.NewClient(opts)
	token := client.Connect()
	if !token.WaitTimeout(brokerConnectTimeout) {
		slog.Warn("state", "engine", "broker", "phase", "connect", "broker", brokerURL, "error", "initial connect pending, retrying in background")
		return client, nil
	}
	if token.Error() != nil {
		return nil, fmt.Errorf("connect failed [%s] [%w]", brokerURL, token.Error())
	}
	return client, nil
}

func (b *brokerClient) publishAggregate(m plugin.Aggregate) {
	payload, err := m.MarshalJSON()
	if err != nil {
		slog.Warn("state", "engine", "broker", "phase", "publish", "plugin", m.Plugin, "error", err)
		return
	}
	b.client.Publish(brokerDataTopicPrefix+m.Plugin, 0, true, payload).WaitTimeout(brokerPublishTimeout)
	slog.Debug("state", "engine", "broker", "phase", "publish", "plugin", m.Plugin, "topic", brokerDataTopicPrefix+m.Plugin)
}

func (b *brokerClient) publishResult(m plugin.Aggregate) {
	payload, err := m.MarshalJSON()
	if err != nil {
		return
	}
	b.client.Publish(brokerResultTopic, 0, false, payload).WaitTimeout(brokerPublishTimeout)
}

func (b *brokerClient) disconnect() {
	b.client.Publish(brokerStatusTopic, 1, true, brokerStatusOffline).WaitTimeout(brokerPublishTimeout)
	b.client.Disconnect(2500)
}
