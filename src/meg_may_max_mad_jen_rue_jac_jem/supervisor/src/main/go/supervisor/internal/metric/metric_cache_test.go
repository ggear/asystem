package metric

import (
	"reflect"
	"slices"
	"testing"
	"time"
)

func TestRecordCache_Hosts(t *testing.T) {
	tests := []struct {
		name     string
		records  []RecordGUID
		expected map[string]int
	}{
		{
			name: "happy_sorted_hosts",
			records: []RecordGUID{
				NewRecordGUID(MetricHost, "beta"),
				NewRecordGUID(MetricHost, "alpha"),
				NewRecordGUID(MetricHost, "gamma"),
			},
			expected: map[string]int{"alpha": 0, "beta": 1, "gamma": 2},
		},
		{
			name: "happy_single_host",
			records: []RecordGUID{
				NewRecordGUID(MetricHost, "alpha"),
			},
			expected: map[string]int{"alpha": 0},
		},
		{
			name:     "happy_no_hosts",
			records:  []RecordGUID{},
			expected: map[string]int{},
		},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			cache := NewRecordCache()
			for _, guid := range tt.records {
				cache.Store(guid, &Record{})
			}
			hosts := cache.Hosts()
			t.Logf("Cache:\n%s", cache.String())
			if !reflect.DeepEqual(hosts, tt.expected) {
				t.Fatalf("Got hosts = %+v, expected %+v", hosts, tt.expected)
			}
		})
	}
	t.Run("happy_nil_cache_returns_nil", func(t *testing.T) {
		var c *RecordCache
		if c.Hosts() != nil {
			t.Fatalf("Got non-nil from nil cache, expected nil")
		}
	})
}


func TestRecordCache_ServicesForHost(t *testing.T) {
	tests := []struct {
		name     string
		records  []RecordGUID
		host     string
		expected []string
	}{
		{
			name: "happy_returns_only_services_for_given_host",
			records: []RecordGUID{
				NewServiceRecordGUID(MetricServiceName, "alpha", "svc-a"),
				NewServiceRecordGUID(MetricServiceName, "beta", "svc-b"),
			},
			host:     "alpha",
			expected: []string{"svc-a"},
		},
		{
			name: "happy_excludes_services_from_other_hosts",
			records: []RecordGUID{
				NewServiceRecordGUID(MetricServiceName, "alpha", "svc-a"),
				NewServiceRecordGUID(MetricServiceName, "alpha", "svc-b"),
				NewServiceRecordGUID(MetricServiceName, "beta", "svc-c"),
			},
			host:     "alpha",
			expected: []string{"svc-a", "svc-b"},
		},
		{
			name: "happy_excludes_schema_entries",
			records: []RecordGUID{
				NewServiceSchemaRecordGUID(MetricServiceName, "alpha", 0),
				NewServiceRecordGUID(MetricServiceName, "alpha", "svc-a"),
			},
			host:     "alpha",
			expected: []string{"svc-a"},
		},
		{
			name: "happy_unknown_host_returns_nil",
			records: []RecordGUID{
				NewServiceRecordGUID(MetricServiceName, "alpha", "svc-a"),
			},
			host:     "beta",
			expected: nil,
		},
		{
			name:     "happy_empty_cache_returns_nil",
			records:  []RecordGUID{},
			host:     "alpha",
			expected: nil,
		},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			cache := NewRecordCache()
			for _, guid := range tt.records {
				cache.Store(guid, &Record{})
			}
			services := cache.Services(tt.host)
			t.Logf("Cache:\n%s", cache.String())
			if !reflect.DeepEqual(services, tt.expected) {
				t.Fatalf("Got services = %+v, expected %+v", services, tt.expected)
			}
		})
	}
	t.Run("happy_nil_cache_returns_nil", func(t *testing.T) {
		var c *RecordCache
		if c.Services("alpha") != nil {
			t.Fatalf("Got non-nil from nil cache, expected nil")
		}
	})
}

func TestRecordCache_Records(t *testing.T) {
	tests := []struct {
		name      string
		setupFunc func(*RecordCache)
		checkFunc func(*testing.T, []RecordGUID, map[RecordGUID]Record)
	}{
		{
			name:      "happy_empty_cache_visits_nothing",
			setupFunc: func(_ *RecordCache) {},
			checkFunc: func(t *testing.T, visited []RecordGUID, _ map[RecordGUID]Record) {
				if len(visited) != 0 {
					t.Fatalf("Got visited = %+v, expected empty", visited)
				}
			},
		},
		{
			name: "happy_host_record_included",
			setupFunc: func(cache *RecordCache) {
				cache.Store(NewRecordGUID(MetricHost, "alpha"), &Record{})
			},
			checkFunc: func(t *testing.T, _ []RecordGUID, seen map[RecordGUID]Record) {
				if _, ok := seen[NewRecordGUID(MetricHost, "alpha")]; !ok {
					t.Fatalf("Got host record missing, expected present")
				}
			},
		},
		{
			name: "happy_service_record_included",
			setupFunc: func(cache *RecordCache) {
				cache.Store(NewServiceRecordGUID(MetricServiceName, "alpha", "svc-a"), &Record{})
			},
			checkFunc: func(t *testing.T, _ []RecordGUID, seen map[RecordGUID]Record) {
				found := false
				for guid := range seen {
					if guid.Host == "alpha" && guid.ServiceName == "svc-a" {
						found = true
					}
				}
				if !found {
					t.Fatalf("Got service record missing, expected present")
				}
			},
		},
		{
			name: "happy_schema_record_included",
			setupFunc: func(cache *RecordCache) {
				cache.Store(NewServiceSchemaRecordGUID(MetricServiceName, "alpha", 0), &Record{})
			},
			checkFunc: func(t *testing.T, _ []RecordGUID, seen map[RecordGUID]Record) {
				found := false
				for guid := range seen {
					if guid.Host == "alpha" && guid.ServiceName == ServiceNameSchema {
						found = true
					}
				}
				if !found {
					t.Fatalf("Got schema record missing, expected present")
				}
			},
		},
		{
			name: "happy_nil_value_record_included",
			setupFunc: func(cache *RecordCache) {
				value := ValueData{Pulse: &ValueDataDetail{OK: true, Kind: ValueString, ValueString: "v"}}
				cache.Store(NewServiceRecordGUID(MetricServiceName, "alpha", "svc-a"), &Record{Value: value})
				cache.Evict("alpha", "svc-a")
			},
			checkFunc: func(t *testing.T, _ []RecordGUID, seen map[RecordGUID]Record) {
				found := false
				for guid, record := range seen {
					if guid.Host == "alpha" && guid.ServiceName == "svc-a" {
						found = true
						if record.Value.Pulse != nil {
							t.Fatalf("Got pulse non-nil for evicted record, expected nil")
						}
					}
				}
				if !found {
					t.Fatalf("Got evicted record missing, expected present")
				}
			},
		},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			cache := NewRecordCache()
			tt.setupFunc(cache)
			var visited []RecordGUID
			seen := make(map[RecordGUID]Record)
			cache.Records(func(guid RecordGUID, record *Record) {
				visited = append(visited, guid)
				seen[guid] = *record
			})
			tt.checkFunc(t, visited, seen)
		})
	}
	t.Run("happy_nil_cache_no_panic", func(t *testing.T) {
		var c *RecordCache
		c.Records(func(_ RecordGUID, _ *Record) {
			t.Fatalf("Got callback called, expected no call on nil cache")
		})
	})
}

func TestRecordCache_IDs(t *testing.T) {
	t.Run("happy_nil_cache_returns_nil", func(t *testing.T) {
		var c *RecordCache
		if c.IDs() != nil {
			t.Fatalf("Got non-nil from nil cache, expected nil")
		}
	})
	t.Run("happy_returns_all_ids", func(t *testing.T) {
		cache := NewRecordCache()
		cache.Store(NewRecordGUID(MetricHost, "alpha"), &Record{})
		cache.Store(NewServiceRecordGUID(MetricServiceName, "alpha", "svc-a"), &Record{})
		ids := cache.IDs()
		if len(ids) != 2 {
			t.Fatalf("Got %d IDs, expected 2", len(ids))
		}
	})
}

func TestRecordCache_StoreLoad(t *testing.T) {
	tests := []struct {
		name      string
		setupFunc func(*RecordCache)
		checkFunc func(*testing.T, *RecordCache)
	}{
		{
			name: "happy_nil_value_no_op",
			setupFunc: func(cache *RecordCache) {
				guid := NewRecordGUID(MetricHost, "alpha")
				cache.Store(guid, nil)
			},
			checkFunc: func(t *testing.T, cache *RecordCache) {
				if cache.Size() != 0 {
					t.Fatalf("Got size = %d, expected 0 after nil store", cache.Size())
				}
			},
		},
		{
			name: "happy_store_then_load",
			setupFunc: func(cache *RecordCache) {
				guid := NewRecordGUID(MetricHost, "alpha")
				value := ValueData{Pulse: &ValueDataDetail{OK: true, Kind: ValueString, ValueString: "alpha-host"}}
				cache.Store(guid, &Record{Value: value})
			},
			checkFunc: func(t *testing.T, cache *RecordCache) {
				guid := NewRecordGUID(MetricHost, "alpha")
				value := ValueData{Pulse: &ValueDataDetail{OK: true, Kind: ValueString, ValueString: "alpha-host"}}
				if cache.Size() != 1 {
					t.Fatalf("Got size = %d, expected 1 after store", cache.Size())
				}
				record, ok := cache.Load(guid)
				if !ok || record == nil {
					t.Fatalf("Got record not found, expected to find stored guid")
				}
				if !record.Value.Equal(&value) {
					t.Fatalf("Got record value = %+v, expected %+v", record.Value, value)
				}
			},
		},
		{
			name: "happy_load_missing_guid",
			setupFunc: func(cache *RecordCache) {
				guid := NewRecordGUID(MetricHost, "alpha")
				value := ValueData{Pulse: &ValueDataDetail{OK: true, Kind: ValueString, ValueString: "alpha-host"}}
				cache.Store(guid, &Record{Value: value})
			},
			checkFunc: func(t *testing.T, cache *RecordCache) {
				_, ok := cache.Load(NewServiceRecordGUID(MetricServiceName, "alpha", "svc-a"))
				if ok {
					t.Fatalf("Got record found, expected missing for unknown guid")
				}
			},
		},
		{
			name: "happy_store_same_value_twice",
			setupFunc: func(cache *RecordCache) {
				guid := NewRecordGUID(MetricHost, "alpha")
				value := ValueData{Pulse: &ValueDataDetail{OK: true, Kind: ValueString, ValueString: "alpha-host"}}
				cache.Store(guid, &Record{Value: value})
				cache.Store(guid, &Record{Value: value})
			},
			checkFunc: func(t *testing.T, cache *RecordCache) {
				if cache.Size() != 1 {
					t.Fatalf("Got size = %d, expected 1 after duplicate store of same value", cache.Size())
				}
			},
		},
		{
			name: "happy_store_updated_value",
			setupFunc: func(cache *RecordCache) {
				guid := NewRecordGUID(MetricHost, "alpha")
				value1 := ValueData{Pulse: &ValueDataDetail{OK: true, Kind: ValueString, ValueString: "first"}}
				value2 := ValueData{Pulse: &ValueDataDetail{OK: true, Kind: ValueString, ValueString: "second"}}
				cache.Store(guid, &Record{Value: value1})
				cache.Store(guid, &Record{Value: value2})
			},
			checkFunc: func(t *testing.T, cache *RecordCache) {
				guid := NewRecordGUID(MetricHost, "alpha")
				expected := ValueData{Pulse: &ValueDataDetail{OK: true, Kind: ValueString, ValueString: "second"}}
				if cache.Size() != 1 {
					t.Fatalf("Got size = %d, expected 1 after update", cache.Size())
				}
				record, ok := cache.Load(guid)
				if !ok {
					t.Fatalf("Got record not found after update")
				}
				if !record.Value.Equal(&expected) {
					t.Fatalf("Got record value = %+v, expected updated value %+v", record.Value, expected)
				}
			},
		},
		{
			name: "happy_store_service_name_keyed",
			setupFunc: func(cache *RecordCache) {
				value := ValueData{Pulse: &ValueDataDetail{OK: true, Kind: ValueString, ValueString: "v"}}
				cache.Store(NewServiceRecordGUID(MetricServiceName, "alpha", "svc-a"), &Record{Value: value})
			},
			checkFunc: func(t *testing.T, cache *RecordCache) {
				if cache.Size() != 1 {
					t.Fatalf("Got size = %d, expected 1", cache.Size())
				}
				services := cache.Services("alpha")
				if !slices.Contains(services, "svc-a") {
					t.Fatalf("Got services = %+v, expected svc-a present", services)
				}
			},
		},
		{
			name: "happy_load_by_service_name",
			setupFunc: func(cache *RecordCache) {
				value := ValueData{Pulse: &ValueDataDetail{OK: true, Kind: ValueString, ValueString: "v"}}
				cache.Store(NewServiceRecordGUID(MetricServiceName, "alpha", "svc-a"), &Record{Value: value})
			},
			checkFunc: func(t *testing.T, cache *RecordCache) {
				record, ok := cache.Load(NewServiceRecordGUID(MetricServiceName, "alpha", "svc-a"))
				if !ok || record == nil {
					t.Fatalf("Got record not found, expected Load with ServiceName to match")
				}
			},
		},
		{
			name: "happy_store_does_not_alias_caller_record",
			setupFunc: func(cache *RecordCache) {
				guid := NewRecordGUID(MetricHost, "alpha")
				value := ValueData{Pulse: &ValueDataDetail{OK: true, Kind: ValueString, ValueString: "first"}}
				record := &Record{Topic: "original-topic", Value: value}
				cache.Store(guid, record)
				value2 := ValueData{Pulse: &ValueDataDetail{OK: true, Kind: ValueString, ValueString: "second"}}
				update := &Record{Value: value2}
				cache.Store(guid, update)
				update.Topic = "mutated-by-caller"
			},
			checkFunc: func(t *testing.T, cache *RecordCache) {
				guid := NewRecordGUID(MetricHost, "alpha")
				record, ok := cache.Load(guid)
				if !ok || record == nil {
					t.Fatalf("Got record not found, expected stored")
				}
				if record.Topic == "mutated-by-caller" {
					t.Fatalf("Got topic = %q, expected cache to be isolated from caller mutation", record.Topic)
				}
				if record.Topic != "original-topic" {
					t.Fatalf("Got topic = %q, expected original-topic inherited from first store", record.Topic)
				}
			},
		},
		{
			name: "happy_multiple_hosts",
			setupFunc: func(cache *RecordCache) {
				for _, host := range []string{"alpha", "beta", "gamma"} {
					guid := NewRecordGUID(MetricHost, host)
					value := ValueData{Pulse: &ValueDataDetail{OK: true, Kind: ValueString, ValueString: host}}
					cache.Store(guid, &Record{Value: value})
				}
			},
			checkFunc: func(t *testing.T, cache *RecordCache) {
				if cache.Size() != 3 {
					t.Fatalf("Got size = %d, expected 3", cache.Size())
				}
				for _, host := range []string{"alpha", "beta", "gamma"} {
					guid := NewRecordGUID(MetricHost, host)
					record, ok := cache.Load(guid)
					if !ok {
						t.Fatalf("Got record not found for host %q", host)
					}
					if record.Value.Pulse.ValueString != host {
						t.Fatalf("Got value = %q, expected %q for host %q", record.Value.Pulse.ValueString, host, host)
					}
				}
			},
		},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			cache := NewRecordCache()
			tt.setupFunc(cache)
			tt.checkFunc(t, cache)
		})
	}
}

