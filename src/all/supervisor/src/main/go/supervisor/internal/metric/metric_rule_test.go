package metric

import (
	"strings"
	"testing"
	"unicode/utf8"
)

func TestMetricRule_Evaluate(t *testing.T) {
	values := map[ID]float64{MetricHostWarnTemperature: 70}
	resolve := func(id ID) (float64, bool) {
		value, found := values[id]
		return value, found
	}
	gates := func(gate GateID) (bool, bool) {
		switch gate {
		case GateServiceAggregate:
			return true, true
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
			expectedOK: true, expectedDetails: []string{"within [<=90] pct"},
		},
		{
			name: "at most beyond the limit", rule: Bounded(Self, AtMost, 90), self: 91, selfNumeric: true,
			expectedOK: false, expectedDetails: []string{"not within [<=90] pct"},
		},
		{
			name: "at least within the limit", rule: Bounded(Self, AtLeast, 10), self: 10, selfNumeric: true,
			expectedOK: true, expectedDetails: []string{"within [>=10] pct"},
		},
		{
			name: "at least beyond the limit", rule: Bounded(Self, AtLeast, 10), self: 9, selfNumeric: true,
			expectedOK: false, expectedDetails: []string{"not within [>=10] pct"},
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
			expectedOK: false, expectedDetails: []string{"host/warn_temperature [70] pct not within [<=65] pct"},
		},
		{
			name: "an unreadable sibling fails the bound", rule: Bounded(MetricHostUsedMemory, AtMost, 90), self: 0, selfNumeric: true,
			expectedOK: false, expectedDetails: []string{"host/used_memory", "not within"},
		},
		{
			name: "a bound gate reports its value", rule: Gated(GateServiceAggregate), self: 0, selfNumeric: true,
			expectedOK: true, expectedDetails: []string{"gate [service aggregate] is [true]"},
		},
		{
			name: "an unbound gate is not ok", rule: Gated(GateID(99)), self: 0, selfNumeric: true,
			expectedOK: false, expectedDetails: []string{"is unbound"},
		},
		{
			name: "all requires every term", rule: All(Bounded(Self, AtMost, 90), Gated(GateServiceAggregate)), self: 12, selfNumeric: true,
			expectedOK: true, expectedDetails: []string{"within [<=90] pct and gate [service aggregate] is [true]"},
		},
		{
			name: "all fails on one term", rule: All(Bounded(Self, AtMost, 90), Gated(GateID(99))), self: 12, selfNumeric: true,
			expectedOK: false, expectedDetails: []string{"within [<=90] pct and gate [-] is unbound"},
		},
		{
			name: "any passes on one term", rule: Any(Gated(GateID(99)), Bounded(Self, Above, 80)), self: 90, selfNumeric: true,
			expectedOK: true, expectedDetails: []string{"is unbound or within [>80] pct"},
		},
		{
			name: "any fails when no term passes", rule: Any(Gated(GateID(99)), Bounded(Self, Above, 80)), self: 10, selfNumeric: true,
			expectedOK: false, expectedDetails: []string{"is unbound or not within [>80] pct"},
		},
		{
			name: "truthy is ok on a true value", rule: Truthy(), self: 1, selfNumeric: true,
			expectedOK: true, expectedDetails: []string{"value is [true]"},
		},
		{
			name: "truthy is not ok on a false value", rule: Truthy(), self: 0, selfNumeric: true,
			expectedOK: false, expectedDetails: []string{"value is [false]"},
		},
		{
			name: "healthy follows a readable sibling", rule: Healthy(MetricHostWarnTemperature), self: 0, selfNumeric: true,
			expectedOK: true, expectedDetails: []string{"host/warn_temperature is [true]"},
		},
		{
			name: "healthy fails an unreadable sibling", rule: Healthy(MetricHostUsedMemory), self: 0, selfNumeric: true,
			expectedOK: false, expectedDetails: []string{"host/used_memory is [false]"},
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

func TestMetricRule_TargetsAndGates(t *testing.T) {
	rule := Any(Gated(GateServiceAggregate), Bounded(MetricHostWarnTemperature, AtMost, 65), Bounded(Self, Above, 80))
	if siblings := rule.Siblings(); len(siblings) != 1 || siblings[0] != MetricHostWarnTemperature {
		t.Errorf("siblings: got %v want [%v]", siblings, MetricHostWarnTemperature)
	}
	if siblings := Healthy(MetricHostUsedMemory).Siblings(); len(siblings) != 1 || siblings[0] != MetricHostUsedMemory {
		t.Errorf("healthy siblings: got %v want [%v]", siblings, MetricHostUsedMemory)
	}
	targets := rule.Targets()
	if len(targets) != 2 || targets[0] != MetricHostWarnTemperature || targets[1] != Self {
		t.Errorf("targets: got %v want [%v %v]", targets, MetricHostWarnTemperature, Self)
	}
	gates := rule.Gates()
	if len(gates) != 1 || gates[0] != GateServiceAggregate {
		t.Errorf("gates: got %v want [%v]", gates, GateServiceAggregate)
	}
	if !(Rule{}).IsZero() || Always().IsZero() {
		t.Errorf("isZero: got %v %v want true false", (Rule{}).IsZero(), Always().IsZero())
	}
}

func TestMetricRule_DeclaredByEveryMetric(t *testing.T) {
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

func TestMetricRule_UnitLabel(t *testing.T) {
	tests := []struct {
		unit     string
		expected string
	}{
		{unit: "", expected: ""},
		{unit: "%", expected: "pct"},
		{unit: "°C", expected: "degC"},
		{unit: "°F", expected: "degF"},
		{unit: "℃", expected: "degC"},
		{unit: "MiB", expected: "MiB"},
		{unit: "Mbit/s", expected: "Mbit/s"},
		{unit: "µs", expected: "us"},
		{unit: "Ω", expected: "ohm"},
		{unit: "m²", expected: "m2"},
		{unit: "µΩ·m", expected: "uohm.m"},
		{unit: "°é", expected: "dege"},
	}
	for _, test := range tests {
		t.Run(test.unit, func(t *testing.T) {
			if label := unitLabel(test.unit); label != test.expected {
				t.Errorf("label: got %q want %q", label, test.expected)
			}
		})
	}
}

func TestMetricRule_UnitLabelIsAsciiForEveryMetric(t *testing.T) {
	for _, id := range GetIDs() {
		unit := GetIDUnit(id)
		label := unitLabel(unit)
		if unit != "" && label == "" {
			t.Errorf("%v label: got %q want a spelling of unit %q", GetIDName(id), label, unit)
		}
		if strings.IndexFunc(label, func(glyph rune) bool { return glyph >= utf8.RuneSelf || glyph == '%' }) >= 0 {
			t.Errorf("%v label: got %q want ascii with no percent, from unit %q", GetIDName(id), label, unit)
		}
	}
}
