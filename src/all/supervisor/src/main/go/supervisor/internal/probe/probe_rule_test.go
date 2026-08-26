package probe

import (
	"go/ast"
	"go/parser"
	"go/token"
	"path/filepath"
	"strings"
	"supervisor/internal/metric"
	"testing"
)

func TestProbeRule_GatesCarryNoThreshold(t *testing.T) {
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

func TestProbeRule_SiblingIsProbedEarlier(t *testing.T) {
	order := map[string]int{}
	files, err := filepath.Glob("probe_*.go")
	if err != nil {
		t.Fatalf("glob: %v", err)
	}
	for _, file := range files {
		if strings.HasSuffix(file, "_test.go") {
			continue
		}
		parsed, err := parser.ParseFile(token.NewFileSet(), file, nil, 0)
		if err != nil {
			t.Fatalf("parse %s: %v", file, err)
		}
		ast.Inspect(parsed, func(node ast.Node) bool {
			call, isCall := node.(*ast.CallExpr)
			if !isCall {
				return true
			}
			name, isName := call.Fun.(*ast.Ident)
			if !isName || name.Name != "newCacheMetricTask" || len(call.Args) < 2 {
				return true
			}
			if selector, isSelector := call.Args[1].(*ast.SelectorExpr); isSelector {
				if _, seen := order[selector.Sel.Name]; !seen {
					order[selector.Sel.Name] = len(order)
				}
			}
			return true
		})
	}
	if len(order) == 0 {
		t.Fatal("found no newCacheMetricTask calls to order")
	}
	for _, id := range metric.GetIDs() {
		for _, rule := range []metric.Rule{metric.GetIDPulseRule(id), metric.GetIDTrendRule(id)} {
			for _, target := range rule.Siblings() {
				reader, readerFound := order[id.String()]
				read, readFound := order[target.String()]
				if !readerFound || !readFound {
					continue
				}
				if read >= reader {
					t.Errorf("%v: reads %v, which is probed at position %d against its own %d, so the rule sees the previous pulse",
						metric.GetIDName(id), metric.GetIDName(target), read, reader)
				}
			}
		}
	}
}

func TestProbeRule_TrendFuncMatchesTrendRule(t *testing.T) {
	trended := map[string]bool{}
	files, err := filepath.Glob("probe_*.go")
	if err != nil {
		t.Fatalf("glob: %v", err)
	}
	for _, file := range files {
		if strings.HasSuffix(file, "_test.go") {
			continue
		}
		parsed, parseErr := parser.ParseFile(token.NewFileSet(), file, nil, 0)
		if parseErr != nil {
			t.Fatalf("parse %s: %v", file, parseErr)
		}
		ast.Inspect(parsed, func(node ast.Node) bool {
			call, isCall := node.(*ast.CallExpr)
			if !isCall {
				return true
			}
			name, isName := call.Fun.(*ast.Ident)
			if !isName || name.Name != "newCacheMetricTask" || len(call.Args) < 7 {
				return true
			}
			selector, isSelector := call.Args[1].(*ast.SelectorExpr)
			if !isSelector {
				return true
			}
			last, isIdent := call.Args[len(call.Args)-1].(*ast.Ident)
			trended[selector.Sel.Name] = !isIdent || last.Name != "nil"
			return true
		})
	}
	if len(trended) == 0 {
		t.Fatal("found no newCacheMetricTask calls to read a trendFunc from")
	}
	for _, id := range metric.GetIDs() {
		probed, found := trended[id.String()]
		if !found {
			continue
		}
		declared := !metric.GetIDTrendRule(id).IsZero()
		if probed != declared {
			t.Errorf("%v: probed with a trendFunc %v but declares a trendRule %v, so the trend is silently dropped",
				metric.GetIDName(id), probed, declared)
		}
	}
}