func TestRecordCache_Delete(t *testing.T) {
	evicted := func(cache *RecordCache, host, serviceName string) {
		cache.Evict(host, serviceName)
	}
	tests := []struct {
		name      string
		setupFunc func(*RecordCache)
		checkFunc func(*testing.T, *RecordCache)
	}{
		{
			name: "happy_delete_evicted_removes_guid",
			setupFunc: func(cache *RecordCache) {
				value := ValueData{Pulse: &ValueDataDetail{OK: true, Kind: ValueString, ValueString: "value"}}
				cache.Store(NewServiceRecordGUID(MetricServiceName, "alpha", "svc-a"), &Record{Value: value})
				evicted(cache, "alpha", "svc-a")
			},
			checkFunc: func(t *testing.T, cache *RecordCache) {
				if dropped := cache.Delete("alpha", "svc-a"); !dropped {
					t.Fatalf("Got Delete = false, expected true after evict")
				}
				if _, ok := cache.Load(NewServiceRecordGUID(MetricServiceName, "alpha", "svc-a")); ok {
					t.Fatalf("Got svc-a still present, expected deleted")
				}
				if cache.Size() != 0 {
					t.Fatalf("Got size = %d, expected 0 after delete", cache.Size())
				}
			},
		},
		{
			name: "happy_delete_non_nil_value_is_noop",
			setupFunc: func(cache *RecordCache) {
				value := ValueData{Pulse: &ValueDataDetail{OK: true, Kind: ValueString, ValueString: "value"}}
				cache.Store(NewServiceRecordGUID(MetricServiceName, "alpha", "svc-a"), &Record{Value: value})
			},
			checkFunc: func(t *testing.T, cache *RecordCache) {
				if dropped := cache.Delete("alpha", "svc-a"); dropped {
					t.Fatalf("Got Delete = true, expected false for non-nil value")
				}
				if _, ok := cache.Load(NewServiceRecordGUID(MetricServiceName, "alpha", "svc-a")); !ok {
					t.Fatalf("Got svc-a missing, expected preserved when value non-nil")
				}
			},
		},
		{
			name: "happy_delete_all_metric_ids_for_service",
			setupFunc: func(cache *RecordCache) {
				value := ValueData{Pulse: &ValueDataDetail{OK: true, Kind: ValueString, ValueString: "value"}}
				cache.Store(NewServiceRecordGUID(MetricServiceName, "alpha", "svc-a"), &Record{Value: value})
				cache.Store(NewServiceRecordGUID(MetricServiceHealthStatus, "alpha", "svc-a"), &Record{Value: value})
				cache.Store(NewServiceRecordGUID(MetricServiceName, "alpha", "svc-b"), &Record{Value: value})
				evicted(cache, "alpha", "svc-a")
			},
			checkFunc: func(t *testing.T, cache *RecordCache) {
				if dropped := cache.Delete("alpha", "svc-a"); !dropped {
					t.Fatalf("Got Delete = false, expected true")
				}
				if _, ok := cache.Load(NewServiceRecordGUID(MetricServiceName, "alpha", "svc-a")); ok {
					t.Fatalf("Got svc-a Name still present, expected deleted")
				}
				if _, ok := cache.Load(NewServiceRecordGUID(MetricServiceHealthStatus, "alpha", "svc-a")); ok {
					t.Fatalf("Got svc-a Health still present, expected deleted")
				}
				if _, ok := cache.Load(NewServiceRecordGUID(MetricServiceName, "alpha", "svc-b")); !ok {
					t.Fatalf("Got svc-b missing, expected preserved")
				}
			},
		},
		{
			name: "happy_delete_scoped_to_host",
			setupFunc: func(cache *RecordCache) {
				value := ValueData{Pulse: &ValueDataDetail{OK: true, Kind: ValueString, ValueString: "value"}}
				cache.Store(NewServiceRecordGUID(MetricServiceName, "alpha", "svc-a"), &Record{Value: value})
				cache.Store(NewServiceRecordGUID(MetricServiceName, "beta", "svc-a"), &Record{Value: value})
				evicted(cache, "alpha", "svc-a")
				evicted(cache, "beta", "svc-a")
			},
			checkFunc: func(t *testing.T, cache *RecordCache) {
				if dropped := cache.Delete("alpha", "svc-a"); !dropped {
					t.Fatalf("Got Delete = false, expected true")
				}
				if _, ok := cache.Load(NewServiceRecordGUID(MetricServiceName, "alpha", "svc-a")); ok {
					t.Fatalf("Got alpha svc-a still present, expected deleted")
				}
				if _, ok := cache.Load(NewServiceRecordGUID(MetricServiceName, "beta", "svc-a")); !ok {
					t.Fatalf("Got beta svc-a missing, expected preserved")
				}
			},
		},
		{
			name: "happy_delete_host_metrics_preserved",
			setupFunc: func(cache *RecordCache) {
				value := ValueData{Pulse: &ValueDataDetail{OK: true, Kind: ValueString, ValueString: "value"}}
				cache.Store(NewRecordGUID(MetricHost, "alpha"), &Record{Value: value})
				cache.Store(NewServiceRecordGUID(MetricServiceName, "alpha", "svc-a"), &Record{Value: value})
				evicted(cache, "alpha", "svc-a")
			},
			checkFunc: func(t *testing.T, cache *RecordCache) {
				cache.Delete("alpha", "svc-a")
				if _, ok := cache.Load(NewRecordGUID(MetricHost, "alpha")); !ok {
					t.Fatalf("Got host record missing, expected preserved")
				}
			},
		},
		{
			name: "happy_delete_reindexes_remaining",
			setupFunc: func(cache *RecordCache) {
				value := ValueData{Pulse: &ValueDataDetail{OK: true, Kind: ValueString, ValueString: "value"}}
				cache.Store(NewServiceRecordGUID(MetricServiceName, "alpha", "svc-a"), &Record{Value: value})
				cache.Store(NewServiceRecordGUID(MetricServiceName, "alpha", "svc-b"), &Record{Value: value})
				cache.Store(NewServiceRecordGUID(MetricServiceName, "alpha", "svc-c"), &Record{Value: value})
				evicted(cache, "alpha", "svc-a")
			},
			checkFunc: func(t *testing.T, cache *RecordCache) {
				cache.Delete("alpha", "svc-a")
				record, ok := cache.LoadByID(MetricServiceName, "alpha", 0)
				if !ok || record == nil {
					t.Fatalf("Got no record at index 0 after delete, expected svc-b")
				}
				record, ok = cache.LoadByID(MetricServiceName, "alpha", 1)
				if !ok || record == nil {
					t.Fatalf("Got no record at index 1 after delete, expected svc-c")
				}
				_, ok = cache.LoadByID(MetricServiceName, "alpha", 2)
				if ok {
					t.Fatalf("Got record at index 2, expected not found after delete")
				}
			},
		},
		{
			name: "happy_delete_notifies_listeners",
			setupFunc: func(cache *RecordCache) {
				value := ValueData{Pulse: &ValueDataDetail{OK: true, Kind: ValueString, ValueString: "value"}}
				cache.Store(NewServiceRecordGUID(MetricServiceName, "alpha", "svc-a"), &Record{Value: value})
				cache.Store(NewServiceRecordGUID(MetricServiceHealthStatus, "alpha", "svc-a"), &Record{Value: value})
				evicted(cache, "alpha", "svc-a")
			},
			checkFunc: func(t *testing.T, cache *RecordCache) {
				listenerName := &mockListener{}
				listenerHealth := &mockListener{}
				cache.SubscribeUpdates(NewServiceRecordGUID(MetricServiceName, "alpha", "svc-a"), listenerName)
				cache.SubscribeUpdates(NewServiceRecordGUID(MetricServiceHealthStatus, "alpha", "svc-a"), listenerHealth)
				cache.Delete("alpha", "svc-a")
				if listenerName.dirtyCount != 1 {
					t.Fatalf("Got name dirty count = %d, expected 1", listenerName.dirtyCount)
				}
				if listenerHealth.dirtyCount != 1 {
					t.Fatalf("Got health dirty count = %d, expected 1", listenerHealth.dirtyCount)
				}
			},
		},
		{
			name:      "happy_delete_nil_cache_returns_false",
			setupFunc: func(cache *RecordCache) {},
			checkFunc: func(t *testing.T, cache *RecordCache) {
				var nilCache *RecordCache
				if nilCache.Delete("alpha", "svc-a") {
					t.Fatalf("Got Delete = true, expected false for nil cache")
				}
			},
		},
		{
			name:      "happy_delete_empty_host_is_noop",
			setupFunc: func(cache *RecordCache) {},
			checkFunc: func(t *testing.T, cache *RecordCache) {
				if cache.Delete("", "svc-a") {
					t.Fatalf("Got Delete = true, expected false for empty host")
				}
			},
		},
		{
			name: "happy_delete_unset_service_name_is_noop",
			setupFunc: func(cache *RecordCache) {
				value := ValueData{Pulse: &ValueDataDetail{OK: true, Kind: ValueString, ValueString: "value"}}
				cache.Store(NewServiceRecordGUID(MetricServiceName, "alpha", "svc-a"), &Record{Value: value})
			},
			checkFunc: func(t *testing.T, cache *RecordCache) {
				if cache.Delete("alpha", ServiceNameUnset) {
					t.Fatalf("Got Delete = true, expected false for unset service name")
				}
			},
		},
		{
			name: "happy_delete_schema_name_is_noop",
			setupFunc: func(cache *RecordCache) {
				cache.Store(NewServiceSchemaRecordGUID(MetricServiceName, "alpha", 0), &Record{Value: NewNilValue()})
			},
			checkFunc: func(t *testing.T, cache *RecordCache) {
				if cache.Delete("alpha", ServiceNameSchema) {
					t.Fatalf("Got Delete = true, expected false for schema name")
				}
				if _, ok := cache.Load(NewServiceSchemaRecordGUID(MetricServiceName, "alpha", 0)); !ok {
					t.Fatalf("Got schema record missing, expected preserved")
				}
			},
		},
		{
			name:      "happy_delete_from_empty_cache_returns_false",
			setupFunc: func(cache *RecordCache) {},
			checkFunc: func(t *testing.T, cache *RecordCache) {
				if cache.Delete("alpha", "svc-a") {
					t.Fatalf("Got Delete = true, expected false on empty cache")
				}
			},
		},
		{
			name: "happy_delete_partial_eviction_removes_only_nil",
			setupFunc: func(cache *RecordCache) {
				value := ValueData{Pulse: &ValueDataDetail{OK: true, Kind: ValueString, ValueString: "value"}}
				cache.Store(NewServiceRecordGUID(MetricServiceName, "alpha", "svc-a"), &Record{Value: value})
				cache.Store(NewServiceRecordGUID(MetricServiceHealthStatus, "alpha", "svc-a"), &Record{Value: value})
				cache.Evict("alpha", "svc-a")
				cache.Store(NewServiceRecordGUID(MetricServiceName, "alpha", "svc-a"), &Record{Value: value})
			},
			checkFunc: func(t *testing.T, cache *RecordCache) {
				if dropped := cache.Delete("alpha", "svc-a"); !dropped {
					t.Fatalf("Got Delete = false, expected true for partial eviction")
				}
				if _, ok := cache.Load(NewServiceRecordGUID(MetricServiceHealthStatus, "alpha", "svc-a")); ok {
					t.Fatalf("Got health record still present, expected deleted (was nil)")
				}
				if _, ok := cache.Load(NewServiceRecordGUID(MetricServiceName, "alpha", "svc-a")); !ok {
					t.Fatalf("Got name record missing, expected preserved (was non-nil)")
				}
			},
		},
		{
			name: "happy_delete_already_missing_returns_false",
			setupFunc: func(cache *RecordCache) {
				value := ValueData{Pulse: &ValueDataDetail{OK: true, Kind: ValueString, ValueString: "value"}}
				cache.Store(NewServiceRecordGUID(MetricServiceName, "alpha", "svc-b"), &Record{Value: value})
				evicted(cache, "alpha", "svc-b")
			},
			checkFunc: func(t *testing.T, cache *RecordCache) {
				if cache.Delete("alpha", "svc-a") {
					t.Fatalf("Got Delete = true, expected false when no records match")
				}
			},
		},
		{
			name: "happy_delete_orphan_guid_cleaned_up",
			setupFunc: func(cache *RecordCache) {
				value := ValueData{Pulse: &ValueDataDetail{OK: true, Kind: ValueString, ValueString: "value"}}
				cache.Store(NewServiceRecordGUID(MetricServiceName, "alpha", "svc-a"), &Record{Value: value})
				cache.Store(NewServiceRecordGUID(MetricServiceName, "alpha", "svc-b"), &Record{Value: value})
				cache.mutex.Lock()
				delete(cache.records, NewServiceRecordGUID(MetricServiceName, "alpha", "svc-a").key())
				cache.mutex.Unlock()
			},
			checkFunc: func(t *testing.T, cache *RecordCache) {
				if dropped := cache.Delete("alpha", "svc-a"); !dropped {
					t.Fatalf("Got Delete = false, expected true for orphan guid")
				}
				services := cache.Services("alpha")
				if slices.Contains(services, "svc-a") {
					t.Fatalf("Got svc-a still in services, expected orphan removed")
				}
				if !slices.Contains(services, "svc-b") {
					t.Fatalf("Got svc-b missing, expected preserved")
				}
			},
		},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			cache := NewRecordCache()
			tt.setupFunc(cache)
			tt.checkFunc(t, cache)
		})
	}
}

