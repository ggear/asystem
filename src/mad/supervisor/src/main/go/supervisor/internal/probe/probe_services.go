package probe

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"sort"
	"strings"
	"time"

	"github.com/docker/docker/api/types/container"
	"github.com/docker/docker/client"
)

const (
	servicesDockerTimeoutSecs            = 2
	servicesDockerContainerIgnorePattern = "reaper_"
)

type Services struct {
	dockerClient     *client.Client
	newDockerClient  func() (*client.Client, error)
	listContainers   func(context.Context, *client.Client) ([]container.Summary, error)
	statsOneShot     func(context.Context, *client.Client, string) (container.StatsResponseReader, error)
	inspectContainer func(context.Context, *client.Client, string) (container.InspectResponse, error)
}

type Service struct {
	name                string
	nameErr             error
	usedProcessor       int8
	usedProcessorErr    error
	usedMemory          int8
	usedMemoryErr       error
	backupStatus        bool
	backupStatusErr     error
	healthStatus        bool
	healthStatusErr     error
	configuredStatus    bool
	configuredStatusErr error
	restartCount        int
	restartCountErr     error
	runtime             time.Duration
	runtimeErr          error
	version             string
	versionErr          error
}

func NewServices() *Services {
	return &Services{
		newDockerClient: func() (*client.Client, error) {
			return client.NewClientWithOpts(client.FromEnv, client.WithAPIVersionNegotiation())
		},
		listContainers: func(ctx context.Context, dockerClient *client.Client) ([]container.Summary, error) {
			return dockerClient.ContainerList(ctx, container.ListOptions{})
		},
		statsOneShot: func(ctx context.Context, dockerClient *client.Client, id string) (container.StatsResponseReader, error) {
			return dockerClient.ContainerStatsOneShot(ctx, id)
		},
		inspectContainer: func(ctx context.Context, dockerClient *client.Client, id string) (container.InspectResponse, error) {
			return dockerClient.ContainerInspect(ctx, id)
		},
	}
}

func (s *Services) Services() ([]Service, error) {
	if s == nil {
		return nil, errors.New("services not initialised")
	}
	if s.newDockerClient == nil || s.listContainers == nil || s.statsOneShot == nil || s.inspectContainer == nil {
		return nil, errors.New("docker client not initialised")
	}
	dockerClient, err := s.ensureDockerClient()
	if err != nil {
		return nil, fmt.Errorf("ensure docker client: %w", err)
	}
	ctx, cancel := context.WithTimeout(context.Background(), servicesDockerTimeoutSecs*time.Second)
	defer cancel()
	containers, err := s.listContainers(ctx, dockerClient)
	if err != nil {
		dockerClient, err = s.reconnectDockerClient()
		if err != nil {
			return nil, fmt.Errorf("reconnect docker client: %w", err)
		}
		containers, err = s.listContainers(ctx, dockerClient)
		if err != nil {
			return nil, fmt.Errorf("list containers after reconnect: %w", err)
		}
	}
	services := make([]Service, 0, len(containers))
	for _, serviceContainer := range containers {
		name := ""
		for _, rawName := range serviceContainer.Names {
			rawName = strings.TrimPrefix(rawName, "/")
			if rawName != "" {
				name = rawName
				break
			}
		}
		if strings.HasPrefix(name, servicesDockerContainerIgnorePattern) {
			continue
		}
		service := Service{name: name}
		if name == "" {
			service.nameErr = errors.New("service name not available")
		}
		stats, err := fetchStats(ctx, dockerClient, s.statsOneShot, serviceContainer.ID)
		if err != nil {
			service.usedProcessorErr = err
			service.usedMemoryErr = err
		} else {
			usedProcessor, processorErr := processorUsed(stats)
			if processorErr != nil {
				service.usedProcessorErr = processorErr
			} else {
				service.usedProcessor = usedProcessor
			}
			usedMemory, memoryErr := memoryUsed(stats)
			if memoryErr != nil {
				service.usedMemoryErr = memoryErr
			} else {
				service.usedMemory = usedMemory
			}
		}
		inspectInfo, err := fetchInspect(ctx, dockerClient, s.inspectContainer, serviceContainer.ID)
		if err != nil {
			service.healthStatusErr = err
			service.runtimeErr = err
			service.configuredStatusErr = err
			service.restartCountErr = err
			service.versionErr = err
		} else {
			healthStatusValue, healthErr := healthStatus(inspectInfo)
			if healthErr != nil {
				service.healthStatusErr = healthErr
			} else {
				service.healthStatus = healthStatusValue
			}
			runtimeValue, runtimeErr := runtime(inspectInfo)
			if runtimeErr != nil {
				service.runtimeErr = runtimeErr
			} else {
				service.runtime = runtimeValue
			}
			restartCountValue, restartErr := restartCount(inspectInfo)
			if restartErr != nil {
				service.restartCountErr = restartErr
			} else {
				service.restartCount = restartCountValue
			}
			versionValue, versionErr := version(inspectInfo)
			if versionErr != nil {
				service.versionErr = versionErr
			} else {
				service.version = versionValue
			}
		}
		configuredStatusValue, configuredErr := configuredStatus()
		if configuredErr != nil {
			service.configuredStatusErr = configuredErr
		} else {
			service.configuredStatus = configuredStatusValue
		}
		backupStatusValue, backupErr := backupStatus()
		if backupErr != nil {
			service.backupStatusErr = backupErr
		} else {
			service.backupStatus = backupStatusValue
		}
		services = append(services, service)
	}
	sort.Slice(services, func(leftIndex, rightIndex int) bool {
		return services[leftIndex].name < services[rightIndex].name
	})
	return services, nil
}

