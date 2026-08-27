package metric

import (
	"errors"
	"fmt"
	"regexp"
	"strings"
)

const (
	ScopeData = "data"
	ScopeMeta = "meta"
)

type builder struct {
	id           ID
	valueKind    ValueKind
	metricKind   MetricKind
	unit         string
	description  string
	template     string
	persisted    bool
	warming      bool
	pulseRule    Rule
	trendRule    Rule
	dependencies []ID
}

const (
	FailedLogsBudget     = 10.0
	FailedLogsPulseLimit = 100.0 / FailedLogsBudget
)

const (
	WarnTemperatureBaseCelsius  = 40.0
	WarnTemperaturePerCelsius   = 5.0
	WarnTemperaturePulseCelsius = 53.0
	WarnTemperatureTrendCelsius = 51.0
	WarnTemperaturePulseLimit   = WarnTemperaturePerCelsius * (WarnTemperaturePulseCelsius - WarnTemperatureBaseCelsius)
	WarnTemperatureTrendLimit   = WarnTemperaturePerCelsius * (WarnTemperatureTrendCelsius - WarnTemperatureBaseCelsius)
	WarnTemperatureFullCelsius  = WarnTemperatureBaseCelsius + 100.0/WarnTemperaturePerCelsius
)

var metricBuildersByID = []builder{
	MetricHost: {
		id:          MetricHost,
		valueKind:   ValueBool,
		unit:        "",
		description: "host is reporting metrics",
		template:    "supervisor/$HOST/$SCOPE/host",
		persisted:   true,
		pulseRule:   Always(),
		trendRule:   Always(),
	},
	MetricHostUsedProcessor: {
		id:          MetricHostUsedProcessor,
		valueKind:   ValueInt,
		unit:        "%",
		description: "processor time used across all cores",
		template:    "supervisor/$HOST/$SCOPE/host/used_processor",
		persisted:   true,
		pulseRule:   Bounded(Self, AtMost, 90),
		trendRule:   Bounded(Self, AtMost, 70),
	},
	MetricHostUsedMemory: {
		id:          MetricHostUsedMemory,
		valueKind:   ValueInt,
		unit:        "%",
		description: "memory in use against the total fitted",
		template:    "supervisor/$HOST/$SCOPE/host/used_memory",
		persisted:   true,
		pulseRule:   Bounded(Self, AtMost, 95),
		trendRule:   Bounded(Self, AtMost, 90),
	},
	MetricHostAllocatedMemory: {
		id:           MetricHostAllocatedMemory,
		valueKind:    ValueInt,
		unit:         "%",
		description:  "memory ceilings of the installed services against the total fitted, capped at 100",
		template:     "supervisor/$HOST/$SCOPE/host/allocated_memory",
		persisted:    true,
		dependencies: []ID{MetricHostServicesMaxMemory},
		pulseRule:    Bounded(Self, AtMost, 95),
		trendRule:    Bounded(Self, AtMost, 90),
	},
	MetricHostFailedLogs: {
		id:          MetricHostFailedLogs,
		valueKind:   ValueInt,
		unit:        "%",
		description: fmt.Sprintf("kernel errors in the trend window against a %v message budget", FailedLogsBudget),
		template:    "supervisor/$HOST/$SCOPE/host/failed_log_messages",
		persisted:   true,
		pulseRule:   Bounded(Self, AtMost, FailedLogsPulseLimit),
		trendRule:   Bounded(Self, Exactly, 0),
	},
	MetricHostFailedShares: {
		id:          MetricHostFailedShares,
		valueKind:   ValueInt,
		unit:        "%",
		description: "declared shares failing to mount or report, against those declared",
		template:    "supervisor/$HOST/$SCOPE/host/failed_shares",
		persisted:   true,
		warming:     true,
		pulseRule:   Bounded(Self, Exactly, 0),
		trendRule:   Bounded(Self, Exactly, 0),
	},
	MetricHostFailedBackups: {
		id:          MetricHostFailedBackups,
		valueKind:   ValueInt,
		unit:        "",
		description: "backups failing to complete, not yet implemented",
		template:    "supervisor/$HOST/$SCOPE/host/failed_backups",
		persisted:   true,
		pulseRule:   Bounded(Self, Exactly, 0),
		trendRule:   Bounded(Self, Exactly, 0),
	},
	MetricHostWarnTemperature: {
		id:          MetricHostWarnTemperature,
		valueKind:   ValueInt,
		unit:        "%",
		description: fmt.Sprintf("hottest processor temperature against its warning ceiling, zero at %v and full at %v degrees", WarnTemperatureBaseCelsius, WarnTemperatureFullCelsius),
		template:    "supervisor/$HOST/$SCOPE/host/warn_temperature",
		persisted:   true,
		pulseRule:   Bounded(Self, AtMost, WarnTemperaturePulseLimit),
		trendRule:   Bounded(Self, AtMost, WarnTemperatureTrendLimit),
	},
	MetricHostSpinFanSpeed: {
		id:           MetricHostSpinFanSpeed,
		valueKind:    ValueInt,
		unit:         "%",
		description:  "fastest fan speed against its rated maximum",
		template:     "supervisor/$HOST/$SCOPE/host/spin_fan_speed",
		persisted:    true,
		dependencies: []ID{MetricHostWarnTemperature},
		pulseRule:    Any(Bounded(MetricHostWarnTemperature, AtMost, WarnTemperaturePulseLimit), Bounded(Self, Above, 80)),
		trendRule:    Any(Bounded(MetricHostWarnTemperature, AtMost, WarnTemperatureTrendLimit), Bounded(Self, Above, 50)),
	},
	MetricHostLifeUsedDrives: {
		id:           MetricHostLifeUsedDrives,
		valueKind:    ValueInt,
		unit:         "%",
		description:  "rated endurance consumed by the most worn drive",
		template:     "supervisor/$HOST/$SCOPE/host/life_used_drives",
		persisted:    true,
		warming:      true,
		dependencies: []ID{MetricHostFailedDrives},
		pulseRule:    All(Bounded(Self, AtMost, 90), Healthy(MetricHostFailedDrives)),
		trendRule:    All(Bounded(Self, AtMost, 80), Healthy(MetricHostFailedDrives)),
	},
	MetricHostUsedHomeSpace: {
		id:          MetricHostUsedHomeSpace,
		valueKind:   ValueInt,
		unit:        "%",
		description: "space used by the volume holding the module homes",
		template:    "supervisor/$HOST/$SCOPE/host/used_home_space",
		persisted:   true,
		warming:     true,
		pulseRule:   Bounded(Self, AtMost, 90),
		trendRule:   Bounded(Self, AtMost, 80),
	},
	MetricHostUsedShareSpace: {
		id:          MetricHostUsedShareSpace,
		valueKind:   ValueInt,
		unit:        "%",
		description: "space used across the local share volumes, summed as one pool",
		template:    "supervisor/$HOST/$SCOPE/host/used_share_space",
		persisted:   true,
		warming:     true,
		pulseRule:   Bounded(Self, AtMost, 90),
		trendRule:   Bounded(Self, AtMost, 80),
	},
	MetricHostUsedBackupSpace: {
		id:          MetricHostUsedBackupSpace,
		valueKind:   ValueInt,
		unit:        "%",
		description: "backup volume space used, not yet implemented",
		template:    "supervisor/$HOST/$SCOPE/host/used_backup_space",
		persisted:   true,
		pulseRule:   Bounded(Self, AtMost, 90),
		trendRule:   Bounded(Self, AtMost, 80),
	},
	MetricHostUsedSwapSpace: {
		id:          MetricHostUsedSwapSpace,
		valueKind:   ValueInt,
		unit:        "%",
		description: "swap space used, not yet implemented",
		template:    "supervisor/$HOST/$SCOPE/host/used_swap_space",
		persisted:   true,
		pulseRule:   Bounded(Self, AtMost, 80),
		trendRule:   Bounded(Self, AtMost, 70),
	},
	MetricHostUsedDiskOps: {
		id:          MetricHostUsedDiskOps,
		valueKind:   ValueInt,
		unit:        "%",
		description: "disk operations used against capacity, not yet implemented",
		template:    "supervisor/$HOST/$SCOPE/host/used_disk_ops",
		persisted:   true,
		pulseRule:   Bounded(Self, AtMost, 90),
		trendRule:   Bounded(Self, AtMost, 80),
	},
	MetricHostUsedNetwork: {
		id:          MetricHostUsedNetwork,
		valueKind:   ValueInt,
		unit:        "%",
		description: "network throughput used against capacity, not yet implemented",
		template:    "supervisor/$HOST/$SCOPE/host/used_network",
		persisted:   true,
		pulseRule:   Bounded(Self, AtMost, 90),
		trendRule:   Bounded(Self, AtMost, 80),
	},
	MetricHostRunningTime: {
		id:          MetricHostRunningTime,
		valueKind:   ValueFloat,
		unit:        "s",
		description: "time the host has been up, not yet implemented",
		template:    "supervisor/$HOST/$SCOPE/host/running_time",
		persisted:   false,
		pulseRule:   Always(),
	},
	MetricHostTemperature: {
		id:          MetricHostTemperature,
		valueKind:   ValueFloat,
		unit:        "°C",
		description: "hottest processor temperature, from the package, system on chip or offset drive sensor",
		template:    "supervisor/$HOST/$SCOPE/host/temperature",
		persisted:   true,
		pulseRule:   Bounded(Self, AtMost, 80),
		trendRule:   Bounded(Self, AtMost, 70),
	},
	MetricHostServices: {
		id:          MetricHostServices,
		valueKind:   ValueBool,
		unit:        "",
		description: "every configured service is running and healthy",
		template:    "supervisor/$HOST/$SCOPE/host/services",
		persisted:   false,
		pulseRule:   Truthy(),
		trendRule:   Truthy(),
	},
	MetricHostServicesMaxMemory: {
		id:          MetricHostServicesMaxMemory,
		valueKind:   ValueFloat,
		unit:        "MiB",
		description: "memory ceilings summed across the configured services",
		template:    "supervisor/$HOST/$SCOPE/host/services_max_memory",
		persisted:   false,
		pulseRule:   Always(),
	},
	MetricService: {
		id:          MetricService,
		valueKind:   ValueBool,
		unit:        "",
		description: "service is running and reporting metrics",
		template:    "supervisor/$HOST/$SCOPE/service/$SERVICE",
		persisted:   true,
		pulseRule:   Gated(GateServiceAggregate),
		trendRule:   Gated(GateServiceAggregate),
	},
	MetricServiceBackupStatus: {
		id:          MetricServiceBackupStatus,
		valueKind:   ValueBool,
		unit:        "",
		description: "service backup completed, always true until implemented",
		template:    "supervisor/$HOST/$SCOPE/service/$SERVICE/backup_status",
		persisted:   true,
		pulseRule:   Always(),
		trendRule:   Always(),
	},
	MetricServiceHealthStatus: {
		id:          MetricServiceHealthStatus,
		valueKind:   ValueBool,
		unit:        "",
		description: "service container healthcheck reported healthy",
		template:    "supervisor/$HOST/$SCOPE/service/$SERVICE/health_status",
		persisted:   true,
		pulseRule:   Truthy(),
		trendRule:   Truthy(),
	},
	MetricServiceConfiguredStatus: {
		id:          MetricServiceConfiguredStatus,
		valueKind:   ValueBool,
		unit:        "",
		description: "service is configured as expected, not yet implemented",
		template:    "supervisor/$HOST/$SCOPE/service/$SERVICE/configured_status",
		persisted:   true,
		pulseRule:   Truthy(),
		trendRule:   Truthy(),
	},
	MetricServiceName: {
		id:          MetricServiceName,
		valueKind:   ValueString,
		unit:        "",
		description: "service container name",
		template:    "supervisor/$HOST/$SCOPE/service/$SERVICE/name",
		persisted:   false,
		pulseRule:   Gated(GateServiceAggregate),
		trendRule:   Gated(GateServiceAggregate),
	},
	MetricServiceVersion: {
		id:          MetricServiceVersion,
		valueKind:   ValueString,
		unit:        "",
		description: "service version, from the container image tag or the installed environment",
		template:    "supervisor/$HOST/$SCOPE/service/$SERVICE/version",
		persisted:   false,
		pulseRule:   Gated(GateServiceAggregate),
		trendRule:   Gated(GateServiceAggregate),
	},
	MetricServiceUsedProcessor: {
		id:          MetricServiceUsedProcessor,
		valueKind:   ValueInt,
		unit:        "%",
		description: "processor time used by the service across all cores",
		template:    "supervisor/$HOST/$SCOPE/service/$SERVICE/used_processor",
		persisted:   true,
		pulseRule:   All(Gated(GateServiceAggregate), Bounded(Self, AtMost, 90)), trendRule: All(Gated(GateServiceAggregate), Bounded(Self, AtMost, 70)),
	},
	MetricServiceUsedMemory: {
		id:          MetricServiceUsedMemory,
		valueKind:   ValueInt,
		unit:        "%",
		description: "memory in use by the service, excluding page cache, against its ceiling",
		template:    "supervisor/$HOST/$SCOPE/service/$SERVICE/used_memory",
		persisted:   true,
		pulseRule:   All(Gated(GateServiceAggregate), Bounded(Self, AtMost, 90)), trendRule: All(Gated(GateServiceAggregate), Bounded(Self, AtMost, 75)),
	},
	MetricServiceUsedDiskOps: {
		id:          MetricServiceUsedDiskOps,
		valueKind:   ValueInt,
		unit:        "%",
		description: "disk operations used by the service, not yet implemented",
		template:    "supervisor/$HOST/$SCOPE/service/$SERVICE/used_disk_ops",
		persisted:   true,
		pulseRule:   All(Gated(GateServiceAggregate), Bounded(Self, AtMost, 90)), trendRule: All(Gated(GateServiceAggregate), Bounded(Self, AtMost, 80)),
	},
	MetricServiceUsedNetwork: {
		id:          MetricServiceUsedNetwork,
		valueKind:   ValueInt,
		unit:        "%",
		description: "network throughput used by the service, not yet implemented",
		template:    "supervisor/$HOST/$SCOPE/service/$SERVICE/used_network",
		persisted:   true,
		pulseRule:   All(Gated(GateServiceAggregate), Bounded(Self, AtMost, 90)), trendRule: All(Gated(GateServiceAggregate), Bounded(Self, AtMost, 80)),
	},
	MetricServiceUpTime: {
		id:          MetricServiceUpTime,
		valueKind:   ValueFloat,
		unit:        "s",
		description: "time the service container has been running",
		template:    "supervisor/$HOST/$SCOPE/service/$SERVICE/up_time",
		persisted:   false,
		pulseRule:   Gated(GateServiceAggregate),
		trendRule:   Gated(GateServiceAggregate),
	},
	MetricServiceMaxMemory: {
		id:          MetricServiceMaxMemory,
		valueKind:   ValueFloat,
		unit:        "MiB",
		description: "memory ceiling declared for the service in its compose file",
		template:    "supervisor/$HOST/$SCOPE/service/$SERVICE/max_memory",
		persisted:   false,
		pulseRule:   Always(),
	},
	MetricHostFailedDrives: {
		id:          MetricHostFailedDrives,
		valueKind:   ValueInt,
		unit:        "%",
		description: "drives reporting new errors since discovery, against those fitted",
		template:    "supervisor/$HOST/$SCOPE/host/failed_drives",
		persisted:   true,
		pulseRule:   Bounded(Self, Exactly, 0),
		trendRule:   Bounded(Self, Exactly, 0),
	},
	MetricServiceRestartCount: {
		id:          MetricServiceRestartCount,
		valueKind:   ValueFloat,
		unit:        "",
		description: "restarts of the service container since it was created",
		template:    "supervisor/$HOST/$SCOPE/service/$SERVICE/restart_count",
		persisted:   true,
		pulseRule:   All(Gated(GateServiceAggregate), Bounded(Self, AtMost, 80)), trendRule: All(Gated(GateServiceAggregate), Bounded(Self, AtMost, 70)),
	},
}

