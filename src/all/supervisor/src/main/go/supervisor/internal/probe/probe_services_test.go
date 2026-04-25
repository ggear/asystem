package probe

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"io"
	"supervisor/internal/config"
	"supervisor/internal/metric"
	"supervisor/internal/testutil"
	"testing"
	"time"

	"github.com/docker/docker/api/types/container"
	"github.com/docker/docker/client"
)

func TestProbeServices_Services(t *testing.T) {
	tests := []struct {
		name                 string
		newDockerClient      func() (*client.Client, error)
		listContainers       func(context.Context, *client.Client) ([]container.Summary, error)
		statsOneShot         func(context.Context, *client.Client, string) (container.StatsResponseReader, error)
		inspectContainer     func(context.Context, *client.Client, string) (container.InspectResponse, error)
		setupFunc            func(*servicesProbe)
		validateFunc         func(*testing.T, map[string]service)
		expectedServiceCount int
		expectedError        bool
	}{
		{
			name:            "happy_no_services",
			newDockerClient: func() (*client.Client, error) { return &client.Client{}, nil },
			listContainers: func(_ context.Context, _ *client.Client) ([]container.Summary, error) {
				return []container.Summary{}, nil
			},
			expectedServiceCount: 0,
			expectedError:        false,
		},
		{
			name:            "happy_one_service",
			newDockerClient: func() (*client.Client, error) { return &client.Client{}, nil },
			listContainers: func(_ context.Context, _ *client.Client) ([]container.Summary, error) {
				return makeContainerList("c1"), nil
			},
			statsOneShot:         makeStatsMock(1),
			inspectContainer:     makeInspectMock(),
			expectedServiceCount: 1,
			expectedError:        false,
		},
		{
			name:            "happy_three_services",
			newDockerClient: func() (*client.Client, error) { return &client.Client{}, nil },
			listContainers: func(_ context.Context, _ *client.Client) ([]container.Summary, error) {
				return makeContainerList("c1", "c2", "c3"), nil
			},
			statsOneShot:         makeStatsMock(3),
			inspectContainer:     makeInspectMock(),
			expectedServiceCount: 3,
			expectedError:        false,
		},
		{
			name:                 "happy_reconnection",
			expectedServiceCount: 1,
			newDockerClient:      func() (*client.Client, error) { return &client.Client{}, nil },
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
			statsOneShot: func() func(context.Context, *client.Client, string) (container.StatsResponseReader, error) {
				call := 0
				return func(_ context.Context, _ *client.Client, _ string) (container.StatsResponseReader, error) {
					call++
					totalUsage := uint64(1 + call)
					systemUsage := uint64(2 + (call * 2))
					payload, err := json.Marshal(container.StatsResponse{
						CPUStats: container.CPUStats{
							CPUUsage:    container.CPUUsage{TotalUsage: totalUsage},
							SystemUsage: systemUsage,
							OnlineCPUs:  1,
						},
						PreCPUStats: container.CPUStats{
							CPUUsage:    container.CPUUsage{TotalUsage: totalUsage - 1},
							SystemUsage: systemUsage - 2,
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
				}
			}(),
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
			expectedError: false,
		},
		{
			name:            "happy_reaper_prefix_ignored",
			newDockerClient: func() (*client.Client, error) { return &client.Client{}, nil },
			listContainers: func(_ context.Context, _ *client.Client) ([]container.Summary, error) {
				return []container.Summary{{ID: "r1", Names: []string{"/reaper_foo"}}}, nil
			},
			expectedServiceCount: 0,
			expectedError:        false,
		},
		{
			name:            "happy_empty_name_ignored",
			newDockerClient: func() (*client.Client, error) { return &client.Client{}, nil },
			listContainers: func(_ context.Context, _ *client.Client) ([]container.Summary, error) {
				return []container.Summary{{ID: "e1", Names: []string{}}}, nil
			},
			expectedServiceCount: 0,
			expectedError:        false,
		},
		{
			name:            "happy_duplicate_name_ignored",
			newDockerClient: func() (*client.Client, error) { return &client.Client{}, nil },
			listContainers: func(_ context.Context, _ *client.Client) ([]container.Summary, error) {
				return []container.Summary{
					{ID: "d1", Names: []string{"/dup"}},
					{ID: "d2", Names: []string{"/dup"}},
				}, nil
			},
			statsOneShot:         makeStatsMock(1),
			inspectContainer:     makeInspectMock(),
			expectedServiceCount: 1,
			expectedError:        false,
		},
		{
			name:            "happy_stats_error",
			newDockerClient: func() (*client.Client, error) { return &client.Client{}, nil },
			listContainers: func(_ context.Context, _ *client.Client) ([]container.Summary, error) {
				return makeContainerList("c1"), nil
			},
			statsOneShot: func(_ context.Context, _ *client.Client, _ string) (container.StatsResponseReader, error) {
				return container.StatsResponseReader{}, errors.New("stats unavailable")
			},
			inspectContainer: makeInspectMock(),
			validateFunc: func(t *testing.T, services map[string]service) {
				assertConfiguredStatus(t, services, "c1", false)
			},
			expectedServiceCount: 1,
			expectedError:        false,
		},
		{
			name:            "happy_inspect_error",
			newDockerClient: func() (*client.Client, error) { return &client.Client{}, nil },
			listContainers: func(_ context.Context, _ *client.Client) ([]container.Summary, error) {
				return makeContainerList("c1"), nil
			},
			statsOneShot: makeStatsMock(1),
			inspectContainer: func(_ context.Context, _ *client.Client, _ string) (container.InspectResponse, error) {
				return container.InspectResponse{}, errors.New("inspect unavailable")
			},
			validateFunc: func(t *testing.T, services map[string]service) {
				assertConfiguredStatus(t, services, "c1", false)
			},
			expectedServiceCount: 1,
			expectedError:        false,
		},
		{
			name:            "happy_configured_service_running",
			newDockerClient: func() (*client.Client, error) { return &client.Client{}, nil },
			listContainers: func(_ context.Context, _ *client.Client) ([]container.Summary, error) {
				return makeContainerList("c1"), nil
			},
			statsOneShot:     makeStatsMock(1),
			inspectContainer: makeInspectMock(),
			setupFunc: func(p *servicesProbe) {
				p.configuredServiceNames = []string{"c1"}
			},
			validateFunc: func(t *testing.T, services map[string]service) {
				assertConfiguredStatus(t, services, "c1", true)
			},
			expectedServiceCount: 1,
			expectedError:        false,
		},
		{
			name:            "happy_configured_ghost_service",
			newDockerClient: func() (*client.Client, error) { return &client.Client{}, nil },
			listContainers: func(_ context.Context, _ *client.Client) ([]container.Summary, error) {
				return []container.Summary{}, nil
			},
			setupFunc: func(p *servicesProbe) {
				p.configuredServiceNames = []string{"ghost"}
			},
			validateFunc: func(t *testing.T, services map[string]service) {
				assertConfiguredStatus(t, services, "ghost", true)
			},
			expectedServiceCount: 1,
			expectedError:        false,
		},
		{
			name:                 "sad_docker_client_error",
			expectedServiceCount: 0,
			newDockerClient:      func() (*client.Client, error) { return nil, errors.New("boom") },
			expectedError:        true,
		},
		{
			name:                 "sad_list_containers_error",
			expectedServiceCount: 0,
			newDockerClient:      func() (*client.Client, error) { return &client.Client{}, nil },
			listContainers:       func(_ context.Context, _ *client.Client) ([]container.Summary, error) { return nil, errors.New("boom") },
			expectedError:        true,
		},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			probe := newServicesProbe()
			if tt.newDockerClient != nil {
				probe.newDockerClient = tt.newDockerClient
			}
			if tt.listContainers != nil {
				probe.listContainers = tt.listContainers
			}
			if tt.statsOneShot != nil {
				probe.statsOneShot = tt.statsOneShot
			}
			if tt.inspectContainer != nil {
				probe.inspectContainer = tt.inspectContainer
			}
			if tt.setupFunc != nil {
				tt.setupFunc(probe)
			}
			var err error
			var services map[string]service
			for i := 0; i < 2; i++ {
				services, err = probe.services(context.Background())
				if tt.expectedError {
					if err == nil {
						t.Fatalf("expected error but got nil")
					}
					return
				} else if err != nil {
					t.Fatalf("unexpected error: %v", err)
				}
				if len(services) != tt.expectedServiceCount {
					t.Fatalf("expected %d probe, got %d", tt.expectedServiceCount, len(services))
				}
			}
			if tt.validateFunc != nil {
				tt.validateFunc(t, services)
			} else {
				for _, service := range services {
					isUp, err := service.isUp()
					if err != nil {
						t.Fatalf("unexpected isUp error: %v", err)
					}
					if !isUp {
						t.Fatalf("isUp out of range [%v]", isUp)
					}
					backupStatus, err := service.backupStatus()
					if err != nil && err.Error() != "backup status not available" {
						t.Fatalf("unexpected backup status error: %v", err)
					}
					_ = backupStatus
					healthStatus, err := service.healthStatus()
					if err != nil {
						t.Fatalf("unexpected health status error: %v", err)
					}
					_ = healthStatus
					configuredStatus, err := service.configuredStatus()
					if err != nil {
						t.Fatalf("unexpected configured status error: %v", err)
					}
					_ = configuredStatus
					name := service.name()
					if name == "" {
						t.Fatalf("expected service name")
					}
					version, err := service.version()
					if err != nil {
						t.Fatalf("unexpected version error: %v", err)
					}
					if version == "" {
						t.Fatalf("expected version value")
					}
					usedProcessor, err := service.usedProcessor()
					if errors.Is(err, errProbeWarmingUp) {
						time.Sleep(1 * time.Second)
						usedProcessor, err = service.usedProcessor()
					}
					if err != nil {
						t.Fatalf("unexpected processor error: %v", err)
					}
					if usedProcessor < 0 || usedProcessor > 100 {
						t.Fatalf("usedProcessor out of range [%d]", usedProcessor)
					}
					usedMemory, err := service.usedMemory()
					if err != nil {
						t.Fatalf("unexpected memory error: %v", err)
					}
					if usedMemory < 0 || usedMemory > 100 {
						t.Fatalf("usedMemory out of range [%d]", usedMemory)
					}
					usedDiskOps, err := service.usedDiskOps()
					if err != nil {
						t.Fatalf("unexpected usedDiskOps error: %v", err)
					}
					if usedDiskOps < 0 || usedDiskOps > 100 {
						t.Fatalf("usedDiskOps out of range [%d]", usedDiskOps)
					}
					usedNetwork, err := service.usedNetwork()
					if err != nil {
						t.Fatalf("unexpected usedNetwork error: %v", err)
					}
					if usedNetwork < 0 || usedNetwork > 100 {
						t.Fatalf("usedNetwork out of range [%d]", usedNetwork)
					}
					upTime, err := service.upTime()
					if err != nil {
						t.Fatalf("unexpected runningTime error: %v", err)
					}
					if upTime < 0 {
						t.Fatalf("upTime out of range: %v", upTime)
					}
					maxMemory, err := service.maxMemory()
					if err != nil {
						t.Fatalf("unexpected maxMemory error: %v", err)
					}
					if maxMemory < 0 {
						t.Fatalf("maxMemory out of range: %v", maxMemory)
					}
					restartCount, err := service.restartCount()
					if err != nil {
						t.Fatalf("unexpected restart count error: %v", err)
					}
					if restartCount < 0 {
						t.Fatalf("restart count out of range [%f]", restartCount)
					}
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
		expectedError bool
	}{
		{
			name:          "happy_health_healthy",
			healthScript:  testutil.FindTestFile(t, "healthy.sh", "health"),
			expectHealthy: true,
			expectedError: false,
		},
		{
			name:          "happy_health_unhealthy",
			healthScript:  testutil.FindTestFile(t, "unhealthy.sh", "health"),
			expectHealthy: false,
			expectedError: false,
		},
		{
			name:          "happy_health_bad",
			healthScript:  testutil.FindTestFile(t, "bad.sh", "health"),
			expectHealthy: false,
			expectedError: false,
		},
		{
			name:          "happy_health_unknown",
			healthScript:  "",
			expectHealthy: false,
			expectedError: false,
		},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			_, err := testutil.SetupSleepContainer(t, testCase.healthScript, testCase.expectHealthy, "health-1")
			if err != nil {
				t.Fatalf("setup sleep container failed: %v", err)
			}
			services := newServicesProbe()
			serviceMap, err := services.services(context.Background())
			if err != nil {
				t.Fatalf("Services failed: %v", err)
			}
			sleepService, exists := serviceMap["sleep-health-1"]
			if !exists {
				t.Fatalf("sleep-health-1 not found in %d services", len(serviceMap))
			}
			_, healthErr := sleepService.healthStatus()
			if testCase.expectedError {
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

func TestProbeServices_Run(t *testing.T) {
	tests := []struct {
		name      string
		setupFunc func(*servicesProbe, *metric.RecordCache)
		checkFunc func(*testing.T, *servicesProbe, *metric.RecordCache)
	}{
		{
			name: "happy_delete_on_missing_poll",
			setupFunc: func(p *servicesProbe, cache *metric.RecordCache) {
				host := config.Load("").Host()
				value := metric.ValueData{Pulse: &metric.ValueDataDetail{OK: true, Kind: metric.ValueString, ValueString: "svc-a"}}
				cache.Store(metric.NewServiceRecordGUID(metric.MetricServiceName, host, "svc-a"), &metric.Record{Value: value})
				p.listContainers = func(_ context.Context, _ *client.Client) ([]container.Summary, error) {
					return []container.Summary{}, nil
				}
			},
			checkFunc: func(t *testing.T, p *servicesProbe, cache *metric.RecordCache) {
				if err := p.run(context.Background(), true); err != nil {
					t.Fatalf("Got run error = %v, expected nil", err)
				}
				host := config.Load("").Host()
				if _, ok := cache.Load(metric.NewServiceRecordGUID(metric.MetricServiceName, host, "svc-a")); ok {
					t.Fatalf("Got guid present after missing poll, expected deleted")
				}
			},
		},
		{
			name: "happy_does_not_evict_other_host_services",
			setupFunc: func(p *servicesProbe, cache *metric.RecordCache) {
				value := metric.ValueData{Pulse: &metric.ValueDataDetail{OK: true, Kind: metric.ValueString, ValueString: "svc-a"}}
				cache.Store(metric.NewServiceRecordGUID(metric.MetricServiceName, "other-host", "svc-a"), &metric.Record{Value: value})
				p.listContainers = func(_ context.Context, _ *client.Client) ([]container.Summary, error) {
					return []container.Summary{}, nil
				}
			},
			checkFunc: func(t *testing.T, p *servicesProbe, cache *metric.RecordCache) {
				if err := p.run(context.Background(), true); err != nil {
					t.Fatalf("Got run error = %v, expected nil", err)
				}
				record, ok := cache.Load(metric.NewServiceRecordGUID(metric.MetricServiceName, "other-host", "svc-a"))
				if !ok || record == nil {
					t.Fatalf("Got other-host guid missing, expected preserved")
				}
				if record.Value.Pulse == nil {
					t.Fatalf("Got other-host pulse nil, expected untouched")
				}
			},
		},
		{
			name: "happy_delete_removes_all_service_records",
			setupFunc: func(p *servicesProbe, cache *metric.RecordCache) {
				host := config.Load("").Host()
				value := metric.ValueData{Pulse: &metric.ValueDataDetail{OK: true, Kind: metric.ValueString, ValueString: "v"}}
				cache.Store(metric.NewServiceRecordGUID(metric.MetricServiceName, host, "svc-a"), &metric.Record{Value: value})
				cache.Store(metric.NewServiceRecordGUID(metric.MetricServiceHealthStatus, host, "svc-a"), &metric.Record{Value: value})
				p.listContainers = func(_ context.Context, _ *client.Client) ([]container.Summary, error) {
					return []container.Summary{}, nil
				}
			},
			checkFunc: func(t *testing.T, p *servicesProbe, cache *metric.RecordCache) {
				host := config.Load("").Host()
				if err := p.run(context.Background(), true); err != nil {
					t.Fatalf("Got run error = %v, expected nil", err)
				}
				if _, ok := cache.Load(metric.NewServiceRecordGUID(metric.MetricServiceName, host, "svc-a")); ok {
					t.Fatalf("Got name guid present after missing poll, expected deleted")
				}
				if _, ok := cache.Load(metric.NewServiceRecordGUID(metric.MetricServiceHealthStatus, host, "svc-a")); ok {
					t.Fatalf("Got health guid present after missing poll, expected deleted")
				}
			},
		},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			cache := metric.NewRecordCache()
			p := newServicesProbe()
			p.cache = cache
			p.newDockerClient = func() (*client.Client, error) { return &client.Client{}, nil }
			tt.setupFunc(p, cache)
			tt.checkFunc(t, p, cache)
		})
	}
}

func TestProbe_Version(t *testing.T) {
	tests := []struct {
		name          string
		containerInfo container.InspectResponse
		mountSubDir   string
		expected      string
		expectedError bool
	}{
		{
			name: "happy_ghost_service_env_file_version",
			containerInfo: container.InspectResponse{
				ContainerJSONBase: &container.ContainerJSONBase{Name: "/myservice"},
				Config:            &container.Config{Image: "myservice"},
			},
			mountSubDir:   "happy-1",
			expected:      "10.100.5678",
			expectedError: false,
		},
		{
			name: "happy_image_tag_version",
			containerInfo: container.InspectResponse{
				Config: &container.Config{Image: "myimage:10.100.1234"},
			},
			expected:      "10.100.1234",
			expectedError: false,
		},
		{
			name: "happy_image_tag_snapshot_version",
			containerInfo: container.InspectResponse{
				Config: &container.Config{Image: "myimage:10.100.1000-SNAPSHOT"},
			},
			expected:      "10.100.1000-SNAPSHOT",
			expectedError: false,
		},
		{
			name: "happy_env_file_version",
			containerInfo: container.InspectResponse{
				ContainerJSONBase: &container.ContainerJSONBase{Name: "/myservice"},
				Config:            &container.Config{Image: "myimage:latest"},
			},
			mountSubDir:   "happy-1",
			expected:      "10.100.5678",
			expectedError: false,
		},
		{
			name: "happy_env_file_snapshot_version",
			containerInfo: container.InspectResponse{
				ContainerJSONBase: &container.ContainerJSONBase{Name: "/myservice"},
				Config:            &container.Config{Image: "myimage:latest"},
			},
			mountSubDir:   "happy-2",
			expected:      "10.100.9999-SNAPSHOT",
			expectedError: false,
		},
		{
			name: "happy_no_env_file_returns_dash",
			containerInfo: container.InspectResponse{
				ContainerJSONBase: &container.ContainerJSONBase{Name: "/myservice"},
				Config:            &container.Config{Image: "myimage:latest"},
			},
			mountSubDir:   "sad-1",
			expected:      "-",
			expectedError: false,
		},
		{
			name: "happy_env_file_no_version_line_returns_dash",
			containerInfo: container.InspectResponse{
				ContainerJSONBase: &container.ContainerJSONBase{Name: "/myservice"},
				Config:            &container.Config{Image: "myimage:latest"},
			},
			mountSubDir:   "sad-2",
			expected:      "-",
			expectedError: false,
		},
		{
			name: "happy_nil_config_returns_dash",
			containerInfo: container.InspectResponse{
				ContainerJSONBase: &container.ContainerJSONBase{Name: "/myservice"},
			},
			expected:      "-",
			expectedError: false,
		},
		{
			name: "happy_empty_image_returns_dash",
			containerInfo: container.InspectResponse{
				ContainerJSONBase: &container.ContainerJSONBase{Name: "/myservice"},
				Config:            &container.Config{Image: ""},
			},
			expected:      "-",
			expectedError: false,
		},
		{
			name: "sad_image_tag_version_invalid",
			containerInfo: container.InspectResponse{
				Config:            &container.Config{Image: "myimage:10.100.1234p"},
			},
			expected:      "-",
			expectedError: false,
		},
		{
			name: "sad_image_no_tag_returns_dash",
			containerInfo: container.InspectResponse{
				ContainerJSONBase: &container.ContainerJSONBase{Name: "/myservice"},
				Config:            &container.Config{Image: "myimage"},
			},
			expected:      "-",
			expectedError: false,
		},
		{
			name: "sad_image_empty_tag_returns_dash",
			containerInfo: container.InspectResponse{
				ContainerJSONBase: &container.ContainerJSONBase{Name: "/myservice"},
				Config:            &container.Config{Image: "myimage:"},
			},
			expected:      "-",
			expectedError: false,
		},
		{
			name: "sad_image_tag_v_prefix_returns_dash",
			containerInfo: container.InspectResponse{
				ContainerJSONBase: &container.ContainerJSONBase{Name: "/myservice"},
				Config:            &container.Config{Image: "myimage:v10.100.1234"},
			},
			expected:      "-",
			expectedError: false,
		},
		{
			name: "sad_image_tag_missing_patch_returns_dash",
			containerInfo: container.InspectResponse{
				ContainerJSONBase: &container.ContainerJSONBase{Name: "/myservice"},
				Config:            &container.Config{Image: "myimage:10.100"},
			},
			expected:      "-",
			expectedError: false,
		},
		{
			name: "sad_image_tag_too_few_patch_digits_returns_dash",
			containerInfo: container.InspectResponse{
				ContainerJSONBase: &container.ContainerJSONBase{Name: "/myservice"},
				Config:            &container.Config{Image: "myimage:10.100.123"},
			},
			expected:      "-",
			expectedError: false,
		},
		{
			name: "sad_image_tag_too_many_patch_digits_returns_dash",
			containerInfo: container.InspectResponse{
				ContainerJSONBase: &container.ContainerJSONBase{Name: "/myservice"},
				Config:            &container.Config{Image: "myimage:10.100.12345"},
			},
			expected:      "-",
			expectedError: false,
		},
		{
			name: "sad_image_tag_too_few_minor_digits_returns_dash",
			containerInfo: container.InspectResponse{
				ContainerJSONBase: &container.ContainerJSONBase{Name: "/myservice"},
				Config:            &container.Config{Image: "myimage:10.10.1234"},
			},
			expected:      "-",
			expectedError: false,
		},
		{
			name: "sad_image_tag_too_few_major_digits_returns_dash",
			containerInfo: container.InspectResponse{
				ContainerJSONBase: &container.ContainerJSONBase{Name: "/myservice"},
				Config:            &container.Config{Image: "myimage:1.100.1234"},
			},
			expected:      "-",
			expectedError: false,
		},
		{
			name: "sad_image_tag_invalid_suffix_returns_dash",
			containerInfo: container.InspectResponse{
				ContainerJSONBase: &container.ContainerJSONBase{Name: "/myservice"},
				Config:            &container.Config{Image: "myimage:10.100.1234-RC1"},
			},
			expected:      "-",
			expectedError: false,
		},
		{
			name: "sad_image_tag_latest_returns_dash",
			containerInfo: container.InspectResponse{
				ContainerJSONBase: &container.ContainerJSONBase{Name: "/myservice"},
				Config:            &container.Config{Image: "myimage:latest"},
			},
			expected:      "-",
			expectedError: false,
		},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			t.Cleanup(config.Reset)
			if tt.mountSubDir != "" {
				t.Setenv("SUPERVISOR_MOUNT", testutil.FindDir(t, "src", "test", "resources", "mount", tt.mountSubDir))
			}
			p := newServicesProbe()
			got, err := p.version(tt.containerInfo)
			if tt.expectedError {
				if err == nil {
					t.Fatalf("Got no error, expected error")
				}
				return
			}
			if err != nil {
				t.Fatalf("Got error = %v, expected nil", err)
			}
			if got != tt.expected {
				t.Fatalf("Got version = %q, expected %q", got, tt.expected)
			}
		})
	}
}

func makeStatsMock(containerCount int) func(context.Context, *client.Client, string) (container.StatsResponseReader, error) {
	call := 0
	return func(_ context.Context, _ *client.Client, _ string) (container.StatsResponseReader, error) {
		call++
		totalUsage := uint64(1 + call)
		systemUsage := uint64(2 + (call * 2))
		payload, err := json.Marshal(container.StatsResponse{
			CPUStats: container.CPUStats{
				CPUUsage:    container.CPUUsage{TotalUsage: totalUsage},
				SystemUsage: systemUsage,
				OnlineCPUs:  1,
			},
			PreCPUStats: container.CPUStats{
				CPUUsage:    container.CPUUsage{TotalUsage: totalUsage - 1},
				SystemUsage: systemUsage - 2,
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
	}
}

func makeInspectMock() func(context.Context, *client.Client, string) (container.InspectResponse, error) {
	return func(_ context.Context, _ *client.Client, _ string) (container.InspectResponse, error) {
		return container.InspectResponse{
			ContainerJSONBase: &container.ContainerJSONBase{
				State:        &container.State{StartedAt: time.Now().Add(-time.Minute).Format(time.RFC3339Nano)},
				RestartCount: 0,
				Image:        "test-image",
			},
			Config: &container.Config{Image: "test-image"},
		}, nil
	}
}

func makeContainerList(ids ...string) []container.Summary {
	summaries := make([]container.Summary, len(ids))
	for i, id := range ids {
		summaries[i] = container.Summary{ID: id, Names: []string{"/" + id}}
	}
	return summaries
}

func assertConfiguredStatus(t *testing.T, services map[string]service, name string, want bool) {
	t.Helper()
	s, exists := services[name]
	if !exists {
		t.Fatalf("Got service %q = not found", name)
	}
	got, err := s.configuredStatus()
	if err != nil {
		t.Fatalf("Got configuredStatus error = %v, expected none", err)
	}
	if got != want {
		t.Fatalf("Got configuredStatus = %v, expected %v", got, want)
	}
}
