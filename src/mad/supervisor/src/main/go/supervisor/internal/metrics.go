package internal

import (
	"fmt"
	"regexp"
	"strings"
	"time"

	"github.com/emirpasic/gods/maps/treemap"
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
	time     time.Time
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

type metricRecordCache struct {
	treeMap *treemap.Map
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
			return metricValue{ok: true, unit: "%", value: "10"}
		},
	},
	metricHostRuntimePeakFanSpeedMax: {
		topicBuilder{
			metricID: metricHostRuntimePeakFanSpeedMax,
			template: "supervisor/$HOSTNAME/host/runtime/peak_fan_speed_max",
		},
		func(period int, serviceName string) metricValue {
			return metricValue{ok: true, unit: "%", value: "10"}
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

func newMetricRecordCache() *metricRecordCache {
	return &metricRecordCache{
		treeMap: treemap.NewWith(metricRecordGUIDComparator),
	}
}

func CacheMetrics(hostName string, schemaPath string) (*metricRecordCache, error) {

	// TODO: How to reload for new or removed services
	// TODO: -> onChange triggered by value and or serviceIndex change
	//       -> input metricCache, if null load for first time, otherwise use for onchnage
	//       -> have display work out if a service has been deleted and not replaced, to nil out display

	if hostName == "" {
		return nil, fmt.Errorf("host name not defined")
	}
	serviceNameSlice, err := GetServices(hostName, schemaPath)
	if err != nil {
		return nil, err
	}
	metricCache := newMetricRecordCache()
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
		if metricBuilders[index].topicBuilder.isService() {
			for serviceIndex, serviceName := range serviceNameSlice {
				topic, err := metricBuilders[index].topicBuilder.buildService(hostName, serviceName)
				if err != nil {
					return nil, fmt.Errorf("service topic build error: %w", err)
				}
				metricCache.Put(
					metricRecordGUID{metricBuilders[index].topicBuilder.metricID, serviceIndex, true},
					&metricRecord{topic: topic, load: metricBuilders[index].load},
				)
			}
		} else {
			topic, err := metricBuilders[index].topicBuilder.buildHost(hostName)
			if err != nil {
				return nil, fmt.Errorf("host topic build error: %w", err)
			}
			metricCache.Put(
				metricRecordGUID{metricBuilders[index].topicBuilder.metricID, 0, false},
				&metricRecord{topic: topic, load: metricBuilders[index].load},
			)
		}
	}
	return metricCache, nil
}

func (mc *metricRecordCache) Put(key metricRecordGUID, record *metricRecord) {
	if mc == nil || mc.treeMap == nil || record == nil {
		return
	}
	mc.treeMap.Put(key, record)
}

func (mc *metricRecordCache) Get(key metricRecordGUID) (*metricRecord, bool) {
	if mc == nil || mc.treeMap == nil {
		return nil, false
	}
	rawValue, found := mc.treeMap.Get(key)
	if !found || rawValue == nil {
		return nil, false
	}
	record, ok := rawValue.(*metricRecord)
	if !ok {
		return nil, false
	}
	return record, true
}

func (mc *metricRecordCache) Keys() []metricRecordGUID {
	if mc == nil || mc.treeMap == nil {
		return nil
	}
	rawKeys := mc.treeMap.Keys()
	recordGUIDs := make([]metricRecordGUID, len(rawKeys))
	for index, rawKey := range rawKeys {
		recordGUIDs[index] = rawKey.(metricRecordGUID)
	}
	return recordGUIDs
}

func (mc *metricRecordCache) Size() int {
	if mc == nil || mc.treeMap == nil {
		return 0
	}
	return mc.treeMap.Size()
}

func (mc *metricRecordCache) String() string {
	if mc == nil {
		return "<nil>"
	}
	var stringBuilder strings.Builder
	recordGUIDs := mc.Keys()
	for recordIndex, recordGUID := range recordGUIDs {
		record, ok := mc.Get(recordGUID)
		if !ok || record == nil {
			fmt.Fprintf(&stringBuilder,
				"Index[%03d] Service[%03d] Metric[%03d] <nil>\n",
				recordIndex,
				recordGUID.serviceIndex,
				recordGUID.metricID,
			)
			continue
		}
		recordValue := fmt.Sprintf("%v", record.value.value)
		recordTopic := record.topic
		if recordTopic == "" {
			recordTopic = "<no topic>"
		}
		fmt.Fprintf(
			&stringBuilder,
			"Index[%03d] Service[%03d] Metric[%03d] Value[%-6s] Topic[%s]\n",
			recordIndex,
			recordGUID.serviceIndex,
			recordGUID.metricID,
			recordValue,
			recordTopic,
		)
	}
	return stringBuilder.String()
}

func metricRecordGUIDComparator(this, that interface{}) int {
	thisGUID := this.(metricRecordGUID)
	thatGUID := that.(metricRecordGUID)
	if thisGUID.isService != thatGUID.isService {
		if !thisGUID.isService {
			return -1
		}
		return 1
	}
	if !thisGUID.isService {
		switch {
		case thisGUID.metricID < thatGUID.metricID:
			return -1
		case thisGUID.metricID > thatGUID.metricID:
			return 1
		default:
			return 0
		}
	}
	switch {
	case thisGUID.serviceIndex < thatGUID.serviceIndex:
		return -1
	case thisGUID.serviceIndex > thatGUID.serviceIndex:
		return 1
	case thisGUID.metricID < thatGUID.metricID:
		return -1
	case thisGUID.metricID > thatGUID.metricID:
		return 1
	default:
		return 0
	}
}

func (me metricEnum) isValid() bool {
	return me > METRIC_MIN && me < METRIC_MAX
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

func (tb *topicBuilder) buildHost(hostName string) (string, error) {
	return tb.build(map[string]string{"HOSTNAME": hostName})
}

func (tb *topicBuilder) buildService(hostName string, servicename string) (string, error) {
	return tb.build(map[string]string{"HOSTNAME": hostName, "SERVICENAME": servicename})
}
