package metric

import (
	"encoding/json"
	"reflect"
	"testing"
)

func TestValueData_UnmarshalJSON(t *testing.T) {
	tests := []struct {
		name          string
		json          string
		pulseKind     ValueKind
		trendKind     ValueKind
		pulseOK       bool
		trendOK       bool
		expectedTime  int64
		expectedPulse bool
		expectedTrend bool
		expectedError bool
	}{
		{
			name:          "happy_percentage",
			json:          `{"timestamp":1771744503,"pulse":{"ok":true,"value":20},"trend":{"ok":false,"value":91}}`,
			pulseKind:     ValueInt,
			trendKind:     ValueInt,
			pulseOK:       true,
			trendOK:       false,
			expectedTime:  1771744503,
			expectedPulse: true,
			expectedTrend: true,
			expectedError: false,
		},
		{
			name:          "happy_string_values",
			json:          `{"timestamp":42,"pulse":{"ok":true,"value":"hot"},"trend":{"ok":true,"value":"cold"}}`,
			pulseKind:     ValueString,
			trendKind:     ValueString,
			pulseOK:       true,
			trendOK:       true,
			expectedTime:  42,
			expectedPulse: true,
			expectedTrend: true,
			expectedError: false,
		},
		{
			name:          "happy_missing_pulse",
			json:          `{"timestamp":7,"trend":{"ok":true,"value":1}}`,
			pulseKind:     ValueNone,
			trendKind:     ValueInt,
			pulseOK:       false,
			trendOK:       true,
			expectedTime:  7,
			expectedPulse: false,
			expectedTrend: true,
			expectedError: false,
		},
		{
			name:          "happy_bool_values",
			json:          `{"timestamp":9,"pulse":{"ok":true},"trend":{"ok":false}}`,
			pulseKind:     ValueBool,
			trendKind:     ValueBool,
			pulseOK:       true,
			trendOK:       false,
			expectedTime:  9,
			expectedPulse: true,
			expectedTrend: true,
			expectedError: false,
		},
		{
			name:          "happy_null_pulse_trend",
			json:          `{"timestamp":11,"pulse":null,"trend":null}`,
			pulseKind:     ValueNone,
			trendKind:     ValueNone,
			expectedTime:  11,
			expectedPulse: false,
			expectedTrend: false,
			expectedError: false,
		},
		{
			name:          "happy_empty_object_input",
			json:          `{}`,
			pulseKind:     ValueNone,
			trendKind:     ValueNone,
			expectedPulse: false,
			expectedTrend: false,
			expectedError: false,
		},
		{
			name:          "happy_null_input",
			json:          `null`,
			pulseKind:     ValueNone,
			trendKind:     ValueNone,
			expectedPulse: false,
			expectedTrend: false,
			expectedError: false,
		},
		{
			name:          "happy_empty_input",
			json:          "",
			pulseKind:     ValueNone,
			trendKind:     ValueNone,
			expectedPulse: false,
			expectedTrend: false,
			expectedError: false,
		},
		{
			name:          "sad_empty_string_input",
			json:          `""`,
			pulseKind:     ValueNone,
			trendKind:     ValueNone,
			expectedPulse: false,
			expectedTrend: false,
			expectedError: true,
		},
		{
			name:          "sad_invalid_json_input",
			json:          `{`,
			expectedError: true,
		},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			var s ValueData
			var err error
			if tt.json == "" {
				s = ValueData{}
			} else {
				err = json.Unmarshal([]byte(tt.json), &s)
			}
			if (err != nil) != tt.expectedError {
				t.Fatalf("Got err = %v, expected error? %t", err, tt.expectedError)
			}
			if err != nil {
				return
			}
			if s.Timestamp != tt.expectedTime {
				t.Fatalf("Got timestamp = %d, expected %d", s.Timestamp, tt.expectedTime)
			}
			if (s.Pulse == nil) && tt.expectedPulse {
				t.Fatalf("Got pulse nil = %t, expected %t", s.Pulse == nil, tt.expectedPulse)
			}
			if (s.Trend == nil) && tt.expectedTrend {
				t.Fatalf("Got trend nil = %t, expected %t", s.Trend == nil, tt.expectedTrend)
			}
			if s.Pulse != nil {
				if s.Pulse.OK != tt.pulseOK {
					t.Fatalf("Got pulse ok = %t, expected %t", s.Pulse.OK, tt.pulseOK)
				}
				if s.Pulse.Kind != tt.pulseKind {
					t.Fatal("pulse kind mismatch")
				}
			}
			if s.Trend != nil {
				if s.Trend.OK != tt.trendOK {
					t.Fatalf("Got trend ok = %t, expected %t", s.Trend.OK, tt.trendOK)
				}
				if s.Trend.Kind != tt.trendKind {
					t.Fatal("trend kind mismatch")
				}
			}
		})
	}
}

