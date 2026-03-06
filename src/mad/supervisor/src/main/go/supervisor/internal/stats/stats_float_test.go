package stats

import (
	"math"
	"testing"
)

func TestFloatStats_NewFloatStats(t *testing.T) {
	tests := []struct {
		name          string
		trendHours    int
		pulseSecs     float64
		tickFreqSecs  float64
		expectedSize  int
		expectedPanic bool
	}{
		{
			name:          "happy_minimum_config",
			trendHours:    1,
			pulseSecs:     1,
			tickFreqSecs:  1,
			expectedSize:  1,
			expectedPanic: false,
		},
		{
			name:          "happy_default_5_seconds",
			trendHours:    24,
			pulseSecs:     5,
			tickFreqSecs:  1,
			expectedSize:  5,
			expectedPanic: false,
		},
		{
			name:          "happy_slow_tick_frequency",
			trendHours:    24,
			pulseSecs:     60,
			tickFreqSecs:  10,
			expectedSize:  6,
			expectedPanic: false,
		},
		{
			name:          "happy_zero_trend_hours_trend_off",
			trendHours:    0,
			pulseSecs:     5,
			tickFreqSecs:  1,
			expectedSize:  5,
			expectedPanic: false,
		},
		{
			name:          "happy_sub_second_trend_off",
			trendHours:    0,
			pulseSecs:     0.5,
			tickFreqSecs:  0.1,
			expectedSize:  5,
			expectedPanic: false,
		},
		{
			name:          "sad_negative_trend_hours",
			trendHours:    -1,
			pulseSecs:     5,
			tickFreqSecs:  1,
			expectedPanic: true,
		},
		{
			name:          "sad_zero_pulse_secs",
			trendHours:    1,
			pulseSecs:     0,
			tickFreqSecs:  1,
			expectedPanic: true,
		},
		{
			name:          "sad_negative_pulse_secs",
			trendHours:    1,
			pulseSecs:     -1,
			tickFreqSecs:  1,
			expectedPanic: true,
		},
		{
			name:          "sad_zero_tick_frequency",
			trendHours:    1,
			pulseSecs:     5,
			tickFreqSecs:  0,
			expectedPanic: true,
		},
		{
			name:          "sad_negative_tick_frequency",
			trendHours:    1,
			pulseSecs:     5,
			tickFreqSecs:  -1,
			expectedPanic: true,
		},
		{
			name:          "sad_sub_second_tick_freq_with_trend",
			trendHours:    1,
			pulseSecs:     5,
			tickFreqSecs:  0.4,
			expectedPanic: true,
		},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			if testCase.expectedPanic {
				defer func() {
					if recover() == nil {
						t.Fatalf("expected panic but did not panic")
					}
				}()
				NewFloatStats(testCase.trendHours, testCase.pulseSecs, testCase.tickFreqSecs)
				return
			}
			window := NewFloatStats(testCase.trendHours, testCase.pulseSecs, testCase.tickFreqSecs)
			if window == nil {
				t.Fatal("Got window = nil, expected non-nil")
			}
			if len(window.pulseWindow) != testCase.expectedSize {
				t.Fatalf("Got pulseWindow size = %d, expected %d", len(window.pulseWindow), testCase.expectedSize)
			}
		})
	}
}

