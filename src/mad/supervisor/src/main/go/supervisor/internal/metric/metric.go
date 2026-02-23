package metric

import (
	"errors"
	"fmt"
	"log/slog"
	"maps"
	"regexp"
	"slices"
	"strconv"
	"strings"
	"supervisor/internal/config"
	"supervisor/internal/probe"
	"sync"
	"time"

	"github.com/vmihailenco/msgpack/v5"
)

// TODO: Reorder and remove comments

// Exported types
type ID int

// noinspection GoNameStartsWithPackageName
const (
	MetricAll ID = iota
	MetricHost
	MetricHostCompute
	MetricHostComputeUsedProcessor
	MetricHostComputeUsedMemory
	MetricHostComputeAllocatedMemory
	MetricHostHealth
	MetricHostHealthFailedServices
	MetricHostHealthFailedShares
	MetricHostHealthFailedBackups
	MetricHostRuntime
	MetricHostRuntimeWarningTemperatureOfMax
	MetricHostRuntimeRevsFanSpeedOfMax
	MetricHostRuntimeLifeUsedDrives
	MetricHostStorage
	MetricHostStorageUsedSystemDrive
	MetricHostStorageUsedShareDrives
	MetricHostStorageUsedBackupDrives
	MetricService
	MetricServiceName
	MetricServiceUsedProcessor
	MetricServiceUsedMemory
	MetricServiceBackupStatus
	MetricServiceHealthStatus
	MetricServiceConfiguredStatus
	MetricServiceRestartCount
	MetricServiceRuntime
	MetricServiceVersion
	MetricMax
)

type Value struct {
	OK    *bool  `msgpack:"ok,omitempty" json:"ok,omitempty"`
	Datum string `msgpack:"datum,omitempty" json:"datum,omitempty"`
	Unit  string `msgpack:"unit,omitempty" json:"unit,omitempty"`
}

type UpdatesListener interface {
	MarkDirty()
}

type RecordSnapshot struct {
	Version   string           `msgpack:"version" json:"version"`
	Timestamp int64            `msgpack:"timestamp" json:"timestamp"`
	Metrics   map[string]Value `msgpack:"metrics" json:"metrics"`
}

type RecordGUID struct {
	ID           ID
	Host         string
	ServiceIndex int
}

type Record struct {
	Topic       string
	Pulse       Value
	Trend       Value
	Timestamp   int64
	depsForward []RecordGUID
	depsReverse map[RecordGUID]struct{}
	depsCompute func(values []Value) Value
}

type RecordCache struct {
	mutex       sync.RWMutex
	records     map[RecordGUID]*Record
	notify      chan struct{}
	listeners   map[RecordGUID][]UpdatesListener
	depsPending map[RecordGUID]map[RecordGUID]struct{}
}

