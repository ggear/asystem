package scribe

import (
	"bytes"
	"fmt"
	"go/ast"
	"go/parser"
	"go/token"
	"io/fs"
	"log/slog"
	"os"
	"path/filepath"
	"slices"
	"strings"
	"testing"
	"time"
)

func TestScribe_Stdout(t *testing.T) {
	tests := []struct {
		name     string
		setup    func()
		logFunc  func(string)
		expected bool
	}{
		{
			name:     "happy_debug_enabled",
			setup:    func() { EnableStdout(slog.LevelDebug) },
			logFunc:  func(message string) { slog.Debug(message) },
			expected: true,
		},
		{
			name:     "happy_level_too_high",
			setup:    func() { EnableStdout(9) },
			logFunc:  func(message string) { slog.Error(message) },
			expected: false,
		},
		{
			name:     "happy_re_enabled",
			setup:    func() { EnableStdout(slog.LevelDebug) },
			logFunc:  func(message string) { slog.Debug(message) },
			expected: true,
		},
		{
			name:     "happy_disabled",
			setup:    func() { Disable() },
			logFunc:  func(message string) { slog.Error(message) },
			expected: false,
		},
	}
	for index, testCase := range tests {
		testCase := testCase
		message := fmt.Sprintf("Expected log message %d", index)
		if !testCase.expected {
			message = fmt.Sprintf("UNEXPECTED LOG MESSAGE %d!!!!", index)
		}
		t.Run(testCase.name, func(t *testing.T) {
			testCase.setup()
			t.Logf("Log in mode [%s] and level [%v]", Mode(), Level())
			testCase.logFunc(message)
		})
	}
}

func TestScribe_File(t *testing.T) {
	t.Setenv("HOME", t.TempDir())
	tests := []struct {
		name     string
		setup    func(string) error
		logFunc  func(string)
		expected bool
	}{
		{
			name:     "happy_debug_enabled",
			setup:    func(cmd string) error { return EnableFile(slog.LevelDebug, cmd, 10, 7, 30) },
			logFunc:  func(message string) { slog.Debug(message) },
			expected: true,
		},
		{
			name:     "happy_level_too_high",
			setup:    func(cmd string) error { return EnableFile(9, cmd, 10, 7, 30) },
			logFunc:  func(message string) { slog.Error(message) },
			expected: false,
		},
		{
			name:     "happy_re_enabled",
			setup:    func(cmd string) error { return EnableFile(slog.LevelDebug, cmd, 10, 7, 30) },
			logFunc:  func(message string) { slog.Debug(message) },
			expected: true,
		},
		{
			name:     "happy_disabled",
			setup:    func(cmd string) error { Disable(); return nil },
			logFunc:  func(message string) { slog.Error(message) },
			expected: false,
		},
	}
	logDir := logDir()
	for index, testCase := range tests {
		testCase := testCase
		message := fmt.Sprintf("exp%d", index)
		if !testCase.expected {
			message = fmt.Sprintf("bad%d", index)
		}
		cmdName := fmt.Sprintf("supervisor-test-%d", index)
		logPath := filepath.Join(logDir, fmt.Sprintf("%s-pid-%d.log", cmdName, os.Getpid()))
		t.Run(testCase.name, func(t *testing.T) {
			_ = os.Remove(logPath)
			if err := testCase.setup(cmdName); err != nil {
				t.Fatalf("Got err = %v, expected nil", err)
			}
			t.Logf("Log in mode [%s] and level [%v]", Mode(), Level())
			testCase.logFunc(message)
			content, err := os.ReadFile(logPath)
			if err != nil {
				if !testCase.expected && os.IsNotExist(err) {
					return
				}
				t.Fatalf("ReadFile failed: %v", err)
			}
			contains := bytes.Contains(content, []byte(message))
			if testCase.expected && !contains {
				t.Fatalf("Got log content = %q, expected to contain %q", string(content), message)
			}
			if !testCase.expected && contains {
				t.Fatalf("Got log content contains %q, expected not to", message)
			}
		})
	}
}