func (s *Services) Reset() {
	if s == nil {
		return
	}
	if s.dockerClient != nil {
		_ = s.dockerClient.Close()
	}
	*s = *NewServices()
}

func (s *Service) Name() (string, error) {
	if s == nil {
		return "", errors.New("service name not available")
	}
	if s.nameErr != nil {
		err := s.nameErr
		s.nameErr = nil
		return "", err
	}
	return s.name, nil
}

func (s *Service) UsedProcessor() (int8, error) {
	if s.usedProcessorErr != nil {
		err := s.usedProcessorErr
		s.usedProcessorErr = nil
		return 0, err
	}
	return s.usedProcessor, nil
}

func (s *Service) UsedMemory() (int8, error) {
	if s.usedMemoryErr != nil {
		err := s.usedMemoryErr
		s.usedMemoryErr = nil
		return 0, err
	}
	return s.usedMemory, nil
}

func (s *Service) BackupStatus() (bool, error) {
	if s.backupStatusErr != nil {
		err := s.backupStatusErr
		s.backupStatusErr = nil
		return false, err
	}
	return s.backupStatus, nil
}

func (s *Service) HealthStatus() (bool, error) {
	if s.healthStatusErr != nil {
		err := s.healthStatusErr
		s.healthStatusErr = nil
		return false, err
	}
	return s.healthStatus, nil
}

func (s *Service) ConfiguredStatus() (bool, error) {
	if s.configuredStatusErr != nil {
		err := s.configuredStatusErr
		s.configuredStatusErr = nil
		return false, err
	}
	return s.configuredStatus, nil
}

func (s *Service) RestartCount() (int, error) {
	if s.restartCountErr != nil {
		err := s.restartCountErr
		s.restartCountErr = nil
		return 0, err
	}
	return s.restartCount, nil
}

func (s *Service) Runtime() (time.Duration, error) {
	if s.runtimeErr != nil {
		err := s.runtimeErr
		s.runtimeErr = nil
		return 0, err
	}
	return s.runtime, nil
}

func (s *Service) Version() (string, error) {
	if s.versionErr != nil {
		err := s.versionErr
		s.versionErr = nil
		return "", err
	}
	return s.version, nil
}

func (s *Services) ensureDockerClient() (*client.Client, error) {
	if s.dockerClient != nil {
		return s.dockerClient, nil
	}
	dockerClient, err := s.newDockerClient()
	if err != nil {
		return nil, fmt.Errorf("create docker client: %w", err)
	}
	s.dockerClient = dockerClient
	return dockerClient, nil
}

func (s *Services) reconnectDockerClient() (*client.Client, error) {
	if s.dockerClient != nil {
		_ = s.dockerClient.Close()
		s.dockerClient = nil
	}
	return s.ensureDockerClient()
}

