package schema

import (
	"encoding/json"
	"fmt"
	"io"
	"sort"
	"strings"
	"sync"
)

type Kind string

const (
	KindFloat Kind = "float"
	KindInt   Kind = "int"
	KindBool  Kind = "bool"
	KindStr   Kind = "str"
)

type Role string

const (
	RoleState        Role = "state"
	RoleCommand      Role = "command"
	RoleAvailability Role = "availability"
)

type Dimension struct {
	Key         string `json:"key"`
	Description string `json:"description"`
	Subject     bool   `json:"subject"`
}

type Measure struct {
	Key         string `json:"key"`
	Kind        Kind   `json:"kind"`
	Unit        string `json:"unit"`
	Description string `json:"description"`
	Persist     bool   `json:"persist"`
	Period      string `json:"period,omitempty"`
}

type Relation struct {
	Path        string      `json:"path"`
	Description string      `json:"description"`
	Cadence     string      `json:"cadence"`
	Entities    []string    `json:"entities"`
	Dimensions  []Dimension `json:"dimensions"`
	Measures    []Measure   `json:"measures"`
}

type Member struct {
	Key     string   `json:"key,omitempty"`
	Kind    Kind     `json:"kind,omitempty"`
	Enum    []string `json:"enum,omitempty"`
	Members []Member `json:"members,omitempty"`
}

type Payload struct {
	Role  Role   `json:"role"`
	Match string `json:"match,omitempty"`
	Root  Member `json:"root"`
}

type DatabaseSchema interface {
	Relations() []Relation
}

type BrokerSchema interface {
	Payloads() []Payload
}

type Database []Relation

func (d Database) Relations() []Relation { return d }

type Broker []Payload

func (b Broker) Payloads() []Payload { return b }

type Document struct {
	Module   string           `json:"module"`
	Database *DatabaseSection `json:"database,omitempty"`
	Broker   *BrokerSection   `json:"broker,omitempty"`
}

type DatabaseSection struct {
	Relations []Relation `json:"relations"`
}

type BrokerSection struct {
	Payloads []Payload `json:"payloads"`
}

func Reflect(w io.Writer, module string, database DatabaseSchema, broker BrokerSchema) error {
	document := Document{Module: module}
	if database != nil {
		document.Database = &DatabaseSection{Relations: database.Relations()}
	}
	if broker != nil {
		document.Broker = &BrokerSection{Payloads: broker.Payloads()}
	}
	encoder := json.NewEncoder(w)
	encoder.SetIndent("", "  ")
	if err := encoder.Encode(document); err != nil {
		return err
	}
	return nil
}

func (d Database) WithCadence(cadence string) Database {
	if cadence == "" {
		return d
	}
	relations := make(Database, 0, len(d))
	for _, relation := range d {
		relation.Cadence = cadence
		relations = append(relations, relation)
	}
	return relations
}

func Registered() Database {
	registryMu.RLock()
	defer registryMu.RUnlock()
	paths := make([]string, 0, len(registry))
	for path := range registry {
		paths = append(paths, path)
	}
	sort.Strings(paths)
	relations := make(Database, 0, len(paths))
	for _, path := range paths {
		relations = append(relations, registry[path].Relation())
	}
	return relations
}

type Builder struct {
	relation Relation
	declared map[string]bool
}

func Declare(path, description, cadence string) *Builder {
	if !strings.Contains(path, "/") {
		panic(fmt.Sprintf("relation path must be [<plugin>/<scope>] [%s]", path))
	}
	builder := &Builder{
		relation: Relation{Path: path, Description: description, Cadence: cadence, Entities: []string{},
			Dimensions: []Dimension{}, Measures: []Measure{}},
		declared: map[string]bool{},
	}
	registryMu.Lock()
	defer registryMu.Unlock()
	if _, exists := registry[path]; exists {
		panic(fmt.Sprintf("duplicate relation declaration [%s]", path))
	}
	registry[path] = builder
	return builder
}

func (b *Builder) Entities(values ...string) *Builder {
	b.relation.Entities = append([]string{}, values...)
	return b
}

func (b *Builder) Relation() Relation { return b.relation }

func (b *Builder) Path() string { return b.relation.Path }

func (b *Builder) Plugin() string {
	return b.relation.Path[:strings.Index(b.relation.Path, "/")]
}

func (b *Builder) Scope() string {
	return b.relation.Path[strings.Index(b.relation.Path, "/")+1:]
}

func (b *Builder) Subject(key, description string) DimensionKey {
	return b.dimension(key, description, true)
}

func (b *Builder) Dimension(key, description string) DimensionKey {
	return b.dimension(key, description, false)
}

func (b *Builder) Float(key, unit, description string) FloatKey {
	return FloatKey{b.measure(key, KindFloat, unit, description)}
}

