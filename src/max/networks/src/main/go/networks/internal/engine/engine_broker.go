package engine

import (
	"context"
	"errors"
	"fmt"
	"networks/internal/config"
	"networks/internal/plugin"
	"networks/internal/scribe"
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
				scribe.Warnf(name, "command ignored because payload [%s] is unparseable", string(msg.Payload()))
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
	p, ok := e.findPlugin(name)
	if !ok {
		scribe.Warnf(name, "command ignored because plugin is unknown")
		return
	}
	if err := p.Command(ctx, state); err != nil {
		scribe.Warnf(name, "command to state [%s] failed [%v]", state.String(), err)
		return
	}
	scribe.Infof(name, "command received to set state to [%s]", state.String())
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
			scribe.Infof(scribe.Global, "connected to broker [%s]", broker)
		}).
		SetConnectionLostHandler(func(_ mqtt.Client, err error) {
			scribe.Warnf(scribe.Global, "disconnected from broker [%s] [%v]", broker, err)
		}).
		SetReconnectingHandler(func(_ mqtt.Client, _ *mqtt.ClientOptions) {
			scribe.Infof(scribe.Global, "reconnecting to broker [%s]", broker)
		})
	if config.Load().BrokerToken() != "" {
		opts.SetUsername("networks")
	}
	opts.SetWill(willTopic, willPayload, 1, true)
	client := mqtt.NewClient(opts)
	token := client.Connect()
	if !token.WaitTimeout(brokerConnectTimeout) {
		scribe.Infof(scribe.Global, "connecting to broker [%s]", broker)
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
		scribe.Warnf(m.Plugin, "marshal for broker failed [%v]", err)
		return
	}
	b.client.Publish(brokerDataTopicPrefix+m.Plugin, 0, true, payload).WaitTimeout(brokerPublishTimeout)
}

func (b *brokerClient) disconnect() {
	b.client.Publish(brokerStatusTopic, 1, true, brokerStatusOffline).WaitTimeout(brokerPublishTimeout)
	b.client.Disconnect(2500)
}
