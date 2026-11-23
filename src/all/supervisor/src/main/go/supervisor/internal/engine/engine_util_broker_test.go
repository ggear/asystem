package engine

import (
	"bufio"
	"context"
	"fmt"
	"net"
	"os"
	"path/filepath"
	"supervisor/internal/config"
	"testing"
	"time"

	mqtt "github.com/eclipse/paho.mqtt.golang"
)

func TestEngineUtilBroker_ConnectWaitsForTheBroker(t *testing.T) {
	tests := []struct {
		name          string
		brokerUpAfter time.Duration
		cancelAfter   time.Duration
		expectedError bool
	}{
		{name: "a_broker_that_is_up_connects_at_once"},
		{name: "a_broker_that_comes_up_late_is_waited_for", brokerUpAfter: 4 * time.Second},
		{name: "a_broker_that_never_comes_up_ends_with_the_context", cancelAfter: 2 * time.Second, expectedError: true},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			probe, err := net.Listen("tcp", "127.0.0.1:0")
			if err != nil {
				t.Fatalf("listen failed with [%v]", err)
			}
			address := probe.Addr().(*net.TCPAddr)
			if testCase.cancelAfter > 0 || testCase.brokerUpAfter > 0 {
				_ = probe.Close()
			} else {
				go serveFakeBroker(probe)
			}
			t.Cleanup(func() { _ = probe.Close() })
			t.Cleanup(config.Reset)
			configFile := filepath.Join(t.TempDir(), "config.json")
			content := fmt.Sprintf(`{"asystem":{"version":"10.100.6000","host":"alpha","broker":{"host":"127.0.0.1","port":"%d"}}}`, address.Port)
			if err := os.WriteFile(configFile, []byte(content), 0o644); err != nil {
				t.Fatalf("write failed with [%v]", err)
			}
			ctx, cancel := context.WithCancel(context.Background())
			defer cancel()
			if testCase.cancelAfter > 0 {
				time.AfterFunc(testCase.cancelAfter, cancel)
			}
			if testCase.brokerUpAfter > 0 {
				time.AfterFunc(testCase.brokerUpAfter, func() {
					if listener, err := net.Listen("tcp", address.String()); err == nil {
						t.Cleanup(func() { _ = listener.Close() })
						go serveFakeBroker(listener)
					}
				})
			}
			connected := make(chan struct{}, 1)
			started := time.Now()
			client, err := brokerConnect(ctx, configFile, brokerSession{keepAlive: brokerInterval, pingTimeout: brokerTimeout, onConnect: func(mqtt.Client) { connected <- struct{}{} }})
			if (err != nil) != testCase.expectedError {
				t.Fatalf("connect: got error [%v] after [%s] want error %v", err, time.Since(started), testCase.expectedError)
			}
			if err != nil {
				if time.Since(started) > testCase.cancelAfter+10*time.Second {
					t.Fatalf("abandon: got [%s] want within [%s] of the cancel", time.Since(started), 10*time.Second)
				}
				return
			}
			defer client.Disconnect(0)
			select {
			case <-connected:
			case <-time.After(5 * time.Second):
				t.Fatalf("on connect handler: got none after [%s]", time.Since(started))
			}
			if elapsed := time.Since(started); elapsed < testCase.brokerUpAfter {
				t.Fatalf("connected: got [%s] before the broker was up at [%s]", elapsed, testCase.brokerUpAfter)
			}
		})
	}
}

func serveFakeBroker(listener net.Listener) {
	for {
		connection, err := listener.Accept()
		if err != nil {
			return
		}
		go func() {
			defer func() { _ = connection.Close() }()
			reader := bufio.NewReader(connection)
			for {
				header, err := reader.ReadByte()
				if err != nil {
					return
				}
				length, multiplier := 0, 1
				for {
					digit, err := reader.ReadByte()
					if err != nil {
						return
					}
					length += int(digit&0x7f) * multiplier
					multiplier *= 128
					if digit&0x80 == 0 {
						break
					}
				}
				if _, err := reader.Discard(length); err != nil {
					return
				}
				switch header >> 4 {
				case 1:
					_, _ = connection.Write([]byte{0x20, 0x02, 0x00, 0x00})
				case 12:
					_, _ = connection.Write([]byte{0xd0, 0x00})
				case 14:
					return
				}
			}
		}()
	}
}
