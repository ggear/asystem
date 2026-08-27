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
	"syscall"
	"time"
	"unicode/utf8"

	"gopkg.in/natefinch/lumberjack.v2"

	"supervisor/internal/metric"
)

const (
	bufferScreens    = 50
	logDirUser       = "/tmp/supervisor"
	logDirUserMac    = "Library/Logs/supervisor"
	logDirRoot       = "/var/log/supervisor"
	logFileSuffix    = ".log"
	logFileArchive   = ".gz"
	logFilePIDMarker = "-pid-"
	stampFile        = "01-02T15:04:05"
	stampOverlay     = "15:04:05"
)

func EnableStdout(level slog.Level) {
	scribeLoggerMutex.Lock()
	defer scribeLoggerMutex.Unlock()
	scribeLoggerLevel = level
	scribeLoggerMode = "stdout"
	scribeLoggerInstance = slog.New(&streamHandler{level: level, writer: os.Stdout, sink: sinkFile()})
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
	scribeLoggerInstance = slog.New(&streamHandler{level: level, writer: writer, sink: sinkFile()})
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
	scribeLoggerInstance = slog.New(&streamHandler{level: level, writer: multi, sink: sinkFile()})
	slog.SetDefault(scribeLoggerInstance)
	purgeLogFiles(path)
	return nil
}

func Disable() {
	scribeLoggerMutex.Lock()
	defer scribeLoggerMutex.Unlock()
	scribeLoggerMode = "disabled"
	scribeLoggerInstance = slog.New(&streamHandler{level: slog.LevelError + 1, writer: io.Discard, sink: sinkFile()})
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
		&streamHandler{level: level, writer: writer, sink: sinkFile()},
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
	Time     time.Time
	Level    slog.Level
	Source   string
	Subject  string
	Action   string
	Duration string
	Verb     string
	Detail   string
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
	line := lineOf(record)
	if !allowed(line.Source, line.Subject, line.Action) {
		return nil
	}
	h.buffer.Push(line)
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
	sink       sink
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
		_, _ = io.WriteString(h.writer, headerFor(layoutFor(h.sink))+"\n")
	})
	for _, line := range wrapped(lineOf(record), layoutFor(h.sink)) {
		if _, err := io.WriteString(h.writer, line+"\n"); err != nil {
			return err
		}
	}
	return nil
}

func (h *streamHandler) WithAttrs(_ []slog.Attr) slog.Handler { return h }
func (h *streamHandler) WithGroup(_ string) slog.Handler      { return h }

func OverlayHeader(width int) string {
	return headerFor(layoutFor(sinkOverlay(width)))
}

func OverlayLines(line LogLine, width int) []string {
	return wrapped(line, layoutFor(sinkOverlay(width)))
}

func headerFor(l layout) string {
	return render(LogLine{Source: "SOURCE", Subject: "SUBJECT", Action: "ACTION", Duration: "DURATION", Verb: "VERB", Detail: "DETAIL"},
		l, pad("TIME", l.time), "LEVEL")
}

func render(line LogLine, l layout, stamp, level string) string {
	detail := line.Detail
	if detail != "" {
		detail = " " + detail
	}
	return strings.TrimRight(stamp+" "+pad(level, l.level)+" "+
		pad(stemmed(line.Source, l.source), l.source)+" "+
		pad(tokened(line.Subject, l.subject), l.subject)+" "+
		pad(head(line.Action, l.action), l.action)+" "+
		pad(line.Duration, l.duration)+" "+
		pad(line.Verb, l.verb)+detail, " ")
}

