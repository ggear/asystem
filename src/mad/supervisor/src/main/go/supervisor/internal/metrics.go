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
	ID           metricID
	ServiceIndex int
	IsService    bool
}

type metricRecord struct {
	Topic     string
	Value     metricValue
	Time      time.Time
	LoadValue func(int, string) metricValue
	OnChange  func(previous, current metricValue)
}

type metricValue struct {
	OK    bool   `msgpack:"ok" json:"ok"`
	Value string `msgpack:"value" json:"value"`
	Unit  string `msgpack:"unit,omitempty" json:"unit,omitempty"`
}

type metricRecordCache struct {
	Metrics *treemap.Map
}

type metricRecordSnapshot struct {
	Timestamp time.Time              `msgpack:"timestamp" json:"timestamp"`
	Metrics   map[string]metricValue `msgpack:"data" json:"data"`
}

type metricBuilder struct {
	TopicBuilder topicBuilder
	LoadValue    func(int, string) metricValue
}

type topicBuilder struct {
	ID       metricID
	Template string
}

var metricBuilders = [METRIC_MAX]metricBuilder{
	metricAll: {
		topicBuilder{
			ID:       metricAll,
			Template: "supervisor/$HOSTNAME/all",
		},
		func(period int, serviceName string) metricValue {
			return metricValue{OK: true}
		},
	},
	metricHost: {
		topicBuilder{
			ID:       metricHost,
			Template: "supervisor/$HOSTNAME/host",
		},
		func(period int, serviceName string) metricValue {
			return metricValue{OK: true}
		},
	},
	metricHostCompute: {
		topicBuilder{
			ID:       metricHostCompute,
			Template: "supervisor/$HOSTNAME/host/compute",
		},
		func(period int, serviceName string) metricValue {
			return metricValue{OK: true}
		},
	},
	metricHostComputeUsedProcessor: {
		topicBuilder{
			ID:       metricHostComputeUsedProcessor,
			Template: "supervisor/$HOSTNAME/host/compute/used_processor",
		},
		func(period int, serviceName string) metricValue {
			return metricValue{OK: true, Unit: "%", Value: "10"}
		},
	},
	metricHostComputeUsedMemory: {
		topicBuilder{
			ID:       metricHostComputeUsedMemory,
			Template: "supervisor/$HOSTNAME/host/compute/used_memory",
		},
		func(period int, serviceName string) metricValue {
			return metricValue{OK: true, Unit: "%", Value: "10"}
		},
	},
	metricHostComputeAllocatedMemory: {
		topicBuilder{
			ID:       metricHostComputeAllocatedMemory,
			Template: "supervisor/$HOSTNAME/host/compute/allocated_memory",
		},
		func(period int, serviceName string) metricValue {
			return metricValue{OK: true, Unit: "GB", Value: "10"}
		},
	},
	metricHostHealth: {
		topicBuilder{
			ID:       metricHostHealth,
			Template: "supervisor/$HOSTNAME/host/health",
		},
		func(period int, serviceName string) metricValue {
			return metricValue{OK: true}
		},
	},
	metricHostHealthFailedServices: {
		topicBuilder{
			ID:       metricHostHealthFailedServices,
			Template: "supervisor/$HOSTNAME/host/health/failed_services",
		},
		func(period int, serviceName string) metricValue {
			return metricValue{OK: true, Unit: "", Value: "10"}
		},
	},
	metricHostHealthFailedShares: {
		topicBuilder{
			ID:       metricHostHealthFailedShares,
			Template: "supervisor/$HOSTNAME/host/health/failed_shares",
		},
		func(period int, serviceName string) metricValue {
			return metricValue{OK: true, Unit: "", Value: "10"}
		},
	},
	metricHostHealthFailedBackups: {
		topicBuilder{
			ID:       metricHostHealthFailedBackups,
			Template: "supervisor/$HOSTNAME/host/health/failed_backups",
		},
		func(period int, serviceName string) metricValue {
			return metricValue{OK: true, Unit: "", Value: "10"}
		},
	},
	metricHostRuntime: {
		topicBuilder{
			ID:       metricHostRuntime,
			Template: "supervisor/$HOSTNAME/host/runtime",
		},
		func(period int, serviceName string) metricValue {
			return metricValue{OK: true}
		},
	},
	metricHostRuntimePeakTemperatureMax: {
		topicBuilder{
			ID:       metricHostRuntimePeakTemperatureMax,
			Template: "supervisor/$HOSTNAME/host/runtime/peak_temperature_max",
		},
		func(period int, serviceName string) metricValue {
			return metricValue{OK: true, Unit: "%", Value: "10"}
		},
	},
	metricHostRuntimePeakFanSpeedMax: {
		topicBuilder{
			ID:       metricHostRuntimePeakFanSpeedMax,
			Template: "supervisor/$HOSTNAME/host/runtime/peak_fan_speed_max",
		},
		func(period int, serviceName string) metricValue {
			return metricValue{OK: true, Unit: "%", Value: "10"}
		},
	},
	metricHostRuntimeLifeUsedDrives: {
		topicBuilder{
			ID:       metricHostRuntimeLifeUsedDrives,
			Template: "supervisor/$HOSTNAME/host/runtime/life_used_drives",
		},
		func(period int, serviceName string) metricValue {
			return metricValue{OK: true, Unit: "%", Value: "10"}
		},
	},
	metricHostStorage: {
		topicBuilder{
			ID:       metricHostStorage,
			Template: "supervisor/$HOSTNAME/host/storage",
		},
		func(period int, serviceName string) metricValue {
			return metricValue{OK: true}
		},
	},
	metricHostStorageUsedSystemDrive: {
		topicBuilder{
			ID:       metricHostStorageUsedSystemDrive,
			Template: "supervisor/$HOSTNAME/host/storage/used_system_drive",
		},
		func(period int, serviceName string) metricValue {
			return metricValue{OK: true, Unit: "%", Value: "10"}
		},
	},
	metricHostStorageUsedShareDrives: {
		topicBuilder{
			ID:       metricHostStorageUsedShareDrives,
			Template: "supervisor/$HOSTNAME/host/storage/used_share_drives",
		},
		func(period int, serviceName string) metricValue {
			return metricValue{OK: true, Unit: "%", Value: "10"}
		},
	},
	metricHostStorageUsedBackupDrives: {
		topicBuilder{
			ID:       metricHostStorageUsedBackupDrives,
			Template: "supervisor/$HOSTNAME/host/storage/used_backup_drives",
		},
		func(period int, serviceName string) metricValue {
			return metricValue{OK: true, Unit: "%", Value: "10"}
		},
	},
	metricService: {
		topicBuilder{
			ID:       metricService,
			Template: "supervisor/$HOSTNAME/service",
		},
		func(period int, serviceName string) metricValue {
			return metricValue{OK: true}
		},
	},
	metricServiceName: {
		topicBuilder{
			ID:       metricServiceName,
			Template: "supervisor/$HOSTNAME/service/$SERVICENAME/name",
		},
		func(period int, serviceName string) metricValue {
			return metricValue{OK: true, Value: serviceName}
		},
	},
	metricServiceVersion: {
		topicBuilder{
			ID:       metricServiceVersion,
			Template: "supervisor/$HOSTNAME/service/$SERVICENAME/version",
		},
		func(period int, serviceName string) metricValue {
			return metricValue{OK: true, Value: "1.0.0"}
		},
	},
	metricServiceUsedProcessor: {
		topicBuilder{
			ID:       metricServiceUsedProcessor,
			Template: "supervisor/$HOSTNAME/service/$SERVICENAME/used_processor",
		},
		func(period int, serviceName string) metricValue {
			return metricValue{OK: true, Unit: "%", Value: "10"}
		},
	},
	metricServiceUsedMemory: {
		topicBuilder{
			ID:       metricServiceUsedMemory,
			Template: "supervisor/$HOSTNAME/service/$SERVICENAME/used_memory",
		},
		func(period int, serviceName string) metricValue {
			return metricValue{OK: true, Unit: "MB", Value: "256"}
		},
	},
	metricServiceBackupStatus: {
		topicBuilder{
			ID:       metricServiceBackupStatus,
			Template: "supervisor/$HOSTNAME/service/$SERVICENAME/backup_status",
		},
		func(period int, serviceName string) metricValue {
			return metricValue{OK: true, Value: "1"}
		},
	},
	metricServiceConfiguredStatus: {
		topicBuilder{
			ID:       metricServiceConfiguredStatus,
			Template: "supervisor/$HOSTNAME/service/$SERVICENAME/configured_status",
		},
		func(period int, serviceName string) metricValue {
			return metricValue{OK: true, Value: "true"}
		},
	},
	metricServiceRestartCount: {
		topicBuilder{
			ID:       metricServiceRestartCount,
			Template: "supervisor/$HOSTNAME/service/$SERVICENAME/restart_count",
		},
		func(period int, serviceName string) metricValue {
			return metricValue{OK: true, Value: "0"}
		},
	},
	metricServiceRuntime: {
		topicBuilder{
			ID:       metricServiceRuntime,
			Template: "supervisor/$HOSTNAME/service/$SERVICENAME/runtime",
		},
		func(period int, serviceName string) metricValue {
			return metricValue{OK: true, Unit: "s", Value: "3600"}
		},
	},
}

