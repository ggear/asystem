package engine

import (
	"errors"
	"fmt"
	"log/slog"
	"supervisor/internal/config"
	"time"

	mqtt "github.com/eclipse/paho.mqtt.golang"
)

type brokerDeletesListener struct {
	client mqtt.Client
}

func (b *brokerDeletesListener) Unsubscribe(topic string) {
	b.client.Unsubscribe(topic)
}

type brokerPublishDeletesListener struct {
	client mqtt.Client
}

func (b *brokerPublishDeletesListener) Unsubscribe(topic string) {
	b.client.Publish(topic, 0, true, "")
}

func brokerConnect(configPath string, onConnect func(mqtt.Client), willTopic, willPayload string) (mqtt.Client, error) {
	broker := config.Load(configPath).Broker()
	if broker == "" {
		return nil, errors.New("broker address is empty")
	}
	brokerURL := fmt.Sprintf("tcp://%s", broker)
	opts := mqtt.NewClientOptions().
		AddBroker(brokerURL).
		SetClientID(fmt.Sprintf("supervisor-subscriber-%d", time.Now().UnixNano())).
		SetCleanSession(true).
		SetConnectTimeout(5 * time.Second).
		SetAutoReconnect(true).
		SetOnConnectHandler(func(client mqtt.Client) {
			connectStart := time.Now()
			if onConnect != nil {
				onConnect(client)
			}
			slog.Debug("state", "engine", "broker", "phase", "connect", "duration", time.Since(connectStart).Truncate(time.Millisecond), "broker", brokerURL)
		}).
		SetConnectionLostHandler(func(_ mqtt.Client, err error) {
			slog.Warn("state", "engine", "broker", "phase", "disconnect", "duration", "0s", "broker", brokerURL, "error", err)
		}).
		SetReconnectingHandler(func(_ mqtt.Client, _ *mqtt.ClientOptions) {
			slog.Debug("state", "engine", "broker", "phase", "reconnect", "duration", "0s", "broker", brokerURL)
		})
	if willTopic != "" {
		opts.SetWill(willTopic, willPayload, 1, true)
	}
	client := mqtt.NewClient(opts)
	token := client.Connect()
	token.Wait()
	if token.Error() != nil {
		return nil, fmt.Errorf("connect failed [%s]: %w", brokerURL, token.Error())
	}
	return client, nil
}