func TestFloatStats_PulseWindowStats(t *testing.T) {
	tests := []struct {
		name           string
		windowSize     float64
		setupFunc      func(*FloatStats)
		expectedLast   float64
		expectedMean   float64
		expectedMedian float64
		expectedMax    float64
		expectedMin    float64
	}{
		{
			name:       "happy_empty_before_push",
			windowSize: 3,
			setupFunc:  func(w *FloatStats) {},
		},
		{
			name:           "happy_single_value",
			windowSize:     5,
			setupFunc:      func(w *FloatStats) { w.Push(42.0) },
			expectedLast:   42.0,
			expectedMean:   42.0,
			expectedMedian: 42.0,
			expectedMax:    42.0,
			expectedMin:    42.0,
		},
		{
			name:       "happy_fill_window_exactly",
			windowSize: 3,
			setupFunc: func(w *FloatStats) {
				w.PushAndTick(1)
				w.PushAndTick(2)
				w.PushAndTick(3)
			},
			expectedLast:   3,
			expectedMean:   2.5,
			expectedMedian: 2.5,
			expectedMax:    3,
			expectedMin:    2,
		},
		{
			name:       "happy_overflow_window",
			windowSize: 5,
			setupFunc: func(w *FloatStats) {
				for i := 1; i <= 7; i++ {
					w.PushAndTick(float64(i))
				}
			},
			expectedLast:   7,
			expectedMean:   5.5,
			expectedMedian: 5.5,
			expectedMax:    7,
			expectedMin:    4,
		},
		{
			name:       "happy_same_values",
			windowSize: 5,
			setupFunc: func(w *FloatStats) {
				for i := 0; i < 5; i++ {
					w.PushAndTick(10.0)
				}
			},
			expectedLast:   10.0,
			expectedMean:   10.0,
			expectedMedian: 10.0,
			expectedMax:    10.0,
			expectedMin:    10.0,
		},
		{
			name:       "happy_push_only_no_tick",
			windowSize: 5,
			setupFunc: func(w *FloatStats) {
				w.Push(1.0)
				w.Push(2.0)
				w.Push(3.0)
			},
			expectedLast:   3.0,
			expectedMean:   3.0,
			expectedMedian: 3.0,
			expectedMax:    3.0,
			expectedMin:    3.0,
		},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			window := NewFloatStats(1, testCase.windowSize, 1)
			testCase.setupFunc(window)
			expectApprox(t, "PulseLast", window.PulseLast(), testCase.expectedLast, 1e-6)
			expectApprox(t, "PulseMean", window.PulseMean(), testCase.expectedMean, 1e-6)
			expectApprox(t, "PulseMedian", window.PulseMedian(), testCase.expectedMedian, 1e-6)
			expectApprox(t, "PulseMax", window.PulseMax(), testCase.expectedMax, 1e-6)
			expectApprox(t, "PulseMin", window.PulseMin(), testCase.expectedMin, 1e-6)
		})
	}
}

func TestFloatStats_TrendDecay(t *testing.T) {
	tests := []struct {
		name      string
		setupFunc func(*FloatStats, float64)
		alpha     float64
	}{
		{
			name:  "happy_three_push_sequence",
			alpha: math.Exp(-float64(3600) / (1.0 * 3600.0)),
			setupFunc: func(w *FloatStats, alpha float64) {
				w.Push(10)
				expectApprox(t, "TrendMean after first", w.TrendMean(), 10, 1e-6)
				expectApprox(t, "TrendMin after first", w.TrendMin(), 10, 1e-6)
				expectApprox(t, "TrendMax after first", w.TrendMax(), 10, 1e-6)
				w.Push(20)
				expectedMean := (alpha*10 + 20) / (alpha + 1.0)
				expectedMin := math.Min(20, 10*alpha+20*(1.0-alpha))
				expectedMax := math.Max(20, 10*alpha+20*(1.0-alpha))
				expectApprox(t, "TrendMean after second", w.TrendMean(), expectedMean, 1e-6)
				expectApprox(t, "TrendMin after second", w.TrendMin(), expectedMin, 1e-6)
				expectApprox(t, "TrendMax after second", w.TrendMax(), expectedMax, 1e-6)
				w.Push(5)
				decayedWeight := (alpha + 1.0) * alpha
				decayedSum := (alpha*10 + 20) * alpha
				expectedMean = (decayedSum + 5) / (decayedWeight + 1.0)
				decayedMin := expectedMin*alpha + 5*(1.0-alpha)
				decayedMax := expectedMax*alpha + 5*(1.0-alpha)
				expectedMin = math.Min(5, decayedMin)
				expectedMax = math.Max(5, decayedMax)
				expectApprox(t, "TrendMean after third", w.TrendMean(), expectedMean, 1e-6)
				expectApprox(t, "TrendMin after third", w.TrendMin(), expectedMin, 1e-6)
				expectApprox(t, "TrendMax after third", w.TrendMax(), expectedMax, 1e-6)
			},
		},
		{
			name:  "happy_empty_before_push",
			alpha: math.Exp(-float64(3600) / (1.0 * 3600.0)),
			setupFunc: func(w *FloatStats, alpha float64) {
				expectApprox(t, "TrendMean empty", w.TrendMean(), 0, 1e-6)
				expectApprox(t, "TrendMin empty", w.TrendMin(), 0, 1e-6)
				expectApprox(t, "TrendMax empty", w.TrendMax(), 0, 1e-6)
			},
		},
		{
			name:  "happy_single_push",
			alpha: math.Exp(-float64(3600) / (1.0 * 3600.0)),
			setupFunc: func(w *FloatStats, alpha float64) {
				w.Push(50.0)
				expectApprox(t, "TrendMean single", w.TrendMean(), 50.0, 1e-6)
				expectApprox(t, "TrendMin single", w.TrendMin(), 50.0, 1e-6)
				expectApprox(t, "TrendMax single", w.TrendMax(), 50.0, 1e-6)
			},
		},
		{
			name:  "happy_push_same_value_twice",
			alpha: math.Exp(-float64(3600) / (1.0 * 3600.0)),
			setupFunc: func(w *FloatStats, alpha float64) {
				w.Push(30.0)
				w.Push(30.0)
				if got := w.TrendMean(); math.Abs(got-30.0) > 0.1 {
					t.Fatalf("Got TrendMean = %v, expected ~30", got)
				}
				if w.TrendMin() > 30.0 || w.TrendMax() < 30.0 {
					t.Fatalf("Got TrendMin/Max = %v/%v, expected to bracket 30", w.TrendMin(), w.TrendMax())
				}
			},
		},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			window := NewFloatStats(1, 1, 3600)
			testCase.setupFunc(window, testCase.alpha)
		})
	}
}

