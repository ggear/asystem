package metric

import (
	"fmt"
	"reflect"
	"slices"
	"strings"
	"sync"
)

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

type RecordCache struct {
	mutex        sync.RWMutex
	guids        []RecordGUID
	records      map[guidKey]*Record
	serviceIndex map[indexKey]guidKey
	notify       chan struct{}
	listeners    map[guidKey][]UpdatesListener
}

func NewRecordCache() *RecordCache {
	return &RecordCache{
		guids:        make([]RecordGUID, 0),
		records:      make(map[guidKey]*Record),
		serviceIndex: make(map[indexKey]guidKey),
		notify:       make(chan struct{}, 1),
		listeners:    make(map[guidKey][]UpdatesListener),
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
	} else {
		if record.Topic == "" && cached != nil {
			record.Topic = cached.Topic
			record.Tags = cached.Tags
		}
		c.records[k] = record
	}
	listeners = append([]UpdatesListener(nil), c.listeners[k]...)
	c.mutex.Unlock()
	if notify {
		for _, listener := range listeners {
			listener.MarkDirty()
		}
		c.NotifyUpdates()
	}
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

func (c *RecordCache) LoadByID(id ID, host string, serviceIndex int) (*Record, bool) {
	if c == nil {
		return nil, false
	}
	c.mutex.RLock()
	defer c.mutex.RUnlock()

	var record *Record
	if serviceIndex == ServiceIndexUnset {
		guid := NewRecordGUID(id, host)
		record = c.records[guid.key()]
	} else {
		key, found := c.serviceIndex[indexKey{ID: id, Host: host, ServiceIndex: serviceIndex}]
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

func (c *RecordCache) Evict(host, serviceName string) bool {
	if c == nil || host == "" || serviceName == ServiceNameUnset || strings.HasPrefix(serviceName, ServiceNameSchema) {
		return false
	}
	nilValue := NewNilValue()
	c.mutex.Lock()
	var allListeners []UpdatesListener
	evicted := false
	for _, guid := range c.guids {
		if guid.Host != host || guid.ServiceName != serviceName {
			continue
		}
		k := guid.key()
		record := c.records[k]
		if record == nil || record.Value.Equal(&nilValue) {
			continue
		}
		c.records[k] = &Record{Topic: record.Topic, Tags: record.Tags, Value: nilValue}
		allListeners = append(allListeners, c.listeners[k]...)
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

func (c *RecordCache) Delete(host, serviceName string) bool {
	if c == nil || host == "" || serviceName == ServiceNameUnset || strings.HasPrefix(serviceName, ServiceNameSchema) {
		return false
	}
	nilValue := NewNilValue()
	c.mutex.Lock()
	if len(c.guids) == 0 {
		c.mutex.Unlock()
		return false
	}
	var allListeners []UpdatesListener
	removedGuids := false
	updated := c.guids[:0]
	for _, guid := range c.guids {
		if guid.Host != host || guid.ServiceName != serviceName {
			updated = append(updated, guid)
			continue
		}
		k := guid.key()
		record := c.records[k]
		if record == nil || !record.Value.Equal(&nilValue) {
			updated = append(updated, guid)
			continue
		}
		allListeners = append(allListeners, c.listeners[k]...)
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
		c.NotifyUpdates()
	}
	return removedGuids
}

func (c *RecordCache) IDs() []ID {
	c.mutex.RLock()
	defer c.mutex.RUnlock()
	ids := make([]ID, len(c.guids))
	for id, guid := range c.guids {
		ids[id] = guid.ID
	}
	return ids
}

func (c *RecordCache) Hosts() map[string]int {
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

func (c *RecordCache) Services() map[string]int {
	c.mutex.RLock()
	defer c.mutex.RUnlock()
	services := make(map[string]int)
	for _, guid := range c.guids {
		if guid.ServiceName != ServiceNameUnset {
			if _, exists := services[guid.ServiceName]; !exists {
				services[guid.ServiceName] = len(services)
			}
		}
	}
	return services
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
		host := c.guids[i].Host
		if hostIndices[host] == nil {
			hostIndices[host] = make(map[string]int)
		}
		names := hostIndices[host]
		if _, exists := names[c.guids[i].ServiceName]; !exists {
			names[c.guids[i].ServiceName] = len(names)
		}
		c.guids[i].ServiceIndex = names[c.guids[i].ServiceName]
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
		if GetIDKind(guid.ID) == MetricKindService && guid.ServiceName == ServiceNameUnset {
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