func MarshalSnapshot(cache *metricRecordCache) ([]byte, error) {
	if cache == nil || cache.Metrics == nil {
		return nil, fmt.Errorf("cache is nil")
	}
	snapshot := &metricRecordSnapshot{
		Timestamp: time.Now(),
		Metrics:   make(map[string]metricValue),
	}
	guids := cache.Keys()
	for _, guid := range guids {
		record, ok := cache.Get(guid)
		if !ok || record == nil {
			continue
		}
		var unitDefault string
		if len(record.Value.Unit) > 0 {
			unitDefault = record.Value.Unit
		}
		snapshot.Metrics[record.Topic] = metricValue{
			Value: record.Value.Value,
			OK:    record.Value.OK,
			Unit:  unitDefault,
		}
	}
	return msgpack.Marshal(snapshot)
}

func UnmarshalSnapshot(snapshotMsgPack []byte) (*metricRecordSnapshot, error) {
	if len(snapshotMsgPack) == 0 {
		return nil, fmt.Errorf("empty snapshot")
	}
	var snapshot metricRecordSnapshot
	if err := msgpack.Unmarshal(snapshotMsgPack, &snapshot); err != nil {
		return nil, err
	}
	return &snapshot, nil
}

func newMetricRecordCache() *metricRecordCache {
	return &metricRecordCache{
		Metrics: treemap.NewWith(metricRecordGUIDComparator),
	}
}