func TestValueData_MarshalJSON(t *testing.T) {
	tests := []struct {
		name          string
		value         *ValueData
		expected      string
		expectedError bool
	}{
		{
			name:          "happy_empty_value",
			value:         &ValueData{},
			expected:      `{"timestamp":0}`,
			expectedError: false,
		},
		{
			name: "happy_pulse_only_bool",
			value: func() *ValueData {
				value := NewBoolPulseValue(true)
				value.Timestamp = 1
				return value
			}(),
			expected:      `{"timestamp":1,"pulse":{"ok":true,"value":true}}`,
			expectedError: false,
		},
		{
			name: "happy_trend_only_bool",
			value: func() *ValueData {
				value := NewBoolValue(false, false)
				value.Timestamp = 2
				value.Pulse = nil
				return value
			}(),
			expected:      `{"timestamp":2,"trend":{"ok":false,"value":false}}`,
			expectedError: false,
		},
		{
			name: "happy_pulse_trend_mixed",
			value: func() *ValueData {
				value := NewFloatValue(true, 1.25, false, 0)
				value.Timestamp = 3
				value.Trend = &ValueDataDetail{
					OK:          false,
					Kind:        ValueString,
					ValueString: "down",
				}
				return value
			}(),
			expected:      `{"timestamp":3,"pulse":{"ok":true,"value":1.25},"trend":{"ok":false,"value":"down"}}`,
			expectedError: false,
		},
		{
			name: "happy_pulse_only_string",
			value: func() *ValueData {
				value := NewStringPulseValue(true, "up")
				value.Timestamp = 4
				return value
			}(),
			expected:      `{"timestamp":4,"pulse":{"ok":true,"value":"up"}}`,
			expectedError: false,
		},
		{
			name: "happy_pulse_trend_string",
			value: func() *ValueData {
				value := NewStringValue(false, "down", true, "steady")
				value.Timestamp = 5
				return value
			}(),
			expected:      `{"timestamp":5,"pulse":{"ok":false,"value":"down"},"trend":{"ok":true,"value":"steady"}}`,
			expectedError: false,
		},
		{
			name: "happy_pulse_only_float",
			value: func() *ValueData {
				value := NewFloatPulseValue(true, 42.5)
				value.Timestamp = 6
				return value
			}(),
			expected:      `{"timestamp":6,"pulse":{"ok":true,"value":42.5}}`,
			expectedError: false,
		},
		{
			name: "happy_pulse_only_perc",
			value: func() *ValueData {
				value := NewIntPulseValue(true, 99)
				value.Timestamp = 7
				return value
			}(),
			expected:      `{"timestamp":7,"pulse":{"ok":true,"value":99}}`,
			expectedError: false,
		},
		{
			name: "happy_pulse_trend_perc",
			value: func() *ValueData {
				value := NewIntValue(true, 80, false, 55)
				value.Timestamp = 8
				return value
			}(),
			expected:      `{"timestamp":8,"pulse":{"ok":true,"value":80},"trend":{"ok":false,"value":55}}`,
			expectedError: false,
		},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			raw, err := json.Marshal(tt.value)
			if (err != nil) != tt.expectedError {
				t.Fatalf("Got err = %v, expected error? %t", err, tt.expectedError)
			}
			if err != nil {
				return
			}
			if string(raw) != tt.expected {
				t.Fatalf("Got json = %s, expected %s", raw, tt.expected)
			}
		})
	}
}

