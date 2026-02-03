package probe

import (
	"context"
	"errors"
	"supervisor/testutil"
	"testing"

	"github.com/docker/docker/api/types/container"
	"github.com/docker/docker/client"
)

func TestServices_Services(t *testing.T) {
	sleepNames := []string{"sleep-one", "sleep-two"}
	_, err := testutil.SetupSleepContainerWithoutHealth(t, sleepNames)
	if err != nil {
		t.Fatalf("setup sleep container failed: %v", err)
	}
	tests := []struct {
		name string
		run  func(t *testing.T, sleepService Service, expectedName string)
	}{
		{
			name: "basic",
			run: func(t *testing.T, sleepService Service, expectedName string) {
				name, err := sleepService.Name()
				if err != nil {
					t.Fatalf("Name failed: %v", err)
				}
				if name != expectedName {
					t.Fatalf("Got name = %q, expected %q", name, expectedName)
				}
				if value, err := sleepService.UsedProcessor(); err == nil {
					if value < 0 || value > 100 {
						t.Fatalf("Got usedProcessor = %d, expected between 0 and 100", value)
					}
				}
				if value, err := sleepService.UsedMemory(); err == nil {
					if value < 0 || value > 100 {
						t.Fatalf("Got usedMemory = %d, expected between 0 and 100", value)
					}
				}
				_, _ = sleepService.HealthStatus()
				if configured, err := sleepService.ConfiguredStatus(); err != nil {
					t.Fatalf("ConfiguredStatus failed: %v", err)
				} else if !configured {
					t.Fatalf("ConfiguredStatus = false, expected true")
				}
				if restarts, err := sleepService.RestartCount(); err != nil {
					t.Fatalf("RestartCount failed: %v", err)
				} else if restarts < 0 {
					t.Fatalf("RestartCount = %d, expected >= 0", restarts)
				}
				if runtime, err := sleepService.Runtime(); err != nil {
					t.Fatalf("Runtime failed: %v", err)
				} else if runtime <= 0 {
					t.Fatalf("Runtime = %v, expected > 0", runtime)
				}
				if version, err := sleepService.Version(); err != nil {
					t.Fatalf("Version failed: %v", err)
				} else if version == "" {
					t.Fatalf("Version empty, expected value")
				}
				if _, err := sleepService.BackupStatus(); err == nil {
					t.Fatalf("BackupStatus expected error")
				}
			},
		},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			services := NewServices()
			serviceSlice, err := services.Services()
			if err != nil {
				t.Fatalf("Services failed: %v", err)
			}
			for _, name := range sleepNames {
				sleepService, ok := findService(serviceSlice, name)
				if !ok {
					t.Fatalf("sleep service %q not found", name)
				}
				testCase.run(t, sleepService, name)
			}
		})
	}
}

