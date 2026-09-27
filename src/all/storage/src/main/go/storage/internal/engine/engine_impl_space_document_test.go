package engine

import (
	"bytes"
	"encoding/json"
	"go/ast"
	"go/parser"
	"go/token"
	"reflect"
	"regexp"
	"sort"
	"testing"
)

func TestEngineImplSpace_DocumentCommentMatchesTags(t *testing.T) {
	commented := commentedFieldNames(t)
	if len(commented) == 0 {
		t.Fatal("parsed no field names out of the Document doc comment, the parse itself is broken")
	}
	tagged := taggedFieldNames(
		Document{}, HostDoc{}, MountDoc{}, SpaceFigures{}, Folded{}, BackupInfo{},
	)
	if len(tagged) == 0 {
		t.Fatal("reflected no json tags, the reflection itself is broken")
	}
	assertSameSet(t, commented, tagged)
}

func TestEngineImplSpace_DocumentRoundTrip(t *testing.T) {
	index := 1
	want := Document{
		Version:   "10.200.1725",
		Mode:      "remote",
		StartedTS: "2026-09-25T02:14:07+08:00",
		DurationS: 3,
		Hosts: []HostDoc{
			{Index: &index, Label: "mad", Name: "macmini-mad", Version: "10.200.1725", State: HostStateMeasured, Mounts: []MountDoc{
				{Mount: "/", Class: ClassRoot, State: MountStateMeasured,
					Space:  &SpaceFigures{SizeBytes: 424047280128, UsedBytes: 90930360320, FreeBytes: 333116919808},
					Folded: &Folded{Identity: "/dev/nvme0n1p6", Mounts: []string{"/", "/home", "/var"}}},
				{Mount: "/share/11", Label: "share_09", Class: ClassShare, State: MountStateUnmounted, Error: "declared and not mounted [/share/11]"},
				{Mount: "/backup", Label: "backup_06", Class: ClassBackup, State: MountStateMeasured,
					Space:  &SpaceFigures{SizeBytes: 26388279066624, UsedBytes: 9895604649984, FreeBytes: 16492674416640},
					Backup: &BackupInfo{RunID: "2026-09-25_01-00-00", MeasuredTS: "2026-09-25T02:14:07+08:00"}},
			}},
			{Label: "max", Name: "macmini-max", State: HostStateUnreachable, Error: "ssh dial failed [macmini-max]"},
		},
	}
	encoded, err := json.Marshal(want)
	if err != nil {
		t.Fatal(err)
	}
	var got Document
	if err := json.Unmarshal(encoded, &got); err != nil {
		t.Fatal(err)
	}
	if !reflect.DeepEqual(got, want) {
		t.Errorf("round trip: got %+v want %+v", got, want)
	}
	if index := bytes.Index(encoded, []byte(`"index"`)); index < 0 || index > bytes.Index(encoded, []byte(`"state"`)) {
		t.Errorf("identity fields must encode before state, got %s", encoded)
	}
}

func TestEngineImplSpace_DocumentDecodesUnknownAndMissingFields(t *testing.T) {
	var got Document
	if err := json.Unmarshal([]byte(`{"version":"10.200.1725","surprise":true,"hosts":[{"label":"mad","state":"measured","mounts":[{"mount":"/","class":"root","state":"measured","surprise":{"nested":1}}]}]}`), &got); err != nil {
		t.Fatal(err)
	}
	if got.Mode != "" || got.DurationS != 0 {
		t.Errorf("absent fields: got mode %q duration %d want the zero values", got.Mode, got.DurationS)
	}
	if len(got.Hosts) != 1 || got.Hosts[0].Index != nil {
		t.Fatalf("hosts: got %+v want one host with no index", got.Hosts)
	}
	if len(got.Hosts[0].Mounts) != 1 || got.Hosts[0].Mounts[0].Space != nil {
		t.Errorf("mounts: got %+v want one mount with no space", got.Hosts[0].Mounts)
	}
}

func commentedFieldNames(t *testing.T) map[string]bool {
	t.Helper()
	fileSet := token.NewFileSet()
	file, err := parser.ParseFile(fileSet, "engine_impl_space.go", nil, parser.ParseComments)
	if err != nil {
		t.Fatal(err)
	}
	names := map[string]bool{}
	fieldPattern := regexp.MustCompile(`"(\w+)":`)
	for _, decl := range file.Decls {
		genDecl, ok := decl.(*ast.GenDecl)
		if !ok || genDecl.Doc == nil {
			continue
		}
		for _, spec := range genDecl.Specs {
			typeSpec, ok := spec.(*ast.TypeSpec)
			if !ok || typeSpec.Name.Name != "Document" {
				continue
			}
			for _, match := range fieldPattern.FindAllStringSubmatch(genDecl.Doc.Text(), -1) {
				names[match[1]] = true
			}
		}
	}
	return names
}

func taggedFieldNames(values ...any) map[string]bool {
	names := map[string]bool{}
	for _, value := range values {
		typ := reflect.TypeOf(value)
		for field := range typ.Fields() {
			tag := field.Tag.Get("json")
			if tag == "" {
				continue
			}
			for j, c := range tag {
				if c == ',' {
					tag = tag[:j]
					break
				}
			}
			names[tag] = true
		}
	}
	return names
}

func assertSameSet(t *testing.T, a, b map[string]bool) {
	t.Helper()
	var onlyInA, onlyInB []string
	for name := range a {
		if !b[name] {
			onlyInA = append(onlyInA, name)
		}
	}
	for name := range b {
		if !a[name] {
			onlyInB = append(onlyInB, name)
		}
	}
	sort.Strings(onlyInA)
	sort.Strings(onlyInB)
	if len(onlyInA) > 0 {
		t.Errorf("doc comment names fields absent from the struct tags: %v", onlyInA)
	}
	if len(onlyInB) > 0 {
		t.Errorf("struct tags carry fields the doc comment does not name: %v", onlyInB)
	}
}
