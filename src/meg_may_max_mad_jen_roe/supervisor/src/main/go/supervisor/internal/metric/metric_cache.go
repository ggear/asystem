package metric

import (
	"fmt"
	"reflect"
	"slices"
	"strings"
	"sync"
	"time"
)

type TopicBinding struct {
	Topic string
	GUID  RecordGUID
}

type RecordGUID struct {
	ID           ID
	Host         string
	ServiceName  string
	ServiceIndex int
}

type guidKey struct {
	ID          ID
	Host        string
	ServiceName string
}

type indexKey struct {
	ID           ID
	Host         string
	ServiceIndex int
}

func (g RecordGUID) key() guidKey {
	return guidKey{ID: g.ID, Host: g.Host, ServiceName: g.ServiceName}
}

func NewRecordGUID(id ID, hostName string) RecordGUID {
	return RecordGUID{
		ID:           id,
		Host:         hostName,
		ServiceName:  ServiceNameUnset,
		ServiceIndex: ServiceIndexUnset,
	}
}

func NewServiceRecordGUID(id ID, hostName, serviceName string) RecordGUID {
	return RecordGUID{
		ID:           id,
		Host:         hostName,
		ServiceName:  serviceName,
		ServiceIndex: ServiceIndexUnset,
	}
}

func NewServiceSchemaRecordGUID(id ID, hostName string, serviceIndex int) RecordGUID {
	serviceNameResolved := ServiceNameUnset
	serviceIndexResolved := ServiceIndexUnset
	if GetIDKind(id) == MetricKindService {
		serviceNameResolved = ServiceNameSchema
		serviceIndexResolved = serviceIndex
	}
	return RecordGUID{
		ID:           id,
		Host:         hostName,
		ServiceName:  serviceNameResolved,
		ServiceIndex: serviceIndexResolved,
	}
}

type Record struct {
	Topic string
	Tags  map[string]string
	Value ValueData
}

func NewRecord(value ValueData) Record {
	return Record{
		Value: value,
	}
}

type UpdatesListener interface {
	MarkDirty()
}

type DeletesListener interface {
	Unsubscribe(topic string)
}

type RecordCache struct {
	mutex           sync.RWMutex
	guids           []RecordGUID
	records         map[guidKey]*Record
	serviceIndex    map[indexKey]guidKey
	notify          chan struct{}
	listeners       map[guidKey][]UpdatesListener
	deletesListener DeletesListener
	dirty           map[guidKey]RecordGUID
}

func NewRecordCache() *RecordCache {
	return &RecordCache{
		guids:        make([]RecordGUID, 0),
		records:      make(map[guidKey]*Record),
		serviceIndex: make(map[indexKey]guidKey),
		notify:       make(chan struct{}, 1),
		listeners:    make(map[guidKey][]UpdatesListener),
		dirty:        make(map[guidKey]RecordGUID),
	}
}

func (c *RecordCache) Close() error {
	// TODO:
	//  - Stop all routines
	return nil
}

func (c *RecordCache) Store(guid RecordGUID, record *Record) {
	if c == nil || record == nil {
		return
	}
	var listeners []UpdatesListener
	notify := true
	k := guid.key()
	nilValue := NewNilValue()
	c.mutex.Lock()
	cached, found := c.records[k]
	if found && cached != nil && cached.Value.Equal(&record.Value) {
		notify = false
	}
	index, exists := slices.BinarySearchFunc(c.guids, guid, compareRecordGUID)
	if !exists {
		c.guids = slices.Insert(c.guids, index, guid)
		c.records[k] = record
		c.reindex()
		guid = c.guids[index]
	} else {
		guid = c.guids[index]
		snapshot := *record
		if snapshot.Topic == "" && cached != nil {
			snapshot.Topic = cached.Topic
			snapshot.Tags = cached.Tags
		}
		c.records[k] = &snapshot
	}
	if notify && (!record.Value.Equal(&nilValue) || (found && cached != nil && !cached.Value.Equal(&nilValue))) {
		c.dirty[k] = guid
	}
	listeners = append([]UpdatesListener(nil), c.listeners[k]...)
	if notify && GetIDKind(guid.ID) == MetricKindService && guid.ServiceName != ServiceNameUnset && guid.ServiceName != ServiceNameSchema {
		schemaKey := guidKey{ID: guid.ID, Host: guid.Host, ServiceName: ServiceNameSchema}
		listeners = append(listeners, c.listeners[schemaKey]...)
	}
	c.mutex.Unlock()
	if notify {
		for _, listener := range listeners {
			listener.MarkDirty()
		}
		c.NotifyUpdates()
	}
}

