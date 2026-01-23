package internal

import (
	"fmt"
	"maps"
	"regexp"
	"slices"
	"strconv"
	"strings"
	"sync"
	"time"

	"github.com/emirpasic/gods/maps/treemap"
	"github.com/vmihailenco/msgpack/v5"
)

type MetricID int

const (
	metricAll MetricID = iota
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
	metricHostRuntimeWarningTemperatureOfMax
	metricHostRuntimeRevsFanSpeedOfMax
	metricHostRuntimeLifeUsedDrives
	metricHostStorage
	metricHostStorageUsedSystemDrive
	metricHostStorageUsedShareDrives
	metricHostStorageUsedBackupDrives
	metricService
	metricServiceName
	metricServiceUsedProcessor
	metricServiceUsedMemory
	metricServiceBackupStatus
	metricServiceHealthStatus
	metricServiceConfiguredStatus
	metricServiceRestartCount
	metricServiceRuntime
	metricServiceVersion
	metricMax
)

var metricBuilders = []metricBuilder{
	metricAll: {
		id:       metricAll,
		template: "supervisor/$HOSTNAME",
	},
	metricHost: {
		id:       metricHost,
		template: "supervisor/$HOSTNAME/host",
	},
	metricHostCompute: {
		id:       metricHostCompute,
		template: "supervisor/$HOSTNAME/host/compute",
	},
	metricHostComputeUsedProcessor: {
		id:       metricHostComputeUsedProcessor,
		template: "supervisor/$HOSTNAME/host/compute/used_processor",
	},
	metricHostComputeUsedMemory: {
		id:       metricHostComputeUsedMemory,
		template: "supervisor/$HOSTNAME/host/compute/used_memory",
	},
	metricHostComputeAllocatedMemory: {
		id:       metricHostComputeAllocatedMemory,
		template: "supervisor/$HOSTNAME/host/compute/allocated_memory",
	},
	metricHostHealth: {
		id:       metricHostHealth,
		template: "supervisor/$HOSTNAME/host/health",
	},
	metricHostHealthFailedServices: {
		id:       metricHostHealthFailedServices,
		template: "supervisor/$HOSTNAME/host/health/failed_services",
	},
	metricHostHealthFailedShares: {
		id:       metricHostHealthFailedShares,
		template: "supervisor/$HOSTNAME/host/health/failed_shares",
	},
	metricHostHealthFailedBackups: {
		id:       metricHostHealthFailedBackups,
		template: "supervisor/$HOSTNAME/host/health/failed_backups",
	},
	metricHostRuntime: {
		id:       metricHostRuntime,
		template: "supervisor/$HOSTNAME/host/runtime",
	},
	metricHostRuntimeWarningTemperatureOfMax: {
		id:       metricHostRuntimeWarningTemperatureOfMax,
		template: "supervisor/$HOSTNAME/host/runtime/warn_temperature_of_max",
	},
	metricHostRuntimeRevsFanSpeedOfMax: {
		id:       metricHostRuntimeRevsFanSpeedOfMax,
		template: "supervisor/$HOSTNAME/host/runtime/revs_fan_speed_of_max",
	},
	metricHostRuntimeLifeUsedDrives: {
		id:       metricHostRuntimeLifeUsedDrives,
		template: "supervisor/$HOSTNAME/host/runtime/lifetime_used_of_drives",
	},
	metricHostStorage: {
		id:       metricHostStorage,
		template: "supervisor/$HOSTNAME/host/storage",
	},
	metricHostStorageUsedSystemDrive: {
		id:       metricHostStorageUsedSystemDrive,
		template: "supervisor/$HOSTNAME/host/storage/used_system_drive",
	},
	metricHostStorageUsedShareDrives: {
		id:       metricHostStorageUsedShareDrives,
		template: "supervisor/$HOSTNAME/host/storage/used_share_drives",
	},
	metricHostStorageUsedBackupDrives: {
		id:       metricHostStorageUsedBackupDrives,
		template: "supervisor/$HOSTNAME/host/storage/used_backup_drives",
	},
	metricService: {
		id:       metricService,
		template: "supervisor/$HOSTNAME/service",
	},
	metricServiceName: {
		id:       metricServiceName,
		template: "supervisor/$HOSTNAME/service/$SERVICENAME/name",
	},
	metricServiceUsedProcessor: {
		id:       metricServiceUsedProcessor,
		template: "supervisor/$HOSTNAME/service/$SERVICENAME/used_processor",
	},
	metricServiceUsedMemory: {
		id:       metricServiceUsedMemory,
		template: "supervisor/$HOSTNAME/service/$SERVICENAME/used_memory",
	},
	metricServiceBackupStatus: {
		id:       metricServiceBackupStatus,
		template: "supervisor/$HOSTNAME/service/$SERVICENAME/backup_status",
	},
	metricServiceHealthStatus: {
		id:       metricServiceHealthStatus,
		template: "supervisor/$HOSTNAME/service/$SERVICENAME/health_status",
	},
	metricServiceConfiguredStatus: {
		id:       metricServiceConfiguredStatus,
		template: "supervisor/$HOSTNAME/service/$SERVICENAME/configured_status",
	},
	metricServiceRestartCount: {
		id:       metricServiceRestartCount,
		template: "supervisor/$HOSTNAME/service/$SERVICENAME/restart_count",
	},
	metricServiceRuntime: {
		id:       metricServiceRuntime,
		template: "supervisor/$HOSTNAME/service/$SERVICENAME/runtime",
	},
	metricServiceVersion: {
		id:       metricServiceVersion,
		template: "supervisor/$HOSTNAME/service/$SERVICENAME/version",
	},
}

