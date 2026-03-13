package metric

import (
	"errors"
	"fmt"
	"regexp"
	"strings"
)

type builder struct {
	id       ID
	template string
	skipHist bool
	kind     MetricKind
	deps     []ID
}

var metricBuildersByID = []builder{
	MetricHost: {
		id:       MetricHost,
		template: "supervisor/$HOST/$SCOPE/host",
	},
	MetricHostUsedProcessor: {
		id:       MetricHostUsedProcessor,
		template: "supervisor/$HOST/$SCOPE/host/used_processor",
	},
	MetricHostUsedMemory: {
		id:       MetricHostUsedMemory,
		template: "supervisor/$HOST/$SCOPE/host/used_memory",
	},
	MetricHostAllocatedMemory: {
		id:       MetricHostAllocatedMemory,
		template: "supervisor/$HOST/$SCOPE/host/allocated_memory",
		deps:     []ID{MetricServicesMaxMemory},
	},
	MetricHostFailedLogs: {
		id:       MetricHostFailedLogs,
		template: "supervisor/$HOST/$SCOPE/host/failed_log_messages",
	},
	MetricHostFailedShares: {
		id:       MetricHostFailedShares,
		template: "supervisor/$HOST/$SCOPE/host/failed_shares",
	},
	MetricHostFailedBackups: {
		id:       MetricHostFailedBackups,
		template: "supervisor/$HOST/$SCOPE/host/failed_backups",
	},
	MetricHostWarnTemperatureOfMax: {
		id:       MetricHostWarnTemperatureOfMax,
		template: "supervisor/$HOST/$SCOPE/host/warn_temperature_of_max",
	},
	MetricHostSpinFanSpeedOfMax: {
		id:       MetricHostSpinFanSpeedOfMax,
		template: "supervisor/$HOST/$SCOPE/host/spin_fan_speed_of_max",
	},
	MetricHostLifeUsedDrives: {
		id:       MetricHostLifeUsedDrives,
		template: "supervisor/$HOST/$SCOPE/host/life_used_drives",
	},
	MetricHostUsedSystemSpace: {
		id:       MetricHostUsedSystemSpace,
		template: "supervisor/$HOST/$SCOPE/host/used_system_space",
	},
	MetricHostUsedShareSpace: {
		id:       MetricHostUsedShareSpace,
		template: "supervisor/$HOST/$SCOPE/host/used_share_space",
	},
	MetricHostUsedBackupSpace: {
		id:       MetricHostUsedBackupSpace,
		template: "supervisor/$HOST/$SCOPE/host/used_backup_space",
	},
	MetricHostUsedSwapSpace: {
		id:       MetricHostUsedSwapSpace,
		template: "supervisor/$HOST/$SCOPE/host/used_swap_space",
	},
	MetricHostUsedDiskOps: {
		id:       MetricHostUsedDiskOps,
		template: "supervisor/$HOST/$SCOPE/host/used_disk_ops",
	},
	MetricHostUsedNetwork: {
		id:       MetricHostUsedNetwork,
		template: "supervisor/$HOST/$SCOPE/host/used_network",
	},
	MetricHostRunningTime: {
		id:       MetricHostRunningTime,
		template: "supervisor/$HOST/$SCOPE/host/running_time",
		skipHist: true,
	},
	MetricHostTemperature: {
		id:       MetricHostTemperature,
		template: "supervisor/$HOST/$SCOPE/host/temperature",
	},
	MetricServices: {
		id:       MetricServices,
		template: "supervisor/$HOST/$SCOPE/services",
		skipHist: true,
	},
	MetricServicesMaxMemory: {
		id:       MetricServicesMaxMemory,
		template: "supervisor/$HOST/$SCOPE/services/max_memory",
		skipHist: true,
	},
	MetricService: {
		id:       MetricService,
		template: "supervisor/$HOST/$SCOPE/service/$SERVICE",
	},
	MetricServiceBackupStatus: {
		id:       MetricServiceBackupStatus,
		template: "supervisor/$HOST/$SCOPE/service/$SERVICE/backup_status",
	},
	MetricServiceHealthStatus: {
		id:       MetricServiceHealthStatus,
		template: "supervisor/$HOST/$SCOPE/service/$SERVICE/health_status",
	},
	MetricServiceConfiguredStatus: {
		id:       MetricServiceConfiguredStatus,
		template: "supervisor/$HOST/$SCOPE/service/$SERVICE/configured_status",
	},
	MetricServiceName: {
		id:       MetricServiceName,
		template: "supervisor/$HOST/$SCOPE/service/$SERVICE/name",
		skipHist: true,
	},
	MetricServiceVersion: {
		id:       MetricServiceVersion,
		template: "supervisor/$HOST/$SCOPE/service/$SERVICE/version",
		skipHist: true,
	},
	MetricServiceUsedProcessor: {
		id:       MetricServiceUsedProcessor,
		template: "supervisor/$HOST/$SCOPE/service/$SERVICE/used_processor",
	},
	MetricServiceUsedMemory: {
		id:       MetricServiceUsedMemory,
		template: "supervisor/$HOST/$SCOPE/service/$SERVICE/used_memory",
	},
	MetricServiceUsedDiskOps: {
		id:       MetricServiceUsedDiskOps,
		template: "supervisor/$HOST/$SCOPE/service/$SERVICE/used_disk_ops",
	},
	MetricServiceUsedNetwork: {
		id:       MetricServiceUsedNetwork,
		template: "supervisor/$HOST/$SCOPE/service/$SERVICE/used_network",
	},
	MetricServiceRunningTime: {
		id:       MetricServiceRunningTime,
		template: "supervisor/$HOST/$SCOPE/service/$SERVICE/running_time",
		skipHist: true,
	},
	MetricServiceMaxMemory: {
		id:       MetricServiceMaxMemory,
		template: "supervisor/$HOST/$SCOPE/service/$SERVICE/max_memory",
		skipHist: true,
	},
	MetricServiceRestartCount: {
		id:       MetricServiceRestartCount,
		template: "supervisor/$HOST/$SCOPE/service/$SERVICE/restart_count",
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
	if scope != "data" && scope != "meta" {
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
	if metricBuilder.skipHist {
		tags = map[string]string{}
	} else {
		templateTokens := strings.Split(metricBuilder.template, "/")
		metric := templateTokens[len(templateTokens)-1]
		switch metric {
		case "host", "service", "$SERVICE":
			tags["metric"] = "status"
		default:
			tags["metric"] = metric
		}
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
	if !metricBuilder.skipHist {
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
			metricBuildersByID[id].kind = MetricKindSupervisor
		case strings.HasPrefix(metricBuildersByID[id].template, "supervisor/$HOST/$SCOPE/services"):
			metricBuildersByID[id].kind = MetricKindServices
		case strings.HasPrefix(metricBuildersByID[id].template, "supervisor/$HOST/$SCOPE/service/"):
			metricBuildersByID[id].kind = MetricKindService
		case strings.HasPrefix(metricBuildersByID[id].template, "supervisor/$HOST/$SCOPE/host"):
			metricBuildersByID[id].kind = MetricKindHost
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
