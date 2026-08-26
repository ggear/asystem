package scribe

import (
	"context"
	"fmt"
	"io"
	"log/slog"
	"os"
	"path/filepath"
	"runtime"
	"slices"
	"strings"
	"sync"
	"time"
	"unicode/utf8"

	"gopkg.in/natefinch/lumberjack.v2"

	"supervisor/internal/metric"
)

const (
	logDirUser        = "/tmp/supervisor"
	logDirUserMac     = "Library/Logs/supervisor"
	logDirRoot        = "/var/log/supervisor"
	timeLayout        = "01-02T15:04:05"
	overlayTimeLayout = "15:04:05"
)

func EnableStdout(level slog.Level) {
	scribeLoggerMutex.Lock()
	defer scribeLoggerMutex.Unlock()
	scribeLoggerLevel = level
	scribeLoggerMode = "stdout"
	scribeLoggerInstance = slog.New(&streamHandler{level: level, writer: os.Stdout})
	slog.SetDefault(scribeLoggerInstance)
}

func EnableFile(level slog.Level, cmd string, maxSizeMB, maxBackups, maxAgeDays int) error {
	writer, err := fileWriter(cmd, maxSizeMB, maxBackups, maxAgeDays)
	if err != nil {
		return err
	}
	scribeLoggerMutex.Lock()
	defer scribeLoggerMutex.Unlock()
	scribeLoggerLevel = level
	scribeLoggerMode = "file"
	scribeLoggerInstance = slog.New(&streamHandler{level: level, writer: writer})
	slog.SetDefault(scribeLoggerInstance)
	return nil
}

func EnableStdoutAndFile(level slog.Level, cmd string, maxSizeMB, maxBackups, maxAgeDays int) error {
	writer, err := fileWriter(cmd, maxSizeMB, maxBackups, maxAgeDays)
	if err != nil {
		return err
	}
	scribeLoggerMutex.Lock()
	defer scribeLoggerMutex.Unlock()
	scribeLoggerLevel = level
	scribeLoggerMode = "stdout+file"
	multi := io.MultiWriter(os.Stdout, writer)
	scribeLoggerInstance = slog.New(&streamHandler{level: level, writer: multi})
	slog.SetDefault(scribeLoggerInstance)
	return nil
}

func Disable() {
	scribeLoggerMutex.Lock()
	defer scribeLoggerMutex.Unlock()
	scribeLoggerMode = "disabled"
	scribeLoggerInstance = slog.New(&streamHandler{level: slog.LevelError + 1, writer: io.Discard})
	slog.SetDefault(scribeLoggerInstance)
}

func EnableBuffer(level slog.Level, capacity int) *LogBuffer {
	scribeLoggerMutex.Lock()
	defer scribeLoggerMutex.Unlock()
	scribeLoggerLevel = level
	scribeLoggerMode = "buffer"
	buf := &LogBuffer{lines: make([]LogLine, capacity)}
	scribeLoggerInstance = slog.New(&bufferHandler{level: level, buffer: buf})
	slog.SetDefault(scribeLoggerInstance)
	return buf
}

func EnableBufferAndFile(level slog.Level, cmd string, capacity, maxSizeMB, maxBackups, maxAgeDays int) (*LogBuffer, error) {
	writer, err := fileWriter(cmd, maxSizeMB, maxBackups, maxAgeDays)
	if err != nil {
		return nil, err
	}
	scribeLoggerMutex.Lock()
	defer scribeLoggerMutex.Unlock()
	scribeLoggerLevel = level
	scribeLoggerMode = "buffer+file"
	buf := &LogBuffer{lines: make([]LogLine, capacity)}
	scribeLoggerInstance = slog.New(&multiHandler{handlers: []slog.Handler{
		&bufferHandler{level: level, buffer: buf},
		&streamHandler{level: level, writer: writer},
	}})
	slog.SetDefault(scribeLoggerInstance)
	return buf, nil
}

func Log(source Source, subject Subject, action Action) Logger {
	return Logger{source: source, subject: subject, action: action}
}

type Logger struct {
	source  Source
	subject Subject
	action  Action
}

func (l Logger) Debug(verb string, started time.Time, detail string, args ...any) {
	l.log(slog.LevelDebug, verb, started, detail, args...)
}

