package schema

import (
	"bytes"
	"strconv"
)

func AppendLineProtocol(buf *bytes.Buffer, points []Point, timestamp int64) {
	timestampText := strconv.FormatInt(timestamp, 10)
	for _, point := range points {
		if point.Empty() || !hasPersistedValue(point) {
			continue
		}
		relation := point.builder.relation
		buf.WriteString(escapeTag(point.builder.Plugin()))
		for index, dimension := range relation.Dimensions {
			if !point.dimensionsSet[index] || point.dimensions[index] == "" {
				continue
			}
			buf.WriteByte(',')
			buf.WriteString(escapeTag(dimension.Key))
			buf.WriteByte('=')
			buf.WriteString(escapeTag(point.dimensions[index]))
		}
		buf.WriteByte(' ')
		first := true
		for index, measure := range relation.Measures {
			if !measure.Persist || !point.measuresSet[index] {
				continue
			}
			if !first {
				buf.WriteByte(',')
			}
			first = false
			buf.WriteString(escapeTag(measure.Key))
			buf.WriteByte('=')
			appendFieldValue(buf, point.measures[index])
		}
		buf.WriteByte(' ')
		buf.WriteString(timestampText)
		buf.WriteByte('\n')
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

func appendFieldValue(buf *bytes.Buffer, value Value) {
	switch value.kind {
	case KindFloat:
		buf.WriteString(strconv.FormatFloat(value.number, 'g', -1, 64))
	case KindInt:
		buf.WriteString(strconv.FormatInt(value.integer, 10))
		buf.WriteByte('i')
	case KindBool:
		if value.flag {
			buf.WriteString("1i")
		} else {
			buf.WriteString("0i")
		}
	default:
	}
}

func escapeTag(s string) string {
	if !needsTagEscape(s) {
		return s
	}
	var out bytes.Buffer
	for i := 0; i < len(s); i++ {
		c := s[i]
		if c == ' ' || c == ',' || c == '=' {
			out.WriteByte('\\')
		}
		out.WriteByte(c)
	}
	return out.String()
}

func needsTagEscape(s string) bool {
	for i := 0; i < len(s); i++ {
		c := s[i]
		if c == ' ' || c == ',' || c == '=' {
			return true
		}
	}
	return false
}
