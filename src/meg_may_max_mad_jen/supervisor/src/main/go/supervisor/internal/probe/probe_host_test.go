package probe

import (
	"errors"
	"testing"
	"time"

	"github.com/shirou/gopsutil/v4/cpu"
	"github.com/shirou/gopsutil/v4/mem"
	"github.com/shirou/gopsutil/v4/sensors"
)

func TestProbeHost_UsedProcessor(t *testing.T) {
	tests := []struct {
		name          string
		overrideCpu   func(bool) ([]cpu.TimesStat, error)
		expectInRange bool
		expectedError bool
	}{
		{
			name:          "happy",
			expectInRange: true,
			expectedError: false,
		},
		{
			name:          "sad_cpuTimesStat_error",
			overrideCpu:   func(bool) ([]cpu.TimesStat, error) { return nil, errors.New("boom") },
			expectInRange: false,
			expectedError: true,
		},
		{
			name:          "sad_cpuTimesStat_empty",
			overrideCpu:   func(bool) ([]cpu.TimesStat, error) { return []cpu.TimesStat{}, nil },
			expectInRange: false,
			expectedError: true,
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
			expectInRange: false,
			expectedError: true,
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
			expectedError: true,
		},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			probe := newHostProbe()
			if testCase.overrideCpu != nil {
				probe.cpuTimes = testCase.overrideCpu
			}
			value, err := probe.usedProcessor()
			if errors.Is(err, errProbeWarmingUp) {
				time.Sleep(time.Second)
				value, err = probe.usedProcessor()
			}
			if testCase.expectedError && err == nil {
				t.Fatalf("expected error but got nil")
			}
			if !testCase.expectedError && err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if !testCase.expectedError && testCase.expectInRange && (value < 0 || value > 100) {
				t.Fatalf("CPU value out of range: %d", value)
			}
		})
	}
}

func TestProbeHost_UsedMemory(t *testing.T) {
	tests := []struct {
		name           string
		overrideMemory func() (*mem.VirtualMemoryStat, error)
		expectInRange  bool
		expectedError  bool
	}{
		{
			name:          "happy",
			expectInRange: true,
			expectedError: false,
		},
		{
			name:           "sad_virtualMemory_error",
			overrideMemory: func() (*mem.VirtualMemoryStat, error) { return nil, errors.New("boom") },
			expectInRange:  false,
			expectedError:  true,
		},
		{
			name:           "sad_virtualMemory_zero_total",
			overrideMemory: func() (*mem.VirtualMemoryStat, error) { return &mem.VirtualMemoryStat{Total: 0, Available: 0}, nil },
			expectInRange:  false,
			expectedError:  true,
		},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			probe := newHostProbe()
			if testCase.overrideMemory != nil {
				probe.virtualMemory = testCase.overrideMemory
			}
			value, err := probe.usedMemory()
			if testCase.expectedError && err == nil {
				t.Fatalf("expected error but got nil")
			}
			if !testCase.expectedError && err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if !testCase.expectedError && testCase.expectInRange && (value < 0 || value > 100) {
				t.Fatalf("Memory value out of range: %d", value)
			}
		})
	}
}

func TestProbeHost_Temperature(t *testing.T) {
	tests := []struct {
		name          string
		sensors       []sensors.TemperatureStat
		sensorsErr    error
		expectedMin   float64
		expectedMax   float64
		expectedError bool
	}{
		{
			name:          "sad_sensor_error",
			sensorsErr:    errors.New("boom"),
			expectedError: true,
		},
		{
			name: "happy_package",
			sensors: []sensors.TemperatureStat{
				{SensorKey: "package_id_0", Temperature: 55.0},
			},
			expectedMin:   55.0,
			expectedMax:   55.0,
			expectedError: false,
		},
		{
			name: "happy_composite_adjusted",
			sensors: []sensors.TemperatureStat{
				{SensorKey: "Composite", Temperature: 31.9},
			},
			expectedMin:   41.9,
			expectedMax:   41.9,
			expectedError: false,
		},
		{
			name: "happy_choose_max_package_over_composite",
			sensors: []sensors.TemperatureStat{
				{SensorKey: "package", Temperature: 60.0},
				{SensorKey: "composite", Temperature: 45.0},
			},
			expectedMin:   60.0,
			expectedMax:   60.0,
			expectedError: false,
		},
		{
			name: "sad_out_of_bounds",
			sensors: []sensors.TemperatureStat{
				{SensorKey: "package", Temperature: 5.0},
				{SensorKey: "composite", Temperature: 200.0},
			},
			expectedError: true,
		},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			probe := newHostProbe()
			probe.sensorsTemps = func() ([]sensors.TemperatureStat, error) {
				return testCase.sensors, testCase.sensorsErr
			}
			value, err := probe.temperature()
			if testCase.expectedError {
				if err == nil {
					t.Fatalf("expected error but got nil")
				}
				return
			}
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if value < testCase.expectedMin || value > testCase.expectedMax {
				t.Fatalf("temperature out of range: %f", value)
			}
		})
	}
}

