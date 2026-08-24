package probe

import (
	"errors"
	"math"
	"os"
	"path/filepath"
	"strings"
	"supervisor/internal/config"
	"testing"
	"time"

	"github.com/shirou/gopsutil/v4/cpu"
	"github.com/shirou/gopsutil/v4/mem"
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
		temps         map[string]float64
		zones         map[string]float64
		expected      float64
		expectedError bool
	}{
		{
			name:          "sad_no_sensors",
			expectedError: true,
		},
		{
			name:          "happy_package",
			temps:         map[string]float64{"package id 0": 55.0},
			expected:      55.0,
			expectedError: false,
		},
		{
			name:          "happy_composite_adjusted",
			temps:         map[string]float64{"Composite": 31.9},
			expected:      41.9,
			expectedError: false,
		},
		{
			name:          "happy_choose_package_over_composite",
			temps:         map[string]float64{"package id 0": 60.0, "Composite": 45.0},
			expected:      60.0,
			expectedError: false,
		},
		{
			name:          "happy_choose_package_over_soc",
			temps:         map[string]float64{"cpu_thermal": 70.0, "package id 0": 55.0},
			expected:      55.0,
			expectedError: false,
		},
		{
			name:          "happy_choose_soc_over_composite",
			temps:         map[string]float64{"Composite": 31.9, "soc_thermal": 44.0},
			expected:      44.0,
			expectedError: false,
		},
		{
			name:          "happy_hottest_of_tier",
			temps:         map[string]float64{"package id 0": 55.0, "package id 1": 61.0},
			expected:      61.0,
			expectedError: false,
		},
		{
			name:          "happy_soc_hwmon_raspberry_pi",
			temps:         map[string]float64{"cpu_thermal": 50.4},
			expected:      50.4,
			expectedError: false,
		},
		{
			name:          "happy_soc_hyphenated",
			temps:         map[string]float64{"cpu-thermal": 47.0},
			expected:      47.0,
			expectedError: false,
		},
		{
			name:          "happy_thermal_zone_fallback",
			zones:         map[string]float64{"cpu-thermal": 49.4},
			expected:      49.4,
			expectedError: false,
		},
		{
			name:          "sad_out_of_bounds_readings_rejected",
			temps:         map[string]float64{"package id 0": 5.0},
			expectedError: true,
		},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			t.Cleanup(resetSensors)
			probe := newHostProbe()
			probe.sysRoot = writeSensorTree(t, testCase.temps, testCase.zones, nil)
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
			if math.Abs(value-testCase.expected) > 0.05 {
				t.Fatalf("temperature: got %f want %f", value, testCase.expected)
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
		services      map[string]string
		configured    []string
		totalBytes    uint64
		memoryError   bool
		expectedValue int8
		expectedError bool
	}{
		{
			name:          "happy_half_of_total_allocated",
			services:      map[string]string{"one": "256M", "two": "256M"},
			totalBytes:    1024 << 20,
			expectedValue: 50,
			expectedError: false,
		},
		{
			name:          "sad_no_configured_services_installed",
			services:      map[string]string{"one": "256M"},
			configured:    []string{"absent"},
			totalBytes:    1024 << 20,
			expectedValue: 0,
			expectedError: true,
		},
		{
			name:          "sad_no_services_configured_for_host",
			services:      map[string]string{"one": "256M"},
			configured:    []string{},
			totalBytes:    1024 << 20,
			expectedValue: 0,
			expectedError: true,
		},
		{
			name:          "happy_stale_install_not_configured_excluded",
			services:      map[string]string{"one": "512M", "stale": "512M"},
			configured:    []string{"one"},
			totalBytes:    1024 << 20,
			expectedValue: 50,
			expectedError: false,
		},
		{
			name:          "happy_undeclared_limit_excluded",
			services:      map[string]string{"one": "512M", "two": ""},
			totalBytes:    1024 << 20,
			expectedValue: 50,
			expectedError: false,
		},
		{
			name:          "happy_over_allocated_capped_at_hundred",
			services:      map[string]string{"one": "2G", "two": "2G"},
			totalBytes:    1024 << 20,
			expectedValue: 100,
			expectedError: false,
		},
		{
			name:          "sad_virtual_memory_fails",
			services:      map[string]string{"one": "256M"},
			totalBytes:    1024 << 20,
			memoryError:   true,
			expectedValue: 0,
			expectedError: true,
		},
		{
			name:          "sad_total_memory_zero",
			services:      map[string]string{"one": "256M"},
			totalBytes:    0,
			expectedValue: 0,
			expectedError: true,
		},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			t.Cleanup(config.Reset)
			t.Cleanup(resetInstallTrees)
			mount := t.TempDir()
			for name, limit := range testCase.services {
				home := filepath.Join(mount, "var/lib/asystem/install", name, "latest")
				if err := os.MkdirAll(home, 0o755); err != nil {
					t.Fatalf("mkdir %s failed: %v", home, err)
				}
				compose := "services:\n  " + name + ":\n    container_name: " + name + "\n"
				if limit != "" {
					compose += "    deploy:\n      resources:\n        limits:\n          memory: " + limit + "\n"
				}
				if err := os.WriteFile(filepath.Join(home, "docker-compose.yml"), []byte(compose), 0o644); err != nil {
					t.Fatalf("write docker-compose.yml failed: %v", err)
				}
			}
			t.Setenv("SUPERVISOR_MOUNT", mount)
			config.Reset()
			resetInstallTrees()
			configured := make([]string, 0, len(testCase.services))
			names := testCase.configured
			if testCase.configured == nil {
				for name := range testCase.services {
					names = append(names, name)
				}
			}
			for _, name := range names {
				configured = append(configured, `"`+name+`"`)
			}
			configPath := filepath.Join(t.TempDir(), "config.json")
			configJSON := `{"asystem":{"host":"testhost","schema":[{"host":"testhost","services":[` + strings.Join(configured, ",") + `]}]}}`
			if err := os.WriteFile(configPath, []byte(configJSON), 0o644); err != nil {
				t.Fatalf("write config.json failed: %v", err)
			}
			probe := newHostProbe()
			probe.configPath = configPath
			probe.hostName = config.Load(configPath).Host()
			probe.virtualMemory = func() (*mem.VirtualMemoryStat, error) {
				if testCase.memoryError {
					return nil, errors.New("expected error during unit test")
				}
				return &mem.VirtualMemoryStat{Total: testCase.totalBytes}, nil
			}
			value, err := probe.allocatedMemory()
			if testCase.expectedError {
				if err == nil {
					t.Fatalf("expected error but got nil")
				}
				return
			}
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if value != testCase.expectedValue {
				t.Fatalf("allocatedMemory: got %d want %d", value, testCase.expectedValue)
			}
		})
	}
}

