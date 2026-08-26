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
	scribe.Log(scribe.SourceBroker, scribe.SubjectSurface("terminal"), scribe.ActionConnect).Info("detected", wakeStart, "[wake] revive requested by the stall detector")
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
			scribe.Log(scribe.SourceBroker, scribe.SubjectEndpoint(broker), scribe.ActionConnect).Info("sessions", since, "[%s] after [%d] attempts", state, retries)
			if onConnect != nil {
				onConnect(client)
			}
		}).
		SetConnectionLostHandler(func(_ mqtt.Client, err error) {
			lostAt.Store(time.Now().UnixNano())
			scribe.Log(scribe.SourceBroker, scribe.SubjectEndpoint(broker), scribe.ActionDisconnect).Warn("sessions", time.Now(), "[lost] connection with [%v]", err)
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
			scribe.Log(scribe.SourceBroker, scribe.SubjectEndpoint(broker), scribe.ActionConnect).Debug("sessions", lostSince(), "[offline] attempt [%d]", attempt)
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
	if client == nil || !brokerReviving.CompareAndSwap(false, true) {
		return
	}
	go func() {
		defer brokerReviving.Store(false)
		probeStart := time.Now()
		if !client.IsConnectionOpen() {
			if client.IsConnected() {
				scribe.Log(scribe.SourceBroker, brokerSubject(client), scribe.ActionConnect).Debug("liveness", probeStart, "[false] connection closed, paho is reconnecting")
				return
			}
			scribe.Log(scribe.SourceBroker, brokerSubject(client), scribe.ActionConnect).Warn("liveness", probeStart, "[false] session abandoned by paho, reconnecting")
			brokerReconnect(ctx, client, probeStart)
			return
		}
		token := client.Unsubscribe(brokerProbeTopic)
		if token.WaitTimeout(brokerTimeout) && token.Error() == nil {
			scribe.Log(scribe.SourceBroker, brokerSubject(client), scribe.ActionConnect).Debug("liveness", probeStart, "[true] session responded, no revive needed")
			return
		}
		if !client.IsConnectionOpen() {
			scribe.Log(scribe.SourceBroker, brokerSubject(client), scribe.ActionConnect).Debug("liveness", probeStart, "[false] connection already closed, paho is reconnecting")
			return
		}
		reviveStart := time.Now()
		scribe.Log(scribe.SourceBroker, brokerSubject(client), scribe.ActionConnect).Warn("liveness", probeStart, "[false] session unresponsive, disconnecting to force reconnect")
		client.Disconnect(0)
		brokerReconnect(ctx, client, reviveStart)
	}()
}

func brokerReconnect(ctx context.Context, client mqtt.Client, reviveStart time.Time) {
	for backoff := brokerTimeout; ; backoff = min(2*backoff, brokerInterval) {
		if client.IsConnectionOpen() {
			scribe.Log(scribe.SourceBroker, brokerSubject(client), scribe.ActionConnect).Info("liveness", reviveStart, "[true] session revived")
			return
		}
		token := client.Connect()
		if token.WaitTimeout(brokerTimeout) && token.Error() == nil {
			scribe.Log(scribe.SourceBroker, brokerSubject(client), scribe.ActionConnect).Info("liveness", reviveStart, "[true] session revived")
			return
		}
		scribe.Log(scribe.SourceBroker, brokerSubject(client), scribe.ActionConnect).Warn("liveness", reviveStart, "[false] failed with [%v], retrying after [%d] ms", token.Error(), backoff.Milliseconds())
		select {
		case <-ctx.Done():
			return
		case <-time.After(backoff):
		}
	}
}

func brokerSubject(client mqtt.Client) scribe.Subject {
	if client == nil {
		return scribe.SubjectNone
	}
	options := client.OptionsReader()
	servers := options.Servers()
	if len(servers) == 0 {
		return scribe.SubjectNone
	}
	return scribe.SubjectEndpoint(servers[0].Host)
}

const (
	brokerProbeTopic = "supervisor/probe/wake"
	brokerTimeout    = 3 * time.Second
	brokerInterval   = 10 * time.Second
)

var brokerReviving atomic.Bool