func fetchStats(ctx context.Context, dockerClient *client.Client, statsOneShot func(context.Context, *client.Client, string) (container.StatsResponseReader, error), id string) (container.StatsResponse, error) {
	statsReader, err := statsOneShot(ctx, dockerClient, id)
	if err != nil {
		return container.StatsResponse{}, fmt.Errorf("fetch container stats for id [%s]: %w", id, err)
	}
	defer func(reader container.StatsResponseReader) {
		_ = reader.Body.Close()
	}(statsReader)
	var stats container.StatsResponse
	if decodeErr := json.NewDecoder(statsReader.Body).Decode(&stats); decodeErr != nil {
		return container.StatsResponse{}, fmt.Errorf("decode container stats for id [%s]: %w", id, decodeErr)
	}
	return stats, nil
}

func fetchInspect(ctx context.Context, dockerClient *client.Client, inspectContainer func(context.Context, *client.Client, string) (container.InspectResponse, error), id string) (container.InspectResponse, error) {
	info, err := inspectContainer(ctx, dockerClient, id)
	if err != nil {
		return container.InspectResponse{}, fmt.Errorf("inspect container for id [%s]: %w", id, err)
	}
	return info, nil
}

func processorUsed(stats container.StatsResponse) (int8, error) {
	if stats.PreCPUStats.CPUUsage.TotalUsage == 0 && stats.PreCPUStats.SystemUsage == 0 {
		return 0, ErrProcessorProbeWarmingUp
	}
	cpuDelta := float64(stats.CPUStats.CPUUsage.TotalUsage - stats.PreCPUStats.CPUUsage.TotalUsage)
	systemDelta := float64(stats.CPUStats.SystemUsage - stats.PreCPUStats.SystemUsage)
	if systemDelta <= 0 {
		return 0, errors.New("cpu usage unavailable, non-monotonic counters")
	}
	onlineCPUs := float64(stats.CPUStats.OnlineCPUs)
	if onlineCPUs == 0 {
		onlineCPUs = float64(len(stats.CPUStats.CPUUsage.PercpuUsage))
	}
	usedPercent := (cpuDelta / systemDelta) * onlineCPUs * 100.0
	return convertToQuota(usedPercent)
}

func memoryUsed(stats container.StatsResponse) (int8, error) {
	if stats.MemoryStats.Limit == 0 {
		return 0, errors.New("memory limit must be > 0")
	}
	usedPercent := (float64(stats.MemoryStats.Usage) / float64(stats.MemoryStats.Limit)) * 100.0
	return convertToQuota(usedPercent)
}

func healthStatus(containerInfo container.InspectResponse) (bool, error) {
	if containerInfo.State == nil || containerInfo.State.Health == nil {
		return false, nil
	}
	switch containerInfo.State.Health.Status {
	case container.Healthy:
		return true, nil
	default:
		return false, nil
	}
}

func backupStatus() (bool, error) {
	// TODO: Provide implementation
	return false, nil
}

func configuredStatus() (bool, error) {
	// TODO: Provide implementation
	return false, nil
}

func restartCount(containerInfo container.InspectResponse) (int, error) {
	if containerInfo.ContainerJSONBase == nil {
		return 0, errors.New("restart count not available")
	}
	// TODO: Provide implementation
	return containerInfo.RestartCount, nil
}

func version(containerInfo container.InspectResponse) (string, error) {
	if containerInfo.Config != nil && containerInfo.Config.Image != "" {
		return containerInfo.Config.Image, nil
	}
	if containerInfo.Image != "" {
		return containerInfo.Image, nil
	}
	// TODO: Provide implementation
	return "", errors.New("version not available")
}

func runtime(containerInfo container.InspectResponse) (time.Duration, error) {
	if containerInfo.State == nil || containerInfo.State.StartedAt == "" {
		return 0, errors.New("runtime not available")
	}
	startedAt, err := time.Parse(time.RFC3339Nano, containerInfo.State.StartedAt)
	if err != nil {
		return 0, fmt.Errorf("parse runtime start time [%s]: %w", containerInfo.State.StartedAt, err)
	}
	runtime := time.Since(startedAt)
	if runtime < 0 {
		return 0, errors.New("runtime not available")
	}
	return runtime, nil
}
