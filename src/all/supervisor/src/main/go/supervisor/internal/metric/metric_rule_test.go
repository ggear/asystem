package metric

import (
	"strings"
	"testing"
)

func TestRule_Evaluate(t *testing.T) {
	values := map[ID]float64{MetricHostWarnTemperature: 70}
	resolve := func(id ID) (float64, bool) {
		value, found := values[id]
		return value, found
	}
	gates := func(gate GateID) (bool, bool) {
		switch gate {
		case GateDrivesHealthy:
			return true, true
		case GateFansAbsent:
			return false, true
		default:
			return false, false
		}
	}
	tests := []struct {
		name            string
		rule            Rule
		self            float64
		selfNumeric     bool
		expectedOK      bool
		expectedDetails []string
	}{
		{
			name: "always is ok whatever the value", rule: Always(), self: 999, selfNumeric: true,
			expectedOK: true, expectedDetails: []string{"always ok"},
		},
		{
			name: "at most within the limit", rule: Bounded(Self, AtMost, 90), self: 12, selfNumeric: true,
			expectedOK: true, expectedDetails: []string{"value [12]", "within", "[<=90]"},
		},
		{
			name: "at most beyond the limit", rule: Bounded(Self, AtMost, 90), self: 91, selfNumeric: true,
			expectedOK: false, expectedDetails: []string{"value [91]", "not within", "[<=90]"},
		},
		{
			name: "at least within the limit", rule: Bounded(Self, AtLeast, 10), self: 10, selfNumeric: true,
			expectedOK: true, expectedDetails: []string{"value [10]", "within", "[>=10]"},
		},
		{
			name: "at least beyond the limit", rule: Bounded(Self, AtLeast, 10), self: 9, selfNumeric: true,
			expectedOK: false, expectedDetails: []string{"value [9]", "not within", "[>=10]"},
		},
		{
			name: "above excludes the limit", rule: Bounded(Self, Above, 50), self: 50, selfNumeric: true,
			expectedOK: false, expectedDetails: []string{"[>50]"},
		},
		{
			name: "exactly matches the limit", rule: Bounded(Self, Exactly, 0), self: 0, selfNumeric: true,
			expectedOK: true, expectedDetails: []string{"[==0]"},
		},
		{
			name: "a non numeric value can satisfy no bound", rule: Bounded(Self, AtMost, 90), self: 0, selfNumeric: false,
			expectedOK: false, expectedDetails: []string{"not within"},
		},
		{
			name: "a bound reads another metric by name", rule: Bounded(MetricHostWarnTemperature, AtMost, 65), self: 0, selfNumeric: true,
			expectedOK: false, expectedDetails: []string{"host/warn_temperature [70]", "not within"},
		},
		{
			name: "an unreadable sibling fails the bound", rule: Bounded(MetricHostUsedMemory, AtMost, 90), self: 0, selfNumeric: true,
			expectedOK: false, expectedDetails: []string{"host/used_memory", "not within"},
		},
		{
			name: "a bound gate reports its value", rule: Gated(GateDrivesHealthy), self: 0, selfNumeric: true,
			expectedOK: true, expectedDetails: []string{"gate [drives healthy] is [true]"},
		},
		{
			name: "an unbound gate is not ok", rule: Gated(GateServiceHealthy), self: 0, selfNumeric: true,
			expectedOK: false, expectedDetails: []string{"gate [service healthy] is unbound"},
		},
		{
			name: "all requires every term", rule: All(Bounded(Self, AtMost, 90), Gated(GateDrivesHealthy)), self: 12, selfNumeric: true,
			expectedOK: true, expectedDetails: []string{"value [12]", "gate [drives healthy] is [true]"},
		},
		{
			name: "all fails on one term", rule: All(Bounded(Self, AtMost, 90), Gated(GateFansAbsent)), self: 12, selfNumeric: true,
			expectedOK: false, expectedDetails: []string{"value [12]", "gate [fans absent] is [false]"},
		},
		{
			name: "any passes on one term", rule: Any(Gated(GateFansAbsent), Bounded(Self, Above, 80)), self: 90, selfNumeric: true,
			expectedOK: true, expectedDetails: []string{"gate [fans absent] is [false]", "value [90]"},
		},
		{
			name: "any fails when no term passes", rule: Any(Gated(GateFansAbsent), Bounded(Self, Above, 80)), self: 10, selfNumeric: true,
			expectedOK: false, expectedDetails: []string{"gate [fans absent] is [false]", "not within"},
		},
		{
			name: "an undeclared rule is never ok", rule: Rule{}, self: 0, selfNumeric: true,
			expectedOK: false, expectedDetails: []string{"no rule declared"},
		},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			result := test.rule.Evaluate("pct", test.self, test.selfNumeric, resolve, gates)
			if result.OK != test.expectedOK {
				t.Errorf("ok: got %v want %v, detail %q", result.OK, test.expectedOK, result.Detail)
			}
			for _, fragment := range test.expectedDetails {
				if !strings.Contains(result.Detail, fragment) {
					t.Errorf("detail: got %q want it to contain %q", result.Detail, fragment)
				}
			}
		})
	}
}

func TestRule_TargetsAndGates(t *testing.T) {
	rule := Any(Gated(GateFansAbsent), Bounded(MetricHostWarnTemperature, AtMost, 65), Bounded(Self, Above, 80))
	targets := rule.Targets()
	if len(targets) != 2 || targets[0] != MetricHostWarnTemperature || targets[1] != Self {
		t.Errorf("targets: got %v want [%v %v]", targets, MetricHostWarnTemperature, Self)
	}
	gates := rule.Gates()
	if len(gates) != 1 || gates[0] != GateFansAbsent {
		t.Errorf("gates: got %v want [%v]", gates, GateFansAbsent)
	}
	if !(Rule{}).IsZero() || Always().IsZero() {
		t.Errorf("isZero: got %v %v want true false", (Rule{}).IsZero(), Always().IsZero())
	}
}

func TestRule_DeclaredByEveryMetric(t *testing.T) {
	for _, id := range GetIDs() {
		builder := metricBuildersByID[id]
		if GetIDPulseRule(id).IsZero() {
			t.Errorf("%v: declares no pulseRule", GetIDName(id))
		}
		declared := map[ID]bool{}
		for _, dep := range builder.dependencies {
			declared[dep] = true
		}
		for _, rule := range []Rule{GetIDPulseRule(id), GetIDTrendRule(id)} {
			for _, target := range rule.Targets() {
				if target == Self {
					continue
				}
				if !declared[target] {
					t.Errorf("%v: rule reads %v which is absent from dependencies", GetIDName(id), GetIDName(target))
				}
			}
		}
	}
}
