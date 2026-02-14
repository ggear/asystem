package probe

import (
	"errors"
	"testing"
	"time"

	"github.com/shirou/gopsutil/v4/cpu"
	"github.com/shirou/gopsutil/v4/mem"
)

func TestProbeCompute_UsedProcessor(t *testing.T) {
	tests := []struct {
		name          string
		overrideCpu   func(bool) ([]cpu.TimesStat, error)
		expectInRange bool
		expectError   bool
	}{
		{
			name:          "happy",
			expectInRange: true,
			expectError:   false,
		},
		{
			name:        "sad_cpuTimesStat_error",
			overrideCpu: func(bool) ([]cpu.TimesStat, error) { return nil, errors.New("boom") },
			expectError: true,
		},
		{
			name:        "sad_cpuTimesStat_empty",
			overrideCpu: func(bool) ([]cpu.TimesStat, error) { return []cpu.TimesStat{}, nil },
			expectError: true,
		},
		{
			name: "sad_cpuTimesStat_nonmonotonic_missing",
			overrideCpu: func() func(bool) ([]cpu.TimesStat, error) {
				call := 0
				return func(bool) ([]cpu.TimesStat, error) {
					call++
					return []cpu.TimesStat{{Idle: 5, User: 5}}, nil
				}
			}(),
			expectError: true,
		},
		{
			name: "sad_cpuTimesStat_nonmonotonic",
			overrideCpu: func() func(bool) ([]cpu.TimesStat, error) {
				call := 0
				return func(bool) ([]cpu.TimesStat, error) {
					call++
					if call == 1 {
						return []cpu.TimesStat{{Idle: 30, User: 70}}, nil
					}
					return []cpu.TimesStat{{Idle: 10, User: 20}}, nil
				}
			}(),
			expectError: true,
		},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			compute := NewCompute()
			if testCase.overrideCpu != nil {
				compute.cpuTimes = testCase.overrideCpu
			}
			value, err := compute.UsedProcessor()
			if errors.Is(err, ErrProcessorProbeWarmingUp) {
				time.Sleep(time.Second)
				value, err = compute.UsedProcessor()
			}
			if testCase.expectError && err == nil {
				t.Fatalf("expected error but got nil")
			}
			if !testCase.expectError && err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if !testCase.expectError && testCase.expectInRange && (value < 0 || value > 100) {
				t.Fatalf("CPU value out of range: %d", value)
			}
		})
	}
}
func TestProbeCompute_UsedMemory(t *testing.T) {
	tests := []struct {
		name           string
		overrideMemory func() (*mem.VirtualMemoryStat, error)
		expectInRange  bool
		expectError    bool
	}{
		{
			name:          "happy_path",
			expectInRange: true,
			expectError:   false,
		},
		{
			name:           "virtualMemory_error",
			overrideMemory: func() (*mem.VirtualMemoryStat, error) { return nil, errors.New("boom") },
			expectError:    true,
		},
		{
			name:           "virtualMemory_zero_total",
			overrideMemory: func() (*mem.VirtualMemoryStat, error) { return &mem.VirtualMemoryStat{Total: 0, Available: 0}, nil },
			expectError:    true,
		},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			compute := NewCompute()
			if testCase.overrideMemory != nil {
				compute.virtualMemory = testCase.overrideMemory
			}
			value, err := compute.UsedMemory()
			if testCase.expectError && err == nil {
				t.Fatalf("expected error but got nil")
			}
			if !testCase.expectError && err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if !testCase.expectError && testCase.expectInRange && (value < 0 || value > 100) {
				t.Fatalf("Memory value out of range: %d", value)
			}
		})
	}
}

func TestCompute_AllocatedMemory(t *testing.T) {
	// TODO: Provide implementation
}
