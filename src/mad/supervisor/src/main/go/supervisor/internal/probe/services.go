package probe

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"log/slog"
	"sort"
	"strings"
	"supervisor/internal/window"
	"time"

	"github.com/docker/docker/api/types/container"
	"github.com/docker/docker/client"
)

const (
	dockerTimeoutSeconds    = 2
	containerIgnoredPattern = "reaper_"
)

type Services struct {
	dockerClient     *client.Client
	newDockerClient  func() (*client.Client, error)
	listContainers   func(context.Context, *client.Client) ([]container.Summary, error)
	statsOneShot     func(context.Context, *client.Client, string) (container.StatsResponseReader, error)
	inspectContainer func(context.Context, *client.Client, string) (container.InspectResponse, error)
}

type Service struct {
	name               string
	nameOK             bool
	usedProcessor      int8
	usedProcessorOK    bool
	usedMemory         int8
	usedMemoryOK       bool
	backupStatus       bool
	backupStatusOK     bool
	healthStatus       bool
	healthStatusOK     bool
	configuredStatus   bool
	configuredStatusOK bool
	restartCount       int
	restartCountOK     bool
	runtime            time.Duration
	runtimeOK          bool
	version            string
	versionOK          bool
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
		return nil, errors.New("services not initialized")
	}
	if s.newDockerClient == nil || s.listContainers == nil || s.statsOneShot == nil || s.inspectContainer == nil {
		// TODO: Log error
		slog.Error("docker client not configured")
		return nil, errors.New("docker client not configured")
	}
	dockerClient, err := s.ensureDockerClient()
	if err != nil {
		// TODO: Log error
		return nil, fmt.Errorf("ensure docker client: %w", err)
	}
	ctx, cancel := context.WithTimeout(context.Background(), dockerTimeoutSeconds*time.Second)
	defer cancel()
	containers, err := s.listContainers(ctx, dockerClient)
	if err != nil {
		retryClient, retryErr := s.reconnectDockerClient()
		if retryErr != nil {
			// TODO: Log error
			return nil, fmt.Errorf("reconnect docker client: %w", retryErr)
		}
		containers, err = s.listContainers(ctx, retryClient)
		if err != nil {
			// TODO: Log error
			return nil, fmt.Errorf("list containers after reconnect: %w", err)
		}
	}
	services := make([]Service, 0, len(containers))
	for _, dockerContainer := range containers {
		name := ""
		for _, rawName := range dockerContainer.Names {
			rawName = strings.TrimPrefix(rawName, "/")
			if rawName == "" {
				continue
			}
			name = rawName
			break
		}
		if strings.HasPrefix(name, containerIgnoredPattern) {
			continue
		}
		service := Service{
			name:   name,
			nameOK: name != "",
		}
		stats, err := fetchStats(ctx, dockerClient, s.statsOneShot, dockerContainer.ID)
		if err != nil {
			// TODO: Log error
		} else {
			usedProcessor, processorErr := processorUsed(stats)
			if processorErr != nil {
				// TODO: Log error
			} else {
				service.usedProcessor = usedProcessor
				service.usedProcessorOK = true
			}
			usedMemory, memoryErr := memoryUsed(stats)
			if memoryErr != nil {
				// TODO: Log error
			} else {
				service.usedMemory = usedMemory
				service.usedMemoryOK = true
			}
		}
		inspectInfo, inspectErr := fetchInspect(ctx, dockerClient, s.inspectContainer, dockerContainer.ID)
		if inspectErr != nil {
			// TODO: Log error
		} else {
			healthStatus, healthErr := healthStatus(inspectInfo)
			if healthErr != nil {
				// TODO: Log error
			} else {
				service.healthStatus = healthStatus
				service.healthStatusOK = true
			}
			runtime, runtimeErr := runtime(inspectInfo)
			if runtimeErr != nil {
				// TODO: Log error
			} else {
				service.runtime = runtime
				service.runtimeOK = true
			}
			backupStatus, backupErr := backupStatus()
			if backupErr != nil {
				// TODO: Log error
			} else {
				service.backupStatus = backupStatus
				service.backupStatusOK = true
			}
			configuredStatus, configuredErr := configuredStatus(inspectInfo)
			if configuredErr != nil {
				// TODO: Log error
			} else {
				service.configuredStatus = configuredStatus
				service.configuredStatusOK = true
			}
			restartCount, restartErr := restartCount(inspectInfo)
			if restartErr != nil {
				// TODO: Log error
			} else {
				service.restartCount = restartCount
				service.restartCountOK = true
			}
			version, versionErr := version(inspectInfo)
			if versionErr != nil {
				// TODO: Log error
			} else {
				service.version = version
				service.versionOK = true
			}
		}
		services = append(services, service)
	}
	sort.Slice(services, func(i, j int) bool {
		return services[i].name < services[j].name
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
	if s == nil || !s.nameOK {
		return "", errors.New("service name not available")
	}
	return s.name, nil
}

func (s *Service) UsedProcessor() (int8, error) {
	if !s.usedProcessorOK {
		return 0, errors.New("cpu usage not available")
	}
	return s.usedProcessor, nil
}

func (s *Service) UsedMemory() (int8, error) {
	if !s.usedMemoryOK {
		return 0, errors.New("memory usage not available")
	}
	return s.usedMemory, nil
}

func (s *Service) BackupStatus() (bool, error) {
	if !s.backupStatusOK {
		return false, errors.New("backup status not available")
	}
	return s.backupStatus, nil
}

func (s *Service) HealthStatus() (bool, error) {
	if !s.healthStatusOK {
		return false, errors.New("health status not available")
	}
	return s.healthStatus, nil
}

func (s *Service) ConfiguredStatus() (bool, error) {
	if !s.configuredStatusOK {
		return false, errors.New("configured status not available")
	}
	return s.configuredStatus, nil
}

func (s *Service) RestartCount() (int, error) {
	if !s.restartCountOK {
		return 0, errors.New("restart count not available")
	}
	return s.restartCount, nil
}

func (s *Service) Runtime() (time.Duration, error) {
	if !s.runtimeOK {
		return 0, errors.New("runtime not available")
	}
	return s.runtime, nil
}

func (s *Service) Version() (string, error) {
	if !s.versionOK {
		return "", errors.New("version not available")
	}
	return s.version, nil
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
		return 0, errors.New("cpu usage unavailable, first tick")
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
	return window.ConvertToQuota(usedPercent)
}

func memoryUsed(stats container.StatsResponse) (int8, error) {
	if stats.MemoryStats.Limit == 0 {
		return 0, errors.New("memory limit must be > 0")
	}
	usedPercent := (float64(stats.MemoryStats.Usage) / float64(stats.MemoryStats.Limit)) * 100.0
	return window.ConvertToQuota(usedPercent)
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
	return false, errors.New("backup status not available")
}

func configuredStatus(containerInfo container.InspectResponse) (bool, error) {
	if containerInfo.Config == nil {
		return false, errors.New("configured status not available")
	}
	return true, nil
}

func restartCount(containerInfo container.InspectResponse) (int, error) {
	if containerInfo.ContainerJSONBase == nil {
		return 0, errors.New("restart count not available")
	}
	return containerInfo.RestartCount, nil
}

func version(containerInfo container.InspectResponse) (string, error) {
	if containerInfo.Config != nil && containerInfo.Config.Image != "" {
		return containerInfo.Config.Image, nil
	}
	if containerInfo.Image != "" {
		return containerInfo.Image, nil
	}
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