func CacheRemoteMetrics(metrics map[string]metricValue) (*metricRecordCache, error) {
	metricCache := newMetricRecordCache()
	// TODO: Provide impl
	return metricCache, nil
}

func CacheLocalMetrics(hostName string, schemaPath string) (*metricRecordCache, error) {

	// TODO: How to reload for new or removed services
	// TODO: -> OnChange triggered by Value and or ServiceIndex change
	//       -> input metricCache, if null LoadValue for first Time, otherwise use for onchnage
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
		if !metricBuilders[index].TopicBuilder.ID.isValid() {
			return nil, fmt.Errorf("metric builder [%d] has invalid metric ID [%d]", index, metricBuilders[index].TopicBuilder.ID)
		}
		if metricBuilders[index].TopicBuilder.Template == "" {
			return nil, fmt.Errorf("metric builder [%d] has empty Template string", index)
		}
		if metricBuilders[index].LoadValue == nil {
			return nil, fmt.Errorf("metric builder [%d] has empty LoadValue function", index)
		}
		if metricBuilders[index].TopicBuilder.isService() {
			for serviceIndex, serviceName := range serviceNameSlice {
				topic, err := metricBuilders[index].TopicBuilder.buildService(hostName, serviceName)
				if err != nil {
					return nil, fmt.Errorf("service Topic build error: %w", err)
				}
				metricCache.Put(
					metricRecordGUID{metricBuilders[index].TopicBuilder.ID, serviceIndex, true},
					&metricRecord{Topic: topic, LoadValue: metricBuilders[index].LoadValue},
				)
			}
		} else {
			topic, err := metricBuilders[index].TopicBuilder.buildHost(hostName)
			if err != nil {
				return nil, fmt.Errorf("host Topic build error: %w", err)
			}
			metricCache.Put(
				metricRecordGUID{metricBuilders[index].TopicBuilder.ID, 0, false},
				&metricRecord{Topic: topic, LoadValue: metricBuilders[index].LoadValue},
			)
		}
	}
	return metricCache, nil
}

