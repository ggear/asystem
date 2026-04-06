package stats

import (
	"math"
	"testing"
)

func TestBoolStats_NewBoolStats(t *testing.T) {
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
			expectedSize:  2,
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
				NewBoolStats(testCase.trendHours, testCase.pulseSecs, testCase.tickFreqSecs)
				return
			}
			window := NewBoolStats(testCase.trendHours, testCase.pulseSecs, testCase.tickFreqSecs)
			if window == nil {
				t.Fatal("Got window = nil, expected non-nil")
			}
			if len(window.pulseWindow) != testCase.expectedSize {
				t.Fatalf("Got pulseWindow size = %d, expected %d", len(window.pulseWindow), testCase.expectedSize)
			}
		})
	}
}

func TestBoolStats_PulseWindowStats(t *testing.T) {
	tests := []struct {
		name               string
		windowSize         float64
		setupFunc          func(*BoolStats)
		expectedLast       bool
		expectedMedian     bool
		expectedHasTrue    bool
		expectedHasFalse   bool
		expectedHasChanged bool
	}{
		{
			name:               "happy_empty_before_push",
			windowSize:         3,
			setupFunc:          func(w *BoolStats) {},
			expectedLast:       false,
			expectedMedian:     false,
			expectedHasTrue:    false,
			expectedHasFalse:   false,
			expectedHasChanged: false,
		},
		{
			name:       "happy_all_true",
			windowSize: 3,
			setupFunc: func(w *BoolStats) {
				w.PushAndTick(true)
				w.PushAndTick(true)
				w.Push(true)
			},
			expectedLast:       true,
			expectedMedian:     true,
			expectedHasTrue:    true,
			expectedHasFalse:   false,
			expectedHasChanged: false,
		},
		{
			name:       "happy_all_false",
			windowSize: 3,
			setupFunc: func(w *BoolStats) {
				w.PushAndTick(false)
				w.PushAndTick(false)
				w.Push(false)
			},
			expectedLast:       false,
			expectedMedian:     false,
			expectedHasTrue:    false,
			expectedHasFalse:   true,
			expectedHasChanged: false,
		},
		{
			name:       "happy_mixed_true_false_true",
			windowSize: 3,
			setupFunc: func(w *BoolStats) {
				w.PushAndTick(true)
				w.PushAndTick(false)
				w.Push(true)
			},
			expectedLast:       true,
			expectedMedian:     true,
			expectedHasTrue:    true,
			expectedHasFalse:   true,
			expectedHasChanged: true,
		},
		{
			name:       "happy_single_slot_true",
			windowSize: 1,
			setupFunc: func(w *BoolStats) {
				w.Push(true)
			},
			expectedLast:       true,
			expectedMedian:     true,
			expectedHasTrue:    true,
			expectedHasFalse:   false,
			expectedHasChanged: false,
		},
		{
			name:       "happy_single_slot_false",
			windowSize: 1,
			setupFunc: func(w *BoolStats) {
				w.Push(false)
			},
			expectedLast:       false,
			expectedMedian:     false,
			expectedHasTrue:    false,
			expectedHasFalse:   true,
			expectedHasChanged: false,
		},
		{
			name:       "happy_overflow_evicts_old",
			windowSize: 3,
			setupFunc: func(w *BoolStats) {
				w.PushAndTick(true)
				w.PushAndTick(false)
				w.PushAndTick(false)
				w.Push(false)
			},
			expectedLast:       false,
			expectedMedian:     false,
			expectedHasTrue:    false,
			expectedHasFalse:   true,
			expectedHasChanged: false,
		},
		{
			name:       "happy_push_overwrites_slot",
			windowSize: 5,
			setupFunc: func(w *BoolStats) {
				w.Push(false)
				w.Push(true)
			},
			expectedLast:       true,
			expectedMedian:     true,
			expectedHasTrue:    true,
			expectedHasFalse:   false,
			expectedHasChanged: false,
		},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			window := NewBoolStats(1, testCase.windowSize, 1)
			testCase.setupFunc(window)
			if got := window.PulseLast(); got != testCase.expectedLast {
				t.Fatalf("Got PulseLast = %v, expected %v", got, testCase.expectedLast)
			}
			if got := window.PulseMedian(); got != testCase.expectedMedian {
				t.Fatalf("Got PulseMedian = %v, expected %v", got, testCase.expectedMedian)
			}
			if got := window.PulseHasTrue(); got != testCase.expectedHasTrue {
				t.Fatalf("Got PulseHasTrue = %v, expected %v", got, testCase.expectedHasTrue)
			}
			if got := window.PulseHasFalse(); got != testCase.expectedHasFalse {
				t.Fatalf("Got PulseHasFalse = %v, expected %v", got, testCase.expectedHasFalse)
			}
			if got := window.PulseHasChanged(); got != testCase.expectedHasChanged {
				t.Fatalf("Got PulseHasChanged = %v, expected %v", got, testCase.expectedHasChanged)
			}
		})
	}
}