var metricBuildersCache = func() map[string]metricBuilder {
	if len(metricBuilders) != int(metricMax) {
		panic(fmt.Sprintf("metricBuilders is incorrect length [%d], should use all (and only all) MetricID's (sans metricMax) giving length [%d]",
			len(metricBuilders), metricMax))
	}
	ids := make(map[MetricID]bool)
	templates := make(map[string]bool)
	builders := make(map[string]metricBuilder)
	for i := MetricID(0); i < metricMax; i++ {
		builders[metricBuilders[i].template] = metricBuilders[i]
	}
	for i := MetricID(0); i < metricMax; i++ {
		if err := metricBuilders[i].compile(ids, templates, builders); err != nil {
			panic(fmt.Sprintf("invalid metricBuilder at metricBuilders index [%d]: %v", i, err))
		}
	}
	return builders
}()

func getMetricBuilder(template string) (MetricID, error) {
	builder, ok := metricBuildersCache[template]
	if !ok {
		return -1, fmt.Errorf("unknown template %q", template)
	}
	return builder.id, nil
}

type MetricValue struct {
	OK    *bool  `msgpack:"ok,omitempty" json:"ok,omitempty"`
	Value string `msgpack:"value,omitempty" json:"value,omitempty"`
	Unit  string `msgpack:"unit,omitempty" json:"unit,omitempty"`
}

type MetricRecordSnapshot struct {
	Version   string                 `msgpack:"version" json:"version"`
	Timestamp time.Time              `msgpack:"timestamp" json:"timestamp"`
	Metrics   map[string]MetricValue `msgpack:"metrics" json:"metrics"`
}

type MetricRecordGUID struct {
	ID           MetricID
	Host         string
	ServiceIndex int
}

type MetricRecord struct {
	Topic     string
	Value     MetricValue
	Timestamp time.Time
}

type MetricRecordCache struct {
	lock    sync.Mutex
	dirty   []MetricRecordGUID
	records *treemap.Map
}

type metricBuilder struct {
	id       MetricID
	template string
	topic    string
}

var (
	templateFormatHost     = "supervisor/$HOSTNAME/host/"
	templateFormatService  = "supervisor/$HOSTNAME/service/$SERVICENAME/"
	templateFormatSnapshot = "supervisor/$HOSTNAME"
)