func TestRecordCache_SubscribeUpdates(t *testing.T) {
	tests := []struct {
		name          string
		setupFunc     func(*RecordCache, *mockListener)
		expectedDirty int
	}{
		{
			name: "happy_new_value_notifies_listener",
			setupFunc: func(cache *RecordCache, listener *mockListener) {
				guid := NewRecordGUID(MetricHost, "alpha")
				cache.SubscribeUpdates(guid, listener)
				value := ValueData{Pulse: &ValueDataDetail{OK: true, Kind: ValueString, ValueString: "first"}}
				cache.Store(guid, &Record{Value: value})
			},
			expectedDirty: 1,
		},
		{
			name: "happy_same_value_no_notification",
			setupFunc: func(cache *RecordCache, listener *mockListener) {
				guid := NewRecordGUID(MetricHost, "alpha")
				value := ValueData{Pulse: &ValueDataDetail{OK: true, Kind: ValueString, ValueString: "same"}}
				cache.Store(guid, &Record{Value: value})
				cache.SubscribeUpdates(guid, listener)
				cache.Store(guid, &Record{Value: value})
			},
			expectedDirty: 0,
		},
		{
			name: "happy_updated_value_notifies_listener",
			setupFunc: func(cache *RecordCache, listener *mockListener) {
				guid := NewRecordGUID(MetricHost, "alpha")
				cache.SubscribeUpdates(guid, listener)
				value1 := ValueData{Pulse: &ValueDataDetail{OK: true, Kind: ValueString, ValueString: "first"}}
				value2 := ValueData{Pulse: &ValueDataDetail{OK: true, Kind: ValueString, ValueString: "second"}}
				cache.Store(guid, &Record{Value: value1})
				cache.Store(guid, &Record{Value: value2})
			},
			expectedDirty: 2,
		},
		{
			name: "happy_other_guid_no_notification",
			setupFunc: func(cache *RecordCache, listener *mockListener) {
				guidA := NewRecordGUID(MetricHost, "alpha")
				guidB := NewRecordGUID(MetricHost, "beta")
				cache.SubscribeUpdates(guidA, listener)
				value := ValueData{Pulse: &ValueDataDetail{OK: true, Kind: ValueString, ValueString: "beta-value"}}
				cache.Store(guidB, &Record{Value: value})
			},
			expectedDirty: 0,
		},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			cache := NewRecordCache()
			listener := &mockListener{}
			tt.setupFunc(cache, listener)
			if listener.dirtyCount != tt.expectedDirty {
				t.Fatalf("Got dirty count = %d, expected %d", listener.dirtyCount, tt.expectedDirty)
			}
		})
	}
}

func TestRecordCache_Reindex(t *testing.T) {
	tests := []struct {
		name      string
		setupFunc func(*RecordCache)
		checkFunc func(*testing.T, *RecordCache)
	}{
		{
			name: "happy_derives_service_index_from_sorted_name",
			setupFunc: func(cache *RecordCache) {
				value := ValueData{Pulse: &ValueDataDetail{OK: true, Kind: ValueString, ValueString: "v"}}
				cache.Store(NewServiceRecordGUID(MetricServiceName, "alpha", "svc-b"), &Record{Value: value})
				cache.Store(NewServiceRecordGUID(MetricServiceName, "alpha", "svc-a"), &Record{Value: value})
				cache.Store(NewServiceRecordGUID(MetricServiceName, "alpha", "svc-c"), &Record{Value: value})
			},
			checkFunc: func(t *testing.T, cache *RecordCache) {
				t.Logf("Cache:\n%s", cache.String())
				record, ok := cache.LoadByID(MetricServiceName, "alpha", 0)
				if !ok || record == nil {
					t.Fatalf("Got no record at index 0, expected svc-a")
				}
				record, ok = cache.LoadByID(MetricServiceName, "alpha", 1)
				if !ok || record == nil {
					t.Fatalf("Got no record at index 1, expected svc-b")
				}
				record, ok = cache.LoadByID(MetricServiceName, "alpha", 2)
				if !ok || record == nil {
					t.Fatalf("Got no record at index 2, expected svc-c")
				}
			},
		},
		{
			name: "happy_host_metrics_get_unset_index",
			setupFunc: func(cache *RecordCache) {
				value := ValueData{Pulse: &ValueDataDetail{OK: true, Kind: ValueString, ValueString: "v"}}
				cache.Store(NewRecordGUID(MetricHost, "alpha"), &Record{Value: value})
				cache.Store(NewServiceRecordGUID(MetricServiceName, "alpha", "svc-a"), &Record{Value: value})
			},
			checkFunc: func(t *testing.T, cache *RecordCache) {
				t.Logf("Cache:\n%s", cache.String())
				recordByID, okByID := cache.LoadByID(MetricHost, "alpha", ServiceIndexUnset)
				if !okByID || recordByID == nil {
					t.Fatalf("Got no record for host via Load, expected present")
				}
				record, ok := cache.Load(NewRecordGUID(MetricHost, "alpha"))
				if !ok || record == nil {
					t.Fatalf("Got no record for host via Load, expected present")
				}
			},
		},
		{
			name: "happy_multiple_metrics_same_service_share_index",
			setupFunc: func(cache *RecordCache) {
				value := ValueData{Pulse: &ValueDataDetail{OK: true, Kind: ValueString, ValueString: "v"}}
				cache.Store(NewServiceRecordGUID(MetricServiceName, "alpha", "svc-a"), &Record{Value: value})
				cache.Store(NewServiceRecordGUID(MetricServiceUsedProcessor, "alpha", "svc-a"), &Record{Value: value})
				cache.Store(NewServiceRecordGUID(MetricServiceName, "alpha", "svc-b"), &Record{Value: value})
				cache.Store(NewServiceRecordGUID(MetricServiceUsedProcessor, "alpha", "svc-b"), &Record{Value: value})
			},
			checkFunc: func(t *testing.T, cache *RecordCache) {
				t.Logf("Cache:\n%s", cache.String())
				record, ok := cache.LoadByID(MetricServiceUsedProcessor, "alpha", 0)
				if !ok || record == nil {
					t.Fatalf("Got no record for svc-a processor at index 0")
				}
				record, ok = cache.LoadByID(MetricServiceUsedProcessor, "alpha", 1)
				if !ok || record == nil {
					t.Fatalf("Got no record for svc-b processor at index 1")
				}
			},
		},
		{
			name: "happy_service_index_preserved_on_update",
			setupFunc: func(cache *RecordCache) {
				v1 := ValueData{Pulse: &ValueDataDetail{OK: true, Kind: ValueString, ValueString: "first"}}
				v2 := ValueData{Pulse: &ValueDataDetail{OK: true, Kind: ValueString, ValueString: "second"}}
				cache.Store(NewServiceRecordGUID(MetricServiceName, "alpha", "svc-a"), &Record{Value: v1})
				cache.Store(NewServiceRecordGUID(MetricServiceName, "alpha", "svc-b"), &Record{Value: v1})
				cache.Store(NewServiceRecordGUID(MetricServiceName, "alpha", "svc-a"), &Record{Value: v2})
				cache.Store(NewServiceRecordGUID(MetricServiceName, "alpha", "svc-b"), &Record{Value: v2})
			},
			checkFunc: func(t *testing.T, cache *RecordCache) {
				t.Logf("Cache:\n%s", cache.String())
				record, ok := cache.LoadByID(MetricServiceName, "alpha", 0)
				if !ok || record == nil {
					t.Fatalf("Got no record at index 0 after update, expected svc-a")
				}
				record, ok = cache.LoadByID(MetricServiceName, "alpha", 1)
				if !ok || record == nil {
					t.Fatalf("Got no record at index 1 after update, expected svc-b")
				}
			},
		},
		{
			name: "happy_reindex_after_delete",
			setupFunc: func(cache *RecordCache) {
				value := ValueData{Pulse: &ValueDataDetail{OK: true, Kind: ValueString, ValueString: "v"}}
				cache.Store(NewServiceRecordGUID(MetricServiceName, "alpha", "svc-a"), &Record{Value: value})
				cache.Store(NewServiceRecordGUID(MetricServiceName, "alpha", "svc-b"), &Record{Value: value})
				cache.Store(NewServiceRecordGUID(MetricServiceName, "alpha", "svc-c"), &Record{Value: value})
				cache.Evict("alpha", "svc-a")
				cache.Delete("alpha", "svc-a")
			},
			checkFunc: func(t *testing.T, cache *RecordCache) {
				t.Logf("Cache:\n%s", cache.String())
				record, ok := cache.LoadByID(MetricServiceName, "alpha", 0)
				if !ok || record == nil {
					t.Fatalf("Got no record at index 0 after delete, expected svc-b")
				}
				record, ok = cache.LoadByID(MetricServiceName, "alpha", 1)
				if !ok || record == nil {
					t.Fatalf("Got no record at index 1 after delete, expected svc-c")
				}
				_, ok = cache.LoadByID(MetricServiceName, "alpha", 2)
				if ok {
					t.Fatalf("Got record at index 2 after delete, expected not found")
				}
			},
		},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			cache := NewRecordCache()
			tt.setupFunc(cache)
			tt.checkFunc(t, cache)
		})
	}
}

