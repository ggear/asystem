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
	"strconv"
	"strings"
	"testing"
	"time"
	"unicode/utf8"

	"supervisor/internal/metric"
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
					Time:   time.Now(),
					Level:  slog.LevelInfo,
					Detail: fmt.Sprintf("message %d", i),
				})
			}
			tail := buf.Tail(testCase.tailN)
			if len(tail) != testCase.expectedCount {
				t.Fatalf("Got tail length = %d, expected %d", len(tail), testCase.expectedCount)
			}
			if testCase.pushCount > 0 && testCase.expectedCount > 0 {
				lastMsg := tail[len(tail)-1].Detail
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
			found := len(tail) > 0 && bytes.Contains([]byte(tail[0].Verb), []byte(msg))
			if found != testCase.expected {
				t.Fatalf("Got message found = %v, expected %v", found, testCase.expected)
			}
		})
	}
}

func TestScribe_BufferMinimumCapacity(t *testing.T) {
	buf := EnableBuffer(slog.LevelDebug, 0)
	Log(SourceScribe, SubjectNone, ActionRemove).Infof("minimum", time.Now(), "[1] line")
	if got := len(buf.Tail(1)); got != 1 {
		t.Fatalf("Tail() count: got %d want 1", got)
	}
}

func TestScribe_HandlerWithAttrs(t *testing.T) {
	buf := EnableBuffer(slog.LevelDebug, 1)
	logger := slog.Default().With(
		keySource, SourceScribe.String(),
		keySubject, SubjectNone.String(),
		keyAction, ActionRemove.String(),
		keyDuration, time.Millisecond,
		keyDetail, "[1] line",
	)
	logger.Info("derived")
	line := buf.Tail(1)
	if len(line) != 1 || line[0].Source != SourceScribe.String() || line[0].Action != ActionRemove.String() {
		t.Fatalf("derived logger attributes: got %+v", line)
	}
}

func TestScribe_ReconfigureClosesWriter(t *testing.T) {
	EnableBuffer(slog.LevelDebug, 1)
	reader, writer, err := os.Pipe()
	if err != nil {
		t.Fatalf("Pipe(): %v", err)
	}
	defer reader.Close()
	scribeLoggerWriter = writer
	EnableBuffer(slog.LevelDebug, 1)
	if _, err = writer.Write([]byte("closed")); err == nil {
		t.Fatal("previous writer remains open after reconfiguration")
	}
}

func TestScribe_FormatColumns(t *testing.T) {
	tests := []struct {
		name          string
		width         int
		source        string
		subject       string
		action        string
		verb          string
		expectedError bool
	}{
		{name: "happy_short_values", width: widthFile, source: "probe", subject: "host/x", action: "compute", verb: "computed", expectedError: false},
		{name: "happy_long_values", width: widthFile, source: "engine[database]", subject: "service/configured_status", action: "disconnect", verb: "faulting", expectedError: false},
		{name: "happy_narrow_shrinks_subject", width: 116, source: "engine[database]", subject: "service/configured_status", action: "disconnect", verb: "faulting", expectedError: false},
		{name: "happy_narrower_shrinks_every_column", width: 100, source: "engine[database]", subject: "service/configured_status", action: "disconnect", verb: "faulting", expectedError: false},
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
			l := layoutFor(sinkOverlay(testCase.width))
			line := wrapped(lineOf(record), l)[0]
			sourceOffset := l.time + 1 + l.level + 1
			subjectOffset := sourceOffset + l.source + 1
			actionOffset := subjectOffset + l.subject + 1
			durationOffset := actionOffset + l.action + 1
			verbOffset := durationOffset + l.duration + 1
			for _, column := range []struct {
				name   string
				offset int
				want   string
			}{
				{name: "source", offset: sourceOffset, want: head(testCase.source, l.source)},
				{name: "subject", offset: subjectOffset, want: tokens(testCase.subject, l.subject)},
				{name: "action", offset: actionOffset, want: head(testCase.action, l.action)},
				{name: "duration", offset: durationOffset, want: durationText(slog.DurationValue(time.Millisecond))},
				{name: "verb", offset: verbOffset, want: testCase.verb},
			} {
				if got := line[column.offset : column.offset+len(column.want)]; got != column.want {
					t.Errorf("%s: got %q want %q at %d", column.name, got, column.want, column.offset)
				}
			}
			if got := line[verbOffset+l.verb:]; got != " [1] example" {
				t.Errorf("detail: got %q want %q", got, " [1] example")
			}
		})
	}
}

