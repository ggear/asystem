package scribe

import (
	"fmt"
	"strings"
	"sync"

	"supervisor/internal/metric"
)

type Source uint8

const (
	SourceProcess Source = iota
	SourceProbe
	SourceBroker
	SourceDatabase
	SourceDisplay
	SourceConfig
	SourceSchema
)

func (s Source) String() string {
	switch s {
	case SourceProcess:
		return "process"
	case SourceProbe:
		return "probe"
	case SourceBroker:
		return "broker"
	case SourceDatabase:
		return "database"
	case SourceDisplay:
		return "display"
	case SourceConfig:
		return "config"
	case SourceSchema:
		return "schema"
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

func SubjectService(name string) Subject {
	return Subject{text: name}
}

func SubjectHost(name string) Subject {
	return Subject{text: name}
}

func SubjectField(name string) Subject {
	return Subject{text: name}
}

func SubjectTopic(topic string) Subject {
	return Subject{text: topic}
}

func SubjectPath(path string) Subject {
	return Subject{text: path}
}

func (s Subject) String() string {
	if s.text == "" {
		return unknownValue
	}
	return s.text
}

var (
	AllSources = declaredSources()
	AllActions = declaredActions()
)

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
	return matches(source, filter.source) && matches(subject, filter.subject) && matches(action, filter.action)
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

const unknownValue = "-"

type logFilter struct {
	source  []string
	subject []string
	action  []string
}

var (
	filterMutex  sync.Mutex
	activeFilter logFilter
)
