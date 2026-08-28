package scribe

import (
	"fmt"
	"sort"
	"strings"
	"sync"
	"unicode/utf8"

	"supervisor/internal/metric"
)

type Source uint8

const (
	SourceScribe Source = iota
	SourceCmdServe
	SourceCmdWatch
	SourceConfig
	SourceProbe
	SourceProbeHost
	SourceProbeInstall
	SourceProbeLogs
	SourceProbeDrives
	SourceProbeMounts
	SourceProbeSensors
	SourceProbeServices
	SourceEngine
	SourceEngineBroker
	SourceEngineDatabase
	SourceDisplay
	SourceDisplayLayout
)

func (s Source) String() string {
	switch s {
	case SourceScribe:
		return "scribe"
	case SourceCmdServe:
		return "cmd[serve]"
	case SourceCmdWatch:
		return "cmd[watch]"
	case SourceConfig:
		return "config"
	case SourceProbe:
		return "probe"
	case SourceProbeHost:
		return "probe[host]"
	case SourceProbeInstall:
		return "probe[install]"
	case SourceProbeLogs:
		return "probe[logs]"
	case SourceProbeDrives:
		return "probe[drives]"
	case SourceProbeMounts:
		return "probe[mounts]"
	case SourceProbeSensors:
		return "probe[sensors]"
	case SourceProbeServices:
		return "probe[services]"
	case SourceEngine:
		return "engine"
	case SourceEngineBroker:
		return "engine[broker]"
	case SourceEngineDatabase:
		return "engine[database]"
	case SourceDisplay:
		return "display"
	case SourceDisplayLayout:
		return "display[layout]"
	default:
		return unknownValue
	}
}

type Action uint8

const (
	ActionStart Action = iota
	ActionStop
	ActionConnect
	ActionDisconnect
	ActionSubscribe
	ActionPublish
	ActionRegister
	ActionRemove
	ActionReconcile
	ActionDiscover
	ActionSample
	ActionCompute
	ActionRender
	ActionResolve
	ActionCensus
)

func (a Action) String() string {
	switch a {
	case ActionStart:
		return "start"
	case ActionStop:
		return "stop"
	case ActionConnect:
		return "connect"
	case ActionDisconnect:
		return "disconnect"
	case ActionSubscribe:
		return "subscribe"
	case ActionPublish:
		return "publish"
	case ActionRegister:
		return "register"
	case ActionRemove:
		return "remove"
	case ActionReconcile:
		return "reconcile"
	case ActionDiscover:
		return "discover"
	case ActionSample:
		return "sample"
	case ActionCompute:
		return "compute"
	case ActionRender:
		return "render"
	case ActionResolve:
		return "resolve"
	case ActionCensus:
		return "census"
	default:
		return unknownValue
	}
}

type Subject struct {
	text string
}

var SubjectNone = Subject{}

func SubjectMetric(id metric.ID) Subject {
	return Subject{text: metric.GetIDName(id)}
}

func SubjectHost(name string) Subject {
	if name == "" {
		return Subject{text: subjectHosts}
	}
	return Subject{text: subjectHosts + "/" + name}
}

func SubjectService(name string) Subject {
	if name == metric.ServiceNameUnset {
		return Subject{text: subjectServices}
	}
	return Subject{text: subjectServices + "/" + name}
}

func SubjectTopic(topic string) Subject {
	id, ok := metric.IDFromTopic(topic)
	if !ok {
		return SubjectNone
	}
	return SubjectMetric(id)
}

func (s Subject) String() string {
	return s.text
}

func Attribute(source Source, ids ...metric.ID) {
	names := make([]string, 0, len(ids))
	for _, id := range ids {
		names = append(names, strings.ToLower(metric.GetIDName(id)))
	}
	attributionMutex.Lock()
	attributions[source.String()] = names
	attributionMutex.Unlock()
}

func Widen(hosts, services []string) {
	if Mode() != "" {
		panic(fmt.Sprintf("error: widen called after logging was enabled as [%s], so a written header cannot match its rows", Mode()))
	}
	for _, name := range prefixed(subjectHosts, hosts) {
		spanSubject.ideal = max(spanSubject.ideal, len(name))
	}
	for _, name := range prefixed(subjectServices, services) {
		spanSubject.ideal = max(spanSubject.ideal, len(name))
	}
}

var (
	AllSources = declaredSources()
	AllActions = declaredActions()
)

func Vocabularies(hosts, services []string) string {
	declared := make([]string, 0, len(metric.GetIDs()))
	for _, id := range metric.GetIDs() {
		declared = append(declared, metric.GetIDName(id))
	}
	sort.Strings(declared)
	hostMetrics, serviceMetrics := []string{}, []string{}
	for _, subject := range declared {
		if strings.HasPrefix(subject, subjectServices+"/") {
			serviceMetrics = append(serviceMetrics, subject)
			continue
		}
		if strings.HasPrefix(subject, subjectHosts+"/") {
			hostMetrics = append(hostMetrics, subject)
		}
	}
	hostNames := prefixed(subjectHosts, hosts)
	serviceNames := prefixed(subjectServices, services)
	cell := max(widest(hostMetrics), widest(serviceMetrics), widest(hostNames), widest(serviceNames),
		subjectSplit*widest(sourceStrings()), subjectSplit*widest(actionStrings()))
	if cell%subjectSplit != 0 {
		cell += subjectSplit - cell%subjectSplit
	}
	var builder strings.Builder
	builder.WriteString("Log Sources:\n")
	builder.WriteString(columned(sourceStrings(), cell/subjectSplit))
	builder.WriteString("\nLog Subjects:\n")
	builder.WriteString(grouped(cell, []string{subjectHosts}, nil, []string{subjectServices}, nil))
	builder.WriteString(grouped(cell, hostMetrics, hostNames, serviceMetrics, serviceNames))
	builder.WriteString("\nLog Actions:\n")
	builder.WriteString(columned(actionStrings(), cell/subjectSplit))
	return builder.String()
}

