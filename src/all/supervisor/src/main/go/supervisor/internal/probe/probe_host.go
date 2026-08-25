package probe

import (
	"context"
	"errors"
	"fmt"
	"supervisor/internal/config"
	"supervisor/internal/metric"
	"supervisor/internal/scribe"
	"supervisor/internal/stats"
	"time"

	"github.com/shirou/gopsutil/v4/cpu"
	"github.com/shirou/gopsutil/v4/mem"
)

type hostProbe struct {
	cache      *metric.RecordCache
	mask       [metric.MetricMax]bool
	periods    config.Periods
	configPath string
	hostName   string

	hostBool           *stats.BoolStats
	usedProcessorInt   *stats.IntStats
	usedMemoryInt      *stats.IntStats
	allocatedMemoryInt *stats.IntStats
	failedLogsInt      *stats.IntStats
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

	sysRoot               string
	allocatedMemoryLogged int64
	cpuSampler            *cpuUsageSampler
	cpuTimes              func(bool) ([]cpu.TimesStat, error)
	virtualMemory         func() (*mem.VirtualMemoryStat, error)
}

func newHostProbe() *hostProbe {
	return &hostProbe{
		sysRoot:       sensorSysRoot,
		cpuSampler:    &cpuUsageSampler{},
		cpuTimes:      cpu.Times,
		virtualMemory: mem.VirtualMemory,
	}
}

func (*hostProbe) name() string { return "host" }

