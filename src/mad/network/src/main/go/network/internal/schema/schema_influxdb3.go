package schema

import (
	"bytes"
	"strconv"
)

func AppendLineProtocol(buffer *bytes.Buffer, points []Point, timestamp int64) {
	timestampText := strconv.FormatInt(timestamp, 10)
	for _, point := range points {
		if point.Empty() || !hasPersistedValue(point) {
			continue
		}
		relation := point.builder.relation
		buffer.WriteString(escapeTag(point.builder.Plugin()))
		if module := Module(); module != "" {
			buffer.WriteByte(',')
			buffer.WriteString(TagModule)
			buffer.WriteByte('=')
			buffer.WriteString(escapeTag(module))
		}
		for index, dimension := range relation.Dimensions {
			if !point.dimensionsSet[index] || point.dimensions[index] == "" {
				continue
			}
			buffer.WriteByte(',')
			buffer.WriteString(escapeTag(dimension.Key))
			buffer.WriteByte('=')
			buffer.WriteString(escapeTag(point.dimensions[index]))
		}
		buffer.WriteByte(' ')
		first := true
		for index, measure := range relation.Measures {
			if !measure.Persist || !point.measuresSet[index] {
				continue
			}
			if !first {
				buffer.WriteByte(',')
			}
			first = false
			buffer.WriteString(escapeTag(measure.Key))
			buffer.WriteByte('=')
			appendFieldValue(buffer, point.measures[index])
		}
		buffer.WriteByte(' ')
		buffer.WriteString(timestampText)
		buffer.WriteByte('\n')
	}
}

func hasPersistedValue(point Point) bool {
	for index, measure := range point.builder.relation.Measures {
		if measure.Persist && point.measuresSet[index] {
			return true
		}
	}
	return false
}

func appendFieldValue(buffer *bytes.Buffer, value Value) {
	switch value.kind {
	case KindFloat:
		buffer.WriteString(strconv.FormatFloat(value.number, 'g', -1, 64))
	case KindInt:
		buffer.WriteString(strconv.FormatInt(value.integer, 10))
		buffer.WriteByte('i')
	case KindBool:
		if value.flag {
			buffer.WriteString("1i")
		} else {
			buffer.WriteString("0i")
		}
	default:
	}
}

func escapeTag(text string) string {
	if !needsTagEscape(text) {
		return text
	}
	var out bytes.Buffer
	for i := 0; i < len(text); i++ {
		c := text[i]
		if c == ' ' || c == ',' || c == '=' {
			out.WriteByte('\\')
		}
		out.WriteByte(c)
	}
	return out.String()
}

func needsTagEscape(text string) bool {
	for i := 0; i < len(text); i++ {
		c := text[i]
		if c == ' ' || c == ',' || c == '=' {
			return true
		}
	}
	return false
}
