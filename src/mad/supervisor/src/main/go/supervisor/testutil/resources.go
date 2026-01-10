package testutil

import (
	"context"
	"fmt"
	"os"
	"path/filepath"
	"testing"
	"time"

	mqtt "github.com/eclipse/paho.mqtt.golang"
	"github.com/testcontainers/testcontainers-go"
	"github.com/testcontainers/testcontainers-go/wait"
)

func SetupBrokerService(t *testing.T) (testcontainers.Container, mqtt.Client, error) {
	start := time.Now()
	t.Helper()
	ctx := context.Background()
	req := testcontainers.ContainerRequest{
		Image:        "eclipse-mosquitto:2.0.22",
		ExposedPorts: []string{"1883/tcp"},
		Files: []testcontainers.ContainerFile{{
			HostFilePath:      GetPath(t, []string{}, "mosquitto.conf"),
			ContainerFilePath: "/mosquitto/config/mosquitto.conf",
			FileMode:          0644,
		}},
		WaitingFor: wait.ForAll(
			wait.ForListeningPort("1883/tcp"),
		).WithDeadline(15 * time.Second),
	}
	container, err := testcontainers.GenericContainer(
		ctx,
		testcontainers.GenericContainerRequest{
			ContainerRequest: req,
			Started:          true,
		},
	)
	if err != nil {
		return nil, nil, err
	}
	host := "127.0.0.1"
	port, err := container.MappedPort(ctx, "1883")
	if err != nil {
		return nil, nil, fmt.Errorf("failed to get mapped port: %w", err)
	}
	os.Setenv("VERNEMQ_HOST", host)
	os.Setenv("VERNEMQ_API_PORT", port.Port())
	brokerURL := fmt.Sprintf("tcp://%s:%s", host, port.Port())
	opts := mqtt.NewClientOptions().
		AddBroker(brokerURL).
		SetClientID(fmt.Sprintf("go-test-%d", time.Now().UnixNano())).
		SetCleanSession(true).
		SetConnectTimeout(2 * time.Second)
	client := mqtt.NewClient(opts)
	var connectError error
	for i := 0; i < 50; i++ {
		token := client.Connect()
		token.Wait()
		if token.Error() == nil && client.IsConnected() {
			break
		}
		connectError = token.Error()
		time.Sleep(200 * time.Millisecond)
	}
	if !client.IsConnected() {
		_ = container.Terminate(ctx)
		return nil, nil, fmt.Errorf("failed to connect to broker [%v]: %w", brokerURL, connectError)
	}
	t.Cleanup(func() {
		client.Disconnect(250)
		_ = container.Terminate(context.Background())
		t.Logf("Broker container stopped in [%v ms]", time.Since(start).Milliseconds())
	})
	t.Logf("Broker container started in [%v ms] at %s", time.Since(start).Milliseconds(), brokerURL)
	return container, client, nil
}

func SetupSleepContainer(t *testing.T) (testcontainers.Container, error) {
	start := time.Now()
	t.Helper()
	ctx := context.Background()
	req := testcontainers.ContainerRequest{
		Name:  "sleep",
		Image: "alpine",
		Cmd:   []string{"sleep", "99999"},
	}
	container, err := testcontainers.GenericContainer(ctx, testcontainers.GenericContainerRequest{
		ContainerRequest: req,
		Started:          true,
	})
	if err != nil {
		return nil, err
	}
	t.Cleanup(func() {
		stop := time.Now()
		_ = container.Terminate(context.Background())
		t.Logf("Sleep container stopped in [%v ms]", time.Since(stop).Milliseconds())
	})
	t.Logf("Sleep container started in [%v ms]", time.Since(start).Milliseconds())
	return container, nil
}

func GetPath(t *testing.T, dirs []string, filename string) string {
	t.Helper()
	dir, err := os.Getwd()
	if err != nil {
		t.Fatalf("getwd failed: %v", err)
	}
	path := filepath.Join(append(append([]string{dir, "../../../../test/resources"}, dirs...), filename)...)
	if _, err := os.Stat(path); err != nil {
		t.Fatalf("file not found: %s (%v)", path, err)
	}
	return path
}

func GetSchemaPath(t *testing.T, schemaFilename string) string {
	return GetPath(t, []string{"schema"}, schemaFilename)
}
