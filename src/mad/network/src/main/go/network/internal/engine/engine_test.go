package engine

import (
	"context"
	"errors"
	"strings"
	"sync"
	"testing"
	"time"

	"network/internal/plugin"
	"network/internal/schema"
)

func TestEngine_CreatePeriodValidation(t *testing.T) {
	tests := []struct {
		name          string
		poll          time.Duration
		aggregate     time.Duration
		expectedError bool
	}{
		{name: "valid_multiple", poll: time.Minute, aggregate: 3 * time.Minute, expectedError: false},
		{name: "zero_poll", poll: 0, aggregate: time.Minute, expectedError: true},
		{name: "zero_aggregate", poll: time.Minute, aggregate: 0, expectedError: true},
		{name: "not_multiple", poll: 2 * time.Minute, aggregate: 5 * time.Minute, expectedError: true},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			err := Create(&Engine{Plugins: []plugin.Plugin{&fakePlugin{name: "a"}}, PollPeriod: test.poll, AggregatePeriod: test.aggregate})
			if (err != nil) != test.expectedError {
				t.Fatalf("error mismatch: got %v want error=%v", err, test.expectedError)
			}
		})
	}
}

func TestEngine_CreatePluginValidation(t *testing.T) {
	var nilPlugin *fakePlugin
	tests := []struct {
		name    string
		engine  *Engine
		wantErr bool
	}{
		{name: "nil_engine", engine: nil, wantErr: true},
		{name: "no_plugins", engine: &Engine{Plugins: nil, PollPeriod: time.Minute, AggregatePeriod: time.Minute}, wantErr: true},
		{name: "nil_plugin", engine: &Engine{Plugins: []plugin.Plugin{nil}, PollPeriod: time.Minute, AggregatePeriod: time.Minute}, wantErr: true},
		{name: "typed_nil_plugin", engine: &Engine{Plugins: []plugin.Plugin{nilPlugin}, PollPeriod: time.Minute, AggregatePeriod: time.Minute}, wantErr: true},
		{name: "duplicate_name", engine: &Engine{Plugins: []plugin.Plugin{&fakePlugin{name: "a"}, &fakePlugin{name: "a"}}, PollPeriod: time.Minute, AggregatePeriod: time.Minute}, wantErr: true},
		{name: "valid", engine: &Engine{Plugins: []plugin.Plugin{&fakePlugin{name: "a"}}, PollPeriod: time.Minute, AggregatePeriod: time.Minute}, wantErr: false},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			if err := Create(test.engine); (err != nil) != test.wantErr {
				t.Fatalf("error mismatch: got %v want error=%v", err, test.wantErr)
			}
		})
	}
}

func TestEngine_CreateBuffersOnlyWindowed(t *testing.T) {
	e := newEngine(t,
		&fakePlugin{name: "windowed", mode: plugin.ModeWindowed},
		&fakePlugin{name: "snapshot", mode: plugin.ModeSnapshot},
	)
	if _, ok := e.sampleBuffers["windowed"]; !ok {
		t.Fatalf("windowed plugin should have a buffer")
	}
	if _, ok := e.sampleBuffers["snapshot"]; ok {
		t.Fatalf("snapshot plugin should not have a buffer")
	}
}

func TestEngine_RunAlreadyCanceled(t *testing.T) {
	count := 0
	e := newEngine(t, &fakePlugin{name: "a", mode: plugin.ModeWindowed, pollCount: &count})
	ctx, cancel := context.WithCancel(context.Background())
	cancel()
	if err := e.Run(ctx); !errors.Is(err, context.Canceled) {
		t.Fatalf("run error: got %v want %v", err, context.Canceled)
	}
	if count != 0 {
		t.Fatalf("poll count: got %d want 0", count)
	}
}

func TestEngine_RunSingleCheck(t *testing.T) {
	count := 0
	p := &fakePlugin{name: "windowed", mode: plugin.ModeWindowed, pollCount: &count}
	e := newEngine(t, p)
	if err := e.Run(context.Background()); err != nil {
		t.Fatalf("run: got %v want nil", err)
	}
	if count != 1 {
		t.Fatalf("poll count in single check: got %d want 1", count)
	}
}

