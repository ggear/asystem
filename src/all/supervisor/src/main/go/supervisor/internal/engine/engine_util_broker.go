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

func brokerConnect(ctx context.Context, configPath string, onConnect func(mqtt.Client), willTopic, willPayload string) (mqtt.Client, error) {
	broker := config.Load(configPath).Broker()
	if broker == "" {
		return nil, errors.New("broker address is empty")
	}
	brokerURL := fmt.Sprintf("tcp://%s", broker)
	var attempts atomic.Int64
	var lostAt atomic.Int64
	var connectedOnce atomic.Bool
	var failure atomic.Value
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
		SetConnectRetry(true).
		SetConnectRetryInterval(brokerConnectRetry).
		SetConnectionNotificationHandler(func(_ mqtt.Client, notification mqtt.ConnectionNotification) {
			if failed, ok := notification.(mqtt.ConnectionNotificationFailed); ok && failed.Reason != nil {
				failure.Store(failed.Reason.Error())
			}
		}).
		SetPassword(config.Load(configPath).BrokerToken()).
		SetOnConnectHandler(func(client mqtt.Client) {
			retries := attempts.Swap(0)
			since := time.Now()
			if !connectedOnce.Swap(true) || retries > 0 {
				since = lostSince()
			}
			scribe.Log(scribe.SourceEngineBroker, scribe.SubjectNone, scribe.ActionConnect).Infof("sessions", since, "[broker] connect in [%d] attempts", retries)
			if onConnect != nil {
				onConnect(client)
			}
		}).
		SetConnectionLostHandler(func(_ mqtt.Client, _ error) {
			lostAt.Store(time.Now().UnixNano())
			scribe.Log(scribe.SourceEngineBroker, scribe.SubjectNone, scribe.ActionDisconnect).Warnf("sessions", time.Now(), "[broker] disconnected by network")
			select {
			case lostSignal <- struct{}{}:
			default:
			}
		}).
		SetReconnectingHandler(func(_ mqtt.Client, _ *mqtt.ClientOptions) {
			attempt := attempts.Add(1)
			if attempt > sessionAttemptsMax {
				attempt = sessionAttemptsMax
				attempts.Store(sessionAttemptsMax)
			}
			if attempt == 1 {
				select {
				case <-lostSignal:
				case <-time.After(brokerTimeout):
				}
			}
			scribe.Log(scribe.SourceEngineBroker, scribe.SubjectNone, scribe.ActionConnect).Debugf("sessions", lostSince(), "[broker] backed-off [%2d] attempt", attempt)
		})
	if willTopic != "" {
		opts.SetWill(willTopic, willPayload, 1, true)
	}
	client := mqtt.NewClient(opts)
	token := client.Connect()
	for waits := 1; !token.WaitTimeout(brokerTimeout); waits++ {
		if ctx.Err() != nil {
			client.Disconnect(0)
			return nil, fmt.Errorf("connect abandoned [%s] [%w]", brokerURL, ctx.Err())
		}
		if waits%brokerConnectWarnEvery == 0 {
			reason, _ := failure.Load().(string)
			scribe.Log(scribe.SourceEngineBroker, scribe.SubjectNone, scribe.ActionConnect).Warnf("sessions", lostSince(), "[broker] unreachable at [%s], retrying every [%s], last failure [%s]", brokerURL, brokerConnectRetry, reason)
		}
	}
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
				scribe.Log(scribe.SourceEngineBroker, scribe.SubjectNone, scribe.ActionConnect).Debugf("liveness", probeStart, "[-] is closed, paho retrying")
				return
			}
			scribe.Log(scribe.SourceEngineBroker, scribe.SubjectNone, scribe.ActionConnect).Warnf("liveness", probeStart, "[-] abandoned, reconnect now")
			brokerReconnect(ctx, client, probeStart)
			return
		}
		if frozen > brokerExpiry {
			reviveStart := time.Now()
			scribe.Log(scribe.SourceEngineBroker, scribe.SubjectNone, scribe.ActionConnect).Warnf("liveness", probeStart, "[-] frozen [%5d] sec, gone", int64(frozen.Seconds()))
			client.Disconnect(0)
			brokerReconnect(ctx, client, reviveStart)
			return
		}
		token := client.Unsubscribe(brokerProbeTopic)
		if token.WaitTimeout(brokerTimeout) && token.Error() == nil {
			scribe.Log(scribe.SourceEngineBroker, scribe.SubjectNone, scribe.ActionConnect).Debugf("liveness", probeStart, "[+] responded, no revive owed")
			return
		}
		if !client.IsConnectionOpen() {
			scribe.Log(scribe.SourceEngineBroker, scribe.SubjectNone, scribe.ActionConnect).Debugf("liveness", probeStart, "[-] closed already, retrying")
			return
		}
		reviveStart := time.Now()
		scribe.Log(scribe.SourceEngineBroker, scribe.SubjectNone, scribe.ActionConnect).Warnf("liveness", probeStart, "[-] unresponsive, retry soon")
		client.Disconnect(0)
		brokerReconnect(ctx, client, reviveStart)
	}()
}

func brokerReconnect(ctx context.Context, client mqtt.Client, reviveStart time.Time) {
	for backoff := brokerTimeout; ; backoff = min(2*backoff, brokerInterval) {
		if client.IsConnectionOpen() {
			scribe.Log(scribe.SourceEngineBroker, scribe.SubjectNone, scribe.ActionConnect).Infof("liveness", reviveStart, "[+] session was open, no work")
			return
		}
		token := client.Connect()
		if token.WaitTimeout(brokerTimeout) && token.Error() == nil {
			scribe.Log(scribe.SourceEngineBroker, scribe.SubjectNone, scribe.ActionConnect).Infof("liveness", reviveStart, "[+] session revived and ready")
			return
		}
		scribe.Log(scribe.SourceEngineBroker, scribe.SubjectNone, scribe.ActionConnect).Warnf("liveness", reviveStart, "[-] failed, wait [%5d] ms [%v]", backoff.Milliseconds(), token.Error())
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

	brokerConnectRetry     = 2 * time.Second
	brokerConnectWarnEvery = 5

	sessionAttemptsMax = 9
)

var brokerReviving atomic.Bool
