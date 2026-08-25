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

func TestProbe_SiblingRuleIsProbedEarlier(t *testing.T) {
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
			for _, target := range rule.Targets() {
				if target == metric.Self {
					continue
				}
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
