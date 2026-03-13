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

func TestProbe_RunProbes(t *testing.T) {
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
			if err := Create("", cache, config.Periods{PollMillis: 1000, PulseMillis: 1000}); err != nil {
				t.Fatalf("Create failed: %v", err)
			}
			done := make(chan error, 1)
			go func() {
				done <- Run(ctx, nil)
			}()
			time.Sleep(1100 * time.Millisecond)
			cancel()
			if err := <-done; !errors.Is(err, context.Canceled) {
				t.Fatalf("expected context cancellation, got %v", err)
			}
			createCalls, runCalls := mock.snapshot()
			if createCalls != 1 {
				t.Fatalf("expected createCalls=1, got %d", createCalls)
			}
			if tt.expectExecCalled && runCalls == 0 {
				t.Fatalf("expected runCalls>0, got %d", runCalls)
			}
			if !tt.expectExecCalled && runCalls != 0 {
				t.Fatalf("expected runCalls=0, got %d", runCalls)
			}
		})
	}
}

func TestProbe_RunOnPulse(t *testing.T) {
	tests := []struct {
		name            string
		periods         config.Periods
		onPulse         func(*int, *bool) func(bool)
		expectedMinCalls int
		expectedError   bool
	}{
		{
			name:             "happy_nil_on_pulse_not_called",
			periods:          config.Periods{PollMillis: 1000, PulseMillis: 1000},
			onPulse:          func(_ *int, _ *bool) func(bool) { return nil },
			expectedMinCalls: 0,
			expectedError:    false,
		},
		{
			name:    "happy_on_pulse_called_each_pulse",
			periods: config.Periods{PollMillis: 1000, PulseMillis: 1000},
			onPulse: func(count *int, _ *bool) func(bool) {
				return func(_ bool) { *count++ }
			},
			expectedMinCalls: 1,
			expectedError:    false,
		},
		{
			name:    "happy_heartbeat_fires_on_factor",
			periods: config.Periods{PollMillis: 1000, PulseMillis: 1000, HeartbeatSecs: 1},
			onPulse: func(_ *int, heartbeat *bool) func(bool) {
				return func(isHeartbeat bool) {
					if isHeartbeat {
						*heartbeat = true
					}
				}
			},
			expectedMinCalls: 0,
			expectedError:    false,
		},
		{
			name:    "happy_heartbeat_fires_on_first_pulse",
			periods: config.Periods{PollMillis: 1000, PulseMillis: 1000, HeartbeatSecs: 1000},
			onPulse: func(_ *int, heartbeat *bool) func(bool) {
				return func(isHeartbeat bool) {
					if isHeartbeat {
						*heartbeat = true
					}
				}
			},
			expectedMinCalls: 0,
			expectedError:    false,
		},
		{
			name:    "happy_heartbeat_zero_secs_fires_every_pulse",
			periods: config.Periods{PollMillis: 1000, PulseMillis: 1000, HeartbeatSecs: 0},
			onPulse: func(count *int, heartbeat *bool) func(bool) {
				return func(isHeartbeat bool) {
					if isHeartbeat {
						*count++
						*heartbeat = true
					}
				}
			},
			expectedMinCalls: 1,
			expectedError:    false,
		},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			mock := &mockProbe{metricsList: []metric.ID{metric.MetricHostUsedProcessor}}
			for index := range probesByMetricMask {
				probesByMetricMask[index] = nil
			}
			execProbes = nil
			registerProbes(func() probe { return mock })
			ctx, cancel := context.WithCancel(context.Background())
			defer cancel()
			cache := metric.NewRecordCache()
			cache.Store(metric.NewRecordGUID(metric.MetricHostUsedProcessor, "localhost"), &metric.Record{})
			if err := Create("", cache, tt.periods); err != nil {
				t.Fatalf("Create failed: %v", err)
			}
			callCount := 0
			heartbeatFired := false
			done := make(chan error, 1)
			go func() {
				done <- Run(ctx, tt.onPulse(&callCount, &heartbeatFired))
			}()
			time.Sleep(1100 * time.Millisecond)
			cancel()
			if err := <-done; !errors.Is(err, context.Canceled) {
				t.Fatalf("Got error = %v, expected context.Canceled", err)
			}
			if callCount < tt.expectedMinCalls {
				t.Fatalf("Got onPulse calls = %d, expected >= %d", callCount, tt.expectedMinCalls)
			}
			switch tt.name {
			case "happy_heartbeat_fires_on_factor":
				if !heartbeatFired {
					t.Fatalf("Got heartbeat not fired, expected heartbeat with HeartbeatSecs=1")
				}
			case "happy_heartbeat_fires_on_first_pulse":
				if !heartbeatFired {
					t.Fatalf("Got heartbeat not fired, expected heartbeat on first pulse with HeartbeatSecs=1000")
				}
			case "happy_heartbeat_zero_secs_fires_every_pulse":
				if !heartbeatFired {
					t.Fatalf("Got heartbeat not fired, expected heartbeat every pulse with HeartbeatSecs=0")
				}
			}
		})
	}
}

type mockProbe struct {
	mutex       sync.Mutex
	metricsList []metric.ID
	createErr   error
	runErr      error
	cache       *metric.RecordCache
	mask        [metric.MetricMax]bool
	createCalls int
	runCalls    int
}

func (m *mockProbe) name() string { return "mock" }

func (m *mockProbe) metrics() []metric.ID {
	return m.metricsList
}

func (m *mockProbe) create(_ string, cache *metric.RecordCache, mask [metric.MetricMax]bool, periods config.Periods) error {
	m.mutex.Lock()
	m.createCalls++
	m.cache = cache
	m.mask = mask
	err := m.createErr
	m.mutex.Unlock()
	return err
}

func (m *mockProbe) run(_ context.Context, _ bool) error {
	m.mutex.Lock()
	m.runCalls++
	err := m.runErr
	m.mutex.Unlock()
	return err
}

func (m *mockProbe) records() *metric.RecordCache {
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
	return m.createCalls, m.runCalls
}
