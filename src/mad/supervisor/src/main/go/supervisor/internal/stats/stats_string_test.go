package stats

import (
	"math"
	"testing"
)

func TestStringStats_NewStringStats(t *testing.T) {
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
				NewStringStats(testCase.trendHours, testCase.pulseSecs, testCase.tickFreqSecs)
				return
			}
			window := NewStringStats(testCase.trendHours, testCase.pulseSecs, testCase.tickFreqSecs)
			if window == nil {
				t.Fatal("Got window = nil, expected non-nil")
			}
			if len(window.pulseWindow) != testCase.expectedSize {
				t.Fatalf("Got pulseWindow size = %d, expected %d", len(window.pulseWindow), testCase.expectedSize)
			}
		})
	}
}

func TestStringStats_PulseWindowStats(t *testing.T) {
	tests := []struct {
		name               string
		windowSize         float64
		setupFunc          func(*StringStats)
		expectedLast       string
		expectedDominant   string
		expectedMedian     string
		expectedMax        string
		expectedMin        string
		expectedHasChanged bool
	}{
		{
			name:               "happy_empty_before_push",
			windowSize:         3,
			setupFunc:          func(w *StringStats) {},
			expectedLast:       "",
			expectedDominant:   "",
			expectedMedian:     "",
			expectedMax:        "",
			expectedMin:        "",
			expectedHasChanged: false,
		},
		{
			name:       "happy_single_value",
			windowSize: 3,
			setupFunc: func(w *StringStats) {
				w.Push("alpha")
			},
			expectedLast:       "alpha",
			expectedDominant:   "alpha",
			expectedMedian:     "alpha",
			expectedMax:        "alpha",
			expectedMin:        "alpha",
			expectedHasChanged: false,
		},
		{
			name:       "happy_alpha_beta_alpha_sequence",
			windowSize: 3,
			setupFunc: func(w *StringStats) {
				w.Push("alpha")
				w.Tick()
				w.Push("beta")
				w.Tick()
				w.Push("alpha")
			},
			expectedLast:       "alpha",
			expectedDominant:   "alpha",
			expectedMedian:     "alpha",
			expectedMax:        "beta",
			expectedMin:        "alpha",
			expectedHasChanged: true,
		},
		{
			name:       "happy_overflow_evicts_old",
			windowSize: 3,
			setupFunc: func(w *StringStats) {
				w.Push("alpha")
				w.Tick()
				w.Push("beta")
				w.Tick()
				w.Push("gamma")
				w.Tick()
				w.Push("gamma")
			},
			expectedLast:       "gamma",
			expectedDominant:   "gamma",
			expectedMax:        "gamma",
			expectedMin:        "beta",
			expectedHasChanged: true,
		},
		{
			name:       "happy_push_overwrites_slot",
			windowSize: 5,
			setupFunc: func(w *StringStats) {
				w.Push("first")
				w.Push("second")
				w.Push("third")
			},
			expectedLast:       "third",
			expectedDominant:   "third",
			expectedMedian:     "third",
			expectedMax:        "third",
			expectedMin:        "third",
			expectedHasChanged: false,
		},
		{
			name:       "happy_empty_string_value",
			windowSize: 3,
			setupFunc: func(w *StringStats) {
				w.Push("")
				w.Tick()
				w.Push("alpha")
			},
			expectedLast:       "alpha",
			expectedHasChanged: true,
		},
		{
			name:       "happy_all_same_no_change",
			windowSize: 5,
			setupFunc: func(w *StringStats) {
				for i := 0; i < 5; i++ {
					w.PushAndTick("same")
				}
			},
			expectedLast:       "same",
			expectedDominant:   "same",
			expectedMedian:     "same",
			expectedMax:        "same",
			expectedMin:        "same",
			expectedHasChanged: false,
		},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			window := NewStringStats(1, testCase.windowSize, 1)
			testCase.setupFunc(window)
			if got := window.PulseLast(); got != testCase.expectedLast {
				t.Fatalf("Got PulseLast = %q, expected %q", got, testCase.expectedLast)
			}
			if testCase.expectedDominant != "" {
				if got := window.PulseDominant(); got != testCase.expectedDominant {
					t.Fatalf("Got PulseDominant = %q, expected %q", got, testCase.expectedDominant)
				}
			}
			if testCase.expectedMedian != "" {
				if got := window.PulseMedian(); got != testCase.expectedMedian {
					t.Fatalf("Got PulseMedian = %q, expected %q", got, testCase.expectedMedian)
				}
			}
			if testCase.expectedMax != "" {
				if got := window.PulseMax(); got != testCase.expectedMax {
					t.Fatalf("Got PulseMax = %q, expected %q", got, testCase.expectedMax)
				}
			}
			if testCase.expectedMin != "" {
				if got := window.PulseMin(); got != testCase.expectedMin {
					t.Fatalf("Got PulseMin = %q, expected %q", got, testCase.expectedMin)
				}
			}
			if got := window.PulseHasChanged(); got != testCase.expectedHasChanged {
				t.Fatalf("Got PulseHasChanged = %v, expected %v", got, testCase.expectedHasChanged)
			}
		})
	}
}

