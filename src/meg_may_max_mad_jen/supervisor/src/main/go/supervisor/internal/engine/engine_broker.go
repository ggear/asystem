package engine

import (
	"errors"
	"fmt"
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

func brokerConnect(configPath string, onConnect func(mqtt.Client)) (mqtt.Client, error) {
	cfg, err := config.Load(configPath)
	if err != nil {
		return nil, fmt.Errorf("config load failed: %w", err)
	}
	broker := cfg.Broker()
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
		SetOnConnectHandler(onConnect)
	client := mqtt.NewClient(opts)
	token := client.Connect()
	token.Wait()
	if token.Error() != nil {
		return nil, fmt.Errorf("connect failed [%s]: %w", brokerURL, token.Error())
	}
	return client, nil
}
