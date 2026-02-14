package testutil

import (
	"context"
	"fmt"
	"io"
	"log"
	"os"
	"strings"
	"sync"
	"testing"
	"time"

	cerrdefs "github.com/containerd/errdefs"
	"github.com/docker/docker/api/types/container"
	"github.com/docker/docker/client"
	mqtt "github.com/eclipse/paho.mqtt.golang"
	"github.com/testcontainers/testcontainers-go"
	tclog "github.com/testcontainers/testcontainers-go/log"
	"github.com/testcontainers/testcontainers-go/wait"
)

func SetupBrokerContainer(t *testing.T) (testcontainers.Container, mqtt.Client, error) {
	start := time.Now()
	t.Helper()
	containerSilenceLogs()
	contextValue := context.Background()
	containerRequest := testcontainers.ContainerRequest{
		Image:        "eclipse-mosquitto:2.0.22",
		ExposedPorts: []string{"1883/tcp"},
		Files: []testcontainers.ContainerFile{{
			HostFilePath:      FindTestFile(t, "mosquitto.conf"),
			ContainerFilePath: "/mosquitto/config/mosquitto.conf",
			FileMode:          0644,
		}},
		WaitingFor: wait.ForAll(
			wait.ForListeningPort("1883/tcp"),
		).WithDeadline(12 * time.Second),
	}
	brokerContainer, err := testcontainers.GenericContainer(
		contextValue,
		testcontainers.GenericContainerRequest{
			ContainerRequest: containerRequest,
			Started:          true,
		},
	)
	if err != nil {
		return nil, nil, err
	}
	host := "127.0.0.1"
	port, err := brokerContainer.MappedPort(contextValue, "1883/tcp")
	if err != nil {
		return nil, nil, fmt.Errorf("failed to get mapped port: %w", err)
	}
	_ = os.Setenv("VERNEMQ_HOST", host)
	_ = os.Setenv("VERNEMQ_API_PORT", port.Port())
	brokerURL := fmt.Sprintf("tcp://%s:%s", host, port.Port())
	mqttClientOptions := mqtt.NewClientOptions().
		AddBroker(brokerURL).
		SetClientID(fmt.Sprintf("go-test-%d", time.Now().UnixNano())).
		SetCleanSession(true).
		SetConnectTimeout(2 * time.Second)
	mqttClient := mqtt.NewClient(mqttClientOptions)
	var connectError error
	for i := 0; i < 50; i++ {
		connectToken := mqttClient.Connect()
		connectToken.Wait()
		if connectToken.Error() == nil && mqttClient.IsConnected() {
			break
		}
		connectError = connectToken.Error()
		time.Sleep(200 * time.Millisecond)
	}
	if !mqttClient.IsConnected() {
		_ = brokerContainer.Terminate(contextValue)
		return nil, nil, fmt.Errorf("failed to connect to broker [%v]: %w", brokerURL, connectError)
	}
	t.Cleanup(func() {
		mqttClient.Disconnect(250)
		_ = brokerContainer.Terminate(context.Background())
		t.Logf("Broker brokerContainer stopped in [%v ms]", time.Since(start).Milliseconds())
	})
	t.Logf("Broker brokerContainer started in [%v ms] at %s", time.Since(start).Milliseconds(), brokerURL)
	return brokerContainer, mqttClient, nil
}

func SetupSleepContainerWithHealth(t *testing.T, names ...string) ([]testcontainers.Container, error) {
	return SetupSleepContainer(t, FindTestFile(t, "healthy.sh", "health"), true, names...)
}

func SetupSleepContainerWithoutHealth(t *testing.T, names ...string) ([]testcontainers.Container, error) {
	return SetupSleepContainer(t, "", false, names...)
}

