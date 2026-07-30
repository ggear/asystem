package engine

import (
	"context"
	"errors"
	"fmt"
	"log/slog"
	"networks/internal/config"
	"networks/internal/plugin"
	"strings"
	"time"

	mqtt "github.com/eclipse/paho.mqtt.golang"
)

const (
	brokerStatusTopic      = "networks/status"
	brokerDataTopicPrefix  = "networks/data/"
	brokerCommandSubscribe = "networks/command/#"
	brokerCommandPrefix    = "networks/command"
	brokerStatusOnline     = "online"
	brokerStatusOffline    = "offline"
	brokerPublishTimeout   = 2 * time.Second
	brokerConnectTimeout   = 6 * time.Second
)

type brokerClient struct {
	client mqtt.Client
}

func (e *Engine) connectBroker(ctx context.Context) error {
	onConnect := func(client mqtt.Client) {
		client.Publish(brokerStatusTopic, 1, true, brokerStatusOnline)
		client.Subscribe(brokerCommandSubscribe, 1, func(_ mqtt.Client, msg mqtt.Message) {
			topic := msg.Topic()
			if !strings.HasPrefix(topic, brokerCommandPrefix+"/") {
				return
			}
			name := strings.TrimPrefix(topic, brokerCommandPrefix+"/")
			state, ok := plugin.ParseState(string(msg.Payload()))
			if !ok {
				slog.Warn(fmt.Sprintf("plugin [%s] command ignored because payload [%s] is unparseable", name, string(msg.Payload())))
				return
			}
			e.runCommand(ctx, name, state)
		})
	}
	client, err := brokerConnect(onConnect, brokerStatusTopic, brokerStatusOffline)
	if err != nil {
		return err
	}
	e.broker = &brokerClient{client: client}
	return nil
}

func (e *Engine) runCommand(ctx context.Context, name string, state plugin.State) {
	p, ok := e.pluginByName(name)
	if !ok {
		slog.Warn(fmt.Sprintf("plugin [%s] command ignored because plugin is unknown", name))
		return
	}
	if err := p.Command(ctx, state); err != nil {
		slog.Warn(fmt.Sprintf("plugin [%s] command to state [%s] failed [%v]", name, state.String(), err))
		return
	}
	slog.Info(fmt.Sprintf("plugin [%s] command set state [%s]", name, state.String()))
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
			if onConnect != nil {
				onConnect(client)
			}
			slog.Info(fmt.Sprintf("connected to broker [%s]", broker))
		}).
		SetConnectionLostHandler(func(_ mqtt.Client, err error) {
			slog.Warn(fmt.Sprintf("disconnected from broker [%s] [%v]", broker, err))
		}).
		SetReconnectingHandler(func(_ mqtt.Client, _ *mqtt.ClientOptions) {
			slog.Info(fmt.Sprintf("reconnecting to broker [%s]", broker))
		})
	if config.Load().BrokerToken() != "" {
		opts.SetUsername("networks")
	}
	opts.SetWill(willTopic, willPayload, 1, true)
	client := mqtt.NewClient(opts)
	token := client.Connect()
	if !token.WaitTimeout(brokerConnectTimeout) {
		slog.Info(fmt.Sprintf("connecting to broker [%s]", broker))
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
		slog.Warn(fmt.Sprintf("plugin [%s] marshal for broker failed [%v]", m.Plugin, err))
		return
	}
	b.client.Publish(brokerDataTopicPrefix+m.Plugin, 0, true, payload).WaitTimeout(brokerPublishTimeout)
}

func (b *brokerClient) disconnect() {
	b.client.Publish(brokerStatusTopic, 1, true, brokerStatusOffline).WaitTimeout(brokerPublishTimeout)
	b.client.Disconnect(2500)
}
