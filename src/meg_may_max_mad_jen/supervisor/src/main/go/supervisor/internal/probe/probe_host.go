package probe

import (
	"context"
	"errors"
	"fmt"
	"strings"
	"supervisor/internal/config"
	"supervisor/internal/metric"
	"supervisor/internal/stats"

	"github.com/shirou/gopsutil/v4/cpu"
	"github.com/shirou/gopsutil/v4/mem"
	"github.com/shirou/gopsutil/v4/sensors"
)

type hostProbe struct {
	cache   *metric.RecordCache
	mask    [metric.MetricMax]bool
	periods config.Periods

	hostBool           *stats.BoolStats
	usedProcessorInt   *stats.IntStats
	usedMemoryInt      *stats.IntStats
	allocatedMemoryInt *stats.IntStats
	failedServicesInt  *stats.IntStats
	failedSharesInt    *stats.IntStats
	failedBackupsInt   *stats.IntStats
	warnTemperatureInt *stats.IntStats
	spinFanSpeedInt    *stats.IntStats
	lifeUsedDrivesInt  *stats.IntStats
	usedSystemSpaceInt *stats.IntStats
	usedShareSpaceInt  *stats.IntStats
	usedBackupSpaceInt *stats.IntStats
	usedSwapSpaceInt   *stats.IntStats
	usedDiskOpsInt     *stats.IntStats
	usedNetworkInt     *stats.IntStats
	runningTimeFloat   *stats.FloatStats
	temperatureFloat   *stats.FloatStats

	cpuSampler    *cpuUsageSampler
	cpuTimes      func(bool) ([]cpu.TimesStat, error)
	virtualMemory func() (*mem.VirtualMemoryStat, error)
	sensorsTemps  func() ([]sensors.TemperatureStat, error)
}

func newHostProbe() *hostProbe {
	return &hostProbe{
		cpuSampler:    &cpuUsageSampler{},
		cpuTimes:      cpu.Times,
		virtualMemory: mem.VirtualMemory,
		sensorsTemps:  sensors.SensorsTemperatures,
	}
}

func (*hostProbe) name() string { return "host" }

func (p *hostProbe) metrics() []metric.ID {
	return []metric.ID{
		metric.MetricHost,
		metric.MetricHostUsedProcessor,
		metric.MetricHostUsedMemory,
		metric.MetricHostAllocatedMemory,
		metric.MetricHostFailedServices,
		metric.MetricHostFailedShares,
		metric.MetricHostFailedBackups,
		metric.MetricHostWarnTemperatureOfMax,
		metric.MetricHostSpinFanSpeedOfMax,
		metric.MetricHostLifeUsedDrives,
		metric.MetricHostUsedSystemSpace,
		metric.MetricHostUsedShareSpace,
		metric.MetricHostUsedBackupSpace,
		metric.MetricHostUsedSwapSpace,
		metric.MetricHostUsedDiskOps,
		metric.MetricHostUsedNetwork,
		metric.MetricHostRunningTime,
		metric.MetricHostTemperature,
	}
}

