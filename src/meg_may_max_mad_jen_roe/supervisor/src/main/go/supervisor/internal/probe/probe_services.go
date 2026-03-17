package probe

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"log/slog"
	"os"
	"strings"
	"supervisor/internal/config"
	"supervisor/internal/metric"
	"supervisor/internal/stats"
	"time"

	"github.com/docker/docker/api/types/container"
	"github.com/docker/docker/client"
)

type servicesProbe struct {
	cache      *metric.RecordCache
	mask       [metric.MetricMax]bool
	periods    config.Periods
	hostName   string
	configPath string

	servicesBool           *stats.BoolStats
	servicesMaxMemoryFloat *stats.FloatStats
	serviceBool            map[string]*stats.BoolStats
	backupStatusBool       map[string]*stats.BoolStats
	healthStatusBool       map[string]*stats.BoolStats
	configuredStatusBool   map[string]*stats.BoolStats
	nameString             map[string]*stats.StringStats
	versionString          map[string]*stats.StringStats
	usedProcessorInt       map[string]*stats.IntStats
	usedMemoryInt          map[string]*stats.IntStats
	usedDiskOpsInt         map[string]*stats.IntStats
	usedNetworkInt         map[string]*stats.IntStats
	runningTimeFloat       map[string]*stats.FloatStats
	maxMemoryFloat         map[string]*stats.FloatStats
	restartCountFloat      map[string]*stats.FloatStats

	configuredServiceNames []string
	prevCPUStats           map[string]container.CPUStats

	dockerClient     *client.Client
	newDockerClient  func() (*client.Client, error)
	listContainers   func(context.Context, *client.Client) ([]container.Summary, error)
	statsOneShot     func(context.Context, *client.Client, string) (container.StatsResponseReader, error)
	inspectContainer func(context.Context, *client.Client, string) (container.InspectResponse, error)
}