var (
	topicPattern        = regexp.MustCompile(`^supervisor(/[a-zA-Z0-9$_-]+){1,4}$`)
	topicPatternHost    = regexp.MustCompile(`^supervisor/([a-zA-Z0-9_-]+)/host/([a-zA-Z0-9_-]+(/[a-zA-Z0-9_-]+)*)$`)
	topicPatternService = regexp.MustCompile(`^supervisor/([a-zA-Z0-9_-]+)/service/([a-zA-Z0-9_-]+)/([a-zA-Z0-9_-]+(/[a-zA-Z0-9_-]+)*)$`)
)

func MarshalSnapshot(schemaPath string, records []MetricRecord) ([]byte, error) {
	if records == nil {
		return nil, fmt.Errorf("valueCache is nil")
	}
	version, err := GetVersion(schemaPath)
	if err != nil {
		return nil, err
	}
	snapshot := &MetricRecordSnapshot{
		Version:   version,
		Timestamp: time.Now(),
		Metrics:   make(map[string]MetricValue),
	}
	for _, record := range records {
		recordValueOK := ""
		if ok := record.Value.OK; ok != nil {
			recordValueOK = strconv.FormatBool(*ok)
		}
		snapshot.Metrics[record.Topic] = newMetricValue(
			recordValueOK,
			record.Value.Value,
			record.Value.Unit,
		)
	}
	return msgpack.Marshal(snapshot)
}

func UnmarshalSnapshot(snapshotMsgPack []byte) (*MetricRecordSnapshot, error) {
	if len(snapshotMsgPack) == 0 {
		return nil, fmt.Errorf("empty snapshot")
	}
	var snapshot MetricRecordSnapshot
	if err := msgpack.Unmarshal(snapshotMsgPack, &snapshot); err != nil {
		return nil, err
	}
	return &snapshot, nil
}

func newMetricRecordCache() *MetricRecordCache {
	return &MetricRecordCache{
		dirty:   make([]MetricRecordGUID, 0),
		records: treemap.NewWith(metricRecordGUIDComparator),
	}
}

func CacheRemoteMetrics(metrics map[string]MetricValue) (*MetricRecordCache, error) {
	topics := slices.Collect(maps.Keys(metrics))
	slices.Sort(topics)
	services := make(map[string]int)
	services[""] = -1
	cache := newMetricRecordCache()
	for _, topic := range topics {
		value := metrics[topic]
		builder := metricBuilder{topic: topic}
		template, host, service, err := builder.parse()
		if err != nil {
			return nil, fmt.Errorf("failed to parse topic %s: %w", topic, err)
		}
		id, err := getMetricBuilder(template)
		if err != nil {
			return nil, fmt.Errorf("failed to find samples builder for topic %s and template %s", topic, template)
		}
		if _, exists := services[service]; !exists {
			services[service] = len(services) - 1
		}
		cache.Put(
			MetricRecordGUID{id, host, services[service]},
			&MetricRecord{Topic: topic, Value: value},
		)
	}
	return cache, nil
}

func CacheLocalMetrics(hostName string, schemaPath string) (*MetricRecordCache, error) {

	//TODO: Design for concurrency
	// 	 -> keys are immutable, dont mutate them
	//   -> RWMutex around the TreeMap
	//   -> add batch update for bursty traffic
	//   -> add dirty flag per samples and get dirty metrics func
	//   -> have dirty reader execute after each batch update to update derived metrics and publish to mqtt for run mode
	//   -> have dirty reader execute every sec to update derived metrics and write to screen for stats mode
	//   -> have a samples timeout reappear service to blank out non updated metrics, maybe on snapshot+10 interval when snapshots are expected

	// TODO: How to reload for new or removed services
	//   -> OnChange triggered by Value and or ServiceIndex change
	//   -> input valueCache, if null LoadValue for first Time, otherwise use for onchnage
	//   -> have display work out if a service has been deleted and not replaced, to nil out display

	if hostName == "" {
		return nil, fmt.Errorf("host name not defined")
	}
	serviceNameSlice, err := GetServices(hostName, schemaPath)
	if err != nil {
		return nil, err
	}
	cache := newMetricRecordCache()
	for index := MetricID(0); index < metricMax; index++ {
		if metricBuilders[index].isHost() {
			topic, err := metricBuilders[index].buildHost(hostName)
			if err != nil {
				return nil, fmt.Errorf("host topic build error: %w", err)
			}
			cache.Put(
				MetricRecordGUID{metricBuilders[index].id, hostName, -1},
				&MetricRecord{Topic: topic},
			)
		} else {
			for serviceIndex, serviceName := range serviceNameSlice {
				topic, err := metricBuilders[index].buildService(hostName, serviceName)
				if err != nil {
					return nil, fmt.Errorf("service topic build error: %w", err)
				}
				cache.Put(
					MetricRecordGUID{metricBuilders[index].id, hostName, serviceIndex},
					&MetricRecord{Topic: topic},
				)
			}
		}
	}
	return cache, nil
}