func TestProbeHost_Host(t *testing.T) {
	tests := []struct {
		name          string
		expectedValue bool
		expectedOK    bool
		expectedError bool
	}{
		{
			name:          "happy",
			expectedValue: true,
			expectedOK:    true,
			expectedError: false,
		},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			probe := newHostProbe()
			value, err := probe.host()
			if testCase.expectedError && err == nil {
				t.Fatalf("expected error but got nil")
			}
			if !testCase.expectedError && err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if testCase.expectedOK && value != testCase.expectedValue {
				t.Fatalf("expected %v, got %v", testCase.expectedValue, value)
			}
		})
	}
}

func TestProbeHost_AllocatedMemory(t *testing.T) {
	tests := []struct {
		name          string
		expectedValue int8
		expectedOK    bool
		expectedError bool
	}{
		{
			name:          "happy",
			expectedValue: 0,
			expectedOK:    true,
			expectedError: false,
		},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			probe := newHostProbe()
			value, err := probe.allocatedMemory()
			if testCase.expectedError && err == nil {
				t.Fatalf("expected error but got nil")
			}
			if !testCase.expectedError && err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if testCase.expectedOK && value != testCase.expectedValue {
				t.Fatalf("expected %d, got %d", testCase.expectedValue, value)
			}
		})
	}
}

func TestProbeHost_FailedServices(t *testing.T) {
	tests := []struct {
		name          string
		expectedValue int8
		expectedOK    bool
		expectedError bool
	}{
		{
			name:          "happy",
			expectedValue: 0,
			expectedOK:    true,
			expectedError: false,
		},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			probe := newHostProbe()
			value, err := probe.failedServices()
			if testCase.expectedError && err == nil {
				t.Fatalf("expected error but got nil")
			}
			if !testCase.expectedError && err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if testCase.expectedOK && value != testCase.expectedValue {
				t.Fatalf("expected %d, got %d", testCase.expectedValue, value)
			}
		})
	}
}

func TestProbeHost_FailedShares(t *testing.T) {
	tests := []struct {
		name          string
		expectedValue int8
		expectedOK    bool
		expectedError bool
	}{
		{
			name:          "happy",
			expectedValue: 0,
			expectedOK:    true,
			expectedError: false,
		},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			probe := newHostProbe()
			value, err := probe.failedShares()
			if testCase.expectedError && err == nil {
				t.Fatalf("expected error but got nil")
			}
			if !testCase.expectedError && err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if testCase.expectedOK && value != testCase.expectedValue {
				t.Fatalf("expected %d, got %d", testCase.expectedValue, value)
			}
		})
	}
}

func TestProbeHost_FailedBackups(t *testing.T) {
	tests := []struct {
		name          string
		expectedValue int8
		expectedOK    bool
		expectedError bool
	}{
		{
			name:          "happy",
			expectedValue: 0,
			expectedOK:    true,
			expectedError: false,
		},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			probe := newHostProbe()
			value, err := probe.failedBackups()
			if testCase.expectedError && err == nil {
				t.Fatalf("expected error but got nil")
			}
			if !testCase.expectedError && err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if testCase.expectedOK && value != testCase.expectedValue {
				t.Fatalf("expected %d, got %d", testCase.expectedValue, value)
			}
		})
	}
}

func TestProbeHost_WarnTemperature(t *testing.T) {
	tests := []struct {
		name          string
		expectedValue int8
		expectedOK    bool
		expectedError bool
	}{
		{
			name:          "happy",
			expectedValue: 0,
			expectedOK:    true,
			expectedError: false,
		},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			probe := newHostProbe()
			value, err := probe.warnTemperature()
			if testCase.expectedError && err == nil {
				t.Fatalf("expected error but got nil")
			}
			if !testCase.expectedError && err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if testCase.expectedOK && value != testCase.expectedValue {
				t.Fatalf("expected %d, got %d", testCase.expectedValue, value)
			}
		})
	}
}

func TestProbeHost_SpinFanSpeed(t *testing.T) {
	tests := []struct {
		name          string
		expectedValue int8
		expectedOK    bool
		expectedError bool
	}{
		{
			name:          "happy",
			expectedValue: 0,
			expectedOK:    true,
			expectedError: false,
		},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			probe := newHostProbe()
			value, err := probe.spinFanSpeed()
			if testCase.expectedError && err == nil {
				t.Fatalf("expected error but got nil")
			}
			if !testCase.expectedError && err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if testCase.expectedOK && value != testCase.expectedValue {
				t.Fatalf("expected %d, got %d", testCase.expectedValue, value)
			}
		})
	}
}

func TestProbeHost_LifeUsedDrives(t *testing.T) {
	tests := []struct {
		name          string
		expectedValue int8
		expectedOK    bool
		expectedError bool
	}{
		{
			name:          "happy",
			expectedValue: 0,
			expectedOK:    true,
			expectedError: false,
		},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			probe := newHostProbe()
			value, err := probe.lifeUsedDrives()
			if testCase.expectedError && err == nil {
				t.Fatalf("expected error but got nil")
			}
			if !testCase.expectedError && err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if testCase.expectedOK && value != testCase.expectedValue {
				t.Fatalf("expected %d, got %d", testCase.expectedValue, value)
			}
		})
	}
}

