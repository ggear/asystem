package metric

import (
	"errors"
	"fmt"
	"maps"
	"regexp"
	"slices"
	"strconv"
	"strings"
	"supervisor/internal/schema"
	"sync"
	"time"

	"github.com/emirpasic/gods/maps/treemap"
	"github.com/vmihailenco/msgpack/v5"
)

type ID int

const (
	metricAll ID = iota
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

var metricBuilders = []builder{
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

var metricBuildersCache = func() map[string]builder {
	if len(metricBuilders) != int(metricMax) {
		panic(fmt.Sprintf("metricBuilders is incorrect length [%d], should use all (and only all) ID's (sans metricMax) giving length [%d]",
			len(metricBuilders), metricMax))
	}
	ids := make(map[ID]bool)
	templates := make(map[string]bool)
	builders := make(map[string]builder)
	for i := ID(0); i < metricMax; i++ {
		builders[metricBuilders[i].template] = metricBuilders[i]
	}
	for i := ID(0); i < metricMax; i++ {
		if err := metricBuilders[i].compile(ids, templates, builders); err != nil {
			panic(fmt.Sprintf("invalid builder at metricBuilders index [%d]: %v", i, err))
		}
	}
	return builders
}()

func metricFromTemplate(template string) (ID, error) {
	builder, ok := metricBuildersCache[template]
	if !ok {
		return -1, fmt.Errorf("unknown template [%s]", template)
	}
	return builder.id, nil
}

type Value struct {
	OK    *bool  `msgpack:"ok,omitempty" json:"ok,omitempty"`
	Value string `msgpack:"value,omitempty" json:"value,omitempty"`
	Unit  string `msgpack:"unit,omitempty" json:"unit,omitempty"`
}

type RecordSnapshot struct {
	Version   string           `msgpack:"version" json:"version"`
	Timestamp time.Time        `msgpack:"timestamp" json:"timestamp"`
	Metrics   map[string]Value `msgpack:"metrics" json:"metrics"`
}

type RecordGUID struct {
	ID           ID
	Host         string
	ServiceIndex int
}

type Record struct {
	Topic     string
	Value     Value
	Timestamp time.Time
}

type RecordCache struct {
	lock    sync.Mutex
	dirty   []RecordGUID
	records *treemap.Map
}

type builder struct {
	id       ID
	template string
	topic    string
}

var (
	templateFormatHost    = "supervisor/$HOSTNAME/host/"
	templateFormatService = "supervisor/$HOSTNAME/service/$SERVICENAME/"
)

var (
	topicPattern        = regexp.MustCompile(`^supervisor(/[a-zA-Z0-9$_-]+){1,4}$`)
	topicPatternHost    = regexp.MustCompile(`^supervisor/([a-zA-Z0-9_-]+)/host/([a-zA-Z0-9_-]+(/[a-zA-Z0-9_-]+)*)$`)
	topicPatternService = regexp.MustCompile(`^supervisor/([a-zA-Z0-9_-]+)/service/([a-zA-Z0-9_-]+)/([a-zA-Z0-9_-]+(/[a-zA-Z0-9_-]+)*)$`)
)

func MarshalSnapshot(schemaPath string, records []Record) ([]byte, error) {
	if records == nil {
		return nil, errors.New("value cache is nil")
	}
	schemaData, err := schema.Load(schemaPath)
	if err != nil {
		return nil, fmt.Errorf("load schema [%s]: %w", schemaPath, err)
	}
	snapshot := &RecordSnapshot{
		Version:   schemaData.Version(),
		Timestamp: time.Now(),
		Metrics:   make(map[string]Value),
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
	encoded, err := msgpack.Marshal(snapshot)
	if err != nil {
		return nil, fmt.Errorf("marshal snapshot: %w", err)
	}
	return encoded, nil
}

func UnmarshalSnapshot(snapshotMsgPack []byte) (*RecordSnapshot, error) {
	if len(snapshotMsgPack) == 0 {
		return nil, errors.New("empty snapshot")
	}
	var snapshot RecordSnapshot
	if err := msgpack.Unmarshal(snapshotMsgPack, &snapshot); err != nil {
		return nil, fmt.Errorf("unmarshal snapshot: %w", err)
	}
	return &snapshot, nil
}

func newMetricRecordCache() *RecordCache {
	return &RecordCache{
		dirty:   make([]RecordGUID, 0),
		records: treemap.NewWith(metricRecordGUIDComparator),
	}
}

func CacheRemoteMetrics(metrics map[string]Value) (*RecordCache, error) {
	topics := slices.Collect(maps.Keys(metrics))
	slices.Sort(topics)
	services := make(map[string]int)
	services[""] = -1
	cache := newMetricRecordCache()
	for _, topic := range topics {
		value := metrics[topic]
		builder := builder{topic: topic}
		template, host, service, err := builder.parse()
		if err != nil {
			return nil, fmt.Errorf("parse topic [%s]: %w", topic, err)
		}
		id, err := metricFromTemplate(template)
		if err != nil {
			return nil, fmt.Errorf("find samples builder for topic [%s] and template [%s]: %w", topic, template, err)
		}
		if _, exists := services[service]; !exists {
			services[service] = len(services) - 1
		}
		cache.Put(
			RecordGUID{id, host, services[service]},
			&Record{Topic: topic, Value: value},
		)
	}
	return cache, nil
}

func CacheLocalMetrics(hostName string, schemaPath string) (*RecordCache, error) {
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
		return nil, errors.New("host name not defined")
	}
	schemaData, err := schema.Load(schemaPath)
	if err != nil {
		return nil, fmt.Errorf("load schema [%s]: %w", schemaPath, err)
	}
	serviceNameSlice := schemaData.Services(hostName)
	cache := newMetricRecordCache()
	for index := ID(0); index < metricMax; index++ {
		if metricBuilders[index].isHost() {
			topic, err := metricBuilders[index].buildHost(hostName)
			if err != nil {
				return nil, fmt.Errorf("host topic build error: %w", err)
			}
			cache.Put(
				RecordGUID{metricBuilders[index].id, hostName, -1},
				&Record{Topic: topic},
			)
		} else {
			for serviceIndex, serviceName := range serviceNameSlice {
				topic, err := metricBuilders[index].buildService(hostName, serviceName)
				if err != nil {
					return nil, fmt.Errorf("service topic build error: %w", err)
				}
				cache.Put(
					RecordGUID{metricBuilders[index].id, hostName, serviceIndex},
					&Record{Topic: topic},
				)
			}
		}
	}
	return cache, nil
}

func (c *RecordCache) Put(key RecordGUID, record *Record) {
	if c == nil || c.records == nil || record == nil {
		return
	}
	c.records.Put(key, record)
}

func (c *RecordCache) Get(key RecordGUID) (*Record, bool) {
	if c == nil || c.records == nil {
		return nil, false
	}
	rawValue, found := c.records.Get(key)
	if !found || rawValue == nil {
		return nil, false
	}
	record, ok := rawValue.(*Record)
	if !ok {
		return nil, false
	}
	return record, true
}

func (c *RecordCache) Keys() []RecordGUID {
	if c == nil || c.records == nil {
		return nil
	}
	rawKeys := c.records.Keys()
	recordGUIDs := make([]RecordGUID, 0, len(rawKeys))
	for _, rawKey := range rawKeys {
		if recordGUID, ok := rawKey.(RecordGUID); ok {
			recordGUIDs = append(recordGUIDs, recordGUID)
		}
	}
	return recordGUIDs
}

func (c *RecordCache) Size() int {
	if c == nil || c.records == nil {
		return 0
	}
	return c.records.Size()
}

func (c *RecordCache) String() string {
	if c == nil {
		return "<nil>"
	}
	var stringBuilder strings.Builder
	guids := c.Keys()
	for index, guid := range guids {
		record, _ := c.Get(guid)
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
	thisGUID, thisOK := this.(RecordGUID)
	thatGUID, thatOK := that.(RecordGUID)
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

func newMetricValue(ok string, value string, unit string) Value {
	var okPointer *bool
	if ok != "" {
		okPointer = func() *bool { okVal := strings.ToLower(ok) == "true"; return &okVal }()
	}
	return Value{
		OK:    okPointer,
		Value: value,
		Unit:  unit,
	}
}

func newMetricRecord(topic string, ok string, value string, unit string) Record {
	return Record{
		Topic:     topic,
		Value:     newMetricValue(ok, value, unit),
		Timestamp: time.Now(),
	}
}

func (b builder) compile(ids map[ID]bool, templates map[string]bool, builders map[string]builder) error {
	if b.id < ID(0) || b.id > metricMax {
		return fmt.Errorf("invalid builder.id [%d]", b.id)
	}
	if ids[b.id] {
		return fmt.Errorf("duplicate builder.id [%d]", b.id)
	}
	ids[b.id] = true
	if b.template == "" {
		return fmt.Errorf("invalid builder.template for builder.id [%d]", b.id)
	}
	if templates[b.template] {
		return fmt.Errorf("duplicate builder.template for builder.id [%d]", b.id)
	}
	templates[b.template] = true
	if b.topic != "" {
		return fmt.Errorf("invalid builder.topic for builder.id [%d]", b.id)
	}






	//hostName := "hostname-test"
	//serviceName := "serviceName-test"
	//topic, err := b.build(map[string]string{"HOSTNAME": hostName, "SERVICENAME": serviceName})
	//if err != nil || topic == "" {
	//	return fmt.Errorf("invalid builder.template for builder.id [%d]: %v", b.id, err)
	//}
	//_, _, _, err = (&builder{topic: topic}).parse()
	//if err != nil {
	//	return fmt.Errorf("invalid builder.topic for builder.id [%d]: %v", b.id, err)
	//}
	//if b.isHost() && !topicPattern.MatchString(topic) {
	//	return fmt.Errorf("service topic [%s] does not match expected pattern", topic)
	//}
	//if b.isService() && !topicPatternService.MatchString(topic) {
	//	return fmt.Errorf("service topic [%s] does not match expected pattern", topic)
	//}
	// TODO: Fix topicPattern's/templateFormat's isHost, isService add isSnapshot? work off template and or topic return them in build/parse, collapse isFuncs to one enum driven switch impl, that works on topic and template, remove buildHost/Service, just use build
	// TODO: Work through init v runtime errors, how to handle - look at all exported func's






	return nil
}

func (b builder) build(replacements map[string]string) (topic string, err error) {
	if b.template == "" {
		return "", errors.New("cannot build with empty template")
	}
	if !topicPattern.MatchString(b.template) {
		return "", fmt.Errorf("invalid topic template [%s]", b.template)
	}
	pairs := make([]string, 0, len(replacements)*2)
	for key, value := range replacements {
		pairs = append(pairs, "$"+key, value)
	}
	topic = strings.NewReplacer(pairs...).Replace(b.template)
	if strings.Contains(topic, "$") {
		return "", fmt.Errorf("invalid $TOKEN in template [%s]", b.topic)
	}
	return topic, nil
}

func (b builder) parse() (template string, host string, service string, err error) {
	if b.topic == "" {
		return "", "", "", errors.New("cannot parse with empty topic")
	}
	if serviceMatch := topicPatternService.FindStringSubmatch(b.topic); serviceMatch != nil {
		host = serviceMatch[1]
		service = serviceMatch[2]
		template = templateFormatService + serviceMatch[3]
	} else if hostMatch := topicPatternHost.FindStringSubmatch(b.topic); hostMatch != nil {
		host = hostMatch[1]
		template = templateFormatHost + hostMatch[2]
	} else {
		return "", "", "", fmt.Errorf("topic [%s] does not match expected format", b.topic)
	}
	return template, host, service, nil
}

func (b builder) isHost() bool {
	return strings.Contains(b.template, "$HOSTNAME") && !strings.Contains(b.template, "$SERVICENAME")
}

func (b builder) isService() bool {
	return strings.Contains(b.template, "$HOSTNAME") && strings.Contains(b.template, "$SERVICENAME")
}

func (b builder) buildHost(hostName string) (string, error) {
	return b.build(map[string]string{"HOSTNAME": hostName})
}

func (b builder) buildService(hostName string, serviceName string) (string, error) {
	return b.build(map[string]string{"HOSTNAME": hostName, "SERVICENAME": serviceName})
}
