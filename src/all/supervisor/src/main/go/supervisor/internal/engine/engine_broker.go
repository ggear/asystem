package engine

import (
	"context"
	"errors"
	"fmt"
	"log/slog"
	"supervisor/internal/config"
	"sync/atomic"
	"time"

	mqtt "github.com/eclipse/paho.mqtt.golang"
)

type brokerDeletesListener struct {
	client   mqtt.Client
	onDelete func(topic string)
}

func (b *brokerDeletesListener) MarkDelete(topic string) {
	if b.onDelete != nil {
		b.onDelete(topic)
	}
	b.client.Unsubscribe(topic)
}

type brokerPublishDeletesListener struct {
	client mqtt.Client
}

func (b *brokerPublishDeletesListener) MarkDelete(topic string) {
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
		SetConnectTimeout(brokerConnectTimeout).
		SetKeepAlive(brokerKeepAlive).
		SetPingTimeout(brokerPingTimeout).
		SetMaxReconnectInterval(brokerReconnectMax).
		SetAutoReconnect(true).
		SetPassword(config.Load(configPath).BrokerToken()).
		SetOnConnectHandler(func(client mqtt.Client) {
			connectStart := time.Now()
			if onConnect != nil {
				onConnect(client)
			}
			slog.Info("state", "engine", "broker", "phase", "connect", "duration", time.Since(connectStart), "detail", fmt.Sprintf("connected to [%s]", brokerURL))
		}).
		SetConnectionLostHandler(func(_ mqtt.Client, err error) {
			slog.Warn("state", "engine", "broker", "phase", "disconnect", "detail", fmt.Sprintf("lost connection to [%s] with [%v]", brokerURL, err))
		}).
		SetReconnectingHandler(func(_ mqtt.Client, _ *mqtt.ClientOptions) {
			slog.Warn("state", "engine", "broker", "phase", "reconnect", "detail", fmt.Sprintf("reconnecting to [%s]", brokerURL))
		})
	if willTopic != "" {
		opts.SetWill(willTopic, willPayload, 1, true)
	}
	client := mqtt.NewClient(opts)
	token := client.Connect()
	token.Wait()
	if token.Error() != nil {
		return nil, fmt.Errorf("connect failed [%s] [%w]", brokerURL, token.Error())
	}
	return client, nil
}

func brokerRevive(ctx context.Context, client mqtt.Client) {
	if client == nil || !client.IsConnectionOpen() || !brokerReviving.CompareAndSwap(false, true) {
		return
	}
	go func() {
		defer brokerReviving.Store(false)
		probeStart := time.Now()
		token := client.Unsubscribe(brokerProbeTopic)
		if token.WaitTimeout(brokerProbeTimeout) && token.Error() == nil {
			slog.Debug("profiling", "engine", "broker", "phase", "probe", "duration", time.Since(probeStart), "detail", "alive [true] session responded, no revive needed")
			return
		}
		if !client.IsConnectionOpen() {
			slog.Debug("profiling", "engine", "broker", "phase", "probe", "duration", time.Since(probeStart), "detail", "alive [false] connection already closed, paho is reconnecting")
			return
		}
		reviveStart := time.Now()
		slog.Warn("state", "engine", "broker", "phase", "revive", "duration", time.Since(probeStart), "detail", "alive [false] session unresponsive, disconnecting to force reconnect")
		client.Disconnect(0)
		for backoff := brokerReviveBackoff; ; backoff = min(2*backoff, brokerReconnectMax) {
			token := client.Connect()
			if token.WaitTimeout(brokerConnectTimeout) && token.Error() == nil {
				slog.Info("state", "engine", "broker", "phase", "revive", "duration", time.Since(reviveStart), "detail", "alive [true] session revived")
				return
			}
			slog.Warn("state", "engine", "broker", "phase", "revive", "duration", time.Since(reviveStart), "detail", fmt.Sprintf("alive [false] reconnect failed with [%v], retrying after [%d] ms", token.Error(), backoff.Milliseconds()))
			select {
			case <-ctx.Done():
				return
			case <-time.After(backoff):
			}
		}
	}()
}

const (
	brokerProbeTopic     = "supervisor/probe/wake"
	brokerProbeTimeout   = 2 * time.Second
	brokerConnectTimeout = 5 * time.Second
	brokerKeepAlive      = 10 * time.Second
	brokerPingTimeout    = 3 * time.Second
	brokerReconnectMax   = 10 * time.Second
	brokerReviveBackoff  = 1 * time.Second
)

var brokerReviving atomic.Bool
