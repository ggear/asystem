package metric

import (
	"encoding/json"
	"fmt"
	"math"
	"strconv"
	"strings"
	"time"
)

type ValueData struct {
	Timestamp int64            `json:"timestamp"`
	Pulse     *ValueDataDetail `json:"pulse,omitempty"`
	Trend     *ValueDataDetail `json:"trend,omitempty"`
}

type ValueKind int8

const (
	ValueNone ValueKind = iota
	ValueBool
	ValueFloat
	ValueInt
	ValueString
)

func (k ValueKind) String() string {
	switch k {
	case ValueBool:
		return "bool"
	case ValueFloat:
		return "float"
	case ValueInt:
		return "int"
	case ValueString:
		return "string"
	default:
		return "none"
	}
}

func ParseValueKind(value string) (ValueKind, bool) {
	switch strings.ToLower(strings.TrimSpace(value)) {
	case "bool":
		return ValueBool, true
	case "float":
		return ValueFloat, true
	case "int":
		return ValueInt, true
	case "string":
		return ValueString, true
	case "", "none":
		return ValueNone, true
	default:
		return ValueNone, false
	}
}

func (v *ValueData) Equal(that *ValueData) bool {
	if v == nil || that == nil {
		return v == that
	}
	return valueDataDetailEqual(v.Pulse, that.Pulse) && valueDataDetailEqual(v.Trend, that.Trend)
}

type ValueDataDetail struct {
	Kind        ValueKind
	OK          bool
	ValueInt    int8
	ValueFloat  float64
	ValueString string
}

func NewNilValue() ValueData {
	return ValueData{
		Timestamp: time.Now().Unix(),
	}
}

func NewBoolPulseValue(pulseOK bool) *ValueData {
	return &ValueData{
		Timestamp: time.Now().Unix(),
		Pulse:     &ValueDataDetail{OK: pulseOK, Kind: ValueBool, ValueFloat: 0, ValueString: ""},
		Trend:     nil,
	}
}

func NewBoolValue(pulseOK bool, trendOK bool) *ValueData {
	return &ValueData{
		Timestamp: time.Now().Unix(),
		Pulse:     &ValueDataDetail{OK: pulseOK, Kind: ValueBool, ValueFloat: 0, ValueString: ""},
		Trend:     &ValueDataDetail{OK: trendOK, Kind: ValueBool, ValueFloat: 0, ValueString: ""},
	}
}

func NewFloatPulseValue(pulseOK bool, pulseValue float64) *ValueData {
	return &ValueData{
		Timestamp: time.Now().Unix(),
		Pulse:     &ValueDataDetail{OK: pulseOK, Kind: ValueFloat, ValueFloat: pulseValue, ValueString: ""},
		Trend:     nil,
	}
}

func NewFloatValue(pulseOK bool, pulseValue float64, trendOK bool, trendValue float64) *ValueData {
	return &ValueData{
		Timestamp: time.Now().Unix(),
		Pulse:     &ValueDataDetail{OK: pulseOK, Kind: ValueFloat, ValueFloat: pulseValue, ValueString: ""},
		Trend:     &ValueDataDetail{OK: trendOK, Kind: ValueFloat, ValueFloat: trendValue, ValueString: ""},
	}
}

func NewStringPulseValue(pulseOK bool, pulseValue string) *ValueData {
	return &ValueData{
		Timestamp: time.Now().Unix(),
		Pulse:     &ValueDataDetail{OK: pulseOK, Kind: ValueString, ValueFloat: 0, ValueString: pulseValue},
		Trend:     nil,
	}
}

func NewIntPulseValue(pulseOK bool, pulseValue int8) *ValueData {
	return &ValueData{
		Timestamp: time.Now().Unix(),
		Pulse:     &ValueDataDetail{OK: pulseOK, Kind: ValueInt, ValueInt: pulseValue},
		Trend:     nil,
	}
}

func NewIntValue(pulseOK bool, pulseValue int8, trendOK bool, trendValue int8) *ValueData {
	return &ValueData{
		Timestamp: time.Now().Unix(),
		Pulse:     &ValueDataDetail{OK: pulseOK, Kind: ValueInt, ValueInt: pulseValue},
		Trend:     &ValueDataDetail{OK: trendOK, Kind: ValueInt, ValueInt: trendValue},
	}
}

