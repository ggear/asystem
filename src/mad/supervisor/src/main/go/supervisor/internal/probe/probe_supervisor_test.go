package probe

import (
	"errors"
	"math"
	"supervisor/internal/metric"
	"testing"
	"time"

	"github.com/shirou/gopsutil/v4/cpu"
	"github.com/shirou/gopsutil/v4/process"
)

func TestProbeSupervisor_UsedProcessor(t *testing.T) {
	tests := []struct {
		name          string
		times         []*cpu.TimesStat
		timesErr      error
		clock         []time.Time
		expectedError bool
	}{
		{
			name:          "happy",
			times:         []*cpu.TimesStat{{User: 1}, {User: 2}},
			clock:         []time.Time{time.Unix(0, 0), time.Unix(1, 0), time.Unix(2, 0)},
			expectedError: false,
		},
		{
			name:          "sad_times_error",
			timesErr:      errors.New("boom"),
			clock:         []time.Time{time.Unix(0, 0)},
			expectedError: true,
		},
		{
			name:          "sad_nonmonotonic_counters",
			times:         []*cpu.TimesStat{{User: 2}, {User: 1}},
			clock:         []time.Time{time.Unix(0, 0), time.Unix(1, 0)},
			expectedError: true,
		},
		{
			name:          "sad_nonmonotonic_clock",
			times:         []*cpu.TimesStat{{User: 1}, {User: 2}},
			clock:         []time.Time{time.Unix(1, 0), time.Unix(1, 0)},
			expectedError: true,
		},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			probe := newSupervisorProbe()
			timesIndex := 0
			probe.procTimes = func() (*cpu.TimesStat, error) {
				if testCase.timesErr != nil {
					return nil, testCase.timesErr
				}
				if len(testCase.times) == 0 {
					return nil, nil
				}
				if timesIndex >= len(testCase.times) {
					return testCase.times[len(testCase.times)-1], nil
				}
				value := testCase.times[timesIndex]
				timesIndex++
				return value, nil
			}
			clockIndex := 0
			probe.now = func() time.Time {
				if len(testCase.clock) == 0 {
					return time.Unix(0, 0)
				}
				if clockIndex >= len(testCase.clock) {
					return testCase.clock[len(testCase.clock)-1]
				}
				value := testCase.clock[clockIndex]
				clockIndex++
				return value
			}
			value, err := probe.usedProcessor()
			if errors.Is(err, errProbeWarmingUp) {
				value, err = probe.usedProcessor()
			}
			if testCase.expectedError {
				if err == nil {
					t.Fatalf("expected error but got nil")
				}
				return
			}
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if value < 0 || value > 100 {
				t.Fatalf("processor value out of range: %d", value)
			}
		})
	}
}

func TestProbeSupervisor_UsedMemory(t *testing.T) {
	tests := []struct {
		name          string
		processMemory *process.MemoryInfoStat
		processErr    error
		expectInRange bool
		expectedError bool
	}{
		{
			name:          "happy",
			processMemory: &process.MemoryInfoStat{RSS: 50},
			expectInRange: true,
			expectedError: false,
		},
		{
			name:          "sad_process_error",
			processErr:    errors.New("boom"),
			expectedError: true,
		},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			probe := newSupervisorProbe()
			probe.procMemory = func() (*process.MemoryInfoStat, error) {
				if testCase.processErr != nil {
					return nil, testCase.processErr
				}
				return testCase.processMemory, nil
			}
			value, err := probe.usedMemory()
			if testCase.expectedError {
				if err == nil {
					t.Fatalf("expected error but got nil")
				}
				return
			}
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if testCase.expectInRange && (value < 0 || value > 100) {
				t.Fatalf("memory value out of range: %d", value)
			}
		})
	}
}

func TestProbeSupervisor_RunningTime(t *testing.T) {
	tests := []struct {
		name          string
		startTime     time.Time
		startErr      error
		nowTime       time.Time
		expectedError bool
	}{
		{
			name:          "happy",
			startTime:     time.Unix(0, 0),
			nowTime:       time.Unix(10, 0),
			expectedError: false,
		},
		{
			name:          "sad_start_error",
			startErr:      errors.New("boom"),
			expectedError: true,
		},
		{
			name:          "sad_negative",
			startTime:     time.Unix(10, 0),
			nowTime:       time.Unix(5, 0),
			expectedError: true,
		},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			probe := newSupervisorProbe()
			probe.procCreateTime = func() (int64, error) {
				if testCase.startErr != nil {
					return 0, testCase.startErr
				}
				return testCase.startTime.UnixMilli(), nil
			}
			probe.now = func() time.Time { return testCase.nowTime }
			value, err := probe.runningTime()
			if testCase.expectedError {
				if err == nil {
					t.Fatalf("expected error but got nil")
				}
				return
			}
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if value < 0 {
				t.Fatalf("running time out of range: %f", value)
			}
		})
	}
}

