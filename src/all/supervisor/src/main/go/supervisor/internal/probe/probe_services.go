package probe

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"sort"
	"strings"
	"supervisor/internal/config"
	"supervisor/internal/metric"
	"supervisor/internal/scribe"
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
	installMissingLogged   string
	prevCPUStats           map[string]container.CPUStats

	dockerClient     *client.Client
	newDockerClient  func() (*client.Client, error)
	listContainers   func(context.Context, *client.Client) ([]container.Summary, error)
	statsOneShot     func(context.Context, *client.Client, string) (container.StatsResponseReader, error)
	inspectContainer func(context.Context, *client.Client, string) (container.InspectResponse, error)
}

func newServicesProbe() *servicesProbe {
	hostName, _ := os.Hostname()
	return &servicesProbe{
		hostName:             hostName,
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
		metric.MetricServiceUpTime,
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

func (p *servicesProbe) gates() []metric.GateID {
	return []metric.GateID{metric.GateServiceAggregate}
}

func (p *servicesProbe) run(ctx context.Context, isPulse bool) error {
	snapshot := p.installs().snapshot()
	servicesByName, err := p.services(ctx, snapshot)
	if err != nil {
		return fmt.Errorf("no service metrics sampled, listing services from docker failed with [%w]", err)
	}
	polledServiceNames := make(map[string]struct{}, len(servicesByName))
	for name := range servicesByName {
		polledServiceNames[name] = struct{}{}
	}
	tombstoneStart := time.Now()
	var tombstoned []string
	for _, cachedServiceName := range p.cache.Services(p.hostName) {
		if _, exists := polledServiceNames[cachedServiceName]; !exists {
			p.cache.Evict(p.hostName, cachedServiceName)
			p.cache.Delete(p.hostName, cachedServiceName)
			tombstoned = append(tombstoned, cachedServiceName)
		}
	}
	if len(tombstoned) > 0 {
		scribe.Log(scribe.SourceProbe, scribe.SubjectHost(p.hostName), scribe.ActionRemove).Info("removals", tombstoneStart, "[%d] services, host [%s], services [%s]", len(tombstoned), p.hostName, strings.Join(tombstoned, ","))
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
	upTimeFloats := syncStatsFields(p.runningTimeFloat, polledServiceNames, newFloat)
	maxMemoryFloats := syncStatsFields(p.maxMemoryFloat, polledServiceNames, newFloat)
	restartCountFloats := syncStatsFields(p.restartCountFloat, polledServiceNames, newFloat)

	for polledServiceName, polledService := range servicesByName {
		serviceStart := time.Now()
		healthStatus, _, _ := polledService.healthStatus()
		configuredStatus, _, _ := polledService.configuredStatus()
		sleepStatus, _, _ := polledService.sleepStatus()
		aggregateStatus := sleepStatus || (healthStatus && configuredStatus)
		derivePulse(scribe.Log(scribe.SourceProbe, scribe.SubjectService(polledServiceName), scribe.ActionSample), "computed", serviceStart,
			"[%v] aggregate, service [%s] health [%v] configured [%v] sleeping [%v], every metric of this service is not ok while aggregate is false",
			aggregateStatus, polledServiceName, healthStatus, configuredStatus, sleepStatus)
		gates := gateSet{metric.GateServiceAggregate: func() bool { return aggregateStatus }}
		runMetricCacheTasks(p, isPulse, gates, []cacheMetricTask{
			newCacheMetricTask(
				metric.ValueBool,
				metric.MetricService,
				polledService.name(),
				polledService.isUp,
				serviceBools[polledServiceName],
				func() bool { return serviceBools[polledServiceName].PulseLast() },
				func() bool { return serviceBools[polledServiceName].TrendMean() },
			),
			newCacheMetricTask(
				metric.ValueBool,
				metric.MetricServiceBackupStatus,
				polledService.name(),
				polledService.backupStatus,
				backupStatusBools[polledServiceName],
				func() bool { return backupStatusBools[polledServiceName].PulseLast() },
				func() bool { return backupStatusBools[polledServiceName].TrendMean() },
			),
			newCacheMetricTask(
				metric.ValueBool,
				metric.MetricServiceHealthStatus,
				polledService.name(),
				polledService.healthStatus,
				healthStatusBools[polledServiceName],
				func() bool { return healthStatusBools[polledServiceName].PulseLast() },
				func() bool { return healthStatusBools[polledServiceName].TrendMean() },
			),
			newCacheMetricTask(
				metric.ValueBool,
				metric.MetricServiceConfiguredStatus,
				polledService.name(),
				polledService.configuredStatus,
				configuredStatusBools[polledServiceName],
				func() bool { return configuredStatusBools[polledServiceName].PulseLast() },
				func() bool { return configuredStatusBools[polledServiceName].TrendMean() },
			),
			newCacheMetricTask(
				metric.ValueString,
				metric.MetricServiceName,
				polledService.name(),
				func() (string, derivation, error) {
					return polledService.name(), derived(scribe.ActionSample, "computed [%s] name, read from the container name docker reports", polledService.name()), nil
				},
				nameStrings[polledServiceName],
				func() string { return nameStrings[polledServiceName].PulseLast() },
				func() string { return nameStrings[polledServiceName].TrendDominant() },
			),
			newCacheMetricTask(
				metric.ValueString,
				metric.MetricServiceVersion,
				polledService.name(),
				polledService.version,
				versionStrings[polledServiceName],
				func() string { return versionStrings[polledServiceName].PulseLast() },
				func() string { return versionStrings[polledServiceName].TrendDominant() },
			),
			newCacheMetricTask(
				metric.ValueInt,
				metric.MetricServiceUsedProcessor,
				polledService.name(),
				polledService.usedProcessor,
				usedProcessorInts[polledServiceName],
				func() int8 { return usedProcessorInts[polledServiceName].PulseMax() },
				func() int8 { return usedProcessorInts[polledServiceName].TrendP95() },
			),
			newCacheMetricTask(
				metric.ValueInt,
				metric.MetricServiceUsedMemory,
				polledService.name(),
				polledService.usedMemory,
				usedMemoryInts[polledServiceName],
				func() int8 { return usedMemoryInts[polledServiceName].PulseMax() },
				func() int8 { return usedMemoryInts[polledServiceName].TrendMax() },
			),
			newCacheMetricTask(
				metric.ValueInt,
				metric.MetricServiceUsedDiskOps,
				polledService.name(),
				polledService.usedDiskOps,
				usedDiskOpsInts[polledServiceName],
				func() int8 { return usedDiskOpsInts[polledServiceName].PulseMax() },
				func() int8 { return usedDiskOpsInts[polledServiceName].TrendMax() },
			),
			newCacheMetricTask(
				metric.ValueInt,
				metric.MetricServiceUsedNetwork,
				polledService.name(),
				polledService.usedNetwork,
				usedNetworkInts[polledServiceName],
				func() int8 { return usedNetworkInts[polledServiceName].PulseMax() },
				func() int8 { return usedNetworkInts[polledServiceName].TrendMax() },
			),
			newCacheMetricTask(
				metric.ValueFloat,
				metric.MetricServiceUpTime,
				polledService.name(),
				polledService.upTime,
				upTimeFloats[polledServiceName],
				func() float64 { return upTimeFloats[polledServiceName].PulseLast() },
				func() float64 { return upTimeFloats[polledServiceName].TrendMax() },
			),
			newCacheMetricTask(
				metric.ValueFloat,
				metric.MetricServiceMaxMemory,
				polledService.name(),
				polledService.maxMemory,
				maxMemoryFloats[polledServiceName],
				func() float64 { return maxMemoryFloats[polledServiceName].PulseLast() },
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
			),
		})
	}
	runMetricCacheTasks(p, isPulse, nil, []cacheMetricTask{
		newCacheMetricTask(
			metric.ValueBool,
			metric.MetricHostServices,
			metric.ServiceNameUnset,
			func() (bool, derivation, error) { return p.servicesStatus() },
			p.servicesBool,
			func() bool { return p.servicesBool.PulseLast() },
			func() bool { return p.servicesBool.TrendMean() },
		),
		newCacheMetricTask(
			metric.ValueFloat,
			metric.MetricHostServicesMaxMemory,
			metric.ServiceNameUnset,
			func() (float64, derivation, error) { return p.servicesMaxMemory(snapshot) },
			p.servicesMaxMemoryFloat,
			func() float64 { return p.servicesMaxMemoryFloat.PulseLast() },
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

func (p *servicesProbe) services(ctx context.Context, snapshot *installSnapshot) (map[string]service, error) {
	if p.newDockerClient == nil || p.listContainers == nil || p.statsOneShot == nil || p.inspectContainer == nil {
		return nil, errors.New("no services listed, the probe was created without a docker client, container lister, stats reader or inspector")
	}
	dockerClient, err := p.ensureDockerClient()
	if err != nil {
		return nil, fmt.Errorf("no services listed, connecting to the docker socket failed with [%w]", err)
	}
	ctx, cancel := context.WithTimeout(ctx, servicesDockerTimeoutSecs*time.Second)
	defer cancel()
	containers, err := p.listContainers(ctx, dockerClient)
	if err != nil {
		dockerClient, err = p.reconnectDockerClient()
		if err != nil {
			return nil, fmt.Errorf("no services listed, listing containers failed and reconnecting to the docker socket failed with [%w]", err)
		}
		containers, err = p.listContainers(ctx, dockerClient)
		if err != nil {
			return nil, fmt.Errorf("no services listed, listing containers failed again after a docker socket reconnect with [%w]", err)
		}
	}
	services := make(map[string]service, len(containers))
	servicesStart := time.Now()
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
			scribe.Log(scribe.SourceProbe, scribe.SubjectNone, scribe.ActionDiscover).Error("rejected", servicesStart, "[container] empty name, excluding from the service list")
			continue
		}
		if _, exists := seenNames[name]; exists {
			scribe.Log(scribe.SourceProbe, scribe.SubjectService(name), scribe.ActionDiscover).Error("rejected", servicesStart, "non-unique container name, excluding from the service list")
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
				usedProcessor, processorDerived, processorErr := p.processorUsed(name, fetchedStats)
				if processorErr != nil {
					service.usedProcessorErr = processorErr
				} else {
					service.usedProcessorValue = usedProcessor
					service.usedProcessorDerived = processorDerived
				}
			}
			usedMemory, memoryDerived, memoryErr := p.memoryUsed(name, fetchedStats)
			if memoryErr != nil {
				service.usedMemoryErr = memoryErr
			} else {
				service.usedMemoryValue = usedMemory
				service.usedMemoryDerived = memoryDerived
			}
		}
		fetchedInspect, err := p.fetchInspect(ctx, dockerClient, serviceContainer.ID)
		if err != nil {
			service.healthStatusErr = err
			service.upTimeErr = err
			service.restartCountErr = err
			service.versionErr = err
		} else {
			healthStatusValue, healthDerived, healthErr := p.healthStatus(name, fetchedInspect)
			if healthErr != nil {
				service.healthStatusErr = healthErr
			} else {
				service.healthStatusValue = healthStatusValue
				service.healthStatusDerived = healthDerived
			}
			upTimeValue, upTimeDerived, upTimeErr := p.upTime(name, fetchedInspect)
			if upTimeErr != nil {
				service.upTimeErr = upTimeErr
			} else {
				service.upTimeValue = upTimeValue
				service.upTimeDerived = upTimeDerived
			}
			restartCountValue, restartDerived, restartErr := p.restartCount(name, fetchedInspect)
			if restartErr != nil {
				service.restartCountErr = restartErr
			} else {
				service.restartCountValue = restartCountValue
				service.restartCountDerived = restartDerived
			}
			versionValue, versionDerived, versionErr := p.version(snapshot, fetchedInspect)
			if versionErr != nil {
				service.versionErr = versionErr
			} else {
				service.versionValue = versionValue
				service.versionDerived = versionDerived
			}
		}
		configuredStatusValue, configuredErr := p.configuredStatus()
		if configuredErr != nil {
			service.configuredStatusErr = configuredErr
		} else {
			service.configuredStatusValue = configuredStatusValue
		}
		sleepStatusValue, sleepErr := p.sleep(snapshot, container.InspectResponse{
			ContainerJSONBase: &container.ContainerJSONBase{Name: "/" + name},
		})
		if sleepErr != nil {
			service.sleepStatusErr = sleepErr
		} else {
			service.sleepStatusValue = sleepStatusValue
		}
		service.maxMemoryValue, service.maxMemoryDerived, service.maxMemoryErr = p.maxMemory(snapshot, name)
		backupStatusValue, backupErr := p.backupStatus()
		if backupErr != nil {
			service.backupStatusErr = backupErr
		} else {
			service.backupStatusValue = backupStatusValue
		}
		services[name] = service
	}
	p.logInstallMissing(snapshot, services)
	ghosts := 0
	for _, configuredServiceName := range p.configuredServiceNames {
		if existingService, exists := services[configuredServiceName]; exists {
			existingService.configuredStatusValue = true
			services[configuredServiceName] = existingService
		} else {
			ghosts++
			ghostInspect := container.InspectResponse{
				ContainerJSONBase: &container.ContainerJSONBase{Name: "/" + configuredServiceName},
				Config:            &container.Config{Image: configuredServiceName},
			}
			ghostVersion, ghostVersionDerived, _ := p.version(snapshot, ghostInspect)
			ghostSleep, _ := p.sleep(snapshot, ghostInspect)
			ghostMaxMemory, ghostMaxMemoryDerived, ghostMaxMemoryErr := p.maxMemory(snapshot, configuredServiceName)
			services[configuredServiceName] = service{
				nameValue:             configuredServiceName,
				configuredStatusValue: true,
				sleepStatusValue:      ghostSleep,
				versionValue:          ghostVersion,
				versionDerived:        ghostVersionDerived,
				maxMemoryValue:        ghostMaxMemory,
				maxMemoryDerived:      ghostMaxMemoryDerived,
				maxMemoryErr:          ghostMaxMemoryErr,
			}
		}
	}
	derivePulse(scribe.Log(scribe.SourceProbe, scribe.SubjectProbe(p.name()), scribe.ActionDiscover), "reported", servicesStart,
		"[%3d] containers, services [%d], configured [%d], ghosts [%d] configured but not running",
		len(containers), len(services)-ghosts, len(p.configuredServiceNames), ghosts)
	return services, nil
}

func configuredWord(value bool) string {
	if value {
		return "a"
	}
	return "no"
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
	usedProcessorDerived  derivation
	usedMemoryDerived     derivation
	healthStatusDerived   derivation
	versionDerived        derivation
	upTimeDerived         derivation
	restartCountDerived   derivation
	maxMemoryDerived      derivation
	backupStatusValue     bool
	backupStatusErr       error
	healthStatusValue     bool
	healthStatusErr       error
	configuredStatusValue bool
	configuredStatusErr   error
	sleepStatusValue      bool
	sleepStatusErr        error
	nameValue             string
	versionValue          string
	versionErr            error
	maxMemoryValue        float64
	maxMemoryErr          error
	usedProcessorValue    int8
	usedProcessorErr      error
	usedMemoryValue       int8
	usedMemoryErr         error
	upTimeValue           float64
	upTimeErr             error
	restartCountValue     float64
	restartCountErr       error
}

func (p *servicesProbe) servicesStatus() (bool, derivation, error) {
	return true, derived(scribe.ActionSample, "computed [true] reporting, the host publishes this beacon every pulse and it is ok whenever the record exists"), nil
}

func (p *servicesProbe) servicesMaxMemory(snapshot *installSnapshot) (float64, derivation, error) {
	allocatedBytes, installed, err := snapshot.allocation(p.configuredServiceNames)
	if err != nil {
		return 0, derivation{}, err
	}
	return float64(allocatedBytes) / bytesPerMiB, derived(scribe.ActionCompute, "computed [%.0f] MiB of ceilings, installed [%d] of configured [%d] services",
		float64(allocatedBytes)/bytesPerMiB, installed, len(p.configuredServiceNames)), nil
}

func (s *service) isUp() (bool, derivation, error) {
	return true, derived(scribe.ActionSample, "computed [true] reporting, service [%s] publishes this beacon every pulse and its ok flag is the service aggregate", s.nameValue), nil
}

func (s *service) backupStatus() (bool, derivation, error) {
	// TODO: Provide implementation
	return s.backupStatusValue, stubDerivation(metric.MetricServiceBackupStatus, s.backupStatusValue), s.backupStatusErr
}

func (s *service) healthStatus() (bool, derivation, error) {
	return s.healthStatusValue, s.healthStatusDerived, s.healthStatusErr
}

func (s *service) configuredStatus() (bool, derivation, error) {
	return s.configuredStatusValue, derived(scribe.ActionSample, "computed [%v] configured, service [%s] is %s named in the config file schema for this host",
		s.configuredStatusValue, s.nameValue, configuredWord(s.configuredStatusValue)), s.configuredStatusErr
}

func (s *service) sleepStatus() (bool, derivation, error) {
	return s.sleepStatusValue, derived(scribe.ActionSample, "computed [%v] sleeping, service [%s] holds %s marker in its install tree",
		s.sleepStatusValue, s.nameValue, configuredWord(s.sleepStatusValue)), s.sleepStatusErr
}

func (s *service) name() string {
	return s.nameValue
}

func (s *service) version() (string, derivation, error) {
	return s.versionValue, s.versionDerived, s.versionErr
}

func (s *service) usedProcessor() (int8, derivation, error) {
	return s.usedProcessorValue, s.usedProcessorDerived, s.usedProcessorErr
}

func (s *service) usedMemory() (int8, derivation, error) {
	return s.usedMemoryValue, s.usedMemoryDerived, s.usedMemoryErr
}

func (s *service) usedDiskOps() (int8, derivation, error) {
	// TODO: Provide implementation
	return stub[int8](metric.MetricServiceUsedDiskOps)
}

func (s *service) usedNetwork() (int8, derivation, error) {
	// TODO: Provide implementation
	return stub[int8](metric.MetricServiceUsedNetwork)
}

func (s *service) upTime() (float64, derivation, error) {
	return s.upTimeValue, s.upTimeDerived, s.upTimeErr
}

func (s *service) maxMemory() (float64, derivation, error) {
	return s.maxMemoryValue, s.maxMemoryDerived, s.maxMemoryErr
}

func (s *service) restartCount() (float64, derivation, error) {
	return s.restartCountValue, s.restartCountDerived, s.restartCountErr
}

func (p *servicesProbe) ensureDockerClient() (*client.Client, error) {
	if p.dockerClient != nil {
		return p.dockerClient, nil
	}
	dockerClient, err := p.newDockerClient()
	if err != nil {
		return nil, fmt.Errorf("no docker client created from the environment with [%w]", err)
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
		return container.StatsResponse{}, fmt.Errorf("no processor or memory sample taken, fetching docker stats for container [%s] failed with [%w]", id, err)
	}
	defer func(reader container.StatsResponseReader) {
		_ = reader.Body.Close()
	}(statsReader)
	var statsResponse container.StatsResponse
	if decodeErr := json.NewDecoder(statsReader.Body).Decode(&statsResponse); decodeErr != nil {
		return container.StatsResponse{}, fmt.Errorf("no processor or memory sample taken, decoding docker stats for container [%s] failed with [%w]", id, decodeErr)
	}
	return statsResponse, nil
}

func (p *servicesProbe) fetchInspect(ctx context.Context, dockerClient *client.Client, id string) (container.InspectResponse, error) {
	info, err := p.inspectContainer(ctx, dockerClient, id)
	if err != nil {
		return container.InspectResponse{}, fmt.Errorf("no health, up time, restart or version sample taken, inspecting container [%s] failed with [%w]", id, err)
	}
	return info, nil
}

func (p *servicesProbe) processorUsed(name string, response container.StatsResponse) (int8, derivation, error) {
	cpuDelta := float64(response.CPUStats.CPUUsage.TotalUsage - response.PreCPUStats.CPUUsage.TotalUsage)
	systemDelta := float64(response.CPUStats.SystemUsage - response.PreCPUStats.SystemUsage)
	if systemDelta <= 0 {
		return 0, derivation{}, fmt.Errorf("no processor sample taken, service [%s] reports system cpu moving by [%.0f] ns between polls so the counters are not monotonic", name, systemDelta)
	}
	onlineCPUs := float64(response.CPUStats.OnlineCPUs)
	if onlineCPUs == 0 {
		onlineCPUs = float64(len(response.CPUStats.CPUUsage.PercpuUsage))
	}
	usedPercent := (cpuDelta / systemDelta) * onlineCPUs * 100.0
	return stats.ConvertToInt(usedPercent), derived(scribe.ActionSample, "computed [%3d] pct used processor, service [%s] delta [%.0f] of system [%.0f] ns across [%.0f] cpus",
		stats.ConvertToInt(usedPercent), name, cpuDelta, systemDelta, onlineCPUs), nil
}

func (p *servicesProbe) memoryUsed(name string, response container.StatsResponse) (int8, derivation, error) {
	if response.MemoryStats.Limit == 0 {
		return 0, derivation{}, fmt.Errorf("no memory sample taken, service [%s] reports a [0] byte memory limit so a share of it cannot be computed", name)
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
	return stats.ConvertToInt(usedPercent), derived(scribe.ActionSample, "computed [%3d] pct used memory, service [%s] used [%d] MiB of limit [%d] MiB, cache [%d] MiB excluded",
		stats.ConvertToInt(usedPercent), name, int64(used)/bytesPerMiB, int64(response.MemoryStats.Limit)/bytesPerMiB, int64(cache)/bytesPerMiB), nil
}

func (p *servicesProbe) healthStatus(name string, containerInfo container.InspectResponse) (bool, derivation, error) {
	if containerInfo.ContainerJSONBase == nil || containerInfo.State == nil || containerInfo.State.Health == nil {
		return false, derived(scribe.ActionSample, "computed [false] healthy, service [%s] declares no docker health check so docker reports no health state", name), nil
	}
	healthy := containerInfo.State.Health.Status == container.Healthy
	return healthy, derived(scribe.ActionSample, "computed [%v] healthy, service [%s] docker health [%s] after [%d] failing streak",
		healthy, name, containerInfo.State.Health.Status, containerInfo.State.Health.FailingStreak), nil
}

func (p *servicesProbe) backupStatus() (bool, error) {
	// TODO: Provide implementation
	value, _, err := stub[bool](metric.MetricServiceBackupStatus)
	return value, err
}

func (p *servicesProbe) configuredStatus() (bool, error) {
	// TODO: Provide implementation
	return false, nil
}

func (p *servicesProbe) restartCount(name string, containerInfo container.InspectResponse) (float64, derivation, error) {
	if containerInfo.ContainerJSONBase == nil {
		return 0, derivation{}, fmt.Errorf("no restart count read, docker returned an inspect response for service [%s] with no base section", name)
	}
	return float64(containerInfo.RestartCount), derived(scribe.ActionSample, "computed [%d] restarts, service [%s] as counted by docker since the container was created",
		containerInfo.RestartCount, name), nil
}

func (p *servicesProbe) version(snapshot *installSnapshot, containerInfo container.InspectResponse) (string, derivation, error) {
	if containerInfo.Config != nil && containerInfo.Config.Image != "" {
		tokens := strings.Split(containerInfo.Config.Image, ":")
		if len(tokens) > 1 && config.VersionPattern.MatchString(tokens[1]) {
			return tokens[1], derived(scribe.ActionSample, "computed [%s] version, read from the image tag [%s] docker reports", tokens[1], containerInfo.Config.Image), nil
		}
	}
	name := containerServiceName(containerInfo)
	if name == "" {
		return versionUnknown, derived(scribe.ActionSample, "computed [%s] version, docker reports no usable image tag and the container carries no service name to look up in the install tree", versionUnknown), nil
	}
	installed, _ := snapshot.service(name)
	if installed.version != "" {
		return installed.version, derived(scribe.ActionSample, "computed [%s] version, service [%s] read from the install tree since the image tag carries none", installed.version, name), nil
	}
	return versionUnknown, derived(scribe.ActionSample, "computed [%s] version, service [%s] has no image tag and no version in the install tree under [%s]",
		versionUnknown, name, installRoot), nil
}

func (p *servicesProbe) sleep(snapshot *installSnapshot, containerInfo container.InspectResponse) (bool, error) {
	name := containerServiceName(containerInfo)
	if name == "" {
		return false, nil
	}
	installed, _ := snapshot.service(name)
	return installed.sleepEnabled, nil
}

func (p *servicesProbe) maxMemory(snapshot *installSnapshot, name string) (float64, derivation, error) {
	if name == "" {
		return 0, derivation{}, errors.New("no memory ceiling read, the container carries no service name to look up in the install tree")
	}
	installed, _ := snapshot.service(name)
	if installed.maxMemoryBytes <= 0 {
		return 0, derivation{}, fmt.Errorf("no memory ceiling read, service [%s] declares no [deploy.resources.limits.memory] in its compose file under [%s]", name, installRoot)
	}
	return float64(installed.maxMemoryBytes) / bytesPerMiB, derived(scribe.ActionSample, "computed [%.0f] MiB ceiling, service [%s] read from [deploy.resources.limits.memory] in its compose file",
		float64(installed.maxMemoryBytes)/bytesPerMiB, name), nil
}

func (p *servicesProbe) upTime(name string, containerInfo container.InspectResponse) (float64, derivation, error) {
	if containerInfo.ContainerJSONBase == nil || containerInfo.State == nil || containerInfo.State.StartedAt == "" {
		return 0, derivation{}, fmt.Errorf("no up time read, docker reports no start time for service [%s]", name)
	}
	startedAt, err := time.Parse(time.RFC3339Nano, containerInfo.State.StartedAt)
	if err != nil {
		return 0, derivation{}, fmt.Errorf("no up time read, service [%s] start time [%s] did not parse with [%w]", name, containerInfo.State.StartedAt, err)
	}
	upTime := time.Since(startedAt).Seconds()
	if upTime < 0 {
		return 0, derivation{}, fmt.Errorf("no up time read, service [%s] reports a start time [%s] in the future", name, containerInfo.State.StartedAt)
	}
	return upTime, derived(scribe.ActionSample, "computed [%.0f] s up, service [%s] started at [%s]", upTime, name, startedAt.Format(time.RFC3339)), nil
}

func (p *servicesProbe) logInstallMissing(snapshot *installSnapshot, services map[string]service) {
	missingStart := time.Now()
	var missing []string
	for name := range services {
		if _, found := snapshot.service(name); !found {
			missing = append(missing, name)
		}
	}
	sort.Strings(missing)
	joined := strings.Join(missing, ",")
	if joined == p.installMissingLogged {
		return
	}
	p.installMissingLogged = joined
	if len(missing) == 0 {
		return
	}
	scribe.Log(scribe.SourceProbe, scribe.SubjectHost(p.hostName), scribe.ActionDiscover).Warn("notfound", missingStart, "[%d] containers with no install directory [%s]", len(missing), joined)
}

func (p *servicesProbe) installs() installReader {
	return newInstallReader(p.configPath, p.hostName)
}

func containerServiceName(containerInfo container.InspectResponse) string {
	if containerInfo.ContainerJSONBase != nil {
		if name := strings.TrimPrefix(containerInfo.Name, "/"); name != "" {
			return name
		}
	}
	if containerInfo.Config != nil && containerInfo.Config.Image != "" {
		return strings.Split(strings.Split(containerInfo.Config.Image, ":")[0], "/")[0]
	}
	return ""
}

const (
	servicesDockerTimeoutSecs            = 2
	servicesDockerContainerIgnorePattern = "reaper_"
	versionUnknown                       = "-"
)
