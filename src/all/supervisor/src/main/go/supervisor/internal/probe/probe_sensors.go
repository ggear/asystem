package probe

import (
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strconv"
	"strings"
	"supervisor/internal/scribe"
	"sync"
	"time"
)

type sensorSet struct {
	tier              string
	temperatureInputs []string
	temperatureOffset float64
	fans              []sensorFan
}

type sensorFan struct {
	label  string
	input  string
	maxRPM float64
}

func loadSensors(sysRoot string) *sensorSet {
	sensorCacheMu.RLock()
	if cached, ok := sensorCache[sysRoot]; ok {
		sensorCacheMu.RUnlock()
		return cached
	}
	sensorCacheMu.RUnlock()
	sensorCacheMu.Lock()
	defer sensorCacheMu.Unlock()
	if cached, ok := sensorCache[sysRoot]; ok {
		return cached
	}
	discovered := discoverSensors(sysRoot)
	sensorCache[sysRoot] = discovered
	return discovered
}

func resetSensors() {
	sensorCacheMu.Lock()
	defer sensorCacheMu.Unlock()
	clear(sensorCache)
}

func (s *sensorSet) celsius() (float64, error) {
	if s == nil || len(s.temperatureInputs) == 0 {
		return 0, errors.New("no suitable temperature sensors found")
	}
	hottest := 0.0
	found := false
	for _, input := range s.temperatureInputs {
		milli, err := readSensorValue(input)
		if err != nil {
			continue
		}
		celsius := milli/1000.0 + s.temperatureOffset
		if celsius < sensorMinCelsius || celsius > sensorMaxCelsius {
			continue
		}
		if !found || celsius > hottest {
			hottest = celsius
		}
		found = true
	}
	if !found {
		return 0, fmt.Errorf("no readable [%s] temperature sensors", s.tier)
	}
	return hottest, nil
}

func (s *sensorSet) fanSpeedOfMax() (float64, error) {
	if s == nil || len(s.fans) == 0 {
		return 0, nil
	}
	fastest := 0.0
	found := false
	for _, fan := range s.fans {
		rpm, err := readSensorValue(fan.input)
		if err != nil {
			continue
		}
		if rpm < 0 {
			continue
		}
		ofMax := rpm / fan.maxRPM * 100.0
		if !found || ofMax > fastest {
			fastest = ofMax
		}
		found = true
	}
	if !found {
		return 0, errors.New("no readable fan sensors")
	}
	return fastest, nil
}

func discoverSensors(sysRoot string) *sensorSet {
	discoverStart := time.Now()
	discovered := &sensorSet{}
	var packageInputs, socInputs, compositeInputs []string
	devices, _ := filepath.Glob(filepath.Join(sysRoot, "class", "hwmon", "hwmon*"))
	sort.Strings(devices)
	for _, device := range devices {
		for _, attributes := range []string{device, filepath.Join(device, sensorNestedDir)} {
			inputs, _ := filepath.Glob(filepath.Join(attributes, "temp*_input"))
			sort.Strings(inputs)
			for _, input := range inputs {
				key := strings.ToLower(sensorLabel(input, device))
				switch {
				case strings.Contains(key, "package"):
					packageInputs = append(packageInputs, input)
				case isSocSensor(key):
					socInputs = append(socInputs, input)
				case strings.Contains(key, "composite"):
					compositeInputs = append(compositeInputs, input)
				}
			}
			fans, _ := filepath.Glob(filepath.Join(attributes, "fan*_input"))
			sort.Strings(fans)
			for _, input := range fans {
				maxRPM, err := readSensorValue(strings.TrimSuffix(input, "_input") + "_max")
				if err != nil || maxRPM <= 0 {
					scribe.Probe("state", "sensors").Warn("discover", discoverStart, "skipped  [%s] fan declares no maximum speed", input)
					continue
				}
				discovered.fans = append(discovered.fans, sensorFan{
					label:  sensorLabel(input, device),
					input:  input,
					maxRPM: maxRPM,
				})
			}
		}
	}
	switch {
	case len(packageInputs) > 0:
		discovered.tier = sensorTierPackage
		discovered.temperatureInputs = packageInputs
	case len(socInputs) > 0:
		discovered.tier = sensorTierSoc
		discovered.temperatureInputs = socInputs
	case len(compositeInputs) > 0:
		discovered.tier = sensorTierComposite
		discovered.temperatureInputs = compositeInputs
		discovered.temperatureOffset = sensorCompositeOffset
	default:
		discovered.tier = sensorTierNone
		discovered.temperatureInputs = discoverThermalZones(sysRoot)
		if len(discovered.temperatureInputs) > 0 {
			discovered.tier = sensorTierZone
		}
	}
	if discovered.tier == sensorTierComposite {
		scribe.Probe("state", "sensors").Warn("discover", discoverStart, "derived  [composite] no package or soc sensor found, deriving from a drive sensor offset by [%.0f] C", sensorCompositeOffset)
	}
	scribe.Probe("state", "sensors").Info("discover", discoverStart, "sensors  [%s] tier with [%d] temperature and [%d] fan inputs under [%s]", discovered.tier, len(discovered.temperatureInputs), len(discovered.fans), sysRoot)
	return discovered
}

func discoverThermalZones(sysRoot string) []string {
	zones, _ := filepath.Glob(filepath.Join(sysRoot, "class", "thermal", "thermal_zone*", "temp"))
	sort.Strings(zones)
	return zones
}

func sensorLabel(input, device string) string {
	if label, err := os.ReadFile(strings.TrimSuffix(input, "_input") + "_label"); err == nil {
		if trimmed := strings.TrimSpace(string(label)); trimmed != "" {
			return trimmed
		}
	}
	if name, err := os.ReadFile(filepath.Join(device, "name")); err == nil {
		if trimmed := strings.TrimSpace(string(name)); trimmed != "" {
			return trimmed + " " + strings.TrimSuffix(filepath.Base(input), "_input")
		}
	}
	return filepath.Base(input)
}

func readSensorValue(path string) (float64, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return 0, err
	}
	return strconv.ParseFloat(strings.TrimSpace(string(data)), 64)
}

const (
	sensorSysRoot         = "/sys"
	sensorNestedDir       = "device"
	sensorTierPackage     = "package"
	sensorTierSoc         = "soc"
	sensorTierComposite   = "composite"
	sensorTierZone        = "zone"
	sensorTierNone        = "none"
	sensorCompositeOffset = 10.0
	sensorMinCelsius      = 10.0
	sensorMaxCelsius      = 150.0
)

var (
	sensorCache   = map[string]*sensorSet{}
	sensorCacheMu sync.RWMutex
)
