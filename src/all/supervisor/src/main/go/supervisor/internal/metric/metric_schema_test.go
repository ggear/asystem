package metric

import (
	"strings"
	"testing"

	"supervisor/internal/schema"
)

func TestMetric_SchemaMatchesPublishedFields(t *testing.T) {
	host := HostRelation()
	service := ServiceRelation()
	declared := map[string]map[string]bool{
		host.Path:    measureKeys(host),
		service.Path: measureKeys(service),
	}
	persisted := map[string]map[string]bool{
		host.Path:    persistedKeys(host),
		service.Path: persistedKeys(service),
	}
	for _, id := range GetIDs() {
		_, tags, err := buildFromID(id, "macmini-mad", serviceNameFor(id), "data")
		if err != nil {
			t.Fatalf("build %v: unexpected error %v", id, err)
		}
		field, published := tags["metric"]
		relation := relationPathFor(id)
		if !published {
			if !declared[relation][GetIDField(id)] {
				t.Errorf("%v: skipHist measure [%s] must still be declared, as persist=false", id, GetIDField(id))
			}
			if persisted[relation][GetIDField(id)] {
				t.Errorf("%v: measure [%s] is declared persisted but the topic builder publishes no field", id, GetIDField(id))
			}
			continue
		}
		if !persisted[relation][field] {
			t.Errorf("%v: topic builder publishes field [%s] but it is declared persist=false", id, field)
		}
		if field != GetIDField(id) {
			t.Errorf("%v: topic builder publishes field [%s] but GetIDField says [%s]", id, field, GetIDField(id))
		}
		if !declared[relation][field] {
			t.Errorf("%v: topic builder publishes field [%s] undeclared on relation [%s]", id, field, relation)
		}
		if !declared[relation][field+"_trend"] {
			t.Errorf("%v: field [%s] has no declared trend twin on relation [%s]", id, field, relation)
		}
	}
}

func TestMetric_SchemaPersistMirrorsSkipHist(t *testing.T) {
	for _, relation := range Relations(nil, nil, "1m") {
		for _, measure := range relation.Measures {
			if measure.Key == "" {
				t.Errorf("%s: declared a measure with an empty key", relation.Path)
			}
			if measure.Unit == "" {
				t.Errorf("%s: measure [%s] declares no unit", relation.Path, measure.Key)
			}
			if measure.Description == "" {
				t.Errorf("%s: measure [%s] declares no description", relation.Path, measure.Key)
			}
		}
	}
	for _, id := range GetIDs() {
		builder := metricBuildersByID[id]
		if builder.template == "" {
			continue
		}
		relation := HostRelation()
		if relationPathFor(id) == "supervisor/service" {
			relation = ServiceRelation()
		}
		for _, measure := range relation.Measures {
			if measure.Key != GetIDField(id) {
				continue
			}
			if measure.Persist == builder.skipDatabase {
				t.Errorf("%v: measure [%s] persist=%v but skipHist=%v, they must be opposites",
					id, measure.Key, measure.Persist, builder.skipDatabase)
			}
		}
	}
}

func TestMetric_Cadence(t *testing.T) {
	tests := []struct {
		name        string
		pollPeriod  string
		pulseFactor int
		expected    string
	}{
		{name: "serve_defaults", pollPeriod: DefaultPollPeriodForTest, pulseFactor: 2, expected: "6s"},
		{name: "whole_minutes", pollPeriod: "30s", pulseFactor: 2, expected: "1m"},
		{name: "whole_hours", pollPeriod: "30m", pulseFactor: 2, expected: "1h"},
		{name: "ten_seconds_not_truncated", pollPeriod: "5s", pulseFactor: 2, expected: "10s"},
		{name: "invalid_falls_back", pollPeriod: "banana", pulseFactor: 2, expected: "banana"},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			if got := Cadence(test.pollPeriod, test.pulseFactor); got != test.expected {
				t.Errorf("cadence: got %s want %s", got, test.expected)
			}
		})
	}
}

const DefaultPollPeriodForTest = "3s"

func measureKeys(relation schema.Relation) map[string]bool {
	keys := map[string]bool{}
	for _, measure := range relation.Measures {
		keys[measure.Key] = true
	}
	return keys
}

func persistedKeys(relation schema.Relation) map[string]bool {
	keys := map[string]bool{}
	for _, measure := range relation.Measures {
		if measure.Persist {
			keys[measure.Key] = true
		}
	}
	return keys
}

func relationPathFor(id ID) string {
	if strings.Contains(metricBuildersByID[id].template, "$SERVICE") {
		return "supervisor/service"
	}
	return "supervisor/host"
}

func serviceNameFor(id ID) string {
	if relationPathFor(id) == "supervisor/service" {
		return "plex"
	}
	return ServiceNameUnset
}
