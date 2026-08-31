package metric

import (
	"strings"

	"supervisor/internal/schema"
)

func GetIDs() []ID {
	ids := make([]ID, MetricMax)
	for id := range MetricMax {
		ids[id] = id
	}
	return ids
}

func GetIDDeps(id ID) []ID {
	if id < 0 || id >= MetricMax {
		return nil
	}
	return metricBuildersByID[id].dependencies
}

func GetIDName(id ID) string {
	if id < 0 || id >= MetricMax {
		return ""
	}
	name := metricBuildersByID[id].template
	if _, suffix, found := strings.Cut(name, "$SCOPE/"); found {
		name = suffix
	}
	return strings.TrimSuffix(strings.ReplaceAll(name, "$SERVICE/", ""), "/$SERVICE")
}

func GetIDField(id ID) string {
	if id < 0 || id >= MetricMax {
		return ""
	}
	tokens := strings.Split(metricBuildersByID[id].template, "/")
	field := tokens[len(tokens)-1]
	switch field {
	case "host", "service", "$SERVICE":
		return "status"
	default:
		return field
	}
}

func GetIDKind(id ID) MetricKind {
	if id < 0 || id >= MetricMax {
		return MetricKindUnset
	}
	return metricBuildersByID[id].metricKind
}

func GetIDValueKind(id ID) ValueKind {
	if id < 0 || id >= MetricMax {
		return ValueNone
	}
	return metricBuildersByID[id].valueKind
}

func GetIDKindSchema(id ID) schema.Kind {
	switch GetIDValueKind(id) {
	case ValueBool:
		return schema.KindBool
	case ValueFloat:
		return schema.KindFloat
	case ValueInt:
		return schema.KindInt
	default:
		return schema.KindStr
	}
}

func GetIDUnit(id ID) string {
	if id < 0 || id >= MetricMax {
		return ""
	}
	return metricBuildersByID[id].unit
}

func GetIDWarming(id ID) bool {
	if id < 0 || id >= MetricMax {
		return false
	}
	return metricBuildersByID[id].warming
}

func GetIDPulseRule(id ID) Rule {
	if id < 0 || id >= MetricMax {
		return Rule{}
	}
	return metricBuildersByID[id].pulseRule
}

func GetIDTrendRule(id ID) Rule {
	if id < 0 || id >= MetricMax {
		return Rule{}
	}
	return metricBuildersByID[id].trendRule
}

func GetIDsByKind(types []MetricKind) []ID {
	if len(types) == 0 {
		return nil
	}
	allowed := make(map[MetricKind]bool, len(types))
	for _, t := range types {
		if t == MetricKindUnset {
			continue
		}
		allowed[t] = true
	}
	if len(allowed) == 0 {
		return nil
	}
	ids := make([]ID, 0, MetricMax)
	for _, builder := range metricBuildersByID {
		if allowed[builder.metricKind] {
			ids = append(ids, builder.id)
		}
	}
	return ids
}
