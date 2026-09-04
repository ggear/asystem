package probe

import (
	"fmt"
	"math"
	"os"
	"path/filepath"
	"strconv"
	"testing"
)

func TestProbeLibSensors_DiscoverTier(t *testing.T) {
	tests := []struct {
		name           string
		devices        []sensorDevice
		zones          map[string]float64
		expectedTier   string
		expectedInputs int
		expectedOffset float64
		expectedFans   int
		expectedError  bool
	}{
		{
			name:           "happy_package",
			devices:        []sensorDevice{{name: "coretemp", labelled: map[string]float64{"Package id 0": 55.0, "Core 0": 51.0}}},
			expectedTier:   sensorTierPackage,
			expectedInputs: 1,
			expectedError:  false,
		},
		{
			name:           "happy_soc_from_unlabelled_device_name",
			devices:        []sensorDevice{{name: "cpu_thermal", unlabelled: []float64{50.4}}},
			expectedTier:   sensorTierSoc,
			expectedInputs: 1,
			expectedError:  false,
		},
		{
			name:           "happy_composite_carries_offset",
			devices:        []sensorDevice{{name: "nvme", labelled: map[string]float64{"Composite": 31.9}}},
			expectedTier:   sensorTierComposite,
			expectedInputs: 1,
			expectedOffset: sensorCompositeOffset,
			expectedError:  false,
		},
		{
			name: "happy_package_wins_over_soc_and_composite",
			devices: []sensorDevice{
				{name: "nvme", labelled: map[string]float64{"Composite": 31.9}},
				{name: "cpu_thermal", unlabelled: []float64{60.0}},
				{name: "coretemp", labelled: map[string]float64{"Package id 0": 55.0}},
			},
			expectedTier:   sensorTierPackage,
			expectedInputs: 1,
			expectedError:  false,
		},
		{
			name: "happy_soc_wins_over_composite",
			devices: []sensorDevice{
				{name: "nvme", labelled: map[string]float64{"Composite": 31.9}},
				{name: "soc", labelled: map[string]float64{"soc_thermal": 44.0}},
			},
			expectedTier:   sensorTierSoc,
			expectedInputs: 1,
			expectedError:  false,
		},
		{
			name: "happy_every_input_of_the_winning_tier_is_kept",
			devices: []sensorDevice{
				{name: "coretemp", labelled: map[string]float64{"Package id 0": 55.0}},
				{name: "coretemp", labelled: map[string]float64{"Package id 1": 61.0}},
			},
			expectedTier:   sensorTierPackage,
			expectedInputs: 2,
			expectedError:  false,
		},
		{
			name:           "happy_thermal_zone_fallback",
			zones:          map[string]float64{"cpu-thermal": 49.4},
			expectedTier:   sensorTierZone,
			expectedInputs: 1,
			expectedError:  false,
		},
		{
			name:           "sad_nothing_discovered",
			expectedTier:   sensorTierNone,
			expectedInputs: 0,
			expectedError:  false,
		},
		{
			name:           "happy_fan_with_maximum_kept",
			devices:        []sensorDevice{{name: "applesmc", fans: map[string][2]float64{"Exhaust": {1799, 4800}}}},
			expectedTier:   sensorTierNone,
			expectedInputs: 0,
			expectedFans:   1,
			expectedError:  false,
		},
		{
			name:           "happy_nested_applesmc_fan",
			devices:        []sensorDevice{{name: "", nested: true, fans: map[string][2]float64{"Exhaust": {1799, 4800}}}},
			expectedTier:   sensorTierNone,
			expectedInputs: 0,
			expectedFans:   1,
			expectedError:  false,
		},
		{
			name:           "happy_nested_and_direct_layouts_together",
			devices:        []sensorDevice{{name: "coretemp", labelled: map[string]float64{"Package id 0": 55.0}}, {name: "", nested: true, fans: map[string][2]float64{"Exhaust": {1799, 4800}}}},
			expectedTier:   sensorTierPackage,
			expectedInputs: 1,
			expectedFans:   1,
			expectedError:  false,
		},
		{
			name:           "sad_fan_without_maximum_skipped",
			devices:        []sensorDevice{{name: "applesmc", fans: map[string][2]float64{"Exhaust": {1799, 0}}}},
			expectedTier:   sensorTierNone,
			expectedInputs: 0,
			expectedFans:   0,
			expectedError:  false,
		},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			t.Cleanup(resetSensors)
			discovered := loadSensors(writeSensorDevices(t, testCase.devices, testCase.zones))
			if discovered.tier != testCase.expectedTier {
				t.Errorf("tier: got %q want %q", discovered.tier, testCase.expectedTier)
			}
			if len(discovered.temperatureInputs) != testCase.expectedInputs {
				t.Errorf("temperatureInputs: got %d want %d", len(discovered.temperatureInputs), testCase.expectedInputs)
			}
			if discovered.temperatureOffset != testCase.expectedOffset {
				t.Errorf("temperatureOffset: got %v want %v", discovered.temperatureOffset, testCase.expectedOffset)
			}
			if len(discovered.fans) != testCase.expectedFans {
				t.Errorf("fans: got %d want %d", len(discovered.fans), testCase.expectedFans)
			}
		})
	}
}