func TestProbeHost_UsedSystemSpace(t *testing.T) {
	tests := []struct {
		name          string
		expectedValue int8
		expectedOK    bool
		expectedError bool
	}{
		{
			name:          "happy",
			expectedValue: 0,
			expectedOK:    true,
			expectedError: false,
		},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			probe := newHostProbe()
			value, err := probe.usedSystemSpace()
			if testCase.expectedError && err == nil {
				t.Fatalf("expected error but got nil")
			}
			if !testCase.expectedError && err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if testCase.expectedOK && value != testCase.expectedValue {
				t.Fatalf("expected %d, got %d", testCase.expectedValue, value)
			}
		})
	}
}

func TestProbeHost_UsedShareSpace(t *testing.T) {
	tests := []struct {
		name          string
		expectedValue int8
		expectedOK    bool
		expectedError bool
	}{
		{
			name:          "happy",
			expectedValue: 0,
			expectedOK:    true,
			expectedError: false,
		},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			probe := newHostProbe()
			value, err := probe.usedShareSpace()
			if testCase.expectedError && err == nil {
				t.Fatalf("expected error but got nil")
			}
			if !testCase.expectedError && err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if testCase.expectedOK && value != testCase.expectedValue {
				t.Fatalf("expected %d, got %d", testCase.expectedValue, value)
			}
		})
	}
}

func TestProbeHost_UsedBackupSpace(t *testing.T) {
	tests := []struct {
		name          string
		expectedValue int8
		expectedOK    bool
		expectedError bool
	}{
		{
			name:          "happy",
			expectedValue: 0,
			expectedOK:    true,
			expectedError: false,
		},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			probe := newHostProbe()
			value, err := probe.usedBackupSpace()
			if testCase.expectedError && err == nil {
				t.Fatalf("expected error but got nil")
			}
			if !testCase.expectedError && err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if testCase.expectedOK && value != testCase.expectedValue {
				t.Fatalf("expected %d, got %d", testCase.expectedValue, value)
			}
		})
	}
}

func TestProbeHost_UsedSwapSpace(t *testing.T) {
	tests := []struct {
		name          string
		expectedValue int8
		expectedOK    bool
		expectedError bool
	}{
		{
			name:          "happy",
			expectedValue: 0,
			expectedOK:    true,
			expectedError: false,
		},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			probe := newHostProbe()
			value, err := probe.usedSwapSpace()
			if testCase.expectedError && err == nil {
				t.Fatalf("expected error but got nil")
			}
			if !testCase.expectedError && err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if testCase.expectedOK && value != testCase.expectedValue {
				t.Fatalf("expected %d, got %d", testCase.expectedValue, value)
			}
		})
	}
}

func TestProbeHost_UsedDiskOps(t *testing.T) {
	tests := []struct {
		name          string
		expectedValue int8
		expectedOK    bool
		expectedError bool
	}{
		{
			name:          "happy",
			expectedValue: 0,
			expectedOK:    true,
			expectedError: false,
		},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			probe := newHostProbe()
			value, err := probe.usedDiskOps()
			if testCase.expectedError && err == nil {
				t.Fatalf("expected error but got nil")
			}
			if !testCase.expectedError && err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if testCase.expectedOK && value != testCase.expectedValue {
				t.Fatalf("expected %d, got %d", testCase.expectedValue, value)
			}
		})
	}
}

func TestProbeHost_UsedNetwork(t *testing.T) {
	tests := []struct {
		name          string
		expectedValue int8
		expectedOK    bool
		expectedError bool
	}{
		{
			name:          "happy",
			expectedValue: 0,
			expectedOK:    true,
			expectedError: false,
		},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			probe := newHostProbe()
			value, err := probe.usedNetwork()
			if testCase.expectedError && err == nil {
				t.Fatalf("expected error but got nil")
			}
			if !testCase.expectedError && err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if testCase.expectedOK && value != testCase.expectedValue {
				t.Fatalf("expected %d, got %d", testCase.expectedValue, value)
			}
		})
	}
}

func TestProbeHost_RunningTime(t *testing.T) {
	tests := []struct {
		name          string
		expectedValue float64
		expectedOK    bool
		expectedError bool
	}{
		{
			name:          "happy",
			expectedValue: 0,
			expectedOK:    true,
			expectedError: false,
		},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			probe := newHostProbe()
			value, err := probe.runningTime()
			if testCase.expectedError && err == nil {
				t.Fatalf("expected error but got nil")
			}
			if !testCase.expectedError && err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if testCase.expectedOK && value != testCase.expectedValue {
				t.Fatalf("expected %f, got %f", testCase.expectedValue, value)
			}
		})
	}
}
