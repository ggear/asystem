package plugin

import (
	"fmt"
	"math"
	"strconv"
	"strings"
	"time"

	"network/internal/remote"
	"network/internal/schema"
)

const (
	deviceStaleAfter          = 5 * time.Minute
	deviceExperienceSickBelow = 85.0
	deviceCPUKnee             = 0.8
	deviceMemoryKnee          = 0.9
	deviceNetworkKnee         = 0.8
	deviceRestartPenalty      = 20
	deviceOverheatPenalty     = 10
)

type deviceSchema struct {
	relation    *schema.Builder
	name        schema.DimensionKey
	up          schema.BoolKey
	restarted   schema.BoolKey
	overheating schema.BoolKey
	experience  schema.FloatKey
	throughput  schema.FloatKey
	network     schema.FloatKey
	clients     schema.IntKey
	cpu         schema.FloatKey
	memory      schema.FloatKey
	temperature *schema.FloatKey
	poe         *schema.FloatKey
	poeBudget   *schema.FloatKey
}

type deviceReading struct {
	name           string
	up             bool
	restarted      bool
	overheating    bool
	experience     float64
	throughput     float64
	network        float64
	hasTraffic     bool
	clients        int64
	cpu            float64
	memory         float64
	temperature    float64
	hasTemperature bool
	poe            float64
	poeBudget      float64
	hasPoE         bool
}

func declareDevices(path, description, subject, subjectDescription string, names []string, wired bool) deviceSchema {
	relation := schema.Declare(path, description, aggregateCadence).Entities(names...)
	devices := deviceSchema{
		relation:    relation,
		name:        relation.Subject(subject, subjectDescription),
		up:          relation.Bool("up", "device connected and seen by the controller recently"),
		restarted:   relation.Bool("restarted", "device came up since the previous check"),
		overheating: relation.Bool("overheating", "controller flags the device as overheating"),
		experience:  relation.Float("experience_pct", "%", "experience reported by the controller, capped by processor, memory and busiest link headroom"),
		throughput:  relation.Float("throughput_mbps", "Mbps", "traffic in both directions on the busiest link across the window"),
		network:     relation.Float("network_pct", "%", "busier direction of the busiest link against its negotiated speed across the window"),
		clients:     relation.Int("clients", "", "clients associated with the device, or for a gateway every client on the site"),
		cpu:         relation.Float("cpu_pct", "%", "processor in use"),
		memory:      relation.Float("memory_pct", "%", "memory in use"),
	}
	if wired {
		temperature := relation.Float("temperature", "°C", "hottest temperature sensor the device reports")
		poe := relation.Float("poe_w", "W", "power over ethernet drawn by the powered ports")
		poeBudget := relation.Float("poe_pct", "%", "power over ethernet drawn against the device's budget")
		devices.temperature, devices.poe, devices.poeBudget = &temperature, &poe, &poeBudget
	}
	return devices
}

func readDevices(devices []remote.GatewayDevice, names []string, deltas *deltaTracker, now time.Time) []deviceReading {
	headroom := func(used, knee float64) float64 {
		if used <= knee {
			return 100
		}
		return math.Max(0, 100*(1-used)/(1-knee))
	}
	type link struct {
		key    string
		speed  int
		rx, tx int64
	}
	byName := make(map[string]remote.GatewayDevice, len(devices))
	for _, device := range devices {
		byName[device.Name] = device
	}
	readings := make([]deviceReading, 0, len(names))
	for _, name := range names {
		device, found := byName[name]
		reading := deviceReading{name: name}
		if !found || device.State != 1 || now.Sub(time.Unix(device.LastSeen, 0)) > deviceStaleAfter {
			readings = append(readings, reading)
			continue
		}
		reading.up = true
		reported, reportedOK := deltas.Delta(name+"/last_seen", device.LastSeen)
		reading.restarted = reportedOK && device.Uptime > 0 && device.Uptime < reported
		reading.overheating = device.Overheating
		reading.clients = int64(device.NumSta)
		reading.cpu, _ = strconv.ParseFloat(device.SystemStats.CPU, 64)
		reading.memory, _ = strconv.ParseFloat(device.SystemStats.Memory, 64)
		if device.HasTemperature && device.GeneralTemperature != nil {
			reading.temperature, reading.hasTemperature = *device.GeneralTemperature, true
		}
		for _, sensor := range device.Temperatures {
			if !reading.hasTemperature || sensor.Value > reading.temperature {
				reading.temperature, reading.hasTemperature = sensor.Value, true
			}
		}
		if device.TotalUsedPower != nil && device.TotalMaxPower != nil && *device.TotalMaxPower > 0 {
			reading.poe, reading.poeBudget, reading.hasPoE = *device.TotalUsedPower, *device.TotalUsedPower / *device.TotalMaxPower * 100, true
		}
		var links []link
		for _, port := range device.PortTable {
			if port.Up {
				links = append(links, link{key: strconv.Itoa(port.PortIdx), speed: port.Speed, rx: port.RxBytes, tx: port.TxBytes})
			}
		}
		if len(links) == 0 {
			links = append(links, link{key: "uplink", speed: device.Uplink.Speed, rx: device.Uplink.RxBytes, tx: device.Uplink.TxBytes})
		}
		for _, l := range links {
			key := name + "/" + l.key
			seen, seenOK := deltas.Delta(key+"/seen", device.LastSeen)
			rx, rxOK := deltas.Delta(key+"/rx", l.rx)
			tx, txOK := deltas.Delta(key+"/tx", l.tx)
			if !seenOK || !rxOK || !txOK || seen <= 0 {
				continue
			}
			seconds := float64(seen)
			reading.hasTraffic = true
			reading.throughput = math.Max(reading.throughput, float64(rx+tx)*8/seconds/1e6)
			if l.speed > 0 {
				reading.network = math.Max(reading.network, float64(max(rx, tx))*8/seconds/(float64(l.speed)*1e6)*100)
			}
		}
		reading.experience = math.Min(headroom(reading.cpu/100, deviceCPUKnee), headroom(reading.memory/100, deviceMemoryKnee))
		if reading.hasTraffic {
			reading.experience = math.Min(reading.experience, headroom(reading.network/100, deviceNetworkKnee))
		}
		if device.Satisfaction != nil && *device.Satisfaction >= 0 {
			reading.experience = math.Min(reading.experience, float64(*device.Satisfaction))
		}
		readings = append(readings, reading)
	}
	return readings
}

