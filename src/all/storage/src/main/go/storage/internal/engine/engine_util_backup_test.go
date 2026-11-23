package engine

import (
	"encoding/json"
	"go/ast"
	"go/parser"
	"go/token"
	"os"
	"path/filepath"
	"reflect"
	"strconv"
	"strings"
	"testing"
)

func TestEngineUtilBackup_NewestBackupReading(t *testing.T) {
	tests := []struct {
		name          string
		runs          map[string]*backupTertiaryStatus
		expected      *backupReading
		expectedError bool
	}{
		{
			name: "newest of several runs wins",
			runs: map[string]*backupTertiaryStatus{
				"2026-09-01_01-00-00": {DiskTotalMiB: 100, DiskUsedMiB: 50, FinishedTS: "2026-09-01T02:00:00Z"},
				"2026-09-25_01-00-00": {DiskTotalMiB: 200, DiskUsedMiB: 80, FinishedTS: "2026-09-25T02:00:00Z"},
			},
			expected: &backupReading{RunID: "2026-09-25_01-00-00", MeasuredTS: "2026-09-25T02:00:00Z", TotalBytes: 200 * 1024 * 1024, UsedBytes: 80 * 1024 * 1024},
		},
		{
			name: "a newer run with no tertiary document falls to the next, not to zero",
			runs: map[string]*backupTertiaryStatus{
				"2026-09-01_01-00-00": {DiskTotalMiB: 100, DiskUsedMiB: 50, FinishedTS: "2026-09-01T02:00:00Z"},
				"2026-09-25_01-00-00": nil,
			},
			expected: &backupReading{RunID: "2026-09-01_01-00-00", MeasuredTS: "2026-09-01T02:00:00Z", TotalBytes: 100 * 1024 * 1024, UsedBytes: 50 * 1024 * 1024},
		},
		{
			name: "a disk_total_mb of zero is not a reading",
			runs: map[string]*backupTertiaryStatus{
				"2026-09-25_01-00-00": {DiskTotalMiB: 0, DiskUsedMiB: 0, FinishedTS: "2026-09-25T02:00:00Z"},
			},
			expected: nil,
		},
		{
			name:     "an empty tree",
			runs:     map[string]*backupTertiaryStatus{},
			expected: nil,
		},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			root := t.TempDir()
			for run, status := range testCase.runs {
				dir := filepath.Join(root, run, "stage", "tertiary")
				if err := os.MkdirAll(dir, 0o755); err != nil {
					t.Fatal(err)
				}
				if status == nil {
					continue
				}
				data, err := json.Marshal(status)
				if err != nil {
					t.Fatal(err)
				}
				if err := os.WriteFile(filepath.Join(dir, "status.json"), data, 0o644); err != nil {
					t.Fatal(err)
				}
			}
			got := newestBackupReading(root)
			assertBackupReading(t, got, testCase.expected)
		})
	}
}

func TestEngineUtilBackup_NewestBackupReading_UnparseableDocument(t *testing.T) {
	root := t.TempDir()
	dir := filepath.Join(root, "2026-09-25_01-00-00", "stage", "tertiary")
	if err := os.MkdirAll(dir, 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(dir, "status.json"), []byte("not json"), 0o644); err != nil {
		t.Fatal(err)
	}
	if got := newestBackupReading(root); got != nil {
		t.Errorf("got %+v want nil", got)
	}
}

func TestEngineUtilBackup_TreeMirrorsSupervisor(t *testing.T) {
	owner := filepath.Join("..", "..", "..", "..", "..", "..", "..", "supervisor", "src", "main", "go", "supervisor", "internal")
	literals := map[string]string{}
	tags := map[string]bool{}
	for _, file := range []string{"config/config.go", "probe/probe_util_backup_tree.go", "metric/metric_schema.go", "probe/probe_util_backup_summary.go"} {
		parsed, err := parser.ParseFile(token.NewFileSet(), filepath.Join(owner, file), nil, 0)
		if err != nil {
			t.Fatalf("parse supervisor source [%s] [%v]", file, err)
		}
		ast.Inspect(parsed, func(node ast.Node) bool {
			switch typed := node.(type) {
			case *ast.ValueSpec:
				for index, name := range typed.Names {
					if index >= len(typed.Values) {
						continue
					}
					value := typed.Values[index]
					if call, ok := value.(*ast.CallExpr); ok && len(call.Args) == 1 {
						value = call.Args[0]
					}
					if literal, ok := value.(*ast.BasicLit); ok && literal.Kind == token.STRING {
						unquoted, _ := strconv.Unquote(literal.Value)
						literals[name.Name] = unquoted
					}
				}
			case *ast.TypeSpec:
				if structType, ok := typed.Type.(*ast.StructType); ok && typed.Name.Name == "backupSummary" {
					for _, field := range structType.Fields.List {
						if field.Tag == nil {
							continue
						}
						unquoted, _ := strconv.Unquote(field.Tag.Value)
						tag, _, _ := strings.Cut(reflect.StructTag(unquoted).Get("json"), ",")
						tags[tag] = true
					}
				}
			}
			return true
		})
	}
	if len(literals) == 0 || len(tags) == 0 {
		t.Fatalf("parsed nothing out of supervisor, the parse itself is broken: literals [%d] tags [%d]", len(literals), len(tags))
	}
	mirrors := []struct {
		name     string
		owner    string
		expected string
	}{
		{name: "service home", owner: "DirServiceHome", expected: backupTreeServiceHome},
		{name: "module", owner: "treeModule", expected: backupTreeModule},
		{name: "backup directory", owner: "treeBackupDirectory", expected: backupTreeBackupDirectory},
		{name: "stage directory", owner: "treeStageDirectory", expected: backupTreeStageDirectory},
		{name: "tertiary stage", owner: "BackupStageTertiary", expected: backupTreeStageTertiary},
		{name: "status leaf", owner: "treeStatusLeaf", expected: backupTreeStatusLeaf},
		{name: "run pattern", owner: "treeRunPattern", expected: backupTreeRunPattern.String()},
	}
	for _, mirror := range mirrors {
		t.Run(mirror.name, func(t *testing.T) {
			got, ok := literals[mirror.owner]
			if !ok {
				t.Fatalf("%s: supervisor declares no [%s]", mirror.name, mirror.owner)
			}
			if got != mirror.expected {
				t.Errorf("%s: got %q want %q", mirror.owner, got, mirror.expected)
			}
		})
	}
	read := reflect.TypeFor[backupTertiaryStatus]()
	for field := range read.Fields() {
		if tag := field.Tag.Get("json"); !tags[tag] {
			t.Errorf("backupSummary: got no [%s] tag, storage reads it", tag)
		}
	}
}

func assertBackupReading(t *testing.T, got, expected *backupReading) {
	t.Helper()
	if (got == nil) != (expected == nil) {
		t.Fatalf("got %+v want %+v", got, expected)
	}
	if got == nil {
		return
	}
	if *got != *expected {
		t.Errorf("got %+v want %+v", *got, *expected)
	}
}