func TestBoolStats_TrendDecay(t *testing.T) {
	tests := []struct {
		name      string
		setupFunc func(*BoolStats, float64)
	}{
		{
			name: "happy_empty_before_push",
			setupFunc: func(w *BoolStats, alpha float64) {
				if w.TrendMean() {
					t.Fatalf("Got TrendMean = true, expected false before any push")
				}
				if w.TrendHasTrue() {
					t.Fatalf("Got TrendHasTrue = true, expected false before any push")
				}
				if w.TrendHasFalse() {
					t.Fatalf("Got TrendHasFalse = true, expected false before any push")
				}
				if w.TrendHasChanged() {
					t.Fatalf("Got TrendHasChanged = true, expected false before any push")
				}
			},
		},
		{
			name: "happy_single_true",
			setupFunc: func(w *BoolStats, alpha float64) {
				w.Push(true)
				if !w.TrendMean() {
					t.Fatalf("Got TrendMean = false, expected true after single true push")
				}
				if !w.TrendHasTrue() {
					t.Fatalf("Got TrendHasTrue = false, expected true")
				}
				if w.TrendHasFalse() {
					t.Fatalf("Got TrendHasFalse = true, expected false")
				}
				if w.TrendHasChanged() {
					t.Fatalf("Got TrendHasChanged = true, expected false")
				}
			},
		},
		{
			name: "happy_single_false",
			setupFunc: func(w *BoolStats, alpha float64) {
				w.Push(false)
				if w.TrendMean() {
					t.Fatalf("Got TrendMean = true, expected false after single false push")
				}
				if w.TrendHasTrue() {
					t.Fatalf("Got TrendHasTrue = true, expected false")
				}
				if !w.TrendHasFalse() {
					t.Fatalf("Got TrendHasFalse = false, expected true")
				}
			},
		},
		{
			name: "happy_true_then_false_sequence",
			setupFunc: func(w *BoolStats, alpha float64) {
				w.Push(true)
				if !w.TrendMean() {
					t.Fatalf("Got TrendMean = false, expected true after first sample")
				}
				if !w.TrendHasTrue() {
					t.Fatalf("Got TrendHasTrue = false after first sample")
				}
				if w.TrendHasFalse() {
					t.Fatalf("Got TrendHasFalse = true after first sample")
				}
				w.Push(false)
				expectedTrue := 1.0 * alpha
				expectedFalse := 1.0
				if expectedTrue >= expectedFalse {
					t.Fatalf("expected TrendMean = false after second sample")
				}
				if !w.TrendHasTrue() || !w.TrendHasFalse() {
					t.Fatalf("Got TrendHasTrue/False = %v/%v, expected both true after second sample",
						w.TrendHasTrue(), w.TrendHasFalse())
				}
				if !w.TrendHasChanged() {
					t.Fatalf("Got TrendHasChanged = false, expected true after true then false")
				}
				w.Push(true)
				expectedTrue = expectedTrue*alpha + 1.0
				expectedFalse = expectedFalse * alpha
				if (expectedTrue >= expectedFalse) != w.TrendMean() {
					t.Fatalf("Got TrendMean = %v, unexpected after third sample", w.TrendMean())
				}
			},
		},
		{
			name: "happy_aggressive_decay_false_overtakes",
			setupFunc: func(w *BoolStats, alpha float64) {
				for i := 0; i < 10; i++ {
					w.Push(true)
				}
				w.Push(false)
				if !w.TrendHasTrue() || !w.TrendHasFalse() {
					t.Fatalf("Got TrendHasTrue/False = %v/%v, expected both seen", w.TrendHasTrue(), w.TrendHasFalse())
				}
				if !w.TrendHasChanged() {
					t.Fatalf("Got TrendHasChanged = false, expected true")
				}
			},
		},
	}
	alpha := math.Exp(-float64(3600) / (1.0 * 3600.0))
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			window := NewBoolStats(1, 1, 3600)
			testCase.setupFunc(window, alpha)
		})
	}
}