func (c *RecordCache) ForceRegisterService(hostName, serviceName string) {
	if c == nil || hostName == "" || serviceName == "" || serviceName == ServiceNameUnset || strings.HasPrefix(serviceName, ServiceNameSchema) {
		return
	}
	c.mutex.Lock()
	added := false
	for id := ID(0); id < MetricMax; id++ {
		if GetIDKind(id) != MetricKindService {
			continue
		}
		guid := RecordGUID{ID: id, Host: hostName, ServiceName: serviceName, ServiceIndex: ServiceIndexUnset}
		gk := guid.key()
		if _, exists := c.records[gk]; exists {
			continue
		}
		record := NewRecord(NewNilValue())
		index, exists := slices.BinarySearchFunc(c.guids, guid, compareRecordGUID)
		if !exists {
			c.guids = slices.Insert(c.guids, index, guid)
			c.records[gk] = &record
			added = true
		}
	}
	if !added {
		c.mutex.Unlock()
		return
	}
	c.reindex()
	c.mutex.Unlock()
	c.NotifyUpdates()
}

func (c *RecordCache) RegisterService(hostName, serviceName string) []TopicBinding {
	if c == nil || hostName == "" || serviceName == "" || serviceName == ServiceNameUnset || strings.HasPrefix(serviceName, ServiceNameSchema) {
		return nil
	}
	c.mutex.Lock()
	added := false
	for k := range c.listeners {
		if k.Host != hostName || GetIDKind(k.ID) != MetricKindService {
			continue
		}
		guid := RecordGUID{ID: k.ID, Host: hostName, ServiceName: serviceName, ServiceIndex: ServiceIndexUnset}
		gk := guid.key()
		if _, exists := c.records[gk]; exists {
			continue
		}
		record := NewRecord(NewNilValue())
		index, exists := slices.BinarySearchFunc(c.guids, guid, compareRecordGUID)
		if !exists {
			c.guids = slices.Insert(c.guids, index, guid)
			c.records[gk] = &record
			added = true
		}
	}
	if !added {
		c.mutex.Unlock()
		return nil
	}
	c.reindex()
	var bindings []TopicBinding
	for _, guid := range c.guids {
		if guid.Host != hostName || guid.ServiceName != serviceName {
			continue
		}
		if guid.ID == MetricServiceName {
			continue
		}
		record := c.records[guid.key()]
		if record == nil || record.Topic == "" {
			continue
		}
		bindings = append(bindings, TopicBinding{Topic: record.Topic, GUID: guid})
	}
	c.mutex.Unlock()
	c.NotifyUpdates()
	return bindings
}

func (c *RecordCache) Load(guid RecordGUID) (*Record, bool) {
	if c == nil {
		return nil, false
	}
	c.mutex.RLock()
	defer c.mutex.RUnlock()
	record, found := c.records[guid.key()]
	if !found || record == nil {
		return nil, false
	}
	snapshot := *record
	return &snapshot, true
}

func (c *RecordCache) LoadByID(id ID, hostName string, serviceIndex int) (*Record, bool) {
	if c == nil {
		return nil, false
	}
	c.mutex.RLock()
	defer c.mutex.RUnlock()

	var record *Record
	if serviceIndex == ServiceIndexUnset {
		guid := NewRecordGUID(id, hostName)
		record = c.records[guid.key()]
	} else {
		key, found := c.serviceIndex[indexKey{ID: id, Host: hostName, ServiceIndex: serviceIndex}]
		if !found {
			return nil, false
		}
		record = c.records[key]
	}
	if record == nil {
		return nil, false
	}
	snapshot := *record
	return &snapshot, true
}

func (c *RecordCache) Evict(hostName, serviceName string) bool {
	if c == nil || hostName == "" || serviceName == ServiceNameUnset || strings.HasPrefix(serviceName, ServiceNameSchema) {
		return false
	}
	nilValue := NewNilValue()
	c.mutex.Lock()
	var allListeners []UpdatesListener
	evicted := false
	for _, guid := range c.guids {
		if guid.Host != hostName || guid.ServiceName != serviceName {
			continue
		}
		k := guid.key()
		record := c.records[k]
		if record == nil || record.Value.Equal(&nilValue) {
			continue
		}
		c.records[k] = &Record{Topic: record.Topic, Tags: record.Tags, Value: nilValue}
		c.dirty[k] = guid
		allListeners = append(allListeners, c.listeners[k]...)
		if GetIDKind(guid.ID) == MetricKindService {
			schemaKey := guidKey{ID: guid.ID, Host: guid.Host, ServiceName: ServiceNameSchema}
			allListeners = append(allListeners, c.listeners[schemaKey]...)
		}
		evicted = true
	}
	c.mutex.Unlock()
	if evicted {
		for _, listener := range allListeners {
			listener.MarkDirty()
		}
		c.NotifyUpdates()
	}
	return evicted
}

