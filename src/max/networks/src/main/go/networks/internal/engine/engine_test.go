package engine

import (
	"context"
	"errors"
	"sync"
	"testing"
	"time"

	"networks/internal/plugin"
)

type fakePlugin struct {
	name          string
	mode          plugin.Mode
	pollErr       error
	pollCount     *int
	aggregate     func(sampleBuffer []plugin.Sample) plugin.Aggregate
	panicAgg      bool
	commandErr    error
	commandStates []plugin.State
	state         *plugin.StateTracker
}

func (f *fakePlugin) Name() string { return f.name }

func (f *fakePlugin) Mode() plugin.Mode { return f.mode }

func (f *fakePlugin) Poll(context.Context) (plugin.Sample, error) {
	if f.pollCount != nil {
		*f.pollCount++
	}
	if f.pollErr != nil {
		return plugin.Sample{}, f.pollErr
	}
	return plugin.Sample{Points: []plugin.Point{plugin.NewPoint(nil, plugin.Int("v", 1))}}, nil
}

func (f *fakePlugin) Aggregate(sampleBuffer []plugin.Sample) (plugin.Aggregate, error) {
	if f.panicAgg {
		panic("boom")
	}
	if f.aggregate != nil {
		return f.aggregate(sampleBuffer), nil
	}
	return plugin.Aggregate{Status: plugin.StatusFit, OK: true, Score: 100}, nil
}

func (f *fakePlugin) Command(_ context.Context, state plugin.State) error {
	f.commandStates = append(f.commandStates, state)
	return f.commandErr
}

func (f *fakePlugin) State() *plugin.StateTracker { return f.state }

func newEngine(t *testing.T, plugins ...plugin.Plugin) *Engine {
	t.Helper()
	e, err := Create(Options{Plugins: plugins, PollPeriod: time.Minute, AggregatePeriod: 3 * time.Minute})
	if err != nil {
		t.Fatalf("create: %v", err)
	}
	return e
}

func TestEngine_CreatePeriodValidation(t *testing.T) {
	tests := []struct {
		name          string
		poll          time.Duration
		aggregate     time.Duration
		expectedError bool
	}{
		{name: "valid_multiple", poll: time.Minute, aggregate: 3 * time.Minute, expectedError: false},
		{name: "zero_poll", poll: 0, aggregate: time.Minute, expectedError: true},
		{name: "not_multiple", poll: 2 * time.Minute, aggregate: 5 * time.Minute, expectedError: true},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			_, err := Create(Options{Plugins: []plugin.Plugin{&fakePlugin{name: "a"}}, PollPeriod: test.poll, AggregatePeriod: test.aggregate})
			if (err != nil) != test.expectedError {
				t.Fatalf("error mismatch: got %v want error=%v", err, test.expectedError)
			}
		})
	}
}

func TestEngine_CycleAggregateOnly(t *testing.T) {
	count := 0
	p := &fakePlugin{name: "agg", pollCount: &count}
	e := newEngine(t, p)
	aggregates := e.AggregateSamples(context.Background(), e.plugins)
	if len(aggregates) != 1 {
		t.Fatalf("aggregate count: got %d want 1", len(aggregates))
	}
	if aggregates[0].Status != plugin.StatusFit || aggregates[0].Plugin != "agg" {
		t.Fatalf("unexpected aggregate: %+v", aggregates[0])
	}
	if count != 1 {
		t.Fatalf("poll count: got %d want 1", count)
	}
	if aggregates[0].Score != 100 {
		t.Fatalf("score: got %d want 100", aggregates[0].Score)
	}
}

func TestEngine_CyclePollErrorProducesDeadAggregate(t *testing.T) {
	p := &fakePlugin{name: "unreachable", pollErr: errors.New("boom"), aggregate: func(sampleBuffer []plugin.Sample) plugin.Aggregate {
		if len(sampleBuffer) == 1 && len(sampleBuffer[0].Points) == 0 {
			return plugin.Aggregate{Status: plugin.StatusDead, OK: false, Detail: "SOURCE_UNREACHABLE"}
		}
		return plugin.Aggregate{Status: plugin.StatusFit, OK: true}
	}}
	e := newEngine(t, p)
	aggregates := e.AggregateSamples(context.Background(), e.plugins)
	if aggregates[0].Status != plugin.StatusDead || aggregates[0].Detail != "SOURCE_UNREACHABLE" {
		t.Fatalf("expected dead aggregate, got %+v", aggregates[0])
	}
}

