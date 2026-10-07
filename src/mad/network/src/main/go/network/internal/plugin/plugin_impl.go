package plugin

import (
	"bytes"
	"context"
	"fmt"
	"sort"
	"strconv"
	"strings"
	"sync"
	"time"

	"network/internal/schema"
)

type Plugin interface {
	Name() string
	Mode() Mode
	Poll(ctx context.Context) (Sample, error)
	Aggregate(samples []Sample) (Aggregate, error)
	Command(ctx context.Context, newState State) error
	State() *StateTracker
}

type Paced interface {
	PollPeriod() time.Duration
}

type Sample struct {
	Timestamp time.Time
	Readings  any
}

type Aggregate struct {
	Plugin    string
	Timestamp time.Time
	OK        bool
	Status    Status
	Score     int
	Reason    string
	Points    []schema.Point
}

type Status string

const (
	StatusFit  Status = "fit"
	StatusSick Status = "sick"
	StatusDead Status = "dead"
)

type Mode uint8

const (
	ModeSnapshot Mode = iota
	ModeWindowed
)

type State uint8

const (
	StateOff State = iota
	StateOn
)

type StateTracker struct {
	valueMu sync.Mutex
	value   State
}

func Filter(names []string) ([]Plugin, error) {
	all := registered()
	if len(names) == 0 {
		return all, nil
	}
	byName := map[string]Plugin{}
	for _, p := range all {
		byName[p.Name()] = p
	}
	seen := map[string]bool{}
	filtered := make([]Plugin, 0, len(names))
	for _, name := range names {
		name = strings.TrimSpace(name)
		if name == "" {
			continue
		}
		p, ok := byName[name]
		if !ok {
			return nil, fmt.Errorf("unknown plugin [%s]", name)
		}
		if seen[name] {
			continue
		}
		seen[name] = true
		filtered = append(filtered, p)
	}
	return filtered, nil
}

func ParseState(payload string) (State, bool) {
	switch strings.ToUpper(strings.TrimSpace(payload)) {
	case StateOn.String():
		return StateOn, true
	case StateOff.String():
		return StateOff, true
	default:
		return StateOff, false
	}
}

func (s State) String() string {
	if s == StateOn {
		return "ON"
	}
	return "OFF"
}

func NewStateTracker(initial State) *StateTracker {
	return &StateTracker{value: initial}
}

func (s *StateTracker) Get() State {
	s.valueMu.Lock()
	defer s.valueMu.Unlock()
	return s.value
}

func (s *StateTracker) Set(value State) {
	s.valueMu.Lock()
	defer s.valueMu.Unlock()
	s.value = value
}

func (a Aggregate) MarshalJSON() ([]byte, error) {
	out := make([]byte, 0, 96)
	out = append(out, `{"timestamp":`...)
	out = strconv.AppendInt(out, a.Timestamp.Unix(), 10)
	out = append(out, `,"ok":`...)
	out = strconv.AppendBool(out, a.OK)
	out = append(out, `,"status":`...)
	out = strconv.AppendQuote(out, string(a.Status))
	out = append(out, `,"score":`...)
	out = strconv.AppendInt(out, int64(a.Score), 10)
	out = append(out, '}')
	return out, nil
}

func (a Aggregate) AppendLineProtocol(buf *bytes.Buffer, timestamp int64) {
	schema.AppendLineProtocol(buf, a.Points, timestamp)
}

var (
	registryMu sync.RWMutex
	registry   = map[string]Plugin{}
)

func register(p Plugin) {
	registryMu.Lock()
	defer registryMu.Unlock()
	name := p.Name()
	if _, exists := registry[name]; exists {
		panic(fmt.Sprintf("duplicate plugin registration [%s]", name))
	}
	registry[name] = p
}

func registered() []Plugin {
	registryMu.RLock()
	defer registryMu.RUnlock()
	names := make([]string, 0, len(registry))
	for name := range registry {
		names = append(names, name)
	}
	sort.Strings(names)
	plugins := make([]Plugin, 0, len(names))
	for _, name := range names {
		plugins = append(plugins, registry[name])
	}
	return plugins
}