func (p *hostProbe) create(_ string, cache *metric.RecordCache, mask [metric.MetricMax]bool, periods config.Periods) error {
	p.cache = cache
	p.mask = mask
	p.periods = periods

	p.hostBool = stats.NewBoolStats(periods.TrendHours, float64(periods.PulseMillis)/1000.0, float64(periods.PollMillis)/1000.0)
	p.usedProcessorInt = stats.NewIntStats(periods.TrendHours, float64(periods.PulseMillis)/1000.0, float64(periods.PollMillis)/1000.0)
	p.usedMemoryInt = stats.NewIntStats(periods.TrendHours, float64(periods.PulseMillis)/1000.0, float64(periods.PollMillis)/1000.0)
	p.allocatedMemoryInt = stats.NewIntStats(periods.TrendHours, float64(periods.PulseMillis)/1000.0, float64(periods.PollMillis)/1000.0)
	p.failedServicesInt = stats.NewIntStats(periods.TrendHours, float64(periods.PulseMillis)/1000.0, float64(periods.PollMillis)/1000.0)
	p.failedSharesInt = stats.NewIntStats(periods.TrendHours, float64(periods.PulseMillis)/1000.0, float64(periods.PollMillis)/1000.0)
	p.failedBackupsInt = stats.NewIntStats(periods.TrendHours, float64(periods.PulseMillis)/1000.0, float64(periods.PollMillis)/1000.0)
	p.warnTemperatureInt = stats.NewIntStats(periods.TrendHours, float64(periods.PulseMillis)/1000.0, float64(periods.PollMillis)/1000.0)
	p.spinFanSpeedInt = stats.NewIntStats(periods.TrendHours, float64(periods.PulseMillis)/1000.0, float64(periods.PollMillis)/1000.0)
	p.lifeUsedDrivesInt = stats.NewIntStats(periods.TrendHours, float64(periods.PulseMillis)/1000.0, float64(periods.PollMillis)/1000.0)
	p.usedSystemSpaceInt = stats.NewIntStats(periods.TrendHours, float64(periods.PulseMillis)/1000.0, float64(periods.PollMillis)/1000.0)
	p.usedShareSpaceInt = stats.NewIntStats(periods.TrendHours, float64(periods.PulseMillis)/1000.0, float64(periods.PollMillis)/1000.0)
	p.usedBackupSpaceInt = stats.NewIntStats(periods.TrendHours, float64(periods.PulseMillis)/1000.0, float64(periods.PollMillis)/1000.0)
	p.usedSwapSpaceInt = stats.NewIntStats(periods.TrendHours, float64(periods.PulseMillis)/1000.0, float64(periods.PollMillis)/1000.0)
	p.usedDiskOpsInt = stats.NewIntStats(periods.TrendHours, float64(periods.PulseMillis)/1000.0, float64(periods.PollMillis)/1000.0)
	p.usedNetworkInt = stats.NewIntStats(periods.TrendHours, float64(periods.PulseMillis)/1000.0, float64(periods.PollMillis)/1000.0)
	p.runningTimeFloat = stats.NewFloatStats(periods.TrendHours, float64(periods.PulseMillis)/1000.0, float64(periods.PollMillis)/1000.0)
	p.temperatureFloat = stats.NewFloatStats(periods.TrendHours, float64(periods.PulseMillis)/1000.0, float64(periods.PollMillis)/1000.0)

	return nil
}

