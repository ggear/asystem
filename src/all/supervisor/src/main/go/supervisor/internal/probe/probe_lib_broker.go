package probe

import (
	"fmt"
	"maps"
	"strings"
	"supervisor/internal/config"
	"supervisor/internal/scribe"
	"sync"
	"time"

	mqtt "github.com/eclipse/paho.mqtt.golang"
)

type brokerClient struct {
	client mqtt.Client
}

func brokerDial(configPath, role string) (*brokerClient, error) {
	options, err := brokerOptions(configPath, role)
	if err != nil {
		return nil, err
	}
	client, err := brokerConnect(options)
	if err != nil {
		return nil, err
	}
	return &brokerClient{client: client}, nil
}

func brokerHold(configPath, role, willTopic string) (*brokerClient, error) {
	options, err := brokerOptions(configPath, role)
	if err != nil {
		return nil, err
	}
	options.SetAutoReconnect(true).SetMaxReconnectInterval(brokerReconnectCap).SetWill(willTopic, "", 1, true)
	client, err := brokerConnect(options)
	if err != nil {
		return nil, err
	}
	return &brokerClient{client: client}, nil
}

func (b *brokerClient) publishRetained(topic, payload string) error {
	return b.publish(topic, payload, true)
}

func (b *brokerClient) publishCommand(topic, payload string) error {
	return b.publish(topic, payload, false)
}

func (b *brokerClient) publish(topic, payload string, retained bool) error {
	token := b.client.Publish(topic, 1, retained, payload)
	if !token.WaitTimeout(brokerTimeout) || token.Error() != nil {
		return fmt.Errorf("publish [%s] failed [%v]", topic, token.Error())
	}
	return nil
}

func (b *brokerClient) readRetained(filters ...string) (map[string]string, error) {
	collected := &brokerPayloads{payloads: map[string]string{}}
	if err := brokerSubscribe(b.client, collected, filters); err != nil {
		return collected.snapshot(), err
	}
	time.Sleep(brokerSettle)
	for _, filter := range filters {
		b.client.Unsubscribe(filter).WaitTimeout(brokerTimeout)
	}
	return collected.snapshot(), nil
}

func (b *brokerClient) close() {
	if b != nil && b.client != nil {
		b.client.Disconnect(250)
	}
}

type brokerWatcher struct {
	brokerPayloads
	client    mqtt.Client
	host      string
	filters   []string
	attaching sync.Mutex
	ready     bool
}

func brokerWatch(configPath, host string, filters ...string) (*brokerWatcher, error) {
	watch := &brokerWatcher{brokerPayloads: brokerPayloads{payloads: map[string]string{}}, host: host, filters: filters}
	options, err := brokerOptions(configPath, "watch")
	if err != nil {
		return nil, err
	}
	options.SetAutoReconnect(true).SetMaxReconnectInterval(brokerReconnectCap).
		SetOnConnectHandler(watch.attach).
		SetConnectionLostHandler(func(_ mqtt.Client, lost error) {
			watch.forget()
			scribe.Log(scribe.SourceProbeBroker, scribe.SubjectHost(host), scribe.ActionDisconnect).Warnf("faulting", time.Now(), "[%v] watching the estate, reporting unknown until it is back", lost)
		})
	client, err := brokerConnect(options)
	if err != nil {
		return nil, err
	}
	watch.client = client
	return watch, nil
}

func (w *brokerWatcher) readRetained() (map[string]string, bool) {
	w.mutex.Lock()
	ready := w.ready
	w.mutex.Unlock()
	if !w.client.IsConnected() {
		return w.snapshot(), false
	}
	if !ready {
		go w.attach(w.client)
	}
	return w.snapshot(), ready
}

func (w *brokerWatcher) attach(client mqtt.Client) {
	if !w.attaching.TryLock() {
		return
	}
	defer w.attaching.Unlock()
	w.forget()
	attachStart := time.Now()
	if err := brokerSubscribe(client, &w.brokerPayloads, w.filters); err != nil {
		scribe.Log(scribe.SourceProbeBroker, scribe.SubjectHost(w.host), scribe.ActionSubscribe).Warnf("faulting", attachStart, "[%v] watching the estate, retrying on the next tick", err)
		return
	}
	time.Sleep(brokerSettle)
	w.mutex.Lock()
	w.ready = true
	held := len(w.payloads)
	w.mutex.Unlock()
	scribe.Log(scribe.SourceProbeBroker, scribe.SubjectHost(w.host), scribe.ActionSubscribe).Debugf("attached", attachStart, "[%d] topics across [%d] filters, watching the estate", held, len(w.filters))
}

func (w *brokerWatcher) forget() {
	w.mutex.Lock()
	w.payloads = map[string]string{}
	w.ready = false
	w.mutex.Unlock()
}

type brokerPayloads struct {
	mutex    sync.Mutex
	payloads map[string]string
}

func (p *brokerPayloads) collect(_ mqtt.Client, message mqtt.Message) {
	p.mutex.Lock()
	p.payloads[message.Topic()] = string(message.Payload())
	p.mutex.Unlock()
}

func (p *brokerPayloads) snapshot() map[string]string {
	p.mutex.Lock()
	defer p.mutex.Unlock()
	snapshot := make(map[string]string, len(p.payloads))
	maps.Copy(snapshot, p.payloads)
	return snapshot
}

func brokerOptions(configPath, role string) (*mqtt.ClientOptions, error) {
	loaded := config.Load(configPath)
	broker := loaded.Broker()
	if broker == "" {
		return nil, fmt.Errorf("no broker address in config [%s]", configPath)
	}
	token := loaded.BrokerToken()
	options := mqtt.NewClientOptions().
		AddBroker("tcp://" + broker).
		SetClientID(fmt.Sprintf("supervisor-%s-%d", role, time.Now().UnixNano())).
		SetCleanSession(true).
		SetConnectTimeout(brokerTimeout).
		SetAutoReconnect(false).
		SetPassword(token)
	if token != "" {
		options.SetUsername("supervisor")
	}
	return options, nil
}

func brokerConnect(options *mqtt.ClientOptions) (mqtt.Client, error) {
	client := mqtt.NewClient(options)
	token := client.Connect()
	if !token.WaitTimeout(brokerTimeout) || token.Error() != nil {
		return nil, fmt.Errorf("broker connect failed [%s] [%v]", options.Servers[0].Host, token.Error())
	}
	return client, nil
}

func brokerSubscribe(client mqtt.Client, into *brokerPayloads, filters []string) error {
	var refused []string
	for _, filter := range filters {
		token := client.Subscribe(filter, 1, into.collect)
		if !token.WaitTimeout(brokerTimeout) || token.Error() != nil {
			refused = append(refused, filter)
			continue
		}
		if granted, ok := token.(*mqtt.SubscribeToken); ok && granted.Result()[filter] > brokerQosMax {
			refused = append(refused, filter)
		}
	}
	if len(refused) > 0 {
		return fmt.Errorf("broker refused [%d] of [%d] subscriptions [%s]", len(refused), len(filters), strings.Join(refused, ","))
	}
	return nil
}

const (
	brokerTimeout      = 5 * time.Second
	brokerReconnectCap = 30 * time.Second
	brokerSettle       = 3 * time.Second
	brokerQosMax       = 2
)