func TestStringStats_TrendDecay(t *testing.T) {
	tests := []struct {
		name      string
		setupFunc func(*StringStats, float64)
	}{
		{
			name: "happy_empty_before_push",
			setupFunc: func(w *StringStats, alpha float64) {
				if got := w.TrendDominant(); got != "" {
					t.Fatalf("Got TrendDominant = %q, expected empty before push", got)
				}
				if w.TrendHasChanged() {
					t.Fatalf("Got TrendHasChanged = true, expected false before push")
				}
			},
		},
		{
			name: "happy_single_value",
			setupFunc: func(w *StringStats, alpha float64) {
				w.Push("alpha")
				if got := w.TrendDominant(); got != "alpha" {
					t.Fatalf("Got TrendDominant = %q, expected %q", got, "alpha")
				}
				if w.TrendHasChanged() {
					t.Fatalf("Got TrendHasChanged = true, expected false after first sample")
				}
			},
		},
		{
			name: "happy_alpha_then_beta_changes",
			setupFunc: func(w *StringStats, alpha float64) {
				w.Push("alpha")
				if got := w.TrendDominant(); got != "alpha" {
					t.Fatalf("Got TrendDominant = %q, expected %q", got, "alpha")
				}
				if w.TrendHasChanged() {
					t.Fatalf("Got TrendHasChanged = true, expected false after first sample")
				}
				w.Push("beta")
				if alpha >= 1.0 {
					t.Fatalf("Got alpha = %v, expected < 1.0", alpha)
				}
				if !w.TrendHasChanged() {
					t.Fatalf("Got TrendHasChanged = false, expected true after second different sample")
				}
				w.Push("beta")
				if got := w.TrendDominant(); got != "beta" {
					t.Fatalf("Got TrendDominant = %q, expected %q after two betas", got, "beta")
				}
			},
		},
		{
			name: "happy_trend_max_min_equal_dominant",
			setupFunc: func(w *StringStats, alpha float64) {
				w.Push("alpha")
				w.Push("beta")
				dominant := w.TrendDominant()
				if got := w.TrendMax(); got != dominant {
					t.Fatalf("Got TrendMax = %q, expected dominant %q", got, dominant)
				}
				if got := w.TrendMin(); got != dominant {
					t.Fatalf("Got TrendMin = %q, expected dominant %q", got, dominant)
				}
			},
		},
		{
			name: "happy_aggressive_decay_beta_overtakes",
			setupFunc: func(w *StringStats, alpha float64) {
				for i := 0; i < 10; i++ {
					w.Push("alpha")
				}
				w.Push("beta")
				if !w.TrendHasChanged() {
					t.Fatalf("Got TrendHasChanged = false, expected true after alpha then beta")
				}
				dominant := w.TrendDominant()
				if dominant != "alpha" && dominant != "beta" {
					t.Fatalf("Got TrendDominant = %q, expected either alpha or beta", dominant)
				}
			},
		},
	}
	alpha := math.Exp(-float64(3600) / (1.0 * 3600.0))
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			window := NewStringStats(1, 1, 3600)
			testCase.setupFunc(window, alpha)
		})
	}
}

func TestStringStats_TrendOff(t *testing.T) {
	tests := []struct {
		name                    string
		setupFunc               func(*StringStats)
		expectedPulseLast       string
		expectedPulseDominant   string
		expectedPulseHasChanged bool
	}{
		{
			name:      "happy_trend_off_returns_empty_before_push",
			setupFunc: func(w *StringStats) {},
		},
		{
			name: "happy_trend_off_returns_empty_after_push",
			setupFunc: func(w *StringStats) {
				w.Push("alpha")
				w.Tick()
				w.Push("beta")
			},
			expectedPulseLast:       "beta",
			expectedPulseDominant:   "alpha",
			expectedPulseHasChanged: true,
		},
		{
			name: "happy_pulse_works_with_trend_off",
			setupFunc: func(w *StringStats) {
				w.Push("alpha")
				w.Tick()
				w.Push("alpha")
				w.Tick()
				w.Push("beta")
				w.Tick()
				w.Push("alpha")
			},
			expectedPulseLast:       "alpha",
			expectedPulseDominant:   "alpha",
			expectedPulseHasChanged: true,
		},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			window := NewStringStats(0, 5, 1)
			testCase.setupFunc(window)
			if got := window.TrendDominant(); got != "" {
				t.Fatalf("Got TrendDominant = %q, expected empty", got)
			}
			if got := window.TrendMax(); got != "" {
				t.Fatalf("Got TrendMax = %q, expected empty", got)
			}
			if got := window.TrendMin(); got != "" {
				t.Fatalf("Got TrendMin = %q, expected empty", got)
			}
			if window.TrendHasChanged() {
				t.Fatalf("Got TrendHasChanged = true, expected false")
			}
			if got := window.PulseLast(); got != testCase.expectedPulseLast {
				t.Fatalf("Got PulseLast = %q, expected %q", got, testCase.expectedPulseLast)
			}
			if testCase.expectedPulseDominant != "" {
				if got := window.PulseDominant(); got != testCase.expectedPulseDominant {
					t.Fatalf("Got PulseDominant = %q, expected %q", got, testCase.expectedPulseDominant)
				}
			}
			if got := window.PulseHasChanged(); got != testCase.expectedPulseHasChanged {
				t.Fatalf("Got PulseHasChanged = %v, expected %v", got, testCase.expectedPulseHasChanged)
			}
		})
	}
}
