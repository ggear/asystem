package plugin

import (
	"bytes"
	"context"
	"testing"
	"time"
)

type fakePlugin struct{ name string }

func (f fakePlugin) Name() string                          { return f.name }
func (f fakePlugin) PollPhase() bool                       { return false }
func (f fakePlugin) Poll(context.Context) (Message, error) { return Message{}, nil }
func (f fakePlugin) Aggregate([]Message) (Message, error)  { return Message{}, nil }

func TestFilter(t *testing.T) {
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

func TestFieldConstructors(t *testing.T) {
	if f := Float("a", 1.5); f.Kind != KindFloat || f.Float != 1.5 {
		t.Fatalf("Float wrong: %+v", f)
	}
	if f := Int("a", 3); f.Kind != KindInt || f.Int != 3 {
		t.Fatalf("Int wrong: %+v", f)
	}
	if f := Bool("a", true); f.Kind != KindBool || !f.Bool {
		t.Fatalf("Bool wrong: %+v", f)
	}
	if f := Str("a", "x"); f.Kind != KindStr || f.Str != "x" {
		t.Fatalf("Str wrong: %+v", f)
	}
	if f := Null("a"); f.Kind != KindNull {
		t.Fatalf("Null wrong: %+v", f)
	}
}

func TestMessage_MarshalJSON(t *testing.T) {
	tests := []struct {
		name          string
		message       Message
		expected      string
		expectedError bool
	}{
		{
			name:          "sick_verdict",
			message:       Message{Timestamp: time.Unix(1737686400, 0), OK: true, Status: StatusSick, Score: 72},
			expected:      `{"timestamp":1737686400,"ok":true,"status":"sick","score":72}`,
			expectedError: false,
		},
		{
			name:          "dead_verdict",
			message:       Message{Timestamp: time.Unix(1737686400, 0), OK: false, Status: StatusDead, Score: 0},
			expected:      `{"timestamp":1737686400,"ok":false,"status":"dead","score":0}`,
			expectedError: false,
		},
		{
			name:          "fit_verdict",
			message:       Message{Timestamp: time.Unix(1737686400, 0), OK: true, Status: StatusFit, Score: 100},
			expected:      `{"timestamp":1737686400,"ok":true,"status":"fit","score":100}`,
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

func TestMessage_AppendLineProtocol(t *testing.T) {
	tests := []struct {
		name          string
		message       Message
		expected      string
		expectedError bool
	}{
		{
			name: "summary_and_target",
			message: Message{
				Plugin: "internet",
				Host:   "macmini-max",
				Points: []Point{
					NewPoint([]Tag{{"scope", "summary"}}, Int("score", 72), Float("avg_loss_pct", 12.5), Bool("gateway_ok", true), Null("skip_me")),
					NewPoint([]Tag{{"scope", "target"}, {"target", "8.8.8.8"}}, Bool("ok", true), Float("loss_pct", 25)),
				},
			},
			expected: "network,host=macmini-max,plugin=internet,scope=summary score=72i,avg_loss_pct=12.5,gateway_ok=true 1000\n" +
				"network,host=macmini-max,plugin=internet,scope=target,target=8.8.8.8 ok=true,loss_pct=25 1000\n",
			expectedError: false,
		},
		{
			name: "all_null_point_skipped",
			message: Message{
				Plugin: "internet",
				Host:   "macmini-max",
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

func TestEscapeTag(t *testing.T) {
	tests := []struct {
		name     string
		input    string
		expected string
	}{
		{name: "plain", input: "plain", expected: "plain"},
		{name: "space", input: "a b", expected: `a\ b`},
		{name: "comma", input: "a,b", expected: `a\,b`},
		{name: "equals", input: "a=b", expected: `a\=b`},
		{name: "mixed", input: "a b,c=d", expected: `a\ b\,c\=d`},
		{name: "empty", input: "", expected: ""},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			if got := escapeTag(test.input); got != test.expected {
				t.Errorf("got %q want %q", got, test.expected)
			}
		})
	}
}

func TestMessage_AppendLineProtocol_Escaping(t *testing.T) {
	m := Message{
		Plugin: "zig bee",
		Host:   "host,1",
		Points: []Point{
			NewPoint([]Tag{{"scope", "a=b"}}, Str("note", `x"y\z`), Int("n", 3)),
		},
	}
	var buf bytes.Buffer
	m.AppendLineProtocol(&buf, "network", 1000)
	want := `network,host=host\,1,plugin=zig\ bee,scope=a\=b note="x\"y\\z",n=3i 1000` + "\n"
	if buf.String() != want {
		t.Fatalf("line protocol mismatch:\n got %q\nwant %q", buf.String(), want)
	}
}
