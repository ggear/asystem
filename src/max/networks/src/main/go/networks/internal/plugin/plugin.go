package plugin

import (
	"bytes"
	"context"
	"fmt"
	"math"
	"sort"
	"strconv"
	"strings"
	"sync"
	"time"
)

type Status string

const (
	StatusFit  Status = "fit"
	StatusSick Status = "sick"
	StatusDead Status = "dead"
)

type Kind uint8

const (
	KindNull Kind = iota
	KindFloat
	KindInt
	KindBool
	KindStr
)

type Field struct {
	Key   string
	Kind  Kind
	Float float64
	Int   int64
	Bool  bool
	Str   string
}

func Float(key string, value float64) Field { return Field{Key: key, Kind: KindFloat, Float: value} }

func Int(key string, value int64) Field { return Field{Key: key, Kind: KindInt, Int: value} }

func Bool(key string, value bool) Field { return Field{Key: key, Kind: KindBool, Bool: value} }

func Str(key, value string) Field { return Field{Key: key, Kind: KindStr, Str: value} }

func Null(key string) Field { return Field{Key: key, Kind: KindNull} }

type Tag struct {
	Key   string
	Value string
}

type Point struct {
	Tags   []Tag
	Fields []Field
}

func NewPoint(tags []Tag, fields ...Field) Point { return Point{Tags: tags, Fields: fields} }

type Sample struct {
	Plugin    string
	Timestamp time.Time
	Points    []Point
}

type Aggregate struct {
	Plugin      string
	Timestamp   time.Time
	OK          bool
	Status      Status
	Score       int
	Detail      string
	Reason      string
	WindowS     int
	SampleCount int
	Points      []Point
}

type SampleMode uint8

const (
	Snapshot SampleMode = iota
	Windowed
)

type Plugin interface {
	Name() string
	SampleMode() SampleMode
	Poll(ctx context.Context) (Sample, error)
	Aggregate(samples []Sample) (Aggregate, error)
}

var (
	registryMu sync.RWMutex
	registry   = map[string]Plugin{}
)

func Register(p Plugin) {
	if p == nil {
		panic("nil plugin registration")
	}
	registryMu.Lock()
	defer registryMu.Unlock()
	name := p.Name()
	if _, exists := registry[name]; exists {
		panic(fmt.Sprintf("duplicate plugin registration [%s]", name))
	}
	registry[name] = p
}

func Registered() []Plugin {
	registryMu.RLock()
	defer registryMu.RUnlock()
	names := make([]string, 0, len(registry))
	for name := range registry {
		names = append(names, name)
	}
	sort.Strings(names)
	plugins := make([]Plugin, 0, len(names))
	for _, name := range names {
		plugins = append(plugins, registry[name])
	}
	return plugins
}

func Filter(names []string) ([]Plugin, error) {
	all := Registered()
	if len(names) == 0 {
		return all, nil
	}
	byName := map[string]Plugin{}
	for _, p := range all {
		byName[p.Name()] = p
	}
	seen := map[string]bool{}
	filtered := make([]Plugin, 0, len(names))
	for _, name := range names {
		name = strings.TrimSpace(name)
		if name == "" {
			continue
		}
		p, ok := byName[name]
		if !ok {
			return nil, fmt.Errorf("unknown plugin [%s]", name)
		}
		if seen[name] {
			continue
		}
		seen[name] = true
		filtered = append(filtered, p)
	}
	return filtered, nil
}

func Clamp(v int) int {
	if v < 0 {
		return 0
	}
	if v > 100 {
		return 100
	}
	return v
}

func Round(v float64, places int) float64 {
	factor := math.Pow(10, float64(places))
	return math.Round(v*factor) / factor
}

func Diagnose(status Status, score int, detail, reason string) Aggregate {
	return Aggregate{Status: status, OK: status != StatusDead, Score: score, Detail: detail, Reason: reason}
}

func LatestPoints(samples []Sample) []Point {
	if len(samples) == 0 {
		return nil
	}
	return samples[len(samples)-1].Points
}

