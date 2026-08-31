package engine

import (
	"context"
	"errors"
	"fmt"
	"sort"
	"supervisor/internal/config"
	"supervisor/internal/scribe"
	"sync/atomic"
	"time"

	mqtt "github.com/eclipse/paho.mqtt.golang"
)

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
			state := "connect"
			since := time.Now()
			if !connectedOnce.Swap(true) || retries > 0 {
				since = lostSince()
			}
			if retries > 0 {
				state = "reconnect"
			}
			scribe.Log(scribe.SourceEngineBroker, scribe.SubjectNone, scribe.ActionConnect).Infof("sessions", since, "[broker] %s after [%d] attempts", state, retries)
			if onConnect != nil {
				onConnect(client)
			}
		}).
		SetConnectionLostHandler(func(_ mqtt.Client, err error) {
			lostAt.Store(time.Now().UnixNano())
			scribe.Log(scribe.SourceEngineBroker, scribe.SubjectNone, scribe.ActionDisconnect).Warnf("sessions", time.Now(), "[broker] disconnect with [%v]", err)
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
			scribe.Log(scribe.SourceEngineBroker, scribe.SubjectNone, scribe.ActionConnect).Debugf("sessions", lostSince(), "[broker] offline attempt [%d]", attempt)
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
				scribe.Log(scribe.SourceEngineBroker, scribe.SubjectNone, scribe.ActionConnect).Debugf("liveness", probeStart, "[false] closed, paho reconnecting")
				return
			}
			scribe.Log(scribe.SourceEngineBroker, scribe.SubjectNone, scribe.ActionConnect).Warnf("liveness", probeStart, "[false] abandoned by paho, reconnecting")
			brokerReconnect(ctx, client, probeStart)
			return
		}
		if frozen > brokerExpiry {
			reviveStart := time.Now()
			scribe.Log(scribe.SourceEngineBroker, scribe.SubjectNone, scribe.ActionConnect).Warnf("liveness", probeStart, "[false] frozen [%d] ms past keepalive [%d] ms", frozen.Milliseconds(), brokerExpiry.Milliseconds())
			client.Disconnect(0)
			brokerReconnect(ctx, client, reviveStart)
			return
		}
		token := client.Unsubscribe(brokerProbeTopic)
		if token.WaitTimeout(brokerTimeout) && token.Error() == nil {
			scribe.Log(scribe.SourceEngineBroker, scribe.SubjectNone, scribe.ActionConnect).Debugf("liveness", probeStart, "[true] responded, no revive needed")
			return
		}
		if !client.IsConnectionOpen() {
			scribe.Log(scribe.SourceEngineBroker, scribe.SubjectNone, scribe.ActionConnect).Debugf("liveness", probeStart, "[false] already closed, paho reconnecting")
			return
		}
		reviveStart := time.Now()
		scribe.Log(scribe.SourceEngineBroker, scribe.SubjectNone, scribe.ActionConnect).Warnf("liveness", probeStart, "[false] unresponsive, forcing reconnect")
		client.Disconnect(0)
		brokerReconnect(ctx, client, reviveStart)
	}()
}

func brokerReconnect(ctx context.Context, client mqtt.Client, reviveStart time.Time) {
	for backoff := brokerTimeout; ; backoff = min(2*backoff, brokerInterval) {
		if client.IsConnectionOpen() {
			scribe.Log(scribe.SourceEngineBroker, scribe.SubjectNone, scribe.ActionConnect).Infof("liveness", reviveStart, "[true] session revived")
			return
		}
		token := client.Connect()
		if token.WaitTimeout(brokerTimeout) && token.Error() == nil {
			scribe.Log(scribe.SourceEngineBroker, scribe.SubjectNone, scribe.ActionConnect).Infof("liveness", reviveStart, "[true] session revived")
			return
		}
		scribe.Log(scribe.SourceEngineBroker, scribe.SubjectNone, scribe.ActionConnect).Warnf("liveness", reviveStart, "[false] failed with [%v], retrying after [%d] ms", token.Error(), backoff.Milliseconds())
		select {
		case <-ctx.Done():
			return
		case <-time.After(backoff):
		}
	}
}

func subscribeRefused(token mqtt.Token, filters map[string]byte) ([]string, string) {
	if !token.WaitTimeout(brokerTimeout) || token.Error() != nil {
		refused := make([]string, 0, len(filters))
		for topic := range filters {
			refused = append(refused, topic)
		}
		sort.Strings(refused)
		return refused, fmt.Sprintf("failed with [%v]", token.Error())
	}
	granted, ok := token.(*mqtt.SubscribeToken)
	if !ok {
		return nil, ""
	}
	var refused []string
	for topic, code := range granted.Result() {
		if code <= subscribeQosMax {
			continue
		}
		refused = append(refused, topic)
	}
	if len(refused) == 0 {
		return nil, ""
	}
	sort.Strings(refused)
	return refused, fmt.Sprintf("refused by the broker with [%s]", refused[0])
}

const (
	brokerProbeTopic = "supervisor/probe/wake"
	brokerTimeout    = 3 * time.Second
	brokerInterval   = 10 * time.Second
	brokerExpiry     = brokerInterval * 3 / 2
	subscribeQosMax  = 2
)

var brokerReviving atomic.Bool