func TestRecordCache_Evict(t *testing.T) {
	tests := []struct {
		name      string
		setupFunc func(*RecordCache)
		checkFunc func(*testing.T, *RecordCache)
	}{
		{
			name: "happy_evict_service_nils_all_metrics",
			setupFunc: func(cache *RecordCache) {
				value := ValueData{Pulse: &ValueDataDetail{OK: true, Kind: ValueString, ValueString: "v"}}
				cache.Store(NewServiceRecordGUID(MetricServiceName, "alpha", "svc-a"), &Record{Value: value})
				cache.Store(NewServiceRecordGUID(MetricServiceUsedProcessor, "alpha", "svc-a"), &Record{Value: value})
				cache.Store(NewServiceRecordGUID(MetricServiceHealthStatus, "alpha", "svc-a"), &Record{Value: value})
			},
			checkFunc: func(t *testing.T, cache *RecordCache) {
				if !cache.Evict("alpha", "svc-a") {
					t.Fatalf("Got Evict = false, expected true")
				}
				if cache.Size() != 3 {
					t.Fatalf("Got size = %d, expected 3 (guids preserved)", cache.Size())
				}
				for _, id := range []ID{MetricServiceName, MetricServiceUsedProcessor, MetricServiceHealthStatus} {
					record, ok := cache.Load(NewServiceRecordGUID(id, "alpha", "svc-a"))
					if !ok || record == nil {
						t.Fatalf("Got record not found for metric %d, expected guid preserved", id)
					}
					if record.Value.Pulse != nil || record.Value.Trend != nil {
						t.Fatalf("Got non-nil value for metric %d, expected nil after evict", id)
					}
				}
			},
		},
		{
			name: "happy_evict_service_preserves_other_services",
			setupFunc: func(cache *RecordCache) {
				value := ValueData{Pulse: &ValueDataDetail{OK: true, Kind: ValueString, ValueString: "v"}}
				cache.Store(NewServiceRecordGUID(MetricServiceName, "alpha", "svc-a"), &Record{Value: value})
				cache.Store(NewServiceRecordGUID(MetricServiceName, "alpha", "svc-b"), &Record{Value: value})
			},
			checkFunc: func(t *testing.T, cache *RecordCache) {
				cache.Evict("alpha", "svc-a")
				record, ok := cache.Load(NewServiceRecordGUID(MetricServiceName, "alpha", "svc-b"))
				if !ok || record == nil {
					t.Fatalf("Got svc-b missing, expected preserved")
				}
				if record.Value.Pulse == nil {
					t.Fatalf("Got svc-b pulse nil, expected preserved")
				}
			},
		},
		{
			name: "happy_evict_service_preserves_topic_tags",
			setupFunc: func(cache *RecordCache) {
				value := ValueData{Pulse: &ValueDataDetail{OK: true, Kind: ValueString, ValueString: "v"}}
				cache.Store(NewServiceRecordGUID(MetricServiceName, "alpha", "svc-a"), &Record{
					Topic: "supervisor/alpha/data/service/svc-a/name",
					Tags:  map[string]string{"host": "alpha"},
					Value: value,
				})
			},
			checkFunc: func(t *testing.T, cache *RecordCache) {
				cache.Evict("alpha", "svc-a")
				record, ok := cache.Load(NewServiceRecordGUID(MetricServiceName, "alpha", "svc-a"))
				if !ok || record == nil {
					t.Fatalf("Got record not found after evict")
				}
				if record.Topic != "supervisor/alpha/data/service/svc-a/name" {
					t.Fatalf("Got topic = %q, expected preserved", record.Topic)
				}
				if record.Tags["host"] != "alpha" {
					t.Fatalf("Got tags = %+v, expected preserved", record.Tags)
				}
			},
		},
		{
			name: "happy_evict_service_notifies_listeners",
			setupFunc: func(cache *RecordCache) {
				value := ValueData{Pulse: &ValueDataDetail{OK: true, Kind: ValueString, ValueString: "v"}}
				cache.Store(NewServiceRecordGUID(MetricServiceName, "alpha", "svc-a"), &Record{Value: value})
				cache.Store(NewServiceRecordGUID(MetricServiceUsedProcessor, "alpha", "svc-a"), &Record{Value: value})
			},
			checkFunc: func(t *testing.T, cache *RecordCache) {
				listener := &mockListener{}
				cache.SubscribeUpdates(NewServiceRecordGUID(MetricServiceName, "alpha", "svc-a"), listener)
				cache.Evict("alpha", "svc-a")
				if listener.dirtyCount != 1 {
					t.Fatalf("Got dirty count = %d, expected 1", listener.dirtyCount)
				}
			},
		},
		{
			name:      "happy_evict_nil_cache_returns_false",
			setupFunc: func(cache *RecordCache) {},
			checkFunc: func(t *testing.T, cache *RecordCache) {
				var nilCache *RecordCache
				if nilCache.Evict("alpha", "svc-a") {
					t.Fatalf("Got Evict = true, expected false for nil cache")
				}
			},
		},
		{
			name:      "happy_evict_service_unset_name_is_noop",
			setupFunc: func(cache *RecordCache) {},
			checkFunc: func(t *testing.T, cache *RecordCache) {
				if cache.Evict("alpha", ServiceNameUnset) {
					t.Fatalf("Got Evict = true, expected false for unset name")
				}
			},
		},
		{
			name: "happy_evict_schema_name_is_noop",
			setupFunc: func(cache *RecordCache) {
				value := ValueData{Pulse: &ValueDataDetail{OK: true, Kind: ValueString, ValueString: "v"}}
				cache.Store(NewServiceSchemaRecordGUID(MetricServiceName, "alpha", 0), &Record{Value: value})
			},
			checkFunc: func(t *testing.T, cache *RecordCache) {
				if cache.Evict("alpha", ServiceNameSchema) {
					t.Fatalf("Got Evict = true, expected false for schema name")
				}
				record, ok := cache.Load(NewServiceSchemaRecordGUID(MetricServiceName, "alpha", 0))
				if !ok || record == nil || record.Value.Pulse == nil {
					t.Fatalf("Got schema record evicted, expected preserved")
				}
			},
		},
		{
			name: "happy_evict_host_metrics_preserved",
			setupFunc: func(cache *RecordCache) {
				value := ValueData{Pulse: &ValueDataDetail{OK: true, Kind: ValueString, ValueString: "v"}}
				cache.Store(NewRecordGUID(MetricHost, "alpha"), &Record{Value: value})
				cache.Store(NewServiceRecordGUID(MetricServiceName, "alpha", "svc-a"), &Record{Value: value})
			},
			checkFunc: func(t *testing.T, cache *RecordCache) {
				cache.Evict("alpha", "svc-a")
				record, ok := cache.Load(NewRecordGUID(MetricHost, "alpha"))
				if !ok || record == nil || record.Value.Pulse == nil {
					t.Fatalf("Got host record affected by evict, expected preserved")
				}
			},
		},
		{
			name: "happy_evict_already_evicted_returns_false",
			setupFunc: func(cache *RecordCache) {
				value := ValueData{Pulse: &ValueDataDetail{OK: true, Kind: ValueString, ValueString: "v"}}
				cache.Store(NewServiceRecordGUID(MetricServiceName, "alpha", "svc-a"), &Record{Value: value})
				cache.Evict("alpha", "svc-a")
			},
			checkFunc: func(t *testing.T, cache *RecordCache) {
				if cache.Evict("alpha", "svc-a") {
					t.Fatalf("Got Evict = true, expected false for already-evicted service")
				}
			},
		},
		{
			name: "happy_evict_service_scoped_to_host",
			setupFunc: func(cache *RecordCache) {
				value := ValueData{Pulse: &ValueDataDetail{OK: true, Kind: ValueString, ValueString: "v"}}
				cache.Store(NewServiceRecordGUID(MetricServiceName, "alpha", "svc-a"), &Record{Value: value})
				cache.Store(NewServiceRecordGUID(MetricServiceName, "beta", "svc-a"), &Record{Value: value})
			},
			checkFunc: func(t *testing.T, cache *RecordCache) {
				if !cache.Evict("alpha", "svc-a") {
					t.Fatalf("Got Evict = false, expected true")
				}
				record, ok := cache.Load(NewServiceRecordGUID(MetricServiceName, "alpha", "svc-a"))
				if !ok || record == nil || record.Value.Pulse != nil {
					t.Fatalf("Got alpha record not evicted, expected nil value")
				}
				record, ok = cache.Load(NewServiceRecordGUID(MetricServiceName, "beta", "svc-a"))
				if !ok || record == nil || record.Value.Pulse == nil {
					t.Fatalf("Got beta record evicted, expected preserved")
				}
			},
		},
		{
			name: "happy_evict_service_missing_returns_false",
			setupFunc: func(cache *RecordCache) {
				value := ValueData{Pulse: &ValueDataDetail{OK: true, Kind: ValueString, ValueString: "v"}}
				cache.Store(NewServiceRecordGUID(MetricServiceName, "alpha", "svc-a"), &Record{Value: value})
			},
			checkFunc: func(t *testing.T, cache *RecordCache) {
				if cache.Evict("alpha", "svc-z") {
					t.Fatalf("Got Evict = true, expected false for missing service")
				}
			},
		},
		{
			name: "happy_evict_service_does_not_reindex",
			setupFunc: func(cache *RecordCache) {
				value := ValueData{Pulse: &ValueDataDetail{OK: true, Kind: ValueString, ValueString: "v"}}
				cache.Store(NewServiceRecordGUID(MetricServiceName, "alpha", "svc-a"), &Record{Value: value})
				cache.Store(NewServiceRecordGUID(MetricServiceName, "alpha", "svc-b"), &Record{Value: value})
			},
			checkFunc: func(t *testing.T, cache *RecordCache) {
				record, ok := cache.LoadByID(MetricServiceName, "alpha", 1)
				if !ok || record == nil {
					t.Fatalf("Got no record at index 1 before evict")
				}
				cache.Evict("alpha", "svc-a")
				record, ok = cache.LoadByID(MetricServiceName, "alpha", 1)
				if !ok || record == nil {
					t.Fatalf("Got no record at index 1 after evict, expected svc-b index preserved")
				}
			},
		},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			cache := NewRecordCache()
			tt.setupFunc(cache)
			tt.checkFunc(t, cache)
		})
	}
}

func TestRecordCache_LoadByIndex(t *testing.T) {
	tests := []struct {
		name      string
		setupFunc func(*RecordCache)
		checkFunc func(*testing.T, *RecordCache)
	}{
		{
			name: "happy_load_by_index",
			setupFunc: func(cache *RecordCache) {
				value := ValueData{Pulse: &ValueDataDetail{OK: true, Kind: ValueString, ValueString: "v"}}
				cache.Store(NewServiceRecordGUID(MetricServiceName, "alpha", "svc-a"), &Record{Value: value})
				cache.Store(NewServiceRecordGUID(MetricServiceName, "alpha", "svc-b"), &Record{Value: value})
			},
			checkFunc: func(t *testing.T, cache *RecordCache) {
				t.Logf("Cache:\n%s", cache.String())
				record, ok := cache.LoadByID(MetricServiceName, "alpha", 0)
				if !ok || record == nil {
					t.Fatalf("Got no record at index 0")
				}
				record, ok = cache.LoadByID(MetricServiceName, "alpha", 1)
				if !ok || record == nil {
					t.Fatalf("Got no record at index 1")
				}
				_, ok = cache.LoadByID(MetricServiceName, "alpha", 2)
				if ok {
					t.Fatalf("Got record at index 2, expected not found")
				}
			},
		},
		{
			name: "happy_load_by_index_negative_returns_false",
			setupFunc: func(cache *RecordCache) {
				value := ValueData{Pulse: &ValueDataDetail{OK: true, Kind: ValueString, ValueString: "v"}}
				cache.Store(NewServiceRecordGUID(MetricServiceName, "alpha", "svc-a"), &Record{Value: value})
			},
			checkFunc: func(t *testing.T, cache *RecordCache) {
				_, ok := cache.LoadByID(MetricServiceName, "alpha", -1)
				if ok {
					t.Fatalf("Got record at index -1, expected not found")
				}
			},
		},
		{
			name:      "happy_load_by_index_nil_cache",
			setupFunc: func(cache *RecordCache) {},
			checkFunc: func(t *testing.T, cache *RecordCache) {
				var nilCache *RecordCache
				_, ok := nilCache.LoadByID(MetricServiceName, "alpha", 0)
				if ok {
					t.Fatalf("Got record from nil cache, expected not found")
				}
			},
		},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			cache := NewRecordCache()
			tt.setupFunc(cache)
			tt.checkFunc(t, cache)
		})
	}
}

