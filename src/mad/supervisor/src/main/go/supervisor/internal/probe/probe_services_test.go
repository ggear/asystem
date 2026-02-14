package probe

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"supervisor/internal/testutil"
	"testing"
	"time"

	"github.com/docker/docker/api/types/container"
	"github.com/docker/docker/client"
)

func TestProbeServices_Services(t *testing.T) {
	tests := []struct {
		name                  string
		containersToBeCreated int
		newDockerClient       func() (*client.Client, error)
		listContainers        func(context.Context, *client.Client) ([]container.Summary, error)
		statsOneShot          func(context.Context, *client.Client, string) (container.StatsResponseReader, error)
		inspectContainer      func(context.Context, *client.Client, string) (container.InspectResponse, error)
		expectError           bool
	}{
		{
			name:                  "happy_no_services",
			containersToBeCreated: 0,
			expectError:           false,
		},
		{
			name:                  "happy_one_service",
			containersToBeCreated: 1,
			expectError:           false,
		},
		{
			name:                  "happy_three_services",
			containersToBeCreated: 3,
			expectError:           false,
		},
		{
			name:                  "happy_reconnection",
			containersToBeCreated: 1,
			newDockerClient:       func() (*client.Client, error) { return &client.Client{}, nil },
			listContainers: func() func(context.Context, *client.Client) ([]container.Summary, error) {
				call := 0
				return func(_ context.Context, _ *client.Client) ([]container.Summary, error) {
					call++
					if call == 1 {
						return nil, errors.New("temporary failure")
					}
					return []container.Summary{{ID: "c1", Names: []string{"/c1"}}}, nil
				}
			}(),
			statsOneShot: func(_ context.Context, _ *client.Client, _ string) (container.StatsResponseReader, error) {
				payload, err := json.Marshal(container.StatsResponse{
					CPUStats: container.CPUStats{
						CPUUsage:    container.CPUUsage{TotalUsage: 2},
						SystemUsage: 4,
						OnlineCPUs:  1,
					},
					PreCPUStats: container.CPUStats{
						CPUUsage:    container.CPUUsage{TotalUsage: 1},
						SystemUsage: 2,
						OnlineCPUs:  1,
					},
					MemoryStats: container.MemoryStats{
						Limit: 100,
						Usage: 1,
					},
				})
				if err != nil {
					return container.StatsResponseReader{}, err
				}
				return container.StatsResponseReader{Body: io.NopCloser(bytes.NewReader(payload))}, nil
			},
			inspectContainer: func(_ context.Context, _ *client.Client, _ string) (container.InspectResponse, error) {
				return container.InspectResponse{
					ContainerJSONBase: &container.ContainerJSONBase{
						State: &container.State{
							StartedAt: time.Now().Add(-time.Minute).Format(time.RFC3339Nano),
						},
						RestartCount: 0,
						Image:        "test-image",
					},
					Config: &container.Config{Image: "test-image"},
				}, nil
			},
			expectError: false,
		},
		{
			name:            "sad_docker_client_error",
			newDockerClient: func() (*client.Client, error) { return nil, errors.New("boom") },
			expectError:     true,
		},
		{
			name:            "sad_list_containers_error",
			newDockerClient: func() (*client.Client, error) { return &client.Client{}, nil },
			listContainers:  func(_ context.Context, _ *client.Client) ([]container.Summary, error) { return nil, errors.New("boom") },
			expectError:     true,
		},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			var containerNames []string
			if tt.containersToBeCreated > 0 && tt.newDockerClient == nil && tt.listContainers == nil {
				for i := 0; i < tt.containersToBeCreated; i++ {
					containerNames = append(containerNames, fmt.Sprintf("sleep-services-%d", i+1))
				}
				_, err := testutil.SetupSleepContainer(t, "", false, containerNames...)
				if err != nil {
					t.Fatalf("setup sleep container failed: %v", err)
				}
			}
			services := NewServices()
			if tt.newDockerClient != nil {
				services.newDockerClient = tt.newDockerClient
			}
			if tt.listContainers != nil {
				services.listContainers = tt.listContainers
			}
			if tt.statsOneShot != nil {
				services.statsOneShot = tt.statsOneShot
			}
			if tt.inspectContainer != nil {
				services.inspectContainer = tt.inspectContainer
			}
			slice, err := services.Services()
			if tt.expectError {
				if err == nil {
					t.Fatalf("expected error but got nil")
				}
				return
			} else if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if len(slice) != tt.containersToBeCreated {
				t.Fatalf("expected %d services, got %d", tt.containersToBeCreated, len(slice))
			}
			for _, service := range slice {
				name, err := service.Name()
				if err != nil {
					t.Fatalf("unexpected name error: %v", err)
				}
				if name == "" {
					t.Fatalf("expected service name")
				}
				usedProcessor, err := service.UsedProcessor()
				if errors.Is(err, ErrProcessorProbeWarmingUp) {
					time.Sleep(time.Second)
					usedProcessor, err = service.UsedProcessor()
				}
				if err != nil {
					t.Fatalf("unexpected processor error: %v", err)
				}
				if usedProcessor < 0 || usedProcessor > 100 {
					t.Fatalf("usedProcessor out of range [%d]", usedProcessor)
				}
				usedMemory, err := service.UsedMemory()
				if err != nil {
					t.Fatalf("unexpected memory error: %v", err)
				}
				if usedMemory < 0 || usedMemory > 100 {
					t.Fatalf("usedMemory out of range [%d]", usedMemory)
				}
				backupStatus, err := service.BackupStatus()
				if err != nil && err.Error() != "backup status not available" {
					t.Fatalf("unexpected backup status error: %v", err)
				}
				_ = backupStatus
				healthStatus, err := service.HealthStatus()
				if err != nil {
					t.Fatalf("unexpected health status error: %v", err)
				}
				_ = healthStatus
				configuredStatus, err := service.ConfiguredStatus()
				if err != nil {
					t.Fatalf("unexpected configured status error: %v", err)
				}
				_ = configuredStatus
				restartCount, err := service.RestartCount()
				if err != nil {
					t.Fatalf("unexpected restart count error: %v", err)
				}
				if restartCount < 0 {
					t.Fatalf("restart count out of range [%d]", restartCount)
				}
				runtime, err := service.Runtime()
				if err != nil {
					t.Fatalf("unexpected runtime error: %v", err)
				}
				if runtime < 0 {
					t.Fatalf("runtime out of range: %v", runtime)
				}
				version, err := service.Version()
				if err != nil {
					t.Fatalf("unexpected version error: %v", err)
				}
				if version == "" {
					t.Fatalf("expected version value")
				}
			}
		})
	}
}