func TestScribe_Buffer(t *testing.T) {
	tests := []struct {
		name          string
		pushCount     int
		tailN         int
		expectedCount int
		expectedError bool
	}{
		{
			name:          "happy_single_push",
			pushCount:     1,
			tailN:         10,
			expectedCount: 1,
			expectedError: false,
		},
		{
			name:          "happy_tail_less_than_count",
			pushCount:     10,
			tailN:         3,
			expectedCount: 3,
			expectedError: false,
		},
		{
			name:          "happy_tail_more_than_count",
			pushCount:     5,
			tailN:         10,
			expectedCount: 5,
			expectedError: false,
		},
		{
			name:          "happy_wrap_around",
			pushCount:     80,
			tailN:         50,
			expectedCount: 50,
			expectedError: false,
		},
		{
			name:          "happy_exact_capacity",
			pushCount:     50,
			tailN:         50,
			expectedCount: 50,
			expectedError: false,
		},
		{
			name:          "happy_empty_tail",
			pushCount:     0,
			tailN:         10,
			expectedCount: 0,
			expectedError: false,
		},
		{
			name:          "happy_tail_zero",
			pushCount:     10,
			tailN:         0,
			expectedCount: 0,
			expectedError: false,
		},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			buf := &LogBuffer{lines: make([]LogLine, 50)}
			for i := range testCase.pushCount {
				buf.Push(LogLine{
					Time:    time.Now(),
					Level:   slog.LevelInfo,
					Message: fmt.Sprintf("message %d", i),
				})
			}
			tail := buf.Tail(testCase.tailN)
			if len(tail) != testCase.expectedCount {
				t.Fatalf("Got tail length = %d, expected %d", len(tail), testCase.expectedCount)
			}
			if testCase.pushCount > 0 && testCase.expectedCount > 0 {
				lastMsg := tail[len(tail)-1].Message
				expectedMsg := fmt.Sprintf("message %d", testCase.pushCount-1)
				if lastMsg != expectedMsg {
					t.Fatalf("Got last message = %q, expected %q", lastMsg, expectedMsg)
				}
			}
			expectedVersion := uint64(testCase.pushCount)
			if buf.Version() != expectedVersion {
				t.Fatalf("Got version = %d, expected %d", buf.Version(), expectedVersion)
			}
		})
	}
}

func TestScribe_BufferHandler(t *testing.T) {
	tests := []struct {
		name          string
		level         slog.Level
		logFunc       func(string)
		expected      bool
		expectedError bool
	}{
		{
			name:          "happy_debug_captured",
			level:         slog.LevelDebug,
			logFunc:       func(msg string) { slog.Debug(msg) },
			expected:      true,
			expectedError: false,
		},
		{
			name:          "happy_info_captured",
			level:         slog.LevelDebug,
			logFunc:       func(msg string) { slog.Info(msg) },
			expected:      true,
			expectedError: false,
		},
		{
			name:          "happy_error_captured",
			level:         slog.LevelDebug,
			logFunc:       func(msg string) { slog.Error(msg) },
			expected:      true,
			expectedError: false,
		},
		{
			name:          "happy_filtered_by_level",
			level:         slog.LevelError,
			logFunc:       func(msg string) { slog.Debug(msg) },
			expected:      false,
			expectedError: false,
		},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			buf := EnableBuffer(testCase.level, 50)
			msg := "marker"
			testCase.logFunc(msg)
			tail := buf.Tail(1)
			found := len(tail) > 0 && bytes.Contains([]byte(tail[0].Message), []byte(msg))
			if found != testCase.expected {
				t.Fatalf("Got message found = %v, expected %v", found, testCase.expected)
			}
		})
	}
}

func TestScribe_FormatColumns(t *testing.T) {
	sourceOffset := 0
	subjectOffset := widthSource + 1
	actionOffset := subjectOffset + widthSubject + 1
	durationOffset := actionOffset + widthAction + 1
	verbOffset := durationOffset + widthDuration + 1
	tests := []struct {
		name    string
		source  string
		subject string
		action  string
		verb    string
	}{
		{name: "happy_short_values", source: "probe", subject: "host/x", action: "compute", verb: "computed"},
		{name: "happy_long_values", source: "database", subject: "service/configured_status", action: "disconnect", verb: "faulting"},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			record := slog.NewRecord(time.Now(), slog.LevelInfo, testCase.verb, 0)
			record.AddAttrs(
				slog.String(keySource, testCase.source),
				slog.String(keySubject, testCase.subject),
				slog.String(keyAction, testCase.action),
				slog.Duration(keyDuration, time.Millisecond),
				slog.String(keyDetail, "[1] example"),
			)
			line := format(record)
			if got := line[sourceOffset : sourceOffset+len(testCase.source)]; got != testCase.source {
				t.Errorf("source: got %q want %q at %d", got, testCase.source, sourceOffset)
			}
			if got := line[subjectOffset : subjectOffset+len(testCase.subject)]; got != testCase.subject {
				t.Errorf("subject: got %q want %q at %d", got, testCase.subject, subjectOffset)
			}
			if got := line[actionOffset : actionOffset+len(testCase.action)]; got != testCase.action {
				t.Errorf("action: got %q want %q at %d", got, testCase.action, actionOffset)
			}
			if got := line[verbOffset : verbOffset+len(testCase.verb)]; got != testCase.verb {
				t.Errorf("verb: got %q want %q at %d", got, testCase.verb, verbOffset)
			}
			wantDuration := durationText(slog.DurationValue(time.Millisecond))
			if got := line[durationOffset : durationOffset+widthDuration]; got != wantDuration {
				t.Errorf("duration: got %q want %q at %d", got, wantDuration, durationOffset)
			}
		})
	}
}