func prefixed(branch string, names []string) []string {
	values := make([]string, 0, len(names))
	for _, name := range names {
		values = append(values, branch+"/"+name)
	}
	return values
}

func grouped(cell int, columns ...[]string) string {
	rows := 0
	for _, column := range columns {
		rows = max(rows, len(column))
	}
	var builder strings.Builder
	for row := range rows {
		var line strings.Builder
		line.WriteString(strings.Repeat(" ", widthHelpIndent))
		for _, column := range columns {
			if row < len(column) {
				line.WriteString(pad(column[row], cell))
				continue
			}
			line.WriteString(strings.Repeat(" ", cell))
		}
		builder.WriteString(strings.TrimRight(line.String(), " ") + "\n")
	}
	return builder.String()
}

func widest(values []string) int {
	longest := 0
	for _, value := range values {
		if length := utf8.RuneCountInString(value); length > longest {
			longest = length
		}
	}
	return longest + widthHelpGap
}

func columned(values []string, cell int) string {
	columns := subjectColumns * subjectSplit
	var builder strings.Builder
	for index := 0; index < len(values); index += columns {
		var row strings.Builder
		row.WriteString(strings.Repeat(" ", widthHelpIndent))
		for _, value := range values[index:min(index+columns, len(values))] {
			row.WriteString(pad(value, cell))
		}
		builder.WriteString(strings.TrimRight(row.String(), " ") + "\n")
	}
	return builder.String()
}

func SetFilters(source, subject, action string) error {
	sourcePrefixes, err := closedPrefixes("source", source, sourceStrings())
	if err != nil {
		return err
	}
	actionPrefixes, err := closedPrefixes("action", action, actionStrings())
	if err != nil {
		return err
	}
	subjectPrefixes := openPrefixes(subject)
	filterMutex.Lock()
	activeFilter = logFilter{source: sourcePrefixes, subject: subjectPrefixes, action: actionPrefixes}
	filterMutex.Unlock()
	return nil
}

func ResetFilters() {
	filterMutex.Lock()
	activeFilter = logFilter{}
	filterMutex.Unlock()
}

func allowed(source, subject, action string) bool {
	filterMutex.Lock()
	filter := activeFilter
	filterMutex.Unlock()
	return matches(source, filter.source) && subjected(source, subject, filter.subject) && matches(action, filter.action)
}

func subjected(source, subject string, prefixes []string) bool {
	if matches(subject, prefixes) {
		return true
	}
	attributionMutex.Lock()
	attributed := attributions[source]
	attributionMutex.Unlock()
	for _, name := range attributed {
		if matches(name, prefixes) {
			return true
		}
	}
	return false
}

func declaredSources() []Source {
	var declared []Source
	for source := Source(0); source.String() != unknownValue; source++ {
		declared = append(declared, source)
	}
	return declared
}

func declaredActions() []Action {
	var declared []Action
	for action := Action(0); action.String() != unknownValue; action++ {
		declared = append(declared, action)
	}
	return declared
}

func matches(value string, prefixes []string) bool {
	if len(prefixes) == 0 {
		return true
	}
	lowered := strings.ToLower(value)
	for _, prefix := range prefixes {
		if strings.HasPrefix(lowered, prefix) {
			return true
		}
	}
	return false
}

func openPrefixes(value string) []string {
	if strings.TrimSpace(value) == "" {
		return nil
	}
	prefixes := make([]string, 0, strings.Count(value, ",")+1)
	for token := range strings.SplitSeq(value, ",") {
		if token = strings.ToLower(strings.TrimSpace(token)); token != "" {
			prefixes = append(prefixes, token)
		}
	}
	return prefixes
}

func closedPrefixes(dimension, value string, declared []string) ([]string, error) {
	prefixes := openPrefixes(value)
	for _, prefix := range prefixes {
		matched := false
		for _, candidate := range declared {
			if strings.HasPrefix(strings.ToLower(candidate), prefix) {
				matched = true
				break
			}
		}
		if !matched {
			return nil, fmt.Errorf("log %s filter prefix [%s] matches none of [%s]", dimension, prefix, strings.Join(declared, ", "))
		}
	}
	return prefixes, nil
}

func sourceStrings() []string {
	values := make([]string, len(AllSources))
	for index, source := range AllSources {
		values[index] = source.String()
	}
	return values
}

func actionStrings() []string {
	values := make([]string, len(AllActions))
	for index, action := range AllActions {
		values[index] = action.String()
	}
	return values
}

const (
	unknownValue = "-"
)

var (
	attributionMutex sync.Mutex
	attributions     = map[string][]string{}
)

type logFilter struct {
	source  []string
	subject []string
	action  []string
}

var (
	filterMutex  sync.Mutex
	activeFilter logFilter
)
