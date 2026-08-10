package schema

import (
	"bytes"
	"testing"
)

func TestSchema_AppendLineProtocol(t *testing.T) {
	t.Setenv("SERVICE_NAME", "supervisor")
	relation := Relation{
		Path: "supervisor/service",
		Measures: []Measure{
			{Key: "status", Kind: KindBool, Persist: true},
			{Key: "status_trend", Kind: KindBool, Persist: true},
			{Key: "used_memory", Kind: KindInt, Persist: true},
			{Key: "max_memory", Kind: KindFloat, Persist: false},
			{Key: "restart_count", Kind: KindFloat, Persist: true},
			{Key: "name", Kind: KindStr, Persist: true},
		},
	}
	tests := []struct {
		name          string
		tags          [][2]string
		fields        map[string]Field
		expected      string
		expectedWrote bool
	}{
		{
			name: "declared_order_not_insertion_order",
			tags: [][2]string{{"host", "macmini-mad"}, {"service", "plex"}},
			fields: map[string]Field{
				"restart_count": {Text: "2.0"},
				"used_memory":   {Text: "41"},
				"status":        {Flag: true},
				"status_trend":  {Flag: false},
			},
			expected:      "supervisor,module=supervisor,host=macmini-mad,service=plex status=1i,status_trend=0i,used_memory=41i,restart_count=2.0 1000\n",
			expectedWrote: true,
		},
		{
			name:          "host_scope_omits_empty_tag",
			tags:          [][2]string{{"host", "macmini-max"}, {"service", ""}},
			fields:        map[string]Field{"used_memory": {Text: "7"}},
			expected:      "supervisor,module=supervisor,host=macmini-max used_memory=7i 1000\n",
			expectedWrote: true,
		},
		{
			name:          "non_persisted_and_string_measures_are_dropped",
			tags:          [][2]string{{"host", "macmini-max"}},
			fields:        map[string]Field{"max_memory": {Text: "512.0"}, "name": {Text: "plex"}},
			expected:      "",
			expectedWrote: false,
		},
		{
			name:          "undeclared_field_cannot_be_written",
			tags:          [][2]string{{"host", "macmini-max"}},
			fields:        map[string]Field{"invented_metric": {Text: "1"}},
			expected:      "",
			expectedWrote: false,
		},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			var buf bytes.Buffer
			wrote := AppendLineProtocol(&buf, "supervisor", relation, test.tags, test.fields, "1000")
			if wrote != test.expectedWrote {
				t.Errorf("wrote: got %v want %v", wrote, test.expectedWrote)
			}
			if buf.String() != test.expected {
				t.Fatalf("line protocol mismatch:\n got %q\nwant %q", buf.String(), test.expected)
			}
		})
	}
}

func TestSchema_Reflect(t *testing.T) {
	var buf bytes.Buffer
	relation := Relation{Path: "supervisor/host", Measures: []Measure{{Key: "status", Kind: KindBool, Persist: true}}}
	if err := Reflect(&buf, "supervisor", Database{relation}, nil); err != nil {
		t.Fatalf("reflect: unexpected error %v", err)
	}
	if !bytes.Contains(buf.Bytes(), []byte(`"path": "supervisor/host"`)) {
		t.Errorf("database: got %s want the declared relation", buf.String())
	}
	if bytes.Contains(buf.Bytes(), []byte(`"broker"`)) {
		t.Errorf("broker: got a section want it omitted when no broker schema is supplied")
	}
}
