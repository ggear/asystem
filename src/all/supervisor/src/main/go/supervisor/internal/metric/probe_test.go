package metric

import "testing"

func TestProbeStatusTagging(t *testing.T) {
	cache := NewRecordCache(nil, nil)
	host := NewRecord(*NewBoolValue(true, true))
	cache.Store(NewRecordGUID(MetricHost, "macmini-mad"), &host)
	service := NewRecord(*NewBoolValue(true, true))
	cache.Store(NewServiceRecordGUID(MetricService, "macmini-mad", "plex"), &service)
	memory := NewRecord(*NewIntValue(true, 42, true, 41))
	cache.Store(NewRecordGUID(MetricHostUsedMemory, "macmini-mad"), &memory)
	for _, guid := range cache.Take() {
		record, ok := cache.Load(guid)
		if !ok {
			t.Fatalf("guid %v: not loadable", guid)
		}
		t.Logf("id=%v service=%q topic=%q tags=%v pulse=%v", guid.ID, guid.ServiceName, record.Topic, record.Tags, record.Value.Pulse != nil)
	}
}