func PrependSummaryPoints(summary Point, details []Point) []Point {
	points := make([]Point, 0, len(details)+1)
	points = append(points, summary)
	points = append(points, details...)
	return points
}

func (p Point) Bool(key string) (bool, bool) {
	for _, field := range p.Fields {
		if field.Key == key && field.Kind == KindBool {
			return field.Bool, true
		}
	}
	return false, false
}

func (p Point) Float(key string) (float64, bool) {
	for _, field := range p.Fields {
		if field.Key != key {
			continue
		}
		switch field.Kind {
		case KindFloat:
			return field.Float, true
		case KindInt:
			return float64(field.Int), true
		default:
			return 0, false
		}
	}
	return 0, false
}

func (p Point) Int(key string) (int64, bool) {
	for _, field := range p.Fields {
		if field.Key == key && field.Kind == KindInt {
			return field.Int, true
		}
	}
	return 0, false
}

func (p Point) Tag(key string) (string, bool) {
	for _, tag := range p.Tags {
		if tag.Key == key {
			return tag.Value, true
		}
	}
	return "", false
}

var bufferPool = sync.Pool{New: func() any { return new(bytes.Buffer) }}

func (a Aggregate) MarshalJSON() ([]byte, error) {
	buf := bufferPool.Get().(*bytes.Buffer)
	buf.Reset()
	defer bufferPool.Put(buf)
	buf.WriteString(`{"timestamp":`)
	buf.WriteString(strconv.FormatInt(a.Timestamp.Unix(), 10))
	buf.WriteString(`,"ok":`)
	buf.WriteString(strconv.FormatBool(a.OK))
	buf.WriteString(`,"status":"`)
	buf.WriteString(string(a.Status))
	buf.WriteString(`","score":`)
	buf.WriteString(strconv.Itoa(a.Score))
	buf.WriteByte('}')
	out := make([]byte, buf.Len())
	copy(out, buf.Bytes())
	return out, nil
}

func (a Aggregate) AppendLineProtocol(buf *bytes.Buffer, measurement string, timestamp int64) {
	timestampText := strconv.FormatInt(timestamp, 10)
	for _, point := range a.Points {
		if !hasNumericField(point.Fields) {
			continue
		}
		buf.WriteString(measurement)
		buf.WriteString(",plugin=")
		buf.WriteString(escapeTag(a.Plugin))
		for _, tag := range point.Tags {
			if tag.Value == "" {
				continue
			}
			buf.WriteByte(',')
			buf.WriteString(escapeTag(tag.Key))
			buf.WriteByte('=')
			buf.WriteString(escapeTag(tag.Value))
		}
		for _, field := range point.Fields {
			if field.Kind != KindStr || field.Str == "" {
				continue
			}
			buf.WriteByte(',')
			buf.WriteString(escapeTag(field.Key))
			buf.WriteByte('=')
			buf.WriteString(escapeTag(field.Str))
		}
		buf.WriteByte(' ')
		first := true
		for _, field := range point.Fields {
			if field.Kind != KindFloat && field.Kind != KindInt {
				continue
			}
			if !first {
				buf.WriteByte(',')
			}
			first = false
			buf.WriteString(escapeTag(field.Key))
			buf.WriteByte('=')
			appendFieldValue(buf, field)
		}
		buf.WriteByte(' ')
		buf.WriteString(timestampText)
		buf.WriteByte('\n')
	}
}

func hasNumericField(fields []Field) bool {
	for _, field := range fields {
		if field.Kind == KindFloat || field.Kind == KindInt {
			return true
		}
	}
	return false
}

func appendFieldValue(buf *bytes.Buffer, field Field) {
	switch field.Kind {
	case KindFloat:
		buf.WriteString(strconv.FormatFloat(field.Float, 'g', -1, 64))
	case KindInt:
		buf.WriteString(strconv.FormatInt(field.Int, 10))
		buf.WriteByte('i')
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
