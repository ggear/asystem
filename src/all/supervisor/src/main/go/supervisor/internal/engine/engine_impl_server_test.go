package engine

import (
	"context"
	"encoding/json"
	"fmt"
	"log/slog"
	"maps"
	"os"
	"path/filepath"
	"slices"
	"strings"
	"supervisor/internal/config"
	"supervisor/internal/metric"
	"supervisor/internal/scribe"
	"supervisor/internal/testutil"
	"sync"
	"testing"
	"time"

	mqtt "github.com/eclipse/paho.mqtt.golang"
)

func TestEngineImplServer_RunAllProbesPublishLoop(t *testing.T) {
	logBuffer := scribe.EnableBuffer(slog.LevelDebug, 2000)
	t.Cleanup(func() { scribe.EnableStdout(slog.LevelDebug) })
	testutil.RequiresDocker(t)
	_, mqttClient, err := testutil.SetupBrokerContainer(t)
	if err != nil {
		t.Fatalf("setup broker container failed: %v", err)
	}
	brokerHost := os.Getenv("VERNEMQ_HOST")
	brokerPort := os.Getenv("VERNEMQ_API_PORT")
	periods := config.Periods{PollMillis: 3000, PulseMillis: 3000, HeartbeatSecs: 300, TrendHours: 1}
	tests := []struct {
		name         string
		hostName     string
		databaseHost string
		runFor       time.Duration
		checkFunc    func(*testing.T, string, *topicRecorder)
	}{
		{
			name:         "happy_first_pulse_precedes_an_unreachable_database",
			hostName:     "alpha",
			databaseHost: "127.0.0.1",
			runFor:       8 * time.Second,
			checkFunc: func(t *testing.T, hostName string, recorder *topicRecorder) {
				topic := "supervisor/" + hostName + "/data/host/used_memory"
				recorder.mutex.Lock()
				elapsed, ok := recorder.first[topic]
				recorder.mutex.Unlock()
				if !ok {
					t.Fatalf("Got no publish of %s, expected the first pulse to publish it", topic)
				}
				budget := time.Duration(periods.PollMillis) * time.Millisecond
				if elapsed > budget {
					t.Fatalf("first publish: got %v want under %v, being before the ticker could have fired at all", elapsed, budget)
				}
				t.Logf("First publish of %s after %v", topic, elapsed.Round(time.Millisecond))
			},
		},
		{
			name:         "happy_graceful_stop_keeps_the_retained_records",
			hostName:     "bravo",
			databaseHost: "",
			runFor:       8 * time.Second,
			checkFunc: func(t *testing.T, hostName string, _ *topicRecorder) {
				statusTopic := "supervisor/" + hostName + "/status"
				dataTopic := "supervisor/" + hostName + "/data/host/used_memory"
				retained := subscribeRetained(t, mqttClient, statusTopic, dataTopic)
				if got := string(retained[statusTopic]); got != metric.AvailabilityOffline {
					t.Errorf("status: got %q want %q", got, metric.AvailabilityOffline)
				}
				if len(retained[dataTopic]) == 0 {
					t.Fatalf("Got %s cleared after a graceful stop, expected the record retained", dataTopic)
				}
			},
		},
		{
			name:         "sad_malformed_read_back_is_rejected_rather_than_dropped_in_silence",
			hostName:     "delta",
			databaseHost: "",
			runFor:       8 * time.Second,
			checkFunc: func(t *testing.T, hostName string, _ *topicRecorder) {
				topic := "supervisor/" + hostName + "/data/service/zzbroken/name"
				rejected := false
				for _, line := range logBuffer.Tail(2000) {
					if line.Level != slog.LevelError || line.Verb != "rejected" {
						continue
					}
					if strings.Contains(line.Detail, "unmarshal") && strings.Contains(line.Detail, "readback") {
						rejected = true
					}
				}
				if !rejected {
					t.Fatalf("Got no rejected readback line for %s, expected a malformed payload to name itself", topic)
				}
			},
		},
		{
			name:         "happy_orphan_read_back_is_tombstoned_in_both_forms",
			hostName:     "charlie",
			databaseHost: "",
			runFor:       12 * time.Second,
			checkFunc: func(t *testing.T, hostName string, recorder *topicRecorder) {
				topic := "supervisor/" + hostName + "/data/service/zztest/name"
				recorder.mutex.Lock()
				payloads := slices.Clone(recorder.seen[topic])
				recorder.mutex.Unlock()
				if len(payloads) < 2 {
					t.Fatalf("Got %d publishes of %s, expected the nil pulse and the empty payload", len(payloads), topic)
				}
				last := payloads[len(payloads)-1]
				if len(last) != 0 {
					t.Fatalf("last form: got %q want an empty payload", last)
				}
				var value metric.ValueData
				if err := json.Unmarshal(payloads[len(payloads)-2], &value); err != nil {
					t.Fatalf("unmarshal the form before the empty payload: %v", err)
				}
				if value.Pulse != nil {
					t.Fatalf("Got pulse %v in the form before the empty payload, expected a nil pulse", value.Pulse)
				}
				if value.Timestamp <= 0 {
					t.Fatalf("timestamp: got %d want a timestamp proving the host alive", value.Timestamp)
				}
				retained := subscribeRetained(t, mqttClient, topic)
				if len(retained[topic]) != 0 {
					t.Fatalf("Got %s still retained as %q, expected it cleared", topic, retained[topic])
				}
			},
		},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			t.Cleanup(config.Reset)
			database := ""
			if tt.databaseHost != "" {
				database = fmt.Sprintf(`,"database":{"host":%q,"port":"1","token":"test-token"}`, tt.databaseHost)
			}
			configContent := fmt.Sprintf(`{"asystem":{"version":"10.100.6000","host":%q,"broker":{"host":%q,"port":%q}%s}}`,
				tt.hostName, brokerHost, brokerPort, database)
			configFile := filepath.Join(t.TempDir(), "config.json")
			if err := os.WriteFile(configFile, []byte(configContent), 0644); err != nil {
				t.Fatalf("write config file failed: %v", err)
			}
			recorder := &topicRecorder{first: make(map[string]time.Duration), seen: make(map[string][][]byte)}
			token := mqttClient.Subscribe("supervisor/"+tt.hostName+"/#", 1, recorder.record)
			token.Wait()
			if token.Error() != nil {
				t.Fatalf("subscribe failed: %v", token.Error())
			}
			t.Cleanup(func() { mqttClient.Unsubscribe("supervisor/" + tt.hostName + "/#").Wait() })
			if tt.name == "sad_malformed_read_back_is_rejected_rather_than_dropped_in_silence" {
				mqttClient.Publish("supervisor/"+tt.hostName+"/data/service/zzbroken/name", 1, true, []byte("{not json")).Wait()
			}
			if tt.name == "happy_orphan_read_back_is_tombstoned_in_both_forms" {
				orphan := metric.ValueData{
					Timestamp: time.Now().Unix(),
					Pulse:     &metric.ValueDataDetail{OK: true, Kind: metric.ValueString, ValueString: "zztest"},
				}
				payload, marshalErr := json.Marshal(orphan)
				if marshalErr != nil {
					t.Fatalf("marshal orphan failed: %v", marshalErr)
				}
				mqttClient.Publish("supervisor/"+tt.hostName+"/data/service/zztest/name", 1, true, payload).Wait()
			}
			ctx, cancel := context.WithTimeout(context.Background(), tt.runFor)
			defer cancel()
			cache := metric.NewRecordCache()
			recorder.mutex.Lock()
			recorder.started = time.Now()
			recorder.mutex.Unlock()
			done := make(chan struct{})
			go func() {
				defer close(done)
				RunAllProbesPublishLoop(ctx, configFile, cache, periods)
			}()
			<-done
			time.Sleep(time.Second)
			tt.checkFunc(t, tt.hostName, recorder)
		})
	}
}

func subscribeRetained(t *testing.T, client mqtt.Client, topics ...string) map[string][]byte {
	t.Helper()
	retained := make(map[string][]byte)
	var mutex sync.Mutex
	for _, topic := range topics {
		token := client.Subscribe(topic, 1, func(_ mqtt.Client, msg mqtt.Message) {
			mutex.Lock()
			retained[msg.Topic()] = msg.Payload()
			mutex.Unlock()
		})
		token.Wait()
	}
	time.Sleep(2 * time.Second)
	for _, topic := range topics {
		client.Unsubscribe(topic).Wait()
	}
	mutex.Lock()
	defer mutex.Unlock()
	return maps.Clone(retained)
}

type topicRecorder struct {
	mutex   sync.Mutex
	started time.Time
	first   map[string]time.Duration
	seen    map[string][][]byte
}

func (r *topicRecorder) record(_ mqtt.Client, msg mqtt.Message) {
	r.mutex.Lock()
	if _, exists := r.first[msg.Topic()]; !exists {
		r.first[msg.Topic()] = time.Since(r.started)
	}
	r.seen[msg.Topic()] = append(r.seen[msg.Topic()], msg.Payload())
	r.mutex.Unlock()
}
