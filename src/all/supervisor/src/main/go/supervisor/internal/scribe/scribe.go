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
	"strconv"
	"strings"
	"sync"
	"sync/atomic"
	"syscall"
	"time"
	"unicode/utf8"

	"gopkg.in/natefinch/lumberjack.v2"

	"supervisor/internal/metric"
)

const (
	bufferScreens     = 40
	logDirUser        = "/tmp/supervisor"
	logDirUserMac     = "Library/Logs/supervisor"
	logDirRoot        = "/var/log/supervisor"
	logFileSuffix     = ".log"
	logFileArchive    = ".gz"
	logFilePIDMarker  = "-pid-"
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
	writer, path, err := fileWriter(cmd, maxSizeMB, maxBackups, maxAgeDays)
	if err != nil {
		return err
	}
	scribeLoggerMutex.Lock()
	defer scribeLoggerMutex.Unlock()
	scribeLoggerLevel = level
	scribeLoggerMode = "file"
	scribeLoggerInstance = slog.New(&streamHandler{level: level, writer: writer})
	slog.SetDefault(scribeLoggerInstance)
	purgeLogFiles(path)
	return nil
}

func EnableStdoutAndFile(level slog.Level, cmd string, maxSizeMB, maxBackups, maxAgeDays int) error {
	writer, path, err := fileWriter(cmd, maxSizeMB, maxBackups, maxAgeDays)
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
	purgeLogFiles(path)
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
	writer, path, err := fileWriter(cmd, maxSizeMB, maxBackups, maxAgeDays)
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
	purgeLogFiles(path)
	return buf, nil
}

