package probe

import (
	"context"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"supervisor/internal/config"
	"supervisor/internal/metric"
	"supervisor/internal/scribe"
	"supervisor/internal/stats"
	"time"

	"github.com/shirou/gopsutil/v4/cpu"
	"github.com/shirou/gopsutil/v4/disk"
	"github.com/shirou/gopsutil/v4/host"
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
	warnTemperatureInt *stats.IntStats
	spinFanSpeedInt    *stats.IntStats
	failedDrivesInt    *stats.IntStats
	usedDriveLifeInt   *stats.IntStats
	usedHomeSpaceInt   *stats.IntStats
	usedShareSpaceInt  *stats.IntStats
	usedSwapSpaceInt   *stats.IntStats
	usedDiskTimeInt    *stats.IntStats
	usedNetworkInt     *stats.IntStats
	upTimeFloat        *stats.FloatStats
	temperatureFloat   *stats.FloatStats

	sysRoot               string
	allocatedMemoryLogged int64
	cpuSampler            *cpuUsageSampler
	diskSampler           *diskUsageSampler
	networkSampler        *networkUsageSampler
	cpuTimes              func(bool) ([]cpu.TimesStat, error)
	virtualMemory         func() (*mem.VirtualMemoryStat, error)
	swapMemory            func() (*mem.SwapMemoryStat, error)
	diskCounters          func(...string) (map[string]disk.IOCountersStat, error)
	hostUptime            func() (uint64, error)
}

func newHostProbe() *hostProbe {
	return &hostProbe{
		sysRoot:       sensorSysRoot,
		cpuSampler:    &cpuUsageSampler{},
		diskSampler:   &diskUsageSampler{},
		cpuTimes:      cpu.Times,
		virtualMemory: mem.VirtualMemory,
		swapMemory:    mem.SwapMemory,
		diskCounters:  disk.IOCounters,
		hostUptime:    host.Uptime,
	}
}

func (*hostProbe) subject() scribe.Subject { return scribe.SubjectHost("") }

func (*hostProbe) dormant() bool { return false }

