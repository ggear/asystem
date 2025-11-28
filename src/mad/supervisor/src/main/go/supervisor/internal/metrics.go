package internal

import (
	"fmt"
	"regexp"
	"sort"
	"strconv"
	"strings"
)

type metricEnum int

const (
	METRIC_MIN metricEnum = iota
	metricHost
	metricHostCompute
	metricHostComputeUsedProcessor
	metricHostComputeUsedMemory
	metricHostComputeAllocatedMemory
	metricHostHealth
	metricHostHealthFailedServices
	metricHostHealthFailedShares
	metricHostHealthFailedBackups
	metricHostRuntime
	metricHostRuntimePeakTemperatureMax
	metricHostRuntimePeakFanSpeedMax
	metricHostRuntimeLifeUsedDrives
	metricHostStorage
	metricHostStorageUsedSystemDrive
	metricHostStorageUsedShareDrives
	metricHostStorageUsedBackupDrives
	metricService
	metricServiceName
	metricServiceVersion
	metricServiceUsedProcessor
	metricServiceUsedMemory
	metricServiceBackupStatus
	metricServiceConfiguredStatus
	metricServiceRestartCount
	metricServiceRuntime
	METRIC_MAX
)

func (m metricEnum) isValid() bool {
	return m > METRIC_MIN && m < METRIC_MAX
}