func BufferLines(rows int) int {
	if rows < 1 {
		rows = 1
	}
	return rows * bufferScreens
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
	detail = flattened.Replace(detail)
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

func (b *LogBuffer) From(sequence uint64, n int) ([]LogLine, uint64) {
	b.mutex.Lock()
	defer b.mutex.Unlock()
	if b.count == 0 || n <= 0 {
		return nil, b.version
	}
	oldest := b.version - uint64(b.count)
	if sequence < oldest {
		sequence = oldest
	}
	if sequence >= b.version {
		return nil, b.version
	}
	if behind := int(b.version - sequence); n > behind {
		n = behind
	}
	result := make([]LogLine, n)
	start := ((b.head-int(b.version-sequence))%len(b.lines) + len(b.lines)) % len(b.lines)
	for i := range n {
		result[i] = b.lines[(start+i)%len(b.lines)]
	}
	return result, sequence
}

func (b *LogBuffer) Rewind(n int) uint64 {
	b.mutex.Lock()
	defer b.mutex.Unlock()
	if n < 0 {
		n = 0
	}
	if n > b.count {
		n = b.count
	}
	return b.version - uint64(n)
}

func (b *LogBuffer) Oldest() uint64 {
	b.mutex.Lock()
	defer b.mutex.Unlock()
	return b.version - uint64(b.count)
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
	for _, line := range streamLines(record) {
		if _, err := io.WriteString(h.writer, line+"\n"); err != nil {
			return err
		}
	}
	return nil
}

func (h *streamHandler) WithAttrs(_ []slog.Attr) slog.Handler { return h }
func (h *streamHandler) WithGroup(_ string) slog.Handler      { return h }

func OverlayHeader() string {
	return pad("TIME", len(overlayTimeLayout)) + " " + pad("LEVEL", widthLevel) + " " + columnLine("SOURCE", "SUBJECT", "ACTION", "DURATION", "DETAIL")
}

func OverlayLine(line LogLine) string {
	return line.Time.Format(overlayTimeLayout) + " " + pad(line.Level.String(), widthLevel) + " " + line.Message
}

func OverlayLines(line LogLine, width int) []string {
	return wrapped(OverlayLine(line), len(overlayTimeLayout), width)
}

func streamLines(record slog.Record) []string {
	line := record.Time.Format(timeLayout) + " " + pad(record.Level.String(), widthLevel) + " " + format(record)
	return wrapped(line, widthTime, widthStream)
}

func wrapped(line string, timeWidth, width int) []string {
	rendered := []rune(line)
	prefix := timeWidth + 1 + widthLevel + 1 + widthSource + 1 + subjectWidth() + 1 + widthAction + 1 + widthDuration + 1
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
	return columnLine(source, clipped(subject, subjectWidth()), action, duration, verb(record.Message)+detail)
}

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

func clipped(text string, width int) string {
	runes := []rune(text)
	if len(runes) <= width || width <= len(wrapEllipsis) {
		return text
	}
	return wrapEllipsis + string(runes[len(runes)-width+len(wrapEllipsis):])
}

func columnLine(source, subject, action, duration, detail string) string {
	return strings.TrimRight(pad(source, widthSource)+" "+pad(subject, subjectWidth())+" "+pad(action, widthAction)+" "+pad(duration, widthDuration)+" "+detail, " ")
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
	widthSource     = 17
	widthAction     = 10
	widthDuration   = 8
	widthVerb       = 8
	widthWrapMin    = 40
	widthStream     = 250
	widthHelpIndent = 2
	widthHelpGap    = 2
	subjectColumns  = 4
	subjectSplit    = 2
	subjectHosts    = "host"
	subjectServices = "service"
	wrapEllipsis    = "..."
	widthSubjectMin = 24
)

var widthSubject atomic.Int32

func subjectWidth() int {
	return int(widthSubject.Load())
}

var flattened = strings.NewReplacer("\r\n", " ", "\n", " ", "\r", " ", "\t", " ")

var (
	scribeLoggerMutex    sync.Mutex
	scribeLoggerLevel    slog.Level
	scribeLoggerMode     string
	scribeLoggerInstance *slog.Logger
)

func init() {
	widthSubject.Store(widthSubjectMin)
	for _, id := range metric.GetIDs() {
		if length := len(metric.GetIDName(id)); length > subjectWidth() {
			widthSubject.Store(int32(length))
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

func fileWriter(cmd string, maxSizeMB, maxBackups, maxAgeDays int) (io.Writer, string, error) {
	dir := logDir()
	if err := os.MkdirAll(dir, 0755); err != nil {
		return nil, "", fmt.Errorf("create log directory failed [%s] [%w]", dir, err)
	}
	path := filepath.Join(dir, fmt.Sprintf("%s-pid-%d%s", cmd, os.Getpid(), logFileSuffix))
	return &lumberjack.Logger{Filename: path, MaxSize: maxSizeMB, MaxBackups: maxBackups, MaxAge: maxAgeDays, Compress: true}, path, nil
}

func purgeLogFiles(keep string) {
	purgeStart := time.Now()
	dir := filepath.Dir(keep)
	entries, err := os.ReadDir(dir)
	if err != nil {
		Log(SourceScribe, SubjectNone, ActionRemove).Warn("faulting", purgeStart, "log directory [%s] unreadable with [%v]", dir, err)
		return
	}
	removed := 0
	for _, entry := range entries {
		name := entry.Name()
		if entry.IsDir() || !strings.HasSuffix(name, logFileSuffix) && !strings.HasSuffix(name, logFileSuffix+logFileArchive) {
			continue
		}
		path := filepath.Join(dir, name)
		if path == keep {
			continue
		}
		if pid, ok := logFilePID(name); ok && pid != os.Getpid() && logProcessAlive(pid) {
			continue
		}
		if removeErr := os.Remove(path); removeErr != nil {
			Log(SourceScribe, SubjectNone, ActionRemove).Warn("faulting", purgeStart, "stale log file [%s] with [%v]", name, removeErr)
			continue
		}
		removed++
	}
	if removed > 0 {
		Log(SourceScribe, SubjectNone, ActionRemove).Info("removals", purgeStart, "[%d] stale log files, kept [%s]", removed, filepath.Base(keep))
	}
}

func logFilePID(name string) (int, bool) {
	index := strings.LastIndex(name, logFilePIDMarker)
	if index < 0 {
		return 0, false
	}
	digits := name[index+len(logFilePIDMarker):]
	end := strings.IndexFunc(digits, func(value rune) bool { return value < '0' || value > '9' })
	if end == 0 {
		return 0, false
	}
	if end > 0 {
		digits = digits[:end]
	}
	pid, err := strconv.Atoi(digits)
	if err != nil {
		return 0, false
	}
	return pid, true
}

func logProcessAlive(pid int) bool {
	process, err := os.FindProcess(pid)
	if err != nil {
		return false
	}
	return process.Signal(syscall.Signal(0)) == nil
}
