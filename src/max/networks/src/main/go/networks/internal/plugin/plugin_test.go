package plugin

import (
	"bytes"
	"context"
	"testing"
	"time"
)

func TestPlugin_Filter(t *testing.T) {
	Register(fakePlugin{name: "alpha"})
	Register(fakePlugin{name: "beta"})
	tests := []struct {
		name          string
		names         []string
		expectedNames []string
		expectedError bool
	}{
		{name: "empty_returns_all", names: nil, expectedNames: []string{"alpha", "beta"}, expectedError: false},
		{name: "single", names: []string{"beta"}, expectedNames: []string{"beta"}, expectedError: false},
		{name: "dedup_and_trim", names: []string{" alpha ", "alpha"}, expectedNames: []string{"alpha"}, expectedError: false},
		{name: "unknown_errors", names: []string{"gamma"}, expectedNames: nil, expectedError: true},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			got, err := Filter(test.names)
			if (err != nil) != test.expectedError {
				t.Fatalf("error mismatch: got %v want error=%v", err, test.expectedError)
			}
			if test.expectedError {
				return
			}
			if len(got) != len(test.expectedNames) {
				t.Fatalf("count mismatch: got %d want %d", len(got), len(test.expectedNames))
			}
			for i, p := range got {
				if p.Name() != test.expectedNames[i] {
					t.Fatalf("name mismatch at %d: got %s want %s", i, p.Name(), test.expectedNames[i])
				}
			}
		})
	}
}

func TestAggregate_MarshalJSON(t *testing.T) {
	tests := []struct {
		name          string
		message       Aggregate
		expected      string
		expectedError bool
	}{
		{
			name:          "sick_diagnose",
			message:       Aggregate{Timestamp: time.Unix(1737686400, 0), OK: true, Status: StatusSick, Score: 72},
			expected:      `{"timestamp":1737686400,"ok":true,"status":"sick","score":72}`,
			expectedError: false,
		},
		{
			name:          "dead_diagnose",
			message:       Aggregate{Timestamp: time.Unix(1737686400, 0), OK: false, Status: StatusDead, Score: 0},
			expected:      `{"timestamp":1737686400,"ok":false,"status":"dead","score":0}`,
			expectedError: false,
		},
		{
			name:          "fit_diagnose",
			message:       Aggregate{Timestamp: time.Unix(1737686400, 0), OK: true, Status: StatusFit, Score: 100},
			expected:      `{"timestamp":1737686400,"ok":true,"status":"fit","score":100}`,
			expectedError: false,
		},
		{
			name:          "status_is_escaped",
			message:       Aggregate{Timestamp: time.Unix(1737686400, 0), OK: true, Status: Status("bad\"\nstatus"), Score: 1},
			expected:      `{"timestamp":1737686400,"ok":true,"status":"bad\"\nstatus","score":1}`,
			expectedError: false,
		},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			got, err := test.message.MarshalJSON()
			if (err != nil) != test.expectedError {
				t.Fatalf("error mismatch: got %v want error=%v", err, test.expectedError)
			}
			if string(got) != test.expected {
				t.Fatalf("json mismatch:\n got %s\nwant %s", got, test.expected)
			}
		})
	}
}

func TestAggregate_AppendLineProtocol(t *testing.T) {
	tests := []struct {
		name          string
		message       Aggregate
		expected      string
		expectedError bool
	}{
		{
			name: "summary_and_target",
			message: Aggregate{
				Plugin: "internet",
				Points: []Point{
					NewPoint([]Tag{{"scope", "summary"}}, Int("score", 72), Float("avg_loss_pct", 12.5), Bool("gateway_ok", true), Null("skip_me")),
					NewPoint([]Tag{{"scope", "target"}, {"target", "8.8.8.8"}}, Bool("ok", true), Float("loss_pct", 25)),
				},
			},
			expected: "network,plugin=internet,scope=summary score=72i,avg_loss_pct=12.5 1000\n" +
				"network,plugin=internet,scope=target,target=8.8.8.8 loss_pct=25 1000\n",
			expectedError: false,
		},
		{
			name: "all_null_point_skipped",
			message: Aggregate{
				Plugin: "internet",
				Points: []Point{NewPoint([]Tag{{"scope", "target"}}, Null("avg_rtt_ms"))},
			},
			expected:      "",
			expectedError: false,
		},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			var buf bytes.Buffer
			test.message.AppendLineProtocol(&buf, "network", 1000)
			if buf.String() != test.expected {
				t.Fatalf("line protocol mismatch:\n got %q\nwant %q", buf.String(), test.expected)
			}
		})
	}
}