var metricBuilders = [METRIC_MAX]metricBuilder{
	metricHost: {
		topicBuilder{
			metricID: metricHost,
			template: "supervisor/$HOSTNAME/host",
		},
		func(period int, serviceName string) metricValue {
			return metricValue{ok: true}
		},
	},
	metricHostCompute: {
		topicBuilder{
			metricID: metricHostCompute,
			template: "supervisor/$HOSTNAME/host/compute",
		},
		func(period int, serviceName string) metricValue {
			return metricValue{ok: true}
		},
	},
	metricHostComputeUsedProcessor: {
		topicBuilder{
			metricID: metricHostComputeUsedProcessor,
			template: "supervisor/$HOSTNAME/host/compute/used_processor",
		},
		func(period int, serviceName string) metricValue {
			return metricValue{ok: true, unit: "%", value: "10"}
		},
	},
	metricHostComputeUsedMemory: {
		topicBuilder{
			metricID: metricHostComputeUsedMemory,
			template: "supervisor/$HOSTNAME/host/compute/used_memory",
		},
		func(period int, serviceName string) metricValue {
			return metricValue{ok: true, unit: "%", value: "10"}
		},
	},
	metricHostComputeAllocatedMemory: {
		topicBuilder{
			metricID: metricHostComputeAllocatedMemory,
			template: "supervisor/$HOSTNAME/host/compute/allocated_memory",
		},
		func(period int, serviceName string) metricValue {
			return metricValue{ok: true, unit: "GB", value: "10"}
		},
	},
	metricHostHealth: {
		topicBuilder{
			metricID: metricHostHealth,
			template: "supervisor/$HOSTNAME/host/health",
		},
		func(period int, serviceName string) metricValue {
			return metricValue{ok: true}
		},
	},
	metricHostHealthFailedServices: {
		topicBuilder{
			metricID: metricHostHealthFailedServices,
			template: "supervisor/$HOSTNAME/host/health/failed_services",
		},
		func(period int, serviceName string) metricValue {
			return metricValue{ok: true, unit: "", value: "10"}
		},
	},
	metricHostHealthFailedShares: {
		topicBuilder{
			metricID: metricHostHealthFailedShares,
			template: "supervisor/$HOSTNAME/host/health/failed_shares",
		},
		func(period int, serviceName string) metricValue {
			return metricValue{ok: true, unit: "", value: "10"}
		},
	},
	metricHostHealthFailedBackups: {
		topicBuilder{
			metricID: metricHostHealthFailedBackups,
			template: "supervisor/$HOSTNAME/host/health/failed_backups",
		},
		func(period int, serviceName string) metricValue {
			return metricValue{ok: true, unit: "", value: "10"}
		},
	},
	metricHostRuntime: {
		topicBuilder{
			metricID: metricHostRuntime,
			template: "supervisor/$HOSTNAME/host/runtime",
		},
		func(period int, serviceName string) metricValue {
			return metricValue{ok: true}
		},
	},
	metricHostRuntimePeakTemperatureMax: {
		topicBuilder{
			metricID: metricHostRuntimePeakTemperatureMax,
			template: "supervisor/$HOSTNAME/host/runtime/peak_temperature_max",
		},
		func(period int, serviceName string) metricValue {
			return metricValue{ok: true, unit: "°C", value: "10"}
		},
	},
	metricHostRuntimePeakFanSpeedMax: {
		topicBuilder{
			metricID: metricHostRuntimePeakFanSpeedMax,
			template: "supervisor/$HOSTNAME/host/runtime/peak_fan_speed_max",
		},
		func(period int, serviceName string) metricValue {
			return metricValue{ok: true, unit: "RPM", value: "10"}
		},
	},
	metricHostRuntimeLifeUsedDrives: {
		topicBuilder{
			metricID: metricHostRuntimeLifeUsedDrives,
			template: "supervisor/$HOSTNAME/host/runtime/life_used_drives",
		},
		func(period int, serviceName string) metricValue {
			return metricValue{ok: true, unit: "%", value: "10"}
		},
	},
	metricHostStorage: {
		topicBuilder{
			metricID: metricHostStorage,
			template: "supervisor/$HOSTNAME/host/storage",
		},
		func(period int, serviceName string) metricValue {
			return metricValue{ok: true}
		},
	},
	metricHostStorageUsedSystemDrive: {
		topicBuilder{
			metricID: metricHostStorageUsedSystemDrive,
			template: "supervisor/$HOSTNAME/host/storage/used_system_drive",
		},
		func(period int, serviceName string) metricValue {
			return metricValue{ok: true, unit: "%", value: "10"}
		},
	},
	metricHostStorageUsedShareDrives: {
		topicBuilder{
			metricID: metricHostStorageUsedShareDrives,
			template: "supervisor/$HOSTNAME/host/storage/used_share_drives",
		},
		func(period int, serviceName string) metricValue {
			return metricValue{ok: true, unit: "%", value: "10"}
		},
	},
	metricHostStorageUsedBackupDrives: {
		topicBuilder{
			metricID: metricHostStorageUsedBackupDrives,
			template: "supervisor/$HOSTNAME/host/storage/used_backup_drives",
		},
		func(period int, serviceName string) metricValue {
			return metricValue{ok: true, unit: "%", value: "10"}
		},
	},
	metricService: {
		topicBuilder{
			metricID: metricService,
			template: "supervisor/$HOSTNAME/service",
		},
		func(period int, serviceName string) metricValue {
			return metricValue{ok: true}
		},
	},
	metricServiceName: {
		topicBuilder{
			metricID: metricServiceName,
			template: "supervisor/$HOSTNAME/service/$SERVICENAME/name",
		},
		func(period int, serviceName string) metricValue {
			return metricValue{ok: true, value: serviceName}
		},
	},
	metricServiceVersion: {
		topicBuilder{
			metricID: metricServiceVersion,
			template: "supervisor/$HOSTNAME/service/$SERVICENAME/version",
		},
		func(period int, serviceName string) metricValue {
			return metricValue{ok: true, value: "1.0.0"}
		},
	},
	metricServiceUsedProcessor: {
		topicBuilder{
			metricID: metricServiceUsedProcessor,
			template: "supervisor/$HOSTNAME/service/$SERVICENAME/used_processor",
		},
		func(period int, serviceName string) metricValue {
			return metricValue{ok: true, unit: "%", value: "10"}
		},
	},
	metricServiceUsedMemory: {
		topicBuilder{
			metricID: metricServiceUsedMemory,
			template: "supervisor/$HOSTNAME/service/$SERVICENAME/used_memory",
		},
		func(period int, serviceName string) metricValue {
			return metricValue{ok: true, unit: "MB", value: "256"}
		},
	},
	metricServiceBackupStatus: {
		topicBuilder{
			metricID: metricServiceBackupStatus,
			template: "supervisor/$HOSTNAME/service/$SERVICENAME/backup_status",
		},
		func(period int, serviceName string) metricValue {
			return metricValue{ok: true, value: "1"}
		},
	},
	metricServiceConfiguredStatus: {
		topicBuilder{
			metricID: metricServiceConfiguredStatus,
			template: "supervisor/$HOSTNAME/service/$SERVICENAME/configured_status",
		},
		func(period int, serviceName string) metricValue {
			return metricValue{ok: true, value: "true"}
		},
	},
	metricServiceRestartCount: {
		topicBuilder{
			metricID: metricServiceRestartCount,
			template: "supervisor/$HOSTNAME/service/$SERVICENAME/restart_count",
		},
		func(period int, serviceName string) metricValue {
			return metricValue{ok: true, value: "0"}
		},
	},
	metricServiceRuntime: {
		topicBuilder{
			metricID: metricServiceRuntime,
			template: "supervisor/$HOSTNAME/service/$SERVICENAME/runtime",
		},
		func(period int, serviceName string) metricValue {
			return metricValue{ok: true, unit: "s", value: "3600"}
		},
	},
}