func TestRecordCache_Purge(t *testing.T) {
	now := time.Now().Unix()
	oldTimestamp := now - 200
	freshTimestamp := now
	staleValue := func(s string) ValueData {
		return ValueData{Timestamp: oldTimestamp, Pulse: &ValueDataDetail{OK: true, Kind: ValueString, ValueString: s}}
	}
	freshValue := func(s string) ValueData {
		return ValueData{Timestamp: freshTimestamp, Pulse: &ValueDataDetail{OK: true, Kind: ValueString, ValueString: s}}
	}
	tests := []struct {
		name      string
		setupFunc func(*RecordCache)
		checkFunc func(*testing.T, *RecordCache)
	}{
		{
			name: "happy_stale_records_preserved",
			setupFunc: func(cache *RecordCache) {
				cache.Store(NewServiceRecordGUID(MetricServiceName, "alpha", "svc-a"), &Record{Value: staleValue("v")})
			},
			checkFunc: func(t *testing.T, cache *RecordCache) {
				cache.Purge(9999)
				record, ok := cache.Load(NewServiceRecordGUID(MetricServiceName, "alpha", "svc-a"))
				if !ok || record == nil {
					t.Fatalf("Got record not found, expected stale record preserved by purge")
				}
				if record.Value.Pulse == nil {
					t.Fatalf("Got nil pulse, expected stale record value unchanged by purge")
				}
			},
		},
		{
			name: "happy_preserves_fresh_records",
			setupFunc: func(cache *RecordCache) {
				cache.Store(NewServiceRecordGUID(MetricServiceName, "alpha", "svc-a"), &Record{Value: freshValue("v")})
			},
			checkFunc: func(t *testing.T, cache *RecordCache) {
				cache.Purge(9999)
				record, ok := cache.Load(NewServiceRecordGUID(MetricServiceName, "alpha", "svc-a"))
				if !ok || record == nil {
					t.Fatalf("Got record not found, expected fresh record preserved")
				}
				if record.Value.Pulse == nil {
					t.Fatalf("Got nil pulse, expected fresh record value preserved")
				}
			},
		},
		{
			name: "happy_preserves_already_evicted_records_as_nil",
			setupFunc: func(cache *RecordCache) {
				cache.Store(NewServiceRecordGUID(MetricServiceName, "alpha", "svc-a"), &Record{Value: staleValue("v")})
				cache.Evict("alpha", "svc-a")
			},
			checkFunc: func(t *testing.T, cache *RecordCache) {
				cache.Purge(9999)
				record, ok := cache.Load(NewServiceRecordGUID(MetricServiceName, "alpha", "svc-a"))
				if !ok || record == nil {
					t.Fatalf("Got evicted record deleted by purge, expected preserved as nil")
				}
				if record.Value.Pulse != nil {
					t.Fatalf("Got non-nil pulse, expected nil value for evicted record")
				}
			},
		},
		{
			name: "happy_evict_then_purge_preserves_as_nil",
			setupFunc: func(cache *RecordCache) {
				cache.Store(NewServiceRecordGUID(MetricServiceName, "alpha", "svc-a"), &Record{Value: staleValue("v")})
				cache.Evict("alpha", "svc-a")
			},
			checkFunc: func(t *testing.T, cache *RecordCache) {
				cache.Purge(9999)
				record, ok := cache.Load(NewServiceRecordGUID(MetricServiceName, "alpha", "svc-a"))
				if !ok || record == nil {
					t.Fatalf("Got record deleted after evict+purge, expected preserved as nil")
				}
				if record.Value.Pulse != nil {
					t.Fatalf("Got non-nil pulse after evict+purge, expected nil value")
				}
			},
		},
		{
			name: "happy_schema_records_not_deleted",
			setupFunc: func(cache *RecordCache) {
				cache.Store(NewServiceSchemaRecordGUID(MetricServiceName, "alpha", 0), &Record{Value: NewNilValue()})
			},
			checkFunc: func(t *testing.T, cache *RecordCache) {
				cache.Purge(9999)
				if _, ok := cache.Load(NewServiceSchemaRecordGUID(MetricServiceName, "alpha", 0)); !ok {
					t.Fatalf("Got schema record deleted, expected preserved")
				}
			},
		},
		{
			name:      "happy_nil_cache_is_noop",
			setupFunc: func(cache *RecordCache) {},
			checkFunc: func(t *testing.T, cache *RecordCache) {
				var nilCache *RecordCache
				nilCache.Purge(9999)
			},
		},
		{
			name: "happy_stale_records_no_listener_notification",
			setupFunc: func(cache *RecordCache) {
				cache.Store(NewServiceRecordGUID(MetricServiceName, "alpha", "svc-a"), &Record{Value: staleValue("v")})
			},
			checkFunc: func(t *testing.T, cache *RecordCache) {
				listener := &mockListener{}
				cache.SubscribeUpdates(NewServiceRecordGUID(MetricServiceName, "alpha", "svc-a"), listener)
				cache.Purge(9999)
				if listener.dirtyCount != 0 {
					t.Fatalf("Got dirty count = %d, expected 0 for stale record purge noop", listener.dirtyCount)
				}
			},
		},
		{
			name: "happy_purge_does_not_notify_listeners_for_nil_service_records",
			setupFunc: func(cache *RecordCache) {
				cache.Store(NewServiceRecordGUID(MetricServiceName, "alpha", "svc-a"), &Record{Value: staleValue("v")})
				cache.Evict("alpha", "svc-a")
			},
			checkFunc: func(t *testing.T, cache *RecordCache) {
				listener := &mockListener{}
				cache.SubscribeUpdates(NewServiceRecordGUID(MetricServiceName, "alpha", "svc-a"), listener)
				cache.Purge(9999)
				if listener.dirtyCount != 0 {
					t.Fatalf("Got dirty count = %d, expected 0 — purge must not notify for already-nil service records", listener.dirtyCount)
				}
			},
		},
		{
			name: "happy_stale_records_preserve_topic_tags",
			setupFunc: func(cache *RecordCache) {
				cache.Store(NewServiceRecordGUID(MetricServiceName, "alpha", "svc-a"), &Record{
					Topic: "supervisor/alpha/data/service/svc-a/name",
					Tags:  map[string]string{"host": "alpha"},
					Value: staleValue("v"),
				})
			},
			checkFunc: func(t *testing.T, cache *RecordCache) {
				cache.Purge(9999)
				record, ok := cache.Load(NewServiceRecordGUID(MetricServiceName, "alpha", "svc-a"))
				if !ok || record == nil {
					t.Fatalf("Got record not found after purge")
				}
				if record.Topic != "supervisor/alpha/data/service/svc-a/name" {
					t.Fatalf("Got topic = %q, expected preserved after purge", record.Topic)
				}
				if record.Tags["host"] != "alpha" {
					t.Fatalf("Got tags = %+v, expected preserved after purge", record.Tags)
				}
				if record.Value.Pulse == nil {
					t.Fatalf("Got nil pulse, expected value preserved after purge")
				}
			},
		},
		{
			name: "happy_evicted_service_retains_index_position",
			setupFunc: func(cache *RecordCache) {
				cache.Store(NewServiceRecordGUID(MetricServiceName, "alpha", "svc-a"), &Record{Value: staleValue("v")})
				cache.Store(NewServiceRecordGUID(MetricServiceName, "alpha", "svc-b"), &Record{Value: freshValue("v")})
				cache.Store(NewServiceRecordGUID(MetricServiceName, "alpha", "svc-c"), &Record{Value: freshValue("v")})
				cache.Evict("alpha", "svc-a")
			},
			checkFunc: func(t *testing.T, cache *RecordCache) {
				cache.Purge(9999)
				record, ok := cache.LoadByID(MetricServiceName, "alpha", 0)
				if !ok || record == nil {
					t.Fatalf("Got no record at index 0 after purge, expected svc-a (nil)")
				}
				record, ok = cache.LoadByID(MetricServiceName, "alpha", 1)
				if !ok || record == nil {
					t.Fatalf("Got no record at index 1 after purge, expected svc-b")
				}
				record, ok = cache.LoadByID(MetricServiceName, "alpha", 2)
				if !ok || record == nil {
					t.Fatalf("Got no record at index 2 after purge, expected svc-c")
				}
			},
		},
		{
			name: "happy_host_stale_records_preserved",
			setupFunc: func(cache *RecordCache) {
				cache.Store(NewRecordGUID(MetricHost, "alpha"), &Record{Value: staleValue("v")})
			},
			checkFunc: func(t *testing.T, cache *RecordCache) {
				cache.Purge(9999)
				record, ok := cache.Load(NewRecordGUID(MetricHost, "alpha"))
				if !ok || record == nil {
					t.Fatalf("Got host record not found, expected preserved by purge")
				}
				if record.Value.Pulse == nil {
					t.Fatalf("Got nil pulse, expected stale host record value unchanged by purge")
				}
			},
		},
		{
			name: "happy_host_records_not_deleted_when_nil",
			setupFunc: func(cache *RecordCache) {
				cache.Store(NewRecordGUID(MetricHost, "alpha"), &Record{Value: NewNilValue()})
			},
			checkFunc: func(t *testing.T, cache *RecordCache) {
				cache.Purge(9999)
				if _, ok := cache.Load(NewRecordGUID(MetricHost, "alpha")); !ok {
					t.Fatalf("Got host record deleted, expected preserved by purge")
				}
			},
		},
		{
			name: "happy_orphan_guid_cleaned_up",
			setupFunc: func(cache *RecordCache) {
				cache.Store(NewServiceRecordGUID(MetricServiceName, "alpha", "svc-a"), &Record{Value: freshValue("v")})
				cache.Store(NewServiceRecordGUID(MetricServiceName, "alpha", "svc-b"), &Record{Value: freshValue("v")})
				cache.mutex.Lock()
				delete(cache.records, NewServiceRecordGUID(MetricServiceName, "alpha", "svc-a").key())
				cache.mutex.Unlock()
			},
			checkFunc: func(t *testing.T, cache *RecordCache) {
				cache.Purge(9999)
				services := cache.Services("alpha")
				if slices.Contains(services, "svc-a") {
					t.Fatalf("Got svc-a still in services, expected orphan guid removed")
				}
				if !slices.Contains(services, "svc-b") {
					t.Fatalf("Got svc-b missing, expected preserved")
				}
			},
		},
		{
			name: "happy_evict_secs_stale_service_record_evicted_not_deleted",
			setupFunc: func(cache *RecordCache) {
				cache.Store(NewServiceRecordGUID(MetricServiceName, "alpha", "svc-a"), &Record{Value: staleValue("v")})
			},
			checkFunc: func(t *testing.T, cache *RecordCache) {
				cache.Purge(100)
				record, ok := cache.Load(NewServiceRecordGUID(MetricServiceName, "alpha", "svc-a"))
				if !ok || record == nil {
					t.Fatalf("Got stale service record deleted, expected evicted to nil but still in cache")
				}
				if record.Value.Pulse != nil {
					t.Fatalf("Got non-nil pulse, expected stale service record evicted to nil value")
				}
			},
		},
		{
			name: "happy_evict_secs_stale_service_record_stays_nil_after_subsequent_purge",
			setupFunc: func(cache *RecordCache) {
				cache.Store(NewServiceRecordGUID(MetricServiceName, "alpha", "svc-a"), &Record{Value: staleValue("v")})
			},
			checkFunc: func(t *testing.T, cache *RecordCache) {
				cache.Purge(100)
				cache.Purge(9999)
				record, ok := cache.Load(NewServiceRecordGUID(MetricServiceName, "alpha", "svc-a"))
				if !ok || record == nil {
					t.Fatalf("Got stale service record deleted after second purge, expected preserved as nil")
				}
				if record.Value.Pulse != nil {
					t.Fatalf("Got non-nil pulse after second purge, expected nil value")
				}
			},
		},
		{
			name: "happy_evict_secs_stale_host_record_evicted_not_deleted",
			setupFunc: func(cache *RecordCache) {
				cache.Store(NewRecordGUID(MetricHost, "alpha"), &Record{Value: staleValue("v")})
			},
			checkFunc: func(t *testing.T, cache *RecordCache) {
				cache.Purge(100)
				record, ok := cache.Load(NewRecordGUID(MetricHost, "alpha"))
				if !ok || record == nil {
					t.Fatalf("Got host record deleted, expected preserved after eviction")
				}
				if record.Value.Pulse != nil {
					t.Fatalf("Got non-nil pulse, expected host record evicted to nil value")
				}
			},
		},
		{
			name: "happy_evict_secs_fresh_service_record_not_evicted",
			setupFunc: func(cache *RecordCache) {
				cache.Store(NewServiceRecordGUID(MetricServiceName, "alpha", "svc-a"), &Record{Value: freshValue("v")})
			},
			checkFunc: func(t *testing.T, cache *RecordCache) {
				cache.Purge(100)
				record, ok := cache.Load(NewServiceRecordGUID(MetricServiceName, "alpha", "svc-a"))
				if !ok || record == nil {
					t.Fatalf("Got fresh record deleted, expected preserved")
				}
				if record.Value.Pulse == nil {
					t.Fatalf("Got nil pulse, expected fresh record value unchanged")
				}
			},
		},
		{
			name: "happy_evict_secs_schema_record_not_evicted",
			setupFunc: func(cache *RecordCache) {
				cache.Store(NewServiceSchemaRecordGUID(MetricServiceName, "alpha", 0), &Record{Value: staleValue("v")})
			},
			checkFunc: func(t *testing.T, cache *RecordCache) {
				cache.Purge(100)
				record, ok := cache.Load(NewServiceSchemaRecordGUID(MetricServiceName, "alpha", 0))
				if !ok || record == nil {
					t.Fatalf("Got schema record deleted, expected preserved")
				}
				if record.Value.Pulse == nil {
					t.Fatalf("Got nil pulse, expected schema record value unchanged")
				}
			},
		},
		{
			name: "happy_evict_secs_stale_host_record_marks_dirty",
			setupFunc: func(cache *RecordCache) {
				cache.Store(NewRecordGUID(MetricHost, "alpha"), &Record{Value: staleValue("v")})
				cache.Take()
			},
			checkFunc: func(t *testing.T, cache *RecordCache) {
				cache.Purge(100)
				dirty := cache.Take()
				if len(dirty) != 1 {
					t.Fatalf("Got dirty len = %d, expected 1 for evicted host record", len(dirty))
				}
			},
		},
		{
			name: "happy_evict_secs_stale_service_record_dirty_after_eviction",
			setupFunc: func(cache *RecordCache) {
				cache.Store(NewServiceRecordGUID(MetricServiceName, "alpha", "svc-a"), &Record{Value: staleValue("v")})
				cache.Take()
			},
			checkFunc: func(t *testing.T, cache *RecordCache) {
				cache.Purge(100)
				dirty := cache.Take()
				if len(dirty) != 1 {
					t.Fatalf("Got dirty len = %d, expected 1 after stale service record evicted", len(dirty))
				}
			},
		},
		{
			name: "happy_evict_secs_stale_service_record_dirty_cleared_by_take_not_purge",
			setupFunc: func(cache *RecordCache) {
				cache.Store(NewServiceRecordGUID(MetricServiceName, "alpha", "svc-a"), &Record{Value: staleValue("v")})
				cache.Take()
			},
			checkFunc: func(t *testing.T, cache *RecordCache) {
				cache.Purge(100)
				cache.Take()
				cache.Purge(9999)
				if cache.Take() != nil {
					t.Fatalf("Got dirty records after take cleared dirty and purge did not re-dirty, expected nil")
				}
			},
		},
		{
			name: "happy_evict_secs_stale_service_record_notifies_listener",
			setupFunc: func(cache *RecordCache) {
				cache.Store(NewServiceRecordGUID(MetricServiceName, "alpha", "svc-a"), &Record{Value: staleValue("v")})
			},
			checkFunc: func(t *testing.T, cache *RecordCache) {
				listener := &mockListener{}
				cache.SubscribeUpdates(NewServiceRecordGUID(MetricServiceName, "alpha", "svc-a"), listener)
				cache.Purge(100)
				if listener.dirtyCount == 0 {
					t.Fatalf("Got dirty count = 0, expected notifications for stale service record eviction")
				}
			},
		},
		{
			name: "happy_evict_secs_preserves_topic_tags_on_host_eviction",
			setupFunc: func(cache *RecordCache) {
				cache.Store(NewRecordGUID(MetricHost, "alpha"), &Record{
					Topic: "supervisor/alpha/data/host",
					Tags:  map[string]string{"host": "alpha"},
					Value: staleValue("v"),
				})
			},
			checkFunc: func(t *testing.T, cache *RecordCache) {
				cache.Purge(100)
				record, ok := cache.Load(NewRecordGUID(MetricHost, "alpha"))
				if !ok || record == nil {
					t.Fatalf("Got host record not found after eviction")
				}
				if record.Topic != "supervisor/alpha/data/host" {
					t.Fatalf("Got topic = %q, expected preserved after eviction", record.Topic)
				}
				if record.Tags["host"] != "alpha" {
					t.Fatalf("Got tags = %+v, expected preserved after eviction", record.Tags)
				}
			},
		},
		{
			name: "happy_purge_deletes_stale_nil_service_record",
			setupFunc: func(cache *RecordCache) {
				cache.Store(NewServiceRecordGUID(MetricServiceName, "alpha", "svc-a"), &Record{Value: ValueData{Timestamp: oldTimestamp}})
			},
			checkFunc: func(t *testing.T, cache *RecordCache) {
				cache.Purge(100)
				if _, ok := cache.Load(NewServiceRecordGUID(MetricServiceName, "alpha", "svc-a")); ok {
					t.Fatalf("Got stale nil service record preserved, expected deleted by purge")
				}
			},
		},
		{
			name: "happy_purge_preserves_fresh_nil_service_record",
			setupFunc: func(cache *RecordCache) {
				cache.Store(NewServiceRecordGUID(MetricServiceName, "alpha", "svc-a"), &Record{Value: NewNilValue()})
			},
			checkFunc: func(t *testing.T, cache *RecordCache) {
				cache.Purge(100)
				if _, ok := cache.Load(NewServiceRecordGUID(MetricServiceName, "alpha", "svc-a")); !ok {
					t.Fatalf("Got fresh nil service record deleted, expected preserved by purge")
				}
			},
		},
		{
			name: "happy_purge_does_not_delete_stale_nil_host_record",
			setupFunc: func(cache *RecordCache) {
				cache.Store(NewRecordGUID(MetricHost, "alpha"), &Record{Value: ValueData{Timestamp: oldTimestamp}})
			},
			checkFunc: func(t *testing.T, cache *RecordCache) {
				cache.Purge(100)
				if _, ok := cache.Load(NewRecordGUID(MetricHost, "alpha")); !ok {
					t.Fatalf("Got stale nil host record deleted, expected preserved by purge")
				}
			},
		},
		{
			name: "happy_purge_delete_calls_deletes_listener",
			setupFunc: func(cache *RecordCache) {
				cache.Store(NewServiceRecordGUID(MetricServiceName, "alpha", "svc-a"), &Record{
					Topic: "supervisor/alpha/data/service/svc-a/name",
					Value: ValueData{Timestamp: oldTimestamp},
				})
			},
			checkFunc: func(t *testing.T, cache *RecordCache) {
				listener := &mockDeletesListener{}
				cache.SubscribeDeletes(listener)
				cache.Purge(100)
				if listener.unsubscribeCount != 1 {
					t.Fatalf("Got deletes listener count = %d, expected 1", listener.unsubscribeCount)
				}
			},
		},
		{
			name: "happy_purge_evict_then_delete_after_stale",
			setupFunc: func(cache *RecordCache) {
				cache.Store(NewServiceRecordGUID(MetricServiceName, "alpha", "svc-a"), &Record{Value: staleValue("v")})
			},
			checkFunc: func(t *testing.T, cache *RecordCache) {
				cache.Purge(100)
				record, ok := cache.Load(NewServiceRecordGUID(MetricServiceName, "alpha", "svc-a"))
				if !ok || record == nil {
					t.Fatalf("Got record deleted on first purge, expected evicted to nil")
				}
				if record.Value.Pulse != nil {
					t.Fatalf("Got non-nil pulse after first purge, expected nil")
				}
				cache.mutex.Lock()
				k := NewServiceRecordGUID(MetricServiceName, "alpha", "svc-a").key()
				r := cache.records[k]
				if r != nil {
					r.Value.Timestamp = oldTimestamp
				}
				cache.mutex.Unlock()
				cache.Purge(100)
				if _, ok := cache.Load(NewServiceRecordGUID(MetricServiceName, "alpha", "svc-a")); ok {
					t.Fatalf("Got stale nil service record preserved on second purge, expected deleted")
				}
			},
		},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			cache := NewRecordCache()
			tt.setupFunc(cache)
			tt.checkFunc(t, cache)
		})
	}
}

