package internal

import (
	"fmt"
	"regexp"
	"strings"
	"time"

	"github.com/emirpasic/gods/maps/treemap"
	"github.com/vmihailenco/msgpack/v5"
)

type metricID int

const (
	METRIC_MIN metricID = iota
	metricAll
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

type metricRecordGUID struct {
	id           metricID
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
	ok    bool   `msgpack:"ok" json:"ok"`
	value string `msgpack:"value" json:"value"`
	unit  string `msgpack:"unit,omitempty" json:"unit,omitempty"`
}

type metricRecordCache struct {
	treeMap *treemap.Map
}

type metricRecordSnapshot struct {
	Timestamp time.Time              `msgpack:"timestamp" json:"timestamp"`
	Metrics   map[string]metricValue `msgpack:"data" json:"data"`
}

type metricBuilder struct {
	topicBuilder topicBuilder
	load         func(int, string) metricValue
}

type topicBuilder struct {
	id       metricID
	template string
}

var metricBuilders = [METRIC_MAX]metricBuilder{
	metricAll: {
		topicBuilder{
			id:       metricAll,
			template: "supervisor/$HOSTNAME/all",
		},
		func(period int, serviceName string) metricValue {
			return metricValue{ok: true}
		},
	},
	metricHost: {
		topicBuilder{
			id:       metricHost,
			template: "supervisor/$HOSTNAME/host",
		},
		func(period int, serviceName string) metricValue {
			return metricValue{ok: true}
		},
	},
	metricHostCompute: {
		topicBuilder{
			id:       metricHostCompute,
			template: "supervisor/$HOSTNAME/host/compute",
		},
		func(period int, serviceName string) metricValue {
			return metricValue{ok: true}
		},
	},
	metricHostComputeUsedProcessor: {
		topicBuilder{
			id:       metricHostComputeUsedProcessor,
			template: "supervisor/$HOSTNAME/host/compute/used_processor",
		},
		func(period int, serviceName string) metricValue {
			return metricValue{ok: true, unit: "%", value: "10"}
		},
	},
	metricHostComputeUsedMemory: {
		topicBuilder{
			id:       metricHostComputeUsedMemory,
			template: "supervisor/$HOSTNAME/host/compute/used_memory",
		},
		func(period int, serviceName string) metricValue {
			return metricValue{ok: true, unit: "%", value: "10"}
		},
	},
	metricHostComputeAllocatedMemory: {
		topicBuilder{
			id:       metricHostComputeAllocatedMemory,
			template: "supervisor/$HOSTNAME/host/compute/allocated_memory",
		},
		func(period int, serviceName string) metricValue {
			return metricValue{ok: true, unit: "GB", value: "10"}
		},
	},
	metricHostHealth: {
		topicBuilder{
			id:       metricHostHealth,
			template: "supervisor/$HOSTNAME/host/health",
		},
		func(period int, serviceName string) metricValue {
			return metricValue{ok: true}
		},
	},
	metricHostHealthFailedServices: {
		topicBuilder{
			id:       metricHostHealthFailedServices,
			template: "supervisor/$HOSTNAME/host/health/failed_services",
		},
		func(period int, serviceName string) metricValue {
			return metricValue{ok: true, unit: "", value: "10"}
		},
	},
	metricHostHealthFailedShares: {
		topicBuilder{
			id:       metricHostHealthFailedShares,
			template: "supervisor/$HOSTNAME/host/health/failed_shares",
		},
		func(period int, serviceName string) metricValue {
			return metricValue{ok: true, unit: "", value: "10"}
		},
	},
	metricHostHealthFailedBackups: {
		topicBuilder{
			id:       metricHostHealthFailedBackups,
			template: "supervisor/$HOSTNAME/host/health/failed_backups",
		},
		func(period int, serviceName string) metricValue {
			return metricValue{ok: true, unit: "", value: "10"}
		},
	},
	metricHostRuntime: {
		topicBuilder{
			id:       metricHostRuntime,
			template: "supervisor/$HOSTNAME/host/runtime",
		},
		func(period int, serviceName string) metricValue {
			return metricValue{ok: true}
		},
	},
	metricHostRuntimePeakTemperatureMax: {
		topicBuilder{
			id:       metricHostRuntimePeakTemperatureMax,
			template: "supervisor/$HOSTNAME/host/runtime/peak_temperature_max",
		},
		func(period int, serviceName string) metricValue {
			return metricValue{ok: true, unit: "%", value: "10"}
		},
	},
	metricHostRuntimePeakFanSpeedMax: {
		topicBuilder{
			id:       metricHostRuntimePeakFanSpeedMax,
			template: "supervisor/$HOSTNAME/host/runtime/peak_fan_speed_max",
		},
		func(period int, serviceName string) metricValue {
			return metricValue{ok: true, unit: "%", value: "10"}
		},
	},
	metricHostRuntimeLifeUsedDrives: {
		topicBuilder{
			id:       metricHostRuntimeLifeUsedDrives,
			template: "supervisor/$HOSTNAME/host/runtime/life_used_drives",
		},
		func(period int, serviceName string) metricValue {
			return metricValue{ok: true, unit: "%", value: "10"}
		},
	},
	metricHostStorage: {
		topicBuilder{
			id:       metricHostStorage,
			template: "supervisor/$HOSTNAME/host/storage",
		},
		func(period int, serviceName string) metricValue {
			return metricValue{ok: true}
		},
	},
	metricHostStorageUsedSystemDrive: {
		topicBuilder{
			id:       metricHostStorageUsedSystemDrive,
			template: "supervisor/$HOSTNAME/host/storage/used_system_drive",
		},
		func(period int, serviceName string) metricValue {
			return metricValue{ok: true, unit: "%", value: "10"}
		},
	},
	metricHostStorageUsedShareDrives: {
		topicBuilder{
			id:       metricHostStorageUsedShareDrives,
			template: "supervisor/$HOSTNAME/host/storage/used_share_drives",
		},
		func(period int, serviceName string) metricValue {
			return metricValue{ok: true, unit: "%", value: "10"}
		},
	},
	metricHostStorageUsedBackupDrives: {
		topicBuilder{
			id:       metricHostStorageUsedBackupDrives,
			template: "supervisor/$HOSTNAME/host/storage/used_backup_drives",
		},
		func(period int, serviceName string) metricValue {
			return metricValue{ok: true, unit: "%", value: "10"}
		},
	},
	metricService: {
		topicBuilder{
			id:       metricService,
			template: "supervisor/$HOSTNAME/service",
		},
		func(period int, serviceName string) metricValue {
			return metricValue{ok: true}
		},
	},
	metricServiceName: {
		topicBuilder{
			id:       metricServiceName,
			template: "supervisor/$HOSTNAME/service/$SERVICENAME/name",
		},
		func(period int, serviceName string) metricValue {
			return metricValue{ok: true, value: serviceName}
		},
	},
	metricServiceVersion: {
		topicBuilder{
			id:       metricServiceVersion,
			template: "supervisor/$HOSTNAME/service/$SERVICENAME/version",
		},
		func(period int, serviceName string) metricValue {
			return metricValue{ok: true, value: "1.0.0"}
		},
	},
	metricServiceUsedProcessor: {
		topicBuilder{
			id:       metricServiceUsedProcessor,
			template: "supervisor/$HOSTNAME/service/$SERVICENAME/used_processor",
		},
		func(period int, serviceName string) metricValue {
			return metricValue{ok: true, unit: "%", value: "10"}
		},
	},
	metricServiceUsedMemory: {
		topicBuilder{
			id:       metricServiceUsedMemory,
			template: "supervisor/$HOSTNAME/service/$SERVICENAME/used_memory",
		},
		func(period int, serviceName string) metricValue {
			return metricValue{ok: true, unit: "MB", value: "256"}
		},
	},
	metricServiceBackupStatus: {
		topicBuilder{
			id:       metricServiceBackupStatus,
			template: "supervisor/$HOSTNAME/service/$SERVICENAME/backup_status",
		},
		func(period int, serviceName string) metricValue {
			return metricValue{ok: true, value: "1"}
		},
	},
	metricServiceConfiguredStatus: {
		topicBuilder{
			id:       metricServiceConfiguredStatus,
			template: "supervisor/$HOSTNAME/service/$SERVICENAME/configured_status",
		},
		func(period int, serviceName string) metricValue {
			return metricValue{ok: true, value: "true"}
		},
	},
	metricServiceRestartCount: {
		topicBuilder{
			id:       metricServiceRestartCount,
			template: "supervisor/$HOSTNAME/service/$SERVICENAME/restart_count",
		},
		func(period int, serviceName string) metricValue {
			return metricValue{ok: true, value: "0"}
		},
	},
	metricServiceRuntime: {
		topicBuilder{
			id:       metricServiceRuntime,
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
		if !metricBuilders[index].topicBuilder.id.isValid() {
			return nil, fmt.Errorf("metric builder [%d] has invalid metric id [%d]", index, metricBuilders[index].topicBuilder.id)
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
					metricRecordGUID{metricBuilders[index].topicBuilder.id, serviceIndex, true},
					&metricRecord{topic: topic, load: metricBuilders[index].load},
				)
			}
		} else {
			topic, err := metricBuilders[index].topicBuilder.buildHost(hostName)
			if err != nil {
				return nil, fmt.Errorf("host topic build error: %w", err)
			}
			metricCache.Put(
				metricRecordGUID{metricBuilders[index].topicBuilder.id, 0, false},
				&metricRecord{topic: topic, load: metricBuilders[index].load},
			)
		}
	}
	return metricCache, nil
}