func TestEngine_CycleAggregatePanicRecovered(t *testing.T) {
	p := &fakePlugin{name: "panicky", panicAgg: true}
	e := newEngine(t, p)
	aggregates := e.AggregateSamples(context.Background(), e.plugins)
	if aggregates[0].Status != plugin.StatusDead || aggregates[0].Detail != "PLUGIN_PANIC" {
		t.Fatalf("expected recovered dead aggregate, got %+v", aggregates[0])
	}
}

func TestEngine_CycleConcurrentSafe(t *testing.T) {
	p := &fakePlugin{name: "poller", mode: plugin.ModeWindowed}
	e := newEngine(t, p)
	var wg sync.WaitGroup
	for i := 0; i < 16; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			for j := 0; j < 32; j++ {
				e.AggregateSamples(context.Background(), e.plugins)
				e.PollSamples(context.Background())
			}
		}()
	}
	wg.Wait()
	aggregates := e.AggregateSamples(context.Background(), e.plugins)
	if len(aggregates) != 1 || aggregates[0].Plugin != "poller" {
		t.Fatalf("expected aggregate for poller, got %+v", aggregates)
	}
}

func TestCommand_RunDispatchesToPlugin(t *testing.T) {
	p := &fakePlugin{name: "agg"}
	e := newEngine(t, p)
	e.runCommand(context.Background(), "agg", plugin.StateOn)
	if len(p.commandStates) != 1 || p.commandStates[0] != plugin.StateOn {
		t.Fatalf("command states: got %v want [ON]", p.commandStates)
	}
	e.runCommand(context.Background(), "missing", plugin.StateOff)
	if len(p.commandStates) != 1 {
		t.Fatalf("unknown plugin should not dispatch: got %v", p.commandStates)
	}
}

func TestEngine_AggregateSetsState(t *testing.T) {
	fit := &fakePlugin{name: "fit", state: plugin.NewStateTracker(plugin.StateOff)}
	dead := &fakePlugin{name: "dead", state: plugin.NewStateTracker(plugin.StateOn), aggregate: func([]plugin.Sample) plugin.Aggregate {
		return plugin.Diagnose(plugin.StatusDead, 0, "DOWN", "")
	}}
	e := newEngine(t, fit, dead)
	e.AggregateSamples(context.Background(), e.plugins)
	if got := fit.state.Get(); got != plugin.StateOn {
		t.Errorf("fit state: got %s want ON", got)
	}
	if got := dead.state.Get(); got != plugin.StateOff {
		t.Errorf("dead state: got %s want OFF", got)
	}
}

func TestSampleBuffer_BoundedRing(t *testing.T) {
	tests := []struct {
		name          string
		capacity      int
		adds          int
		expectedLen   int
		expectedFirst int
		expectedLast  int
		expectedError bool
	}{
		{name: "partial", capacity: 3, adds: 2, expectedLen: 2, expectedFirst: 0, expectedLast: 1, expectedError: false},
		{name: "exact", capacity: 3, adds: 3, expectedLen: 3, expectedFirst: 0, expectedLast: 2, expectedError: false},
		{name: "overflow", capacity: 3, adds: 10, expectedLen: 3, expectedFirst: 7, expectedLast: 9, expectedError: false},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			w := newSampleBuffer(test.capacity)
			for i := 0; i < test.adds; i++ {
				w.Add(plugin.Sample{Timestamp: time.Unix(int64(i), 0)})
			}
			if w.Len() != test.expectedLen {
				t.Fatalf("len mismatch: got %d want %d", w.Len(), test.expectedLen)
			}
			samples := w.Samples()
			if len(samples) != test.expectedLen {
				t.Fatalf("samples mismatch: got %d want %d", len(samples), test.expectedLen)
			}
			if got := int(samples[0].Timestamp.Unix()); got != test.expectedFirst {
				t.Fatalf("first mismatch: got %d want %d", got, test.expectedFirst)
			}
			if got := int(samples[len(samples)-1].Timestamp.Unix()); got != test.expectedLast {
				t.Fatalf("last mismatch: got %d want %d", got, test.expectedLast)
			}
		})
	}
}

func TestSampleBuffer_Reset(t *testing.T) {
	w := newSampleBuffer(2)
	w.Add(plugin.Sample{})
	w.Add(plugin.Sample{})
	w.Add(plugin.Sample{})
	w.Reset()
	if w.Len() != 0 {
		t.Fatalf("len after reset: got %d want 0", w.Len())
	}
	if w.Samples() != nil {
		t.Fatalf("samples after reset should be nil")
	}
}