func TestProbeLibSensors_Celsius(t *testing.T) {
	tests := []struct {
		name          string
		devices       []sensorDevice
		removeInputs  bool
		expected      float64
		expectedError bool
	}{
		{
			name:          "happy_single_reading",
			devices:       []sensorDevice{{name: "coretemp", labelled: map[string]float64{"Package id 0": 55.0}}},
			expected:      55.0,
			expectedError: false,
		},
		{
			name: "happy_hottest_of_the_tier",
			devices: []sensorDevice{
				{name: "coretemp", labelled: map[string]float64{"Package id 0": 55.0}},
				{name: "coretemp", labelled: map[string]float64{"Package id 1": 61.0}},
			},
			expected:      61.0,
			expectedError: false,
		},
		{
			name:          "happy_composite_offset_applied",
			devices:       []sensorDevice{{name: "nvme", labelled: map[string]float64{"Composite": 31.9}}},
			expected:      41.9,
			expectedError: false,
		},
		{
			name: "happy_out_of_range_reading_ignored",
			devices: []sensorDevice{
				{name: "coretemp", labelled: map[string]float64{"Package id 0": 200.0}},
				{name: "coretemp", labelled: map[string]float64{"Package id 1": 58.0}},
			},
			expected:      58.0,
			expectedError: false,
		},
		{
			name:          "sad_every_reading_out_of_range",
			devices:       []sensorDevice{{name: "coretemp", labelled: map[string]float64{"Package id 0": 5.0}}},
			expectedError: true,
		},
		{
			name:          "sad_no_sensors",
			expectedError: true,
		},
		{
			name:          "sad_input_disappeared_after_discovery",
			devices:       []sensorDevice{{name: "coretemp", labelled: map[string]float64{"Package id 0": 55.0}}},
			removeInputs:  true,
			expectedError: true,
		},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			t.Cleanup(resetSensors)
			sysRoot := writeSensorDevices(t, testCase.devices, nil)
			discovered := loadSensors(sysRoot)
			if testCase.removeInputs {
				for _, input := range discovered.temperatureInputs {
					if err := os.Remove(input); err != nil {
						t.Fatalf("remove %s failed: %v", input, err)
					}
				}
			}
			value, _, err := discovered.celsius()
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
				t.Errorf("celsius: got %v want %v", value, testCase.expected)
			}
		})
	}
}

func TestProbeLibSensors_FanSpeedOfMax(t *testing.T) {
	tests := []struct {
		name          string
		fans          map[string][2]float64
		removeInputs  bool
		expected      float64
		expectedError bool
	}{
		{
			name:          "happy_no_fan_is_zero_not_an_error",
			expected:      0,
			expectedError: false,
		},
		{
			name:          "happy_macmini_mad_fan",
			fans:          map[string][2]float64{"Fan": {1690, 5000}},
			expected:      33.8,
			expectedError: false,
		},
		{
			name:          "happy_macmini_exhaust",
			fans:          map[string][2]float64{"Exhaust": {1799, 4800}},
			expected:      37.5,
			expectedError: false,
		},
		{
			name:          "happy_fastest_of_several",
			fans:          map[string][2]float64{"Exhaust": {1799, 4800}, "Intake": {4000, 4800}},
			expected:      83.3,
			expectedError: false,
		},
		{
			name:          "happy_stopped_fan",
			fans:          map[string][2]float64{"Exhaust": {0, 4800}},
			expected:      0,
			expectedError: false,
		},
		{
			name:          "happy_above_maximum_is_left_uncapped_here",
			fans:          map[string][2]float64{"Exhaust": {5000, 4800}},
			expected:      104.2,
			expectedError: false,
		},
		{
			name:          "happy_fan_without_maximum_is_never_discovered",
			fans:          map[string][2]float64{"Exhaust": {1799, 0}},
			expected:      0,
			expectedError: false,
		},
		{
			name:          "sad_input_disappeared_after_discovery",
			fans:          map[string][2]float64{"Exhaust": {1799, 4800}},
			removeInputs:  true,
			expectedError: true,
		},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			t.Cleanup(resetSensors)
			sysRoot := writeSensorDevices(t, []sensorDevice{{name: "applesmc", fans: testCase.fans}}, nil)
			discovered := loadSensors(sysRoot)
			if testCase.removeInputs {
				for _, fan := range discovered.fans {
					if err := os.Remove(fan.input); err != nil {
						t.Fatalf("remove %s failed: %v", fan.input, err)
					}
				}
			}
			value, _, err := discovered.fanSpeedOfMax()
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
				t.Errorf("fanSpeedOfMax: got %v want %v", value, testCase.expected)
			}
		})
	}
}