func TestRecordCache_SchemaListeners(t *testing.T) {
	value := ValueData{Pulse: &ValueDataDetail{OK: true, Kind: ValueString, ValueString: "v"}}
	value2 := ValueData{Pulse: &ValueDataDetail{OK: true, Kind: ValueString, ValueString: "w"}}
	tests := []struct {
		name                string
		setupFunc           func(*RecordCache, *mockListener)
		expectedSchemaDirty int
	}{
		{
			name: "happy_store_service_notifies_schema_listener",
			setupFunc: func(cache *RecordCache, listener *mockListener) {
				cache.Store(NewServiceSchemaRecordGUID(MetricServiceName, "alpha", 0), &Record{})
				cache.SubscribeUpdates(NewServiceSchemaRecordGUID(MetricServiceName, "alpha", 0), listener)
				cache.Store(NewServiceRecordGUID(MetricServiceName, "alpha", "svc-a"), &Record{Value: value})
			},
			expectedSchemaDirty: 1,
		},
		{
			name: "happy_store_service_same_value_no_schema_notification",
			setupFunc: func(cache *RecordCache, listener *mockListener) {
				cache.Store(NewServiceSchemaRecordGUID(MetricServiceName, "alpha", 0), &Record{})
				cache.Store(NewServiceRecordGUID(MetricServiceName, "alpha", "svc-a"), &Record{Value: value})
				cache.SubscribeUpdates(NewServiceSchemaRecordGUID(MetricServiceName, "alpha", 0), listener)
				cache.Store(NewServiceRecordGUID(MetricServiceName, "alpha", "svc-a"), &Record{Value: value})
			},
			expectedSchemaDirty: 0,
		},
		{
			name: "happy_store_service_updated_value_notifies_schema_listener",
			setupFunc: func(cache *RecordCache, listener *mockListener) {
				cache.Store(NewServiceSchemaRecordGUID(MetricServiceName, "alpha", 0), &Record{})
				cache.SubscribeUpdates(NewServiceSchemaRecordGUID(MetricServiceName, "alpha", 0), listener)
				cache.Store(NewServiceRecordGUID(MetricServiceName, "alpha", "svc-a"), &Record{Value: value})
				cache.Store(NewServiceRecordGUID(MetricServiceName, "alpha", "svc-a"), &Record{Value: value2})
			},
			expectedSchemaDirty: 2,
		},
		{
			name: "happy_store_host_metric_does_not_notify_schema_listener",
			setupFunc: func(cache *RecordCache, listener *mockListener) {
				cache.Store(NewServiceSchemaRecordGUID(MetricServiceName, "alpha", 0), &Record{})
				cache.SubscribeUpdates(NewServiceSchemaRecordGUID(MetricServiceName, "alpha", 0), listener)
				cache.Store(NewRecordGUID(MetricHost, "alpha"), &Record{Value: value})
			},
			expectedSchemaDirty: 0,
		},
		{
			name: "happy_store_schema_record_notifies_direct_listener",
			setupFunc: func(cache *RecordCache, listener *mockListener) {
				cache.Store(NewServiceSchemaRecordGUID(MetricServiceName, "alpha", 0), &Record{})
				cache.SubscribeUpdates(NewServiceSchemaRecordGUID(MetricServiceName, "alpha", 0), listener)
				cache.Store(NewServiceSchemaRecordGUID(MetricServiceName, "alpha", 0), &Record{Value: value})
			},
			expectedSchemaDirty: 1,
		},
		{
			name: "happy_store_service_different_host_no_schema_notification",
			setupFunc: func(cache *RecordCache, listener *mockListener) {
				cache.Store(NewServiceSchemaRecordGUID(MetricServiceName, "alpha", 0), &Record{})
				cache.SubscribeUpdates(NewServiceSchemaRecordGUID(MetricServiceName, "alpha", 0), listener)
				cache.Store(NewServiceRecordGUID(MetricServiceName, "beta", "svc-a"), &Record{Value: value})
			},
			expectedSchemaDirty: 0,
		},
		{
			name: "happy_store_service_different_metric_no_schema_notification",
			setupFunc: func(cache *RecordCache, listener *mockListener) {
				cache.Store(NewServiceSchemaRecordGUID(MetricServiceName, "alpha", 0), &Record{})
				cache.SubscribeUpdates(NewServiceSchemaRecordGUID(MetricServiceName, "alpha", 0), listener)
				cache.Store(NewServiceRecordGUID(MetricServiceUsedProcessor, "alpha", "svc-a"), &Record{Value: value})
			},
			expectedSchemaDirty: 0,
		},
		{
			name: "happy_store_multiple_services_notify_same_schema_listener",
			setupFunc: func(cache *RecordCache, listener *mockListener) {
				cache.Store(NewServiceSchemaRecordGUID(MetricServiceName, "alpha", 0), &Record{})
				cache.SubscribeUpdates(NewServiceSchemaRecordGUID(MetricServiceName, "alpha", 0), listener)
				cache.Store(NewServiceRecordGUID(MetricServiceName, "alpha", "svc-a"), &Record{Value: value})
				cache.Store(NewServiceRecordGUID(MetricServiceName, "alpha", "svc-b"), &Record{Value: value})
			},
			expectedSchemaDirty: 2,
		},
		{
			name: "happy_evict_notifies_schema_listener",
			setupFunc: func(cache *RecordCache, listener *mockListener) {
				cache.Store(NewServiceSchemaRecordGUID(MetricServiceName, "alpha", 0), &Record{})
				cache.Store(NewServiceRecordGUID(MetricServiceName, "alpha", "svc-a"), &Record{Value: value})
				cache.SubscribeUpdates(NewServiceSchemaRecordGUID(MetricServiceName, "alpha", 0), listener)
				cache.Evict("alpha", "svc-a")
			},
			expectedSchemaDirty: 1,
		},
		{
			name: "happy_evict_noop_no_schema_notification",
			setupFunc: func(cache *RecordCache, listener *mockListener) {
				cache.Store(NewServiceSchemaRecordGUID(MetricServiceName, "alpha", 0), &Record{})
				cache.Store(NewServiceRecordGUID(MetricServiceName, "alpha", "svc-a"), &Record{Value: value})
				cache.Evict("alpha", "svc-a")
				cache.SubscribeUpdates(NewServiceSchemaRecordGUID(MetricServiceName, "alpha", 0), listener)
				cache.Evict("alpha", "svc-a")
			},
			expectedSchemaDirty: 0,
		},
		{
			name: "happy_delete_notifies_schema_listener",
			setupFunc: func(cache *RecordCache, listener *mockListener) {
				cache.Store(NewServiceSchemaRecordGUID(MetricServiceName, "alpha", 0), &Record{})
				cache.Store(NewServiceRecordGUID(MetricServiceName, "alpha", "svc-a"), &Record{Value: value})
				cache.Evict("alpha", "svc-a")
				cache.SubscribeUpdates(NewServiceSchemaRecordGUID(MetricServiceName, "alpha", 0), listener)
				cache.Delete("alpha", "svc-a")
			},
			expectedSchemaDirty: 1,
		},
		{
			name: "happy_delete_noop_no_schema_notification",
			setupFunc: func(cache *RecordCache, listener *mockListener) {
				cache.Store(NewServiceSchemaRecordGUID(MetricServiceName, "alpha", 0), &Record{})
				cache.Store(NewServiceRecordGUID(MetricServiceName, "alpha", "svc-a"), &Record{Value: value})
				cache.SubscribeUpdates(NewServiceSchemaRecordGUID(MetricServiceName, "alpha", 0), listener)
				cache.Delete("alpha", "svc-a")
			},
			expectedSchemaDirty: 0,
		},
		{
			name: "happy_purge_stale_no_schema_notification",
			setupFunc: func(cache *RecordCache, listener *mockListener) {
				stale := ValueData{Timestamp: time.Now().Unix() - 200, Pulse: &ValueDataDetail{OK: true, Kind: ValueString, ValueString: "v"}}
				cache.Store(NewServiceSchemaRecordGUID(MetricServiceName, "alpha", 0), &Record{})
				cache.Store(NewServiceRecordGUID(MetricServiceName, "alpha", "svc-a"), &Record{Value: stale})
				cache.SubscribeUpdates(NewServiceSchemaRecordGUID(MetricServiceName, "alpha", 0), listener)
				cache.Purge(9999)
			},
			expectedSchemaDirty: 0,
		},
		{
			name: "happy_purge_nil_service_record_does_not_notify_schema_listener",
			setupFunc: func(cache *RecordCache, listener *mockListener) {
				cache.Store(NewServiceSchemaRecordGUID(MetricServiceName, "alpha", 0), &Record{})
				cache.Store(NewServiceRecordGUID(MetricServiceName, "alpha", "svc-a"), &Record{Value: value})
				cache.Evict("alpha", "svc-a")
				cache.SubscribeUpdates(NewServiceSchemaRecordGUID(MetricServiceName, "alpha", 0), listener)
				cache.Purge(9999)
			},
			expectedSchemaDirty: 0,
		},
		{
			name: "happy_purge_noop_no_schema_notification",
			setupFunc: func(cache *RecordCache, listener *mockListener) {
				fresh := ValueData{Timestamp: time.Now().Unix(), Pulse: &ValueDataDetail{OK: true, Kind: ValueString, ValueString: "v"}}
				cache.Store(NewServiceSchemaRecordGUID(MetricServiceName, "alpha", 0), &Record{})
				cache.Store(NewServiceRecordGUID(MetricServiceName, "alpha", "svc-a"), &Record{Value: fresh})
				cache.SubscribeUpdates(NewServiceSchemaRecordGUID(MetricServiceName, "alpha", 0), listener)
				cache.Purge(9999)
			},
			expectedSchemaDirty: 0,
		},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			cache := NewRecordCache()
			listener := &mockListener{}
			tt.setupFunc(cache, listener)
			if listener.dirtyCount != tt.expectedSchemaDirty {
				t.Fatalf("Got schema dirty count = %d, expected %d", listener.dirtyCount, tt.expectedSchemaDirty)
			}
		})
	}
}

