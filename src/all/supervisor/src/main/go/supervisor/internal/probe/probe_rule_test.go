package probe

import (
	"go/ast"
	"go/parser"
	"go/token"
	"path/filepath"
	"strings"
	"testing"
)

func TestProbe_GatesCarryNoThreshold(t *testing.T) {
	files, err := filepath.Glob("probe_*.go")
	if err != nil {
		t.Fatalf("glob: %v", err)
	}
	fileSet := token.NewFileSet()
	for _, file := range files {
		if strings.HasSuffix(file, "_test.go") {
			continue
		}
		parsed, parseErr := parser.ParseFile(fileSet, file, nil, 0)
		if parseErr != nil {
			t.Fatalf("parse %s: %v", file, parseErr)
		}
		ast.Inspect(parsed, func(node ast.Node) bool {
			literal, isLiteral := node.(*ast.CompositeLit)
			if !isLiteral {
				return true
			}
			if name, isName := literal.Type.(*ast.Ident); !isName || name.Name != "gateSet" {
				return true
			}
			ast.Inspect(literal, func(inner ast.Node) bool {
				compare, isCompare := inner.(*ast.BinaryExpr)
				if !isCompare {
					return true
				}
				switch compare.Op {
				case token.LSS, token.LEQ, token.GTR, token.GEQ:
				default:
					return true
				}
				for _, side := range []ast.Expr{compare.X, compare.Y} {
					if operand, isOperand := side.(*ast.BasicLit); isOperand &&
						(operand.Kind == token.INT || operand.Kind == token.FLOAT) {
						t.Errorf("%s: got a gate comparing against the literal %s, want the threshold declared as a Bounded rule in metricBuildersByID",
							fileSet.Position(compare.Pos()), operand.Value)
					}
				}
				return true
			})
			return true
		})
	}
}