func TestAggregate_AppendLineProtocol_Escaping(t *testing.T) {
	m := Aggregate{
		Plugin: "zig bee",
		Points: []Point{
			NewPoint([]Tag{{"scope", "a=b"}}, Str("note", "x y=z"), Int("n", 3)),
		},
	}
	var buf bytes.Buffer
	m.AppendLineProtocol(&buf, "network", 1000)
	want := `network,plugin=zig\ bee,scope=a\=b,note=x\ y\=z n=3i 1000` + "\n"
	if buf.String() != want {
		t.Fatalf("line protocol mismatch:\n got %q\nwant %q", buf.String(), want)
	}
}

func TestPlugin_ParseState(t *testing.T) {
	tests := []struct {
		name          string
		payload       string
		expectedState State
		expectedOK    bool
	}{
		{name: "on", payload: "ON", expectedState: StateOn, expectedOK: true},
		{name: "off", payload: "OFF", expectedState: StateOff, expectedOK: true},
		{name: "lower_trimmed", payload: " on ", expectedState: StateOn, expectedOK: true},
		{name: "unknown", payload: "check", expectedState: StateOff, expectedOK: false},
		{name: "empty", payload: "", expectedState: StateOff, expectedOK: false},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			state, ok := ParseState(test.payload)
			if ok != test.expectedOK {
				t.Fatalf("ok: got %v want %v", ok, test.expectedOK)
			}
			if state != test.expectedState {
				t.Errorf("state: got %s want %s", state, test.expectedState)
			}
		})
	}
}

func TestStateTracker_SetGet(t *testing.T) {
	s := NewStateTracker(StateOn)
	if got := s.Get(); got != StateOn {
		t.Fatalf("initial: got %s want ON", got)
	}
	s.Set(StateOff)
	if got := s.Get(); got != StateOff {
		t.Fatalf("after set: got %s want OFF", got)
	}
}

func TestPlugin_Clamp(t *testing.T) {
	tests := []struct {
		name     string
		value    int
		expected int
	}{
		{name: "below", value: -5, expected: 0},
		{name: "low_bound", value: 0, expected: 0},
		{name: "mid", value: 50, expected: 50},
		{name: "high_bound", value: 100, expected: 100},
		{name: "above", value: 150, expected: 100},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			if got := Clamp(test.value); got != test.expected {
				t.Errorf("clamp: got %d want %d", got, test.expected)
			}
		})
	}
}

func TestPlugin_Round(t *testing.T) {
	tests := []struct {
		name     string
		value    float64
		places   int
		expected float64
	}{
		{name: "down", value: 1.2345, places: 2, expected: 1.23},
		{name: "up", value: 1.2356, places: 2, expected: 1.24},
		{name: "half_away", value: 12.5, places: 0, expected: 13},
		{name: "whole", value: 7, places: 2, expected: 7},
		{name: "negative", value: -1.2356, places: 2, expected: -1.24},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			if got := Round(test.value, test.places); got != test.expected {
				t.Errorf("round: got %v want %v", got, test.expected)
			}
		})
	}
}

func TestPlugin_Diagnose(t *testing.T) {
	tests := []struct {
		name       string
		status     Status
		expectedOK bool
	}{
		{name: "fit_is_ok", status: StatusFit, expectedOK: true},
		{name: "sick_is_ok", status: StatusSick, expectedOK: true},
		{name: "dead_is_not_ok", status: StatusDead, expectedOK: false},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			got := Diagnose(test.status, 42, "CODE: [value]")
			if got.OK != test.expectedOK {
				t.Errorf("ok: got %v want %v", got.OK, test.expectedOK)
			}
			if got.Status != test.status {
				t.Errorf("status: got %s want %s", got.Status, test.status)
			}
			if got.Score != 42 {
				t.Errorf("score: got %d want 42", got.Score)
			}
			if got.Reason != "CODE: [value]" {
				t.Errorf("reason: got %s want CODE: [value]", got.Reason)
			}
		})
	}
}