func TestValueDataDetail_UnmarshalJSON(t *testing.T) {
	tests := []struct {
		name          string
		json          string
		expected      ValueDataDetail
		expectedError bool
	}{
		{
			name:          "happy_empty_object_input",
			json:          `{}`,
			expected:      ValueDataDetail{},
			expectedError: false,
		},
		{
			name:          "happy_null_input",
			json:          `null`,
			expected:      ValueDataDetail{},
			expectedError: false,
		},
		{
			name:          "happy_empty_string_input",
			json:          `""`,
			expected:      ValueDataDetail{},
			expectedError: false,
		},
		{
			name: "happy_number_value_float",
			json: `{"ok":true,"value":12.5}`,
			expected: ValueDataDetail{
				OK:         true,
				Kind:       ValueFloat,
				ValueFloat: 12.5,
			},
			expectedError: false,
		},
		{
			name: "happy_number_value_perc",
			json: `{"ok":true,"value":42}`,
			expected: ValueDataDetail{
				OK:       true,
				Kind:     ValueInt,
				ValueInt: 42,
			},
			expectedError: false,
		},
		{
			name: "happy_number_value_perc_min_int8",
			json: `{"ok":true,"value":-128}`,
			expected: ValueDataDetail{
				OK:       true,
				Kind:     ValueInt,
				ValueInt: -128,
			},
			expectedError: false,
		},
		{
			name: "happy_number_value_float_overflow_int8",
			json: `{"ok":true,"value":128}`,
			expected: ValueDataDetail{
				OK:         true,
				Kind:       ValueFloat,
				ValueFloat: 128,
			},
			expectedError: false,
		},
		{
			name: "happy_number_value_float_underflow_int8",
			json: `{"ok":true,"value":-129}`,
			expected: ValueDataDetail{
				OK:         true,
				Kind:       ValueFloat,
				ValueFloat: -129,
			},
			expectedError: false,
		},
		{
			name: "happy_number_value_string",
			json: `{"ok":true,"value":"12.5"}`,
			expected: ValueDataDetail{
				OK:          true,
				Kind:        ValueString,
				ValueString: "12.5",
			},
			expectedError: false,
		},
		{
			name: "happy_string_value_text",
			json: `{"ok":false,"value":"healthy"}`,
			expected: ValueDataDetail{
				OK:          false,
				Kind:        ValueString,
				ValueString: "healthy",
			},
			expectedError: false,
		},
		{
			name: "happy_bool_value_true",
			json: `{"ok":true,"value":true}`,
			expected: ValueDataDetail{
				OK:   true,
				Kind: ValueBool,
			},
			expectedError: false,
		},
		{
			name: "happy_value_missing_true",
			json: `{"ok":true}`,
			expected: ValueDataDetail{
				OK:   true,
				Kind: ValueBool,
			},
			expectedError: false,
		},
		{
			name: "happy_value_missing_false",
			json: `{"ok":false}`,
			expected: ValueDataDetail{
				OK:   false,
				Kind: ValueBool,
			},
			expectedError: false,
		},
		{
			name: "happy_value_null_input",
			json: `{"ok":true,"value":null}`,
			expected: ValueDataDetail{
				OK:   true,
				Kind: ValueNone,
			},
			expectedError: false,
		},
		{
			name: "happy_value_object_input",
			json: `{"ok":true,"value":{}}`,
			expected: ValueDataDetail{
				OK:   true,
				Kind: ValueNone,
			},
			expectedError: false,
		},
		{
			name:          "sad_invalid_json_input",
			json:          `{`,
			expectedError: true,
		},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			var detail ValueDataDetail
			err := json.Unmarshal([]byte(tt.json), &detail)
			if (err != nil) != tt.expectedError {
				t.Fatalf("Got err = %v, expected error? %t", err, tt.expectedError)
			}
			if err != nil {
				return
			}
			if detail.OK != tt.expected.OK {
				t.Fatalf("Got ok = %t, expected %t", detail.OK, tt.expected.OK)
			}
			if detail.Kind != tt.expected.Kind {
				t.Fatalf("Got kind = %v, expected %v", detail.Kind, tt.expected.Kind)
			}
			if detail.ValueFloat != tt.expected.ValueFloat {
				t.Fatalf("Got number = %v, expected %v", detail.ValueFloat, tt.expected.ValueFloat)
			}
			if detail.ValueString != tt.expected.ValueString {
				t.Fatalf("Got string = %q, expected %q", detail.ValueString, tt.expected.ValueString)
			}
		})
	}
}