func diagnoseDevices(readings []deviceReading, devices deviceSchema) Aggregate {
	if len(readings) == 0 {
		return Diagnose(StatusDead, 0, "GATEWAY_UNREACHABLE: controller unreachable or no devices reporting")
	}
	var down, quiet, poor, restarted, overheating []string
	score := 100
	lowest := 100.0
	for _, reading := range readings {
		deviceScore := 0
		switch {
		case !reading.up:
			down = append(down, reading.name)
		case reading.hasTraffic && reading.throughput == 0 && !reading.restarted:
			quiet = append(quiet, reading.name)
		default:
			deviceScore = int(math.Round(reading.experience))
			lowest = math.Min(lowest, reading.experience)
			if reading.experience < deviceExperienceSickBelow {
				poor = append(poor, reading.name)
			}
			if reading.restarted {
				restarted = append(restarted, reading.name)
				deviceScore -= deviceRestartPenalty
			}
			if reading.overheating {
				overheating = append(overheating, reading.name)
				deviceScore -= deviceOverheatPenalty
			}
		}
		score = min(score, clamp(deviceScore))
	}
	result := Aggregate{}
	switch {
	case len(down) > 0:
		result = Diagnose(StatusDead, 0, fmt.Sprintf("DEVICE_DOWN: [%d] of [%d] devices down [%s]", len(down), len(readings), strings.Join(down, ", ")))
	case len(quiet) > 0:
		result = Diagnose(StatusDead, 0, fmt.Sprintf("NO_TRAFFIC: devices up but passing no traffic across window [%s]", strings.Join(quiet, ", ")))
	case len(poor) > 0:
		result = Diagnose(StatusSick, score, fmt.Sprintf("POOR_EXPERIENCE: experience below [%.0f%%] on [%s]", deviceExperienceSickBelow, strings.Join(poor, ", ")))
	case len(restarted) > 0:
		result = Diagnose(StatusSick, score, fmt.Sprintf("RESTARTED: devices restarted within window [%s]", strings.Join(restarted, ", ")))
	case len(overheating) > 0:
		result = Diagnose(StatusSick, score, fmt.Sprintf("OVERHEATING: devices overheating [%s]", strings.Join(overheating, ", ")))
	default:
		result = Diagnose(StatusFit, score, fmt.Sprintf("UP: [%d] devices up with lowest experience [%.0f%%]", len(readings), lowest))
	}
	result.Points = reportDevices(readings, devices)
	return result
}

func reportDevices(readings []deviceReading, devices deviceSchema) []schema.Point {
	points := make([]schema.Point, 0, len(readings))
	for _, reading := range readings {
		values := []schema.Value{devices.name.Of(reading.name), devices.up.Of(reading.up)}
		if !reading.up {
			values = append(values,
				devices.experience.Of(0),
				devices.throughput.Of(0),
				devices.network.Of(0),
				devices.clients.Of(0))
			points = append(points, devices.relation.Point(values...))
			continue
		}
		values = append(values,
			devices.restarted.Of(reading.restarted),
			devices.overheating.Of(reading.overheating),
			devices.experience.Of(round(reading.experience, 1)),
			devices.clients.Of(reading.clients),
			devices.cpu.Of(round(reading.cpu, 1)),
			devices.memory.Of(round(reading.memory, 1)))
		if reading.hasTraffic {
			values = append(values,
				devices.throughput.Of(round(reading.throughput, 2)),
				devices.network.Of(round(reading.network, 1)))
		}
		if reading.hasTemperature && devices.temperature != nil {
			values = append(values, devices.temperature.Of(round(reading.temperature, 1)))
		}
		if reading.hasPoE && devices.poe != nil {
			values = append(values,
				devices.poe.Of(round(reading.poe, 1)),
				devices.poeBudget.Of(round(reading.poeBudget, 1)))
		}
		points = append(points, devices.relation.Point(values...))
	}
	return points
}