func (cache *MetricRecordCache) Put(key MetricRecordGUID, record *MetricRecord) {
	if cache == nil || cache.records == nil || record == nil {
		return
	}
	cache.records.Put(key, record)
}

func (cache *MetricRecordCache) Get(key MetricRecordGUID) (*MetricRecord, bool) {
	if cache == nil || cache.records == nil {
		return nil, false
	}
	rawValue, found := cache.records.Get(key)
	if !found || rawValue == nil {
		return nil, false
	}
	record, ok := rawValue.(*MetricRecord)
	if !ok {
		return nil, false
	}
	return record, true
}

func (cache *MetricRecordCache) Keys() []MetricRecordGUID {
	if cache == nil || cache.records == nil {
		return nil
	}
	rawKeys := cache.records.Keys()
	recordGUIDs := make([]MetricRecordGUID, 0, len(rawKeys))
	for _, rawKey := range rawKeys {
		if recordGUID, ok := rawKey.(MetricRecordGUID); ok {
			recordGUIDs = append(recordGUIDs, recordGUID)
		}
	}
	return recordGUIDs
}

func (cache *MetricRecordCache) Size() int {
	if cache == nil || cache.records == nil {
		return 0
	}
	return cache.records.Size()
}

func (cache *MetricRecordCache) String() string {
	if cache == nil {
		return "<nil>"
	}
	var stringBuilder strings.Builder
	guids := cache.Keys()
	for index, guid := range guids {
		record, _ := cache.Get(guid)
		recordValueOK := ""
		if record.Value.OK != nil {
			recordValueOK = map[bool]string{true: "T", false: "F"}[*record.Value.OK]
		}
		_, err := fmt.Fprintf(
			&stringBuilder,
			"Index[%03d] Metric[%03d] ServiceIndex[%02v] Host[%v] OK[%1s] Value[%3s] Unit[%1v] topic[%s]\n",
			index,
			guid.ID,
			guid.ServiceIndex,
			guid.Host,
			recordValueOK,
			record.Value.Value,
			record.Value.Unit,
			record.Topic,
		)
		if err != nil {
			return ""
		}
	}
	return stringBuilder.String()
}