func TestProbeHost_FailedLogs(t *testing.T) {
	t.Cleanup(resetLogs)
	probe := newHostProbe()
	if _, err := probe.failedLogs(); err != nil {
		t.Fatalf("failedLogs: unexpected error: %v", err)
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
			t.Cleanup(resetMounts)
			seedHostMounts(t)
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
		temps         map[string]float64
		expectedValue int8
		expectedError bool
	}{
		{
			name:          "sad_no_sensor",
			expectedError: true,
		},
		{
			name:          "happy_below_floor_clamps_to_zero",
			temps:         map[string]float64{"package id 0": 30.0},
			expectedValue: 0,
			expectedError: false,
		},
		{
			name:          "happy_floor",
			temps:         map[string]float64{"package id 0": 40.0},
			expectedValue: 0,
			expectedError: false,
		},
		{
			name:          "happy_midpoint",
			temps:         map[string]float64{"package id 0": 45.0},
			expectedValue: 25,
			expectedError: false,
		},
		{
			name:          "happy_high_anchor",
			temps:         map[string]float64{"package id 0": 50.0},
			expectedValue: 50,
			expectedError: false,
		},
		{
			name:          "happy_warn_threshold",
			temps:         map[string]float64{"package id 0": 51.0},
			expectedValue: 55,
			expectedError: false,
		},
		{
			name:          "happy_alert_threshold",
			temps:         map[string]float64{"package id 0": 53.0},
			expectedValue: 65,
			expectedError: false,
		},
		{
			name:          "happy_above_ceiling_clamps_to_full",
			temps:         map[string]float64{"package id 0": 70.0},
			expectedValue: 100,
			expectedError: false,
		},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			t.Cleanup(resetSensors)
			probe := newHostProbe()
			probe.sysRoot = writeSensorTree(t, testCase.temps, nil, nil)
			value, err := probe.warnTemperature()
			if testCase.expectedError {
				if err == nil {
					t.Fatalf("expected error but got nil")
				}
				return
			}
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if value != testCase.expectedValue {
				t.Fatalf("warnTemperature: got %d want %d", value, testCase.expectedValue)
			}
		})
	}
}

