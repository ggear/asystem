package engine

import (
	"context"
	"errors"
	"fmt"
	"supervisor/internal/config"
	"supervisor/internal/scribe"
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

type brokerWakeListener struct {
	onWake func()
}

func (b *brokerWakeListener) MarkWake() {
	wakeStart := time.Now()
	if b.onWake == nil {
		return
	}
	b.onWake()
	scribe.Engine("state", "broker").Info("wake", wakeStart, "detected [wake] revive requested by the display stall detector")
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
	var attempts atomic.Int64
	var lostAt atomic.Int64
	var connectedOnce atomic.Bool
	lostSignal := make(chan struct{}, 1)
	lostAt.Store(time.Now().UnixNano())
	lostSince := func() time.Time {
		return time.Unix(0, lostAt.Load())
	}
	opts := mqtt.NewClientOptions().
		AddBroker(brokerURL).
		SetClientID(fmt.Sprintf("supervisor-subscriber-%d", time.Now().UnixNano())).
		SetCleanSession(true).
		SetConnectTimeout(brokerTimeout).
		SetKeepAlive(brokerInterval).
		SetPingTimeout(brokerTimeout).
		SetMaxReconnectInterval(brokerInterval).
		SetAutoReconnect(true).
		SetPassword(config.Load(configPath).BrokerToken()).
		SetOnConnectHandler(func(client mqtt.Client) {
			retries := attempts.Swap(0)
			state := "connected"
			since := time.Now()
			if !connectedOnce.Swap(true) || retries > 0 {
				since = lostSince()
			}
			if retries > 0 {
				state = "reconnected"
			}
			scribe.Engine("state", "broker").Info("connect", since, "broker   [%s] %s after [%d] attempts", brokerURL, state, retries)
			if onConnect != nil {
				onConnect(client)
			}
		}).
		SetConnectionLostHandler(func(_ mqtt.Client, err error) {
			lostAt.Store(time.Now().UnixNano())
			scribe.Engine("state", "broker").Warn("disconnect", time.Now(), "broker   [%s] connection lost with [%v]", brokerURL, err)
			select {
			case lostSignal <- struct{}{}:
			default:
			}
		}).
		SetReconnectingHandler(func(_ mqtt.Client, _ *mqtt.ClientOptions) {
			attempt := attempts.Add(1)
			if attempt == 1 {
				select {
				case <-lostSignal:
				case <-time.After(brokerTimeout):
				}
			}
			scribe.Engine("state", "broker").Debug("reconnect", lostSince(), "broker   [%s] attempt [%d] while offline", brokerURL, attempt)
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
		if token.WaitTimeout(brokerTimeout) && token.Error() == nil {
			scribe.Engine("profiling", "broker").Debug("probe", probeStart, "alive    [true] session responded, no revive needed")
			return
		}
		if !client.IsConnectionOpen() {
			scribe.Engine("profiling", "broker").Debug("probe", probeStart, "alive    [false] connection already closed, paho is reconnecting")
			return
		}
		reviveStart := time.Now()
		scribe.Engine("state", "broker").Warn("revive", probeStart, "alive    [false] session unresponsive, disconnecting to force reconnect")
		client.Disconnect(0)
		for backoff := brokerTimeout; ; backoff = min(2*backoff, brokerInterval) {
			token := client.Connect()
			if token.WaitTimeout(brokerTimeout) && token.Error() == nil {
				scribe.Engine("state", "broker").Info("revive", reviveStart, "alive    [true] session revived")
				return
			}
			scribe.Engine("state", "broker").Warn("revive", reviveStart, "alive    [false] failed with [%v], retrying after [%d] ms", token.Error(), backoff.Milliseconds())
			select {
			case <-ctx.Done():
				return
			case <-time.After(backoff):
			}
		}
	}()
}

const (
	brokerProbeTopic = "supervisor/probe/wake"
	brokerTimeout    = 3 * time.Second
	brokerInterval   = 10 * time.Second
)

var brokerReviving atomic.Bool