func (p *hostProbe) metrics() []metric.ID {
	return []metric.ID{
		metric.MetricHost,
		metric.MetricHostUsedProcessor,
		metric.MetricHostUsedMemory,
		metric.MetricHostAllocatedMemory,
		metric.MetricHostFailedLogs,
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

func (p *hostProbe) create(configPath string, cache *metric.RecordCache, mask [metric.MetricMax]bool, periods config.Periods) error {
	p.cache = cache
	p.mask = mask
	p.periods = periods
	p.configPath = configPath
	p.hostName = config.Load(configPath).Host()

	p.hostBool = stats.NewBoolStats(periods.TrendHours, float64(periods.PulseMillis)/1000.0, float64(periods.PollMillis)/1000.0)
	p.usedProcessorInt = stats.NewIntStats(periods.TrendHours, float64(periods.PulseMillis)/1000.0, float64(periods.PollMillis)/1000.0)
	p.usedMemoryInt = stats.NewIntStats(periods.TrendHours, float64(periods.PulseMillis)/1000.0, float64(periods.PollMillis)/1000.0)
	p.allocatedMemoryInt = stats.NewIntStats(periods.TrendHours, float64(periods.PulseMillis)/1000.0, float64(periods.PollMillis)/1000.0)
	p.failedLogsInt = stats.NewIntStats(periods.TrendHours, float64(periods.PulseMillis)/1000.0, float64(periods.PollMillis)/1000.0)
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
	reportMetricInert(p)
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
			metric.MetricHostFailedLogs,
			metric.ServiceNameUnset,
			p.failedLogs,
			p.failedLogsInt,
			func() int8 { return p.failedLogsInt.PulseMax() },
			func() int8 { return p.failedLogsInt.TrendMax() },
			func(pulse int8) bool { return pulse <= logErrorPulseOfMax },
			func(trend int8) bool { return trend == 0 },
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
			func(pulse int8) bool { return pulse <= sensorWarnPulseOfMax },
			func(trend int8) bool { return trend <= sensorWarnTrendOfMax },
		),
		newCacheMetricTask(
			metric.ValueInt,
			metric.MetricHostSpinFanSpeedOfMax,
			metric.ServiceNameUnset,
			p.spinFanSpeed,
			p.spinFanSpeedInt,
			func() int8 { return p.spinFanSpeedInt.PulseMax() },
			func() int8 { return p.spinFanSpeedInt.TrendMax() },
			func(fan int8) bool {
				return p.spinFanRespondingOK("pulse", fan, p.warnTemperatureInt.PulseMax(), sensorWarnPulseOfMax, sensorFanPulseOfMax)
			},
			func(fan int8) bool {
				return p.spinFanRespondingOK("trend", fan, p.warnTemperatureInt.TrendMax(), sensorWarnTrendOfMax, sensorFanTrendOfMax)
			},
		),
		newCacheMetricTask(
			metric.ValueInt,
			metric.MetricHostLifeUsedDrives,
			metric.ServiceNameUnset,
			p.lifeUsedDrives,
			p.lifeUsedDrivesInt,
			func() int8 { return p.lifeUsedDrivesInt.PulseMax() },
			func() int8 { return p.lifeUsedDrivesInt.TrendMax() },
			func(pulse int8) bool { return pulse <= 90 && !p.mounts().drivesErrored() },
			func(trend int8) bool { return trend <= 80 && !p.mounts().drivesErrored() },
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
	memoryStart := time.Now()
	memoryStat, err := p.virtualMemory()
	if err != nil {
		return 0, fmt.Errorf("virtual memory stats: %w", err)
	}
	if memoryStat.Total == 0 {
		return 0, errors.New("total memory must be > 0")
	}
	usedPercent := (float64(memoryStat.Used) / float64(memoryStat.Total)) * 100.0
	derive("host", "memory", memoryStart, "computed [%3d] pct used, used [%d] MiB of total [%d] MiB, available [%d] MiB",
		stats.ConvertToInt(usedPercent), memoryStat.Used/bytesPerMiB, memoryStat.Total/bytesPerMiB, memoryStat.Available/bytesPerMiB)
	return stats.ConvertToInt(usedPercent), nil
}

func (p *hostProbe) allocatedMemory() (int8, error) {
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
	allocatedStart := time.Now()
	allocatedBytes, err := p.installs().allocation()
	if err != nil {
		return 0, err
	}
	allocatedPercent := (float64(allocatedBytes) / float64(memoryStat.Total)) * 100.0
	derive("host", "allocated", allocatedStart, "computed [%3d] pct allocated, ceilings [%d] MiB of total [%d] MiB, configured [%d] services",
		stats.ConvertToInt(allocatedPercent), allocatedBytes/bytesPerMiB, int64(memoryStat.Total)/bytesPerMiB, len(config.Load(p.configPath).Services(p.hostName)))
	allocatedMemoryExceeded := allocatedPercent > 100.0
	if allocatedMemoryExceeded {
		if allocatedBytes != p.allocatedMemoryLogged {
			p.allocatedMemoryLogged = allocatedBytes
			scribe.Probe("state", "host").Error("allocated", allocatedStart, "exceeded [%d] MiB allocated of [%d] MiB total at [%.1f] pct", allocatedBytes/bytesPerMiB, int64(memoryStat.Total)/bytesPerMiB, allocatedPercent)
		}
		allocatedPercent = 100.0
	}
	return stats.ConvertToInt(allocatedPercent), nil
}

func (p *hostProbe) failedLogs() (int8, error) {
	logsStart := time.Now()
	window := config.TrendWindow(p.periods.TrendHours)
	count, available := loadLogs(config.Load(p.configPath).Mount()).errorsWithin(window)
	if !available {
		derive("host", "logs", logsStart, "computed [  0] pct failed, kernel log unreadable so the metric is inert and always ok")
		return 0, nil
	}
	derive("host", "logs", logsStart, "computed [%3d] pct failed, errors [%d] of budget [%d] within window [%s], ok pulse at [<=%d] pct trend at [0] pct",
		stats.ConvertToInt(float64(count)/logErrorBudget*100.0), count, int(logErrorBudget), window, logErrorPulseOfMax)
	return stats.ConvertToInt(float64(count) / logErrorBudget * 100.0), nil
}

func (p *hostProbe) failedShares() (int8, error) {
	return p.mounts().failedShares()
}

func (p *hostProbe) failedBackups() (int8, error) {
	return inertInt(metric.MetricHostFailedBackups)
}

func (p *hostProbe) warnTemperature() (int8, error) {
	temperatureCelsius, err := p.temperature()
	if err != nil {
		return 0, err
	}
	warnStart := time.Now()
	warnOfMax := stats.ConvertToInt(sensorWarnPerCelsius * (temperatureCelsius - sensorWarnFloorCelsius))
	derive("host", "temperature", warnStart, "computed [%3d] pct of warn, celsius [%.1f] above floor [%.1f] at [%.1f] pct per celsius, ok pulse at [<=%d] pct trend at [<=%d] pct",
		warnOfMax, temperatureCelsius, sensorWarnFloorCelsius, sensorWarnPerCelsius, sensorWarnPulseOfMax, sensorWarnTrendOfMax)
	return warnOfMax, nil
}

func (p *hostProbe) spinFanRespondingOK(window string, fan int8, temperature int8, temperatureMax int8, fanMin int8) bool {
	respondingStart := time.Now()
	if !loadSensors(p.sysRoot).hasFans() {
		derive("host", "fan", respondingStart, "computed [true] responding over [%s], host reports no fans so the metric is inert and always ok", window)
		return true
	}
	responding := temperature <= temperatureMax || fan > fanMin
	derive("host", "fan", respondingStart, "computed [%v] responding over [%s], speed [%d] pct of max, temperature [%d] pct of warn, ok while temperature [<=%d] pct or speed [>%d] pct",
		responding, window, fan, temperature, temperatureMax, fanMin)
	return responding
}

func (p *hostProbe) spinFanSpeed() (int8, error) {
	speedOfMax, err := loadSensors(p.sysRoot).fanSpeedOfMax()
	if err != nil {
		return 0, err
	}
	return stats.ConvertToInt(speedOfMax), nil
}

func (p *hostProbe) lifeUsedDrives() (int8, error) {
	return p.mounts().lifeUsedDrives()
}

func (p *hostProbe) usedSystemSpace() (int8, error) {
	return p.mounts().usedSystemSpace()
}

func (p *hostProbe) usedShareSpace() (int8, error) {
	return p.mounts().usedShareSpace()
}

func (p *hostProbe) usedBackupSpace() (int8, error) {
	return inertInt(metric.MetricHostUsedBackupSpace)
}

func (p *hostProbe) usedSwapSpace() (int8, error) {
	return inertInt(metric.MetricHostUsedSwapSpace)
}

func (p *hostProbe) usedDiskOps() (int8, error) {
	return inertInt(metric.MetricHostUsedDiskOps)
}

func (p *hostProbe) usedNetwork() (int8, error) {
	return inertInt(metric.MetricHostUsedNetwork)
}

func (p *hostProbe) runningTime() (float64, error) {
	return inertFloat(metric.MetricHostRunningTime)
}

func (p *hostProbe) temperature() (float64, error) {
	return loadSensors(p.sysRoot).celsius()
}

func (p *hostProbe) installs() installReader {
	return newInstallReader(p.configPath, p.hostName)
}

func (p *hostProbe) mounts() *mountSet {
	return loadMounts(config.Load(p.configPath).Mount(), config.CacheWindow(p.periods.CacheMins))
}

type cpuUsageSampler struct {
	hasSample  bool
	lastSample cpu.TimesStat
}

//goland:noinspection GoDeprecation
func (s *cpuUsageSampler) sample(cpuTimes func(bool) ([]cpu.TimesStat, error)) (int8, error) {
	sampleStart := time.Now()
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
	derive("host", "processor", sampleStart, "computed [%3d] pct used, idle delta [%.1f] of total delta [%.1f] ticks",
		stats.ConvertToInt(usedPercent), idleDelta, totalDelta)
	return stats.ConvertToInt(usedPercent), nil
}