func TestBoolStats_TrendOff(t *testing.T) {
	tests := []struct {
		name                    string
		setupFunc               func(*BoolStats)
		expectedPulseLast       bool
		expectedPulseMedian     bool
		expectedPulseHasTrue    bool
		expectedPulseHasFalse   bool
		expectedPulseHasChanged bool
	}{
		{
			name:      "happy_trend_off_returns_false_before_push",
			setupFunc: func(w *BoolStats) {},
		},
		{
			name: "happy_trend_off_returns_false_after_push",
			setupFunc: func(w *BoolStats) {
				w.Push(true)
				w.Tick()
				w.Push(false)
			},
			expectedPulseLast:       false,
			expectedPulseMedian:     true,
			expectedPulseHasTrue:    true,
			expectedPulseHasFalse:   true,
			expectedPulseHasChanged: true,
		},
		{
			name: "happy_pulse_works_with_trend_off",
			setupFunc: func(w *BoolStats) {
				w.PushAndTick(true)
				w.PushAndTick(true)
				w.PushAndTick(false)
				w.Push(true)
			},
			expectedPulseLast:       true,
			expectedPulseMedian:     true,
			expectedPulseHasTrue:    true,
			expectedPulseHasFalse:   true,
			expectedPulseHasChanged: true,
		},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			window := NewBoolStats(0, 5, 1)
			testCase.setupFunc(window)
			if window.TrendMean() {
				t.Fatalf("Got TrendMean = true, expected false")
			}
			if window.TrendHasTrue() {
				t.Fatalf("Got TrendHasTrue = true, expected false")
			}
			if window.TrendHasFalse() {
				t.Fatalf("Got TrendHasFalse = true, expected false")
			}
			if window.TrendHasChanged() {
				t.Fatalf("Got TrendHasChanged = true, expected false")
			}
			if got := window.PulseLast(); got != testCase.expectedPulseLast {
				t.Fatalf("Got PulseLast = %v, expected %v", got, testCase.expectedPulseLast)
			}
			if got := window.PulseMedian(); got != testCase.expectedPulseMedian {
				t.Fatalf("Got PulseMedian = %v, expected %v", got, testCase.expectedPulseMedian)
			}
			if got := window.PulseHasTrue(); got != testCase.expectedPulseHasTrue {
				t.Fatalf("Got PulseHasTrue = %v, expected %v", got, testCase.expectedPulseHasTrue)
			}
			if got := window.PulseHasFalse(); got != testCase.expectedPulseHasFalse {
				t.Fatalf("Got PulseHasFalse = %v, expected %v", got, testCase.expectedPulseHasFalse)
			}
			if got := window.PulseHasChanged(); got != testCase.expectedPulseHasChanged {
				t.Fatalf("Got PulseHasChanged = %v, expected %v", got, testCase.expectedPulseHasChanged)
			}
		})
	}
}