func TestScribe_SubjectNamespace(t *testing.T) {
	tests := []struct {
		name            string
		subject         Subject
		expectedSubject string
	}{
		{name: "happy_host_rollup", subject: SubjectHost(""), expectedSubject: "host"},
		{name: "happy_named_host", subject: SubjectHost("macmini-may"), expectedSubject: "host/macmini-may"},
		{name: "happy_service_rollup", subject: SubjectService(""), expectedSubject: "service"},
		{name: "happy_named_service", subject: SubjectService("letsencrypt"), expectedSubject: "service/letsencrypt"},
		{name: "happy_host_metric", subject: SubjectMetric(metric.MetricHostUsedMemory), expectedSubject: "host/used_memory"},
		{name: "happy_service_metric", subject: SubjectMetric(metric.MetricServiceUpTime), expectedSubject: "service/up_time"},
		{name: "happy_host_topic_resolves_to_its_metric", subject: SubjectTopic("supervisor/macmini-mad/data/host/used_memory"), expectedSubject: "host/used_memory"},
		{name: "happy_service_topic_drops_the_service_name", subject: SubjectTopic("supervisor/macmini-mad/data/service/plex/up_time"), expectedSubject: "service/up_time"},
		{name: "happy_service_wildcard_resolves_to_its_metric", subject: SubjectTopic("supervisor/+/data/service/+/name"), expectedSubject: "service/name"},
		{name: "happy_status_topic_has_no_subject", subject: SubjectTopic("supervisor/macmini-mad/status"), expectedSubject: ""},
		{name: "happy_foreign_topic_has_no_subject", subject: SubjectTopic("homeassistant/switch/plex/config"), expectedSubject: ""},
		{name: "happy_none_renders_blank", subject: SubjectNone, expectedSubject: ""},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			if got := testCase.subject.String(); got != testCase.expectedSubject {
				t.Errorf("subject: got %q want %q", got, testCase.expectedSubject)
			}
		})
	}
}

func TestScribe_WrapsLongDetail(t *testing.T) {
	tests := []struct {
		name          string
		width         int
		spaced        bool
		budgets       int
		expectedLines int
	}{
		{name: "happy_short_detail_is_one_row", width: 250, spaced: true, budgets: 0, expectedLines: 1},
		{name: "happy_spaced_detail_wraps", width: 250, spaced: true, budgets: 2, expectedLines: 3},
		{name: "happy_unbroken_detail_wraps", width: 250, spaced: false, budgets: 2, expectedLines: 3},
		{name: "happy_narrow_terminal_keeps_one_row", width: 60, spaced: true, budgets: 2, expectedLines: 1},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			l := layoutFor(sinkOverlay(testCase.width))
			prefix := l.prefix() - l.verb - 1
			budget := max(l.detail, 1)
			detail := "[1] example"
			if testCase.budgets > 0 {
				length := budget*testCase.budgets + 10
				detail = strings.Repeat("x", length)
				if testCase.spaced {
					detail = strings.TrimSpace(strings.Repeat("word ", length/5))
				}
			}
			record := slog.NewRecord(time.Now(), slog.LevelWarn, "faulting", 0)
			record.AddAttrs(
				slog.String(keySource, "probe"),
				slog.String(keySubject, "host/used_home_space"),
				slog.String(keyAction, "sample"),
				slog.Duration(keyDuration, time.Millisecond),
				slog.String(keyDetail, detail),
			)
			rows := OverlayLines(lineOf(record), testCase.width)
			if len(rows) != testCase.expectedLines {
				t.Fatalf("rows: got %d want %d", len(rows), testCase.expectedLines)
			}
			carried := ""
			for index, row := range rows {
				if len(rows) > 1 && len(row) > testCase.width {
					t.Errorf("width: got %d want at most %d for row %d", len(row), testCase.width, index)
				}
				if index > 0 {
					if got := row[:prefix]; got != rows[0][:prefix] {
						t.Errorf("prefix: got %q want %q for row %d", got, rows[0][:prefix], index)
					}
					if got := row[prefix : prefix+spanVerb.ideal]; strings.TrimSpace(got) != "" {
						t.Errorf("verb: got %q want blank for row %d", got, index)
					}
				}
				carried += strings.TrimSuffix(row[prefix+spanVerb.ideal+1:], clipMarker)
			}
			if got := strings.Join(strings.Fields(carried), " "); got != strings.Join(strings.Fields(detail), " ") {
				t.Errorf("detail: got %q want %q", got, detail)
			}
		})
	}
}