func NewStringValue(pulseOK bool, pulseValue string, trendOK bool, trendValue string) *ValueData {
	return &ValueData{
		Timestamp: time.Now().Unix(),
		Pulse:     &ValueDataDetail{OK: pulseOK, Kind: ValueString, ValueFloat: 0, ValueString: pulseValue},
		Trend:     &ValueDataDetail{OK: trendOK, Kind: ValueString, ValueFloat: 0, ValueString: trendValue},
	}
}

func NewDataPulseValue(pulseOK bool, pulse any) (*ValueData, error) {
	switch p := pulse.(type) {
	case int8:
		return NewIntPulseValue(pulseOK, p), nil
	case float64:
		return NewFloatPulseValue(pulseOK, p), nil
	case string:
		return NewStringPulseValue(pulseOK, p), nil
	case bool:
		return NewBoolPulseValue(pulseOK), nil
	default:
		return nil, fmt.Errorf("unsupported metric pulse value type: %T", pulse)
	}
}

func NewDataValue(pulseOK bool, pulse any, trendOK bool, trend any) (*ValueData, error) {
	typeMismatch := func() error {
		return fmt.Errorf("metric value type mismatch: pulse %T trend %T", pulse, trend)
	}
	switch p := pulse.(type) {
	case int8:
		t, ok := trend.(int8)
		if !ok {
			return nil, typeMismatch()
		}
		return NewIntValue(pulseOK, p, trendOK, t), nil
	case float64:
		t, ok := trend.(float64)
		if !ok {
			return nil, typeMismatch()
		}
		return NewFloatValue(pulseOK, p, trendOK, t), nil
	case string:
		t, ok := trend.(string)
		if !ok {
			return nil, typeMismatch()
		}
		return NewStringValue(pulseOK, p, trendOK, t), nil
	case bool:
		if _, ok := trend.(bool); !ok {
			return nil, typeMismatch()
		}
		return NewBoolValue(pulseOK, trendOK), nil
	default:
		return nil, fmt.Errorf("unsupported metric value type: %T", pulse)
	}
}

func (d ValueDataDetail) IsZero() bool {
	return !d.OK && d.Kind == ValueNone && d.ValueFloat == 0 && d.ValueString == ""
}

func (d ValueDataDetail) Value() string {
	if d.IsZero() {
		return ""
	}
	switch d.Kind {
	case ValueBool:
		return ""
	case ValueFloat:
		truncated := math.Trunc(d.ValueFloat*10) / 10
		return strconv.FormatFloat(truncated, 'f', 1, 64)
	case ValueInt:
		return strconv.FormatInt(int64(d.ValueInt), 10)
	default:
		return d.ValueString
	}
}

func (d ValueDataDetail) String() string {
	if d.IsZero() {
		return ""
	}
	value := d.Value()
	okString := "✖"
	if d.OK {
		okString = "✔"
	}
	if value != "" {
		return "ok[" + okString + "] value[" + value + "]"
	}
	return "ok[" + okString + "]"
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
	case ValueFloat:
		v = d.ValueFloat
	case ValueInt:
		v = d.ValueInt
	case ValueBool:
		v = d.OK
	default:
		v = d.ValueString
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
		d.Kind = ValueBool
		return nil
	}
	if i, err := strconv.ParseInt(v, 10, 8); err == nil {
		d.Kind = ValueInt
		d.ValueInt = int8(i)
		return nil
	}
	if f, err := strconv.ParseFloat(v, 64); err == nil {
		d.Kind = ValueFloat
		d.ValueFloat = f
		return nil
	}
	if strings.HasPrefix(v, `"`) && strings.HasSuffix(v, `"`) {
		var s string
		if err := json.Unmarshal(aux.Value, &s); err != nil {
			return err
		}
		d.Kind = ValueString
		d.ValueString = s
		return nil
	}
	if v == "true" || v == "false" {
		d.Kind = ValueBool
		return nil
	}
	return nil
}

func valueDataDetailEqual(left, right *ValueDataDetail) bool {
	if left == nil || right == nil {
		return left == right
	}
	return left.Kind == right.Kind &&
		left.OK == right.OK &&
		left.ValueInt == right.ValueInt &&
		left.ValueFloat == right.ValueFloat &&
		left.ValueString == right.ValueString
}