func TestRecordCache_RegisterService(t *testing.T) {
	value := ValueData{Pulse: &ValueDataDetail{OK: true, Kind: ValueString, ValueString: "v"}}
	tests := []struct {
		name      string
		setupFunc func(*RecordCache)
		checkFunc func(*testing.T, *RecordCache)
	}{
		{
			name: "happy_registers_new_service",
			setupFunc: func(cache *RecordCache) {
				cache.Store(NewServiceSchemaRecordGUID(MetricServiceName, "alpha", 0), &Record{})
				cache.SubscribeUpdates(NewServiceSchemaRecordGUID(MetricServiceName, "alpha", 0), &mockListener{})
			},
			checkFunc: func(t *testing.T, cache *RecordCache) {
				bindings := cache.RegisterService("alpha", "svc-a", false)
				t.Logf("Cache:\n%s", cache.String())
				if _, ok := cache.Load(NewServiceRecordGUID(MetricServiceName, "alpha", "svc-a")); !ok {
					t.Fatalf("Got svc-a not found, expected registered")
				}
				for _, b := range bindings {
					if b.GUID.ID == MetricServiceName {
						t.Fatalf("Got MetricServiceName in bindings, expected excluded")
					}
				}
			},
		},
		{
			name: "happy_registers_all_metric_ids_from_listeners",
			setupFunc: func(cache *RecordCache) {
				cache.Store(NewServiceSchemaRecordGUID(MetricServiceName, "alpha", 0), &Record{})
				cache.Store(NewServiceSchemaRecordGUID(MetricServiceUsedProcessor, "alpha", 0), &Record{})
				cache.Store(NewServiceSchemaRecordGUID(MetricServiceHealthStatus, "alpha", 0), &Record{})
				cache.SubscribeUpdates(NewServiceSchemaRecordGUID(MetricServiceName, "alpha", 0), &mockListener{})
				cache.SubscribeUpdates(NewServiceSchemaRecordGUID(MetricServiceUsedProcessor, "alpha", 0), &mockListener{})
				cache.SubscribeUpdates(NewServiceSchemaRecordGUID(MetricServiceHealthStatus, "alpha", 0), &mockListener{})
			},
			checkFunc: func(t *testing.T, cache *RecordCache) {
				cache.RegisterService("alpha", "svc-a", false)
				t.Logf("Cache:\n%s", cache.String())
				for _, id := range []ID{MetricServiceName, MetricServiceUsedProcessor, MetricServiceHealthStatus} {
					if _, ok := cache.Load(NewServiceRecordGUID(id, "alpha", "svc-a")); !ok {
						t.Fatalf("Got metric %d not found for svc-a, expected registered", id)
					}
				}
			},
		},
		{
			name: "happy_idempotent_second_call_returns_nil",
			setupFunc: func(cache *RecordCache) {
				cache.Store(NewServiceSchemaRecordGUID(MetricServiceName, "alpha", 0), &Record{})
				cache.SubscribeUpdates(NewServiceSchemaRecordGUID(MetricServiceName, "alpha", 0), &mockListener{})
				cache.RegisterService("alpha", "svc-a", false)
			},
			checkFunc: func(t *testing.T, cache *RecordCache) {
				bindings := cache.RegisterService("alpha", "svc-a", false)
				if len(bindings) != 0 {
					t.Fatalf("Got %d bindings, expected 0 for already-registered service", len(bindings))
				}
			},
		},
		{
			name: "happy_returns_topic_bindings_excluding_name",
			setupFunc: func(cache *RecordCache) {
				cache.Store(NewServiceSchemaRecordGUID(MetricServiceName, "alpha", 0), &Record{})
				cache.Store(NewServiceSchemaRecordGUID(MetricServiceUsedProcessor, "alpha", 0), &Record{})
				cache.SubscribeUpdates(NewServiceSchemaRecordGUID(MetricServiceName, "alpha", 0), &mockListener{})
				cache.SubscribeUpdates(NewServiceSchemaRecordGUID(MetricServiceUsedProcessor, "alpha", 0), &mockListener{})
			},
			checkFunc: func(t *testing.T, cache *RecordCache) {
				bindings := cache.RegisterService("alpha", "svc-a", false)
				t.Logf("Cache:\n%s", cache.String())
				for _, b := range bindings {
					if b.GUID.ID == MetricServiceName {
						t.Fatalf("Got MetricServiceName binding, expected excluded")
					}
					if b.Topic == "" {
						t.Fatalf("Got empty topic in binding for metric %d", b.GUID.ID)
					}
				}
			},
		},
		{
			name: "happy_reindexes_new_service",
			setupFunc: func(cache *RecordCache) {
				cache.Store(NewServiceSchemaRecordGUID(MetricServiceName, "alpha", 0), &Record{})
				cache.SubscribeUpdates(NewServiceSchemaRecordGUID(MetricServiceName, "alpha", 0), &mockListener{})
				cache.Store(NewServiceRecordGUID(MetricServiceName, "alpha", "svc-a"), &Record{Value: value})
			},
			checkFunc: func(t *testing.T, cache *RecordCache) {
				cache.RegisterService("alpha", "svc-b", false)
				t.Logf("Cache:\n%s", cache.String())
				record, ok := cache.LoadByID(MetricServiceName, "alpha", 0)
				if !ok || record == nil {
					t.Fatalf("Got no record at index 0, expected svc-a")
				}
				record, ok = cache.LoadByID(MetricServiceName, "alpha", 1)
				if !ok || record == nil {
					t.Fatalf("Got no record at index 1, expected svc-b")
				}
			},
		},
		{
			name:      "happy_nil_cache_returns_nil",
			setupFunc: func(cache *RecordCache) {},
			checkFunc: func(t *testing.T, cache *RecordCache) {
				var nilCache *RecordCache
				if bindings := nilCache.RegisterService("alpha", "svc-a", false); bindings != nil {
					t.Fatalf("Got non-nil from nil cache, expected nil")
				}
			},
		},
		{
			name:      "happy_empty_host_returns_nil",
			setupFunc: func(cache *RecordCache) {},
			checkFunc: func(t *testing.T, cache *RecordCache) {
				if bindings := cache.RegisterService("", "svc-a", false); bindings != nil {
					t.Fatalf("Got non-nil for empty host, expected nil")
				}
			},
		},
		{
			name:      "happy_empty_service_name_returns_nil",
			setupFunc: func(cache *RecordCache) {},
			checkFunc: func(t *testing.T, cache *RecordCache) {
				if bindings := cache.RegisterService("alpha", "", false); bindings != nil {
					t.Fatalf("Got non-nil for empty service name, expected nil")
				}
			},
		},
		{
			name:      "happy_unset_service_name_returns_nil",
			setupFunc: func(cache *RecordCache) {},
			checkFunc: func(t *testing.T, cache *RecordCache) {
				if bindings := cache.RegisterService("alpha", ServiceNameUnset, false); bindings != nil {
					t.Fatalf("Got non-nil for unset service name, expected nil")
				}
			},
		},
		{
			name:      "happy_schema_service_name_returns_nil",
			setupFunc: func(cache *RecordCache) {},
			checkFunc: func(t *testing.T, cache *RecordCache) {
				if bindings := cache.RegisterService("alpha", ServiceNameSchema, false); bindings != nil {
					t.Fatalf("Got non-nil for schema service name, expected nil")
				}
			},
		},
		{
			name: "happy_no_listeners_returns_nil",
			setupFunc: func(cache *RecordCache) {
				cache.Store(NewServiceSchemaRecordGUID(MetricServiceName, "alpha", 0), &Record{})
			},
			checkFunc: func(t *testing.T, cache *RecordCache) {
				if bindings := cache.RegisterService("alpha", "svc-a", false); bindings != nil {
					t.Fatalf("Got non-nil with no listeners, expected nil")
				}
			},
		},
		{
			name: "happy_ignores_host_metric_listeners",
			setupFunc: func(cache *RecordCache) {
				cache.Store(NewRecordGUID(MetricHost, "alpha"), &Record{})
				cache.SubscribeUpdates(NewRecordGUID(MetricHost, "alpha"), &mockListener{})
			},
			checkFunc: func(t *testing.T, cache *RecordCache) {
				bindings := cache.RegisterService("alpha", "svc-a", false)
				if len(bindings) != 0 {
					t.Fatalf("Got %d bindings, expected 0 for host-only listeners", len(bindings))
				}
			},
		},
		{
			name: "happy_scoped_to_host",
			setupFunc: func(cache *RecordCache) {
				cache.Store(NewServiceSchemaRecordGUID(MetricServiceName, "alpha", 0), &Record{})
				cache.Store(NewServiceSchemaRecordGUID(MetricServiceName, "beta", 0), &Record{})
				cache.SubscribeUpdates(NewServiceSchemaRecordGUID(MetricServiceName, "alpha", 0), &mockListener{})
				cache.SubscribeUpdates(NewServiceSchemaRecordGUID(MetricServiceName, "beta", 0), &mockListener{})
			},
			checkFunc: func(t *testing.T, cache *RecordCache) {
				cache.RegisterService("alpha", "svc-a", false)
				if _, ok := cache.Load(NewServiceRecordGUID(MetricServiceName, "alpha", "svc-a")); !ok {
					t.Fatalf("Got alpha svc-a not found, expected registered")
				}
				if _, ok := cache.Load(NewServiceRecordGUID(MetricServiceName, "beta", "svc-a")); ok {
					t.Fatalf("Got beta svc-a found, expected not registered")
				}
			},
		},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			cache := NewRecordCache()
			tt.setupFunc(cache)
			tt.checkFunc(t, cache)
		})
	}
}

func TestRecordCache_Topics(t *testing.T) {
	tests := []struct {
		name           string
		setupFunc      func(*RecordCache)
		expectedTopics int
	}{
		{
			name: "happy_returns_all_topics",
			setupFunc: func(cache *RecordCache) {
				cache.Store(NewServiceRecordGUID(MetricServiceName, "alpha", "svc-a"), &Record{})
				cache.Store(NewServiceRecordGUID(MetricServiceUsedProcessor, "alpha", "svc-a"), &Record{})
			},
			expectedTopics: 2,
		},
		{
			name: "happy_deduplicates_same_topic",
			setupFunc: func(cache *RecordCache) {
				cache.Store(NewRecordGUID(MetricHost, "alpha"), &Record{Topic: "supervisor/alpha/data/host/host"})
				cache.Store(NewRecordGUID(MetricHost, "beta"), &Record{Topic: "supervisor/alpha/data/host/host"})
			},
			expectedTopics: 1,
		},
		{
			name: "happy_schema_records_without_topics_skipped",
			setupFunc: func(cache *RecordCache) {
				cache.Store(NewServiceSchemaRecordGUID(MetricServiceName, "alpha", 0), &Record{})
			},
			expectedTopics: 0,
		},
		{
			name: "happy_schema_records_with_real_service_records_not_included_in_topics",
			setupFunc: func(cache *RecordCache) {
				cache.Store(NewServiceSchemaRecordGUID(MetricServiceName, "alpha", 0), &Record{})
				cache.Store(NewServiceRecordGUID(MetricServiceName, "alpha", "svc-a"), &Record{})
			},
			expectedTopics: 1,
		},
		{
			name: "happy_evicted_service_record_topic_preserved_for_resubscription",
			setupFunc: func(cache *RecordCache) {
				v := ValueData{Timestamp: time.Now().Unix(), Pulse: &ValueDataDetail{OK: true, Kind: ValueString, ValueString: "v"}}
				cache.Store(NewServiceRecordGUID(MetricServiceName, "alpha", "svc-a"), &Record{Value: v})
				cache.Evict("alpha", "svc-a")
				cache.Purge(9999)
			},
			expectedTopics: 1,
		},
		{
			name:           "happy_empty_cache",
			setupFunc:      func(cache *RecordCache) {},
			expectedTopics: 0,
		},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			cache := NewRecordCache()
			tt.setupFunc(cache)
			topics := cache.Topics()
			t.Logf("Cache:\n%s", cache.String())
			if len(topics) != tt.expectedTopics {
				t.Fatalf("Got %d topics, expected %d", len(topics), tt.expectedTopics)
			}
		})
	}
	t.Run("happy_nil_cache_returns_nil", func(t *testing.T) {
		var c *RecordCache
		if c.Topics() != nil {
			t.Fatalf("Got non-nil from nil cache, expected nil")
		}
	})
}

func TestRecordCache_ListenerIDs(t *testing.T) {
	tests := []struct {
		name     string
		setup    func(*RecordCache)
		expected map[string]int
	}{
		{
			name: "happy_returns_ids_by_host",
			setup: func(cache *RecordCache) {
				cache.SubscribeUpdates(NewServiceSchemaRecordGUID(MetricServiceName, "alpha", 0), &mockListener{})
				cache.SubscribeUpdates(NewServiceSchemaRecordGUID(MetricServiceUsedProcessor, "alpha", 0), &mockListener{})
				cache.SubscribeUpdates(NewServiceSchemaRecordGUID(MetricServiceName, "beta", 0), &mockListener{})
			},
			expected: map[string]int{"alpha": 2, "beta": 1},
		},
		{
			name: "happy_includes_host_metric_listeners",
			setup: func(cache *RecordCache) {
				cache.SubscribeUpdates(NewRecordGUID(MetricHost, "alpha"), &mockListener{})
			},
			expected: map[string]int{"alpha": 1},
		},
		{
			name:     "happy_empty_when_no_listeners",
			setup:    func(cache *RecordCache) {},
			expected: map[string]int{},
		},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			cache := NewRecordCache()
			tt.setup(cache)
			result := cache.ListenerIDs()
			for host, expectedCount := range tt.expected {
				if len(result[host]) != expectedCount {
					t.Fatalf("Got %d IDs for host %q, expected %d", len(result[host]), host, expectedCount)
				}
			}
			if len(result) != len(tt.expected) {
				t.Fatalf("Got %d hosts, expected %d", len(result), len(tt.expected))
			}
		})
	}
}