func TestEngine_RunPollsBeforeScheduledAggregate(t *testing.T) {
	count := 0
	aggregateCount := 0
	observedPolls := make(chan int, 1)
	ctx, cancel := context.WithCancel(context.Background())
	p := &fakePlugin{name: "a", mode: plugin.ModeWindowed, pollCount: &count}
	p.aggregate = func([]plugin.Sample) plugin.Aggregate {
		aggregateCount++
		if aggregateCount == 2 {
			observedPolls <- count
			cancel()
		}
		return plugin.Aggregate{Status: plugin.StatusFit, OK: true}
	}
	e := &Engine{DaemonLoop: true, Plugins: []plugin.Plugin{p}, PollPeriod: time.Millisecond, AggregatePeriod: 2 * time.Millisecond}
	if err := Create(e); err != nil {
		t.Fatalf("create: %v", err)
	}
	if err := e.Run(ctx); !errors.Is(err, context.Canceled) {
		t.Fatalf("run error: got %v want %v", err, context.Canceled)
	}
	if got := <-observedPolls; got != 3 {
		t.Fatalf("poll count at scheduled aggregate: got %d want 3", got)
	}
}

func TestEngine_PollSamplesOnlyPollsWindowed(t *testing.T) {
	windowedCount, snapshotCount := 0, 0
	windowed := &fakePlugin{name: "windowed", mode: plugin.ModeWindowed, pollCount: &windowedCount}
	snapshot := &fakePlugin{name: "snapshot", mode: plugin.ModeSnapshot, pollCount: &snapshotCount}
	e := newEngine(t, windowed, snapshot)
	e.PollSamples(context.Background())
	if windowedCount != 1 {
		t.Fatalf("windowed poll count: got %d want 1", windowedCount)
	}
	if snapshotCount != 0 {
		t.Fatalf("snapshot poll count: got %d want 0", snapshotCount)
	}
	if samples := e.copySamples("windowed"); len(samples) != 1 {
		t.Fatalf("windowed buffered samples: got %d want 1", len(samples))
	}
}

