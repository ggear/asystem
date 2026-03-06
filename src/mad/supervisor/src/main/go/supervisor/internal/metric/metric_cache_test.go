package metric

import (
	"reflect"
	"testing"
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
}

func TestRecordCache_Services(t *testing.T) {
	tests := []struct {
		name     string
		records  []RecordGUID
		expected map[string]int
	}{
		{
			name: "happy_sorted_services",
			records: []RecordGUID{
				NewServiceRecordGUID(MetricServiceName, "alpha", "service-beta"),
				NewServiceRecordGUID(MetricServiceName, "alpha", "service-alpha"),
				NewRecordGUID(MetricHost, "alpha"),
			},
			expected: map[string]int{"service-alpha": 0, "service-beta": 1},
		},
		{
			name: "happy_single_service",
			records: []RecordGUID{
				NewServiceRecordGUID(MetricServiceName, "alpha", "service-beta"),
			},
			expected: map[string]int{"service-beta": 0},
		},
		{
			name: "happy_services_from_any_metric_id",
			records: []RecordGUID{
				NewServiceRecordGUID(MetricServiceUsedProcessor, "alpha", "svc-a"),
			},
			expected: map[string]int{"svc-a": 0},
		},
		{
			name:     "happy_no_services",
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
			services := cache.Services()
			t.Logf("Cache:\n%s", cache.String())
			if !reflect.DeepEqual(services, tt.expected) {
				t.Fatalf("Got services = %+v, expected %+v", services, tt.expected)
			}
		})
	}
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
				services := cache.Services()
				if _, exists := services["svc-a"]; !exists {
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
			name: "happy_delete_notifies_updates_channel",
			setupFunc: func(cache *RecordCache) {
				value := ValueData{Pulse: &ValueDataDetail{OK: true, Kind: ValueString, ValueString: "value"}}
				cache.Store(NewServiceRecordGUID(MetricServiceName, "alpha", "svc-a"), &Record{Value: value})
				evicted(cache, "alpha", "svc-a")
			},
			checkFunc: func(t *testing.T, cache *RecordCache) {
				drainChannel(cache.Updates())
				cache.Delete("alpha", "svc-a")
				select {
				case <-cache.Updates():
				default:
					t.Fatalf("Got no update notification, expected one after delete")
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
			name: "happy_delete_no_notification_when_noop",
			setupFunc: func(cache *RecordCache) {
				value := ValueData{Pulse: &ValueDataDetail{OK: true, Kind: ValueString, ValueString: "value"}}
				cache.Store(NewServiceRecordGUID(MetricServiceName, "alpha", "svc-a"), &Record{Value: value})
			},
			checkFunc: func(t *testing.T, cache *RecordCache) {
				drainChannel(cache.Updates())
				cache.Delete("alpha", "svc-a")
				select {
				case <-cache.Updates():
					t.Fatalf("Got update notification, expected none when delete is noop")
				default:
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
			name: "happy_evict_notifies_updates_channel",
			setupFunc: func(cache *RecordCache) {
				value := ValueData{Pulse: &ValueDataDetail{OK: true, Kind: ValueString, ValueString: "v"}}
				cache.Store(NewServiceRecordGUID(MetricServiceName, "alpha", "svc-a"), &Record{Value: value})
			},
			checkFunc: func(t *testing.T, cache *RecordCache) {
				drainChannel(cache.Updates())
				cache.Evict("alpha", "svc-a")
				select {
				case <-cache.Updates():
				default:
					t.Fatalf("Got no update notification, expected one after evict")
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
			name: "happy_evict_no_notification_when_noop",
			setupFunc: func(cache *RecordCache) {
				value := ValueData{Pulse: &ValueDataDetail{OK: true, Kind: ValueString, ValueString: "v"}}
				cache.Store(NewServiceRecordGUID(MetricServiceName, "alpha", "svc-a"), &Record{Value: value})
				cache.Evict("alpha", "svc-a")
			},
			checkFunc: func(t *testing.T, cache *RecordCache) {
				drainChannel(cache.Updates())
				cache.Evict("alpha", "svc-a")
				select {
				case <-cache.Updates():
					t.Fatalf("Got update notification, expected none when evict is noop")
				default:
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

type mockListener struct {
	dirtyCount int
}

func (m *mockListener) MarkDirty() {
	m.dirtyCount++
}

func drainChannel(ch <-chan struct{}) {
	for {
		select {
		case <-ch:
		default:
			return
		}
	}
}