func metricRecordGUIDComparator(this, that interface{}) int {
	thisGUID, thisOK := this.(MetricRecordGUID)
	thatGUID, thatOK := that.(MetricRecordGUID)
	if !thisOK || !thatOK {
		panic("invalid key type")
	}
	switch {
	case thisGUID.Host < thatGUID.Host:
		return -1
	case thisGUID.Host > thatGUID.Host:
		return 1
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

func newMetricValue(ok string, value string, unit string) MetricValue {
	var okPointer *bool
	if ok != "" {
		okPointer = func() *bool { okVal := strings.ToLower(ok) == "true"; return &okVal }()
	}
	return MetricValue{
		OK:    okPointer,
		Value: value,
		Unit:  unit,
	}
}

func newMetricRecord(topic string, ok string, value string, unit string) MetricRecord {
	return MetricRecord{
		Topic:     topic,
		Value:     newMetricValue(ok, value, unit),
		Timestamp: time.Now(),
	}
}

func (builder metricBuilder) compile(ids map[MetricID]bool, templates map[string]bool, builders map[string]metricBuilder) error {
	if builder.id < MetricID(0) || builder.id > metricMax {
		return fmt.Errorf("invalid metricBuilder.id [%d]", builder.id)
	}
	if ids[builder.id] {
		return fmt.Errorf("duplicate metricBuilder.id [%d]", builder.id)
	}
	ids[builder.id] = true
	if builder.template == "" {
		return fmt.Errorf("invalid metricBuilder.template for metricBuilder.id [%d]", builder.id)
	}
	if templates[builder.template] {
		return fmt.Errorf("duplicate metricBuilder.template for metricBuilder.id [%d]", builder.id)
	}
	templates[builder.template] = true
	if builder.topic != "" {
		return fmt.Errorf("invalid metricBuilder.topic for metricBuilder.id [%d]", builder.id)
	}

	//hostName := "hostname-test"
	//serviceName := "serviceName-test"
	//topic, err := builder.build(map[string]string{"HOSTNAME": hostName, "SERVICENAME": serviceName})
	//if err != nil || topic == "" {
	//	return fmt.Errorf("invalid metricBuilder.template for metricBuilder.id [%d]: %v", builder.id, err)
	//}

	//_, _, _, err = (&metricBuilder{topic: topic}).parse()
	//if err != nil {
	//	return fmt.Errorf("invalid metricBuilder.topic for metricBuilder.id [%d]: %v", builder.id, err)
	//}

	//if builder.isHost() && !topicPattern.MatchString(topic) {
	//	return fmt.Errorf("service topic [%s] does not match expected pattern", topic)
	//}
	//if builder.isService() && !topicPatternService.MatchString(topic) {
	//	return fmt.Errorf("service topic [%s] does not match expected pattern", topic)
	//}

	// TODO: Fix topicPattern's/templateFormat's isHost, isService add isSnapshot? work off template and or topic return them in build/parse, collapse isFuncs to one enum driven switch impl, that works on topic and template, remove buildHost/Service, just use build
	// TODO: Work through init v runtime errors, how to handle - look at all exported func's, make errors consistent []/:

	return nil
}

func (builder metricBuilder) build(replacements map[string]string) (topic string, err error) {
	if builder.template == "" {
		return "", fmt.Errorf("cannot build with empty template")
	}
	if !topicPattern.MatchString(builder.template) {
		return "", fmt.Errorf("invalid topic template [%s]", builder.template)
	}
	pairs := make([]string, 0, len(replacements)*2)
	for key, value := range replacements {
		pairs = append(pairs, "$"+key, value)
	}
	topic = strings.NewReplacer(pairs...).Replace(builder.template)
	if strings.Contains(topic, "$") {
		return "", fmt.Errorf("invalid $TOKEN in template [%s]", builder.topic)
	}
	return topic, nil
}

func (builder metricBuilder) parse() (template string, host string, service string, err error) {
	if builder.topic == "" {
		return "", "", "", fmt.Errorf("cannot parse with empty topic")
	}
	if serviceMatch := topicPatternService.FindStringSubmatch(builder.topic); serviceMatch != nil {
		host = serviceMatch[1]
		service = serviceMatch[2]
		template = templateFormatService + serviceMatch[3]
	} else if hostMatch := topicPatternHost.FindStringSubmatch(builder.topic); hostMatch != nil {
		host = hostMatch[1]
		template = templateFormatHost + hostMatch[2]
	} else {
		return "", "", "", fmt.Errorf("topic [%s] does not match expected format", builder.topic)
	}
	return template, host, service, nil
}

func (builder metricBuilder) isHost() bool {
	return strings.Contains(builder.template, "$HOSTNAME") && !strings.Contains(builder.template, "$SERVICENAME")
}

func (builder metricBuilder) isService() bool {
	return strings.Contains(builder.template, "$HOSTNAME") && strings.Contains(builder.template, "$SERVICENAME")
}

func (builder metricBuilder) buildHost(hostName string) (string, error) {
	return builder.build(map[string]string{"HOSTNAME": hostName})
}

func (builder metricBuilder) buildService(hostName string, serviceName string) (string, error) {
	return builder.build(map[string]string{"HOSTNAME": hostName, "SERVICENAME": serviceName})
}
