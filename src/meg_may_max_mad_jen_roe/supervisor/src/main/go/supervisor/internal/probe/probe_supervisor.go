package probe

import (
	"context"
	"errors"
	"fmt"
	"math"
	"os"
	"runtime"
	"runtime/debug"
	"supervisor/internal/config"
	"supervisor/internal/metric"
	"supervisor/internal/stats"
	"time"

	"github.com/shirou/gopsutil/v4/cpu"
	"github.com/shirou/gopsutil/v4/process"
)

type supervisorProbe struct {
	cache   *metric.RecordCache
	mask    [metric.MetricMax]bool
	periods config.Periods

	supervisorBool   *stats.BoolStats
	versionString    *stats.StringStats
	usedProcessorInt *stats.IntStats
	usedMemoryInt    *stats.IntStats
	runningTimeFloat *stats.FloatStats
	maxMemoryFloat   *stats.FloatStats
	metricRateFloat  *stats.FloatStats

	cpuSampler     *processCPUUsageSampler
	processInfo    processInfo
	newProcess     func(int32) (processInfo, error)
	procTimes      func() (*cpu.TimesStat, error)
	procMemory     func() (*process.MemoryInfoStat, error)
	procCreateTime func() (int64, error)
	setMemoryLimit func(int64) int64
	now            func() time.Time
}

func newSupervisorProbe() *supervisorProbe {
	return &supervisorProbe{
		cpuSampler: &processCPUUsageSampler{},
		newProcess: newProcessInfo,
		setMemoryLimit: func(limit int64) int64 {
			return debug.SetMemoryLimit(limit)
		},
		now: time.Now,
	}
}

func (*supervisorProbe) name() string { return "supervisor" }

func (*supervisorProbe) metrics() []metric.ID {
	return []metric.ID{
		metric.MetricSupervisor,
		metric.MetricSupervisorVersion,
		metric.MetricSupervisorUsedProcessor,
		metric.MetricSupervisorUsedMemory,
		metric.MetricSupervisorRunningTime,
		metric.MetricSupervisorMaxMemory,
		metric.MetricSupervisorMetricRate,
	}
}

func (p *supervisorProbe) create(_ string, cache *metric.RecordCache, mask [metric.MetricMax]bool, periods config.Periods) error {
	p.cache = cache
	p.mask = mask
	p.periods = periods

	p.supervisorBool = stats.NewBoolStats(periods.TrendHours, float64(periods.PulseMillis)/1000.0, float64(periods.PollMillis)/1000.0)
	p.versionString = stats.NewStringStats(periods.TrendHours, float64(periods.PulseMillis)/1000.0, float64(periods.PollMillis)/1000.0)
	p.usedProcessorInt = stats.NewIntStats(periods.TrendHours, float64(periods.PulseMillis)/1000.0, float64(periods.PollMillis)/1000.0)
	p.usedMemoryInt = stats.NewIntStats(periods.TrendHours, float64(periods.PulseMillis)/1000.0, float64(periods.PollMillis)/1000.0)
	p.runningTimeFloat = stats.NewFloatStats(periods.TrendHours, float64(periods.PulseMillis)/1000.0, float64(periods.PollMillis)/1000.0)
	p.maxMemoryFloat = stats.NewFloatStats(periods.TrendHours, float64(periods.PulseMillis)/1000.0, float64(periods.PollMillis)/1000.0)
	p.metricRateFloat = stats.NewFloatStats(periods.TrendHours, float64(periods.PulseMillis)/1000.0, float64(periods.PollMillis)/1000.0)

	proc, err := p.newProcess(int32(os.Getpid()))
	if err != nil {
		return fmt.Errorf("create supervisor process handle: %w", err)
	}
	p.processInfo = proc
	p.procTimes = func() (*cpu.TimesStat, error) {
		if p.processInfo == nil {
			return nil, errors.New("process info unavailable")
		}
		return p.processInfo.Times()
	}
	p.procMemory = func() (*process.MemoryInfoStat, error) {
		if p.processInfo == nil {
			return nil, errors.New("process info unavailable")
		}
		return p.processInfo.MemoryInfo()
	}
	p.procCreateTime = func() (int64, error) {
		if p.processInfo == nil {
			return 0, errors.New("process info unavailable")
		}
		return p.processInfo.CreateTime()
	}
	return nil
}