func TestProbeLibSensors_LoadIsCachedPerRoot(t *testing.T) {
	t.Cleanup(resetSensors)
	sysRoot := writeSensorDevices(t, []sensorDevice{{name: "coretemp", labelled: map[string]float64{"Package id 0": 55.0}}}, nil)
	if loadSensors(sysRoot) != loadSensors(sysRoot) {
		t.Errorf("load: got distinct sets for one root, want the same set")
	}
	if loadSensors(sysRoot) == loadSensors(writeSensorDevices(t, nil, nil)) {
		t.Errorf("load: got the same set for two roots, want distinct sets")
	}
	discovered := loadSensors(sysRoot)
	resetSensors()
	if loadSensors(sysRoot) == discovered {
		t.Errorf("load after reset: got the cached set, want a new set")
	}
}

func TestProbeLibSensors_DiscoveryIsNeverRepeated(t *testing.T) {
	t.Cleanup(resetSensors)
	sysRoot := writeSensorDevices(t, nil, nil)
	discovered := loadSensors(sysRoot)
	if discovered.tier != sensorTierNone || len(discovered.fans) != 0 {
		t.Fatalf("discovered: got tier %q with %d fans want %q with none", discovered.tier, len(discovered.fans), sensorTierNone)
	}
	writeSensorDevicesInto(t, sysRoot, []sensorDevice{{name: "applesmc", fans: map[string][2]float64{"Exhaust": {1799, 4800}}}}, nil)
	if loadSensors(sysRoot) != discovered {
		t.Fatalf("load: got a re-discovery after a sensor appeared, want the cached set until restart")
	}
	speed, _, err := loadSensors(sysRoot).fanSpeedOfMax()
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if speed != 0 {
		t.Errorf("fanSpeedOfMax: got %v want 0, a sensor appearing after discovery needs a restart", speed)
	}
}

type sensorDevice struct {
	name       string
	nested     bool
	labelled   map[string]float64
	unlabelled []float64
	fans       map[string][2]float64
}

func writeSensorTree(t *testing.T, temps, zones map[string]float64, fans map[string][2]float64) string {
	t.Helper()
	return writeSensorDevices(t, []sensorDevice{{name: "fixture", labelled: temps, fans: fans}}, zones)
}

func writeSensorDevices(t *testing.T, devices []sensorDevice, zones map[string]float64) string {
	t.Helper()
	sysRoot := t.TempDir()
	writeSensorDevicesInto(t, sysRoot, devices, zones)
	return sysRoot
}

func writeSensorDevicesInto(t *testing.T, sysRoot string, devices []sensorDevice, zones map[string]float64) {
	t.Helper()
	for offset, device := range devices {
		root := filepath.Join(sysRoot, "class", "hwmon", fmt.Sprintf("hwmon%d", offset))
		writeSensorDir(t, root)
		writeSensorFile(t, filepath.Join(root, "name"), device.name)
		attributes := root
		if device.nested {
			attributes = filepath.Join(root, sensorNestedDir)
			writeSensorDir(t, attributes)
		}
		index := 0
		for label, celsius := range device.labelled {
			index++
			prefix := filepath.Join(attributes, fmt.Sprintf("temp%d", index))
			writeSensorFile(t, prefix+"_label", label)
			writeSensorFile(t, prefix+"_input", sensorMilli(celsius))
		}
		for _, celsius := range device.unlabelled {
			index++
			writeSensorFile(t, filepath.Join(attributes, fmt.Sprintf("temp%d_input", index)), sensorMilli(celsius))
		}
		index = 0
		for label, reading := range device.fans {
			index++
			prefix := filepath.Join(attributes, fmt.Sprintf("fan%d", index))
			writeSensorFile(t, prefix+"_label", label)
			writeSensorFile(t, prefix+"_input", strconv.FormatFloat(reading[0], 'f', 0, 64))
			if reading[1] > 0 {
				writeSensorFile(t, prefix+"_max", strconv.FormatFloat(reading[1], 'f', 0, 64))
			}
		}
	}
	index := 0
	for label, celsius := range zones {
		zone := filepath.Join(sysRoot, "class", "thermal", fmt.Sprintf("thermal_zone%d", index))
		index++
		writeSensorDir(t, zone)
		writeSensorFile(t, filepath.Join(zone, "type"), label)
		writeSensorFile(t, filepath.Join(zone, "temp"), sensorMilli(celsius))
	}
}

func sensorMilli(celsius float64) string {
	return strconv.FormatFloat(celsius*1000.0, 'f', 0, 64)
}

func writeSensorDir(t *testing.T, dir string) {
	t.Helper()
	if err := os.MkdirAll(dir, 0o755); err != nil {
		t.Fatalf("mkdir %s failed: %v", dir, err)
	}
}

func writeSensorFile(t *testing.T, path, content string) {
	t.Helper()
	if err := os.WriteFile(path, []byte(content+"\n"), 0o644); err != nil {
		t.Fatalf("write %s failed: %v", path, err)
	}
}