func TestScribe_WrapsMultibyteDetail(t *testing.T) {
	tests := []struct {
		name          string
		width         int
		detail        string
		expectedError bool
	}{
		{name: "happy_unbroken_multibyte_detail_wraps", width: 250, detail: strings.Repeat("\u00b0", 400), expectedError: false},
		{name: "happy_spaced_multibyte_detail_wraps", width: 250, detail: strings.TrimSpace(strings.Repeat("\u00b0C \u00b0C ", 200)), expectedError: false},
		{name: "happy_wide_multibyte_detail_wraps", width: 250, detail: strings.Repeat("\u4e16\u754c", 300), expectedError: false},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			record := slog.NewRecord(time.Now(), slog.LevelWarn, "computed", 0)
			record.AddAttrs(
				slog.String(keySource, "probe"),
				slog.String(keySubject, "host/warn_temperature"),
				slog.String(keyAction, "compute"),
				slog.Duration(keyDuration, time.Millisecond),
				slog.String(keyDetail, testCase.detail),
			)
			l := layoutFor(sinkOverlay(testCase.width))
			prefix := l.prefix() - l.verb - 1
			rows := OverlayLines(lineOf(record), testCase.width)
			if len(rows) < 2 {
				t.Fatalf("rows: got %d want at least 2", len(rows))
			}
			carried := ""
			for index, row := range rows {
				if !utf8.ValidString(row) {
					t.Errorf("encoding: got invalid utf8 %q for row %d", row, index)
				}
				carried += strings.TrimSuffix(row[prefix+spanVerb.ideal+1:], clipMarker)
			}
			if got := strings.Join(strings.Fields(carried), " "); got != strings.Join(strings.Fields(testCase.detail), " ") {
				t.Errorf("detail: got %q want %q", got, testCase.detail)
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
			wantWidth := spanDuration.ideal
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
			line := wrapped(lineOf(record), layoutFor(sinkFile()))[0]
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

func TestScribe_DetailLeadsWithValue(t *testing.T) {
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
			for _, detail := range detailCalls(t, testCase.root) {
				if strings.HasPrefix(detail.text, "[") || strings.HasPrefix(detail.text, "%s") {
					continue
				}
				t.Errorf("%s: got detail %q, want it to lead with a bracketed value", detail.position, detail.text)
			}
		})
	}
}

type detailCall struct {
	position string
	text     string
}