func TestValueDataDetail_MarshalJSON(t *testing.T) {
	tests := []struct {
		name          string
		value         ValueDataDetail
		expected      string
		expectedError bool
	}{
		{
			name:          "happy_none_value",
			value:         ValueDataDetail{},
			expected:      "null",
			expectedError: false,
		},
		{
			name: "happy_number_value_float",
			value: ValueDataDetail{
				OK:         true,
				Kind:       ValueFloat,
				ValueFloat: 1.5,
			},
			expected:      `{"ok":true,"value":1.5}`,
			expectedError: false,
		},
		{
			name: "happy_string_value_text",
			value: ValueDataDetail{
				OK:          false,
				Kind:        ValueString,
				ValueString: "hi",
			},
			expected:      `{"ok":false,"value":"hi"}`,
			expectedError: false,
		},
		{
			name: "happy_perc_value",
			value: ValueDataDetail{
				OK:       true,
				Kind:     ValueInt,
				ValueInt: 85,
			},
			expected:      `{"ok":true,"value":85}`,
			expectedError: false,
		},
		{
			name: "happy_bool_value_true",
			value: ValueDataDetail{
				OK:   true,
				Kind: ValueBool,
			},
			expected:      `{"ok":true,"value":true}`,
			expectedError: false,
		},
		{
			name: "happy_bool_value_false",
			value: ValueDataDetail{
				OK:   false,
				Kind: ValueBool,
			},
			expected:      `{"ok":false,"value":false}`,
			expectedError: false,
		},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			raw, err := json.Marshal(tt.value)
			if (err != nil) != tt.expectedError {
				t.Fatalf("Got err = %v, expected error? %t", err, tt.expectedError)
			}
			if err != nil {
				return
			}
			if string(raw) != tt.expected {
				t.Fatalf("Got json = %s, expected %s", raw, tt.expected)
			}
		})
	}
}

func TestValueMeta_UnmarshalJSON(t *testing.T) {
	tests := []struct {
		name          string
		json          string
		expected      ValueMeta
		expectedError bool
	}{
		{
			name: "happy_with_pulse_and_trend",
			json: `{"version":"10.100.6842","pulse":{"window":"5s","unit":"%","type":"percentage","measure":"mean"},"trend":{"window":"24h","unit":"%","type":"percentage","measure":"p95"}}`,
			expected: ValueMeta{
				Version: "10.100.6842",
				Pulse: &ValueMetaDetail{
					Window:  "5s",
					Unit:    "%",
					Type:    "percentage",
					Measure: "mean",
				},
				Trend: &ValueMetaDetail{
					Window:  "24h",
					Unit:    "%",
					Type:    "percentage",
					Measure: "p95",
				},
			},
			expectedError: false,
		},
		{
			name: "happy_pulse_only",
			json: `{"version":"10.100.6842","pulse":{"window":"5s","unit":"%","type":"percentage","measure":"mean"}}`,
			expected: ValueMeta{
				Version: "10.100.6842",
				Pulse: &ValueMetaDetail{
					Window:  "5s",
					Unit:    "%",
					Type:    "percentage",
					Measure: "mean",
				},
				Trend: nil,
			},
			expectedError: false,
		},
		{
			name: "happy_trend_only",
			json: `{"version":"10.100.6842","trend":{"window":"24h","unit":"%","type":"percentage","measure":"p95"}}`,
			expected: ValueMeta{
				Version: "10.100.6842",
				Pulse:   nil,
				Trend: &ValueMetaDetail{
					Window:  "24h",
					Unit:    "%",
					Type:    "percentage",
					Measure: "p95",
				},
			},
			expectedError: false,
		},
		{
			name: "happy_version_only",
			json: `{"version":"10.100.6842"}`,
			expected: ValueMeta{
				Version: "10.100.6842",
			},
			expectedError: false,
		},
		{
			name: "happy_pulse_missing_unit",
			json: `{"version":"10.100.6842","pulse":{"window":"5s","type":"percentage","measure":"mean"}}`,
			expected: ValueMeta{
				Version: "10.100.6842",
				Pulse: &ValueMetaDetail{
					Window:  "5s",
					Unit:    "",
					Type:    "percentage",
					Measure: "mean",
				},
			},
			expectedError: false,
		},
		{
			name:          "sad_invalid_json_input",
			json:          `{`,
			expectedError: true,
		},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			var meta ValueMeta
			err := json.Unmarshal([]byte(tt.json), &meta)
			if (err != nil) != tt.expectedError {
				t.Fatalf("Got err = %v, expected error? %t", err, tt.expectedError)
			}
			if err != nil {
				return
			}
			if !reflect.DeepEqual(meta, tt.expected) {
				t.Fatalf("Got meta = %+v, expected %+v", meta, tt.expected)
			}
		})
	}
}