func (l Logger) Info(verb string, started time.Time, detail string, args ...any) {
	l.log(slog.LevelInfo, verb, started, detail, args...)
}

func (l Logger) Warn(verb string, started time.Time, detail string, args ...any) {
	l.log(slog.LevelWarn, verb, started, detail, args...)
}

func (l Logger) Error(verb string, started time.Time, detail string, args ...any) {
	l.log(slog.LevelError, verb, started, detail, args...)
}

func (l Logger) log(level slog.Level, verb string, started time.Time, detail string, args ...any) {
	if len(args) > 0 {
		detail = fmt.Sprintf(detail, args...)
	}
	slog.Log(context.Background(), level, verb, keySource, l.source.String(), keySubject, l.subject.String(),
		keyAction, l.action.String(), keyDuration, time.Since(started), keyDetail, detail)
}

func Level() slog.Level {
	scribeLoggerMutex.Lock()
	defer scribeLoggerMutex.Unlock()
	return scribeLoggerLevel
}

func Mode() string {
	scribeLoggerMutex.Lock()
	defer scribeLoggerMutex.Unlock()
	return scribeLoggerMode
}

type LogLine struct {
	Time    time.Time
	Level   slog.Level
	Message string
}

type LogBuffer struct {
	mutex   sync.Mutex
	lines   []LogLine
	head    int
	count   int
	version uint64
}

func (b *LogBuffer) Push(line LogLine) {
	b.mutex.Lock()
	b.lines[b.head] = line
	b.head = (b.head + 1) % len(b.lines)
	if b.count < len(b.lines) {
		b.count++
	}
	b.version++
	b.mutex.Unlock()
}

func (b *LogBuffer) Tail(n int) []LogLine {
	b.mutex.Lock()
	defer b.mutex.Unlock()
	if b.count == 0 || n <= 0 {
		return nil
	}
	if n > b.count {
		n = b.count
	}
	result := make([]LogLine, n)
	start := (b.head - n + len(b.lines)) % len(b.lines)
	for i := range n {
		result[i] = b.lines[(start+i)%len(b.lines)]
	}
	return result
}

func (b *LogBuffer) Version() uint64 {
	b.mutex.Lock()
	defer b.mutex.Unlock()
	return b.version
}

type bufferHandler struct {
	level  slog.Level
	buffer *LogBuffer
}

func (h *bufferHandler) Enabled(_ context.Context, level slog.Level) bool {
	return level >= h.level
}

func (h *bufferHandler) Handle(_ context.Context, record slog.Record) error {
	source, subject, action, _, _ := dimensions(record)
	if !allowed(source, subject, action) {
		return nil
	}
	h.buffer.Push(LogLine{Time: record.Time, Level: record.Level, Message: format(record)})
	return nil
}

func (h *bufferHandler) WithAttrs(_ []slog.Attr) slog.Handler { return h }
func (h *bufferHandler) WithGroup(_ string) slog.Handler      { return h }

type multiHandler struct {
	handlers []slog.Handler
}

func (h *multiHandler) Enabled(ctx context.Context, level slog.Level) bool {
	for _, handler := range h.handlers {
		if handler.Enabled(ctx, level) {
			return true
		}
	}
	return false
}

func (h *multiHandler) Handle(ctx context.Context, record slog.Record) error {
	var failed error
	for _, handler := range h.handlers {
		if !handler.Enabled(ctx, record.Level) {
			continue
		}
		if err := handler.Handle(ctx, record.Clone()); err != nil && failed == nil {
			failed = err
		}
	}
	return failed
}

func (h *multiHandler) WithAttrs(_ []slog.Attr) slog.Handler { return h }
func (h *multiHandler) WithGroup(_ string) slog.Handler      { return h }

type streamHandler struct {
	level      slog.Level
	writer     io.Writer
	mutex      sync.Mutex
	headerOnce sync.Once
}

func (h *streamHandler) Enabled(_ context.Context, level slog.Level) bool {
	return level >= h.level
}

func (h *streamHandler) Handle(_ context.Context, record slog.Record) error {
	source, subject, action, _, _ := dimensions(record)
	if !allowed(source, subject, action) {
		return nil
	}
	h.mutex.Lock()
	defer h.mutex.Unlock()
	h.headerOnce.Do(func() {
		_, _ = io.WriteString(h.writer, headerLine()+"\n")
	})
	line := fmt.Sprintf("%s %-5s %s\n", record.Time.Format(timeLayout), record.Level.String(), format(record))
	_, err := io.WriteString(h.writer, line)
	return err
}