// Exported constructors
func MarshalSnapshot(configPath string, records []Record) ([]byte, error) {
	if records == nil {
		return nil, errors.New("value cache is nil")
	}
	configData, err := config.Load(configPath)
	if err != nil {
		return nil, fmt.Errorf("load config [%s]: %w", configPath, err)
	}
	snapshot := &RecordSnapshot{
		Version:   configData.Version(),
		Timestamp: time.Now().Unix(),
		Metrics:   make(map[string]Value),
	}
	for _, record := range records {
		recordValueOK := ""
		if ok := record.Pulse.OK; ok != nil {
			recordValueOK = strconv.FormatBool(*ok)
		}
		snapshot.Metrics[record.Topic] = newMetricValue(
			recordValueOK,
			record.Pulse.Datum,
			record.Pulse.Unit,
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

func NewRecordCache() *RecordCache {
	return &RecordCache{
		records:     make(map[RecordGUID]*Record),
		notify:      make(chan struct{}, 1),
		listeners:   make(map[RecordGUID][]UpdatesListener),
		depsPending: make(map[RecordGUID]map[RecordGUID]struct{}),
	}
}

func (c *RecordCache) LoadProbes(periods probe.Periods) error {
	// TODO:
	//  - Loop over all metrics and load into cache
	//  - Start probes for one cycle, writing to cache per metric
	return nil
}

func (c *RecordCache) LoadProbesListeners(periods probe.Periods) error {
	// TODO:
	//  - Loop over listeners, load each and its deps into cache
	//  - Start probes, writing to cache per metric
	return nil
}

func (c *RecordCache) LoadProbesPublishers(periods probe.Periods) error {
	// TODO:
	//  - Loop over all metrics and load into cache
	//  - Start probes, writing to cache per metric (necessary for deps, not for JSON/LineProto),
	//                  writing async cache.publishStream by value (JSON) per metric,
	//                  writing line protocol to reused buffer per metric,
	//                  writing async cache.publishHistory by value (String LineProto) at the end fo cycle
	return nil
}

func (c *RecordCache) LoadBrokerListeners(periods probe.Periods) error {
	// TODO:
	//  - Loop over listeners, load each and its deps into cache
	//  - Start topic subscriptions, writing to cache per metric
	//  - Start reaper routine, if timestamp > poll period + 1, set to nil
	return nil
}

func (c *RecordCache) Close() error {
	// TODO:
	//  - Stop all routines
	return nil
}

func CacheRemoteMetrics(metrics map[string]Value) (*RecordCache, error) {
	topics := slices.Collect(maps.Keys(metrics))
	slices.Sort(topics)
	services := make(map[string]int)
	services[""] = -1
	cache := NewRecordCache()
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
			&Record{Topic: topic, Pulse: value, Trend: value},
		)
	}
	return cache, nil
}

func CacheLocalMetrics(hostName string, configPath string) (*RecordCache, error) {
	//TODO: Design for concurrency
	// 	 -> keys are immutable, dont mutate them
	//   -> RWMutex around the Map
	//   -> have a samples timeout reappear service to blank out non updated metrics, maybe on snapshot+10 interval when snapshots are expected
	// TODO: How to reload for new or removed services
	//   -> OnChange triggered by Datum and or ServiceIndex change
	//   -> have display work out if a service has been deleted and not replaced, to nil out display
	if hostName == "" {
		return nil, errors.New("host name not defined")
	}
	configData, err := config.Load(configPath)
	if err != nil {
		return nil, fmt.Errorf("load config [%s]: %w", configPath, err)
	}
	serviceNameSlice := configData.Services(hostName)
	cache := NewRecordCache()
	for index := ID(0); index < MetricMax; index++ {
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

// Exported methods
func (c *RecordCache) Put(key RecordGUID, record *Record) {
	if c == nil || c.records == nil || record == nil {
		return
	}
	c.mutex.Lock()
	defer c.mutex.Unlock()
	c.records[key] = record
	if pendingDependents, found := c.depsPending[key]; found {
		if record.depsReverse == nil {
			record.depsReverse = make(map[RecordGUID]struct{})
		}
		for dependentID := range pendingDependents {
			record.depsReverse[dependentID] = struct{}{}
		}
		delete(c.depsPending, key)
	}
	for _, depID := range record.depsForward {
		if depRec, found := c.records[depID]; found && depRec != nil {
			if depRec.depsReverse == nil {
				depRec.depsReverse = make(map[RecordGUID]struct{})
			}
			depRec.depsReverse[key] = struct{}{}
			continue
		}
		if c.depsPending[depID] == nil {
			c.depsPending[depID] = make(map[RecordGUID]struct{})
		}
		c.depsPending[depID][key] = struct{}{}
	}
}

func (c *RecordCache) Get(key RecordGUID) (*Record, bool) {
	if c == nil || c.records == nil {
		return nil, false
	}
	c.mutex.RLock()
	defer c.mutex.RUnlock()
	record, found := c.records[key]
	return record, found
}

func (c *RecordCache) Set(key RecordGUID, value *Value) {
	if c == nil || value == nil {
		return
	}
	var listeners []UpdatesListener
	c.mutex.Lock()
	record, found := c.records[key]
	if !found || record == nil {
		c.mutex.Unlock()
		return
	}
	old := record.Pulse
	record.Pulse = *value
	record.Trend = *value
	record.Timestamp = time.Now().Unix()
	listeners = append(listeners, append([]UpdatesListener(nil), c.listeners[key]...)...)
	if old != record.Pulse {
		visited := make(map[RecordGUID]bool)
		listeners = c.propagateUpdateLocked(key, visited, listeners)
	}
	c.mutex.Unlock()
	for _, listener := range listeners {
		listener.MarkDirty()
	}
}

func (c *RecordCache) SubscribeUpdates(key RecordGUID, listener UpdatesListener) {
	if c == nil {
		return
	}
	c.mutex.Lock()
	defer c.mutex.Unlock()
	c.listeners[key] = append(c.listeners[key], listener)
}

func (c *RecordCache) Updates() <-chan struct{} {
	return c.notify
}

func (c *RecordCache) NotifyUpdates() {
	select {
	case c.notify <- struct{}{}:
	default:
	}
}

func (c *RecordCache) Keys() []RecordGUID {
	if c == nil || c.records == nil {
		return nil
	}
	c.mutex.RLock()
	defer c.mutex.RUnlock()
	recordGUIDs := make([]RecordGUID, 0, len(c.records))
	for key := range c.records {
		recordGUIDs = append(recordGUIDs, key)
	}
	return recordGUIDs
}

func (c *RecordCache) Hosts() []string {
	if c == nil || c.records == nil {
		return nil
	}
	c.mutex.RLock()
	hostMap := make(map[string]bool)
	for key := range c.records {
		hostMap[key.Host] = true
	}
	c.mutex.RUnlock()
	if len(hostMap) == 0 {
		return nil
	}
	hosts := make([]string, 0, len(hostMap))
	for host := range hostMap {
		hosts = append(hosts, host)
	}
	slices.Sort(hosts)
	return hosts
}

func (c *RecordCache) Size() int {
	if c == nil || c.records == nil {
		return 0
	}
	c.mutex.RLock()
	defer c.mutex.RUnlock()
	return len(c.records)
}

func (c *RecordCache) String() string {
	if c == nil {
		return "<nil>"
	}
	type recordStringEntry struct {
		guid  RecordGUID
		topic string
		value Value
	}
	c.mutex.RLock()
	entries := make([]recordStringEntry, 0, len(c.records))
	for guid, record := range c.records {
		if record == nil {
			continue
		}
		entries = append(entries, recordStringEntry{
			guid:  guid,
			topic: record.Topic,
			value: record.Pulse,
		})
	}
	c.mutex.RUnlock()
	slices.SortFunc(entries, func(a, b recordStringEntry) int {
		return compareRecordGUID(a.guid, b.guid)
	})
	var stringBuilder strings.Builder
	for index, entry := range entries {
		recordValueOK := ""
		if entry.value.OK != nil {
			recordValueOK = map[bool]string{true: "T", false: "F"}[*entry.value.OK]
		}
		_, err := fmt.Fprintf(
			&stringBuilder,
			"Index[%03d] Metric[%03d] ServiceIndex[%02v] Host[%v] OK[%1s] Datum[%3s] Unit[%1v] topic[%s]\n",
			index,
			entry.guid.ID,
			entry.guid.ServiceIndex,
			entry.guid.Host,
			recordValueOK,
			entry.value.Datum,
			entry.value.Unit,
			entry.topic,
		)
		if err != nil {
			return ""
		}
	}
	return stringBuilder.String()
}

// Unexported types
type builder struct {
	id       ID
	template string
	topic    string
}

// Unexported functions
func metricFromTemplate(template string) (ID, error) {
	builder, ok := metricBuildersCache[template]
	if !ok {
		return -1, fmt.Errorf("unknown template [%s]", template)
	}
	return builder.id, nil
}

func compareRecordGUID(this, that RecordGUID) int {
	switch {
	case this.Host < that.Host:
		return -1
	case this.Host > that.Host:
		return 1
	case this.ServiceIndex < that.ServiceIndex:
		return -1
	case this.ServiceIndex > that.ServiceIndex:
		return 1
	case this.ID < that.ID:
		return -1
	case this.ID > that.ID:
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
		Datum: value,
		Unit:  unit,
	}
}

func newMetricRecord(topic string, ok string, value string, unit string) Record {
	return Record{
		Topic:     topic,
		Pulse:     newMetricValue(ok, value, unit),
		Trend:     newMetricValue(ok, value, unit),
		Timestamp: time.Now().Unix(),
	}
}

func (c *RecordCache) propagateUpdateLocked(updatedID RecordGUID, visited map[RecordGUID]bool, listeners []UpdatesListener) []UpdatesListener {
	if visited[updatedID] {
		slog.Error("Circular dependency detected in metric calculation graph", "record", updatedID)
		return listeners
	}
	visited[updatedID] = true
	updatedRecord, found := c.records[updatedID]
	if !found || updatedRecord == nil {
		return listeners
	}
	for dependentID := range updatedRecord.depsReverse {
		record, found := c.records[dependentID]
		if !found || record == nil {
			continue
		}
		if record.depsCompute == nil {
			continue
		}
		var depValues []Value
		for _, depRecordGUID := range record.depsForward {
			if depRecord, found := c.records[depRecordGUID]; found {
				depValues = append(depValues, depRecord.Pulse)
			}
		}
		oldValue := record.Pulse
		newValue := record.depsCompute(depValues)
		if newValue != oldValue {
			record.Pulse = newValue
			record.Trend = newValue
			record.Timestamp = time.Now().Unix()
			listeners = append(listeners, append([]UpdatesListener(nil), c.listeners[dependentID]...)...)
			listeners = c.propagateUpdateLocked(dependentID, visited, listeners)
		}
	}
	return listeners
}

func (b builder) compile(ids map[ID]bool, templates map[string]bool, builders map[string]builder) error {
	if b.id < ID(0) || b.id >= MetricMax {
		return fmt.Errorf("invalid ID [%d]", b.id)
	}
	if ids[b.id] {
		return fmt.Errorf("duplicate ID [%d]", b.id)
	}
	ids[b.id] = true
	if b.template == "" {
		return fmt.Errorf("empty template for ID [%d]", b.id)
	}
	if templates[b.template] {
		return fmt.Errorf("duplicate template [%s] for ID [%d]", b.template, b.id)
	}
	templates[b.template] = true
	if b.topic != "" {
		return fmt.Errorf("topic already exists for ID [%d]", b.id)
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
	//if b.isHost() && !templatePattern.MatchString(topic) {
	//	return fmt.Errorf("service topic [%s] does not match expected pattern", topic)
	//}
	//if b.isService() && !topicPatternService.MatchString(topic) {
	//	return fmt.Errorf("service topic [%s] does not match expected pattern", topic)
	//}

	// TODO: Remove deps fields, add a compile time deps list against metricID, add to cache in listener load funcs
	// TODO: Add influxdb tag/metric labels to metricID
	// TODO: Fix templatePattern's/templateFormat's isHost, isService add isSnapshot? work off template and or topic return them in build/parse, collapse isFuncs to one enum driven switch impl, that works on topic and template, remove buildHost/Service, just use build
	// TODO: Work through init v runtime errors, how to handle - look at all exported func's

	return nil
}

func (b builder) build(replacements map[string]string) (topic string, err error) {
	if b.template == "" {
		return "", errors.New("cannot build with empty template")
	}
	if !templatePattern.MatchString(b.template) {
		return "", fmt.Errorf("invalid topic template [%s]", b.template)
	}
	pairs := make([]string, 0, len(replacements)*2)
	for key, value := range replacements {
		pairs = append(pairs, "$"+key, value)
	}
	topic = strings.NewReplacer(pairs...).Replace(b.template)
	if strings.Contains(topic, "$") {
		return "", fmt.Errorf("invalid $TOKEN in template [%s]", b.template)
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

// Unexported variables
var metricBuilders = []builder{
	MetricAll: {
		id:       MetricAll,
		template: "supervisor/$HOSTNAME",
	},
	MetricHost: {
		id:       MetricHost,
		template: "supervisor/$HOSTNAME/host",
	},
	MetricHostCompute: {
		id:       MetricHostCompute,
		template: "supervisor/$HOSTNAME/host/depsCompute",
	},
	MetricHostComputeUsedProcessor: {
		id:       MetricHostComputeUsedProcessor,
		template: "supervisor/$HOSTNAME/host/depsCompute/used_processor",
	},
	MetricHostComputeUsedMemory: {
		id:       MetricHostComputeUsedMemory,
		template: "supervisor/$HOSTNAME/host/depsCompute/used_memory",
	},
	MetricHostComputeAllocatedMemory: {
		id:       MetricHostComputeAllocatedMemory,
		template: "supervisor/$HOSTNAME/host/depsCompute/allocated_memory",
	},
	MetricHostHealth: {
		id:       MetricHostHealth,
		template: "supervisor/$HOSTNAME/host/health",
	},
	MetricHostHealthFailedServices: {
		id:       MetricHostHealthFailedServices,
		template: "supervisor/$HOSTNAME/host/health/failed_services",
	},
	MetricHostHealthFailedShares: {
		id:       MetricHostHealthFailedShares,
		template: "supervisor/$HOSTNAME/host/health/failed_shares",
	},
	MetricHostHealthFailedBackups: {
		id:       MetricHostHealthFailedBackups,
		template: "supervisor/$HOSTNAME/host/health/failed_backups",
	},
	MetricHostRuntime: {
		id:       MetricHostRuntime,
		template: "supervisor/$HOSTNAME/host/runtime",
	},
	MetricHostRuntimeWarningTemperatureOfMax: {
		id:       MetricHostRuntimeWarningTemperatureOfMax,
		template: "supervisor/$HOSTNAME/host/runtime/warn_temperature_of_max",
	},
	MetricHostRuntimeRevsFanSpeedOfMax: {
		id:       MetricHostRuntimeRevsFanSpeedOfMax,
		template: "supervisor/$HOSTNAME/host/runtime/revs_fan_speed_of_max",
	},
	MetricHostRuntimeLifeUsedDrives: {
		id:       MetricHostRuntimeLifeUsedDrives,
		template: "supervisor/$HOSTNAME/host/runtime/lifetime_used_of_drives",
	},
	MetricHostStorage: {
		id:       MetricHostStorage,
		template: "supervisor/$HOSTNAME/host/storage",
	},
	MetricHostStorageUsedSystemDrive: {
		id:       MetricHostStorageUsedSystemDrive,
		template: "supervisor/$HOSTNAME/host/storage/used_system_drive",
	},
	MetricHostStorageUsedShareDrives: {
		id:       MetricHostStorageUsedShareDrives,
		template: "supervisor/$HOSTNAME/host/storage/used_share_drives",
	},
	MetricHostStorageUsedBackupDrives: {
		id:       MetricHostStorageUsedBackupDrives,
		template: "supervisor/$HOSTNAME/host/storage/used_backup_drives",
	},
	MetricService: {
		id:       MetricService,
		template: "supervisor/$HOSTNAME/service",
	},
	MetricServiceName: {
		id:       MetricServiceName,
		template: "supervisor/$HOSTNAME/service/$SERVICENAME/name",
	},
	MetricServiceUsedProcessor: {
		id:       MetricServiceUsedProcessor,
		template: "supervisor/$HOSTNAME/service/$SERVICENAME/used_processor",
	},
	MetricServiceUsedMemory: {
		id:       MetricServiceUsedMemory,
		template: "supervisor/$HOSTNAME/service/$SERVICENAME/used_memory",
	},
	MetricServiceBackupStatus: {
		id:       MetricServiceBackupStatus,
		template: "supervisor/$HOSTNAME/service/$SERVICENAME/backup_status",
	},
	MetricServiceHealthStatus: {
		id:       MetricServiceHealthStatus,
		template: "supervisor/$HOSTNAME/service/$SERVICENAME/health_status",
	},
	MetricServiceConfiguredStatus: {
		id:       MetricServiceConfiguredStatus,
		template: "supervisor/$HOSTNAME/service/$SERVICENAME/configured_status",
	},
	MetricServiceRestartCount: {
		id:       MetricServiceRestartCount,
		template: "supervisor/$HOSTNAME/service/$SERVICENAME/restart_count",
	},
	MetricServiceRuntime: {
		id:       MetricServiceRuntime,
		template: "supervisor/$HOSTNAME/service/$SERVICENAME/runtime",
	},
	MetricServiceVersion: {
		id:       MetricServiceVersion,
		template: "supervisor/$HOSTNAME/service/$SERVICENAME/version",
	},
}

var metricBuildersCache = func() map[string]builder {
	if len(metricBuilders) != int(MetricMax) {
		panic(fmt.Sprintf("metricBuilders is incorrect length [%d], should use all (and only all) ID's (sans MetricMax) giving length [%d]",
			len(metricBuilders), MetricMax))
	}
	ids := make(map[ID]bool)
	templates := make(map[string]bool)
	builders := make(map[string]builder)
	for i := ID(0); i < MetricMax; i++ {
		builders[metricBuilders[i].template] = metricBuilders[i]
	}
	for i := ID(0); i < MetricMax; i++ {
		if err := metricBuilders[i].compile(ids, templates, builders); err != nil {
			panic(fmt.Sprintf("invalid builder at metricBuilders index [%d]: %v", i, err))
		}
	}
	return builders
}()

var (
	templateFormatHost    = "supervisor/$HOSTNAME/host/"
	templateFormatService = "supervisor/$HOSTNAME/service/$SERVICENAME/"
)

var (
	templatePattern     = regexp.MustCompile(`^supervisor(/[a-zA-Z0-9$_-]+){1,4}$`)
	topicPatternHost    = regexp.MustCompile(`^supervisor/([a-zA-Z0-9_-]+)/host/([a-zA-Z0-9_-]+(/[a-zA-Z0-9_-]+)*)$`)
	topicPatternService = regexp.MustCompile(`^supervisor/([a-zA-Z0-9_-]+)/service/([a-zA-Z0-9_-]+)/([a-zA-Z0-9_-]+(/[a-zA-Z0-9_-]+)*)$`)
)