func detailCalls(t *testing.T, root string) []detailCall {
	t.Helper()
	var details []detailCall
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
			call, ok := node.(*ast.CallExpr)
			if !ok || len(call.Args) < 3 {
				return true
			}
			selector, ok := call.Fun.(*ast.SelectorExpr)
			if !ok || !slices.Contains([]string{"Debugf", "Infof", "Warnf", "Errorf"}, selector.Sel.Name) {
				return true
			}

			if pkg, ok := selector.X.(*ast.Ident); ok && pkg.Name == "fmt" {

				return true

			}
			if _, ok := call.Args[0].(*ast.BasicLit); !ok {
				return true
			}
			literal, ok := call.Args[2].(*ast.BasicLit)
			if !ok || literal.Kind != token.STRING {
				return true
			}
			text, unquoteErr := strconv.Unquote(literal.Value)
			if unquoteErr != nil {
				return true
			}
			details = append(details, detailCall{position: fileSet.Position(literal.Pos()).String(), text: text})
			return true
		})
		return nil
	})
	if err != nil {
		t.Fatalf("walk %s: %v", root, err)
	}
	if len(details) == 0 {
		t.Fatalf("walk %s: got 0 detail literals, want the logging call sites", root)
	}
	return details
}

func TestScribe_SetFilters(t *testing.T) {
	tests := []struct {
		name          string
		source        string
		subject       string
		action        string
		expectedError bool
	}{
		{
			name:          "happy_empty_means_no_filter",
			expectedError: false,
		},
		{
			name:          "happy_valid_source_prefix",
			source:        "probe,engine",
			expectedError: false,
		},
		{
			name:          "happy_valid_action_prefix",
			action:        "compute,census",
			expectedError: false,
		},
		{
			name:          "happy_valid_source_abbreviation",
			source:        "d",
			expectedError: false,
		},
		{
			name:          "happy_open_subject_never_validated",
			subject:       "host/use",
			expectedError: false,
		},
		{
			name:          "sad_unknown_source_prefix",
			source:        "xyz",
			expectedError: true,
		},
		{
			name:          "sad_unknown_action_prefix",
			action:        "xyz",
			expectedError: true,
		},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			t.Cleanup(ResetFilters)
			err := SetFilters(testCase.source, testCase.subject, testCase.action)
			if (err != nil) != testCase.expectedError {
				t.Fatalf("SetFilters: got err = %v, expectedError %v", err, testCase.expectedError)
			}
		})
	}
}

func TestScribe_Allowed(t *testing.T) {
	tests := []struct {
		name          string
		source        string
		subject       string
		action        string
		recordSource  string
		recordSubject string
		recordAction  string
		expected      bool
		expectedError bool
	}{
		{
			name:          "happy_no_filters_allows_everything",
			recordSource:  "probe",
			recordSubject: "host/used_memory",
			recordAction:  "compute",
			expected:      true,
			expectedError: false,
		},
		{
			name:          "happy_source_matches",
			source:        "probe",
			recordSource:  "probe",
			recordSubject: "host/used_memory",
			recordAction:  "compute",
			expected:      true,
			expectedError: false,
		},
		{
			name:          "happy_source_mismatches",
			source:        "engine",
			recordSource:  "probe",
			recordSubject: "host/used_memory",
			recordAction:  "compute",
			expected:      false,
			expectedError: false,
		},
		{
			name:          "happy_subject_prefix_matches",
			subject:       "host/use",
			recordSource:  "probe",
			recordSubject: "host/used_memory",
			recordAction:  "compute",
			expected:      true,
			expectedError: false,
		},
		{
			name:          "happy_subject_prefix_mismatches",
			subject:       "service/",
			recordSource:  "probe",
			recordSubject: "host/used_memory",
			recordAction:  "compute",
			expected:      false,
			expectedError: false,
		},
		{
			name:          "happy_action_or_within_dimension",
			action:        "sample,compute",
			recordSource:  "probe",
			recordSubject: "host/used_memory",
			recordAction:  "compute",
			expected:      true,
			expectedError: false,
		},
		{
			name:          "happy_and_across_dimensions",
			source:        "probe",
			action:        "connect",
			recordSource:  "probe",
			recordSubject: "host/used_memory",
			recordAction:  "compute",
			expected:      false,
			expectedError: false,
		},
		{
			name:          "happy_case_insensitive",
			source:        "PROBE",
			recordSource:  "probe",
			recordSubject: "host/used_memory",
			recordAction:  "compute",
			expected:      true,
			expectedError: false,
		},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			t.Cleanup(ResetFilters)
			if err := SetFilters(testCase.source, testCase.subject, testCase.action); (err != nil) != testCase.expectedError {
				t.Fatalf("SetFilters: got err = %v, expectedError %v", err, testCase.expectedError)
			}
			if got := allowed(testCase.recordSource, testCase.recordSubject, testCase.recordAction); got != testCase.expected {
				t.Errorf("allowed: got %v want %v", got, testCase.expected)
			}
		})
	}
}