func (h *streamHandler) WithAttrs(_ []slog.Attr) slog.Handler { return h }
func (h *streamHandler) WithGroup(_ string) slog.Handler      { return h }

// OverlayHeader OverlayLine and OverlayHeader render the watch overlay's own prefix, so the whole line's geometry is owned here
// rather than split between scribe and display. The overlay carries a shorter time than the file and stdout, since it
// is read live and the date is never in question, but every column after it is the same width in all three sinks.
func OverlayHeader() string {
	return pad("TIME", len(overlayTimeLayout)) + " " + pad("LEVEL", widthLevel) + " " + columnLine("SOURCE", "SUBJECT", "ACTION", "DURATION", "DETAIL")
}

func OverlayLine(line LogLine) string {
	return line.Time.Format(overlayTimeLayout) + " " + pad(line.Level.String(), widthLevel) + " " + line.Message
}

// OverlayLines renders one buffered line as the rows the watch overlay draws, wrapping a detail too wide for the
// terminal onto further rows that repeat every column but the verb. Wrapping belongs to the overlay alone — the file
// and stdout carry the whole detail on one line, since they are read with a pager and grepped by position — so the
// width is the terminal's rather than a constant, and a terminal too narrow to hold a readable detail column falls
// back to the single line the caller clips.
func OverlayLines(line LogLine, width int) []string {
	rendered := []rune(OverlayLine(line))
	prefix := len(overlayTimeLayout) + 1 + widthLevel + 1 + widthSource + 1 + widthSubject + 1 + widthAction + 1 + widthDuration + 1
	budget := width - prefix - widthVerb - 1
	if len(rendered) <= width || budget < widthWrapMin || len(rendered) <= prefix+widthVerb+1 {
		return []string{string(rendered)}
	}
	head, verbText, detail := string(rendered[:prefix]), string(rendered[prefix:prefix+widthVerb]), string(rendered[prefix+widthVerb+1:])
	var lines []string
	for index, chunk := range chunked(detail, budget) {
		slot := verbText
		if index > 0 {
			slot = strings.Repeat(" ", widthVerb)
		}
		lines = append(lines, strings.TrimRight(head+slot+" "+chunk, " "))
	}
	return lines
}

func headerLine() string {
	return pad("TIME", widthTime) + " " + pad("LEVEL", widthLevel) + " " +
		columnLine("SOURCE", "SUBJECT", "ACTION", "DURATION", "DETAIL")
}

func dimensions(record slog.Record) (source, subject, action, duration, detail string) {
	record.Attrs(func(a slog.Attr) bool {
		switch a.Key {
		case keySource:
			source = a.Value.String()
		case keySubject:
			subject = a.Value.String()
		case keyAction:
			action = a.Value.String()
		case keyDuration:
			duration = durationText(a.Value)
		case keyDetail:
			detail = a.Value.String()
		}
		return true
	})
	return
}

func format(record slog.Record) string {
	source, subject, action, duration, detail := dimensions(record)
	if detail != "" {
		detail = " " + detail
	}
	return columnLine(source, subject, action, duration, verb(record.Message)+detail)
}

// chunked splits a detail too long for the budget, cutting at a space where there is one and mid-token where there is
// not, and ending every continuing chunk with wrapEllipsis.
func chunked(detail string, budget int) []string {
	runes := []rune(detail)
	if budget < widthWrapMin || len(runes) <= budget {
		return []string{detail}
	}
	limit := budget - len(wrapEllipsis) - 1
	var chunks []string
	for len(runes) > budget {
		chunk, rest, spaced := split(runes, limit)
		if spaced {
			chunk += " "
		}
		chunks = append(chunks, chunk+wrapEllipsis)
		runes = rest
	}
	return append(chunks, string(runes))
}

func split(detail []rune, limit int) (string, []rune, bool) {
	cut := spaced(detail[:limit+1])
	if cut <= 0 {
		return string(detail[:limit]), detail[limit:], false
	}
	return strings.TrimRight(string(detail[:cut]), " "), []rune(strings.TrimLeft(string(detail[cut:]), " ")), true
}

func spaced(runes []rune) int {
	for index, value := range slices.Backward(runes) {
		if value == ' ' {
			return index
		}
	}
	return -1
}

