package testutil

import (
	"context"
	"fmt"
	"io"
	"log"
	"os"
	"strings"
	"sync"
	"syscall"
	"testing"
	"time"

	cerrdefs "github.com/containerd/errdefs"
	"github.com/docker/docker/api/types/container"
	"github.com/docker/docker/client"
	mqtt "github.com/eclipse/paho.mqtt.golang"
	mobycontainer "github.com/moby/moby/api/types/container"
	"github.com/testcontainers/testcontainers-go"
	tclog "github.com/testcontainers/testcontainers-go/log"
	"github.com/testcontainers/testcontainers-go/wait"
)

func SetupBrokerContainer(t *testing.T) (testcontainers.Container, mqtt.Client, error) {
	start := time.Now()
	t.Helper()
	RequiresDocker(t)
	containerSilenceLogs()
	contextValue := t.Context()
	containerRequest := testcontainers.ContainerRequest{
		Name:         containerBrokerName,
		Labels:       map[string]string{containerLabel: "true"},
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
	for range 50 {
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
	containerOwned.Store(brokerContainer.GetContainerID(), struct{}{})
	t.Cleanup(func() {
		stopStart := time.Now()
		zeroTimeout := time.Duration(0)
		mqttClient.Disconnect(250)
		_ = brokerContainer.Stop(context.Background(), &zeroTimeout)
		containerOwned.Delete(brokerContainer.GetContainerID())
		containerReclaim(t)
		t.Logf("Broker brokerContainer stopped in [%v ms]", time.Since(stopStart).Milliseconds())
	})
	t.Logf("Broker brokerContainer started in [%v ms] at %s", time.Since(start).Milliseconds(), brokerURL)
	return brokerContainer, mqttClient, nil
}

func SetupSleepContainer(t *testing.T, healthScriptPath string, healthyScriptExit bool, names ...string) ([]testcontainers.Container, error) {
	t.Helper()
	RequiresDocker(t)
	containerSilenceLogs()
	ctx := t.Context()
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
			uniqueNames = append(uniqueNames, "sleep-"+base)
		} else {
			uniqueNames = append(uniqueNames, fmt.Sprintf("sleep-%s-%d", base, count+1))
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
		containerRequest := testcontainers.ContainerRequest{Name: containerName, Labels: map[string]string{containerLabel: "true"}, Image: "alpine", Cmd: []string{"sleep", "99999"}}
		if healthScriptPath != "" {
			containerRequest.Files = []testcontainers.ContainerFile{{HostFilePath: healthScriptPath, ContainerFilePath: "/healthcheck.sh", FileMode: 0755}}
			containerRequest.ConfigModifier = func(config *mobycontainer.Config) {
				if config == nil {
					return
				}
				config.Healthcheck = &mobycontainer.HealthConfig{Test: []string{"CMD-SHELL", "/healthcheck.sh"}, Interval: 250 * time.Millisecond, Timeout: 250 * time.Millisecond, Retries: 1, StartPeriod: 0}
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
		containerOwned.Store(containerInstance.GetContainerID(), struct{}{})
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
		zeroTimeout := time.Duration(0)
		for _, c := range containers {
			_ = c.Stop(context.Background(), &zeroTimeout)
			containerOwned.Delete(c.GetContainerID())
		}
		containerReclaim(t)
	})
	return containers, nil
}

var dockerTestActive sync.Map

func RequiresDocker(t *testing.T) {
	t.Helper()
	if _, loaded := dockerTestActive.LoadOrStore(t.Name(), true); loaded {
		return
	}
	fileLock, err := os.OpenFile("/tmp/supervisor-docker-test.lock", os.O_CREATE|os.O_RDWR, 0600)
	if err != nil {
		t.Fatalf("failed to open docker test lock: %v", err)
	}
	if err := syscall.Flock(int(fileLock.Fd()), syscall.LOCK_EX); err != nil {
		_ = fileLock.Close()
		t.Fatalf("failed to acquire docker test lock: %v", err)
	}
	containerReclaim(t)
	t.Cleanup(func() {
		dockerTestActive.Delete(t.Name())
		_ = syscall.Flock(int(fileLock.Fd()), syscall.LOCK_UN)
		_ = fileLock.Close()
	})
}

func containerReclaim(t *testing.T) {
	t.Helper()
	dockerClient, err := client.NewClientWithOpts(client.FromEnv, client.WithAPIVersionNegotiation())
	if err != nil {
		t.Logf("failed to reclaim containers with [%v]", err)
		return
	}
	defer func(dockerClient *client.Client) {
		_ = dockerClient.Close()
	}(dockerClient)
	containerList, err := dockerClient.ContainerList(context.Background(), container.ListOptions{All: true})
	if err != nil {
		t.Logf("failed to list containers for reclaim with [%v]", err)
		return
	}
	for _, listed := range containerList {
		if listed.Labels[containerLabel] != "true" {
			continue
		}
		if _, owned := containerOwned.Load(listed.ID); owned {
			continue
		}
		removeErr := dockerClient.ContainerRemove(context.Background(), listed.ID, container.RemoveOptions{Force: true})
		if removeErr != nil && !cerrdefs.IsNotFound(removeErr) {
			t.Logf("failed to reclaim container [%s] with [%v]", listed.ID, removeErr)
		}
	}
}

const (
	containerBrokerName = "supervisor-test-broker"
	containerLabel      = "supervisor.test"
)

var containerOwned sync.Map

var containerSilenceLogsOnce sync.Once

func containerSilenceLogs() {
	containerSilenceLogsOnce.Do(func() {
		_ = os.Setenv("TESTCONTAINERS_RYUK_DISABLED", "true")
		tclog.SetDefault(log.New(io.Discard, "", 0))
	})
}
