package probe

import (
	"context"
	"errors"
	"sync"
	"testing"
	"time"

	"supervisor/internal/config"
	"supervisor/internal/metric"
)

func TestProbe_ExecuteProbes(t *testing.T) {
	tests := []struct {
		name             string
		createErr        error
		expectExecCalled bool
	}{
		{
			name:             "happy_create_error_skips_execute",
			createErr:        errors.New("expected error during unit test"),
			expectExecCalled: false,
		},
		{
			name:             "happy_executes_and_closes_on_cancel",
			expectExecCalled: true,
		},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			mock := &mockProbe{
				metricsList: []metric.ID{metric.MetricHostUsedProcessor},
				createErr:   tt.createErr,
			}
			for index := range probesByMetricMask {
				probesByMetricMask[index] = nil
			}
			execProbes = nil
			registerProbes(func() probe { return mock })
			ctx, cancel := context.WithCancel(context.Background())
			defer cancel()
			cache := metric.NewRecordCache()
			cache.Store(metric.NewRecordGUID(metric.MetricHostUsedProcessor, "localhost"), &metric.Record{})
			if err := Create("", cache, config.Periods{PollSecs: 1.0, PulseSecs: 1.0}); err != nil {
				t.Fatalf("Create failed: %v", err)
			}
			done := make(chan error, 1)
			go func() {
				done <- Execute(ctx)
			}()
			time.Sleep(1100 * time.Millisecond)
			cancel()
			if err := <-done; !errors.Is(err, context.Canceled) {
				t.Fatalf("expected context cancellation, got %v", err)
			}
			createCalls, executeCalls := mock.snapshot()
			if createCalls != 1 {
				t.Fatalf("expected createCalls=1, got %d", createCalls)
			}
			if tt.expectExecCalled && executeCalls == 0 {
				t.Fatalf("expected executeCalls>0, got %d", executeCalls)
			}
			if !tt.expectExecCalled && executeCalls != 0 {
				t.Fatalf("expected executeCalls=0, got %d", executeCalls)
			}
		})
	}
}

type mockProbe struct {
	mutex        sync.Mutex
	metricsList  []metric.ID
	createErr    error
	executeErr   error
	cache        *metric.RecordCache
	mask         [metric.MetricMax]bool
	createCalls  int
	executeCalls int
}

func (m *mockProbe) name() string { return "mock" }

func (m *mockProbe) metrics() []metric.ID {
	return m.metricsList
}

func (m *mockProbe) create(configPath string, cache *metric.RecordCache, mask [metric.MetricMax]bool, periods config.Periods) error {
	m.mutex.Lock()
	m.createCalls++
	m.cache = cache
	m.mask = mask
	err := m.createErr
	m.mutex.Unlock()
	return err
}

func (m *mockProbe) execute(_ bool) error {
	m.mutex.Lock()
	m.executeCalls++
	err := m.executeErr
	m.mutex.Unlock()
	return err
}

func (m *mockProbe) metricCache() *metric.RecordCache {
	m.mutex.Lock()
	cache := m.cache
	m.mutex.Unlock()
	return cache
}

func (m *mockProbe) hasMetric(id metric.ID) bool {
	m.mutex.Lock()
	ok := m.mask[id]
	m.mutex.Unlock()
	return ok
}

func (m *mockProbe) snapshot() (createCalls, executeCalls int) {
	m.mutex.Lock()
	defer m.mutex.Unlock()
	return m.createCalls, m.executeCalls
}