func TestRecordCache_SubscribeDeletes(t *testing.T) {
	tests := []struct {
		name      string
		setupFunc func(*RecordCache)
		checkFunc func(*testing.T, *RecordCache)
	}{
		{
			name: "happy_delete_unsubscribes_topics",
			setupFunc: func(cache *RecordCache) {
				value := ValueData{Pulse: &ValueDataDetail{OK: true, Kind: ValueString, ValueString: "v"}}
				cache.Store(NewServiceRecordGUID(MetricServiceName, "alpha", "svc-a"), &Record{Value: value})
				cache.Evict("alpha", "svc-a")
			},
			checkFunc: func(t *testing.T, cache *RecordCache) {
				listener := &mockDeletesListener{}
				cache.SubscribeDeletes(listener)
				cache.Delete("alpha", "svc-a")
				if listener.unsubscribeCount != 1 {
					t.Fatalf("Got unsubscribe count = %d, expected 1", listener.unsubscribeCount)
				}
			},
		},
		{
			name: "happy_purge_does_not_unsubscribe_evicted_service_topics",
			setupFunc: func(cache *RecordCache) {
				value := ValueData{Pulse: &ValueDataDetail{OK: true, Kind: ValueString, ValueString: "v"}}
				cache.Store(NewServiceRecordGUID(MetricServiceName, "alpha", "svc-a"), &Record{Value: value})
				cache.Evict("alpha", "svc-a")
			},
			checkFunc: func(t *testing.T, cache *RecordCache) {
				listener := &mockDeletesListener{}
				cache.SubscribeDeletes(listener)
				cache.Purge(9999)
				if listener.unsubscribeCount != 0 {
					t.Fatalf("Got unsubscribe count = %d, expected 0 — purge must not unsubscribe evicted service topics", listener.unsubscribeCount)
				}
			},
		},
		{
			name: "happy_no_unsubscribe_when_no_deletes_listener",
			setupFunc: func(cache *RecordCache) {
				value := ValueData{Pulse: &ValueDataDetail{OK: true, Kind: ValueString, ValueString: "v"}}
				cache.Store(NewServiceRecordGUID(MetricServiceName, "alpha", "svc-a"), &Record{Value: value})
				cache.Evict("alpha", "svc-a")
			},
			checkFunc: func(t *testing.T, cache *RecordCache) {
				cache.Delete("alpha", "svc-a")
			},
		},
		{
			name:      "happy_nil_cache_is_noop",
			setupFunc: func(cache *RecordCache) {},
			checkFunc: func(t *testing.T, cache *RecordCache) {
				var nilCache *RecordCache
				nilCache.SubscribeDeletes(&mockDeletesListener{})
			},
		},
		{
			name: "happy_delete_multiple_metrics_unsubscribes_all",
			setupFunc: func(cache *RecordCache) {
				value := ValueData{Pulse: &ValueDataDetail{OK: true, Kind: ValueString, ValueString: "v"}}
				cache.Store(NewServiceRecordGUID(MetricServiceName, "alpha", "svc-a"), &Record{Value: value})
				cache.Store(NewServiceRecordGUID(MetricServiceUsedProcessor, "alpha", "svc-a"), &Record{Value: value})
				cache.Evict("alpha", "svc-a")
			},
			checkFunc: func(t *testing.T, cache *RecordCache) {
				listener := &mockDeletesListener{}
				cache.SubscribeDeletes(listener)
				cache.Delete("alpha", "svc-a")
				if listener.unsubscribeCount != 2 {
					t.Fatalf("Got unsubscribe count = %d, expected 2", listener.unsubscribeCount)
				}
			},
		},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			cache := NewRecordCache()
			tt.setupFunc(cache)
			tt.checkFunc(t, cache)
		})
	}
}

type mockListener struct {
	dirtyCount int
}

func (m *mockListener) MarkDirty() {
	m.dirtyCount++
}

type mockDeletesListener struct {
	unsubscribeCount int
}

func (m *mockDeletesListener) Unsubscribe(_ string) {
	m.unsubscribeCount++
}

func guidSliceToSet(guids []RecordGUID) map[guidKey]struct{} {
	s := make(map[guidKey]struct{}, len(guids))
	for _, g := range guids {
		s[g.key()] = struct{}{}
	}
	return s
}

func TestRecordCache_Take(t *testing.T) {
	value1 := ValueData{Pulse: &ValueDataDetail{OK: true, Kind: ValueString, ValueString: "first"}}
	value2 := ValueData{Pulse: &ValueDataDetail{OK: true, Kind: ValueString, ValueString: "second"}}
	tests := []struct {
		name          string
		setupFunc     func(*RecordCache)
		checkFunc     func(*testing.T, *RecordCache)
		expectedError bool
	}{
		{
			name:      "happy_nil_cache_returns_nil",
			setupFunc: func(_ *RecordCache) {},
			checkFunc: func(t *testing.T, _ *RecordCache) {
				var c *RecordCache
				if c.Take() != nil {
					t.Fatalf("Got non-nil from nil cache, expected nil")
				}
			},
			expectedError: false,
		},
		{
			name:      "happy_empty_cache_returns_nil",
			setupFunc: func(_ *RecordCache) {},
			checkFunc: func(t *testing.T, cache *RecordCache) {
				if cache.Take() != nil {
					t.Fatalf("Got non-nil from empty cache, expected nil")
				}
			},
			expectedError: false,
		},
		{
			name: "happy_store_new_value_marks_dirty",
			setupFunc: func(cache *RecordCache) {
				guid := NewRecordGUID(MetricHost, "alpha")
				cache.Store(guid, &Record{Value: value1})
			},
			checkFunc: func(t *testing.T, cache *RecordCache) {
				got := cache.Take()
				if len(got) != 1 {
					t.Fatalf("Got %d dirty records, expected 1", len(got))
				}
				if got[0] != NewRecordGUID(MetricHost, "alpha") {
					t.Fatalf("Got dirty guid = %+v, expected alpha/MetricHost", got[0])
				}
			},
			expectedError: false,
		},
		{
			name: "happy_new_service_insert_dirty_has_reindexed_service_index",
			setupFunc: func(cache *RecordCache) {
				cache.Store(NewServiceRecordGUID(MetricServiceName, "alpha", "svc-a"), &Record{Value: value1})
			},
			checkFunc: func(t *testing.T, cache *RecordCache) {
				got := cache.Take()
				if len(got) != 1 {
					t.Fatalf("Got %d dirty records, expected 1", len(got))
				}
				if got[0].ServiceIndex != 0 {
					t.Fatalf("Got ServiceIndex = %d, expected 0 after reindex", got[0].ServiceIndex)
				}
			},
			expectedError: false,
		},
		{
			name: "happy_existing_service_update_dirty_has_reindexed_service_index",
			setupFunc: func(cache *RecordCache) {
				cache.Store(NewServiceRecordGUID(MetricServiceName, "alpha", "svc-a"), &Record{Value: value1})
				cache.Take()
				cache.Store(NewServiceRecordGUID(MetricServiceName, "alpha", "svc-a"), &Record{Value: value2})
			},
			checkFunc: func(t *testing.T, cache *RecordCache) {
				got := cache.Take()
				if len(got) != 1 {
					t.Fatalf("Got %d dirty records, expected 1", len(got))
				}
				if got[0].ServiceIndex != 0 {
					t.Fatalf("Got ServiceIndex = %d, expected 0 for existing record update", got[0].ServiceIndex)
				}
			},
			expectedError: false,
		},
		{
			name: "happy_reindex_updates_dirty_service_index_on_earlier_insertion",
			setupFunc: func(cache *RecordCache) {
				cache.Store(NewServiceRecordGUID(MetricServiceName, "alpha", "nginx"), &Record{Value: value1})
				cache.Store(NewServiceRecordGUID(MetricServiceName, "alpha", "apache"), &Record{Value: value1})
			},
			checkFunc: func(t *testing.T, cache *RecordCache) {
				got := cache.Take()
				indices := make(map[string]int)
				for _, guid := range got {
					indices[guid.ServiceName] = guid.ServiceIndex
				}
				if indices["nginx"] != 1 {
					t.Fatalf("Got nginx ServiceIndex = %d, expected 1 after apache inserted before it", indices["nginx"])
				}
				if indices["apache"] != 0 {
					t.Fatalf("Got apache ServiceIndex = %d, expected 0", indices["apache"])
				}
			},
			expectedError: false,
		},
		{
			name: "happy_nil_value_new_insert_not_dirty",
			setupFunc: func(cache *RecordCache) {
				cache.Store(NewRecordGUID(MetricHost, "alpha"), &Record{Value: NewNilValue()})
			},
			checkFunc: func(t *testing.T, cache *RecordCache) {
				if cache.Take() != nil {
					t.Fatalf("Got dirty records after nil-value new insert, expected nil")
				}
			},
			expectedError: false,
		},
		{
			name: "happy_nil_value_schema_insert_not_dirty",
			setupFunc: func(cache *RecordCache) {
				cache.Store(NewServiceSchemaRecordGUID(MetricServiceName, "alpha", 0), &Record{Value: NewNilValue()})
			},
			checkFunc: func(t *testing.T, cache *RecordCache) {
				if cache.Take() != nil {
					t.Fatalf("Got dirty records after nil-value schema insert, expected nil")
				}
			},
			expectedError: false,
		},
		{
			name: "happy_store_same_value_not_dirty",
			setupFunc: func(cache *RecordCache) {
				guid := NewRecordGUID(MetricHost, "alpha")
				cache.Store(guid, &Record{Value: value1})
				cache.Take()
				cache.Store(guid, &Record{Value: value1})
			},
			checkFunc: func(t *testing.T, cache *RecordCache) {
				if cache.Take() != nil {
					t.Fatalf("Got dirty records after same-value store, expected nil")
				}
			},
			expectedError: false,
		},
		{
			name: "happy_store_changed_value_marks_dirty",
			setupFunc: func(cache *RecordCache) {
				guid := NewRecordGUID(MetricHost, "alpha")
				cache.Store(guid, &Record{Value: value1})
				cache.Take()
				cache.Store(guid, &Record{Value: value2})
			},
			checkFunc: func(t *testing.T, cache *RecordCache) {
				got := cache.Take()
				if len(got) != 1 {
					t.Fatalf("Got %d dirty records after value change, expected 1", len(got))
				}
			},
			expectedError: false,
		},
		{
			name: "happy_take_flushes_dirty_map",
			setupFunc: func(cache *RecordCache) {
				cache.Store(NewRecordGUID(MetricHost, "alpha"), &Record{Value: value1})
			},
			checkFunc: func(t *testing.T, cache *RecordCache) {
				first := cache.Take()
				if len(first) != 1 {
					t.Fatalf("Got %d dirty records on first Take, expected 1", len(first))
				}
				second := cache.Take()
				if second != nil {
					t.Fatalf("Got %d dirty records on second Take, expected nil", len(second))
				}
			},
			expectedError: false,
		},
		{
			name: "happy_store_nil_value_after_non_nil_marks_dirty",
			setupFunc: func(cache *RecordCache) {
				cache.Store(NewRecordGUID(MetricHost, "alpha"), &Record{Value: value1})
				cache.Take()
				nilRecord := NewRecord(NewNilValue())
				cache.Store(NewRecordGUID(MetricHost, "alpha"), &nilRecord)
			},
			checkFunc: func(t *testing.T, cache *RecordCache) {
				got := cache.Take()
				if len(got) != 1 {
					t.Fatalf("Got %d dirty records after nil store over non-nil, expected 1", len(got))
				}
			},
			expectedError: false,
		},
		{
			name: "happy_evict_marks_dirty",
			setupFunc: func(cache *RecordCache) {
				cache.Store(NewServiceRecordGUID(MetricServiceName, "alpha", "svc-a"), &Record{Value: value1})
				cache.Take()
				cache.Evict("alpha", "svc-a")
			},
			checkFunc: func(t *testing.T, cache *RecordCache) {
				got := cache.Take()
				if len(got) != 1 {
					t.Fatalf("Got %d dirty records after evict, expected 1", len(got))
				}
			},
			expectedError: false,
		},
		{
			name: "happy_delete_clears_dirty",
			setupFunc: func(cache *RecordCache) {
				cache.Store(NewServiceRecordGUID(MetricServiceName, "alpha", "svc-a"), &Record{Value: value1})
				cache.Evict("alpha", "svc-a")
				cache.Delete("alpha", "svc-a")
			},
			checkFunc: func(t *testing.T, cache *RecordCache) {
				if cache.Take() != nil {
					t.Fatalf("Got dirty records after delete, expected nil")
				}
			},
			expectedError: false,
		},
		{
			name: "happy_purge_stale_not_dirty",
			setupFunc: func(cache *RecordCache) {
				fresh := ValueData{Timestamp: time.Now().Unix(), Pulse: &ValueDataDetail{OK: true, Kind: ValueString, ValueString: "first"}}
				cache.Store(NewServiceRecordGUID(MetricServiceName, "alpha", "svc-a"), &Record{Value: fresh})
				cache.Take()
				cache.Purge(9999)
			},
			checkFunc: func(t *testing.T, cache *RecordCache) {
				if cache.Take() != nil {
					t.Fatalf("Got dirty records after purge of non-nil record, expected nil")
				}
			},
			expectedError: false,
		},
		{
			name: "happy_purge_preserves_dirty_for_nil_service_records",
			setupFunc: func(cache *RecordCache) {
				cache.Store(NewServiceRecordGUID(MetricServiceName, "alpha", "svc-a"), &Record{Value: value1})
				cache.Evict("alpha", "svc-a")
			},
			checkFunc: func(t *testing.T, cache *RecordCache) {
				cache.Purge(9999)
				got := cache.Take()
				if len(got) != 1 {
					t.Fatalf("Got %d dirty records after purge of nil service record, expected 1 — purge must not clear dirty", len(got))
				}
			},
			expectedError: false,
		},
		{
			name: "happy_multiple_dirty_records",
			setupFunc: func(cache *RecordCache) {
				cache.Store(NewRecordGUID(MetricHost, "alpha"), &Record{Value: value1})
				cache.Store(NewRecordGUID(MetricHost, "beta"), &Record{Value: value1})
				cache.Store(NewServiceRecordGUID(MetricServiceName, "alpha", "svc-a"), &Record{Value: value1})
			},
			checkFunc: func(t *testing.T, cache *RecordCache) {
				got := cache.Take()
				if len(got) != 3 {
					t.Fatalf("Got %d dirty records, expected 3", len(got))
				}
				gotSet := guidSliceToSet(got)
				expected := []RecordGUID{
					NewRecordGUID(MetricHost, "alpha"),
					NewRecordGUID(MetricHost, "beta"),
					NewServiceRecordGUID(MetricServiceName, "alpha", "svc-a"),
				}
				for _, g := range expected {
					if _, ok := gotSet[g.key()]; !ok {
						t.Fatalf("Got dirty set missing guid %+v", g)
					}
				}
			},
			expectedError: false,
		},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			cache := NewRecordCache()
			tt.setupFunc(cache)
			tt.checkFunc(t, cache)
		})
	}
}
