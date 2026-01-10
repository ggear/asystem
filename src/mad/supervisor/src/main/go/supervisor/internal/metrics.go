package internal

import (
	"fmt"
	"maps"
	"regexp"
	"slices"
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
	Version   string                 `msgpack:"version" json:"version"`
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
	Topic    string
}

var metricBuilders = [METRIC_MAX]metricBuilder{
	metricAll: {
		topicBuilder{
			ID:       metricAll,
			Template: "supervisor/$HOSTNAME",
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
			return metricValue{OK: true, Unit: "%", Value: "10"}
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

var metricBuildersCache = func() map[string]metricBuilder {
	builders := make(map[string]metricBuilder)
	for i := METRIC_MIN + 1; i < METRIC_MAX; i++ {
		if err := metricBuilders[i].isValid(); err != nil {
			panic(fmt.Sprintf("invalid metric builder at index %d: %v", i, err))
		}
		builders[metricBuilders[i].TopicBuilder.Template] = metricBuilders[i]
	}
	return builders
}()

func MarshalSnapshot(schemaPath string, records []metricRecord) ([]byte, error) {
	if records == nil {
		return nil, fmt.Errorf("cache is nil")
	}
	version, err := GetVersion(schemaPath)
	if err != nil {
		return nil, err
	}
	snapshot := &metricRecordSnapshot{
		Version:   version,
		Timestamp: time.Now(),
		Metrics:   make(map[string]metricValue),
	}
	for _, record := range records {
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
	topics := slices.Collect(maps.Keys(metrics))
	slices.Sort(topics)
	services := make(map[string]int)
	services[""] = 0
	cache := newMetricRecordCache()
	for _, topic := range topics {
		value := metrics[topic]
		builder := topicBuilder{Topic: topic}
		id, _, service, err := builder.parse()
		if err != nil {
			return nil, fmt.Errorf("failed to parse topic %s: %w", topic, err)
		}
		if _, exists := services[service]; !exists {
			services[service] = len(services) - 1
		}
		cache.Put(
			metricRecordGUID{id, services[service], builder.isService()},
			&metricRecord{Topic: topic, Value: value, LoadValue: metricBuilders[id].LoadValue},
		)
	}
	return cache, nil
}

func CacheLocalMetrics(hostName string, schemaPath string) (*metricRecordCache, error) {

	// TODO: How to reload for new or removed services
	// TODO: -> OnChange triggered by Value and or ServiceIndex change
	//       -> input cache, if null LoadValue for first Time, otherwise use for onchnage
	//       -> have display work out if a service has been deleted and not replaced, to nil out display

	if hostName == "" {
		return nil, fmt.Errorf("host name not defined")
	}
	serviceNameSlice, err := GetServices(hostName, schemaPath)
	if err != nil {
		return nil, err
	}
	cache := newMetricRecordCache()
	for index := 1; index <= len(metricBuilders)-1; index++ {
		if metricBuilders[index].TopicBuilder.isService() {
			for serviceIndex, serviceName := range serviceNameSlice {
				topic, err := metricBuilders[index].TopicBuilder.buildService(hostName, serviceName)
				if err != nil {
					return nil, fmt.Errorf("service Topic build error: %w", err)
				}
				cache.Put(
					metricRecordGUID{metricBuilders[index].TopicBuilder.ID, serviceIndex, true},
					&metricRecord{Topic: topic, LoadValue: metricBuilders[index].LoadValue},
				)
			}
		} else {
			topic, err := metricBuilders[index].TopicBuilder.buildHost(hostName)
			if err != nil {
				return nil, fmt.Errorf("host Topic build error: %w", err)
			}
			cache.Put(
				metricRecordGUID{metricBuilders[index].TopicBuilder.ID, 0, false},
				&metricRecord{Topic: topic, LoadValue: metricBuilders[index].LoadValue},
			)
		}
	}
	return cache, nil
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
		metricOK := map[bool]string{true: "✔", false: "✖"}[record.Value.OK]
		metricServiceIndex := map[bool]string{true: fmt.Sprintf("%03d", guid.ServiceIndex), false: "   "}[guid.IsService]
		fmt.Fprintf(
			&stringBuilder,
			"Index[%03d] Service[%v] Metric[%03d] OK[%v] Value[%3s] Unit[%1v] Topic[%s]\n",
			index,
			metricServiceIndex,
			guid.ID,
			metricOK,
			value,
			record.Value.Unit,
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

func (id metricID) isValid() error {
	if id < METRIC_MIN || id > METRIC_MAX {
		return fmt.Errorf("metric ID %d outside [%d, %d]", id, METRIC_MIN, METRIC_MAX)
	}
	return nil
}

func (builder metricBuilder) isValid() error {
	id := builder.TopicBuilder.ID
	if err := id.isValid(); err != nil {
		return fmt.Errorf("metric builder %d: %w", id, err)
	}
	if builder.TopicBuilder.Template == "" {
		return fmt.Errorf("metric builder %d: empty template", id)
	}
	if builder.LoadValue == nil {
		return fmt.Errorf("metric builder %d: LoadValue is nil", id)
	}
	return nil
}

func (builder *topicBuilder) build(replacements map[string]string) (string, error) {
	if builder.Topic != "" {
		return builder.Topic, nil
	}
	if builder.Template == "" {
		return "", fmt.Errorf("cannot build with empty template")
	}
	if !regexp.MustCompile(`^supervisor(/[a-zA-Z0-9$_-]+){1,4}$`).MatchString(builder.Template) {
		return "", fmt.Errorf("invalid Topic Template [%s]", builder.Template)
	}
	pairs := make([]string, 0, len(replacements)*2)
	for key, value := range replacements {
		pairs = append(pairs, "$"+key, value)
	}
	replacer := strings.NewReplacer(pairs...)
	builder.Topic = replacer.Replace(builder.Template)
	if strings.Contains(builder.Topic, "$") {
		return "", fmt.Errorf("invalid $TOKEN in Template [%s]", builder.Topic)
	}
	return builder.Topic, nil
}

func (builder *topicBuilder) parse() (metricID, string, string, error) {
	host := ""
	service := ""
	if builder.Template == "" {
		if builder.Topic == "" {
			return METRIC_MIN, "", "", fmt.Errorf("cannot parse with empty topic")
		}
		if serviceMatch := regexp.MustCompile(`^supervisor/([a-zA-Z0-9_-]+)/service/([a-zA-Z0-9_-]+)/([a-zA-Z0-9_-]+(/[a-zA-Z0-9_-]+)*)$`).FindStringSubmatch(builder.Topic); serviceMatch != nil {
			host = serviceMatch[1]
			service = serviceMatch[2]
			builder.Template = "supervisor/$HOSTNAME/service/$SERVICENAME/" + serviceMatch[3]
		} else if hostMatch := regexp.MustCompile(`^supervisor/([a-zA-Z0-9_-]+)/host/([a-zA-Z0-9_-]+(/[a-zA-Z0-9_-]+)*)$`).FindStringSubmatch(builder.Topic); hostMatch != nil {
			host = hostMatch[1]
			builder.Template = "supervisor/$HOSTNAME/host/" + hostMatch[2]
		} else {
			return METRIC_MIN, "", "", fmt.Errorf("topic [%s] does not match expected format", builder.Topic)
		}
	}
	if cached, found := metricBuildersCache[builder.Template]; found {
		builder.ID = cached.TopicBuilder.ID
	} else {
		return METRIC_MIN, "", "", fmt.Errorf("template [%s] not found in metric builders cache", builder.Template)
	}
	return builder.ID, host, service, nil
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
