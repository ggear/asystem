package schema

import (
	"bytes"
	"encoding/json"
	"strings"
	"testing"
)

var (
	fakeSummary   = Declare("fake/summary", "rollup across the fake things", "15 min")
	fakeScore     = fakeSummary.Int("score", "count", "diagnosis score from 0 to 100")
	fakeLoss      = fakeSummary.Float("avg_loss_pct", "percent", "mean loss across the fake things")
	fakeGatewayOK = fakeSummary.Bool("gateway_ok", "the fake gateway answered")

	fakeThing      = Declare("fake/thing", "reading for one fake thing", "15 min").Entities("alpha", "beta")
	fakeThingName  = fakeThing.Subject("thing", "name of the fake thing")
	fakeThingNote  = fakeThing.Dimension("note", "free text carried as a tag")
	fakeThingUp    = fakeThing.Bool("up", "thing is up")
	fakeThingCount = fakeThing.Int("count", "count", "things counted")
	fakeThingDraft = fakeThing.Float("draft_pct", "percent", "declared but never persisted").Transient()
)

func TestSchema_KeysReadBack(t *testing.T) {
	point := fakeThing.Point(fakeThingName.Of("alpha"), fakeThingUp.Of(true), fakeThingCount.Of(7))
	if got, ok := fakeThingName.Read(point); !ok || got != "alpha" {
		t.Errorf("thing: got %v %v want alpha true", got, ok)
	}
	if got, ok := fakeThingUp.Read(point); !ok || !got {
		t.Errorf("up: got %v %v want true true", got, ok)
	}
	if got, ok := fakeThingCount.Read(point); !ok || got != 7 {
		t.Errorf("count: got %v %v want 7 true", got, ok)
	}
	if _, ok := fakeThingDraft.Read(point); ok {
		t.Errorf("draft_pct: got ok=true want false for an unset measure")
	}
	if _, ok := fakeThingNote.Read(point); ok {
		t.Errorf("note: got ok=true want false for an unset dimension")
	}
	if _, ok := fakeScore.Read(point); ok {
		t.Errorf("score: got ok=true want false for a key of another relation")
	}
}

func TestSchema_DeclareRejectsDuplicateKey(t *testing.T) {
	defer func() {
		if recovered := recover(); recovered == nil {
			t.Fatal("duplicate key: got no panic want a panic at declaration")
		}
	}()
	duplicate := Declare("fake/duplicate", "relation declaring one key twice", "15 min")
	duplicate.Int("score", "count", "first")
	duplicate.Int("score", "count", "second")
}

func TestSchema_DeclareRejectsDuplicateRelation(t *testing.T) {
	defer func() {
		if recovered := recover(); recovered == nil {
			t.Fatal("duplicate relation: got no panic want a panic at declaration")
		}
	}()
	Declare("fake/thing", "already declared above", "15 min")
}

func TestSchema_AppendLineProtocol(t *testing.T) {
	tests := []struct {
		name     string
		points   []Point
		expected string
	}{
		{
			name:     "summary_coerces_bool_to_int",
			points:   []Point{fakeSummary.Point(fakeScore.Of(72), fakeLoss.Of(12.5), fakeGatewayOK.Of(true))},
			expected: "fake score=72i,avg_loss_pct=12.5,gateway_ok=1i 1000\n",
		},
		{
			name:     "false_bool_is_zero",
			points:   []Point{fakeSummary.Point(fakeGatewayOK.Of(false))},
			expected: "fake gateway_ok=0i 1000\n",
		},
		{
			name:     "dimensions_become_tags_in_declared_order",
			points:   []Point{fakeThing.Point(fakeThingName.Of("alpha"), fakeThingNote.Of("x y=z"), fakeThingUp.Of(true))},
			expected: "fake,thing=alpha,note=x\\ y\\=z up=1i 1000\n",
		},
		{
			name:     "transient_measure_is_not_written",
			points:   []Point{fakeThing.Point(fakeThingName.Of("beta"), fakeThingDraft.Of(50))},
			expected: "",
		},
		{
			name:     "empty_point_is_skipped",
			points:   []Point{{}},
			expected: "",
		},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			var buf bytes.Buffer
			AppendLineProtocol(&buf, test.points, 1000)
			if buf.String() != test.expected {
				t.Fatalf("line protocol mismatch:\n got %q\nwant %q", buf.String(), test.expected)
			}
		})
	}
}

func TestSchema_Reflect(t *testing.T) {
	var buf bytes.Buffer
	if err := Reflect(&buf, "fake", Database{fakeThing.Relation()}, nil); err != nil {
		t.Fatalf("reflect: unexpected error %v", err)
	}
	if strings.Contains(buf.String(), `"broker"`) {
		t.Errorf("broker: got a section want it omitted when no broker schema is supplied")
	}
	var document Document
	if err := json.Unmarshal(buf.Bytes(), &document); err != nil {
		t.Fatalf("decode: unexpected error %v", err)
	}
	if document.Module != "fake" {
		t.Errorf("module: got %s want fake", document.Module)
	}
	if document.Database == nil || len(document.Database.Relations) != 1 {
		t.Fatalf("relations: got %+v want one relation", document.Database)
	}
	relation := document.Database.Relations[0]
	if relation.Path != "fake/thing" {
		t.Errorf("path: got %s want fake/thing", relation.Path)
	}
	if len(relation.Entities) != 2 || relation.Entities[0] != "alpha" {
		t.Errorf("entities: got %v want [alpha beta]", relation.Entities)
	}
	if relation.Dimensions[0].Key != "thing" || !relation.Dimensions[0].Subject {
		t.Errorf("subject: got %+v want thing as the subject", relation.Dimensions[0])
	}
	for _, measure := range relation.Measures {
		if measure.Key == "draft_pct" && measure.Persist {
			t.Errorf("draft_pct: got persist=true want false after Transient")
		}
		if measure.Key == "up" && measure.Kind != KindBool {
			t.Errorf("up: got kind %s want bool", measure.Kind)
		}
	}
}

func TestSchema_Registered(t *testing.T) {
	relations := Registered()
	paths := make([]string, 0, len(relations))
	for _, relation := range relations {
		paths = append(paths, relation.Path)
	}
	joined := strings.Join(paths, ",")
	if !strings.Contains(joined, "fake/summary") || !strings.Contains(joined, "fake/thing") {
		t.Fatalf("registered: got %s want the fake relations", joined)
	}
	for i := 1; i < len(paths); i++ {
		if paths[i-1] > paths[i] {
			t.Fatalf("order: got %s before %s want sorted paths", paths[i-1], paths[i])
		}
	}
}