func newServicesProbe() *servicesProbe {
	return &servicesProbe{
		hostName: config.Load("").Host(),

		serviceBool:          make(map[string]*stats.BoolStats),
		backupStatusBool:     make(map[string]*stats.BoolStats),
		healthStatusBool:     make(map[string]*stats.BoolStats),
		configuredStatusBool: make(map[string]*stats.BoolStats),
		nameString:           make(map[string]*stats.StringStats),
		versionString:        make(map[string]*stats.StringStats),
		usedProcessorInt:     make(map[string]*stats.IntStats),
		usedMemoryInt:        make(map[string]*stats.IntStats),
		usedDiskOpsInt:       make(map[string]*stats.IntStats),
		usedNetworkInt:       make(map[string]*stats.IntStats),
		runningTimeFloat:     make(map[string]*stats.FloatStats),
		maxMemoryFloat:       make(map[string]*stats.FloatStats),
		restartCountFloat:    make(map[string]*stats.FloatStats),

		prevCPUStats: make(map[string]container.CPUStats),

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

func (*servicesProbe) name() string { return "services" }

func (p *servicesProbe) metrics() []metric.ID {
	return []metric.ID{
		metric.MetricHostServices,
		metric.MetricHostServicesMaxMemory,
		metric.MetricService,
		metric.MetricServiceBackupStatus,
		metric.MetricServiceHealthStatus,
		metric.MetricServiceConfiguredStatus,
		metric.MetricServiceName,
		metric.MetricServiceVersion,
		metric.MetricServiceUsedProcessor,
		metric.MetricServiceUsedMemory,
		metric.MetricServiceUsedDiskOps,
		metric.MetricServiceUsedNetwork,
		metric.MetricServiceRunningTime,
		metric.MetricServiceMaxMemory,
		metric.MetricServiceRestartCount,
	}
}

func (p *servicesProbe) create(configPath string, cache *metric.RecordCache, mask [metric.MetricMax]bool, periods config.Periods) error {
	p.cache = cache
	p.mask = mask
	p.periods = periods
	p.servicesBool = stats.NewBoolStats(p.periods.TrendHours, float64(p.periods.PulseMillis)/1000.0, float64(p.periods.PollMillis)/1000.0)
	p.servicesMaxMemoryFloat = stats.NewFloatStats(p.periods.TrendHours, float64(p.periods.PulseMillis)/1000.0, float64(p.periods.PollMillis)/1000.0)
	p.configPath = configPath
	c := config.Load(configPath)
	p.hostName = c.Host()
	p.configuredServiceNames = c.Services(p.hostName)
	return nil
}

func (p *servicesProbe) run(ctx context.Context, isPulse bool) error {
	servicesByName, err := p.services(ctx)
	if err != nil {
		return fmt.Errorf("get services: %w", err)
	}
	polledServiceNames := make(map[string]struct{}, len(servicesByName))
	for name := range servicesByName {
		polledServiceNames[name] = struct{}{}
	}
	for _, cachedServiceName := range p.cache.Services(p.hostName) {
		if _, exists := polledServiceNames[cachedServiceName]; !exists {
			p.cache.EvictAndDelete(p.hostName, cachedServiceName)
		}
	}
	newBool := func() *stats.BoolStats {
		return stats.NewBoolStats(p.periods.TrendHours, float64(p.periods.PulseMillis)/1000.0, float64(p.periods.PollMillis)/1000.0)
	}
	newString := func() *stats.StringStats {
		return stats.NewStringStats(p.periods.TrendHours, float64(p.periods.PulseMillis)/1000.0, float64(p.periods.PollMillis)/1000.0)
	}
	newInt := func() *stats.IntStats {
		return stats.NewIntStats(p.periods.TrendHours, float64(p.periods.PulseMillis)/1000.0, float64(p.periods.PollMillis)/1000.0)
	}
	newFloat := func() *stats.FloatStats {
		return stats.NewFloatStats(p.periods.TrendHours, float64(p.periods.PulseMillis)/1000.0, float64(p.periods.PollMillis)/1000.0)
	}
	serviceBools := syncStatsFields(p.serviceBool, polledServiceNames, newBool)
	backupStatusBools := syncStatsFields(p.backupStatusBool, polledServiceNames, newBool)
	healthStatusBools := syncStatsFields(p.healthStatusBool, polledServiceNames, newBool)
	configuredStatusBools := syncStatsFields(p.configuredStatusBool, polledServiceNames, newBool)
	nameStrings := syncStatsFields(p.nameString, polledServiceNames, newString)
	versionStrings := syncStatsFields(p.versionString, polledServiceNames, newString)
	usedProcessorInts := syncStatsFields(p.usedProcessorInt, polledServiceNames, newInt)
	usedMemoryInts := syncStatsFields(p.usedMemoryInt, polledServiceNames, newInt)
	usedDiskOpsInts := syncStatsFields(p.usedDiskOpsInt, polledServiceNames, newInt)
	usedNetworkInts := syncStatsFields(p.usedNetworkInt, polledServiceNames, newInt)
	runningTimeFloats := syncStatsFields(p.runningTimeFloat, polledServiceNames, newFloat)
	maxMemoryFloats := syncStatsFields(p.maxMemoryFloat, polledServiceNames, newFloat)
	restartCountFloats := syncStatsFields(p.restartCountFloat, polledServiceNames, newFloat)

	for polledServiceName, polledService := range servicesByName {
		healthStatus, _ := polledService.healthStatus()
		configuredStatus, _ := polledService.configuredStatus()
		healthyAndConfigured := healthStatus && configuredStatus
		runMetricCacheTasks(p, isPulse, []cacheMetricTask{
			newCacheMetricTask(
				metric.ValueBool,
				metric.MetricService,
				polledService.name(),
				polledService.isUp,
				serviceBools[polledServiceName],
				func() bool { return serviceBools[polledServiceName].PulseLast() },
				func() bool { return serviceBools[polledServiceName].TrendMean() },
				func(bool) bool { return healthyAndConfigured },
				func(bool) bool { return healthyAndConfigured },
			),
			newCacheMetricTask(
				metric.ValueBool,
				metric.MetricServiceBackupStatus,
				polledService.name(),
				polledService.backupStatus,
				backupStatusBools[polledServiceName],
				func() bool { return backupStatusBools[polledServiceName].PulseLast() },
				func() bool { return backupStatusBools[polledServiceName].TrendMean() },
				func(v bool) bool { return v },
				func(v bool) bool { return v },
			),
			newCacheMetricTask(
				metric.ValueBool,
				metric.MetricServiceHealthStatus,
				polledService.name(),
				polledService.healthStatus,
				healthStatusBools[polledServiceName],
				func() bool { return healthStatusBools[polledServiceName].PulseLast() },
				func() bool { return healthStatusBools[polledServiceName].TrendMean() },
				func(bool) bool { return healthStatus },
				func(bool) bool { return healthStatus },
			),
			newCacheMetricTask(
				metric.ValueBool,
				metric.MetricServiceConfiguredStatus,
				polledService.name(),
				polledService.configuredStatus,
				configuredStatusBools[polledServiceName],
				func() bool { return configuredStatusBools[polledServiceName].PulseLast() },
				func() bool { return configuredStatusBools[polledServiceName].TrendMean() },
				func(bool) bool { return configuredStatus },
				func(bool) bool { return configuredStatus },
			),
			newCacheMetricTask(
				metric.ValueString,
				metric.MetricServiceName,
				polledService.name(),
				func() (string, error) { return polledService.name(), nil },
				nameStrings[polledServiceName],
				func() string { return nameStrings[polledServiceName].PulseLast() },
				func() string { return nameStrings[polledServiceName].TrendDominant() },
				func(string) bool { return healthyAndConfigured },
				func(string) bool { return healthyAndConfigured },
			),
			newCacheMetricTask(
				metric.ValueString,
				metric.MetricServiceVersion,
				polledService.name(),
				polledService.version,
				versionStrings[polledServiceName],
				func() string { return versionStrings[polledServiceName].PulseLast() },
				func() string { return versionStrings[polledServiceName].TrendDominant() },
				func(string) bool { return healthyAndConfigured },
				func(string) bool { return healthyAndConfigured },
			),
			newCacheMetricTask(
				metric.ValueInt,
				metric.MetricServiceUsedProcessor,
				polledService.name(),
				polledService.usedProcessor,
				usedProcessorInts[polledServiceName],
				func() int8 { return usedProcessorInts[polledServiceName].PulseMax() },
				func() int8 { return usedProcessorInts[polledServiceName].TrendP95() },
				func(p int8) bool { return healthyAndConfigured && p <= 90 },
				func(t int8) bool { return healthyAndConfigured && t <= 70 },
			),
			newCacheMetricTask(
				metric.ValueInt,
				metric.MetricServiceUsedMemory,
				polledService.name(),
				polledService.usedMemory,
				usedMemoryInts[polledServiceName],
				func() int8 { return usedMemoryInts[polledServiceName].PulseMax() },
				func() int8 { return usedMemoryInts[polledServiceName].TrendMax() },
				func(p int8) bool { return healthyAndConfigured && p <= 90 },
				func(t int8) bool { return healthyAndConfigured && t <= 75 },
			),
			newCacheMetricTask(
				metric.ValueInt,
				metric.MetricServiceUsedDiskOps,
				polledService.name(),
				polledService.usedDiskOps,
				usedDiskOpsInts[polledServiceName],
				func() int8 { return usedDiskOpsInts[polledServiceName].PulseMax() },
				func() int8 { return usedDiskOpsInts[polledServiceName].TrendMax() },
				func(p int8) bool { return healthyAndConfigured && p <= 90 },
				func(t int8) bool { return healthyAndConfigured && t <= 80 },
			),
			newCacheMetricTask(
				metric.ValueInt,
				metric.MetricServiceUsedNetwork,
				polledService.name(),
				polledService.usedNetwork,
				usedNetworkInts[polledServiceName],
				func() int8 { return usedNetworkInts[polledServiceName].PulseMax() },
				func() int8 { return usedNetworkInts[polledServiceName].TrendMax() },
				func(p int8) bool { return healthyAndConfigured && p <= 90 },
				func(t int8) bool { return healthyAndConfigured && t <= 80 },
			),
			newCacheMetricTask(
				metric.ValueFloat,
				metric.MetricServiceRunningTime,
				polledService.name(),
				polledService.runningTime,
				runningTimeFloats[polledServiceName],
				func() float64 { return runningTimeFloats[polledServiceName].PulseLast() },
				func() float64 { return runningTimeFloats[polledServiceName].TrendMax() },
				func(float64) bool { return healthyAndConfigured },
				func(float64) bool { return healthyAndConfigured },
			),
			newCacheMetricTask(
				metric.ValueFloat,
				metric.MetricServiceMaxMemory,
				polledService.name(),
				polledService.maxMemory,
				maxMemoryFloats[polledServiceName],
				func() float64 { return maxMemoryFloats[polledServiceName].PulseLast() },
				nil,
				func(float64) bool { return true },
				nil,
			),
			newCacheMetricTask(
				metric.ValueFloat,
				metric.MetricServiceRestartCount,
				polledService.name(),
				polledService.restartCount,
				restartCountFloats[polledServiceName],
				func() float64 { return restartCountFloats[polledServiceName].PulseLast() },
				func() float64 { return restartCountFloats[polledServiceName].TrendMax() },
				func(p float64) bool { return healthyAndConfigured && p <= 80 },
				func(t float64) bool { return healthyAndConfigured && t <= 70 },
			),
		})
	}
	runMetricCacheTasks(p, isPulse, []cacheMetricTask{
		newCacheMetricTask(
			metric.ValueBool,
			metric.MetricHostServices,
			metric.ServiceNameUnset,
			func() (bool, error) { return p.servicesStatus() },
			p.servicesBool,
			func() bool { return p.servicesBool.PulseLast() },
			func() bool { return p.servicesBool.TrendMean() },
			func(bool) bool { return true },
			func(bool) bool { return true },
		),
		newCacheMetricTask(
			metric.ValueFloat,
			metric.MetricHostServicesMaxMemory,
			metric.ServiceNameUnset,
			func() (float64, error) { return p.servicesMaxMemory() },
			p.servicesMaxMemoryFloat,
			func() float64 { return p.servicesMaxMemoryFloat.PulseLast() },
			nil,
			func(float64) bool { return true },
			nil,
		),
	})

	return nil
}

func (p *servicesProbe) records() *metric.RecordCache {
	return p.cache
}

func (p *servicesProbe) hasMetric(id metric.ID) bool {
	return p.mask[id]
}

func (p *servicesProbe) services(ctx context.Context) (map[string]service, error) {
	if p.newDockerClient == nil || p.listContainers == nil || p.statsOneShot == nil || p.inspectContainer == nil {
		return nil, errors.New("docker client not initialised")
	}
	dockerClient, err := p.ensureDockerClient()
	if err != nil {
		return nil, fmt.Errorf("ensure docker client: %w", err)
	}
	ctx, cancel := context.WithTimeout(ctx, servicesDockerTimeoutSecs*time.Second)
	defer cancel()
	containers, err := p.listContainers(ctx, dockerClient)
	if err != nil {
		dockerClient, err = p.reconnectDockerClient()
		if err != nil {
			return nil, fmt.Errorf("reconnect docker client: %w", err)
		}
		containers, err = p.listContainers(ctx, dockerClient)
		if err != nil {
			return nil, fmt.Errorf("list containers after reconnect: %w", err)
		}
	}
	services := make(map[string]service, len(containers))
	seenNames := make(map[string]struct{})
	activeIDs := make(map[string]struct{}, len(containers))
	for _, c := range containers {
		activeIDs[c.ID] = struct{}{}
	}
	for prevID := range p.prevCPUStats {
		if _, exists := activeIDs[prevID]; !exists {
			delete(p.prevCPUStats, prevID)
		}
	}
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
		if name == "" {
			slog.Error("empty container name reported by docker, excluding from service list")
			continue
		}
		if _, exists := seenNames[name]; exists {
			slog.Error("non-unique container name reported by docker, excluding from service list", "name", name)
			continue
		}
		seenNames[name] = struct{}{}
		service := service{nameValue: name}
		fetchedStats, err := p.fetchStats(ctx, dockerClient, serviceContainer.ID)
		if err != nil {
			service.usedProcessorErr = err
			service.usedMemoryErr = err
		} else {
			prev, hasPrev := p.prevCPUStats[serviceContainer.ID]
			p.prevCPUStats[serviceContainer.ID] = fetchedStats.CPUStats
			if !hasPrev {
				service.usedProcessorErr = errProbeWarmingUp
			} else {
				fetchedStats.PreCPUStats = prev
				usedProcessor, processorErr := p.processorUsed(fetchedStats)
				if processorErr != nil {
					service.usedProcessorErr = processorErr
				} else {
					service.usedProcessorValue = usedProcessor
				}
			}
			usedMemory, memoryErr := p.memoryUsed(fetchedStats)
			if memoryErr != nil {
				service.usedMemoryErr = memoryErr
			} else {
				service.usedMemoryValue = usedMemory
			}
		}
		fetchedInspect, err := p.fetchInspect(ctx, dockerClient, serviceContainer.ID)
		if err != nil {
			service.healthStatusErr = err
			service.runningTimeErr = err
			service.restartCountErr = err
			service.versionErr = err
		} else {
			healthStatusValue, healthErr := p.healthStatus(fetchedInspect)
			if healthErr != nil {
				service.healthStatusErr = healthErr
			} else {
				service.healthStatusValue = healthStatusValue
			}
			runningTimeValue, runningTimeErr := p.runningTime(fetchedInspect)
			if runningTimeErr != nil {
				service.runningTimeErr = runningTimeErr
			} else {
				service.runningTimeValue = runningTimeValue
			}
			restartCountValue, restartErr := p.restartCount(fetchedInspect)
			if restartErr != nil {
				service.restartCountErr = restartErr
			} else {
				service.restartCountValue = restartCountValue
			}
			versionValue, versionErr := p.version(fetchedInspect)
			if versionErr != nil {
				service.versionErr = versionErr
			} else {
				service.versionValue = versionValue
			}
		}
		configuredStatusValue, configuredErr := p.configuredStatus()
		if configuredErr != nil {
			service.configuredStatusErr = configuredErr
		} else {
			service.configuredStatusValue = configuredStatusValue
		}
		backupStatusValue, backupErr := p.backupStatus()
		if backupErr != nil {
			service.backupStatusErr = backupErr
		} else {
			service.backupStatusValue = backupStatusValue
		}
		services[name] = service
	}
	for _, configuredServiceName := range p.configuredServiceNames {
		if existingService, exists := services[configuredServiceName]; exists {
			existingService.configuredStatusValue = true
			services[configuredServiceName] = existingService
		} else {
			services[configuredServiceName] = service{
				nameValue:             configuredServiceName,
				configuredStatusValue: true,
				versionValue:          "-",
			}
		}
	}
	return services, nil
}

func syncStatsFields[V any](statsNames map[string]V, polledNames map[string]struct{}, newValue func() V) map[string]V {
	for statsName := range statsNames {
		if _, exists := polledNames[statsName]; !exists {
			delete(statsNames, statsName)
		}
	}
	for polledName := range polledNames {
		if _, exists := statsNames[polledName]; !exists {
			statsNames[polledName] = newValue()
		}
	}
	return statsNames
}

type service struct {
	backupStatusValue     bool
	backupStatusErr       error
	healthStatusValue     bool
	healthStatusErr       error
	configuredStatusValue bool
	configuredStatusErr   error
	nameValue             string
	versionValue          string
	versionErr            error
	usedProcessorValue    int8
	usedProcessorErr      error
	usedMemoryValue       int8
	usedMemoryErr         error
	runningTimeValue      float64
	runningTimeErr        error
	restartCountValue     float64
	restartCountErr       error
}

func (p *servicesProbe) servicesStatus() (bool, error) {
	return true, nil
}

func (p *servicesProbe) servicesMaxMemory() (float64, error) {
	return 0, nil
}

func (s *service) isUp() (bool, error) {
	return true, nil
}

func (s *service) backupStatus() (bool, error) {
	return s.backupStatusValue, s.backupStatusErr
}

func (s *service) healthStatus() (bool, error) {
	return s.healthStatusValue, s.healthStatusErr
}

func (s *service) configuredStatus() (bool, error) {
	return s.configuredStatusValue, s.configuredStatusErr
}

func (s *service) name() string {
	return s.nameValue
}

func (s *service) version() (string, error) {
	return s.versionValue, s.versionErr
}

func (s *service) usedProcessor() (int8, error) {
	return s.usedProcessorValue, s.usedProcessorErr
}

func (s *service) usedMemory() (int8, error) {
	return s.usedMemoryValue, s.usedMemoryErr
}

func (s *service) usedDiskOps() (int8, error) {
	return 0, nil
}

func (s *service) usedNetwork() (int8, error) {
	return 0, nil
}

func (s *service) runningTime() (float64, error) {
	return s.runningTimeValue, s.runningTimeErr
}

func (s *service) maxMemory() (float64, error) {
	return 0, nil
}

func (s *service) restartCount() (float64, error) {
	return s.restartCountValue, s.restartCountErr
}

func (p *servicesProbe) ensureDockerClient() (*client.Client, error) {
	if p.dockerClient != nil {
		return p.dockerClient, nil
	}
	dockerClient, err := p.newDockerClient()
	if err != nil {
		return nil, fmt.Errorf("create docker client: %w", err)
	}
	p.dockerClient = dockerClient
	return dockerClient, nil
}

func (p *servicesProbe) reconnectDockerClient() (*client.Client, error) {
	if p.dockerClient != nil {
		_ = p.dockerClient.Close()
		p.dockerClient = nil
	}
	return p.ensureDockerClient()
}

func (p *servicesProbe) fetchStats(ctx context.Context, dockerClient *client.Client, id string) (container.StatsResponse, error) {
	statsReader, err := p.statsOneShot(ctx, dockerClient, id)
	if err != nil {
		return container.StatsResponse{}, fmt.Errorf("fetch container statsResponse for id [%s]: %w", id, err)
	}
	defer func(reader container.StatsResponseReader) {
		_ = reader.Body.Close()
	}(statsReader)
	var statsResponse container.StatsResponse
	if decodeErr := json.NewDecoder(statsReader.Body).Decode(&statsResponse); decodeErr != nil {
		return container.StatsResponse{}, fmt.Errorf("decode container statsResponse for id [%s]: %w", id, decodeErr)
	}
	return statsResponse, nil
}

func (p *servicesProbe) fetchInspect(ctx context.Context, dockerClient *client.Client, id string) (container.InspectResponse, error) {
	info, err := p.inspectContainer(ctx, dockerClient, id)
	if err != nil {
		return container.InspectResponse{}, fmt.Errorf("inspect container for id [%s]: %w", id, err)
	}
	return info, nil
}

func (p *servicesProbe) processorUsed(response container.StatsResponse) (int8, error) {
	cpuDelta := float64(response.CPUStats.CPUUsage.TotalUsage - response.PreCPUStats.CPUUsage.TotalUsage)
	systemDelta := float64(response.CPUStats.SystemUsage - response.PreCPUStats.SystemUsage)
	if systemDelta <= 0 {
		return 0, errors.New("cpu usage unavailable, non-monotonic counters")
	}
	onlineCPUs := float64(response.CPUStats.OnlineCPUs)
	if onlineCPUs == 0 {
		onlineCPUs = float64(len(response.CPUStats.CPUUsage.PercpuUsage))
	}
	usedPercent := (cpuDelta / systemDelta) * onlineCPUs * 100.0
	return stats.ConvertToInt(usedPercent), nil
}

func (p *servicesProbe) memoryUsed(response container.StatsResponse) (int8, error) {
	if response.MemoryStats.Limit == 0 {
		return 0, errors.New("memory limit must be > 0")
	}
	cache := response.MemoryStats.Stats["inactive_file"]
	if cache == 0 {
		cache = response.MemoryStats.Stats["cache"]
	}
	used := float64(response.MemoryStats.Usage) - float64(cache)
	if used < 0 {
		used = 0
	}
	usedPercent := (used / float64(response.MemoryStats.Limit)) * 100.0
	return stats.ConvertToInt(usedPercent), nil
}

func (p *servicesProbe) healthStatus(containerInfo container.InspectResponse) (bool, error) {
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

func (p *servicesProbe) backupStatus() (bool, error) {
	// TODO: Provide implementation
	return true, nil
}

func (p *servicesProbe) configuredStatus() (bool, error) {
	// TODO: Provide implementation
	return false, nil
}

func (p *servicesProbe) restartCount(containerInfo container.InspectResponse) (float64, error) {
	if containerInfo.ContainerJSONBase == nil {
		return 0, errors.New("restart count not available")
	}
	// TODO: Provide implementation
	return float64(containerInfo.RestartCount), nil
}

func (p *servicesProbe) version(containerInfo container.InspectResponse) (string, error) {
	version := ""
	if containerInfo.Config != nil && containerInfo.Config.Image != "" {
		tokens := strings.Split(containerInfo.Config.Image, ":")
		if len(tokens) > 1 {
			if config.VersionPattern.MatchString(tokens[1]) {
				version = tokens[1]
			}
		}
		if version == "" {
			name := strings.TrimPrefix(containerInfo.Name, "/")
			if name == "" {
				tokens = strings.Split(tokens[0], "/")
				name = tokens[0]
			}
			if name != "" {
				if data, err := os.ReadFile(config.Load(p.configPath).Mount() + "/root/install/" + name + "/latest/.env"); err == nil {
					for _, line := range strings.Split(string(data), "\n") {
						if v, ok := strings.CutPrefix(line, "SERVICE_VERSION_ABSOLUTE="); ok {
							version = v
							break
						}
					}
				}
			}
		}
	}
	if version == "" {
		image := ""
		if containerInfo.Config != nil {
			image = containerInfo.Config.Image
		}
		slog.Debug("version not available", "name", containerInfo.Name, "image", image)
		return "-", nil
	}
	return version, nil
}

func (p *servicesProbe) runningTime(containerInfo container.InspectResponse) (float64, error) {
	if containerInfo.State == nil || containerInfo.State.StartedAt == "" {
		return 0, errors.New("started at time not available")
	}
	startedAt, err := time.Parse(time.RFC3339Nano, containerInfo.State.StartedAt)
	if err != nil {
		return 0, fmt.Errorf("parse start at time [%s] failed: %w", containerInfo.State.StartedAt, err)
	}
	runningTime := time.Since(startedAt).Seconds()
	if runningTime < 0 {
		return 0, errors.New("running time not available")
	}
	return runningTime, nil
}

const (
	servicesDockerTimeoutSecs            = 2
	servicesDockerContainerIgnorePattern = "reaper_"
)
