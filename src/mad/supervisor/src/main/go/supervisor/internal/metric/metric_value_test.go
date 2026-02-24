package metric

import (
	"encoding/json"
	"reflect"
	"testing"
)

func TestValueData_UnmarshalJSON(t *testing.T) {
	tests := []struct {
		name              string
		json              string
		expectedTimestamp int64
		pulseKind         ValueKind
		trendKind         ValueKind
		pulseOK           bool
		trendOK           bool
		expectedError     bool
	}{
		{
			name:              "happy_percentage",
			json:              `{"timestamp":1771744503,"pulse":{"ok":true,"value":20},"trend":{"ok":false,"value":91}}`,
			expectedTimestamp: 1771744503,
			pulseKind:         ValueNumber,
			trendKind:         ValueNumber,
			pulseOK:           true,
			trendOK:           false,
			expectedError:     false,
		},
		{
			name:              "happy_string_values",
			json:              `{"timestamp":42,"pulse":{"ok":true,"value":"hot"},"trend":{"ok":true,"value":"cold"}}`,
			expectedTimestamp: 42,
			pulseKind:         ValueString,
			trendKind:         ValueString,
			pulseOK:           true,
			trendOK:           true,
			expectedError:     false,
		},
		{
			name:              "happy_missing_pulse",
			json:              `{"timestamp":7,"trend":{"ok":true,"value":1}}`,
			expectedTimestamp: 7,
			pulseKind:         ValueNone,
			trendKind:         ValueNumber,
			pulseOK:           false,
			trendOK:           true,
			expectedError:     false,
		},
		{
			name:              "happy_bool_values",
			json:              `{"timestamp":9,"pulse":{"ok":true},"trend":{"ok":false}}`,
			expectedTimestamp: 9,
			pulseKind:         ValueBoolean,
			trendKind:         ValueBoolean,
			pulseOK:           true,
			trendOK:           false,
			expectedError:     false,
		},
		{
			name:              "happy_null_pulse_trend",
			json:              `{"timestamp":11,"pulse":null,"trend":null}`,
			expectedTimestamp: 11,
			pulseKind:         ValueNone,
			trendKind:         ValueNone,
			expectedError:     false,
		},
		{
			name:          "happy_empty_object",
			json:          `{}`,
			pulseKind:     ValueNone,
			trendKind:     ValueNone,
			expectedError: false,
		},
		{
			name:          "happy_empty_string",
			json:          `""`,
			pulseKind:     ValueNone,
			trendKind:     ValueNone,
			expectedError: false,
		},
		{
			name:          "happy_null",
			json:          `null`,
			pulseKind:     ValueNone,
			trendKind:     ValueNone,
			expectedError: false,
		},
		{
			name:          "happy_empty",
			json:          "",
			pulseKind:     ValueNone,
			trendKind:     ValueNone,
			expectedError: false,
		},
		{
			name:          "sad_invalid_json",
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
			if s.Timestamp != tt.expectedTimestamp {
				t.Fatalf("Got timestamp = %d, expected %d", s.Timestamp, tt.expectedTimestamp)
			}
			if s.Pulse.OK != tt.pulseOK {
				t.Fatalf("Got pulse ok = %t, expected %t", s.Pulse.OK, tt.pulseOK)
			}
			if s.Trend.OK != tt.trendOK {
				t.Fatalf("Got trend ok = %t, expected %t", s.Trend.OK, tt.trendOK)
			}
			if s.Pulse.Kind != tt.pulseKind {
				t.Fatal("pulse kind mismatch")
			}
			if s.Trend.Kind != tt.trendKind {
				t.Fatal("trend kind mismatch")
			}
		})
	}
}