func TestServices_ServicesEdgeCases(t *testing.T) {
	sleepNames := []string{"sleep-one", "sleep-two"}
	_, err := testutil.SetupSleepContainerWithHealth(t, sleepNames)
	if err != nil {
		t.Fatalf("setup sleep container failed: %v", err)
	}
	tests := []struct {
		name   string
		run    func(*Services)
		assert func(t *testing.T, serviceSlice []Service)
	}{
		{
			name: "no containers",
			run: func(services *Services) {
				services.listContainers = func(context.Context, *client.Client) ([]container.Summary, error) {
					return []container.Summary{}, nil
				}
			},
			assert: func(t *testing.T, serviceSlice []Service) {
				if len(serviceSlice) != 0 {
					t.Fatalf("Got services = %d, expected 0", len(serviceSlice))
				}
			},
		},
		{
			name: "stats error",
			run: func(services *Services) {
				services.statsOneShot = func(context.Context, *client.Client, string) (container.StatsResponseReader, error) {
					return container.StatsResponseReader{}, errors.New("boom")
				}
			},
			assert: func(t *testing.T, serviceSlice []Service) {
				for _, name := range sleepNames {
					sleepService, ok := findService(serviceSlice, name)
					if !ok {
						t.Fatalf("sleep service %q not found", name)
					}
					if _, err := sleepService.UsedProcessor(); err == nil {
						t.Fatalf("UsedProcessor expected error")
					}
					if _, err := sleepService.UsedMemory(); err == nil {
						t.Fatalf("UsedMemory expected error")
					}
				}
			},
		},
		{
			name: "inspect error",
			run: func(services *Services) {
				services.inspectContainer = func(context.Context, *client.Client, string) (container.InspectResponse, error) {
					return container.InspectResponse{}, errors.New("boom")
				}
			},
			assert: func(t *testing.T, serviceSlice []Service) {
				for _, name := range sleepNames {
					sleepService, ok := findService(serviceSlice, name)
					if !ok {
						t.Fatalf("sleep service %q not found", name)
					}
					if _, err := sleepService.HealthStatus(); err == nil {
						t.Fatalf("HealthStatus expected error")
					}
					if _, err := sleepService.Runtime(); err == nil {
						t.Fatalf("Runtime expected error")
					}
					if _, err := sleepService.RestartCount(); err == nil {
						t.Fatalf("RestartCount expected error")
					}
					if _, err := sleepService.Version(); err == nil {
						t.Fatalf("Version expected error")
					}
					if _, err := sleepService.ConfiguredStatus(); err == nil {
						t.Fatalf("ConfiguredStatus expected error")
					}
				}
			},
		},
		{
			name: "docker reconnect",
			run: func(services *Services) {
				originalList := services.listContainers
				callCount := 0
				services.listContainers = func(ctx context.Context, dockerClient *client.Client) ([]container.Summary, error) {
					callCount++
					if callCount == 1 {
						return nil, errors.New("disconnected")
					}
					return originalList(ctx, dockerClient)
				}
			},
			assert: func(t *testing.T, serviceSlice []Service) {
				for _, name := range sleepNames {
					sleepService, ok := findService(serviceSlice, name)
					if !ok {
						t.Fatalf("sleep service %q not found", name)
					}
					actual, err := sleepService.Name()
					if err != nil {
						t.Fatalf("Name failed: %v", err)
					}
					if actual != name {
						t.Fatalf("Got name = %q, expected %q", actual, name)
					}
				}
			},
		},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			services := NewServices()
			testCase.run(services)
			serviceSlice, err := services.Services()
			if err != nil {
				t.Fatalf("Services failed: %v", err)
			}
			testCase.assert(t, serviceSlice)
		})
	}
}

func TestServices_ServicesHealth(t *testing.T) {
	tests := []struct {
		name          string
		healthScript  string
		expectHealthy bool
		expectError   bool
	}{
		{
			name:          "health_unknown",
			healthScript:  "",
			expectHealthy: false,
			expectError:   false,
		},
		{
			name:          "health_bad",
			healthScript:  testutil.Path(t, []string{"health"}, "bad.sh"),
			expectHealthy: false,
			expectError:   false,
		},
		{
			name:          "health_healthy",
			healthScript:  testutil.Path(t, []string{"health"}, "healthy.sh"),
			expectHealthy: true,
			expectError:   false,
		},
		{
			name:          "health_unhealthy",
			healthScript:  testutil.Path(t, []string{"health"}, "unhealthy.sh"),
			expectHealthy: false,
			expectError:   false,
		},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			sleepNames := []string{"sleep-health-one", "sleep-health-two"}
			_, err := testutil.SetupSleepContainer(t, sleepNames, testCase.healthScript, testCase.expectHealthy)
			if err != nil {
				t.Fatalf("setup sleep container failed: %v", err)
			}
			services := NewServices()
			serviceSlice, err := services.Services()
			if err != nil {
				t.Fatalf("Services failed: %v", err)
			}
			for _, name := range sleepNames {
				sleepService, found := findService(serviceSlice, name)
				if !found {
					t.Fatalf("sleep service %q not found", name)
				}
				healthValue, healthErr := sleepService.HealthStatus()
				if testCase.expectError {
					if healthErr == nil {
						t.Fatalf("expected health status error")
					}
				} else {
					if healthErr != nil {
						t.Fatalf("unexpected health status error: %v", healthErr)
					}
					if healthValue != testCase.expectHealthy {
						t.Fatalf("Got healthStatus = %v, expected %v", healthValue, testCase.expectHealthy)
					}
				}
			}
		})
	}
}

func findService(services []Service, name string) (Service, bool) {
	for _, service := range services {
		if service.name == name {
			return service, true
		}
	}
	return Service{}, false
}