func (c *RecordCache) Delete(hostName, serviceName string) bool {
	if c == nil || hostName == "" || serviceName == ServiceNameUnset || strings.HasPrefix(serviceName, ServiceNameSchema) {
		return false
	}
	nilValue := NewNilValue()
	c.mutex.Lock()
	if len(c.guids) == 0 {
		c.mutex.Unlock()
		return false
	}
	var allListeners []UpdatesListener
	var removedTopics []string
	removedGuids := false
	deletesListener := c.deletesListener
	updated := c.guids[:0]
	for _, guid := range c.guids {
		if guid.Host != hostName || guid.ServiceName != serviceName {
			updated = append(updated, guid)
			continue
		}
		k := guid.key()
		record := c.records[k]
		if record != nil && !record.Value.Equal(&nilValue) {
			updated = append(updated, guid)
			continue
		}
		if record != nil && record.Topic != "" {
			removedTopics = append(removedTopics, record.Topic)
		}
		delete(c.dirty, k)
		allListeners = append(allListeners, c.listeners[k]...)
		if GetIDKind(guid.ID) == MetricKindService {
			schemaKey := guidKey{ID: guid.ID, Host: guid.Host, ServiceName: ServiceNameSchema}
			allListeners = append(allListeners, c.listeners[schemaKey]...)
		}
		delete(c.records, k)
		delete(c.listeners, k)
		removedGuids = true
	}
	if removedGuids {
		for i := len(updated); i < len(c.guids); i++ {
			c.guids[i] = RecordGUID{}
		}
		c.guids = updated
		c.reindex()
	}
	c.mutex.Unlock()
	if removedGuids {
		for _, listener := range allListeners {
			listener.MarkDirty()
		}
		if deletesListener != nil {
			for _, topic := range removedTopics {
				deletesListener.Unsubscribe(topic)
			}
		}
		c.NotifyUpdates()
	}
	return removedGuids
}

func (c *RecordCache) Purge(evictSecs int) {
	if c == nil {
		return
	}
	now := time.Now().Unix()
	nilValue := NewNilValue()
	c.mutex.Lock()
	changed := false
	removedGuids := false
	updated := c.guids[:0]
	var allListeners []UpdatesListener
	for _, guid := range c.guids {
		k := guid.key()
		record := c.records[k]
		if record == nil {
			delete(c.dirty, k)
			delete(c.listeners, k)
			removedGuids = true
			continue
		}
		if strings.HasPrefix(guid.ServiceName, ServiceNameSchema) {
			updated = append(updated, guid)
			continue
		}
		if !record.Value.Equal(&nilValue) && now-record.Value.Timestamp > int64(evictSecs) {
			c.records[k] = &Record{Topic: record.Topic, Tags: record.Tags, Value: nilValue}
			c.dirty[k] = guid
			allListeners = append(allListeners, c.listeners[k]...)
			if GetIDKind(guid.ID) == MetricKindService {
				schemaKey := guidKey{ID: guid.ID, Host: guid.Host, ServiceName: ServiceNameSchema}
				allListeners = append(allListeners, c.listeners[schemaKey]...)
			}
			changed = true
		}
		updated = append(updated, guid)
	}
	if removedGuids {
		for i := len(updated); i < len(c.guids); i++ {
			c.guids[i] = RecordGUID{}
		}
		c.guids = updated
		c.reindex()
	}
	c.mutex.Unlock()
	if changed {
		for _, listener := range allListeners {
			listener.MarkDirty()
		}
		c.NotifyUpdates()
	}
}

func (c *RecordCache) IDs() []ID {
	if c == nil {
		return nil
	}
	c.mutex.RLock()
	defer c.mutex.RUnlock()
	ids := make([]ID, len(c.guids))
	for id, guid := range c.guids {
		ids[id] = guid.ID
	}
	return ids
}

func (c *RecordCache) Hosts() map[string]int {
	if c == nil {
		return nil
	}
	c.mutex.RLock()
	defer c.mutex.RUnlock()
	var last string
	hosts := make(map[string]int)
	for _, guid := range c.guids {
		if guid.Host != last {
			last = guid.Host
			hosts[last] = len(hosts)
		}
	}
	return hosts
}