func TestScribe_VerbsAreEightCharacters(t *testing.T) {
	for _, found := range verbLiterals(t, "../..") {
		if len(found.verb) != spanVerb.ideal || found.verb != strings.ToLower(found.verb) {
			t.Errorf("%s: got verb %q of %d characters, want a lower-case word of exactly %d",
				found.position, found.verb, len(found.verb), spanVerb.ideal)
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
			pkg, isPkg := function.X.(*ast.Ident)
			if slices.Contains([]string{"Debugf", "Infof", "Warnf", "Errorf"}, function.Sel.Name) && !(isPkg && pkg.Name == "fmt") {
				index = 0
			}
		case *ast.Ident:
			if function.Name == "derivedf" && len(call.Args) > 1 {
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

func TestScribe_LogFilePID(t *testing.T) {
	tests := []struct {
		name        string
		file        string
		expectedPID int
		expectedOK  bool
	}{
		{name: "happy current log carries its pid", file: "serve-pid-4321.log", expectedPID: 4321, expectedOK: true},
		{name: "happy rotated log carries the pid of the run that wrote it", file: "watch-pid-77-2026-08-26T14-00-00.000.log.gz", expectedPID: 77, expectedOK: true},
		{name: "sad marker missing", file: "serve.log", expectedPID: 0, expectedOK: false},
		{name: "sad marker carries no digits", file: "serve-pid-.log", expectedPID: 0, expectedOK: false},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			pid, ok := logFilePID(testCase.file)
			if pid != testCase.expectedPID || ok != testCase.expectedOK {
				t.Errorf("pid: got %d,%v want %d,%v", pid, ok, testCase.expectedPID, testCase.expectedOK)
			}
		})
	}
}

func TestScribe_PurgeLogFiles(t *testing.T) {
	dir := t.TempDir()
	keep := filepath.Join(dir, fmt.Sprintf("serve-pid-%d.log", os.Getpid()))
	files := []string{
		keep,
		filepath.Join(dir, fmt.Sprintf("serve-pid-%d-2026-08-26T14-00-00.000.log.gz", os.Getpid())),
		filepath.Join(dir, "serve-pid-999999.log"),
		filepath.Join(dir, "watch-pid-999998.log.gz"),
		filepath.Join(dir, fmt.Sprintf("watch-pid-%d-2026-08-26T02-26-08.340.log.gz", os.Getppid())),
		filepath.Join(dir, fmt.Sprintf("watch-pid-%d.log", os.Getppid())),
		filepath.Join(dir, "notes.txt"),
	}
	for _, file := range files {
		if err := os.WriteFile(file, []byte("x"), 0o600); err != nil {
			t.Fatalf("write %s: %v", file, err)
		}
	}
	purgeLogFiles(keep)
	expected := map[string]bool{
		keep:                            true,
		filepath.Join(dir, "notes.txt"): true,
		filepath.Join(dir, fmt.Sprintf("watch-pid-%d-2026-08-26T02-26-08.340.log.gz", os.Getppid())): true,
		filepath.Join(dir, fmt.Sprintf("watch-pid-%d.log", os.Getppid())):                            true,
	}
	for _, file := range files {
		_, err := os.Stat(file)
		if expected[file] && err != nil {
			t.Errorf("kept: %s got removed", filepath.Base(file))
		}
		if !expected[file] && err == nil {
			t.Errorf("purged: %s got kept", filepath.Base(file))
		}
	}
}

func TestScribe_FlattensDetailLineBreaks(t *testing.T) {
	tests := []struct {
		name          string
		detail        string
		expectedRows  int
		expectedError bool
	}{
		{name: "happy_joined_error_newlines_flatten", detail: "read failed [sdb]\nread failed [sdc]", expectedRows: 1, expectedError: false},
		{name: "happy_carriage_returns_and_tabs_flatten", detail: "read failed [sdb]\r\n\tread failed [sdc]", expectedRows: 1, expectedError: false},
		{name: "happy_long_joined_error_wraps_without_breaks", detail: strings.TrimSpace(strings.Repeat("read failed at node [/dev/sdb] with status [4]\n", 12)), expectedRows: 4, expectedError: false},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			buffer := &bytes.Buffer{}
			restore := slog.Default()
			slog.SetDefault(slog.New(&streamHandler{level: slog.LevelDebug, writer: buffer, sink: sinkFile()}))
			defer slog.SetDefault(restore)
			Log(SourceProbe, SubjectMetric(metric.MetricHostUsedDriveLife), ActionSample).Warnf("excluded", time.Now(), "%s", testCase.detail)
			rows := strings.Split(strings.TrimSuffix(buffer.String(), "\n"), "\n")[1:]
			if len(rows) != testCase.expectedRows {
				t.Fatalf("rows: got %d want %d", len(rows), testCase.expectedRows)
			}
			for index, row := range rows {
				if strings.ContainsAny(row, "\r\t") {
					t.Errorf("breaks: got %q with a control character for row %d", row, index)
				}
				if utf8.RuneCountInString(row) > widthFile {
					t.Errorf("width: got %d want at most %d for row %d", utf8.RuneCountInString(row), widthFile, index)
				}
			}
		})
	}
}