func TestProbeSupervisor_MaxMemory(t *testing.T) {
	tests := []struct {
		name          string
		goMemLimit    string
		limitOverride *int64
		expectValue   float64
		expectFromEnv bool
		expectedError bool
	}{
		{
			name:          "happy",
			expectedError: false,
		},
		{
			name:          "happy_gomemlimit",
			goMemLimit:    "64MiB",
			expectValue:   64 * 1024 * 1024,
			expectFromEnv: true,
			expectedError: false,
		},
		{
			name: "happy_default_when_unlimited",
			limitOverride: func() *int64 {
				value := int64(math.MaxInt64)
				return &value
			}(),
			expectedError: false,
		},
		{
			name: "happy_default_when_zero",
			limitOverride: func() *int64 {
				value := int64(0)
				return &value
			}(),
			expectedError: false,
		},
		{
			name:          "sad_missing_set_memory_limit",
			expectedError: true,
		},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			probe := newSupervisorProbe()
			switch {
			case testCase.expectedError:
				probe.setMemoryLimit = nil
			case testCase.limitOverride != nil:
				override := *testCase.limitOverride
				probe.setMemoryLimit = func(limit int64) int64 {
					return override
				}
			default:
				probe.setMemoryLimit = func(limit int64) int64 {
					if testCase.goMemLimit != "" {
						return int64(testCase.expectValue)
					}
					return math.MaxInt64
				}
			}
			value, err := probe.maxMemory()
			if testCase.expectedError {
				if err == nil {
					t.Fatalf("expected error but got nil")
				}
				return
			}
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if testCase.expectFromEnv {
				if value != testCase.expectValue {
					t.Fatalf("expected goMemLimit value %f, got %f", testCase.expectValue, value)
				}
				return
			}
			if testCase.limitOverride != nil {
				if value != 256*1024*1024 {
					t.Fatalf("expected default max memory, got %f", value)
				}
				return
			}
			if value <= 0 {
				t.Fatalf("expected positive max memory, got %f", value)
			}
		})
	}
}

func TestProbeSupervisor_Supervisor(t *testing.T) {
	tests := []struct {
		name          string
		expectedValue bool
		expectedOK    bool
		expectedError bool
	}{
		{
			name:          "happy",
			expectedValue: true,
			expectedOK:    true,
			expectedError: false,
		},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			probe := newSupervisorProbe()
			value, err := probe.supervisor()
			if testCase.expectedError && err == nil {
				t.Fatalf("expected error but got nil")
			}
			if !testCase.expectedError && err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if testCase.expectedOK && value != testCase.expectedValue {
				t.Fatalf("expected %v, got %v", testCase.expectedValue, value)
			}
		})
	}
}

func TestProbeSupervisor_Version(t *testing.T) {
	tests := []struct {
		name          string
		expectedValue string
		expectedOK    bool
		expectedError bool
	}{
		{
			name:          "happy",
			expectedValue: "",
			expectedOK:    true,
			expectedError: false,
		},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			probe := newSupervisorProbe()
			value, err := probe.version()
			if testCase.expectedError && err == nil {
				t.Fatalf("expected error but got nil")
			}
			if !testCase.expectedError && err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if testCase.expectedOK && value != testCase.expectedValue {
				t.Fatalf("expected %q, got %q", testCase.expectedValue, value)
			}
		})
	}
}

func TestProbeSupervisor_MetricRate(t *testing.T) {
	tests := []struct {
		name          string
		hasCache      bool
		expectedValue float64
		expectedOK    bool
		expectedError bool
	}{
		{
			name:          "happy",
			hasCache:      true,
			expectedValue: 0,
			expectedOK:    true,
			expectedError: false,
		},
		{
			name:          "sad_nil_cache",
			hasCache:      false,
			expectedValue: 0,
			expectedOK:    false,
			expectedError: true,
		},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			probe := newSupervisorProbe()
			if testCase.hasCache {
				probe.cache = metric.NewRecordCache()
			}
			value, err := probe.metricRate()
			if testCase.expectedError && err == nil {
				t.Fatalf("expected error but got nil")
			}
			if !testCase.expectedError && err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if testCase.expectedOK && value != testCase.expectedValue {
				t.Fatalf("expected %f, got %f", testCase.expectedValue, value)
			}
		})
	}
}