func TestValueMeta_MarshalJSON(t *testing.T) {
	tests := []struct {
		name          string
		value         ValueMeta
		expected      string
		expectedError bool
	}{
		{
			name: "happy_version_only",
			value: ValueMeta{
				Version: "10.100.6842",
			},
			expected:      `{"version":"10.100.6842"}`,
			expectedError: false,
		},
		{
			name: "happy_with_pulse_and_trend",
			value: ValueMeta{
				Version: "10.100.6842",
				Pulse: &ValueMetaDetail{
					Window:  "5s",
					Unit:    "%",
					Type:    "percentage",
					Measure: "mean",
				},
				Trend: &ValueMetaDetail{
					Window:  "24h",
					Unit:    "%",
					Type:    "percentage",
					Measure: "p95",
				},
			},
			expected:      `{"version":"10.100.6842","pulse":{"window":"5s","unit":"%","type":"percentage","measure":"mean"},"trend":{"window":"24h","unit":"%","type":"percentage","measure":"p95"}}`,
			expectedError: false,
		},
		{
			name: "happy_pulse_only",
			value: ValueMeta{
				Version: "10.100.6842",
				Pulse: &ValueMetaDetail{
					Window:  "5s",
					Unit:    "%",
					Type:    "percentage",
					Measure: "mean",
				},
			},
			expected:      `{"version":"10.100.6842","pulse":{"window":"5s","unit":"%","type":"percentage","measure":"mean"}}`,
			expectedError: false,
		},
		{
			name: "happy_trend_only",
			value: ValueMeta{
				Version: "10.100.6842",
				Trend: &ValueMetaDetail{
					Window:  "24h",
					Unit:    "%",
					Type:    "percentage",
					Measure: "p95",
				},
			},
			expected:      `{"version":"10.100.6842","trend":{"window":"24h","unit":"%","type":"percentage","measure":"p95"}}`,
			expectedError: false,
		},
		{
			name: "happy_pulse_missing_unit",
			value: ValueMeta{
				Version: "10.100.6842",
				Pulse: &ValueMetaDetail{
					Window:  "5s",
					Unit:    "",
					Type:    "percentage",
					Measure: "mean",
				},
			},
			expected:      `{"version":"10.100.6842","pulse":{"window":"5s","type":"percentage","measure":"mean"}}`,
			expectedError: false,
		},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			raw, err := json.Marshal(tt.value)
			if (err != nil) != tt.expectedError {
				t.Fatalf("Got err = %v, expected error? %t", err, tt.expectedError)
			}
			if err != nil {
				return
			}
			if string(raw) != tt.expected {
				t.Fatalf("Got json = %s, expected %s", raw, tt.expected)
			}
		})
	}
}
