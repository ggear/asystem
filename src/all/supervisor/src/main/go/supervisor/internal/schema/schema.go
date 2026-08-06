package schema

import (
	"bytes"
	"encoding/json"
	"io"
	"strings"
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
	Path        string            `json:"path"`
	Description string            `json:"description"`
	Cadence     string            `json:"cadence"`
	Filter      map[string]string `json:"filter,omitempty"`
	Entities    []string          `json:"entities"`
	Dimensions  []Dimension       `json:"dimensions"`
	Measures    []Measure         `json:"measures"`
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
	return encoder.Encode(document)
}

type Field struct {
	Text string
	Flag bool
}

func AppendLineProtocol(buf *bytes.Buffer, measurement string, relation Relation, tags [][2]string, fields map[string]Field, timestamp string) bool {
	rendered := make([]string, 0, len(relation.Measures))
	for _, measure := range relation.Measures {
		if !measure.Persist {
			continue
		}
		field, declared := fields[measure.Key]
		if !declared {
			continue
		}
		switch measure.Kind {
		case KindBool:
			if field.Flag {
				rendered = append(rendered, measure.Key+"=1i")
			} else {
				rendered = append(rendered, measure.Key+"=0i")
			}
		case KindInt:
			rendered = append(rendered, measure.Key+"="+field.Text+"i")
		case KindFloat:
			rendered = append(rendered, measure.Key+"="+field.Text)
		default:
		}
	}
	if len(rendered) == 0 {
		return false
	}
	buf.WriteString(measurement)
	for _, tag := range tags {
		if tag[1] == "" {
			continue
		}
		buf.WriteByte(',')
		buf.WriteString(tag[0])
		buf.WriteByte('=')
		buf.WriteString(tag[1])
	}
	buf.WriteByte(' ')
	buf.WriteString(strings.Join(rendered, ","))
	buf.WriteByte(' ')
	buf.WriteString(timestamp)
	buf.WriteByte('\n')
	return true
}
