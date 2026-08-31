package probe

import (
	"context"
	"errors"
	"sync"
	"testing"
	"time"

	"supervisor/internal/config"
	"supervisor/internal/metric"
	"supervisor/internal/scribe"
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
			for index := range probesByMetricID {
				probesByMetricID[index] = nil
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
		name             string
		periods          config.Periods
		onPulse          func(*int, *bool) func(bool)
		expectedMinCalls int
		expectedError    bool
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
			for index := range probesByMetricID {
				probesByMetricID[index] = nil
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

func (m *mockProbe) subject() scribe.Subject { return scribe.SubjectHost("") }

func (m *mockProbe) metrics() []metric.ID {
	return m.metricsList
}

func (m *mockProbe) gates() []metric.GateID {
	return nil
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

func TestProbe_FailedSampleBlanks(t *testing.T) {
	tests := []struct {
		name           string
		sampleErr      error
		metricID       metric.ID
		serviceName    string
		expectedStored bool
		expectedFailed bool
		expectedPushes int
		expectedTicks  int
		expectedStatus metricStatus
		expectedError  bool
	}{
		{name: "healthy sample stores a reading", sampleErr: nil, metricID: metric.MetricHostUsedProcessor, serviceName: metric.ServiceNameUnset, expectedStored: true, expectedFailed: false, expectedPushes: 1, expectedTicks: 0, expectedStatus: metricStatusAmber, expectedError: false},
		{name: "failed sample stores a failure", sampleErr: errors.New("expected error during unit test"), metricID: metric.MetricHostUsedProcessor, serviceName: metric.ServiceNameUnset, expectedStored: true, expectedFailed: true, expectedPushes: 0, expectedTicks: 1, expectedStatus: metricStatusUnknown, expectedError: false},
		{name: "warming up declared host metric stores nothing", sampleErr: errProbeWarmingUp, metricID: metric.MetricHostUsedHomeSpace, serviceName: metric.ServiceNameUnset, expectedStored: false, expectedFailed: false, expectedPushes: 0, expectedTicks: 1, expectedStatus: metricStatusUnknown, expectedError: false},
		{name: "warming up undeclared host metric stores no failure", sampleErr: errProbeWarmingUp, metricID: metric.MetricHostUsedProcessor, serviceName: metric.ServiceNameUnset, expectedStored: true, expectedFailed: false, expectedPushes: 0, expectedTicks: 1, expectedStatus: metricStatusAmber, expectedError: false},
		{name: "warming up undeclared service metric stores no failure", sampleErr: errProbeWarmingUp, metricID: metric.MetricServiceUsedProcessor, serviceName: "svc-a", expectedStored: true, expectedFailed: false, expectedPushes: 0, expectedTicks: 1, expectedStatus: metricStatusAmber, expectedError: false},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			cache := metric.NewRecordCache()
			mock := &mockProbe{metricsList: []metric.ID{testCase.metricID}, cache: cache}
			mock.mask[testCase.metricID] = true
			execConfigPath = ""
			hostName := config.Load(execConfigPath).Host()
			pushes := 0
			ticks := 0
			task := cacheMetricTask{
				valueKind:   metric.ValueInt,
				metricID:    testCase.metricID,
				serviceName: testCase.serviceName,
				sampleFunc: func() (any, derivation, error) {
					return int8(42), derived(scribe.ActionSample, "computed [42] pct for the test"), testCase.sampleErr
				},
				statsFunc: func(any) { pushes++ },
				tickFunc:  func() { ticks++ },
				pulseFunc: func() any { return int8(42) },
			}
			gates := gateSet{metric.GateServiceAggregate: func() bool { return true }}
			status := runCacheMetricTask(mock, true, gates, task)
			if status != testCase.expectedStatus {
				t.Errorf("status: got %v want %v", status, testCase.expectedStatus)
			}
			if pushes != testCase.expectedPushes {
				t.Errorf("pushes: got %v want %v", pushes, testCase.expectedPushes)
			}
			if ticks != testCase.expectedTicks {
				t.Errorf("ticks: got %v want %v", ticks, testCase.expectedTicks)
			}
			record, found := cache.Load(metric.NewServiceRecordGUID(testCase.metricID, hostName, testCase.serviceName))
			if found != testCase.expectedStored {
				t.Fatalf("stored: got %v want %v", found, testCase.expectedStored)
			}
			if !found {
				return
			}
			if record.Value.Failed != testCase.expectedFailed {
				t.Errorf("failed: got %v want %v", record.Value.Failed, testCase.expectedFailed)
			}
			if record.Value.Pulse == nil {
				t.Fatalf("pulse: got nil want a pulse carrying the last computed value")
			}
			if record.Value.Pulse.ValueInt != 42 {
				t.Errorf("pulse value: got %v want 42", record.Value.Pulse.ValueInt)
			}
		})
	}
}

func TestProbe_MetricStatusOf(t *testing.T) {
	trended := func(value bool) *bool { return &value }
	testCases := []struct {
		name           string
		failed         bool
		pulseOK        bool
		trendOK        *bool
		expectedStatus metricStatus
		expectedError  bool
	}{
		{name: "pulse and trend ok", failed: false, pulseOK: true, trendOK: trended(true), expectedStatus: metricStatusGreen, expectedError: false},
		{name: "pulse ok trend not ok", failed: false, pulseOK: true, trendOK: trended(false), expectedStatus: metricStatusAmber, expectedError: false},
		{name: "pulse ok trend absent", failed: false, pulseOK: true, trendOK: nil, expectedStatus: metricStatusAmber, expectedError: false},
		{name: "pulse not ok", failed: false, pulseOK: false, trendOK: trended(true), expectedStatus: metricStatusRed, expectedError: false},
		{name: "failed with pulse and trend ok", failed: true, pulseOK: true, trendOK: trended(true), expectedStatus: metricStatusUnknown, expectedError: false},
		{name: "failed with pulse not ok", failed: true, pulseOK: false, trendOK: trended(false), expectedStatus: metricStatusUnknown, expectedError: false},
	}
	for _, testCase := range testCases {
		t.Run(testCase.name, func(t *testing.T) {
			if status := metricStatusOf(testCase.failed, testCase.pulseOK, testCase.trendOK); status != testCase.expectedStatus {
				t.Errorf("status: got %v want %v", status, testCase.expectedStatus)
			}
		})
	}
}