func (p *supervisorProbe) run(_ context.Context, isPulse bool) error {
	runMetricCacheTasks(p, isPulse, []cacheMetricTask{
		newCacheMetricTask(
			metric.ValueBool,
			metric.MetricSupervisor,
			metric.ServiceNameUnset,
			p.supervisor,
			p.supervisorBool,
			func() bool { return p.supervisorBool.PulseLast() },
			func() bool { return p.supervisorBool.TrendMean() },
			func(bool) bool { return true },
			func(bool) bool { return true },
		),
		newCacheMetricTask(
			metric.ValueString,
			metric.MetricSupervisorVersion,
			metric.ServiceNameUnset,
			p.version,
			p.versionString,
			func() string { return p.versionString.PulseLast() },
			nil,
			func(string) bool { return true },
			nil,
		),
		newCacheMetricTask(
			metric.ValueInt,
			metric.MetricSupervisorUsedProcessor,
			metric.ServiceNameUnset,
			p.usedProcessor,
			p.usedProcessorInt,
			func() int8 { return p.usedProcessorInt.PulseMax() },
			func() int8 { return p.usedProcessorInt.TrendP95() },
			func(v int8) bool { return v <= 90 },
			func(v int8) bool { return v <= 70 },
		),
		newCacheMetricTask(
			metric.ValueInt,
			metric.MetricSupervisorUsedMemory,
			metric.ServiceNameUnset,
			p.usedMemory,
			p.usedMemoryInt,
			func() int8 { return p.usedMemoryInt.PulseMax() },
			func() int8 { return p.usedMemoryInt.TrendMax() },
			func(v int8) bool { return v <= 95 },
			func(v int8) bool { return v <= 90 },
		),
		newCacheMetricTask(
			metric.ValueFloat,
			metric.MetricSupervisorRunningTime,
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
			metric.MetricSupervisorMaxMemory,
			metric.ServiceNameUnset,
			p.maxMemory,
			p.maxMemoryFloat,
			func() float64 { return p.maxMemoryFloat.PulseLast() },
			nil,
			func(float64) bool { return true },
			nil,
		),
		newCacheMetricTask(
			metric.ValueFloat,
			metric.MetricSupervisorMetricRate,
			metric.ServiceNameUnset,
			p.metricRate,
			p.metricRateFloat,
			func() float64 { return p.metricRateFloat.PulseLast() },
			func() float64 { return p.metricRateFloat.TrendMax() },
			func(float64) bool { return true },
			func(float64) bool { return true },
		),
	})
	return nil
}

func (p *supervisorProbe) records() *metric.RecordCache {
	return p.cache
}

func (p *supervisorProbe) hasMetric(id metric.ID) bool {
	return p.mask[id]
}

func (p *supervisorProbe) supervisor() (bool, error) {
	return true, nil
}

func (p *supervisorProbe) version() (string, error) {
	return "", nil
}

func (p *supervisorProbe) usedProcessor() (int8, error) {
	if p.cpuSampler == nil || p.procTimes == nil {
		return 0, errors.New("cpu sampler not initialized")
	}
	return p.cpuSampler.sample(p.procTimes, p.now)
}

func (p *supervisorProbe) usedMemory() (int8, error) {
	if p.procMemory == nil {
		return 0, errors.New("process memory unavailable")
	}
	processMemory, err := p.procMemory()
	if err != nil {
		return 0, fmt.Errorf("process memory stats: %w", err)
	}
	limit, err := p.maxMemory()
	if err != nil {
		return 0, fmt.Errorf("process memory limit: %w", err)
	}
	usedPercent := (float64(processMemory.RSS) / limit) * 100.0
	return stats.ConvertToInt(usedPercent), nil
}

func (p *supervisorProbe) runningTime() (float64, error) {
	if p.procCreateTime == nil {
		return 0, errors.New("process start time unavailable")
	}
	createdAtMillis, err := p.procCreateTime()
	if err != nil {
		return 0, fmt.Errorf("process start time: %w", err)
	}
	startedAt := time.UnixMilli(createdAtMillis)
	running := p.now().Sub(startedAt)
	if running < 0 {
		return 0, errors.New("running time not available")
	}
	return running.Seconds(), nil
}

func (p *supervisorProbe) maxMemory() (float64, error) {
	if p.setMemoryLimit == nil {
		return 0, errors.New("memory limit resolver unavailable")
	}
	limit := p.setMemoryLimit(-1)
	if limit > 0 && limit != math.MaxInt64 {
		return float64(limit), nil
	}
	return 256 * 1024 * 1024, nil
}

func (p *supervisorProbe) metricRate() (float64, error) {
	if p.cache == nil {
		return 0, errors.New("cache unavailable")
	}
	return 0, nil
}

type processInfo interface {
	Times() (*cpu.TimesStat, error)
	MemoryInfo() (*process.MemoryInfoStat, error)
	CreateTime() (int64, error)
}

func newProcessInfo(pid int32) (processInfo, error) {
	return process.NewProcess(pid)
}

type processCPUUsageSampler struct {
	hasSample bool
	lastTotal float64
	lastTime  time.Time
}

//goland:noinspection GoDeprecation
func (s *processCPUUsageSampler) sample(procTimes func() (*cpu.TimesStat, error), now func() time.Time) (int8, error) {
	if procTimes == nil {
		return 0, errors.New("process times unavailable")
	}
	currentTimes, err := procTimes()
	if err != nil {
		return 0, fmt.Errorf("process cpu times: %w", err)
	}
	if currentTimes == nil {
		return 0, errors.New("process cpu times unavailable")
	}
	currentTotal := currentTimes.Total()
	currentTime := now()
	if !s.hasSample {
		s.hasSample = true
		s.lastTotal = currentTotal
		s.lastTime = currentTime
		return 0, errProbeWarmingUp
	}
	elapsed := currentTime.Sub(s.lastTime).Seconds()
	if elapsed <= 0 {
		return 0, errors.New("cpu usage unavailable, non-monotonic clock")
	}
	totalDelta := currentTotal - s.lastTotal
	s.lastTotal = currentTotal
	s.lastTime = currentTime
	if totalDelta < 0 {
		return 0, errors.New("cpu usage unavailable, non-monotonic counters")
	}
	usedPercent := (totalDelta / elapsed) * 100.0 / float64(runtime.NumCPU())
	return stats.ConvertToInt(usedPercent), nil
}
