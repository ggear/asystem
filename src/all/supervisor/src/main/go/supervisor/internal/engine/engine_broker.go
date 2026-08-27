package engine

import (
	"context"
	"errors"
	"fmt"
	"supervisor/internal/clock"
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
	onWake func(time.Duration)
}

func (b *brokerWakeListener) MarkWake(frozen time.Duration) {
	wakeStart := clock.NowIncludingSuspend().Add(-frozen)
	if b.onWake == nil {
		scribe.Log(scribe.SourceEngineBroker, scribe.SubjectNone, scribe.ActionConnect).Error("unusable", wakeStart, "[wake] requested by the stall detector with no revive bound, so nothing recovers the session")
		return
	}
	scribe.Log(scribe.SourceEngineBroker, scribe.SubjectNone, scribe.ActionConnect).Info("detected", wakeStart, "[wake] revive requested by the stall detector")
	b.onWake(frozen)
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
			scribe.Log(scribe.SourceEngineBroker, scribe.SubjectNone, scribe.ActionConnect).Info("sessions", since, "[%s] after [%d] attempts at [%s]", state, retries, broker)
			if onConnect != nil {
				onConnect(client)
			}
		}).
		SetConnectionLostHandler(func(_ mqtt.Client, err error) {
			lostAt.Store(time.Now().UnixNano())
			scribe.Log(scribe.SourceEngineBroker, scribe.SubjectNone, scribe.ActionDisconnect).Warn("sessions", time.Now(), "[lost] connection at [%s] with [%v]", broker, err)
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
			scribe.Log(scribe.SourceEngineBroker, scribe.SubjectNone, scribe.ActionConnect).Debug("sessions", lostSince(), "[offline] attempt [%d] at [%s]", attempt, broker)
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

func brokerRevive(ctx context.Context, client mqtt.Client, frozen time.Duration) {
	if client == nil || !brokerReviving.CompareAndSwap(false, true) {
		return
	}
	go func() {
		defer brokerReviving.Store(false)
		probeStart := time.Now()
		if !client.IsConnectionOpen() {
			if client.IsConnected() {
				scribe.Log(scribe.SourceEngineBroker, scribe.SubjectNone, scribe.ActionConnect).Debug("liveness", probeStart, "[false] connection closed, paho is reconnecting")
				return
			}
			scribe.Log(scribe.SourceEngineBroker, scribe.SubjectNone, scribe.ActionConnect).Warn("liveness", probeStart, "[false] session abandoned by paho, reconnecting")
			brokerReconnect(ctx, client, probeStart)
			return
		}
		if frozen > brokerExpiry {
			reviveStart := time.Now()
			scribe.Log(scribe.SourceEngineBroker, scribe.SubjectNone, scribe.ActionConnect).Warn("liveness", probeStart, "[false] frozen for [%d] ms beyond the broker keepalive of [%d] ms, reconnecting without probing", frozen.Milliseconds(), brokerExpiry.Milliseconds())
			client.Disconnect(0)
			brokerReconnect(ctx, client, reviveStart)
			return
		}
		token := client.Unsubscribe(brokerProbeTopic)
		if token.WaitTimeout(brokerTimeout) && token.Error() == nil {
			scribe.Log(scribe.SourceEngineBroker, scribe.SubjectNone, scribe.ActionConnect).Debug("liveness", probeStart, "[true] session responded, no revive needed")
			return
		}
		if !client.IsConnectionOpen() {
			scribe.Log(scribe.SourceEngineBroker, scribe.SubjectNone, scribe.ActionConnect).Debug("liveness", probeStart, "[false] connection already closed, paho is reconnecting")
			return
		}
		reviveStart := time.Now()
		scribe.Log(scribe.SourceEngineBroker, scribe.SubjectNone, scribe.ActionConnect).Warn("liveness", probeStart, "[false] session unresponsive, disconnecting to force reconnect")
		client.Disconnect(0)
		brokerReconnect(ctx, client, reviveStart)
	}()
}

func brokerReconnect(ctx context.Context, client mqtt.Client, reviveStart time.Time) {
	for backoff := brokerTimeout; ; backoff = min(2*backoff, brokerInterval) {
		if client.IsConnectionOpen() {
			scribe.Log(scribe.SourceEngineBroker, scribe.SubjectNone, scribe.ActionConnect).Info("liveness", reviveStart, "[true] session revived")
			return
		}
		token := client.Connect()
		if token.WaitTimeout(brokerTimeout) && token.Error() == nil {
			scribe.Log(scribe.SourceEngineBroker, scribe.SubjectNone, scribe.ActionConnect).Info("liveness", reviveStart, "[true] session revived")
			return
		}
		scribe.Log(scribe.SourceEngineBroker, scribe.SubjectNone, scribe.ActionConnect).Warn("liveness", reviveStart, "[false] failed with [%v], retrying after [%d] ms", token.Error(), backoff.Milliseconds())
		select {
		case <-ctx.Done():
			return
		case <-time.After(backoff):
		}
	}
}

const (
	brokerProbeTopic = "supervisor/probe/wake"
	brokerTimeout    = 3 * time.Second
	brokerInterval   = 10 * time.Second
	brokerExpiry     = brokerInterval * 3 / 2
)

var brokerReviving atomic.Bool