func (p *hostProbe) run(_ context.Context, isPulse bool) error {
	runMetricCacheTasks(p, isPulse, []cacheMetricTask{
		newCacheMetricTask(
			metric.ValueBool,
			metric.MetricHost,
			metric.ServiceNameUnset,
			p.host,
			p.hostBool,
			func() bool { return p.hostBool.PulseLast() },
			func() bool { return p.hostBool.TrendMean() },
			func(bool) bool { return true },
			func(bool) bool { return true },
		),
		newCacheMetricTask(
			metric.ValueInt,
			metric.MetricHostUsedProcessor,
			metric.ServiceNameUnset,
			p.usedProcessor,
			p.usedProcessorInt,
			func() int8 { return p.usedProcessorInt.PulseMax() },
			func() int8 { return p.usedProcessorInt.TrendP95() },
			func(p int8) bool { return p <= 90 },
			func(t int8) bool { return t <= 70 },
		),
		newCacheMetricTask(
			metric.ValueInt,
			metric.MetricHostUsedMemory,
			metric.ServiceNameUnset,
			p.usedMemory,
			p.usedMemoryInt,
			func() int8 { return p.usedMemoryInt.PulseMax() },
			func() int8 { return p.usedMemoryInt.TrendMax() },
			func(p int8) bool { return p <= 95 },
			func(t int8) bool { return t <= 90 },
		),
		newCacheMetricTask(
			metric.ValueInt,
			metric.MetricHostAllocatedMemory,
			metric.ServiceNameUnset,
			p.allocatedMemory,
			p.allocatedMemoryInt,
			func() int8 { return p.allocatedMemoryInt.PulseMax() },
			func() int8 { return p.allocatedMemoryInt.TrendMax() },
			func(p int8) bool { return p <= 95 },
			func(t int8) bool { return t <= 90 },
		),
		newCacheMetricTask(
			metric.ValueInt,
			metric.MetricHostFailedServices,
			metric.ServiceNameUnset,
			p.failedServices,
			p.failedServicesInt,
			func() int8 { return p.failedServicesInt.PulseMax() },
			func() int8 { return p.failedServicesInt.TrendMax() },
			func(p int8) bool { return p == 0 },
			func(t int8) bool { return t == 0 },
		),
		newCacheMetricTask(
			metric.ValueInt,
			metric.MetricHostFailedShares,
			metric.ServiceNameUnset,
			p.failedShares,
			p.failedSharesInt,
			func() int8 { return p.failedSharesInt.PulseMax() },
			func() int8 { return p.failedSharesInt.TrendMax() },
			func(p int8) bool { return p == 0 },
			func(t int8) bool { return t == 0 },
		),
		newCacheMetricTask(
			metric.ValueInt,
			metric.MetricHostFailedBackups,
			metric.ServiceNameUnset,
			p.failedBackups,
			p.failedBackupsInt,
			func() int8 { return p.failedBackupsInt.PulseMax() },
			func() int8 { return p.failedBackupsInt.TrendMax() },
			func(p int8) bool { return p == 0 },
			func(t int8) bool { return t == 0 },
		),
		newCacheMetricTask(
			metric.ValueInt,
			metric.MetricHostWarnTemperatureOfMax,
			metric.ServiceNameUnset,
			p.warnTemperature,
			p.warnTemperatureInt,
			func() int8 { return p.warnTemperatureInt.PulseMax() },
			func() int8 { return p.warnTemperatureInt.TrendMax() },
			func(p int8) bool { return p <= 80 },
			func(t int8) bool { return t <= 70 },
		),
		newCacheMetricTask(
			metric.ValueInt,
			metric.MetricHostSpinFanSpeedOfMax,
			metric.ServiceNameUnset,
			p.spinFanSpeed,
			p.spinFanSpeedInt,
			func() int8 { return p.spinFanSpeedInt.PulseMax() },
			func() int8 { return p.spinFanSpeedInt.TrendMax() },
			func(int8) bool { return true },
			func(int8) bool { return true },
		),
		newCacheMetricTask(
			metric.ValueInt,
			metric.MetricHostLifeUsedDrives,
			metric.ServiceNameUnset,
			p.lifeUsedDrives,
			p.lifeUsedDrivesInt,
			func() int8 { return p.lifeUsedDrivesInt.PulseMax() },
			func() int8 { return p.lifeUsedDrivesInt.TrendMax() },
			func(p int8) bool { return p <= 90 },
			func(t int8) bool { return t <= 80 },
		),
		newCacheMetricTask(
			metric.ValueInt,
			metric.MetricHostUsedSystemSpace,
			metric.ServiceNameUnset,
			p.usedSystemSpace,
			p.usedSystemSpaceInt,
			func() int8 { return p.usedSystemSpaceInt.PulseMax() },
			func() int8 { return p.usedSystemSpaceInt.TrendMax() },
			func(p int8) bool { return p <= 90 },
			func(t int8) bool { return t <= 80 },
		),
		newCacheMetricTask(
			metric.ValueInt,
			metric.MetricHostUsedShareSpace,
			metric.ServiceNameUnset,
			p.usedShareSpace,
			p.usedShareSpaceInt,
			func() int8 { return p.usedShareSpaceInt.PulseMax() },
			func() int8 { return p.usedShareSpaceInt.TrendMax() },
			func(p int8) bool { return p <= 90 },
			func(t int8) bool { return t <= 80 },
		),
		newCacheMetricTask(
			metric.ValueInt,
			metric.MetricHostUsedBackupSpace,
			metric.ServiceNameUnset,
			p.usedBackupSpace,
			p.usedBackupSpaceInt,
			func() int8 { return p.usedBackupSpaceInt.PulseMax() },
			func() int8 { return p.usedBackupSpaceInt.TrendMax() },
			func(p int8) bool { return p <= 90 },
			func(t int8) bool { return t <= 80 },
		),
		newCacheMetricTask(
			metric.ValueInt,
			metric.MetricHostUsedSwapSpace,
			metric.ServiceNameUnset,
			p.usedSwapSpace,
			p.usedSwapSpaceInt,
			func() int8 { return p.usedSwapSpaceInt.PulseMax() },
			func() int8 { return p.usedSwapSpaceInt.TrendMax() },
			func(p int8) bool { return p <= 80 },
			func(t int8) bool { return t <= 70 },
		),
		newCacheMetricTask(
			metric.ValueInt,
			metric.MetricHostUsedDiskOps,
			metric.ServiceNameUnset,
			p.usedDiskOps,
			p.usedDiskOpsInt,
			func() int8 { return p.usedDiskOpsInt.PulseMax() },
			func() int8 { return p.usedDiskOpsInt.TrendMax() },
			func(p int8) bool { return p <= 90 },
			func(t int8) bool { return t <= 80 },
		),
		newCacheMetricTask(
			metric.ValueInt,
			metric.MetricHostUsedNetwork,
			metric.ServiceNameUnset,
			p.usedNetwork,
			p.usedNetworkInt,
			func() int8 { return p.usedNetworkInt.PulseMax() },
			func() int8 { return p.usedNetworkInt.TrendMax() },
			func(p int8) bool { return p <= 90 },
			func(t int8) bool { return t <= 80 },
		),
		newCacheMetricTask(
			metric.ValueFloat,
			metric.MetricHostRunningTime,
			metric.ServiceNameUnset,
			p.runningTime,
			p.runningTimeFloat,
			func() float64 { return p.runningTimeFloat.PulseLast() },
			nil,
			func(float64) bool { return true },
			nil,
		),
		newCacheMetricTask(
			metric.ValueFloat,
			metric.MetricHostTemperature,
			metric.ServiceNameUnset,
			p.temperature,
			p.temperatureFloat,
			func() float64 { return p.temperatureFloat.PulseMax() },
			func() float64 { return p.temperatureFloat.TrendMax() },
			func(p float64) bool { return p <= 80 },
			func(t float64) bool { return t <= 70 },
		),
	})
	return nil
}