func buildFromID(id ID, hostName string, serviceName string, scope string) (string, map[string]string, error) {
	if id < ID(0) || id >= MetricMax {
		return "", nil, fmt.Errorf("invalid metric ID [%d]", id)
	}
	if hostName == "" {
		return "", nil, fmt.Errorf("cannot build metric ID [%d] without host", id)
	}
	if !patternToken.MatchString(hostName) {
		return "", nil, fmt.Errorf("cannot build metric ID [%d] with invalid host [%s]", id, hostName)
	}
	if scope != ScopeData && scope != ScopeMeta {
		return "", nil, fmt.Errorf("cannot build metric ID [%d] with invalid scope [%s]", id, scope)
	}
	metricBuilder := metricBuildersByID[id]
	replacer := strings.NewReplacer("$HOST", hostName, "$SCOPE", scope)
	if serviceName != ServiceNameUnset {
		if !patternToken.MatchString(serviceName) {
			return "", nil, fmt.Errorf("cannot build metric ID [%d] with invalid service [%s]", id, serviceName)
		}
		replacer = strings.NewReplacer("$HOST", hostName, "$SCOPE", scope, "$SERVICE", serviceName)
	}
	topic := replacer.Replace(metricBuilder.template)
	tags := map[string]string{}
	tags["host"] = hostName
	if serviceName != ServiceNameUnset {
		tags["service"] = serviceName
	}
	if !patternTopic.MatchString(topic) {
		return "", nil, fmt.Errorf("metric ID [%d] produced invalid topic [%s]", id, topic)
	}
	if !metricBuilder.persisted {
		tags = map[string]string{}
	} else {
		tags["metric"] = GetIDField(id)
	}
	return topic, tags, nil
}