func TestProbeServices_Health(t *testing.T) {
	tests := []struct {
		name          string
		healthScript  string
		expectHealthy bool
		expectError   bool
	}{
		{
			name:          "happy_health_healthy",
			healthScript:  testutil.FindTestFile(t, "healthy.sh", "health"),
			expectHealthy: true,
			expectError:   false,
		},
		{
			name:          "happy_health_unhealthy",
			healthScript:  testutil.FindTestFile(t, "unhealthy.sh", "health"),
			expectHealthy: false,
			expectError:   false,
		},
		{
			name:          "happy_health_bad",
			healthScript:  testutil.FindTestFile(t, "bad.sh", "health"),
			expectHealthy: false,
			expectError:   false,
		},
		{
			name:          "happy_health_unknown",
			healthScript:  "",
			expectHealthy: false,
			expectError:   false,
		},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			_, err := testutil.SetupSleepContainer(t, testCase.healthScript, testCase.expectHealthy, "sleep-health-1")
			if err != nil {
				t.Fatalf("setup sleep container failed: %v", err)
			}
			services := NewServices()
			serviceSlice, err := services.Services()
			if err != nil {
				t.Fatalf("Services failed: %v", err)
			}
			if len(serviceSlice) != 1 {
				t.Fatalf("expected 1 service, got %d", len(serviceSlice))
			}
			sleepService := serviceSlice[0]
			_, healthErr := sleepService.HealthStatus()
			if testCase.expectError {
				if healthErr == nil {
					t.Fatalf("expected health status error")
				}
			} else {
				if healthErr != nil {
					t.Fatalf("unexpected health status error: %v", healthErr)
				}
			}
		})
	}
}
