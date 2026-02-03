package probe

import (
	"errors"
	"strings"
	"testing"
	"time"

	"github.com/shirou/gopsutil/v4/cpu"
	"github.com/shirou/gopsutil/v4/mem"
)

func TestCompute_UsedProcessor(t *testing.T) {
	tests := []struct {
		name string
		run  func(t *testing.T)
	}{
		{
			name: "basic",
			run: func(t *testing.T) {
				compute := NewCompute()
				_, err := compute.UsedProcessor()
				if err == nil {
					t.Fatalf("Got err = nil, expected error")
				}
				var lastErr error
				for attempt := 0; attempt < 20; attempt++ {
					time.Sleep(50 * time.Millisecond)
					value, err := compute.UsedProcessor()
					if err != nil {
						lastErr = err
						continue
					}
					if value < 0 || value > 100 {
						t.Fatalf("Got value = %d, expected between 0 and 100", value)
					}
					return
				}
				t.Fatalf("Got err = %v, expected nil", lastErr)
			},
		},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			testCase.run(t)
		})
	}
}

func TestCompute_UsedMemory(t *testing.T) {
	tests := []struct {
		name string
		run  func(t *testing.T)
	}{
		{
			name: "basic",
			run: func(t *testing.T) {
				compute := NewCompute()
				value, err := compute.UsedMemory()
				if err != nil {
					t.Fatalf("Got err = %v, expected nil", err)
				}
				if value < 0 || value > 100 {
					t.Fatalf("Got value = %d, expected between 0 and 100", value)
				}
			},
		},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			testCase.run(t)
		})
	}
}

func TestCompute_UsedMemoryErrors(t *testing.T) {
	tests := []struct {
		name string
		run  func(t *testing.T, compute *Compute)
	}{
		{
			name: "virtualMemory error",
			run: func(t *testing.T, compute *Compute) {
				compute.virtualMemory = func() (*mem.VirtualMemoryStat, error) {
					return nil, errors.New("boom")
				}
				_, err := compute.UsedMemory()
				if err == nil {
					t.Fatalf("Got err = nil, expected error")
				}
			},
		},
		{
			name: "zero total",
			run: func(t *testing.T, compute *Compute) {
				compute.virtualMemory = func() (*mem.VirtualMemoryStat, error) {
					return &mem.VirtualMemoryStat{Total: 0, Available: 0}, nil
				}
				_, err := compute.UsedMemory()
				if err == nil {
					t.Fatalf("Got err = nil, expected error")
				}
			},
		},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			compute := NewCompute()
			testCase.run(t, compute)
		})
	}
}

func TestCompute_CpuUsageSamplerErrors(t *testing.T) {
	tests := []struct {
		name string
		run  func(t *testing.T, compute *Compute)
	}{
		{
			name: "cpuTimes error",
			run: func(t *testing.T, compute *Compute) {
				compute.cpuTimes = func(bool) ([]cpu.TimesStat, error) {
					return nil, errors.New("boom")
				}
				_, err := compute.UsedProcessor()
				if err == nil {
					t.Fatalf("Got err = nil, expected error")
				}
			},
		},
		{
			name: "empty sample",
			run: func(t *testing.T, compute *Compute) {
				compute.cpuTimes = func(bool) ([]cpu.TimesStat, error) {
					return []cpu.TimesStat{}, nil
				}
				_, err := compute.UsedProcessor()
				if err == nil {
					t.Fatalf("Got err = nil, expected error")
				}
			},
		},
		{
			name: "clock sync issue",
			run: func(t *testing.T, compute *Compute) {
				callCount := 0
				compute.cpuTimes = func(bool) ([]cpu.TimesStat, error) {
					callCount++
					switch callCount {
					case 1:
						return []cpu.TimesStat{{Idle: 5, User: 5}}, nil
					default:
						return []cpu.TimesStat{{Idle: 5, User: 5}}, nil
					}
				}
				_, err := compute.UsedProcessor()
				if err == nil {
					t.Fatalf("Got err = nil, expected error")
				}
				_, err = compute.UsedProcessor()
				if err == nil {
					t.Fatalf("Got err = nil, expected error")
				}
			},
		},
		{
			name: "clock sync issue with decreasing total",
			run: func(t *testing.T, compute *Compute) {
				callCount := 0
				compute.cpuTimes = func(bool) ([]cpu.TimesStat, error) {
					callCount++
					switch callCount {
					case 1:
						return []cpu.TimesStat{{Idle: 30, User: 70}}, nil
					default:
						return []cpu.TimesStat{{Idle: 10, User: 20}}, nil
					}
				}
				_, err := compute.UsedProcessor()
				if err == nil {
					t.Fatalf("Got err = nil, expected error")
				}
				_, err = compute.UsedProcessor()
				if err == nil {
					t.Fatalf("Got err = nil, expected error")
				}
				if !strings.Contains(err.Error(), "non-monotonic counters") {
					t.Fatalf("Got err = %v, expected non-monotonic counters issue", err)
				}
			},
		},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			compute := NewCompute()
			testCase.run(t, compute)
		})
	}
}
