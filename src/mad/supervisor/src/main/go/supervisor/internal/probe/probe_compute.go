package probe

import (
	"errors"
	"fmt"

	"github.com/shirou/gopsutil/v4/cpu"
	"github.com/shirou/gopsutil/v4/mem"
)

type Compute struct {
	cpuSampler    *cpuUsageSampler
	cpuTimes      func(bool) ([]cpu.TimesStat, error)
	virtualMemory func() (*mem.VirtualMemoryStat, error)
}

func NewCompute() *Compute {
	return &Compute{
		cpuSampler:    &cpuUsageSampler{},
		cpuTimes:      cpu.Times,
		virtualMemory: mem.VirtualMemory,
	}
}

func (c *Compute) UsedProcessor() (int8, error) {
	return c.cpuSampler.sample(c.cpuTimes)
}

func (c *Compute) UsedMemory() (int8, error) {
	memoryStat, err := c.virtualMemory()
	if err != nil {
		return 0, fmt.Errorf("virtual memory stats: %w", err)
	}
	if memoryStat.Total == 0 {
		return 0, errors.New("total memory must be > 0")
	}
	usedPercent := (float64(memoryStat.Total-memoryStat.Available) / float64(memoryStat.Total)) * 100.0
	return convertToPercentage(usedPercent)
}

func (c *Compute) AllocatedMemory() (int8, error) {
	// TODO: Provide implementation
	return 0, nil
}

func (c *Compute) Reset() {
	if c.cpuSampler == nil {
		c.cpuSampler = &cpuUsageSampler{}
	} else {
		c.cpuSampler.reset()
	}
	c.cpuTimes = cpu.Times
	c.virtualMemory = mem.VirtualMemory
}

type cpuUsageSampler struct {
	hasSample  bool
	lastSample cpu.TimesStat
}

func (s *cpuUsageSampler) reset() {
	s.hasSample = false
	s.lastSample = cpu.TimesStat{}
}

//goland:noinspection GoDeprecation
func (s *cpuUsageSampler) sample(cpuTimes func(bool) ([]cpu.TimesStat, error)) (int8, error) {
	currentTimes, err := cpuTimes(false)
	if err != nil {
		return 0, fmt.Errorf("cpu times: %w", err)
	}
	if len(currentTimes) == 0 {
		return 0, errors.New("failed to get processor usage")
	}
	if !s.hasSample {
		s.lastSample = currentTimes[0]
		s.hasSample = true
		return 0, ErrProcessorProbeWarmingUp
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
	return convertToPercentage(usedPercent)
}