func (c *RecordCache) Services(hostName string) []string {
	if c == nil {
		return nil
	}
	c.mutex.RLock()
	defer c.mutex.RUnlock()
	var services []string
	seen := make(map[string]struct{})
	for _, guid := range c.guids {
		if guid.Host != hostName {
			continue
		}
		if guid.ServiceName == ServiceNameUnset || strings.HasPrefix(guid.ServiceName, ServiceNameSchema) {
			continue
		}
		if _, exists := seen[guid.ServiceName]; !exists {
			seen[guid.ServiceName] = struct{}{}
			services = append(services, guid.ServiceName)
		}
	}
	return services
}

func (c *RecordCache) Records(fn func(RecordGUID, *Record)) {
	if c == nil {
		return
	}
	c.mutex.RLock()
	guids := make([]RecordGUID, 0, len(c.guids))
	records := make([]Record, 0, len(c.guids))
	for _, guid := range c.guids {
		record := c.records[guid.key()]
		if record == nil {
			continue
		}
		guids = append(guids, guid)
		records = append(records, *record)
	}
	c.mutex.RUnlock()
	for i, guid := range guids {
		fn(guid, &records[i])
	}
}

func (c *RecordCache) Topics() []TopicBinding {
	if c == nil {
		return nil
	}
	c.mutex.RLock()
	defer c.mutex.RUnlock()
	seen := make(map[string]struct{})
	var bindings []TopicBinding
	for _, guid := range c.guids {
		record := c.records[guid.key()]
		if record == nil || record.Topic == "" {
			continue
		}
		if _, exists := seen[record.Topic]; exists {
			continue
		}
		seen[record.Topic] = struct{}{}
		bindings = append(bindings, TopicBinding{Topic: record.Topic, GUID: guid})
	}
	return bindings
}

func (c *RecordCache) Take() []RecordGUID {
	if c == nil {
		return nil
	}
	c.mutex.Lock()
	if len(c.dirty) == 0 {
		c.mutex.Unlock()
		return nil
	}
	result := make([]RecordGUID, 0, len(c.dirty))
	for _, guid := range c.dirty {
		result = append(result, guid)
	}
	c.dirty = make(map[guidKey]RecordGUID, len(result))
	c.mutex.Unlock()
	return result
}

func (c *RecordCache) SubscribeDeletes(listener DeletesListener) {
	if c == nil || listener == nil {
		return
	}
	c.mutex.Lock()
	defer c.mutex.Unlock()
	c.deletesListener = listener
}

func (c *RecordCache) ListenerIDs() map[string][]ID {
	if c == nil {
		return nil
	}
	c.mutex.RLock()
	defer c.mutex.RUnlock()
	idsByHost := make(map[string][]ID)
	for k := range c.listeners {
		idsByHost[k.Host] = append(idsByHost[k.Host], k.ID)
	}
	return idsByHost
}

func (c *RecordCache) ClearUpdateListeners() {
	if c == nil {
		return
	}
	c.mutex.Lock()
	defer c.mutex.Unlock()
	for k := range c.listeners {
		c.listeners[k] = nil
	}
}

func (c *RecordCache) SubscribeUpdates(guid RecordGUID, listener UpdatesListener) {
	if c == nil || listener == nil {
		return
	}
	c.mutex.Lock()
	defer c.mutex.Unlock()
	k := guid.key()
	c.listeners[k] = append(c.listeners[k], listener)
}

func (c *RecordCache) Updates() <-chan struct{} {
	if c == nil {
		return nil
	}
	return c.notify
}

func (c *RecordCache) NotifyUpdates() {
	if c == nil || c.notify == nil {
		return
	}
	select {
	case c.notify <- struct{}{}:
	default:
	}
}

func (c *RecordCache) Size() int {
	if c == nil {
		return 0
	}
	c.mutex.RLock()
	defer c.mutex.RUnlock()
	count := 0
	for key := range c.records {
		if strings.HasPrefix(key.ServiceName, ServiceNameSchema) {
			continue
		}
		count++
	}
	return count
}