func (cache *metricRecordCache) Put(key metricRecordGUID, record *metricRecord) {
	if cache == nil || cache.treeMap == nil || record == nil {
		return
	}
	cache.treeMap.Put(key, record)
}

func (cache *metricRecordCache) Get(key metricRecordGUID) (*metricRecord, bool) {
	if cache == nil || cache.treeMap == nil {
		return nil, false
	}
	rawValue, found := cache.treeMap.Get(key)
	if !found || rawValue == nil {
		return nil, false
	}
	record, ok := rawValue.(*metricRecord)
	if !ok {
		return nil, false
	}
	return record, true
}

func (cache *metricRecordCache) Keys() []metricRecordGUID {
	if cache == nil || cache.treeMap == nil {
		return nil
	}
	rawKeys := cache.treeMap.Keys()
	recordGUIDs := make([]metricRecordGUID, 0, len(rawKeys))
	for _, rawKey := range rawKeys {
		if recordGUID, ok := rawKey.(metricRecordGUID); ok {
			recordGUIDs = append(recordGUIDs, recordGUID)
		}
	}
	return recordGUIDs
}

func (cache *metricRecordCache) Size() int {
	if cache == nil || cache.treeMap == nil {
		return 0
	}
	return cache.treeMap.Size()
}

func (cache *metricRecordCache) String() string {
	if cache == nil {
		return "<nil>"
	}
	var stringBuilder strings.Builder
	guids := cache.Keys()
	for index, guid := range guids {
		record, ok := cache.Get(guid)
		if !ok || record == nil {
			fmt.Fprintf(&stringBuilder,
				"Index[%03d] Service[%03d] Metric[%03d] <nil>\n",
				index,
				guid.serviceIndex,
				guid.id,
			)
			continue
		}
		value := fmt.Sprintf("%v", record.value.value)
		topic := record.topic
		if topic == "" {
			topic = "<no topic>"
		}
		fmt.Fprintf(
			&stringBuilder,
			"Index[%03d] Service[%03d] Metric[%03d] value[%-6s] topic[%s]\n",
			index,
			guid.serviceIndex,
			guid.id,
			value,
			topic,
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
		case thisGUID.id < thatGUID.id:
			return -1
		case thisGUID.id > thatGUID.id:
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
	case thisGUID.id < thatGUID.id:
		return -1
	case thisGUID.id > thatGUID.id:
		return 1
	default:
		return 0
	}
}

func (id metricID) isValid() bool {
	return id > METRIC_MIN && id < METRIC_MAX
}

func (builder *topicBuilder) build(replacements map[string]string) (string, error) {
	if !regexp.MustCompile(`^supervisor(/[a-zA-Z0-9$_-]+){2,4}$`).MatchString(builder.template) {
		return "", fmt.Errorf("invalid topic template [%s]", builder.template)
	}
	pairs := make([]string, 0, len(replacements)*2)
	for key, value := range replacements {
		pairs = append(pairs, "$"+key, value)
	}
	replacer := strings.NewReplacer(pairs...)
	result := replacer.Replace(builder.template)
	if strings.Contains(result, "$") {
		return "", fmt.Errorf("invalid $TOKEN in template [%s]", result)
	}
	return result, nil
}

func (builder *topicBuilder) isHost() bool {
	return strings.Contains(builder.template, "$HOSTNAME") && !strings.Contains(builder.template, "$SERVICENAME")
}

func (builder *topicBuilder) isService() bool {
	return strings.Contains(builder.template, "$HOSTNAME") && strings.Contains(builder.template, "$SERVICENAME")
}

func (builder *topicBuilder) buildHost(hostName string) (string, error) {
	return builder.build(map[string]string{"HOSTNAME": hostName})
}

func (builder *topicBuilder) buildService(hostName string, servicename string) (string, error) {
	return builder.build(map[string]string{"HOSTNAME": hostName, "SERVICENAME": servicename})
}

// TODO: Fix, move all structs to exported (title case)
func (cache *metricRecordCache) MarshalSnapshot() ([]byte, error) {
	if cache == nil || cache.treeMap == nil {
		return nil, fmt.Errorf("cache is nil")
	}
	snapshot := &metricSnapshotCache{
		Timestamp: time.Now(),
		Data:      make([]metricSnapshotDatum, 0, cache.Size()),
	}
	guids := cache.Keys()
	for _, guid := range guids {
		record, ok := cache.Get(guid)
		if !ok || record == nil {
			continue
		}
		var unitDefault string
		if len(record.value.unit) > 0 {
			unitDefault = record.value.unit
		}
		snapshot.Data = append(snapshot.Data, metricSnapshotDatum{
			Topic: record.topic,
			Value: record.value.value,
			OK:    record.value.ok,
			Unit:  unitDefault,
		})
	}
	return msgpack.Marshal(snapshot)
}

func (cache *metricRecordCache) UnmarshalSnapshot(data []byte) (*metricSnapshotCache, error) {
	if len(data) == 0 {
		return nil, fmt.Errorf("empty snapshot")
	}
	var snapshot metricSnapshotCache
	if err := msgpack.Unmarshal(data, &snapshot); err != nil {
		return nil, err
	}

	// TODO: Load values into cache by topic

	return &snapshot, nil
}

func (snapshot *metricSnapshotCache) String() string {
	if snapshot == nil {
		return "<nil>"
	}
	var stringBuilder strings.Builder
	//guids := snapshot.Keys()
	//for index, guid := range guids {
	//	record, ok := snapshot.Get(guid)
	//	if !ok || record == nil {
	//		fmt.Fprintf(&stringBuilder,
	//			"Index[%03d] Service[%03d] Metric[%03d] <nil>\n",
	//			index,
	//			guid.serviceIndex,
	//			guid.id,
	//		)
	//		continue
	//	}
	//	value := fmt.Sprintf("%v", record.value.value)
	//	topic := record.topic
	//	if topic == "" {
	//		topic = "<no topic>"
	//	}
	//	fmt.Fprintf(
	//		&stringBuilder,
	//		"Index[%03d] Service[%03d] Metric[%03d] value[%-6s] topic[%s]\n",
	//		index,
	//		guid.serviceIndex,
	//		guid.id,
	//		value,
	//		topic,
	//	)
	//}
	return stringBuilder.String()
}