func columnLine(source, subject, action, duration, detail string) string {
	return strings.TrimRight(pad(source, widthSource)+" "+pad(subject, widthSubject)+" "+pad(action, widthAction)+" "+pad(duration, widthDuration)+" "+detail, " ")
}

func verb(word string) string {
	runes := []rune(word)
	if len(runes) >= widthVerb {
		return string(runes[:widthVerb])
	}
	return word + strings.Repeat(" ", widthVerb-len(runes))
}

func durationText(value slog.Value) string {
	text := value.String()
	if value.Kind() == slog.KindDuration {
		text = elapsed(value.Duration())
	}
	if space := widthDuration - utf8.RuneCountInString(text); space > 0 {
		return strings.Repeat(" ", space) + text
	}
	return text
}

func elapsed(value time.Duration) string {
	if millis := value.Milliseconds(); millis < durationCoarser {
		return fmt.Sprintf("%dms", millis)
	}
	if seconds := int64(value.Seconds()); seconds < durationCoarser {
		return fmt.Sprintf("%ds", seconds)
	}
	if minutes := int64(value.Minutes()); minutes < durationCoarser {
		return fmt.Sprintf("%dm", minutes)
	}
	return fmt.Sprintf("%dh", int64(value.Hours()))
}

func pad(text string, width int) string {
	count := utf8.RuneCountInString(text)
	if count >= width {
		return text
	}
	return text + strings.Repeat(" ", width-count)
}

const (
	keyDetail   = "detail"
	keyDuration = "duration"
	keySource   = "source"
	keySubject  = "subject"
	keyAction   = "action"
)

const (
	durationCoarser = 10000
	widthTime       = 14
	widthLevel      = 5
	widthSource     = 8
	widthAction     = 10
	widthDuration   = 8
	widthVerb       = 8
	widthWrapMin    = 40
	wrapEllipsis    = "..."
	widthSubjectMin = 24
)

var widthSubject = widthSubjectMin

var (
	scribeLoggerMutex    sync.Mutex
	scribeLoggerLevel    slog.Level
	scribeLoggerMode     string
	scribeLoggerInstance *slog.Logger
)

func init() {
	for _, id := range metric.GetIDs() {
		if length := len(metric.GetIDName(id)); length > widthSubject {
			widthSubject = length
		}
	}
	for _, source := range AllSources {
		if length := len(source.String()); length > widthSource {
			panic(fmt.Sprintf("error: source [%s] is [%d] characters, wider than the [%d] column", source, length, widthSource))
		}
	}
	for _, action := range AllActions {
		if length := len(action.String()); length > widthAction {
			panic(fmt.Sprintf("error: action [%s] is [%d] characters, wider than the [%d] column", action, length, widthAction))
		}
	}
	verifyVocabularies()
}

func verifyVocabularies() {
	claimed := map[string]string{}
	claim := func(vocabulary, value string) {
		if owner, taken := claimed[value]; taken {
			panic(fmt.Sprintf("error: [%s] is declared by both the [%s] and [%s] vocabularies, so a bare column value would be ambiguous", value, owner, vocabulary))
		}
		claimed[value] = vocabulary
	}
	for _, source := range AllSources {
		claim("source", source.String())
	}
	for _, action := range AllActions {
		claim("action", action.String())
	}
	for _, id := range metric.GetIDs() {
		claim("subject", metric.GetIDName(id))
	}
}

func logDir() string {
	if os.Geteuid() == 0 {
		return logDirRoot
	}
	if runtime.GOOS == "darwin" {
		if home, err := os.UserHomeDir(); err == nil {
			return filepath.Join(home, logDirUserMac)
		}
	}
	return logDirUser
}

func fileWriter(cmd string, maxSizeMB, maxBackups, maxAgeDays int) (io.Writer, error) {
	dir := logDir()
	if err := os.MkdirAll(dir, 0755); err != nil {
		return nil, fmt.Errorf("create log directory failed [%s] [%w]", dir, err)
	}
	path := filepath.Join(dir, fmt.Sprintf("%s-pid-%d.log", cmd, os.Getpid()))
	return &lumberjack.Logger{Filename: path, MaxSize: maxSizeMB, MaxBackups: maxBackups, MaxAge: maxAgeDays, Compress: true}, nil
}
