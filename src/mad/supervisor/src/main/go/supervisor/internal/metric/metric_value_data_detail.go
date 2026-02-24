package metric

import (
	"encoding/json"
	"strconv"
	"strings"
)

type ValueKind uint8

const (
	ValueNone ValueKind = iota
	ValueNumber
	ValueString
	ValueBoolean
)

type ValueDataDetail struct {
	OK     bool
	Kind   ValueKind
	Number float64
	String string
}

func (d ValueDataDetail) IsZero() bool {
	return !d.OK && d.Kind == ValueNone && d.Number == 0 && d.String == ""
}

func (d ValueDataDetail) MarshalJSON() ([]byte, error) {
	if d.Kind == ValueNone {
		return []byte("null"), nil
	}
	type Alias struct {
		OK    bool        `json:"ok"`
		Value interface{} `json:"value,omitempty"`
	}
	var v interface{}
	switch d.Kind {
	case ValueNumber:
		v = d.Number
	case ValueBoolean:
		v = d.OK
	default:
		v = d.String
	}
	return json.Marshal(Alias{OK: d.OK, Value: v})
}

// noinspection GoMixedReceiverTypes
func (d *ValueDataDetail) UnmarshalJSON(data []byte) error {
	if len(data) == 0 || len(data) == 2 && data[0] == '{' && data[1] == '}' || string(data) == `""` || string(data) == "null" {
		*d = ValueDataDetail{}
		return nil
	}
	var aux struct {
		OK    bool            `json:"ok"`
		Value json.RawMessage `json:"value"`
	}
	if err := json.Unmarshal(data, &aux); err != nil {
		return err
	}
	d.OK = aux.OK
	v := strings.TrimSpace(string(aux.Value))
	if v == "" {
		d.Kind = ValueBoolean
		return nil
	}
	if num, err := strconv.ParseFloat(v, 64); err == nil {
		d.Kind = ValueNumber
		d.Number = num
		return nil
	}
	if strings.HasPrefix(v, `"`) && strings.HasSuffix(v, `"`) {
		d.Kind = ValueString
		d.String = strings.Trim(v, `"`)
		return nil
	}
	return nil
}