func TestProbeHost_SpinFanSpeed(t *testing.T) {
	tests := []struct {
		name          string
		fans          map[string][2]float64
		expectedValue int8
		expectedError bool
	}{
		{
			name:          "happy_no_fan_reads_zero",
			fans:          nil,
			expectedValue: 0,
			expectedError: false,
		},
		{
			name:          "happy_macmini_mad_fan",
			fans:          map[string][2]float64{"Fan": {1690, 5000}},
			expectedValue: 34,
			expectedError: false,
		},
		{
			name:          "happy_macmini_exhaust",
			fans:          map[string][2]float64{"Exhaust": {1799, 4800}},
			expectedValue: 37,
			expectedError: false,
		},
		{
			name:          "happy_fastest_of_several",
			fans:          map[string][2]float64{"Exhaust": {1799, 4800}, "Intake": {4000, 4800}},
			expectedValue: 83,
			expectedError: false,
		},
		{
			name:          "happy_stopped_fan",
			fans:          map[string][2]float64{"Exhaust": {0, 4800}},
			expectedValue: 0,
			expectedError: false,
		},
		{
			name:          "happy_full_speed",
			fans:          map[string][2]float64{"Exhaust": {4800, 4800}},
			expectedValue: 100,
			expectedError: false,
		},
		{
			name:          "happy_fan_without_maximum_skipped",
			fans:          map[string][2]float64{"Exhaust": {1799, 0}},
			expectedValue: 0,
			expectedError: false,
		},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			t.Cleanup(resetSensors)
			probe := newHostProbe()
			probe.sysRoot = writeSensorTree(t, nil, nil, testCase.fans)
			value, err := probe.spinFanSpeed()
			if testCase.expectedError {
				if err == nil {
					t.Fatalf("expected error but got nil")
				}
				return
			}
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if value != testCase.expectedValue {
				t.Fatalf("spinFanSpeed: got %d want %d", value, testCase.expectedValue)
			}
		})
	}
}

