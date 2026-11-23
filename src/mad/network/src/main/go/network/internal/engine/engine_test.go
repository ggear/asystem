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
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			err := Create(&Engine{Plugins: []plugin.Plugin{&fakePlugin{name: "a"}}, PollPeriod: testCase.poll, AggregatePeriod: testCase.aggregate})
			if (err != nil) != testCase.expectedError {
				t.Fatalf("error mismatch: got %v want error=%v", err, testCase.expectedError)
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
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			if err := Create(testCase.engine); (err != nil) != testCase.wantErr {
				t.Fatalf("error mismatch: got %v want error=%v", err, testCase.wantErr)
			}
		})
	}
}

func TestEngine_CreatePacedValidation(t *testing.T) {
	tests := []struct {
		name          string
		period        time.Duration
		expectedError bool
	}{
		{name: "paced_multiple", period: 5 * time.Minute, expectedError: false},
		{name: "paced_at_poll", period: time.Minute, expectedError: false},
		{name: "paced_below_poll", period: time.Second, expectedError: false},
		{name: "paced_not_multiple_of_poll", period: 90 * time.Second, expectedError: true},
		{name: "paced_not_dividing_aggregate", period: 4 * time.Minute, expectedError: true},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			p := &fakePlugin{name: "paced", mode: plugin.ModeWindowed, pollPeriod: testCase.period}
			err := Create(&Engine{Plugins: []plugin.Plugin{p}, PollPeriod: time.Minute, AggregatePeriod: 15 * time.Minute})
			if (err != nil) != testCase.expectedError {
				t.Fatalf("error mismatch: got %v want error=%v", err, testCase.expectedError)
			}
		})
	}
}

