package probe

import (
	"sync/atomic"
	"testing"
	"time"

	mqtt "github.com/eclipse/paho.mqtt.golang"
)

type stubToken struct {
	granted bool
	done    chan struct{}
}

func (t *stubToken) Wait() bool                     { return t.granted }
func (t *stubToken) WaitTimeout(time.Duration) bool { return t.granted }
func (t *stubToken) Done() <-chan struct{}          { return t.done }
func (t *stubToken) Error() error                   { return nil }

type stubClient struct {
	connected  bool
	subscribes atomic.Int64
}

func (c *stubClient) IsConnected() bool      { return c.connected }
func (c *stubClient) IsConnectionOpen() bool { return c.connected }
func (c *stubClient) Connect() mqtt.Token    { return &stubToken{granted: true, done: closedChannel()} }
func (c *stubClient) Disconnect(uint)        {}
func (c *stubClient) Publish(string, byte, bool, any) mqtt.Token {
	return &stubToken{granted: true, done: closedChannel()}
}
func (c *stubClient) Subscribe(string, byte, mqtt.MessageHandler) mqtt.Token {
	c.subscribes.Add(1)
	return &stubToken{done: closedChannel()}
}
func (c *stubClient) SubscribeMultiple(map[string]byte, mqtt.MessageHandler) mqtt.Token {
	return &stubToken{done: closedChannel()}
}
func (c *stubClient) Unsubscribe(...string) mqtt.Token {
	return &stubToken{granted: true, done: closedChannel()}
}
func (c *stubClient) AddRoute(string, mqtt.MessageHandler)    {}
func (c *stubClient) OptionsReader() mqtt.ClientOptionsReader { return mqtt.ClientOptionsReader{} }

func closedChannel() chan struct{} {
	done := make(chan struct{})
	close(done)
	return done
}

type stubMessage struct {
	topic   string
	payload string
}

func (m stubMessage) Duplicate() bool   { return false }
func (m stubMessage) Qos() byte         { return 1 }
func (m stubMessage) Retained() bool    { return true }
func (m stubMessage) Topic() string     { return m.topic }
func (m stubMessage) MessageID() uint16 { return 0 }
func (m stubMessage) Payload() []byte   { return []byte(m.payload) }
func (m stubMessage) Ack()              {}

func TestProbeLibBroker_PayloadsKeepLatestPerTopic(t *testing.T) {
	store := &brokerPayloads{payloads: map[string]string{}}
	store.collect(nil, stubMessage{topic: "tasmota/stat/POWER", payload: "OFF"})
	store.collect(nil, stubMessage{topic: "tasmota/stat/POWER", payload: "ON"})
	store.collect(nil, stubMessage{topic: "supervisor/leader/backup/election", payload: "{}"})
	snapshot := store.snapshot()
	if got := snapshot["tasmota/stat/POWER"]; got != "ON" {
		t.Errorf("latest payload: got %q want %q", got, "ON")
	}
	if len(snapshot) != 2 {
		t.Errorf("topics: got %d want %d", len(snapshot), 2)
	}
	snapshot["tasmota/stat/POWER"] = "mutated"
	if again := store.snapshot(); again["tasmota/stat/POWER"] != "ON" {
		t.Errorf("snapshot aliases the store: got %q want %q", again["tasmota/stat/POWER"], "ON")
	}
}

func TestProbeLibBroker_WatcherReportsFreshOnlyWhenConnectedAndReady(t *testing.T) {
	tests := []struct {
		name          string
		connected     bool
		ready         bool
		wantFresh     bool
		wantResubcrib bool
		expectedError bool
	}{
		{"connected and subscribed is fresh", true, true, true, false, false},
		{"connected but never granted is unknown", true, false, false, true, false},
		{"disconnected is unknown", false, false, false, false, false},
		{"disconnected while still marked ready is unknown", false, true, false, false, false},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			client := &stubClient{connected: tt.connected}
			watch := &brokerWatcher{
				brokerPayloads: brokerPayloads{payloads: map[string]string{"a/b": "1"}},
				client:         client,
				filters:        []string{"a/b"},
				ready:          tt.ready,
			}
			retained, fresh := watch.readRetained()
			if fresh != tt.wantFresh {
				t.Errorf("fresh: got %v want %v", fresh, tt.wantFresh)
			}
			if retained["a/b"] != "1" {
				t.Errorf("payload: got %q want %q", retained["a/b"], "1")
			}
			if tt.wantResubcrib {
				deadline := time.Now().Add(2 * time.Second)
				for client.subscribes.Load() == 0 && time.Now().Before(deadline) {
					time.Sleep(5 * time.Millisecond)
				}
				if client.subscribes.Load() == 0 {
					t.Error("resubscribe: got none want one, a connected but ungranted watcher must retry")
				}
			}
		})
	}
}

func TestProbeLibBroker_ForgetClearsPayloadsAndReadiness(t *testing.T) {
	watch := &brokerWatcher{
		brokerPayloads: brokerPayloads{payloads: map[string]string{"a/b": "1"}},
		client:         &stubClient{connected: true},
		ready:          true,
	}
	if _, fresh := watch.readRetained(); !fresh {
		t.Fatal("fresh: got false want true before forget")
	}
	watch.forget()
	retained, fresh := watch.readRetained()
	if fresh {
		t.Error("fresh: got true want false after forget")
	}
	if len(retained) != 0 {
		t.Errorf("payloads: got %d want 0, a lost connection must not leave a phantom reading", len(retained))
	}
}
