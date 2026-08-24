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
	skipDatabase bool
	dependencies []ID
}

var metricBuildersByID = []builder{
	MetricHost: {
		id:          MetricHost,
		valueKind:   ValueBool,
		unit:        "",
		description: "host is reporting metrics",
		template:    "supervisor/$HOST/$SCOPE/host",
	},
	MetricHostUsedProcessor: {
		id:          MetricHostUsedProcessor,
		valueKind:   ValueInt,
		unit:        "%",
		description: "processor time used across all cores of the host",
		template:    "supervisor/$HOST/$SCOPE/host/used_processor",
	},
	MetricHostUsedMemory: {
		id:          MetricHostUsedMemory,
		valueKind:   ValueInt,
		unit:        "%",
		description: "memory in use as a percentage of the total memory of the host",
		template:    "supervisor/$HOST/$SCOPE/host/used_memory",
	},
	MetricHostAllocatedMemory: {
		id:           MetricHostAllocatedMemory,
		valueKind:    ValueInt,
		unit:         "%",
		description:  "memory ceilings of the installed services as a percentage of the total memory of the host, capped at one hundred",
		template:     "supervisor/$HOST/$SCOPE/host/allocated_memory",
		dependencies: []ID{MetricHostServicesMaxMemory},
	},
	MetricHostFailedLogs: {
		id:          MetricHostFailedLogs,
		valueKind:   ValueInt,
		unit:        "%",
		description: "kernel log messages at error level within the trend window, as a percentage of a ten message budget",
		template:    "supervisor/$HOST/$SCOPE/host/failed_log_messages",
	},
	MetricHostFailedShares: {
		id:          MetricHostFailedShares,
		valueKind:   ValueInt,
		unit:        "%",
		description: "declared shares failing to mount or report, as a percentage of those defined",
		template:    "supervisor/$HOST/$SCOPE/host/failed_shares",
	},
	MetricHostFailedBackups: {
		id:          MetricHostFailedBackups,
		valueKind:   ValueInt,
		unit:        "",
		description: "backups failing to complete, not yet implemented and always zero",
		template:    "supervisor/$HOST/$SCOPE/host/failed_backups",
	},
	MetricHostWarnTemperatureOfMax: {
		id:          MetricHostWarnTemperatureOfMax,
		valueKind:   ValueInt,
		unit:        "%",
		description: "hottest processor temperature as a percentage of its warning ceiling, zero at forty degrees and full at sixty degrees",
		template:    "supervisor/$HOST/$SCOPE/host/warn_temperature_of_max",
	},
	MetricHostSpinFanSpeedOfMax: {
		id:          MetricHostSpinFanSpeedOfMax,
		valueKind:   ValueInt,
		unit:        "%",
		description: "fastest fan speed as a percentage of its rated maximum speed",
		template:    "supervisor/$HOST/$SCOPE/host/spin_fan_speed_of_max",
	},
	MetricHostLifeUsedDrives: {
		id:          MetricHostLifeUsedDrives,
		valueKind:   ValueInt,
		unit:        "%",
		description: "rated endurance consumed by the most worn drive, not ok when any drive reports new errors",
		template:    "supervisor/$HOST/$SCOPE/host/life_used_drives",
	},
	MetricHostUsedSystemSpace: {
		id:          MetricHostUsedSystemSpace,
		valueKind:   ValueInt,
		unit:        "%",
		description: "space used by the fullest system volume of the host",
		template:    "supervisor/$HOST/$SCOPE/host/used_system_space",
	},
	MetricHostUsedShareSpace: {
		id:          MetricHostUsedShareSpace,
		valueKind:   ValueInt,
		unit:        "%",
		description: "space used across the local share volumes of the host, summed as one pool",
		template:    "supervisor/$HOST/$SCOPE/host/used_share_space",
	},
	MetricHostUsedBackupSpace: {
		id:          MetricHostUsedBackupSpace,
		valueKind:   ValueInt,
		unit:        "%",
		description: "backup volume space used, not yet implemented and always zero",
		template:    "supervisor/$HOST/$SCOPE/host/used_backup_space",
	},
	MetricHostUsedSwapSpace: {
		id:          MetricHostUsedSwapSpace,
		valueKind:   ValueInt,
		unit:        "%",
		description: "swap space used, not yet implemented and always zero",
		template:    "supervisor/$HOST/$SCOPE/host/used_swap_space",
	},
	MetricHostUsedDiskOps: {
		id:          MetricHostUsedDiskOps,
		valueKind:   ValueInt,
		unit:        "%",
		description: "disk operations used against capacity, not yet implemented and always zero",
		template:    "supervisor/$HOST/$SCOPE/host/used_disk_ops",
	},
	MetricHostUsedNetwork: {
		id:          MetricHostUsedNetwork,
		valueKind:   ValueInt,
		unit:        "%",
		description: "network throughput used against capacity, not yet implemented and always zero",
		template:    "supervisor/$HOST/$SCOPE/host/used_network",
	},
	MetricHostRunningTime: {
		id:           MetricHostRunningTime,
		valueKind:    ValueFloat,
		unit:         "s",
		description:  "time the host has been up, not yet implemented and always zero",
		template:     "supervisor/$HOST/$SCOPE/host/running_time",
		skipDatabase: true,
	},
	MetricHostTemperature: {
		id:          MetricHostTemperature,
		valueKind:   ValueFloat,
		unit:        "°C",
		description: "hottest processor temperature, from the package sensor, the system on chip sensor or a drive sensor offset upwards",
		template:    "supervisor/$HOST/$SCOPE/host/temperature",
	},
	MetricHostServices: {
		id:           MetricHostServices,
		valueKind:    ValueBool,
		unit:         "",
		description:  "every service configured for the host is running and healthy",
		template:     "supervisor/$HOST/$SCOPE/host/services",
		skipDatabase: true,
	},
	MetricHostServicesMaxMemory: {
		id:           MetricHostServicesMaxMemory,
		valueKind:    ValueFloat,
		unit:         "MiB",
		description:  "memory ceilings summed across the installed services configured for the host",
		template:     "supervisor/$HOST/$SCOPE/host/services_max_memory",
		skipDatabase: true,
	},
	MetricService: {
		id:          MetricService,
		valueKind:   ValueBool,
		unit:        "",
		description: "service is running and reporting metrics",
		template:    "supervisor/$HOST/$SCOPE/service/$SERVICE",
	},
	MetricServiceBackupStatus: {
		id:          MetricServiceBackupStatus,
		valueKind:   ValueBool,
		unit:        "",
		description: "service backup completed, not yet implemented and always true",
		template:    "supervisor/$HOST/$SCOPE/service/$SERVICE/backup_status",
	},
	MetricServiceHealthStatus: {
		id:          MetricServiceHealthStatus,
		valueKind:   ValueBool,
		unit:        "",
		description: "service container healthcheck reported healthy",
		template:    "supervisor/$HOST/$SCOPE/service/$SERVICE/health_status",
	},
	MetricServiceConfiguredStatus: {
		id:          MetricServiceConfiguredStatus,
		valueKind:   ValueBool,
		unit:        "",
		description: "service is configured as expected, not yet implemented and always false",
		template:    "supervisor/$HOST/$SCOPE/service/$SERVICE/configured_status",
	},
	MetricServiceName: {
		id:           MetricServiceName,
		valueKind:    ValueString,
		unit:         "",
		description:  "service container name",
		template:     "supervisor/$HOST/$SCOPE/service/$SERVICE/name",
		skipDatabase: true,
	},
	MetricServiceVersion: {
		id:           MetricServiceVersion,
		valueKind:    ValueString,
		unit:         "",
		description:  "service version, from the container image tag or the installed environment",
		template:     "supervisor/$HOST/$SCOPE/service/$SERVICE/version",
		skipDatabase: true,
	},
	MetricServiceUsedProcessor: {
		id:          MetricServiceUsedProcessor,
		valueKind:   ValueInt,
		unit:        "%",
		description: "processor time used by the service across all cores of the host",
		template:    "supervisor/$HOST/$SCOPE/service/$SERVICE/used_processor",
	},
	MetricServiceUsedMemory: {
		id:          MetricServiceUsedMemory,
		valueKind:   ValueInt,
		unit:        "%",
		description: "memory in use by the service, excluding page cache, as a percentage of its ceiling",
		template:    "supervisor/$HOST/$SCOPE/service/$SERVICE/used_memory",
	},
	MetricServiceUsedDiskOps: {
		id:          MetricServiceUsedDiskOps,
		valueKind:   ValueInt,
		unit:        "%",
		description: "disk operations used by the service, not yet implemented and always zero",
		template:    "supervisor/$HOST/$SCOPE/service/$SERVICE/used_disk_ops",
	},
	MetricServiceUsedNetwork: {
		id:          MetricServiceUsedNetwork,
		valueKind:   ValueInt,
		unit:        "%",
		description: "network throughput used by the service, not yet implemented and always zero",
		template:    "supervisor/$HOST/$SCOPE/service/$SERVICE/used_network",
	},
	MetricServiceUpTime: {
		id:           MetricServiceUpTime,
		valueKind:    ValueFloat,
		unit:         "s",
		description:  "time the service container has been running",
		template:     "supervisor/$HOST/$SCOPE/service/$SERVICE/up_time",
		skipDatabase: true,
	},
	MetricServiceMaxMemory: {
		id:           MetricServiceMaxMemory,
		valueKind:    ValueFloat,
		unit:         "MiB",
		description:  "memory ceiling declared for the service in its compose file",
		template:     "supervisor/$HOST/$SCOPE/service/$SERVICE/max_memory",
		skipDatabase: true,
	},
	MetricServiceRestartCount: {
		id:          MetricServiceRestartCount,
		valueKind:   ValueFloat,
		unit:        "",
		description: "restarts of the service container since it was created",
		template:    "supervisor/$HOST/$SCOPE/service/$SERVICE/restart_count",
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
	if metricBuilder.skipDatabase {
		tags = map[string]string{}
	} else {
		tags["metric"] = GetIDField(id)
	}
	return topic, tags, nil
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
	if !metricBuilder.skipDatabase {
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
	for id := ID(0); id < MetricMax; id++ {
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
		builders[metricBuildersByID[id].template] = metricBuildersByID[id]
	}
	return builders
}()

var (
	templateCommand  = "supervisor/$HOST/command"
	templateSnapshot = "supervisor/$HOST/snapshot"
)

var (
	patternToken    = regexp.MustCompile(`^[a-z0-9-_]+$`)
	patternTemplate = regexp.MustCompile(`^supervisor/\$HOST(/(command|snapshot)|/\$SCOPE/(host|services|service(/[^/]+)?)(/[A-Za-z0-9_]+)*)$`)
	patternTopic    = regexp.MustCompile(`^supervisor/[a-z0-9-_]+(/(command|snapshot)|/(meta|data)/(host|services|service(/[a-z0-9-_]+)?)(/[a-z0-9-_]+)*)$`)
)