func TestEngine_PollSamplesPacedStride(t *testing.T) {
	pacedCount, everyCount := 0, 0
	paced := &fakePlugin{name: "paced", mode: plugin.ModeWindowed, pollCount: &pacedCount, pollPeriod: 5 * time.Minute}
	every := &fakePlugin{name: "every", mode: plugin.ModeWindowed, pollCount: &everyCount}
	e := &Engine{Plugins: []plugin.Plugin{paced, every}, PollPeriod: time.Minute, AggregatePeriod: 15 * time.Minute}
	if err := Create(e); err != nil {
		t.Fatalf("create: %v", err)
	}
	for range 31 {
		e.PollSamples(context.Background())
	}
	if pacedCount != 7 {
		t.Errorf("paced poll count over 31 ticks: got %d want 7 (ticks 0, 5, … 30)", pacedCount)
	}
	if everyCount != 31 {
		t.Errorf("unpaced poll count over 31 ticks: got %d want 31", everyCount)
	}
	if got := len(e.copySamples("paced")); got != 3 {
		t.Errorf("paced window: got %d samples want 3 (15m aggregate over 5m polls)", got)
	}
	if got := len(e.copySamples("every")); got != 15 {
		t.Errorf("unpaced window: got %d samples want 15", got)
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
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			e := &Engine{sampleWindow: testCase.window, sampleBuffers: map[string][]plugin.Sample{}}
			for i := 0; i < testCase.adds; i++ {
				e.addSample("p", plugin.Sample{Timestamp: time.Unix(int64(i), 0)})
			}
			samples := e.copySamples("p")
			if len(samples) != testCase.expectedLen {
				t.Fatalf("len mismatch: got %d want %d", len(samples), testCase.expectedLen)
			}
			if got := int(samples[0].Timestamp.Unix()); got != testCase.expectedFirst {
				t.Fatalf("first mismatch: got %d want %d", got, testCase.expectedFirst)
			}
			if got := int(samples[len(samples)-1].Timestamp.Unix()); got != testCase.expectedLast {
				t.Fatalf("last mismatch: got %d want %d", got, testCase.expectedLast)
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
	if aggregates[0].Status != plugin.StatusDead || aggregates[0].Reason != "PLUGIN_ERROR: boom" {
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
	for range 16 {
		wg.Go(func() {
			for range 32 {
				e.AggregateSamples(context.Background(), e.Plugins)
				e.PollSamples(context.Background())
			}
		})
	}
	wg.Wait()
	aggregates := e.AggregateSamples(context.Background(), e.Plugins)
	if len(aggregates) != 1 || aggregates[0].Plugin != "poller" {
		t.Fatalf("expected aggregate for poller, got %+v", aggregates)
	}
}

func TestEngine_AggregateChangesPublishesOnlyStateChanges(t *testing.T) {
	ok := true
	windowed := &fakePlugin{name: "windowed", mode: plugin.ModeWindowed, state: plugin.NewStateTracker(plugin.StateOn), aggregate: func([]plugin.Sample) plugin.Aggregate {
		if ok {
			return plugin.Diagnose(plugin.StatusFit, 100, "UP")
		}
		return plugin.Diagnose(plugin.StatusDead, 0, "DOWN")
	}}
	snapshotCount := 0
	snapshot := &fakePlugin{name: "snapshot", mode: plugin.ModeSnapshot, pollCount: &snapshotCount, state: plugin.NewStateTracker(plugin.StateOn)}
	e := newEngine(t, windowed, snapshot)
	if got := e.AggregateChanges(); len(got) != 0 {
		t.Fatalf("changes before any poll: got %d want 0", len(got))
	}
	steps := []struct {
		ok       bool
		changes  int
		expected plugin.State
	}{
		{ok: true, changes: 0, expected: plugin.StateOn},
		{ok: false, changes: 1, expected: plugin.StateOff},
		{ok: false, changes: 0, expected: plugin.StateOff},
		{ok: true, changes: 1, expected: plugin.StateOn},
	}
	for index, step := range steps {
		ok = step.ok
		e.PollSamples(context.Background())
		got := e.AggregateChanges()
		if len(got) != step.changes {
			t.Fatalf("step %d changes: got %d want %d", index, len(got), step.changes)
		}
		if len(got) == 1 && got[0].Plugin != "windowed" {
			t.Fatalf("step %d changed plugin: got %q want windowed", index, got[0].Plugin)
		}
		if state := windowed.state.Get(); state != step.expected {
			t.Fatalf("step %d state: got %s want %s", index, state, step.expected)
		}
	}
	if snapshotCount != 0 {
		t.Fatalf("snapshot poll count while on: got %d want 0", snapshotCount)
	}
}

func TestEngine_PollSamplesRecoversDownPlugins(t *testing.T) {
	snapshotCount, pacedCount := 0, 0
	snapshot := &fakePlugin{name: "snapshot", mode: plugin.ModeSnapshot, pollCount: &snapshotCount, state: plugin.NewStateTracker(plugin.StateOn)}
	paced := &fakePlugin{name: "paced", mode: plugin.ModeWindowed, pollCount: &pacedCount, pollPeriod: 5 * time.Minute, state: plugin.NewStateTracker(plugin.StateOn)}
	e := &Engine{Plugins: []plugin.Plugin{snapshot, paced}, PollPeriod: time.Minute, AggregatePeriod: 15 * time.Minute}
	if err := Create(e); err != nil {
		t.Fatalf("create: %v", err)
	}
	for range 3 {
		e.PollSamples(context.Background())
	}
	if snapshotCount != 0 || pacedCount != 1 {
		t.Fatalf("polls while up: got snapshot [%d] paced [%d] want 0 and 1", snapshotCount, pacedCount)
	}
	snapshot.state.Set(plugin.StateOff)
	paced.state.Set(plugin.StateOff)
	for range 3 {
		e.PollSamples(context.Background())
	}
	if snapshotCount != 3 || pacedCount != 4 {
		t.Fatalf("polls while down: got snapshot [%d] paced [%d] want 3 and 4", snapshotCount, pacedCount)
	}
	if got := len(e.copySamples("snapshot")); got != 1 {
		t.Fatalf("snapshot window: got %d samples want 1", got)
	}
}

func TestEngine_AggregateChangesRestoresSnapshotPlugin(t *testing.T) {
	healthy := false
	p := &fakePlugin{name: "snapshot", mode: plugin.ModeSnapshot, state: plugin.NewStateTracker(plugin.StateOn), aggregate: func([]plugin.Sample) plugin.Aggregate {
		if healthy {
			return plugin.Diagnose(plugin.StatusFit, 100, "UP")
		}
		return plugin.Diagnose(plugin.StatusDead, 0, "DOWN")
	}}
	e := newEngine(t, p)
	e.AggregateSamples(context.Background(), e.Plugins)
	if p.state.Get() != plugin.StateOff {
		t.Fatalf("state after failed aggregate: got %s want OFF", p.state.Get())
	}
	e.PollSamples(context.Background())
	if got := e.AggregateChanges(); len(got) != 0 {
		t.Fatalf("changes while still down: got %d want 0", len(got))
	}
	healthy = true
	e.PollSamples(context.Background())
	if got := e.AggregateChanges(); len(got) != 1 || p.state.Get() != plugin.StateOn {
		t.Fatalf("changes on restoration: got %d state %s want 1 and ON", len(got), p.state.Get())
	}
	e.PollSamples(context.Background())
	if got := e.AggregateChanges(); len(got) != 0 {
		t.Fatalf("changes once restored: got %d want 0", len(got))
	}
}

func TestEngine_AggregateChangesIgnoresStaleSampleOfRecoveredSnapshotPlugin(t *testing.T) {
	p := &fakePlugin{name: "snapshot", mode: plugin.ModeSnapshot, pollReading: -1, state: plugin.NewStateTracker(plugin.StateOn), aggregate: func(samples []plugin.Sample) plugin.Aggregate {
		if samples[len(samples)-1].Readings.([]int)[0] < 0 {
			return plugin.Diagnose(plugin.StatusDead, 0, "DOWN")
		}
		return plugin.Diagnose(plugin.StatusFit, 100, "UP")
	}}
	e := newEngine(t, p)
	e.AggregateSamples(context.Background(), e.Plugins)
	e.PollSamples(context.Background())
	p.pollReading = 1
	e.AggregateSamples(context.Background(), e.Plugins)
	if got := e.AggregateChanges(); len(got) != 0 || p.state.Get() != plugin.StateOn {
		t.Fatalf("changes after recovery at aggregate: got %d state %s want 0 and ON", len(got), p.state.Get())
	}
}

func TestEngine_HandleCommand(t *testing.T) {
	tests := []struct {
		name              string
		plugin            string
		payload           string
		initialState      plugin.State
		pollErr           error
		aggregate         func([]plugin.Sample) plugin.Aggregate
		gap               time.Duration
		repeat            int
		expectedPolls     int
		expectedState     plugin.State
		expectedSampleLen int
	}{
		{name: "on_repolls_and_recovers", plugin: "agg", payload: "ON", initialState: plugin.StateOff, repeat: 1, expectedPolls: 1, expectedState: plugin.StateOn, expectedSampleLen: 1},
		{name: "off_repolls_and_stays_dead", plugin: "agg", payload: "OFF", initialState: plugin.StateOff, repeat: 1, expectedPolls: 1, expectedState: plugin.StateOff, expectedSampleLen: 1,
			aggregate: func([]plugin.Sample) plugin.Aggregate { return plugin.Diagnose(plugin.StatusDead, 0, "DOWN") }},
		{name: "off_repolls_and_goes_dead", plugin: "agg", payload: "off", initialState: plugin.StateOn, repeat: 1, expectedPolls: 1, expectedState: plugin.StateOff, expectedSampleLen: 1,
			aggregate: func([]plugin.Sample) plugin.Aggregate { return plugin.Diagnose(plugin.StatusDead, 0, "DOWN") }},
		{name: "repeat_inside_gap_is_dropped", plugin: "agg", payload: "ON", initialState: plugin.StateOff, repeat: 3, gap: time.Hour, expectedPolls: 1, expectedState: plugin.StateOn, expectedSampleLen: 1},
		{name: "repeat_after_gap_polls_again", plugin: "agg", payload: "ON", initialState: plugin.StateOff, repeat: 3, expectedPolls: 3, expectedState: plugin.StateOn, expectedSampleLen: 1},
		{name: "unparseable_payload", plugin: "agg", payload: "garbage", initialState: plugin.StateOff, repeat: 1, expectedPolls: 0, expectedState: plugin.StateOff},
		{name: "unknown_plugin", plugin: "missing", payload: "ON", initialState: plugin.StateOff, repeat: 1, expectedPolls: 0, expectedState: plugin.StateOff},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			polls := 0
			p := &fakePlugin{name: "agg", pollCount: &polls, aggregate: testCase.aggregate, state: plugin.NewStateTracker(testCase.initialState)}
			e := newEngine(t, p)
			e.refreshGap = testCase.gap
			for range testCase.repeat {
				e.handleCommand(context.Background(), testCase.plugin, []byte(testCase.payload))
			}
			if polls != testCase.expectedPolls {
				t.Errorf("polls: got %d want %d", polls, testCase.expectedPolls)
			}
			if got := p.state.Get(); got != testCase.expectedState {
				t.Errorf("state: got %s want %s", got, testCase.expectedState)
			}
			if got := len(e.copySamples("agg")); got != testCase.expectedSampleLen {
				t.Errorf("samples: got %d want %d", got, testCase.expectedSampleLen)
			}
		})
	}
}

func TestEngine_HandleCommandInFlight(t *testing.T) {
	polls := 0
	release := make(chan struct{})
	p := &fakePlugin{name: "agg", pollCount: &polls, pollGate: release}
	e := newEngine(t, p)
	e.refreshGap = 0
	time.AfterFunc(200*time.Millisecond, func() { close(release) })
	done := make(chan struct{})
	go func() {
		e.handleCommand(context.Background(), "agg", []byte("ON"))
		close(done)
	}()
	for {
		e.refreshMu.Lock()
		busy := e.refreshing["agg"]
		e.refreshMu.Unlock()
		if busy {
			break
		}
		time.Sleep(time.Millisecond)
	}
	e.handleCommand(context.Background(), "agg", []byte("ON"))
	<-done
	if polls != 1 {
		t.Errorf("polls: got %d want 1", polls)
	}
}

func TestEngine_HandleCommandWaitsForARunningPoll(t *testing.T) {
	release := make(chan struct{})
	entered := make(chan struct{}, 2)
	p := &fakePlugin{name: "snapshot", mode: plugin.ModeSnapshot, pollGate: release, pollEntered: entered, state: plugin.NewStateTracker(plugin.StateOff)}
	e := newEngine(t, p)
	e.refreshGap = 0
	var wg sync.WaitGroup
	wg.Go(func() { e.PollSamples(context.Background()) })
	<-entered
	wg.Go(func() { e.handleCommand(context.Background(), "snapshot", []byte("ON")) })
	select {
	case <-entered:
		t.Fatalf("command poll: got a poll running alongside the loop poll want it to wait")
	case <-time.After(100 * time.Millisecond):
	}
	close(release)
	wg.Wait()
	select {
	case <-entered:
	default:
		t.Fatalf("command poll: got none want one after the loop poll finished")
	}
}

var (
	engineTestRelation = schema.Declare("enginetest/detail", "detail used by the engine tests", "15 min")
	engineTestValue    = engineTestRelation.Int("v", "count", "counter used by the engine tests")
)

type fakePlugin struct {
	name         string
	mode         plugin.Mode
	pollErr      error
	pollCount    *int
	panicPoll    bool
	aggregate    func(sampleBuffer []plugin.Sample) plugin.Aggregate
	aggregateErr error
	panicAgg     bool
	pollGate     chan struct{}
	pollEntered  chan struct{}
	state        *plugin.StateTracker
	pollPeriod   time.Duration
	pollReading  int
}

func (f *fakePlugin) Name() string { return f.name }

func (f *fakePlugin) Mode() plugin.Mode { return f.mode }

func (f *fakePlugin) Poll(context.Context) (plugin.Sample, error) {
	if f.pollCount != nil {
		*f.pollCount++
	}
	if f.pollEntered != nil {
		f.pollEntered <- struct{}{}
	}
	if f.pollGate != nil {
		<-f.pollGate
	}
	if f.panicPoll {
		panic("poll boom")
	}
	if f.pollErr != nil {
		return plugin.Sample{}, f.pollErr
	}
	if f.pollReading != 0 {
		return plugin.Sample{Readings: []int{f.pollReading}}, nil
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

func (f *fakePlugin) State() *plugin.StateTracker { return f.state }

func (f *fakePlugin) PollPeriod() time.Duration { return f.pollPeriod }

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
