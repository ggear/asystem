package engine

import (
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
