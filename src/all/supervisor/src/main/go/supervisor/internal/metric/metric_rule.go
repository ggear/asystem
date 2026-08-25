package metric

import (
	"fmt"
	"strings"
)

type Comparator uint8

const (
	AtMost Comparator = iota
	AtLeast
	Above
	Exactly
)

func (c Comparator) String() string {
	switch c {
	case AtMost:
		return "<="
	case AtLeast:
		return ">="
	case Above:
		return ">"
	case Exactly:
		return "=="
	default:
		return "?"
	}
}

func (c Comparator) satisfies(value, limit float64) bool {
	switch c {
	case AtMost:
		return value <= limit
	case AtLeast:
		return value >= limit
	case Above:
		return value > limit
	case Exactly:
		return value == limit
	default:
		return false
	}
}

type GateID uint8

const (
	GateDrivesHealthy GateID = iota
	GateServiceAggregate
	GateServiceHealthy
	GateServiceConfigured
	GateFansAbsent
)

func (g GateID) String() string {
	switch g {
	case GateDrivesHealthy:
		return "drives healthy"
	case GateServiceAggregate:
		return "service aggregate"
	case GateServiceHealthy:
		return "service healthy"
	case GateServiceConfigured:
		return "service configured"
	case GateFansAbsent:
		return "fans absent"
	default:
		return "?"
	}
}

const Self ID = -1

type ruleKind uint8

const (
	ruleUnset ruleKind = iota
	ruleAlways
	ruleBounded
	ruleGated
	ruleAll
	ruleAny
)

type Rule struct {
	kind       ruleKind
	target     ID
	comparator Comparator
	limit      float64
	gate       GateID
	children   []Rule
}

func Always() Rule { return Rule{kind: ruleAlways} }

func Bounded(target ID, compare Comparator, limit float64) Rule {
	return Rule{kind: ruleBounded, target: target, comparator: compare, limit: limit}
}

func Gated(gate GateID) Rule { return Rule{kind: ruleGated, gate: gate} }

func All(rules ...Rule) Rule { return Rule{kind: ruleAll, children: rules} }

func Any(rules ...Rule) Rule { return Rule{kind: ruleAny, children: rules} }

func (r Rule) IsZero() bool { return r.kind == ruleUnset }

func (r Rule) Targets() []ID {
	var targets []ID
	r.walk(func(term Rule) {
		if term.kind == ruleBounded {
			targets = append(targets, term.target)
		}
	})
	return targets
}

func (r Rule) Gates() []GateID {
	var gates []GateID
	r.walk(func(term Rule) {
		if term.kind == ruleGated {
			gates = append(gates, term.gate)
		}
	})
	return gates
}

type ValueResolver func(id ID) (float64, bool)

type GateResolver func(gate GateID) (bool, bool)

type RuleResult struct {
	OK     bool
	Detail string
}

func (r Rule) Evaluate(unit string, self float64, selfNumeric bool, values ValueResolver, gates GateResolver) RuleResult {
	switch r.kind {
	case ruleAlways:
		return RuleResult{OK: true, Detail: "always ok"}
	case ruleBounded:
		return r.evaluateBounded(unit, self, selfNumeric, values)
	case ruleGated:
		value, bound := gates(r.gate)
		if !bound {
			return RuleResult{OK: false, Detail: fmt.Sprintf("gate [%s] is unbound", r.gate)}
		}
		return RuleResult{OK: value, Detail: fmt.Sprintf("gate [%s] is [%v]", r.gate, value)}
	case ruleAll, ruleAny:
		return r.combine(unit, self, selfNumeric, values, gates)
	default:
		return RuleResult{OK: false, Detail: "no rule declared"}
	}
}

func (r Rule) walk(visit func(Rule)) {
	visit(r)
	for _, child := range r.children {
		child.walk(visit)
	}
}

func (r Rule) evaluateBounded(unit string, self float64, selfNumeric bool, values ValueResolver) RuleResult {
	value, ok, label := self, selfNumeric, "value"
	if r.target != Self {
		label = GetIDName(r.target)
		value, ok = values(r.target)
	}
	satisfied := ok && r.comparator.satisfies(value, r.limit)
	word := "within"
	if !satisfied {
		word = "not within"
	}
	return RuleResult{OK: satisfied, Detail: fmt.Sprintf("%s [%v] %s %s [%s%v] %s", label, value, unit, word, r.comparator, r.limit, unit)}
}

func (r Rule) combine(unit string, self float64, selfNumeric bool, values ValueResolver, gates GateResolver) RuleResult {
	conjunction := r.kind == ruleAll
	ok := conjunction
	details := make([]string, 0, len(r.children))
	for _, child := range r.children {
		result := child.Evaluate(unit, self, selfNumeric, values, gates)
		details = append(details, result.Detail)
		if conjunction {
			ok = ok && result.OK
		} else {
			ok = ok || result.OK
		}
	}
	return RuleResult{OK: ok, Detail: strings.Join(details, ", ")}
}