func IDFromTopic(topic string) (ID, bool) {
	id, _, err := buildFromTopic(topic)
	if err != nil {
		return MetricMax, false
	}
	return id, true
}

func buildFromTopic(topic string) (ID, map[string]string, error) {
	if topic == "" {
		return MetricMax, nil, errors.New("invalid topic, empty string")
	}
	topicTokens := strings.Split(topic, "/")
	if len(topicTokens) < 4 {
		return MetricMax, nil, fmt.Errorf("invalid topic [%s]", topic)
	}
	if topicTokens[0] != "supervisor" {
		return MetricMax, nil, fmt.Errorf("invalid namespace [%s]", topicTokens[0])
	}
	service := ""
	metricIndex := 4
	entity := topicTokens[3]
	template := "supervisor/$HOST/$SCOPE/" + entity
	if entity == "service" && len(topicTokens) > 4 {
		service = topicTokens[4]
		template += "/$SERVICE"
		metricIndex = 5
	}
	if len(topicTokens) > metricIndex {
		template += "/" + strings.Join(topicTokens[metricIndex:], "/")
	}
	metricBuilder, found := metricBuildersByTemplate[template]
	if !found {
		return MetricMax, nil, fmt.Errorf("template [%s] not found in metricBuildersByTemplate", template)
	}
	tags := map[string]string{}
	if metricBuilder.persisted {
		if !patternToken.MatchString(topicTokens[1]) {
			return MetricMax, nil, fmt.Errorf("invalid host [%s]", topicTokens[1])
		}
		tags["host"] = topicTokens[1]
		if service != "" {
			if !patternToken.MatchString(service) {
				return MetricMax, nil, fmt.Errorf("invalid service [%s]", service)
			}
			tags["service"] = service
		}
		templateTokens := strings.Split(template, "/")
		metric := templateTokens[len(templateTokens)-1]
		switch metric {
		case "host", "service", "$SERVICE":
			tags["metric"] = "status"
		default:
			if !patternToken.MatchString(metric) {
				return MetricMax, nil, fmt.Errorf("invalid metric [%s]", metric)
			}
			tags["metric"] = metric
		}
	}
	return metricBuilder.id, tags, nil
}