func TestScribe_ClipsSubjectToColumn(t *testing.T) {
	tests := []struct {
		name            string
		subject         string
		expectedSubject string
		expectedError   bool
	}{
		{name: "happy_short_subject_is_untouched", subject: "host/used_memory", expectedSubject: "host/used_memory", expectedError: false},
		{name: "happy_long_subject_keeps_its_underscored_token", subject: "supervisor/macmini-mad/data/service/plex/backup_status", expectedSubject: "~status", expectedError: false},
		{name: "happy_long_subject_keeps_its_hyphenated_token", subject: "supervisor/data/host/raspberrypi-jen", expectedSubject: "~jen", expectedError: false},
		{name: "happy_long_subject_without_a_token_keeps_its_tail", subject: "supervisorsupervisorsupervisor/temperature", expectedSubject: "~orsupervisor/temperature", expectedError: false},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			record := slog.NewRecord(time.Now(), slog.LevelDebug, "snapshot", 0)
			record.AddAttrs(
				slog.String(keySource, "probe"),
				slog.String(keySubject, testCase.subject),
				slog.String(keyAction, "discover"),
				slog.Duration(keyDuration, 6*time.Millisecond),
				slog.String(keyDetail, strings.Repeat("detail ", 60)),
			)
			l := layoutFor(sinkFile())
			rows := wrapped(lineOf(record), l)
			if len(rows) < 2 {
				t.Fatalf("rows: got %d want at least 2", len(rows))
			}
			subjectOffset := l.time + 1 + l.level + 1 + l.source + 1
			prefix := subjectOffset + l.subject + 1 + l.action + 1 + l.duration
			for index, row := range rows {
				column := string([]rune(row)[subjectOffset : subjectOffset+l.subject])
				if strings.TrimRight(column, " ") != testCase.expectedSubject {
					t.Errorf("column: got %q want %q for row %d", column, testCase.expectedSubject, index)
				}
				if utf8.RuneCountInString(row) > widthFile {
					t.Errorf("width: got %d want at most %d for row %d", utf8.RuneCountInString(row), widthFile, index)
				}
				if index > 0 && strings.TrimSpace(string([]rune(row)[prefix:prefix+1+spanVerb.ideal])) != "" {
					t.Errorf("verb: got %q want blank for continuation row %d", string([]rune(row)[prefix:prefix+1+spanVerb.ideal]), index)
				}
			}
		})
	}
}

