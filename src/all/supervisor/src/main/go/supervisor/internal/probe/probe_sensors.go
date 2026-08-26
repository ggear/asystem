package probe

import (
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strconv"
	"strings"
	"supervisor/internal/metric"
	"supervisor/internal/scribe"
	"sync"
	"time"
)

type sensorSet struct {
	sysRoot           string
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
	sensorCacheMutex.RLock()
	if cached, ok := sensorCache[sysRoot]; ok {
		sensorCacheMutex.RUnlock()
		return cached
	}
	sensorCacheMutex.RUnlock()
	sensorCacheMutex.Lock()
	defer sensorCacheMutex.Unlock()
	if cached, ok := sensorCache[sysRoot]; ok {
		return cached
	}
	discovered := discoverSensors(sysRoot)
	sensorCache[sysRoot] = discovered
	return discovered
}

func resetSensors() {
	sensorCacheMutex.Lock()
	defer sensorCacheMutex.Unlock()
	clear(sensorCache)
}

func (s *sensorSet) celsius() (float64, derivation, error) {
	if s == nil {
		return 0, derivation{}, fmt.Errorf("no temperature read, discovery found no package, soc, composite or thermal zone sensor, so this host exposes none this probe knows how to read [%w]", errEnvironment)
	}
	if len(s.temperatureInputs) == 0 {
		return 0, derivation{}, fmt.Errorf("no temperature read, discovery found no package, soc, composite or thermal zone sensor under [%s], so this host exposes none this probe knows how to read [%w]", s.sysRoot, errEnvironment)
	}
	hottest := 0.0
	found := false
	var rejected []string
	for _, input := range s.temperatureInputs {
		milli, err := readSensorValue(input)
		if err != nil {
			rejected = append(rejected, fmt.Sprintf("%s unreadable with [%v]", input, err))
			continue
		}
		celsius := milli/1000.0 + s.temperatureOffset
		if celsius < sensorMinCelsius || celsius > sensorMaxCelsius {
			rejected = append(rejected, fmt.Sprintf("%s read [%.1f] celsius outside [%.0f] to [%.0f]", input, celsius, sensorMinCelsius, sensorMaxCelsius))
			continue
		}
		if !found || celsius > hottest {
			hottest = celsius
		}
		found = true
	}
	if !found {
		return 0, derivation{}, fmt.Errorf("no temperature read, none of the [%d] discovered [%s] tier sensors answered sanely, rejected [%s]",
			len(s.temperatureInputs), s.tier, strings.Join(rejected, ", "))
	}
	return hottest, derived(scribe.ActionSample, "computed [%.1f] C hottest, tier [%s], inputs [%d], offset [%.1f] C, sane between [%.0f] and [%.0f] C",
		hottest, s.tier, len(s.temperatureInputs), s.temperatureOffset, sensorMinCelsius, sensorMaxCelsius), nil
}

func (s *sensorSet) fanSpeedOfMax() (float64, derivation, error) {
	if s == nil {
		return 0, derivedInert(scribe.ActionSample, "computed [0.0] pct of max, discovery found no fan input so the metric is inert and always ok"), nil
	}
	if len(s.fans) == 0 {
		return 0, derivedInert(scribe.ActionSample, "computed [0.0] pct of max, discovery found no fan input under [%s] so the metric is inert and always ok", s.sysRoot), nil
	}
	fastest := 0.0
	found := false
	var fastestDetail []string
	var rejected []string
	for _, fan := range s.fans {
		rpm, err := readSensorValue(fan.input)
		if err != nil {
			rejected = append(rejected, fmt.Sprintf("%s unreadable with [%v]", fan.input, err))
			continue
		}
		if rpm < 0 {
			rejected = append(rejected, fmt.Sprintf("%s read [%.0f] rpm below zero", fan.input, rpm))
			continue
		}
		ofMax := rpm / fan.maxRPM * 100.0
		fastestDetail = append(fastestDetail, fmt.Sprintf("%s=%.0f/%.0f rpm", fan.label, rpm, fan.maxRPM))
		if !found || ofMax > fastest {
			fastest = ofMax
		}
		found = true
	}
	if !found {
		return 0, derivation{}, fmt.Errorf("no fan speed read, none of the [%d] discovered fans answered, rejected [%s]", len(s.fans), strings.Join(rejected, ", "))
	}
	return fastest, derived(scribe.ActionSample, "computed [%.1f] pct of max fastest, fans [%d], readings [%s]",
		fastest, len(s.fans), strings.Join(fastestDetail, " ")), nil
}

func discoverSensors(sysRoot string) *sensorSet {
	discoverStart := time.Now()
	discovered := &sensorSet{sysRoot: sysRoot}
	isSocSensor := func(zoneKey string) bool {
		for _, prefix := range socSensorKeys {
			if strings.Contains(zoneKey, prefix) {
				return true
			}
		}
		return false
	}
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
					scribe.Log(scribe.SourceProbe, scribe.SubjectMetric(metric.MetricHostSpinFanSpeed), scribe.ActionDiscover).Info("bypassed", discoverStart, "[%s] fan declares no maximum speed", input)
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
		scribe.Log(scribe.SourceProbe, scribe.SubjectMetric(metric.MetricHostTemperature), scribe.ActionDiscover).Info("fallback", discoverStart, "[composite] no package or soc sensor found, deriving from a drive sensor offset by [%.0f] C", sensorCompositeOffset)
	}
	scribe.Log(scribe.SourceProbe, scribe.SubjectMetric(metric.MetricHostTemperature), scribe.ActionDiscover).Info("topology", discoverStart, "[%s] tier with [%d] temperature and [%d] fan inputs under [%s]", discovered.tier, len(discovered.temperatureInputs), len(discovered.fans), sysRoot)
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

var socSensorKeys = []string{"cpu_therm", "cpu-therm", "soc_therm", "soc-therm"}

var (
	sensorCache      = map[string]*sensorSet{}
	sensorCacheMutex sync.RWMutex
)