func TestDeltaTracker_Delta(t *testing.T) {
	d := NewDeltaTracker()
	steps := []struct {
		name       string
		key        string
		cumulative int64
		expected   int64
	}{
		{name: "first_seen_zero", key: "rx", cumulative: 100, expected: 0},
		{name: "increment", key: "rx", cumulative: 150, expected: 50},
		{name: "equal_zero", key: "rx", cumulative: 150, expected: 0},
		{name: "reset_zero", key: "rx", cumulative: 120, expected: 0},
		{name: "increment_after_reset", key: "rx", cumulative: 170, expected: 50},
		{name: "other_key_first_seen", key: "tx", cumulative: 10, expected: 0},
		{name: "other_key_increment", key: "tx", cumulative: 25, expected: 15},
	}
	for _, step := range steps {
		if got := d.Delta(step.key, step.cumulative); got != step.expected {
			t.Errorf("%s: got %d want %d", step.name, got, step.expected)
		}
	}
}

func TestPoint_Accessors(t *testing.T) {
	p := NewPoint(
		[]Tag{{"scope", "summary"}},
		Float("loss_pct", 12.5),
		Int("count", 7),
		Bool("up", true),
		Str("note", "hello"),
		Null("missing"),
	)
	if v, ok := p.Float("loss_pct"); !ok || v != 12.5 {
		t.Errorf("Float(loss_pct): got %v %v want 12.5 true", v, ok)
	}
	if v, ok := p.Float("count"); !ok || v != 7 {
		t.Errorf("Float(count): got %v %v want 7 true", v, ok)
	}
	if _, ok := p.Float("up"); ok {
		t.Errorf("Float(up): got ok=true want false")
	}
	if _, ok := p.Float("absent"); ok {
		t.Errorf("Float(absent): got ok=true want false")
	}
	if v, ok := p.Int("count"); !ok || v != 7 {
		t.Errorf("Int(count): got %v %v want 7 true", v, ok)
	}
	if _, ok := p.Int("loss_pct"); ok {
		t.Errorf("Int(loss_pct): got ok=true want false")
	}
	if v, ok := p.Bool("up"); !ok || !v {
		t.Errorf("Bool(up): got %v %v want true true", v, ok)
	}
	if _, ok := p.Bool("count"); ok {
		t.Errorf("Bool(count): got ok=true want false")
	}
	if v, ok := p.Tag("scope"); !ok || v != "summary" {
		t.Errorf("Tag(scope): got %v %v want summary true", v, ok)
	}
	if _, ok := p.Tag("absent"); ok {
		t.Errorf("Tag(absent): got ok=true want false")
	}
}

func TestPlugin_LatestPoints(t *testing.T) {
	if got := LatestPoints(nil); got != nil {
		t.Errorf("empty: got %v want nil", got)
	}
	samples := []Sample{
		{Points: []Point{NewPoint(nil, Int("n", 1))}},
		{Points: []Point{NewPoint(nil, Int("n", 2))}},
	}
	got := LatestPoints(samples)
	if len(got) != 1 {
		t.Fatalf("len: got %d want 1", len(got))
	}
	if v, ok := got[0].Int("n"); !ok || v != 2 {
		t.Errorf("latest: got %v %v want 2 true", v, ok)
	}
}

func TestPlugin_PrependSummaryPoints(t *testing.T) {
	summary := NewPoint([]Tag{{"scope", "summary"}}, Int("score", 90))
	details := []Point{
		NewPoint([]Tag{{"scope", "target"}}, Int("n", 1)),
		NewPoint([]Tag{{"scope", "target"}}, Int("n", 2)),
	}
	got := PrependSummaryPoints(summary, details)
	if len(got) != 3 {
		t.Fatalf("len: got %d want 3", len(got))
	}
	if v, _ := got[0].Tag("scope"); v != "summary" {
		t.Errorf("first scope: got %s want summary", v)
	}
	if v, _ := got[2].Int("n"); v != 2 {
		t.Errorf("last n: got %d want 2", v)
	}
}

type fakePlugin struct{ name string }

func (f fakePlugin) Name() string                          { return f.name }
func (f fakePlugin) Mode() Mode                            { return ModeSnapshot }
func (f fakePlugin) Poll(context.Context) (Sample, error)  { return Sample{}, nil }
func (f fakePlugin) Aggregate([]Sample) (Aggregate, error) { return Aggregate{}, nil }
func (f fakePlugin) Command(context.Context, State) error  { return nil }
func (f fakePlugin) State() *StateTracker                  { return nil }