func (p *hostProbe) records() *metric.RecordCache {
	return p.cache
}

func (p *hostProbe) hasMetric(id metric.ID) bool {
	return p.mask[id]
}

func (p *hostProbe) host() (bool, error) {
	return true, nil
}

func (p *hostProbe) usedProcessor() (int8, error) {
	if p.cpuSampler == nil || p.cpuTimes == nil {
		return 0, errors.New("cpu sampler not initialized")
	}
	return p.cpuSampler.sample(p.cpuTimes)
}

func (p *hostProbe) usedMemory() (int8, error) {
	if p.virtualMemory == nil {
		return 0, errors.New("host memory unavailable")
	}
	memoryStat, err := p.virtualMemory()
	if err != nil {
		return 0, fmt.Errorf("virtual memory stats: %w", err)
	}
	if memoryStat.Total == 0 {
		return 0, errors.New("total memory must be > 0")
	}
	usedPercent := (float64(memoryStat.Used) / float64(memoryStat.Total)) * 100.0
	return stats.ConvertToInt(usedPercent), nil
}

func (p *hostProbe) allocatedMemory() (int8, error) {
	return 0, nil
}

func (p *hostProbe) failedServices() (int8, error) {
	return 0, nil
}

func (p *hostProbe) failedShares() (int8, error) {
	return 0, nil
}