func TestScribe_FormatDuration(t *testing.T) {
	tests := []struct {
		name          string
		value         time.Duration
		expected      string
		expectedError bool
	}{
		{
			name:          "happy_sub_millisecond_floors_to_zero",
			value:         time.Microsecond,
			expected:      "0ms",
			expectedError: false,
		},
		{
			name:          "happy_milliseconds",
			value:         104 * time.Millisecond,
			expected:      "104ms",
			expectedError: false,
		},
		{
			name:          "happy_milliseconds_hold_to_the_ladder",
			value:         9999 * time.Millisecond,
			expected:      "9999ms",
			expectedError: false,
		},
		{
			name:          "happy_seconds_past_the_ladder",
			value:         90 * time.Second,
			expected:      "90s",
			expectedError: false,
		},
		{
			name:          "happy_minutes_past_the_ladder",
			value:         5 * time.Hour,
			expected:      "300m",
			expectedError: false,
		},
		{
			name:          "happy_hours_past_the_ladder",
			value:         200 * time.Hour,
			expected:      "200h",
			expectedError: false,
		},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			got := durationText(slog.DurationValue(testCase.value))
			wantWidth := widthDuration
			if size := len(testCase.expected); size > wantWidth {
				wantWidth = size
			}
			if len(got) != wantWidth {
				t.Errorf("width: got %d want %d", len(got), wantWidth)
			}
			if !strings.HasSuffix(got, testCase.expected) {
				t.Errorf("value: got %q want suffix %q", got, testCase.expected)
			}
		})
	}
}

func TestScribe_FormatDetailIsLast(t *testing.T) {
	tests := []struct {
		name          string
		attrs         []slog.Attr
		expectedError bool
	}{
		{
			name:          "happy_detail_only",
			attrs:         []slog.Attr{slog.String(keyDetail, "a [1] b")},
			expectedError: false,
		},
		{
			name:          "happy_detail_after_columns",
			attrs:         []slog.Attr{slog.String(keyDetail, "a [1] b"), slog.String(keySource, "c"), slog.Duration(keyDuration, 0)},
			expectedError: false,
		},
		{
			name:          "happy_detail_after_unknown_key",
			attrs:         []slog.Attr{slog.String(keyDetail, "a [1] b"), slog.Int("unknown", 1)},
			expectedError: false,
		},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			record := slog.NewRecord(time.Now(), slog.LevelInfo, "computed", 0)
			record.AddAttrs(testCase.attrs...)
			line := format(record)
			if !strings.HasSuffix(line, " a [1] b") {
				t.Errorf("detail: got %q want it to end the line", line)
			}
		})
	}
}

func TestScribe_NoDirectLogging(t *testing.T) {
	tests := []struct {
		name          string
		root          string
		expectedError bool
	}{
		{
			name:          "happy_module",
			root:          "../..",
			expectedError: false,
		},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			calls := logCalls(t, testCase.root)
			for _, call := range calls {
				t.Errorf("%s: got a direct slog.%s call, want a scribe.Log logger", call.position, call.level)
			}
		})
	}
}

type logCall struct {
	position string
	level    string
}

func logCalls(t *testing.T, root string) []logCall {
	t.Helper()
	var calls []logCall
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
		if !strings.HasSuffix(path, ".go") || strings.HasSuffix(path, "_test.go") || strings.Contains(path, "internal/scribe") {
			return nil
		}
		parsed, parseErr := parser.ParseFile(fileSet, path, nil, 0)
		if parseErr != nil {
			return parseErr
		}
		ast.Inspect(parsed, func(node ast.Node) bool {
			call, ok := node.(*ast.CallExpr)
			if !ok {
				return true
			}
			selector, ok := call.Fun.(*ast.SelectorExpr)
			if !ok {
				return true
			}
			pkg, ok := selector.X.(*ast.Ident)
			if !ok || pkg.Name != "slog" {
				return true
			}
			if !slices.Contains([]string{"Debug", "Info", "Warn", "Error"}, selector.Sel.Name) {
				return true
			}
			calls = append(calls, logCall{position: fileSet.Position(call.Pos()).String(), level: selector.Sel.Name})
			return true
		})
		return nil
	})
	if err != nil {
		t.Fatalf("walk %s: %v", root, err)
	}
	return calls
}
