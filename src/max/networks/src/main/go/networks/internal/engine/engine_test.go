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
	name      string
	pollPhase bool
	pollErr   error
	pollCount *int
	aggregate func(sampleBuffer []plugin.Message) plugin.Message
	panicAgg  bool
}

func (f *fakePlugin) Name() string { return f.name }

func (f *fakePlugin) PollPhase() bool { return f.pollPhase }

func (f *fakePlugin) Poll(context.Context) (plugin.Message, error) {
	if f.pollCount != nil {
		*f.pollCount++
	}
	if f.pollErr != nil {
		return plugin.Message{}, f.pollErr
	}
	return plugin.Message{Points: []plugin.Point{plugin.NewPoint(nil, plugin.Int("v", 1))}}, nil
}

func (f *fakePlugin) Aggregate(sampleBuffer []plugin.Message) (plugin.Message, error) {
	if f.panicAgg {
		panic("boom")
	}
	if f.aggregate != nil {
		return f.aggregate(sampleBuffer), nil
	}
	return plugin.Message{Status: plugin.StatusFit, OK: true, Score: 100}, nil
}

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
	p := &fakePlugin{name: "agg", pollPhase: false, pollCount: &count}
	e := newEngine(t, p)
	vitals := e.Cycle(context.Background(), e.plugins)
	if len(vitals) != 1 {
		t.Fatalf("vitals count: got %d want 1", len(vitals))
	}
	if vitals[0].Status != plugin.StatusFit || vitals[0].Plugin != "agg" {
		t.Fatalf("unexpected vitals: %+v", vitals[0])
	}
	if count != 1 {
		t.Fatalf("poll count: got %d want 1", count)
	}
	if vitals[0].Score != 100 {
		t.Fatalf("score: got %d want 100", vitals[0].Score)
	}
}

func TestEngine_CyclePollErrorProducesDeadVitals(t *testing.T) {
	p := &fakePlugin{name: "unreachable", pollPhase: false, pollErr: errors.New("boom"), aggregate: func(sampleBuffer []plugin.Message) plugin.Message {
		if len(sampleBuffer) == 1 && len(sampleBuffer[0].Points) == 0 {
			return plugin.Message{Status: plugin.StatusDead, OK: false, Detail: "SOURCE_UNREACHABLE"}
		}
		return plugin.Message{Status: plugin.StatusFit, OK: true}
	}}
	e := newEngine(t, p)
	vitals := e.Cycle(context.Background(), e.plugins)
	if vitals[0].Status != plugin.StatusDead || vitals[0].Detail != "SOURCE_UNREACHABLE" {
		t.Fatalf("expected dead vitals, got %+v", vitals[0])
	}
}

func TestEngine_CycleAggregatePanicRecovered(t *testing.T) {
	p := &fakePlugin{name: "panicky", pollPhase: false, panicAgg: true}
	e := newEngine(t, p)
	vitals := e.Cycle(context.Background(), e.plugins)
	if vitals[0].Status != plugin.StatusDead || vitals[0].Detail != "PLUGIN_PANIC" {
		t.Fatalf("expected recovered dead vitals, got %+v", vitals[0])
	}
}

func TestEngine_CycleConcurrentSafe(t *testing.T) {
	p := &fakePlugin{name: "poller", pollPhase: true}
	e := newEngine(t, p)
	var wg sync.WaitGroup
	for i := 0; i < 16; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			for j := 0; j < 32; j++ {
				e.Cycle(context.Background(), e.plugins)
				e.pollOnce(context.Background())
			}
		}()
	}
	wg.Wait()
	vitals := e.Cycle(context.Background(), e.plugins)
	if len(vitals) != 1 || vitals[0].Plugin != "poller" {
		t.Fatalf("expected vitals for poller, got %+v", vitals)
	}
}

func TestCommand_RunResultChannel(t *testing.T) {
	p := &fakePlugin{name: "agg"}
	e := newEngine(t, p)
	result := make(chan plugin.Message, 1)
	e.runCommand(context.Background(), command{Action: "check", Plugin: "agg", Result: result, Source: "cli"})
	select {
	case vitals := <-result:
		if vitals.Status != plugin.StatusFit {
			t.Fatalf("unexpected vitals: %+v", vitals)
		}
	case <-time.After(time.Second):
		t.Fatal("no result received")
	}
	if _, open := <-result; open {
		t.Fatal("result channel should be closed after draining")
	}
}

func TestCommand_EnqueueDropsWhenFull(t *testing.T) {
	p := &fakePlugin{name: "agg"}
	e := newEngine(t, p)
	for i := 0; i < commandQueueSize; i++ {
		e.enqueue(command{Action: "check", Source: "mqtt"})
	}
	done := make(chan struct{})
	go func() {
		e.enqueue(command{Action: "check", Source: "mqtt"})
		close(done)
	}()
	select {
	case <-done:
	case <-time.After(time.Second):
		t.Fatal("enqueue blocked when queue full")
	}
	if len(e.commands) != commandQueueSize {
		t.Fatalf("queue length: got %d want %d", len(e.commands), commandQueueSize)
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
				w.Add(plugin.Message{Score: i})
			}
			if w.Len() != test.expectedLen {
				t.Fatalf("len mismatch: got %d want %d", w.Len(), test.expectedLen)
			}
			msgs := w.Messages()
			if len(msgs) != test.expectedLen {
				t.Fatalf("messages mismatch: got %d want %d", len(msgs), test.expectedLen)
			}
			if msgs[0].Score != test.expectedFirst {
				t.Fatalf("first mismatch: got %d want %d", msgs[0].Score, test.expectedFirst)
			}
			if msgs[len(msgs)-1].Score != test.expectedLast {
				t.Fatalf("last mismatch: got %d want %d", msgs[len(msgs)-1].Score, test.expectedLast)
			}
		})
	}
}

func TestSampleBuffer_Reset(t *testing.T) {
	w := newSampleBuffer(2)
	w.Add(plugin.Message{Score: 1})
	w.Add(plugin.Message{Score: 2})
	w.Add(plugin.Message{Score: 3})
	w.Reset()
	if w.Len() != 0 {
		t.Fatalf("len after reset: got %d want 0", w.Len())
	}
	if w.Messages() != nil {
		t.Fatalf("messages after reset should be nil")
	}
}