func (p *hostProbe) metrics() []metric.ID {
	return []metric.ID{
		metric.MetricHost,
		metric.MetricHostUsedProcessor,
		metric.MetricHostUsedMemory,
		metric.MetricHostAllocatedMemory,
		metric.MetricHostFailedLogs,
		metric.MetricHostFailedShares,
		metric.MetricHostWarnTemperature,
		metric.MetricHostSpinFanSpeed,
		metric.MetricHostFailedDrives,
		metric.MetricHostUsedDriveLife,
		metric.MetricHostUsedHomeSpace,
		metric.MetricHostUsedShareSpace,
		metric.MetricHostUsedSwapSpace,
		metric.MetricHostUsedDiskTime,
		metric.MetricHostUsedNetwork,
		metric.MetricHostUpTime,
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
	p.warnTemperatureInt = stats.NewIntStats(periods.TrendHours, float64(periods.PulseMillis)/1000.0, float64(periods.PollMillis)/1000.0)
	p.spinFanSpeedInt = stats.NewIntStats(periods.TrendHours, float64(periods.PulseMillis)/1000.0, float64(periods.PollMillis)/1000.0)
	p.failedDrivesInt = stats.NewIntStats(periods.TrendHours, float64(periods.PulseMillis)/1000.0, float64(periods.PollMillis)/1000.0)
	p.usedDriveLifeInt = stats.NewIntStats(periods.TrendHours, float64(periods.PulseMillis)/1000.0, float64(periods.PollMillis)/1000.0)
	p.usedHomeSpaceInt = stats.NewIntStats(periods.TrendHours, float64(periods.PulseMillis)/1000.0, float64(periods.PollMillis)/1000.0)
	p.usedShareSpaceInt = stats.NewIntStats(periods.TrendHours, float64(periods.PulseMillis)/1000.0, float64(periods.PollMillis)/1000.0)
	p.usedSwapSpaceInt = stats.NewIntStats(periods.TrendHours, float64(periods.PulseMillis)/1000.0, float64(periods.PollMillis)/1000.0)
	p.usedDiskTimeInt = stats.NewIntStats(periods.TrendHours, float64(periods.PulseMillis)/1000.0, float64(periods.PollMillis)/1000.0)
	p.usedNetworkInt = stats.NewIntStats(periods.TrendHours, float64(periods.PulseMillis)/1000.0, float64(periods.PollMillis)/1000.0)
	p.upTimeFloat = stats.NewFloatStats(periods.TrendHours, float64(periods.PulseMillis)/1000.0, float64(periods.PollMillis)/1000.0)
	p.temperatureFloat = stats.NewFloatStats(periods.TrendHours, float64(periods.PulseMillis)/1000.0, float64(periods.PollMillis)/1000.0)
	return nil
}

func (p *hostProbe) gates() []metric.GateID { return nil }

func (p *hostProbe) poll(_ context.Context, isPulse bool) error {
	runCacheMetricTasks(p, isPulse, nil, []cacheMetricTask{
		newCacheMetricTask(
			metric.ValueBool,
			metric.MetricHost,
			metric.ServiceNameUnset,
			p.host,
			p.hostBool,
			func() bool { return p.hostBool.PulseLast() },
			func() bool { return p.hostBool.TrendMean() },
		),
		newCacheMetricTask(
			metric.ValueInt,
			metric.MetricHostUsedProcessor,
			metric.ServiceNameUnset,
			p.usedProcessor,
			p.usedProcessorInt,
			func() int8 { return p.usedProcessorInt.PulseMax() },
			func() int8 { return p.usedProcessorInt.TrendP95() },
		),
		newCacheMetricTask(
			metric.ValueInt,
			metric.MetricHostUsedMemory,
			metric.ServiceNameUnset,
			p.usedMemory,
			p.usedMemoryInt,
			func() int8 { return p.usedMemoryInt.PulseMax() },
			func() int8 { return p.usedMemoryInt.TrendMax() },
		),
		newCacheMetricTask(
			metric.ValueInt,
			metric.MetricHostAllocatedMemory,
			metric.ServiceNameUnset,
			p.allocatedMemory,
			p.allocatedMemoryInt,
			func() int8 { return p.allocatedMemoryInt.PulseMax() },
			func() int8 { return p.allocatedMemoryInt.TrendMax() },
		),
		newCacheMetricTask(
			metric.ValueInt,
			metric.MetricHostFailedLogs,
			metric.ServiceNameUnset,
			p.failedLogs,
			p.failedLogsInt,
			func() int8 { return p.failedLogsInt.PulseMax() },
			func() int8 { return p.failedLogsInt.TrendMax() },
		),
		newCacheMetricTask(
			metric.ValueInt,
			metric.MetricHostFailedShares,
			metric.ServiceNameUnset,
			p.failedShares,
			p.failedSharesInt,
			func() int8 { return p.failedSharesInt.PulseMax() },
			func() int8 { return p.failedSharesInt.TrendMax() },
		),
		newCacheMetricTask(
			metric.ValueInt,
			metric.MetricHostWarnTemperature,
			metric.ServiceNameUnset,
			p.warnTemperature,
			p.warnTemperatureInt,
			func() int8 { return p.warnTemperatureInt.PulseMax() },
			func() int8 { return p.warnTemperatureInt.TrendMax() },
		),
		newCacheMetricTask(
			metric.ValueInt,
			metric.MetricHostSpinFanSpeed,
			metric.ServiceNameUnset,
			p.spinFanSpeed,
			p.spinFanSpeedInt,
			func() int8 { return p.spinFanSpeedInt.PulseMax() },
			func() int8 { return p.spinFanSpeedInt.TrendMax() },
		),
		newCacheMetricTask(
			metric.ValueInt,
			metric.MetricHostFailedDrives,
			metric.ServiceNameUnset,
			p.failedDrives,
			p.failedDrivesInt,
			func() int8 { return p.failedDrivesInt.PulseMax() },
			func() int8 { return p.failedDrivesInt.TrendMax() },
		),
		newCacheMetricTask(
			metric.ValueInt,
			metric.MetricHostUsedDriveLife,
			metric.ServiceNameUnset,
			p.usedDriveLife,
			p.usedDriveLifeInt,
			func() int8 { return p.usedDriveLifeInt.PulseMax() },
			func() int8 { return p.usedDriveLifeInt.TrendMax() },
		),
		newCacheMetricTask(
			metric.ValueInt,
			metric.MetricHostUsedHomeSpace,
			metric.ServiceNameUnset,
			p.usedHomeSpace,
			p.usedHomeSpaceInt,
			func() int8 { return p.usedHomeSpaceInt.PulseMax() },
			func() int8 { return p.usedHomeSpaceInt.TrendMax() },
		),
		newCacheMetricTask(
			metric.ValueInt,
			metric.MetricHostUsedShareSpace,
			metric.ServiceNameUnset,
			p.usedShareSpace,
			p.usedShareSpaceInt,
			func() int8 { return p.usedShareSpaceInt.PulseMax() },
			func() int8 { return p.usedShareSpaceInt.TrendMax() },
		),
		newCacheMetricTask(
			metric.ValueInt,
			metric.MetricHostUsedSwapSpace,
			metric.ServiceNameUnset,
			p.usedSwapSpace,
			p.usedSwapSpaceInt,
			func() int8 { return p.usedSwapSpaceInt.PulseMax() },
			func() int8 { return p.usedSwapSpaceInt.TrendMax() },
		),
		newCacheMetricTask(
			metric.ValueInt,
			metric.MetricHostUsedDiskTime,
			metric.ServiceNameUnset,
			p.usedDiskTime,
			p.usedDiskTimeInt,
			func() int8 { return p.usedDiskTimeInt.PulseMax() },
			func() int8 { return p.usedDiskTimeInt.TrendMax() },
		),
		newCacheMetricTask(
			metric.ValueInt,
			metric.MetricHostUsedNetwork,
			metric.ServiceNameUnset,
			p.usedNetwork,
			p.usedNetworkInt,
			func() int8 { return p.usedNetworkInt.PulseMax() },
			func() int8 { return p.usedNetworkInt.TrendMax() },
		),
		newCacheMetricTask(
			metric.ValueFloat,
			metric.MetricHostUpTime,
			metric.ServiceNameUnset,
			p.upTime,
			p.upTimeFloat,
			func() float64 { return p.upTimeFloat.PulseLast() },
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

func (p *hostProbe) host() (bool, derivation, error) {
	return true, derivedf(scribe.ActionSample, "computed [true] reporting, the host publishes this beacon every pulse and it is ok whenever the record exists"), nil
}

func (p *hostProbe) usedProcessor() (int8, derivation, error) {
	if p.cpuSampler == nil || p.cpuTimes == nil {
		return 0, derivation{}, errors.New("no processor sample taken, the probe was created without a cpu sampler or a times reader")
	}
	return p.cpuSampler.sample(p.cpuTimes)
}

func (p *hostProbe) usedMemory() (int8, derivation, error) {
	if p.virtualMemory == nil {
		return 0, derivation{}, errors.New("no memory reading taken, the probe was created without a virtual memory reader")
	}
	memoryStat, err := p.virtualMemory()
	if err != nil {
		return 0, derivation{}, fmt.Errorf("no memory reading taken, virtual memory stats failed with [%w]", err)
	}
	if memoryStat.Total == 0 {
		return 0, derivation{}, errors.New("no memory reading taken, the host reports [0] bytes of total memory so a share of it cannot be computed")
	}
	usedPercent := (float64(memoryStat.Used) / float64(memoryStat.Total)) * 100.0
	return stats.ConvertToInt(usedPercent), derivedf(scribe.ActionCompute, "computed [%3d] pct used, used [%d] MiB of total [%d] MiB, available [%d] MiB",
		stats.ConvertToInt(usedPercent), memoryStat.Used/bytesPerMiB, memoryStat.Total/bytesPerMiB, memoryStat.Available/bytesPerMiB), nil
}

func (p *hostProbe) allocatedMemory() (int8, derivation, error) {
	if p.virtualMemory == nil {
		return 0, derivation{}, errors.New("no memory ceiling computed, the probe was created without a virtual memory reader")
	}
	memoryStat, err := p.virtualMemory()
	if err != nil {
		return 0, derivation{}, fmt.Errorf("no memory ceiling computed, virtual memory stats failed with [%w]", err)
	}
	if memoryStat.Total == 0 {
		return 0, derivation{}, errors.New("no memory ceiling computed, the host reports [0] bytes of total memory so a share of it cannot be computed")
	}
	allocatedStart := time.Now()
	allocatedBytes, installed, err := p.installs().allocation()
	if err != nil {
		return 0, derivation{}, err
	}
	allocatedPercent := (float64(allocatedBytes) / float64(memoryStat.Total)) * 100.0
	sampled := derivedf(scribe.ActionCompute, "computed [%3d] pct allocated, ceilings [%d] MiB of total [%d] MiB, installed [%d] of configured [%d] services",
		stats.ConvertToInt(allocatedPercent), allocatedBytes/bytesPerMiB, int64(memoryStat.Total)/bytesPerMiB, installed, len(config.Load(p.configPath).Services(p.hostName)))
	if allocatedPercent > 100.0 {
		if allocatedBytes != p.allocatedMemoryLogged {
			p.allocatedMemoryLogged = allocatedBytes
			scribe.Log(scribe.SourceProbeHost, scribe.SubjectMetric(metric.MetricHostAllocatedMemory), scribe.ActionCompute).Warnf("exceeded", allocatedStart, "[%d] MiB allocated of [%d] MiB total at [%.1f] pct across [%d] installed services, capping the metric at [100] pct",
				allocatedBytes/bytesPerMiB, int64(memoryStat.Total)/bytesPerMiB, allocatedPercent, installed)
		}
		allocatedPercent = 100.0
	}
	return stats.ConvertToInt(allocatedPercent), sampled, nil
}

func (p *hostProbe) failedLogs() (int8, derivation, error) {
	window := config.TrendWindow(p.periods.TrendHours)
	logs := loadLogs(config.Load(p.configPath).Mount())
	count, available := logs.errorsWithin(window)
	if !available {
		return 0, derivedInertf(scribe.ActionSample, "computed [  0] pct failed, kernel log unreadable at [%s] so the metric is inert and always ok", logs.attempted()), nil
	}
	message, leading := logs.leading()
	return stats.ConvertToInt(float64(count) / metric.FailedLogsBudget * 100.0), derivedf(scribe.ActionSample, "computed [%3d] pct failed, errors [%d] of budget [%d] within window [%s], most frequent [%d] of them logged [%s], following [%s]",
		stats.ConvertToInt(float64(count)/metric.FailedLogsBudget*100.0), count, int(metric.FailedLogsBudget), window, leading, message, logs.path), nil
}

func (p *hostProbe) failedShares() (int8, derivation, error) {
	return p.mounts().failedShares()
}

func (p *hostProbe) warnTemperature() (int8, derivation, error) {
	temperatureCelsius, _, err := p.temperature()
	if err != nil {
		return 0, derivation{}, err
	}
	warnOfMax := stats.ConvertToInt(metric.WarnTemperaturePerCelsius * (temperatureCelsius - metric.WarnTemperatureBaseCelsius))
	return warnOfMax, derivedf(scribe.ActionCompute, "computed [%3d] pct of warn, [%.1f] C above floor [%.1f] C at [%.1f] pct/C",
		warnOfMax, temperatureCelsius, metric.WarnTemperatureBaseCelsius, metric.WarnTemperaturePerCelsius), nil
}

func (p *hostProbe) spinFanSpeed() (int8, derivation, error) {
	speedOfMax, sampled, err := loadSensors(p.sysRoot).fanSpeedOfMax()
	if err != nil {
		return 0, derivation{}, err
	}
	return stats.ConvertToInt(speedOfMax), sampled, nil
}

func (p *hostProbe) failedDrives() (int8, derivation, error) {
	return p.mounts().failedDrives()
}

func (p *hostProbe) usedDriveLife() (int8, derivation, error) {
	return p.mounts().usedDriveLife()
}

func (p *hostProbe) usedHomeSpace() (int8, derivation, error) {
	return p.mounts().usedHomeSpace()
}

func (p *hostProbe) usedShareSpace() (int8, derivation, error) {
	return p.mounts().usedShareSpace()
}

func (p *hostProbe) usedSwapSpace() (int8, derivation, error) {
	if p.swapMemory == nil {
		return 0, derivation{}, errors.New("no swap reading taken, the probe was created without a swap memory reader")
	}
	swapStat, err := p.swapMemory()
	if err != nil {
		return 0, derivation{}, fmt.Errorf("no swap reading taken, swap memory stats failed with [%w]", err)
	}
	if swapStat.Total == 0 {
		return 0, derivedInertf(scribe.ActionSample, "computed [  0] pct used, the host configures no swap so the metric is inert and always ok"), nil
	}
	usedPercent := (float64(swapStat.Used) / float64(swapStat.Total)) * 100.0
	return percentValue(usedPercent), derivedf(scribe.ActionCompute, "computed [%3d] pct used, used [%d] MiB of total [%d] MiB, free [%d] MiB",
		percentValue(usedPercent), swapStat.Used/bytesPerMiB, swapStat.Total/bytesPerMiB, swapStat.Free/bytesPerMiB), nil
}

func (p *hostProbe) usedDiskTime() (int8, derivation, error) {
	if p.diskSampler == nil || p.diskCounters == nil {
		return 0, derivation{}, errors.New("no disk operations sample taken, the probe was created without a disk sampler or an io counter reader")
	}
	return p.diskSampler.sample(p.diskCounters)
}

func (p *hostProbe) usedNetwork() (int8, derivation, error) {
	if p.networkSampler == nil {
		return 0, derivation{}, errors.New("no network sample taken, the probe was created without a network sampler")
	}
	roots := []string{networkBareRoot}
	if mount := config.Load(p.configPath).Mount(); mount != "" {
		roots = []string{mount, networkBareRoot}
	}
	return p.networkSampler.sample(roots)
}

func (p *hostProbe) upTime() (float64, derivation, error) {
	if p.hostUptime == nil {
		return 0, derivation{}, errors.New("no up time read, the probe was created without an up time reader")
	}
	seconds, err := p.hostUptime()
	if err != nil {
		return 0, derivation{}, fmt.Errorf("no up time read, host up time failed with [%w] [%w]", err, errEnvironment)
	}
	running := time.Duration(seconds) * time.Second
	return float64(seconds), derivedf(scribe.ActionSample, "computed [%d] s running, the host booted [%s] ago at [%s]",
		seconds, running, config.NowIncludingSuspend().Add(-running).Format(time.RFC3339)), nil
}

func (p *hostProbe) temperature() (float64, derivation, error) {
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
func (s *cpuUsageSampler) sample(cpuTimes func(bool) ([]cpu.TimesStat, error)) (int8, derivation, error) {
	currentTimes, err := cpuTimes(false)
	if err != nil {
		return 0, derivation{}, fmt.Errorf("no processor sample taken, reading cpu times failed with [%w]", err)
	}
	if len(currentTimes) == 0 {
		return 0, derivation{}, errors.New("no processor sample taken, the host returned an empty set of cpu times")
	}
	if !s.hasSample {
		s.lastSample = currentTimes[0]
		s.hasSample = true
		return 0, derivation{}, errProbeWarmingUp
	}
	previousIdleTime := s.lastSample.Idle
	previousTotalTime := s.lastSample.Total()
	currentIdleTime := currentTimes[0].Idle
	currentTotalTime := currentTimes[0].Total()
	idleDelta := currentIdleTime - previousIdleTime
	totalDelta := currentTotalTime - previousTotalTime
	s.lastSample = currentTimes[0]
	if totalDelta <= 0 {
		return 0, derivation{}, fmt.Errorf("no processor sample taken, cpu counters moved by [%.1f] ticks between polls so they are not monotonic", totalDelta)
	}
	usedPercent := (1.0 - idleDelta/totalDelta) * 100.0
	return stats.ConvertToInt(usedPercent), derivedf(scribe.ActionCompute, "computed [%3d] pct used, idle delta [%.1f] of total delta [%.1f] ticks",
		stats.ConvertToInt(usedPercent), idleDelta, totalDelta), nil
}

type diskUsageSampler struct {
	hasSample bool
	taken     time.Time
	samples   map[string]uint64
}

func (s *diskUsageSampler) sample(ioCounters func(...string) (map[string]disk.IOCountersStat, error)) (int8, derivation, error) {
	counters, err := ioCounters()
	if err != nil {
		return 0, derivation{}, fmt.Errorf("no disk operations sample taken, reading device counters failed with [%w] [%w]", err, errEnvironment)
	}
	current := make(map[string]uint64, len(counters))
	for name, counter := range counters {
		for _, device := range diskDevices {
			if strings.HasPrefix(name, device) {
				current[name] = counter.IoTime
				break
			}
		}
	}
	if len(current) == 0 {
		return 0, derivedInertf(scribe.ActionSample, "computed [  0] pct used, none of the [%d] devices the host reports is named [%s] so the metric is inert and always ok", len(counters), strings.Join(diskDevices, "] or [")), nil
	}
	taken := config.NowIncludingSuspend()
	previous, previousTaken, hadSample := s.samples, s.taken, s.hasSample
	s.samples, s.taken, s.hasSample = current, taken, true
	if !hadSample {
		return 0, derivation{}, errProbeWarmingUp
	}
	elapsed := taken.Sub(previousTaken).Seconds()
	if elapsed <= 0 {
		return 0, derivation{}, fmt.Errorf("no disk operations sample taken, [%.3f] seconds elapsed between polls so a share of them cannot be computed", elapsed)
	}
	busiest, busiestPercent, busiestMillis := "", 0.0, 0.0
	for name, now := range current {
		then, had := previous[name]
		if !had || now < then {
			continue
		}
		millis := float64(now - then)
		percent := millis / (elapsed * 1000.0) * 100.0
		if busiest == "" || percent > busiestPercent {
			busiest, busiestPercent, busiestMillis = name, percent, millis
		}
	}
	if busiest == "" {
		return 0, derivation{}, errProbeWarmingUp
	}
	return percentValue(busiestPercent), derivedf(scribe.ActionCompute, "computed [%3d] pct used, busiest [%s] serviced operations for [%.0f] ms of [%.0f] ms elapsed across [%d] devices",
		percentValue(busiestPercent), busiest, busiestMillis, elapsed*1000.0, len(current)), nil
}

type networkLink struct {
	name       string
	statistics string
	ratedBits  float64
}

type networkUsageSampler struct {
	discovered bool
	root       string
	links      []networkLink
	hasSample  bool
	taken      time.Time
	samples    map[string]uint64
}

func (s *networkUsageSampler) sample(roots []string) (int8, derivation, error) {
	s.discover(roots)
	if len(s.links) == 0 {
		return 0, derivedInertf(scribe.ActionSample, "computed [  0] pct used, discovery found no physical interface carrying a rated link speed under [%s] so the metric is inert and always ok", s.root), nil
	}
	current := make(map[string]uint64, len(s.links))
	var rejected []string
	for _, link := range s.links {
		received, receivedErr := networkCounter(filepath.Join(link.statistics, networkReceivedFile))
		transmitted, transmittedErr := networkCounter(filepath.Join(link.statistics, networkTransmittedFile))
		if receivedErr != nil || transmittedErr != nil {
			rejected = append(rejected, fmt.Sprintf("%s unreadable with [%v] and [%v]", link.name, receivedErr, transmittedErr))
			continue
		}
		current[link.name] = received + transmitted
	}
	if len(current) == 0 {
		return 0, derivation{}, fmt.Errorf("no network sample taken, none of the [%d] discovered interfaces under [%s] answered, rejected [%s] [%w]",
			len(s.links), s.root, strings.Join(rejected, ", "), errEnvironment)
	}
	taken := config.NowIncludingSuspend()
	previous, previousTaken, hadSample := s.samples, s.taken, s.hasSample
	s.samples, s.taken, s.hasSample = current, taken, true
	if !hadSample {
		return 0, derivation{}, errProbeWarmingUp
	}
	elapsed := taken.Sub(previousTaken).Seconds()
	if elapsed <= 0 {
		return 0, derivation{}, fmt.Errorf("no network sample taken, [%.3f] seconds elapsed between polls so a rate cannot be computed", elapsed)
	}
	busiest, busiestPercent, busiestBits, busiestRated := "", 0.0, 0.0, 0.0
	for _, link := range s.links {
		now, read := current[link.name]
		then, had := previous[link.name]
		if !read || !had || now < then {
			continue
		}
		bits := float64(now-then) * networkBitsPerByte / elapsed
		percent := bits / link.ratedBits * 100.0
		if busiest == "" || percent > busiestPercent {
			busiest, busiestPercent, busiestBits, busiestRated = link.name, percent, bits, link.ratedBits
		}
	}
	if busiest == "" {
		return 0, derivation{}, errProbeWarmingUp
	}
	return percentValue(busiestPercent), derivedf(scribe.ActionCompute, "computed [%3d] pct used, busiest [%s] moved [%.1f] Mbit per second of its rated [%.0f] Mbit across [%d] interfaces over [%.1f] s",
		percentValue(busiestPercent), busiest, busiestBits/networkBitsPerMbit, busiestRated/networkBitsPerMbit, len(current), elapsed), nil
}

func (s *networkUsageSampler) discover(roots []string) {
	if s.discovered {
		return
	}
	s.discovered = true
	discoverStart := time.Now()
	s.root = strings.Join(roots, ", ")
	for _, root := range roots {
		classDir := filepath.Join(root, networkClassPath)
		entries, err := os.ReadDir(classDir)
		if err != nil {
			continue
		}
		s.root = classDir
		var virtual []string
		for _, entry := range entries {
			name := entry.Name()
			if _, deviceErr := os.Stat(filepath.Join(classDir, name, networkDeviceDir)); deviceErr != nil {
				virtual = append(virtual, name)
				continue
			}
			rated, ratedErr := networkCounter(filepath.Join(classDir, name, networkSpeedFile))
			if ratedErr != nil || rated == 0 {
				virtual = append(virtual, name)
				continue
			}
			s.links = append(s.links, networkLink{
				name:       name,
				statistics: filepath.Join(classDir, name, networkStatisticsDir),
				ratedBits:  float64(rated) * networkBitsPerMbit,
			})
		}
		scribe.Log(scribe.SourceProbeHost, scribe.SubjectMetric(metric.MetricHostUsedNetwork), scribe.ActionDiscover).Infof("topology", discoverStart, "[%d] rated physical interfaces of [%d] under [%s], not rated [%s]",
			len(s.links), len(entries), classDir, strings.Join(virtual, ", "))
		return
	}
	scribe.Log(scribe.SourceProbeHost, scribe.SubjectMetric(metric.MetricHostUsedNetwork), scribe.ActionDiscover).Infof("topology", discoverStart, "[0] rated physical interfaces, no directory under [%s]", s.root)
}

func networkCounter(path string) (uint64, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return 0, err
	}
	value, err := strconv.ParseInt(strings.TrimSpace(string(data)), 10, 64)
	if err != nil {
		return 0, err
	}
	if value < 0 {
		return 0, fmt.Errorf("read [%d] which is not a counter", value)
	}
	return uint64(value), nil
}

const (
	networkBareRoot        = "/"
	networkClassPath       = "sys/class/net"
	networkStatisticsDir   = "statistics"
	networkDeviceDir       = "device"
	networkReceivedFile    = "rx_bytes"
	networkTransmittedFile = "tx_bytes"
	networkSpeedFile       = "speed"
	networkBitsPerByte     = 8.0
	networkBitsPerMbit     = 1000000.0
)

var diskDevices = []string{"sd", "nvme"}