var metricBuildersByTemplate = func() map[string]builder {
	if len(metricBuildersByID) != int(MetricMax) {
		panic(fmt.Sprintf("error: metricBuildersByID is incorrect length [%d], should use all (and only all) ID's (sans MetricMax) giving length [%d]",
			len(metricBuildersByID), MetricMax))
	}
	ids := make(map[ID]bool)
	templates := make(map[string]bool)
	builders := make(map[string]builder)
	for id := range MetricMax {
		if metricBuildersByID[id].id < ID(0) || metricBuildersByID[id].id >= MetricMax {
			panic(fmt.Sprintf("error: invalid metric ID [%d]", id))
		}
		if ids[metricBuildersByID[id].id] {
			panic(fmt.Sprintf("error: duplicate or missing metric ID [%d]", id))
		}
		ids[metricBuildersByID[id].id] = true
		if templates[metricBuildersByID[id].template] {
			panic(fmt.Sprintf("error: duplicate template [%s] for metric ID [%d]", metricBuildersByID[id].template, id))
		}
		templates[metricBuildersByID[id].template] = true
		if metricBuildersByID[id].template == "" {
			panic(fmt.Sprintf("error: invalid template [%s] for metric ID [%d]", metricBuildersByID[id].template, id))
		}
		if !patternTemplate.MatchString(metricBuildersByID[id].template) {
			panic(fmt.Sprintf("error: invalid template [%s] for metric ID [%d]", metricBuildersByID[id].template, id))
		}
		switch {
		case strings.HasPrefix(metricBuildersByID[id].template, "supervisor/$HOST/$SCOPE/service/supervisor"):
			metricBuildersByID[id].metricKind = MetricKindSupervisor
		case strings.HasPrefix(metricBuildersByID[id].template, "supervisor/$HOST/$SCOPE/services"):
			metricBuildersByID[id].metricKind = MetricKindServices
		case strings.HasPrefix(metricBuildersByID[id].template, "supervisor/$HOST/$SCOPE/service/"):
			metricBuildersByID[id].metricKind = MetricKindService
		case strings.HasPrefix(metricBuildersByID[id].template, "supervisor/$HOST/$SCOPE/host"):
			metricBuildersByID[id].metricKind = MetricKindHost
		default:
			panic(fmt.Sprintf("error: could not determine metric type from template [%s] for ID [%d]", metricBuildersByID[id].template, id))
		}
		if metricBuildersByID[id].warming && metricBuildersByID[id].metricKind == MetricKindService {
			panic(fmt.Sprintf("error: metric ID [%d] is service scoped and declares warming, which would stop the service refreshing", id))
		}
		if metricBuildersByID[id].pulseRule.IsZero() {
			panic(fmt.Sprintf("error: metric ID [%d] declares no pulseRule", id))
		}
		validateRule(metricBuildersByID[id], metricBuildersByID[id].pulseRule)
		if !metricBuildersByID[id].trendRule.IsZero() {
			validateRule(metricBuildersByID[id], metricBuildersByID[id].trendRule)
		}
		builders[metricBuildersByID[id].template] = metricBuildersByID[id]
	}
	return builders
}()