func (p *hostProbe) failedBackups() (int8, error) {
	return 0, nil
}

func (p *hostProbe) warnTemperature() (int8, error) {
	return 0, nil
}

func (p *hostProbe) spinFanSpeed() (int8, error) {
	return 0, nil
}

func (p *hostProbe) lifeUsedDrives() (int8, error) {
	return 0, nil
}

func (p *hostProbe) usedSystemSpace() (int8, error) {
	return 0, nil
}

func (p *hostProbe) usedShareSpace() (int8, error) {
	return 0, nil
}

func (p *hostProbe) usedBackupSpace() (int8, error) {
	return 0, nil
}

func (p *hostProbe) usedSwapSpace() (int8, error) {
	return 0, nil
}

func (p *hostProbe) usedDiskOps() (int8, error) {
	return 0, nil
}

func (p *hostProbe) usedNetwork() (int8, error) {
	return 0, nil
}

func (p *hostProbe) runningTime() (float64, error) {
	return 0, nil
}

func (p *hostProbe) temperature() (float64, error) {
	if p.sensorsTemps == nil {
		return 0, errors.New("temperature sensors unavailable")
	}
	temperatures, err := p.sensorsTemps()
	if err != nil {
		return 0, fmt.Errorf("temperature sensors unavailable: %w", err)
	}
	const (
		minTemp = 10.0
		maxTemp = 150.0
	)
	packageTemp := 0.0
	packageFound := false
	compositeTemp := 0.0
	compositeFound := false
	for _, entry := range temperatures {
		zoneKey := strings.ToLower(entry.SensorKey)
		if entry.Temperature < minTemp || entry.Temperature > maxTemp {
			continue
		}
		if strings.Contains(zoneKey, "package") {
			if !packageFound || entry.Temperature > packageTemp {
				packageTemp = entry.Temperature
			}
			packageFound = true
			continue
		}
		if strings.Contains(zoneKey, "composite") {
			adjusted := entry.Temperature + 10.0
			if adjusted < minTemp || adjusted > maxTemp {
				continue
			}
			if !compositeFound || adjusted > compositeTemp {
				compositeTemp = adjusted
			}
			compositeFound = true
		}
	}
	if packageFound {
		return packageTemp, nil
	}
	if compositeFound {
		return compositeTemp, nil
	}
	return 0, errors.New("no suitable temperature sensors found")
}

type cpuUsageSampler struct {
	hasSample  bool
	lastSample cpu.TimesStat
}

//goland:noinspection GoDeprecation
func (s *cpuUsageSampler) sample(cpuTimes func(bool) ([]cpu.TimesStat, error)) (int8, error) {
	currentTimes, err := cpuTimes(false)
	if err != nil {
		return 0, fmt.Errorf("cpu times: %w", err)
	}
	if len(currentTimes) == 0 {
		return 0, errors.New("failed to sampleFunc processor usage")
	}
	if !s.hasSample {
		s.lastSample = currentTimes[0]
		s.hasSample = true
		return 0, errProbeWarmingUp
	}
	previousIdleTime := s.lastSample.Idle
	previousTotalTime := s.lastSample.Total()
	currentIdleTime := currentTimes[0].Idle
	currentTotalTime := currentTimes[0].Total()
	idleDelta := currentIdleTime - previousIdleTime
	totalDelta := currentTotalTime - previousTotalTime
	s.lastSample = currentTimes[0]
	if totalDelta <= 0 {
		return 0, errors.New("cpu usage unavailable, non-monotonic counters")
	}
	usedPercent := (1.0 - idleDelta/totalDelta) * 100.0
	return stats.ConvertToInt(usedPercent), nil
}