func (b *Builder) Int(key, unit, description string) IntKey {
	return IntKey{b.measure(key, KindInt, unit, description)}
}

func (b *Builder) Bool(key, description string) BoolKey {
	return BoolKey{b.measure(key, KindBool, "state", description)}
}

func (b *Builder) Point(values ...Value) Point {
	point := Point{
		builder:       b,
		dimensions:    make([]string, len(b.relation.Dimensions)),
		dimensionsSet: make([]bool, len(b.relation.Dimensions)),
		measures:      make([]Value, len(b.relation.Measures)),
		measuresSet:   make([]bool, len(b.relation.Measures)),
	}
	for _, value := range values {
		if value.owner != b {
			panic(fmt.Sprintf("key from relation [%s] used to build a point of relation [%s]", value.owner.relation.Path, b.relation.Path))
		}
		if value.dimension {
			point.dimensions[value.index] = value.text
			point.dimensionsSet[value.index] = true
			continue
		}
		point.measures[value.index] = value
		point.measuresSet[value.index] = true
	}
	return point
}

type DimensionKey struct{ key }

func (k DimensionKey) Of(value string) Value {
	return Value{owner: k.owner, index: k.index, dimension: true, kind: KindStr, text: value}
}

func (k DimensionKey) Read(p Point) (string, bool) {
	if p.builder != k.owner || !p.dimensionsSet[k.index] {
		return "", false
	}
	return p.dimensions[k.index], true
}

type FloatKey struct{ key }

func (k FloatKey) Transient() FloatKey {
	k.owner.transient(k.index)
	return k
}

func (k FloatKey) Of(value float64) Value {
	return Value{owner: k.owner, index: k.index, kind: KindFloat, number: value}
}

func (k FloatKey) Read(p Point) (float64, bool) {
	value, ok := k.read(p)
	if !ok {
		return 0, false
	}
	return value.number, true
}

type IntKey struct{ key }

func (k IntKey) Transient() IntKey {
	k.owner.transient(k.index)
	return k
}

func (k IntKey) Of(value int64) Value {
	return Value{owner: k.owner, index: k.index, kind: KindInt, integer: value}
}

func (k IntKey) Read(p Point) (int64, bool) {
	value, ok := k.read(p)
	if !ok {
		return 0, false
	}
	return value.integer, true
}

type BoolKey struct{ key }

func (k BoolKey) Transient() BoolKey {
	k.owner.transient(k.index)
	return k
}

func (k BoolKey) Of(value bool) Value {
	return Value{owner: k.owner, index: k.index, kind: KindBool, flag: value}
}

func (k BoolKey) Read(p Point) (bool, bool) {
	value, ok := k.read(p)
	if !ok {
		return false, false
	}
	return value.flag, true
}

type Value struct {
	owner     *Builder
	index     int
	dimension bool
	kind      Kind
	number    float64
	integer   int64
	flag      bool
	text      string
}

type Point struct {
	builder       *Builder
	dimensions    []string
	dimensionsSet []bool
	measures      []Value
	measuresSet   []bool
}

func (p Point) Relation() Relation { return p.builder.relation }

func (p Point) Path() string {
	if p.builder == nil {
		return ""
	}
	return p.builder.relation.Path
}

func (p Point) Empty() bool { return p.builder == nil }

type key struct {
	owner *Builder
	index int
}

func (k key) read(p Point) (Value, bool) {
	if p.builder != k.owner || !p.measuresSet[k.index] {
		return Value{}, false
	}
	return p.measures[k.index], true
}

func (b *Builder) dimension(name, description string, subject bool) DimensionKey {
	b.reserve(name)
	b.relation.Dimensions = append(b.relation.Dimensions, Dimension{Key: name, Description: description, Subject: subject})
	return DimensionKey{newKey(b, len(b.relation.Dimensions)-1)}
}

func (b *Builder) measure(name string, kind Kind, unit, description string) key {
	b.reserve(name)
	b.relation.Measures = append(b.relation.Measures, Measure{Key: name, Kind: kind, Unit: unit, Description: description, Persist: true})
	return newKey(b, len(b.relation.Measures)-1)
}

func (b *Builder) reserve(name string) {
	if name == "" {
		panic(fmt.Sprintf("empty key declared on relation [%s]", b.relation.Path))
	}
	if b.declared[name] {
		panic(fmt.Sprintf("duplicate key [%s] declared on relation [%s]", name, b.relation.Path))
	}
	b.declared[name] = true
}

func (b *Builder) transient(index int) {
	b.relation.Measures[index].Persist = false
}

func newKey(owner *Builder, index int) key {
	return key{owner: owner, index: index}
}

var (
	registryMu sync.RWMutex
	registry   = map[string]*Builder{}
)