func TestScribe_BufferFrom(t *testing.T) {
	tests := []struct {
		name            string
		capacity        int
		pushCount       int
		sequence        uint64
		window          int
		expectedFirst   string
		expectedCount   int
		expectedAnchor  uint64
		expectedOldest  uint64
		expectedDropped bool
		expectedError   bool
	}{
		{
			name:            "happy_page_from_the_oldest",
			capacity:        50,
			pushCount:       10,
			sequence:        0,
			window:          4,
			expectedFirst:   "message 0",
			expectedCount:   4,
			expectedAnchor:  0,
			expectedOldest:  0,
			expectedDropped: false,
			expectedError:   false,
		},
		{
			name:            "happy_page_from_the_middle",
			capacity:        50,
			pushCount:       10,
			sequence:        4,
			window:          4,
			expectedFirst:   "message 4",
			expectedCount:   4,
			expectedAnchor:  4,
			expectedOldest:  0,
			expectedDropped: false,
			expectedError:   false,
		},
		{
			name:            "happy_window_clipped_by_the_newest",
			capacity:        50,
			pushCount:       10,
			sequence:        8,
			window:          4,
			expectedFirst:   "message 8",
			expectedCount:   2,
			expectedAnchor:  8,
			expectedOldest:  0,
			expectedDropped: false,
			expectedError:   false,
		},
		{
			name:            "happy_caught_up_returns_nothing",
			capacity:        50,
			pushCount:       10,
			sequence:        10,
			window:          4,
			expectedFirst:   "",
			expectedCount:   0,
			expectedAnchor:  10,
			expectedOldest:  0,
			expectedDropped: false,
			expectedError:   false,
		},
		{
			name:            "happy_rolled_past_the_anchor",
			capacity:        4,
			pushCount:       10,
			sequence:        0,
			window:          4,
			expectedFirst:   "message 6",
			expectedCount:   4,
			expectedAnchor:  6,
			expectedOldest:  6,
			expectedDropped: true,
			expectedError:   false,
		},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			buf := &LogBuffer{lines: make([]LogLine, testCase.capacity)}
			for i := range testCase.pushCount {
				buf.Push(LogLine{Time: time.Now(), Level: slog.LevelInfo, Detail: fmt.Sprintf("message %d", i)})
			}
			lines, anchor := buf.From(testCase.sequence, testCase.window)
			if len(lines) != testCase.expectedCount {
				t.Fatalf("From() count: got %d want %d", len(lines), testCase.expectedCount)
			}
			if anchor != testCase.expectedAnchor {
				t.Errorf("From() anchor: got %d want %d", anchor, testCase.expectedAnchor)
			}
			if len(lines) > 0 && lines[0].Detail != testCase.expectedFirst {
				t.Errorf("From() first: got %q want %q", lines[0].Detail, testCase.expectedFirst)
			}
			if buf.Oldest() != testCase.expectedOldest {
				t.Errorf("Oldest(): got %d want %d", buf.Oldest(), testCase.expectedOldest)
			}
			if dropped := anchor > testCase.sequence; dropped != testCase.expectedDropped {
				t.Errorf("dropped: got %v want %v", dropped, testCase.expectedDropped)
			}
			if buf.Version() != uint64(testCase.pushCount) {
				t.Errorf("Version(): got %d want %d", buf.Version(), testCase.pushCount)
			}
		})
	}
}