func TestProbeHost_SpinFanRespondingOK(t *testing.T) {
	tests := []struct {
		name           string
		fans           map[string][2]float64
		fan            int8
		temperature    int8
		temperatureMax int8
		fanMin         int8
		expectedOK     bool
	}{
		{
			name:           "happy_cool_host",
			fans:           map[string][2]float64{"Exhaust": {1799, 4800}},
			fan:            37,
			temperature:    40,
			temperatureMax: 65,
			fanMin:         80,
			expectedOK:     true,
		},
		{
			name:           "happy_hot_host_fan_idle",
			fans:           map[string][2]float64{"Exhaust": {1799, 4800}},
			fan:            37,
			temperature:    90,
			temperatureMax: 65,
			fanMin:         80,
			expectedOK:     false,
		},
		{
			name:           "happy_hot_host_fan_ramped",
			fans:           map[string][2]float64{"Exhaust": {4080, 4800}},
			fan:            85,
			temperature:    90,
			temperatureMax: 65,
			fanMin:         80,
			expectedOK:     true,
		},
		{
			name:           "happy_warm_trend_fan_idle",
			fans:           map[string][2]float64{"Exhaust": {1799, 4800}},
			fan:            37,
			temperature:    60,
			temperatureMax: 55,
			fanMin:         50,
			expectedOK:     false,
		},
		{
			name:           "happy_warm_trend_fan_ramped",
			fans:           map[string][2]float64{"Exhaust": {2880, 4800}},
			fan:            60,
			temperature:    60,
			temperatureMax: 55,
			fanMin:         50,
			expectedOK:     true,
		},
		{
			name:           "happy_fanless_host_exempt",
			fans:           nil,
			fan:            0,
			temperature:    90,
			temperatureMax: 65,
			fanMin:         80,
			expectedOK:     true,
		},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			t.Cleanup(resetSensors)
			probe := newHostProbe()
			probe.sysRoot = writeSensorTree(t, nil, nil, testCase.fans)
			ok := probe.spinFanRespondingOK(testCase.fan, testCase.temperature, testCase.temperatureMax, testCase.fanMin)
			if ok != testCase.expectedOK {
				t.Fatalf("spinFanRespondingOK: got %v want %v", ok, testCase.expectedOK)
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
			t.Cleanup(resetMounts)
			seedHostMounts(t)
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
			expectedValue: 38,
			expectedOK:    true,
			expectedError: false,
		},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			t.Cleanup(resetMounts)
			seedHostMounts(t)
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
			expectedValue: 20,
			expectedOK:    true,
			expectedError: false,
		},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			t.Cleanup(resetMounts)
			seedHostMounts(t)
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

func TestProbeHost_TemperatureDiscoversOnce(t *testing.T) {
	t.Cleanup(resetSensors)
	probe := newHostProbe()
	probe.sysRoot = writeSensorTree(t, map[string]float64{"Composite": 31.9}, nil, nil)
	discovered := loadSensors(probe.sysRoot)
	if discovered.tier != sensorTierComposite {
		t.Fatalf("tier: got %q want %q", discovered.tier, sensorTierComposite)
	}
	for index := range 3 {
		value, err := probe.temperature()
		if err != nil {
			t.Fatalf("unexpected error: %v", err)
		}
		if math.Abs(value-41.9) > 0.05 {
			t.Errorf("temperature: got %v want %v on call %d", value, 41.9, index+1)
		}
		if loadSensors(probe.sysRoot) != discovered {
			t.Fatalf("sensors: got a re-discovery on call %d, want the cached set", index+1)
		}
	}
}

func seedHostMounts(t *testing.T) {
	t.Helper()
	mounts := "/dev/nvme0n1p6 / btrfs rw 0 0\n" +
		"/dev/nvme0n1p5 /var ext4 rw 0 0\n" +
		"/dev/sdb1 /share/10 ext4 rw 0 0\n" +
		"/dev/sdc1 /share/11 ext4 rw 0 0\n"
	fstab := "PARTLABEL=share_08 /share/10 ext4 noatime 0 2\n" +
		"PARTLABEL=share_09 /share/11 ext4 noatime 0 2\n"
	sizes := map[string][2]uint64{
		"/":         {1000, 48},
		"/var":      {1000, 380},
		"/share/10": {1000, 500},
		"/share/11": {3000, 300},
	}
	set := newMountFixture(t, writeMountTree(t, mounts, fstab, nil), sizes, nil)
	set.current = set.collect()
	mountCacheMu.Lock()
	mountCache[""] = set
	mountCacheMu.Unlock()
}