func (cache *metricRecordCache) Put(key metricRecordGUID, record *metricRecord) {
	if cache == nil || cache.Metrics == nil || record == nil {
		return
	}
	cache.Metrics.Put(key, record)
}

func (cache *metricRecordCache) Get(key metricRecordGUID) (*metricRecord, bool) {
	if cache == nil || cache.Metrics == nil {
		return nil, false
	}
	rawValue, found := cache.Metrics.Get(key)
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
	if cache == nil || cache.Metrics == nil {
		return nil
	}
	rawKeys := cache.Metrics.Keys()
	recordGUIDs := make([]metricRecordGUID, 0, len(rawKeys))
	for _, rawKey := range rawKeys {
		if recordGUID, ok := rawKey.(metricRecordGUID); ok {
			recordGUIDs = append(recordGUIDs, recordGUID)
		}
	}
	return recordGUIDs
}

func (cache *metricRecordCache) Size() int {
	if cache == nil || cache.Metrics == nil {
		return 0
	}
	return cache.Metrics.Size()
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
				guid.ServiceIndex,
				guid.ID,
			)
			continue
		}
		value := fmt.Sprintf("%v", record.Value.Value)
		topic := record.Topic
		if topic == "" {
			topic = "<no Topic>"
		}
		fmt.Fprintf(
			&stringBuilder,
			"Index[%03d] Service[%03d] Metric[%03d] Value[%-6s] Topic[%s]\n",
			index,
			guid.ServiceIndex,
			guid.ID,
			value,
			topic,
		)
	}
	return stringBuilder.String()
}

func metricRecordGUIDComparator(this, that interface{}) int {
	thisGUID := this.(metricRecordGUID)
	thatGUID := that.(metricRecordGUID)
	if thisGUID.IsService != thatGUID.IsService {
		if !thisGUID.IsService {
			return -1
		}
		return 1
	}
	if !thisGUID.IsService {
		switch {
		case thisGUID.ID < thatGUID.ID:
			return -1
		case thisGUID.ID > thatGUID.ID:
			return 1
		default:
			return 0
		}
	}
	switch {
	case thisGUID.ServiceIndex < thatGUID.ServiceIndex:
		return -1
	case thisGUID.ServiceIndex > thatGUID.ServiceIndex:
		return 1
	case thisGUID.ID < thatGUID.ID:
		return -1
	case thisGUID.ID > thatGUID.ID:
		return 1
	default:
		return 0
	}
}

func (id metricID) isValid() bool {
	return id > METRIC_MIN && id < METRIC_MAX
}

func (builder *topicBuilder) build(replacements map[string]string) (string, error) {
	if !regexp.MustCompile(`^supervisor(/[a-zA-Z0-9$_-]+){2,4}$`).MatchString(builder.Template) {
		return "", fmt.Errorf("invalid Topic Template [%s]", builder.Template)
	}
	pairs := make([]string, 0, len(replacements)*2)
	for key, value := range replacements {
		pairs = append(pairs, "$"+key, value)
	}
	replacer := strings.NewReplacer(pairs...)
	result := replacer.Replace(builder.Template)
	if strings.Contains(result, "$") {
		return "", fmt.Errorf("invalid $TOKEN in Template [%s]", result)
	}
	return result, nil
}

func (builder *topicBuilder) isHost() bool {
	return strings.Contains(builder.Template, "$HOSTNAME") && !strings.Contains(builder.Template, "$SERVICENAME")
}

func (builder *topicBuilder) isService() bool {
	return strings.Contains(builder.Template, "$HOSTNAME") && strings.Contains(builder.Template, "$SERVICENAME")
}

func (builder *topicBuilder) buildHost(hostName string) (string, error) {
	return builder.build(map[string]string{"HOSTNAME": hostName})
}

func (builder *topicBuilder) buildService(hostName string, servicename string) (string, error) {
	return builder.build(map[string]string{"HOSTNAME": hostName, "SERVICENAME": servicename})
}
