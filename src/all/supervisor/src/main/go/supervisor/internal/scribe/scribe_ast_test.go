package scribe

import (
	"go/ast"
	"go/parser"
	"go/token"
	"io/fs"
	"path/filepath"
	"slices"
	"strings"
	"testing"
)

func TestScribe_VerbsAreEightCharacters(t *testing.T) {
	for _, found := range verbLiterals(t, "../..") {
		if len(found.verb) != widthVerb || found.verb != strings.ToLower(found.verb) {
			t.Errorf("%s: got verb %q of %d characters, want a lower-case word of exactly %d",
				found.position, found.verb, len(found.verb), widthVerb)
		}
	}
}

type verbLiteral struct {
	position string
	verb     string
}

func verbLiterals(t *testing.T, root string) []verbLiteral {
	t.Helper()
	var found []verbLiteral
	walkGoFiles(t, root, func(position string, node ast.Node) {
		call, isCall := node.(*ast.CallExpr)
		if !isCall || len(call.Args) == 0 {
			return
		}
		index := -1
		switch function := call.Fun.(type) {
		case *ast.SelectorExpr:
			if slices.Contains([]string{"Debug", "Info", "Warn", "Error"}, function.Sel.Name) {
				index = 0
			}
		case *ast.Ident:
			if function.Name == "derived" && len(call.Args) > 1 {
				index = 1
			}
			if function.Name == "derivePulse" && len(call.Args) > 1 {
				index = 1
			}
		}
		if index < 0 {
			return
		}
		literal, isLiteral := call.Args[index].(*ast.BasicLit)
		if !isLiteral || literal.Kind != token.STRING {
			return
		}
		word := strings.Trim(literal.Value, `"`)
		if index == 1 {
			word, _, _ = strings.Cut(word, " ")
		}
		found = append(found, verbLiteral{position: position, verb: word})
	})
	return found
}

func walkGoFiles(t *testing.T, root string, visit func(position string, node ast.Node)) {
	t.Helper()
	fileSet := token.NewFileSet()
	err := filepath.WalkDir(root, func(path string, entry fs.DirEntry, err error) error {
		if err != nil {
			return err
		}
		if entry.IsDir() {
			if entry.Name() == "target" || entry.Name() == ".go" {
				return filepath.SkipDir
			}
			return nil
		}
		if !strings.HasSuffix(path, ".go") || strings.HasSuffix(path, "_test.go") {
			return nil
		}
		parsed, parseErr := parser.ParseFile(fileSet, path, nil, 0)
		if parseErr != nil {
			return parseErr
		}
		ast.Inspect(parsed, func(node ast.Node) bool {
			if node != nil {
				visit(fileSet.Position(node.Pos()).String(), node)
			}
			return true
		})
		return nil
	})
	if err != nil {
		t.Fatalf("walk %s: %v", root, err)
	}
}