func (c *RecordCache) String() string {
	if c == nil {
		return "<nil>"
	}
	const (
		hostWidth  = 11
		nameWidth  = 10
		pulseWidth = 19
		trendWidth = 19
		topicWidth = 70
	)
	format := fmt.Sprintf(
		"%%03d %%03d %%02v %%-%ds %%-%ds pulse:%%-%ds trend:%%-%ds %%-%ds %%s\n",
		hostWidth,
		nameWidth,
		pulseWidth,
		trendWidth,
		topicWidth,
	)
	orNil := func(s string) string {
		if s == "" {
			return "<nil>"
		}
		return s
	}
	truncate := func(value string, width int) string {
		if width <= 0 || len(value) <= width {
			return value
		}
		if width == 1 {
			return "~"
		}
		return value[:width-1] + "~"
	}
	type entry struct {
		guid  RecordGUID
		topic string
		tags  map[string]string
		value ValueData
	}
	c.mutex.RLock()
	entries := make([]entry, 0, len(c.guids))
	for _, guid := range c.guids {
		r := c.records[guid.key()]
		if r == nil {
			continue
		}
		entries = append(entries, entry{guid: guid, topic: r.Topic, tags: r.Tags, value: r.Value})
	}
	c.mutex.RUnlock()
	tagsString := func(tags map[string]string) string {
		if len(tags) == 0 {
			return "<nil>"
		}
		keys := make([]string, 0, len(tags))
		for k := range tags {
			keys = append(keys, k)
		}
		slices.Sort(keys)
		parts := make([]string, 0, len(keys))
		for _, k := range keys {
			parts = append(parts, k+"="+tags[k])
		}
		return strings.Join(parts, ",")
	}
	pulseOrNil := func(p interface{ String() string }) string {
		if p == nil {
			return "<nil>"
		}
		v := reflect.ValueOf(p)
		if v.Kind() == reflect.Pointer && v.IsNil() {
			return "<nil>"
		}
		return orNil(p.String())
	}
	var stringBuilder strings.Builder
	for index, entry := range entries {
		fmt.Fprintf(&stringBuilder, format,
			index,
			entry.guid.ID,
			entry.guid.ServiceIndex,
			truncate(orNil(entry.guid.Host), hostWidth),
			truncate(orNil(entry.guid.ServiceName), nameWidth),
			truncate(pulseOrNil(entry.value.Pulse), pulseWidth),
			truncate(pulseOrNil(entry.value.Trend), trendWidth),
			truncate(orNil(entry.topic), topicWidth),
			tagsString(entry.tags),
		)
	}
	return stringBuilder.String()
}

func compareRecordGUID(this, that RecordGUID) int {
	switch {
	case this.Host < that.Host:
		return -1
	case this.Host > that.Host:
		return 1
	case this.ServiceName < that.ServiceName:
		return -1
	case this.ServiceName > that.ServiceName:
		return 1
	case this.ID < that.ID:
		return -1
	case this.ID > that.ID:
		return 1
	default:
		return 0
	}
}

func (c *RecordCache) reindex() {
	hostIndices := make(map[string]map[string]int)
	for i := range c.guids {
		if GetIDKind(c.guids[i].ID) != MetricKindService || strings.HasPrefix(c.guids[i].ServiceName, ServiceNameSchema) {
			c.guids[i].ServiceIndex = ServiceIndexUnset
			continue
		}
		hostName := c.guids[i].Host
		if hostIndices[hostName] == nil {
			hostIndices[hostName] = make(map[string]int)
		}
		names := hostIndices[hostName]
		if _, exists := names[c.guids[i].ServiceName]; !exists {
			names[c.guids[i].ServiceName] = len(names)
		}
		c.guids[i].ServiceIndex = names[c.guids[i].ServiceName]
		k := c.guids[i].key()
		if _, inDirty := c.dirty[k]; inDirty {
			c.dirty[k] = c.guids[i]
		}
	}
	clear(c.serviceIndex)
	for _, guid := range c.guids {
		if guid.ServiceIndex >= 0 {
			c.serviceIndex[indexKey{ID: guid.ID, Host: guid.Host, ServiceIndex: guid.ServiceIndex}] = guid.key()
		}
	}
	for i := range c.guids {
		guid := c.guids[i]
		record := c.records[guid.key()]
		if record == nil || record.Topic != "" {
			continue
		}
		if guid.Host == "" {
			continue
		}
		if GetIDKind(guid.ID) == MetricKindService && (guid.ServiceName == ServiceNameUnset || strings.HasPrefix(guid.ServiceName, ServiceNameSchema)) {
			continue
		}
		topic, tags, err := buildFromID(guid.ID, guid.Host, guid.ServiceName, "data")
		if err != nil {
			continue
		}
		record.Topic = topic
		record.Tags = tags
	}
}