func SetupSleepContainer(t *testing.T, healthScriptPath string, healthyScriptExit bool, names ...string) ([]testcontainers.Container, error) {
	t.Helper()
	containerSilenceLogs()
	ctx := context.Background()
	if len(names) == 0 {
		names = []string{"sleep"}
	}
	uniqueNames := make([]string, 0, len(names))
	nameCount := make(map[string]int)
	for _, raw := range names {
		base := strings.TrimSpace(raw)
		if base == "" {
			base = "sleep"
		}
		count := nameCount[base]
		nameCount[base] = count + 1
		if count == 0 {
			uniqueNames = append(uniqueNames, base)
		} else {
			uniqueNames = append(uniqueNames, fmt.Sprintf("%s-%d", base, count+1))
		}
	}
	if healthScriptPath != "" {
		if _, err := os.Stat(healthScriptPath); err != nil {
			return nil, err
		}
	}
	dockerClient, err := client.NewClientWithOpts(client.FromEnv, client.WithAPIVersionNegotiation())
	if err != nil {
		return nil, err
	}
	defer func(dockerClient *client.Client) {
		_ = dockerClient.Close()
	}(dockerClient)
	containers := make([]testcontainers.Container, 0, len(uniqueNames))
	for _, containerName := range uniqueNames {
		containerRequest := testcontainers.ContainerRequest{Name: containerName, Image: "alpine", Cmd: []string{"sleep", "99999"}}
		if healthScriptPath != "" {
			containerRequest.Files = []testcontainers.ContainerFile{{HostFilePath: healthScriptPath, ContainerFilePath: "/healthcheck.sh", FileMode: 0755}}
			containerRequest.ConfigModifier = func(config *container.Config) {
				if config == nil {
					return
				}
				config.Healthcheck = &container.HealthConfig{Test: []string{"CMD-SHELL", "/healthcheck.sh"}, Interval: 250 * time.Millisecond, Timeout: 250 * time.Millisecond, Retries: 1, StartPeriod: 0}
			}
			containerRequest.WaitingFor = nil
		}
		containerInstance, err := testcontainers.GenericContainer(ctx, testcontainers.GenericContainerRequest{ContainerRequest: containerRequest, Started: true, Reuse: false})
		if err != nil {
			for _, started := range containers {
				_ = started.Terminate(ctx)
			}
			return nil, err
		}
		containers = append(containers, containerInstance)
		if healthScriptPath != "" {
			expectedStatus := container.Unhealthy
			if healthyScriptExit {
				expectedStatus = container.Healthy
			}
			deadline := time.Now().Add(2 * time.Second)
			reached := false
			for time.Now().Before(deadline) && !reached {
				info, inspectErr := dockerClient.ContainerInspect(ctx, containerName)
				if inspectErr == nil && info.State != nil && info.State.Health != nil && info.State.Health.Status == expectedStatus {
					reached = true
				}
				time.Sleep(200 * time.Millisecond)
			}
			if !reached {
				for _, started := range containers {
					_ = started.Terminate(ctx)
				}
				return nil, fmt.Errorf("health status [%q] not reached for [%s]", expectedStatus, containerName)
			}
		}
	}
	t.Cleanup(func() {
		clientInstance, err := client.NewClientWithOpts(client.FromEnv, client.WithAPIVersionNegotiation())
		if err != nil {
			return
		}
		defer func(clientInstance *client.Client) {
			_ = clientInstance.Close()
		}(clientInstance)
		for _, name := range uniqueNames {
			killErr := clientInstance.ContainerKill(ctx, name, "KILL")
			if killErr != nil && !cerrdefs.IsNotFound(killErr) {
				t.Logf("failed to kill container [%s]: %v", name, killErr)
			}
			removeErr := clientInstance.ContainerRemove(ctx, name, container.RemoveOptions{Force: true})
			if removeErr != nil && !cerrdefs.IsNotFound(removeErr) {
				t.Logf("failed to remove container [%s]: %v", name, removeErr)
			}
		}
	})
	return containers, nil
}

var containerSilenceLogsOnce sync.Once

func containerSilenceLogs() {
	containerSilenceLogsOnce.Do(func() {
		tclog.SetDefault(log.New(io.Discard, "", 0))
	})
}

var _ = SetupBrokerContainer
var _ = SetupSleepContainer
var _ = SetupSleepContainerWithHealth
var _ = SetupSleepContainerWithoutHealth
