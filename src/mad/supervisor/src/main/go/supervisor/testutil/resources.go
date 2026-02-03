package testutil

import (
	"context"
	"fmt"
	"io"
	"log"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"testing"
	"time"

	"github.com/docker/docker/api/types/container"
	"github.com/docker/docker/client"
	"github.com/docker/docker/errdefs"
	mqtt "github.com/eclipse/paho.mqtt.golang"
	"github.com/testcontainers/testcontainers-go"
	tclog "github.com/testcontainers/testcontainers-go/log"
	"github.com/testcontainers/testcontainers-go/wait"
)

var suppressTestcontainersLoggingOnce sync.Once

func suppressTestcontainersLogging() {
	suppressTestcontainersLoggingOnce.Do(func() {
		tclog.SetDefault(log.New(io.Discard, "", 0))
	})
}

func SetupBrokerService(t *testing.T) (testcontainers.Container, mqtt.Client, error) {
	start := time.Now()
	t.Helper()
	suppressTestcontainersLogging()
	contextValue := context.Background()
	containerRequest := testcontainers.ContainerRequest{
		Image:        "eclipse-mosquitto:2.0.22",
		ExposedPorts: []string{"1883/tcp"},
		Files: []testcontainers.ContainerFile{{
			HostFilePath:      Path(t, []string{}, "mosquitto.conf"),
			ContainerFilePath: "/mosquitto/config/mosquitto.conf",
			FileMode:          0644,
		}},
		WaitingFor: wait.ForAll(
			wait.ForListeningPort("1883/tcp"),
		).WithDeadline(15 * time.Second),
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

func SetupSleepContainerWithHealth(t *testing.T, names []string) ([]testcontainers.Container, error) {
	return SetupSleepContainer(t, names, Path(t, []string{"health"}, "healthy.sh"), true)
}

func SetupSleepContainerWithoutHealth(t *testing.T, names []string) ([]testcontainers.Container, error) {
	return SetupSleepContainer(t, names, "", false)
}

func SetupSleepContainer(t *testing.T, names []string, healthScriptPath string, healthyScriptExit bool) ([]testcontainers.Container, error) {
	start := time.Now()
	t.Helper()
	suppressTestcontainersLogging()
	contextValue := context.Background()
	if len(names) == 0 {
		names = []string{"sleep"}
	}
	uniqueNames := make([]string, 0, len(names))
	nameCounts := make(map[string]int)
	for _, rawName := range names {
		base := strings.TrimSpace(rawName)
		if base == "" {
			base = "sleep"
		}
		count := nameCounts[base]
		nameCounts[base] = count + 1
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
	containers := make([]testcontainers.Container, 0, len(uniqueNames))
	reuseContainers := healthScriptPath == ""
	for _, name := range uniqueNames {
		if !reuseContainers {
			removeErr := func() error {
				dockerClient, err := client.NewClientWithOpts(client.FromEnv, client.WithAPIVersionNegotiation())
				if err != nil {
					return err
				}
				defer func(dockerClient *client.Client) {
					_ = dockerClient.Close()
				}(dockerClient)
				removeErr := dockerClient.ContainerRemove(contextValue, name, container.RemoveOptions{Force: true})
				if removeErr == nil {
					return nil
				}
				removeErrText := strings.ToLower(removeErr.Error())
				if errdefs.IsNotFound(removeErr) || strings.Contains(removeErrText, "no such container") || strings.Contains(removeErrText, "not found") {
					return nil
				}
				return removeErr
			}()
			if removeErr != nil {
				return nil, removeErr
			}
		}
		containerRequest := testcontainers.ContainerRequest{
			Name:  name,
			Image: "alpine",
			Cmd:   []string{"sleep", "99999"},
		}
		if healthScriptPath != "" {
			containerRequest.Files = []testcontainers.ContainerFile{{
				HostFilePath:      healthScriptPath,
				ContainerFilePath: "/healthcheck.sh",
				FileMode:          0755,
			}}
			containerRequest.ConfigModifier = func(config *container.Config) {
				if config == nil {
					return
				}
				config.Healthcheck = &container.HealthConfig{
					Test:        []string{"CMD-SHELL", "/healthcheck.sh"},
					Interval:    250 * time.Millisecond,
					Timeout:     250 * time.Millisecond,
					Retries:     1,
					StartPeriod: 0,
				}
			}
			containerRequest.WaitingFor = nil
		}
		containerInstance, err := testcontainers.GenericContainer(contextValue, testcontainers.GenericContainerRequest{
			ContainerRequest: containerRequest,
			Started:          true,
			Reuse:            reuseContainers,
		})
		if err != nil {
			for _, started := range containers {
				_ = started.Terminate(context.Background())
			}
			return nil, err
		}
		containers = append(containers, containerInstance)
		if healthScriptPath != "" {
			expectedStatus := container.Unhealthy
			if healthyScriptExit {
				expectedStatus = container.Healthy
			}
			waitErr := func() error {
				dockerClient, err := client.NewClientWithOpts(client.FromEnv, client.WithAPIVersionNegotiation())
				if err != nil {
					return err
				}
				defer func(dockerClient *client.Client) {
					_ = dockerClient.Close()
				}(dockerClient)
				deadline := time.Now().Add(10 * time.Second)
				for time.Now().Before(deadline) {
					containerInfo, inspectErr := dockerClient.ContainerInspect(contextValue, name)
					if inspectErr == nil && containerInfo.State != nil && containerInfo.State.Health != nil {
						if containerInfo.State.Health.Status == expectedStatus {
							return nil
						}
					}
					time.Sleep(200 * time.Millisecond)
				}
				return fmt.Errorf("health status %q not reached for %s", expectedStatus, name)
			}()
			if waitErr != nil {
				for _, started := range containers {
					_ = started.Terminate(context.Background())
				}
				return nil, waitErr
			}
		}
	}
	t.Cleanup(func() {
		stop := time.Now()
		stopContext, stopCancel := context.WithTimeout(context.Background(), time.Second)
		defer stopCancel()
		for _, containerInstance := range containers {
			_ = containerInstance.Terminate(stopContext)
		}
		t.Logf("Sleep containers stopped in [%v ms]", time.Since(stop).Milliseconds())
	})
	t.Logf("Sleep containers started in [%v ms]", time.Since(start).Milliseconds())
	return containers, nil
}

func Path(t *testing.T, dirs []string, filename string) string {
	t.Helper()
	workingDirectory, err := os.Getwd()
	if err != nil {
		t.Fatalf("getwd failed: %v", err)
	}
	testRoot := ""
	searchDir := workingDirectory
	for {
		candidate := filepath.Join(searchDir, "supervisor", "src", "test")
		if info, err := os.Stat(candidate); err == nil && info.IsDir() {
			testRoot = candidate
			break
		}
		parent := filepath.Dir(searchDir)
		if parent == searchDir {
			t.Fatalf("test root not found from: %s", workingDirectory)
		}
		searchDir = parent
	}
	path := filepath.Join(append(append([]string{testRoot, "resources"}, dirs...), filename)...)
	if _, err := os.Stat(path); err != nil {
		t.Fatalf("file not found: %s (%v)", path, err)
	}
	return path
}

func SchemaPath(t *testing.T, schemaFilename string) string {
	return Path(t, []string{"schema"}, schemaFilename)
}