func CacheMetrics(hostname string, schemaPath string) (map[string]*metricRecord, error) {

	// TODO: How to present topic/index/row-col mapped metric to display
	// TODO: -> Return Map keyed by metricRecordGUID, update sort, getServiceIndexRange
	// TODO: How to reload for new or removed services
	// TODO: -> onChange triggered by value and or serviceIndex change
	//       -> input metricRecordMap, if null load for first time, otherwise use for onchnage
	//       -> have display work out if a service has been deleted and not replaced, to nil out display

	if hostname == "" {
		return nil, fmt.Errorf("hostname not defined")
	}
	serviceNameSlice, err := GetServices(hostname, schemaPath)
	if err != nil {
		return nil, err
	}
	metricRecordMap := make(map[string]*metricRecord)
	for index := 1; index <= len(metricBuilders)-1; index++ {
		if !metricBuilders[index].topicBuilder.metricID.isValid() {
			return nil, fmt.Errorf("metric builder [%d] has invalid metric ID [%d]", index, metricBuilders[index].topicBuilder.metricID)
		}
		if metricBuilders[index].topicBuilder.template == "" {
			return nil, fmt.Errorf("metric builder [%d] has empty template string", index)
		}
		if metricBuilders[index].load == nil {
			return nil, fmt.Errorf("metric builder [%d] has empty load function", index)
		}
		if metricBuilders[index].topicBuilder.isHost() {
			topic, err := metricBuilders[index].topicBuilder.buildHost(hostname)
			if err != nil {
				return nil, fmt.Errorf("host topic build error: %w", err)
			}
			metricRecordMap[fmt.Sprintf("%d", metricBuilders[index].topicBuilder.metricID)] =
				&metricRecord{topic: topic, load: metricBuilders[index].load}
		} else {
			for serviceIndex, serviceName := range serviceNameSlice {
				topic, err := metricBuilders[index].topicBuilder.buildService(hostname, serviceName)
				if err != nil {
					return nil, fmt.Errorf("service topic build error: %w", err)
				}
				metricRecordMap[fmt.Sprintf("%d_%d", metricBuilders[index].topicBuilder.metricID, serviceIndex)] =
					&metricRecord{topic: topic, load: metricBuilders[index].load}
			}
		}
	}
	return metricRecordMap, nil
}

func SortMetricIDs(metricRecords map[string]*metricRecord) []string {
	keys := make([]string, 0, len(metricRecords))
	for key := range metricRecords {
		keys = append(keys, key)
	}
	sort.Slice(keys, func(i, j int) bool {
		keyA, keyB := keys[i], keys[j]
		partsA, partsB := strings.Split(keyA, "_"), strings.Split(keyB, "_")
		if len(partsA) == 1 && len(partsB) > 1 {
			return true
		}
		if len(partsA) > 1 && len(partsB) == 1 {
			return false
		}
		numberA, _ := strconv.Atoi(partsA[0])
		numberB, _ := strconv.Atoi(partsB[0])
		if len(partsA) == 1 && len(partsB) == 1 {
			return numberA < numberB
		}
		subNumberA, _ := strconv.Atoi(partsA[1])
		subNumberB, _ := strconv.Atoi(partsB[1])
		if subNumberA != subNumberB {
			return subNumberA < subNumberB
		}
		return numberA < numberB
	})
	return keys
}

type metricBuilder struct {
	topicBuilder topicBuilder
	load         func(int, string) metricValue
}

type metricRecordGUID struct {
	metricID     metricEnum
	serviceIndex int
	isService    bool
}

type metricRecord struct {
	topic    string
	value    metricValue
	load     func(int, string) metricValue
	onChange func(previous, current metricValue)
}

type metricValue struct {
	ok    bool   `json:"ok"`
	unit  string `json:"unit,omitempty"`
	value string `json:"value,omitempty"`
}

type topicBuilder struct {
	metricID metricEnum
	template string
}

func (tb *topicBuilder) build(replacements map[string]string) (string, error) {
	if !regexp.MustCompile(`^supervisor(/[a-zA-Z0-9$_-]+){2,4}$`).MatchString(tb.template) {
		return "", fmt.Errorf("invalid topic template [%s]", tb.template)
	}
	pairs := make([]string, 0, len(replacements)*2)
	for key, value := range replacements {
		pairs = append(pairs, "$"+key, value)
	}
	replacer := strings.NewReplacer(pairs...)
	result := replacer.Replace(tb.template)
	if strings.Contains(result, "$") {
		return "", fmt.Errorf("invalid $TOKEN in template [%s]", result)
	}
	return result, nil
}

func (tb *topicBuilder) isHost() bool {
	return strings.Contains(tb.template, "$HOSTNAME") && !strings.Contains(tb.template, "$SERVICENAME")
}

func (tb *topicBuilder) isService() bool {
	return strings.Contains(tb.template, "$HOSTNAME") && strings.Contains(tb.template, "$SERVICENAME")
}

func (tb *topicBuilder) buildHost(hostname string) (string, error) {
	return tb.build(map[string]string{"HOSTNAME": hostname})
}

func (tb *topicBuilder) buildService(hostname string, servicename string) (string, error) {
	return tb.build(map[string]string{"HOSTNAME": hostname, "SERVICENAME": servicename})
}