func TestValueData_MarshalJSON(t *testing.T) {
	tests := []struct {
		name          string
		value         ValueData
		expected      string
		expectedError bool
	}{
		{
			name:          "happy_empty",
			value:         ValueData{},
			expected:      `{"timestamp":0}`,
			expectedError: false,
		},
		{
			name: "happy_with_pulse_only",
			value: ValueData{
				Timestamp: 1,
				Pulse: ValueDataDetail{
					OK:   true,
					Kind: ValueBoolean,
				},
			},
			expected:      `{"timestamp":1,"pulse":{"ok":true,"value":true}}`,
			expectedError: false,
		},
		{
			name: "happy_with_trend_only",
			value: ValueData{
				Timestamp: 2,
				Trend: ValueDataDetail{
					OK:   false,
					Kind: ValueBoolean,
				},
			},
			expected:      `{"timestamp":2,"trend":{"ok":false,"value":false}}`,
			expectedError: false,
		},
		{
			name: "happy_with_pulse_trend",
			value: ValueData{
				Timestamp: 3,
				Pulse: ValueDataDetail{
					OK:     true,
					Kind:   ValueNumber,
					Number: 1.25,
				},
				Trend: ValueDataDetail{
					OK:     false,
					Kind:   ValueString,
					String: "down",
				},
			},
			expected:      `{"timestamp":3,"pulse":{"ok":true,"value":1.25},"trend":{"ok":false,"value":"down"}}`,
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
			name:          "happy_empty_object",
			json:          `{}`,
			expected:      ValueDataDetail{},
			expectedError: false,
		},
		{
			name:          "happy_null",
			json:          `null`,
			expected:      ValueDataDetail{},
			expectedError: false,
		},
		{
			name:          "happy_empty_string",
			json:          `""`,
			expected:      ValueDataDetail{},
			expectedError: false,
		},
		{
			name: "happy_number_value",
			json: `{"ok":true,"value":12.5}`,
			expected: ValueDataDetail{
				OK:     true,
				Kind:   ValueNumber,
				Number: 12.5,
			},
			expectedError: false,
		},
		{
			name: "happy_number_string_value",
			json: `{"ok":true,"value":"12.5"}`,
			expected: ValueDataDetail{
				OK:     true,
				Kind:   ValueString,
				String: "12.5",
			},
			expectedError: false,
		},
		{
			name: "happy_string_value",
			json: `{"ok":false,"value":"healthy"}`,
			expected: ValueDataDetail{
				OK:     false,
				Kind:   ValueString,
				String: "healthy",
			},
			expectedError: false,
		},
		{
			name: "happy_non_parseable_value",
			json: `{"ok":true,"value":true}`,
			expected: ValueDataDetail{
				OK:   true,
				Kind: ValueNone,
			},
			expectedError: false,
		},
		{
			name: "happy_missing_value",
			json: `{"ok":true}`,
			expected: ValueDataDetail{
				OK:   true,
				Kind: ValueBoolean,
			},
			expectedError: false,
		},
		{
			name: "happy_missing_value_false",
			json: `{"ok":false}`,
			expected: ValueDataDetail{
				OK:   false,
				Kind: ValueBoolean,
			},
			expectedError: false,
		},
		{
			name: "happy_value_null",
			json: `{"ok":true,"value":null}`,
			expected: ValueDataDetail{
				OK:   true,
				Kind: ValueNone,
			},
			expectedError: false,
		},
		{
			name: "happy_value_object",
			json: `{"ok":true,"value":{}}`,
			expected: ValueDataDetail{
				OK:   true,
				Kind: ValueNone,
			},
			expectedError: false,
		},
		{
			name:          "sad_invalid_json",
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
			if detail.Number != tt.expected.Number {
				t.Fatalf("Got number = %v, expected %v", detail.Number, tt.expected.Number)
			}
			if detail.String != tt.expected.String {
				t.Fatalf("Got string = %q, expected %q", detail.String, tt.expected.String)
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
			name:          "happy_none",
			value:         ValueDataDetail{},
			expected:      "null",
			expectedError: false,
		},
		{
			name: "happy_number",
			value: ValueDataDetail{
				OK:     true,
				Kind:   ValueNumber,
				Number: 1.5,
			},
			expected:      `{"ok":true,"value":1.5}`,
			expectedError: false,
		},
		{
			name: "happy_string",
			value: ValueDataDetail{
				OK:     false,
				Kind:   ValueString,
				String: "hi",
			},
			expected:      `{"ok":false,"value":"hi"}`,
			expectedError: false,
		},
		{
			name: "happy_bool_true",
			value: ValueDataDetail{
				OK:   true,
				Kind: ValueBoolean,
			},
			expected:      `{"ok":true,"value":true}`,
			expectedError: false,
		},
		{
			name: "happy_bool_false",
			value: ValueDataDetail{
				OK:   false,
				Kind: ValueBoolean,
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
			name: "happy_with_pulse_trend",
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
			name: "happy_omit_trend",
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
			name: "happy_omit_pulse",
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
			name: "happy_missing_unit",
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
			name:          "sad_invalid_json",
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
			name: "happy_with_pulse_trend",
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
			name: "happy_with_pulse_only",
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
			name: "happy_with_trend_only",
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
			name: "happy_without_unit",
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