func TestEngine_SampleWindow(t *testing.T) {
	tests := []struct {
		name          string
		window        int
		adds          int
		expectedLen   int
		expectedFirst int
		expectedLast  int
	}{
		{name: "partial", window: 3, adds: 2, expectedLen: 2, expectedFirst: 0, expectedLast: 1},
		{name: "exact", window: 3, adds: 3, expectedLen: 3, expectedFirst: 0, expectedLast: 2},
		{name: "overflow", window: 3, adds: 10, expectedLen: 3, expectedFirst: 7, expectedLast: 9},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			e := &Engine{sampleWindow: test.window, sampleBuffers: map[string][]plugin.Sample{}}
			for i := 0; i < test.adds; i++ {
				e.addSample("p", plugin.Sample{Timestamp: time.Unix(int64(i), 0)})
			}
			samples := e.copySamples("p")
			if len(samples) != test.expectedLen {
				t.Fatalf("len mismatch: got %d want %d", len(samples), test.expectedLen)
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

func TestEngine_CycleAggregateOnly(t *testing.T) {
	count := 0
	p := &fakePlugin{name: "agg", pollCount: &count}
	e := newEngine(t, p)
	aggregates := e.AggregateSamples(context.Background(), e.Plugins)
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

func TestEngine_CycleStampsWindowSeconds(t *testing.T) {
	p := &fakePlugin{name: "agg"}
	e := newEngine(t, p)
	aggregates := e.AggregateSamples(context.Background(), e.Plugins)
	if aggregates[0].WindowSeconds != 180 {
		t.Fatalf("window seconds: got %d want 180", aggregates[0].WindowSeconds)
	}
}

func TestEngine_CycleWindowedFallbackPolls(t *testing.T) {
	count := 0
	p := &fakePlugin{name: "windowed", mode: plugin.ModeWindowed, pollCount: &count}
	e := newEngine(t, p)
	aggregates := e.AggregateSamples(context.Background(), e.Plugins)
	if count != 1 {
		t.Fatalf("fallback poll count: got %d want 1", count)
	}
	if len(aggregates) != 1 || aggregates[0].Plugin != "windowed" {
		t.Fatalf("expected one aggregate from fallback poll, got %+v", aggregates)
	}
}

func TestEngine_CyclePollErrorProducesDeadAggregate(t *testing.T) {
	p := &fakePlugin{name: "unreachable", pollErr: errors.New("boom"), aggregate: func(sampleBuffer []plugin.Sample) plugin.Aggregate {
		if len(sampleBuffer) == 1 && sampleBuffer[0].Readings == nil {
			return plugin.Aggregate{Status: plugin.StatusDead, OK: false, Reason: "SOURCE_UNREACHABLE"}
		}
		return plugin.Aggregate{Status: plugin.StatusFit, OK: true}
	}}
	e := newEngine(t, p)
	aggregates := e.AggregateSamples(context.Background(), e.Plugins)
	if aggregates[0].Status != plugin.StatusDead || aggregates[0].Reason != "SOURCE_UNREACHABLE" {
		t.Fatalf("expected dead aggregate, got %+v", aggregates[0])
	}
}

func TestEngine_CyclePollPanicRecovered(t *testing.T) {
	p := &fakePlugin{name: "panicky", panicPoll: true, aggregate: func(sampleBuffer []plugin.Sample) plugin.Aggregate {
		if len(sampleBuffer) == 1 && sampleBuffer[0].Readings == nil {
			return plugin.Aggregate{Status: plugin.StatusDead, OK: false, Reason: "SOURCE_UNREACHABLE"}
		}
		return plugin.Aggregate{Status: plugin.StatusFit, OK: true}
	}}
	e := newEngine(t, p)
	aggregates := e.AggregateSamples(context.Background(), e.Plugins)
	if len(aggregates) != 1 || aggregates[0].Plugin != "panicky" {
		t.Fatalf("expected one aggregate for panicky, got %+v", aggregates)
	}
	if aggregates[0].Status != plugin.StatusDead || aggregates[0].Reason != "SOURCE_UNREACHABLE" {
		t.Fatalf("poll panic should yield empty sample, got %+v", aggregates[0])
	}
}

func TestEngine_CycleAggregatePanicRecovered(t *testing.T) {
	p := &fakePlugin{name: "panicky", panicAgg: true}
	e := newEngine(t, p)
	aggregates := e.AggregateSamples(context.Background(), e.Plugins)
	if aggregates[0].Status != plugin.StatusDead || !strings.HasPrefix(aggregates[0].Reason, "PLUGIN_PANIC") {
		t.Fatalf("expected recovered dead aggregate, got %+v", aggregates[0])
	}
}

func TestEngine_CycleAggregateErrorProducesDeadAggregate(t *testing.T) {
	p := &fakePlugin{name: "broken", aggregateErr: errors.New("boom")}
	e := newEngine(t, p)
	aggregates := e.AggregateSamples(context.Background(), e.Plugins)
	if aggregates[0].Status != plugin.StatusDead || aggregates[0].Reason != "PLUGIN_ERROR: [boom]" {
		t.Fatalf("expected aggregate error diagnosis, got %+v", aggregates[0])
	}
}

func TestEngine_CycleSetsState(t *testing.T) {
	fit := &fakePlugin{name: "fit", state: plugin.NewStateTracker(plugin.StateOff)}
	dead := &fakePlugin{name: "dead", state: plugin.NewStateTracker(plugin.StateOn), aggregate: func([]plugin.Sample) plugin.Aggregate {
		return plugin.Diagnose(plugin.StatusDead, 0, "DOWN")
	}}
	e := newEngine(t, fit, dead)
	e.AggregateSamples(context.Background(), e.Plugins)
	if got := fit.state.Get(); got != plugin.StateOn {
		t.Errorf("fit state: got %s want ON", got)
	}
	if got := dead.state.Get(); got != plugin.StateOff {
		t.Errorf("dead state: got %s want OFF", got)
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
				e.AggregateSamples(context.Background(), e.Plugins)
				e.PollSamples(context.Background())
			}
		}()
	}
	wg.Wait()
	aggregates := e.AggregateSamples(context.Background(), e.Plugins)
	if len(aggregates) != 1 || aggregates[0].Plugin != "poller" {
		t.Fatalf("expected aggregate for poller, got %+v", aggregates)
	}
}

func TestEngine_HandleCommand(t *testing.T) {
	p := &fakePlugin{name: "agg"}
	e := newEngine(t, p)
	e.handleCommand(context.Background(), "agg", []byte("ON"))
	if len(p.commandStates) != 1 || p.commandStates[0] != plugin.StateOn {
		t.Fatalf("command states after ON: got %v want [ON]", p.commandStates)
	}
	e.handleCommand(context.Background(), "agg", []byte("garbage"))
	if len(p.commandStates) != 1 {
		t.Fatalf("unparseable payload should not dispatch: got %v", p.commandStates)
	}
}

func TestEngine_RunCommandDispatchesToPlugin(t *testing.T) {
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

var (
	engineTestRelation = schema.Declare("enginetest/detail", "detail used by the engine tests", "15 min")
	engineTestValue    = engineTestRelation.Int("v", "count", "counter used by the engine tests")
)

type fakePlugin struct {
	name          string
	mode          plugin.Mode
	pollErr       error
	pollCount     *int
	panicPoll     bool
	aggregate     func(sampleBuffer []plugin.Sample) plugin.Aggregate
	aggregateErr  error
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
	if f.panicPoll {
		panic("poll boom")
	}
	if f.pollErr != nil {
		return plugin.Sample{}, f.pollErr
	}
	return plugin.Sample{Readings: []int{1}}, nil
}

func (f *fakePlugin) Aggregate(sampleBuffer []plugin.Sample) (plugin.Aggregate, error) {
	if f.panicAgg {
		panic("boom")
	}
	if f.aggregate != nil {
		return f.aggregate(sampleBuffer), f.aggregateErr
	}
	return plugin.Aggregate{Status: plugin.StatusFit, OK: true, Score: 100}, f.aggregateErr
}

func (f *fakePlugin) Command(_ context.Context, state plugin.State) error {
	f.commandStates = append(f.commandStates, state)
	return f.commandErr
}

func (f *fakePlugin) State() *plugin.StateTracker { return f.state }

func newEngine(t *testing.T, plugins ...plugin.Plugin) *Engine {
	t.Helper()
	e := &Engine{Plugins: plugins, PollPeriod: time.Minute, AggregatePeriod: 3 * time.Minute}
	if err := Create(e); err != nil {
		t.Fatalf("create: %v", err)
	}
	return e
}

func TestEngine_AggregateAppendsDiagnosisPoint(t *testing.T) {
	p := &fakePlugin{name: "agg", aggregate: func([]plugin.Sample) plugin.Aggregate {
		return plugin.Aggregate{Status: plugin.StatusSick, OK: true, Score: 42,
			Points: []schema.Point{engineTestRelation.Point(engineTestValue.Of(1))}}
	}}
	e := newEngine(t, p)
	aggregates := e.AggregateSamples(context.Background(), e.Plugins)
	if len(aggregates) != 1 {
		t.Fatalf("aggregates: got %d want 1", len(aggregates))
	}
	points := aggregates[0].Points
	if len(points) != 2 {
		t.Fatalf("points: got %d want 2 (the plugin point plus the diagnosis point)", len(points))
	}
	if path := points[1].Path(); path != "diagnosis/plugin" {
		t.Fatalf("appended point path: got %q want %q", path, "diagnosis/plugin")
	}
}

func TestEngine_AggregatePanicStillReportsDiagnosisPoint(t *testing.T) {
	p := &fakePlugin{name: "agg", panicAgg: true}
	e := newEngine(t, p)
	aggregates := e.AggregateSamples(context.Background(), e.Plugins)
	points := aggregates[0].Points
	if len(points) != 1 || points[0].Path() != "diagnosis/plugin" {
		t.Fatalf("points after panic: got %v want a single diagnosis point", points)
	}
}