func TestFloatStats_TrendOff(t *testing.T) {
	tests := []struct {
		name                string
		setupFunc           func(*FloatStats)
		expectedPulseLast   float64
		expectedPulseMean   float64
		expectedPulseMedian float64
		expectedPulseMax    float64
		expectedPulseMin    float64
	}{
		{
			name:      "happy_trend_off_returns_zero_before_push",
			setupFunc: func(w *FloatStats) {},
		},
		{
			name: "happy_trend_off_returns_zero_after_push",
			setupFunc: func(w *FloatStats) {
				w.Push(50.0)
				w.Tick()
				w.Push(100.0)
			},
			expectedPulseLast:   100.0,
			expectedPulseMean:   75.0,
			expectedPulseMedian: 75.0,
			expectedPulseMax:    100.0,
			expectedPulseMin:    50.0,
		},
		{
			name: "happy_pulse_works_with_trend_off",
			setupFunc: func(w *FloatStats) {
				w.PushAndTick(10.0)
				w.PushAndTick(20.0)
				w.PushAndTick(30.0)
				w.PushAndTick(40.0)
				w.Push(50.0)
			},
			expectedPulseLast:   50.0,
			expectedPulseMean:   30.0,
			expectedPulseMedian: 30.0,
			expectedPulseMax:    50.0,
			expectedPulseMin:    10.0,
		},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			window := NewFloatStats(0, 5, 1)
			testCase.setupFunc(window)
			expectApprox(t, "TrendMean", window.TrendMean(), 0, 1e-6)
			expectApprox(t, "TrendMax", window.TrendMax(), 0, 1e-6)
			expectApprox(t, "TrendMin", window.TrendMin(), 0, 1e-6)
			expectApprox(t, "PulseLast", window.PulseLast(), testCase.expectedPulseLast, 1e-6)
			expectApprox(t, "PulseMean", window.PulseMean(), testCase.expectedPulseMean, 1e-6)
			expectApprox(t, "PulseMedian", window.PulseMedian(), testCase.expectedPulseMedian, 1e-6)
			expectApprox(t, "PulseMax", window.PulseMax(), testCase.expectedPulseMax, 1e-6)
			expectApprox(t, "PulseMin", window.PulseMin(), testCase.expectedPulseMin, 1e-6)
		})
	}
}

func expectApprox(t *testing.T, name string, got float64, want float64, tolerance float64) {
	t.Helper()
	if math.IsNaN(got) || math.IsInf(got, 0) {
		t.Fatalf("%s: got invalid value %v", name, got)
	}
	if math.Abs(got-want) > tolerance {
		t.Fatalf("%s: got %v, expected %v (tol %v)", name, got, want, tolerance)
	}
}