func validateRule(owner builder, rule Rule) {
	deps := make(map[ID]bool, len(owner.dependencies))
	for _, dep := range owner.dependencies {
		if dep == Self {
			panic(fmt.Sprintf("error: metric ID [%d] lists [Self] in dependencies", owner.id))
		}
		deps[dep] = true
	}
	for _, target := range rule.Siblings() {
		if target < 0 || target >= MetricMax {
			panic(fmt.Sprintf("error: metric ID [%d] rule reads unknown metric ID [%d]", owner.id, target))
		}
		if !deps[target] {
			panic(fmt.Sprintf("error: metric ID [%d] rule reads metric ID [%d] which is not listed in dependencies", owner.id, target))
		}
	}
	for _, target := range rule.Targets() {
		kind := owner.valueKind
		if target != Self {
			kind = metricBuildersByID[target].valueKind
		}
		if kind == ValueBool || kind == ValueString {
			panic(fmt.Sprintf("error: metric ID [%d] declares a bounded rule against a [%s] valued metric", owner.id, kind))
		}
	}
}

var (
	templateCommand  = "supervisor/$HOST/command"
	templateSnapshot = "supervisor/$HOST/snapshot"
)

var (
	patternToken    = regexp.MustCompile(`^[a-z0-9-_]+$`)
	patternTemplate = regexp.MustCompile(`^supervisor/\$HOST(/(command|snapshot)|/\$SCOPE/(host|services|service(/[^/]+)?)(/[A-Za-z0-9_]+)*)$`)
	patternTopic    = regexp.MustCompile(`^supervisor/[a-z0-9-_]+(/(command|snapshot)|/(meta|data)/(host|services|service(/[a-z0-9-_]+)?)(/[a-z0-9-_]+)*)$`)
)
