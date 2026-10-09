package metric

import (
	"strings"
	"testing"

	"supervisor/internal/schema"
)

func TestMetricSchema_MatchesPublishedFields(t *testing.T) {
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

func TestMetricSchema_PersistMirrorsSkipHist(t *testing.T) {
	for _, relation := range Relations(nil, nil, "1m") {
		for _, measure := range relation.Measures {
			if measure.Key == "" {
				t.Errorf("%s: declared a measure with an empty key", relation.Path)
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
			if measure.Persist != builder.persisted {
				t.Errorf("%v: measure [%s] persist=%v but persisted=%v, they must agree",
					id, measure.Key, measure.Persist, builder.persisted)
			}
		}
	}
}

func TestMetricSchema_LevelsOf(t *testing.T) {
	limit, always := 90.0, 1.0
	tests := []struct {
		name     string
		rule     Rule
		red      bool
		flag     bool
		expected *schema.Levels
	}{
		{name: "at_most_pulse_is_inclusive_red", rule: Bounded(Self, AtMost, limit), red: true, expected: &schema.Levels{Better: schema.BetterLower, Red: &limit, Inclusive: true}},
		{name: "at_most_trend_is_inclusive_amber", rule: Bounded(Self, AtMost, limit), expected: &schema.Levels{Better: schema.BetterLower, Amber: &limit, Inclusive: true}},
		{name: "below_is_strict", rule: Bounded(Self, Below, limit), red: true, expected: &schema.Levels{Better: schema.BetterLower, Red: &limit}},
		{name: "at_least_is_higher_better", rule: Bounded(Self, AtLeast, limit), red: true, expected: &schema.Levels{Better: schema.BetterHigher, Red: &limit, Inclusive: true}},
		{name: "above_is_strict_higher_better", rule: Bounded(Self, Above, limit), red: true, expected: &schema.Levels{Better: schema.BetterHigher, Red: &limit}},
		{name: "exactly_exports_nothing", rule: Bounded(Self, Exactly, 0), red: true},
		{name: "a_sibling_bound_exports_nothing", rule: Bounded(MetricHostUsedMemory, AtMost, limit), red: true},
		{name: "a_sibling_verdict_leaves_its_bound", rule: All(Bounded(Self, AtMost, limit), Healthy(MetricHostFailedDrives)), red: true, expected: &schema.Levels{Better: schema.BetterLower, Red: &limit, Inclusive: true}},
		{name: "a_bool_of_sibling_verdicts_is_red_below_always_true", rule: All(Healthy(MetricHostUsedMemory), Healthy(MetricHostFailedDrives)), red: true, flag: true, expected: &schema.Levels{Better: schema.BetterHigher, Red: &always, Inclusive: true}},
		{name: "an_either_rule_exports_nothing", rule: Any(Healthy(MetricHostWarnTemperature), Against(MetricHostWarnTemperature, AtLeast)), red: true},
		{name: "two_own_bounds_export_nothing", rule: All(Bounded(Self, AtMost, limit), Bounded(Self, AtLeast, 0)), red: true},
		{name: "truthy_pulse_is_red_below_always_true", rule: Truthy(), red: true, expected: &schema.Levels{Better: schema.BetterHigher, Red: &always, Inclusive: true}},
		{name: "truthy_trend_is_amber_below_always_true", rule: Truthy(), expected: &schema.Levels{Better: schema.BetterHigher, Amber: &always, Inclusive: true}},
		{name: "a_gated_bool_is_red_below_always_true", rule: Gated(GateServiceAggregate), red: true, flag: true, expected: &schema.Levels{Better: schema.BetterHigher, Red: &always, Inclusive: true}},
		{name: "a_gated_value_exports_nothing", rule: Gated(GateServiceAggregate), red: true},
		{name: "a_gate_leaves_its_bound", rule: All(Gated(GateServiceAggregate), Bounded(Self, AtMost, limit)), red: true, expected: &schema.Levels{Better: schema.BetterLower, Red: &limit, Inclusive: true}},
		{name: "an_unjudged_bool_exports_nothing", rule: Rule{}, red: true, flag: true},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			got := levelsOf(test.rule, test.red, test.flag)
			if (got == nil) != (test.expected == nil) {
				t.Fatalf("levels: got %+v want %+v", got, test.expected)
			}
			if got == nil {
				return
			}
			if got.Better != test.expected.Better || got.Inclusive != test.expected.Inclusive ||
				(got.Red == nil) != (test.expected.Red == nil) || (got.Amber == nil) != (test.expected.Amber == nil) {
				t.Errorf("levels: got %+v want %+v", got, test.expected)
			}
			if bound := got.Red; bound != nil && *bound != *test.expected.Red {
				t.Errorf("red: got %v want %v", *bound, *test.expected.Red)
			}
			if bound := got.Amber; bound != nil && *bound != *test.expected.Amber {
				t.Errorf("amber: got %v want %v", *bound, *test.expected.Amber)
			}
		})
	}
}

func TestMetricSchema_Cadence(t *testing.T) {
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

func TestMetricSchema_Topics(t *testing.T) {
	topics := Topics()
	if len(topics) == 0 {
		t.Fatalf("topics: got none want one per templated metric")
	}
	seen := map[string]bool{}
	for _, topic := range topics {
		expectedRole := map[string]schema.Role{TopicAllStatus: schema.RoleAvailability, TopicAllCommand: schema.RoleCommand}[topic.Template]
		if expectedRole == "" {
			expectedRole = schema.RoleState
		}
		if topic.Role != expectedRole {
			t.Errorf("role: got %v want %v for %s", topic.Role, expectedRole, topic.Template)
		}
		if strings.Contains(topic.Template, "$SCOPE") {
			t.Errorf("template: got %s want $SCOPE resolved to %s", topic.Template, ScopeData)
		}
		if seen[topic.Template] {
			t.Errorf("template: got duplicate %s want each declared once", topic.Template)
		}
		seen[topic.Template] = true
	}
	for _, id := range GetIDs() {
		template := metricBuildersByID[id].template
		if template == "" {
			continue
		}
		declared := strings.ReplaceAll(template, "$SCOPE", ScopeData)
		if GetIDKind(id) == MetricKindCluster {
			declared = strings.ReplaceAll(declared, "$HOST", HostAll)
		}
		if !seen[declared] {
			t.Errorf("template: got none want one declared for %s", template)
		}
	}
}