func wrapped(line LogLine, l layout) []string {
	stamp, level := line.Time.Format(l.stamp), line.Level.String()
	single := render(line, l, stamp, level)
	if l.detail < spanDetail.min || utf8.RuneCountInString(line.Detail) <= l.detail {
		return []string{single}
	}
	var lines []string
	for index, chunk := range chunked(line.Detail, l.detail) {
		part := line
		part.Detail = chunk
		if index > 0 {
			part.Verb = ""
		}
		lines = append(lines, render(part, l, stamp, level))
	}
	return lines
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

func lineOf(record slog.Record) LogLine {
	source, subject, action, duration, detail := dimensions(record)
	return LogLine{Time: record.Time, Level: record.Level, Source: source, Subject: subject,
		Action: action, Duration: duration, Verb: verb(record.Message), Detail: detail}
}

func chunked(detail string, budget int) []string {
	runes := []rune(detail)
	if budget < spanDetail.min || len(runes) <= budget {
		return []string{detail}
	}
	limit := budget - len(clipMarker) - 1
	var chunks []string
	for len(runes) > budget {
		chunk, rest, spaced := split(runes, limit)
		if spaced {
			chunk += " "
		}
		chunks = append(chunks, chunk+clipMarker)
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

func stemmed(text string, width int) string {
	if cut := strings.IndexByte(text, '['); len(text) > width && cut > 0 && cut < width {
		return text[:cut] + clipMarker
	}
	return head(text, width)
}

func head(text string, width int) string {
	runes := []rune(text)
	if len(runes) <= width {
		return text
	}
	if width <= len(clipMarker) {
		return string([]rune(clipMarker)[:max(width, 0)])
	}
	return string(runes[:width-len(clipMarker)]) + clipMarker
}

func tokened(text string, width int) string {
	if cut := strings.LastIndexAny(text, clipTokens); len(text) > width && cut >= 0 && cut+1 < len(text) {
		if token := clipMarker + text[cut+1:]; utf8.RuneCountInString(token) <= width {
			return token
		}
	}
	return tail(text, width)
}

func tail(text string, width int) string {
	runes := []rune(text)
	if len(runes) <= width {
		return text
	}
	if width <= len(clipMarker) {
		return string([]rune(clipMarker)[:max(width, 0)])
	}
	return clipMarker + string(runes[len(runes)-width+len(clipMarker):])
}

func verb(word string) string {
	runes := []rune(word)
	if len(runes) >= spanVerb.ideal {
		return string(runes[:spanVerb.ideal])
	}
	return word + strings.Repeat(" ", spanVerb.ideal-len(runes))
}

func durationText(value slog.Value) string {
	text := value.String()
	if value.Kind() == slog.KindDuration {
		text = elapsed(value.Duration())
	}
	if space := spanDuration.ideal - utf8.RuneCountInString(text); space > 0 {
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
	widthFile       = 250
	widthHelpIndent = 2
	widthHelpGap    = 2
	subjectColumns  = 4
	subjectSplit    = 2
	subjectHosts    = "host"
	subjectServices = "service"
	clipMarker      = "~"
	clipTokens      = "-_"
)

type span struct {
	ideal int
	min   int
}

var (
	spanLevel    = span{ideal: 5, min: 5}
	spanSource   = span{ideal: 16}
	spanSubject  = span{ideal: 24, min: 8}
	spanAction   = span{ideal: 10, min: 9}
	spanDuration = span{ideal: 8, min: 8}
	spanVerb     = span{ideal: 8, min: 8}
	spanDetail   = span{ideal: 60, min: 40}
)

type sink struct {
	stamp string
	width int
}

func sinkFile() sink             { return sink{stamp: stampFile, width: widthFile} }
func sinkOverlay(width int) sink { return sink{stamp: stampOverlay, width: width} }

type layout struct {
	stamp                                          string
	time, level, source, subject, action, duration int
	verb, detail                                   int
}

func (l layout) prefix() int {
	return l.time + 1 + l.level + 1 + l.source + 1 + l.subject + 1 + l.action + 1 + l.duration + 1 + l.verb + 1
}

func (l layout) width() int {
	return l.prefix() + l.detail
}

func layoutFor(s sink) layout {
	if s.stamp == "" || s.width <= 0 {
		s = sinkFile()
	}
	l := layout{stamp: s.stamp, time: len(s.stamp), level: spanLevel.ideal, source: spanSource.min,
		subject: spanSubject.min, action: spanAction.min, duration: spanDuration.ideal, verb: spanVerb.ideal}
	for _, rung := range []struct {
		column *int
		upto   int
	}{
		{column: &l.detail, upto: spanDetail.min},
		{column: &l.detail, upto: spanDetail.ideal},
		{column: &l.action, upto: spanAction.ideal},
		{column: &l.subject, upto: spanSubject.ideal},
		{column: &l.source, upto: spanSource.ideal},
	} {
		*rung.column += max(min(rung.upto-*rung.column, s.width-l.width()), 0)
	}
	l.detail += max(s.width-l.width(), 0)
	return l
}

var flattened = strings.NewReplacer("\r\n", " ", "\n", " ", "\r", " ", "\t", " ")

var (
	scribeLoggerMutex    sync.Mutex
	scribeLoggerLevel    slog.Level
	scribeLoggerMode     string
	scribeLoggerInstance *slog.Logger
)

func init() {
	for _, id := range metric.GetIDs() {
		spanSubject.ideal = max(spanSubject.ideal, len(metric.GetIDName(id)))
	}
	for _, source := range AllSources {
		if length := len(source.String()); length > spanSource.ideal {
			panic(fmt.Sprintf("error: source [%s] is [%d] characters, wider than the [%d] column", source, length, spanSource.ideal))
		}
	}
	for _, action := range AllActions {
		if length := len(action.String()); length > spanAction.ideal {
			panic(fmt.Sprintf("error: action [%s] is [%d] characters, wider than the [%d] column", action, length, spanAction.ideal))
		}
	}
	for _, source := range sourceStrings() {
		if bracket := strings.IndexByte(source, '['); bracket > 0 {
			source = source[:bracket]
		}
		spanSource.min = max(spanSource.min, len(source))
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
