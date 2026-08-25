package scribe

import "supervisor/internal/metric"

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

var (
	AllSources = declaredSources()
	AllActions = declaredActions()
)

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

const unknownValue = "-"
