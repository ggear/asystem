
package internal

import (
	"math"
	"sync"
	"testing"
)

// TestNewTieredRollingWindow tests window creation with various parameters
func TestNewTieredRollingWindow(t *testing.T) {
	tests := []struct {
		name           string
		durationDays   int
		tickFreqSec    int
		expectError    bool
		checkCaps      bool
		expectedOldCap int
	}{
		{
			name:         "invalid zero duration",
			durationDays: 0,
			tickFreqSec:  1,
			expectError:  true,
		},
		{
			name:         "invalid negative duration",
			durationDays: -1,
			tickFreqSec:  1,
			expectError:  true,
		},
		{
			name:         "invalid zero tick frequency",
			durationDays: 1,
			tickFreqSec:  0,
			expectError:  true,
		},
		{
			name:         "invalid negative tick frequency",
			durationDays: 1,
			tickFreqSec:  -1,
			expectError:  true,
		},
		{
			name:           "valid minimum config",
			durationDays:   1,
			tickFreqSec:    1,
			expectError:    false,
			checkCaps:      true,
			expectedOldCap: 17, // Minimal old tier
		},
		{
			name:         "valid default config",
			durationDays: 1,
			tickFreqSec:  1,
			expectError:  false,
		},
		{
			name:           "valid large duration",
			durationDays:   7,
			tickFreqSec:    1,
			expectError:    false,
			checkCaps:      true,
			expectedOldCap: 161, // ~6 days in old tier
		},
		{
			name:         "valid slow tick frequency",
			durationDays: 1,
			tickFreqSec:  60,
			expectError:  false,
		},
	}

	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			window, err := NewTieredRollingWindow(tc.durationDays, tc.tickFreqSec)
			if (err != nil) != tc.expectError {
				t.Fatalf("NewTieredRollingWindow() error = %v, expectError %v", err, tc.expectError)
			}
			if !tc.expectError {
				if window == nil {
					t.Fatal("Expected non-nil window")
				}
				if tc.checkCaps && window.oldCap != tc.expectedOldCap {
					t.Errorf("oldCap = %d, expected %d", window.oldCap, tc.expectedOldCap)
				}
			}
		})
	}
}

// TestNewNarrowWindow tests narrow window creation
func TestNewNarrowWindow(t *testing.T) {
	tests := []struct {
		name         string
		durationSec  int
		tickFreqSec  int
		expectError  bool
		expectedSize int
	}{
		{
			name:        "invalid zero duration",
			durationSec: 0,
			tickFreqSec: 1,
			expectError: true,
		},
		{
			name:        "invalid negative duration",
			durationSec: -1,
			tickFreqSec: 1,
			expectError: true,
		},
		{
			name:        "invalid zero tick frequency",
			durationSec: 5,
			tickFreqSec: 0,
			expectError: true,
		},
		{
			name:         "valid minimum config",
			durationSec:  1,
			tickFreqSec:  1,
			expectError:  false,
			expectedSize: 1,
		},
		{
			name:         "valid default 5 seconds",
			durationSec:  5,
			tickFreqSec:  1,
			expectError:  false,
			expectedSize: 5,
		},
		{
			name:         "valid large duration",
			durationSec:  60,
			tickFreqSec:  1,
			expectError:  false,
			expectedSize: 60,
		},
	}

	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			window, err := NewNarrowWindow(tc.durationSec, tc.tickFreqSec)
			if (err != nil) != tc.expectError {
				t.Fatalf("NewNarrowWindow() error = %v, expectError %v", err, tc.expectError)
			}
			if !tc.expectError {
				if window == nil {
					t.Fatal("Expected non-nil window")
				}
				if window.size != tc.expectedSize {
					t.Errorf("size = %d, expected %d", window.size, tc.expectedSize)
				}
			}
		})
	}
}

// TestNewDualWindow tests dual window creation
func TestNewDualWindow(t *testing.T) {
	tests := []struct {
		name        string
		wideDays    int
		narrowSec   int
		tickFreqSec int
		expectError bool
	}{
		{
			name:        "invalid wide duration",
			wideDays:    0,
			narrowSec:   5,
			tickFreqSec: 1,
			expectError: true,
		},
		{
			name:        "invalid narrow duration",
			wideDays:    1,
			narrowSec:   0,
			tickFreqSec: 1,
			expectError: true,
		},
		{
			name:        "invalid tick frequency",
			wideDays:    1,
			narrowSec:   5,
			tickFreqSec: 0,
			expectError: true,
		},
		{
			name:        "valid default config",
			wideDays:    1,
			narrowSec:   5,
			tickFreqSec: 1,
			expectError: false,
		},
	}

	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			window, err := NewDualWindow(tc.wideDays, tc.narrowSec, tc.tickFreqSec)
			if (err != nil) != tc.expectError {
				t.Fatalf("NewDualWindow() error = %v, expectError %v", err, tc.expectError)
			}
			if !tc.expectError && window == nil {
				t.Fatal("Expected non-nil dual window")
			}
		})
	}
}

// TestTieredRollingWindow_PushOutOfRange tests value range validation
func TestTieredRollingWindow_PushOutOfRange(t *testing.T) {
	tests := []struct {
		name  string
		value int8
	}{
		{"below min", -1},
		{"below min extreme", -128},
		{"above max", 101},
		{"above max extreme", 127},
		{"below zero", -50},
		{"way above max", 120},
	}

	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			window, _ := NewTieredRollingWindow(1, 1)
			window.Push(tc.value)
			// Should be silently ignored, verify window is still empty
			if window.current.count != 0 {
				t.Errorf("Push(%d) should be ignored, but count = %d", tc.value, window.current.count)
			}
			// Verify stats are still default
			if window.GetMean() != 0 || window.GetMax() != 0 || window.GetMin() != 0 {
				t.Error("Out of range push should not affect stats")
			}
		})
	}
}

// TestTieredRollingWindow_SingleValue tests single value behavior
func TestTieredRollingWindow_SingleValue(t *testing.T) {
	tests := []struct {
		name  string
		value int8
	}{
		{"single value 0", 0},
		{"single value 50", 50},
		{"single value 100", 100},
		{"single value boundary 1", 1},
		{"single value boundary 99", 99},
	}

	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			window, _ := NewTieredRollingWindow(1, 1)
			window.Push(tc.value)

			// All stats should equal the single value
			if window.GetMean() != float64(tc.value) {
				t.Errorf("Mean = %f, expected %f", window.GetMean(), float64(tc.value))
			}
			if window.GetMax() != tc.value {
				t.Errorf("Max = %d, expected %d", window.GetMax(), tc.value)
			}
			if window.GetMin() != tc.value {
				t.Errorf("Min = %d, expected %d", window.GetMin(), tc.value)
			}
			if window.GetLast() != tc.value {
				t.Errorf("Last = %d, expected %d", window.GetLast(), tc.value)
			}
			if window.GetP95() != tc.value {
				t.Errorf("P95 = %d, expected %d", window.GetP95(), tc.value)
			}
		})
	}
}

// TestTieredRollingWindow_PushAndStats tests basic push and statistics
func TestTieredRollingWindow_PushAndStats(t *testing.T) {
	tests := []struct {
		name         string
		values       []int8
		expectedMean float64
		expectedMax  int8
		expectedMin  int8
		expectedLast int8
	}{
		{
			name:         "single value",
			values:       []int8{50},
			expectedMean: 50.0,
			expectedMax:  50,
			expectedMin:  50,
			expectedLast: 50,
		},
		{
			name:         "multiple same values",
			values:       []int8{75, 75, 75, 75},
			expectedMean: 75.0,
			expectedMax:  75,
			expectedMin:  75,
			expectedLast: 75,
		},
		{
			name:         "ascending values",
			values:       []int8{10, 20, 30, 40, 50},
			expectedMean: 30.0,
			expectedMax:  50,
			expectedMin:  10,
			expectedLast: 50,
		},
		{
			name:         "descending values",
			values:       []int8{90, 70, 50, 30, 10},
			expectedMean: 50.0,
			expectedMax:  90,
			expectedMin:  10,
			expectedLast: 10,
		},
		{
			name:         "boundary values",
			values:       []int8{0, 100, 0, 100},
			expectedMean: 50.0,
			expectedMax:  100,
			expectedMin:  0,
			expectedLast: 100,
		},
		{
			name:         "all zeros",
			values:       []int8{0, 0, 0, 0, 0},
			expectedMean: 0.0,
			expectedMax:  0,
			expectedMin:  0,
			expectedLast: 0,
		},
		{
			name:         "all max",
			values:       []int8{100, 100, 100, 100},
			expectedMean: 100.0,
			expectedMax:  100,
			expectedMin:  100,
			expectedLast: 100,
		},
	}

	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			window, _ := NewTieredRollingWindow(1, 1)
			for _, v := range tc.values {
				window.Push(v)
			}

			mean := window.GetMean()
			if math.Abs(mean-tc.expectedMean) > 0.01 {
				t.Errorf("GetMean() = %f, expected %f", mean, tc.expectedMean)
			}

			max := window.GetMax()
			if max != tc.expectedMax {
				t.Errorf("GetMax() = %d, expected %d", max, tc.expectedMax)
			}

			min := window.GetMin()
			if min != tc.expectedMin {
				t.Errorf("GetMin() = %d, expected %d", min, tc.expectedMin)
			}

			last := window.GetLast()
			if last != tc.expectedLast {
				t.Errorf("GetLast() = %d, expected %d", last, tc.expectedLast)
			}
		})
	}
}

// TestTieredRollingWindow_ExtremeFrequency tests high-frequency pushes
func TestTieredRollingWindow_ExtremeFrequency(t *testing.T) {
	tests := []struct {
		name              string
		value             int8
		pushesPerSecond   int
		seconds           int
		expectedMean      float64
		checkBucketIntact bool
	}{
		{
			name:              "1000 pushes per second same value",
			value:             85,
			pushesPerSecond:   1000,
			seconds:           1,
			expectedMean:      85.0,
			checkBucketIntact: true,
		},
		{
			name:              "10000 pushes per second",
			value:             50,
			pushesPerSecond:   10000,
			seconds:           1,
			expectedMean:      50.0,
			checkBucketIntact: true,
		},
		{
			name:              "32000 pushes (near bucket limit)",
			value:             75,
			pushesPerSecond:   32000,
			seconds:           1,
			expectedMean:      75.0,
			checkBucketIntact: true,
		},
		{
			name:              "50000 pushes (exceeds bucket limit)",
			value:             90,
			pushesPerSecond:   50000,
			seconds:           1,
			expectedMean:      90.0,
			checkBucketIntact: false, // Bucket will saturate
		},
	}

	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			window, _ := NewTieredRollingWindow(1, 1)

			totalPushes := tc.pushesPerSecond * tc.seconds
			for i := 0; i < totalPushes; i++ {
				window.Push(tc.value)
			}

			// Verify mean accuracy
			mean := window.GetMean()
			if math.Abs(mean-tc.expectedMean) > 0.01 {
				t.Errorf("Mean = %f, expected %f after %d pushes", mean, tc.expectedMean, totalPushes)
			}

			// Verify max/min correct
			if window.GetMax() != tc.value {
				t.Errorf("Max = %d, expected %d", window.GetMax(), tc.value)
			}
			if window.GetMin() != tc.value {
				t.Errorf("Min = %d, expected %d", window.GetMin(), tc.value)
			}

			// Verify no overflow wraparound
			if window.current.buckets[tc.value] < 0 {
				t.Error("Bucket wrapped to negative (overflow)")
			}
			if window.current.count < 0 {
				t.Error("Count wrapped to negative (overflow)")
			}
		})
	}
}

// TestTieredRollingWindow_Percentiles tests percentile calculations
func TestTieredRollingWindow_Percentiles(t *testing.T) {
	tests := []struct {
		name        string
		values      []int8
		expectedP95 int8
	}{
		{
			name:        "uniform distribution",
			values:      []int8{10, 20, 30, 40, 50, 60, 70, 80, 90, 100},
			expectedP95: 100, // 95th percentile of 10 values
		},
		{
			name:        "all same value",
			values:      makeRepeated(50, 100),
			expectedP95: 50,
		},
		{
			name:        "spike at end",
			values:      append(makeRepeated(10, 95), 100, 100, 100, 100, 100),
			expectedP95: 100,
		},
		{
			name:        "linear 0-100",
			values:      makeSequence(0, 100),
			expectedP95: 95,
		},
		{
			name:        "single value percentile",
			values:      []int8{42},
			expectedP95: 42,
		},
	}

	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			window, _ := NewTieredRollingWindow(1, 1)
			for _, v := range tc.values {
				window.Push(v)
			}

			p95 := window.GetP95()
			if p95 != tc.expectedP95 {
				t.Errorf("GetP95() = %d, expected %d", p95, tc.expectedP95)
			}
		})
	}
}

// TestTieredRollingWindow_OverflowProtection tests overflow saturation
func TestTieredRollingWindow_OverflowProtection(t *testing.T) {
	tests := []struct {
		name        string
		value       int8
		pushCount   int
		description string
	}{
		{
			name:        "bucket saturation at 32767",
			value:       85,
			pushCount:   35000, // Exceeds int16 max
			description: "should saturate bucket at 32767",
		},
		{
			name:        "high frequency identical values",
			value:       50,
			pushCount:   50000,
			description: "should handle 50K identical samples",
		},
		{
			name:        "extreme frequency 100K pushes",
			value:       95,
			pushCount:   100000,
			description: "should handle 100K samples with saturation",
		},
	}

	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			window, _ := NewTieredRollingWindow(1, 1)

			for i := 0; i < tc.pushCount; i++ {
				window.Push(tc.value)
			}

			// Verify mean is still correct (uses count, not just bucket)
			mean := window.GetMean()
			if math.Abs(mean-float64(tc.value)) > 0.01 {
				t.Errorf("Mean after overflow = %f, expected %f", mean, float64(tc.value))
			}

			// Verify max/min are correct
			if window.GetMax() != tc.value {
				t.Errorf("Max after overflow = %d, expected %d", window.GetMax(), tc.value)
			}
			if window.GetMin() != tc.value {
				t.Errorf("Min after overflow = %d, expected %d", window.GetMin(), tc.value)
			}

			// Verify bucket saturated (not wrapped)
			if window.current.buckets[tc.value] < 0 {
				t.Error("Bucket count wrapped to negative (overflow not handled)")
			}
			
			// Verify percentile still works after saturation
			p95 := window.GetP95()
			if p95 != tc.value {
				t.Errorf("P95 after saturation = %d, expected %d", p95, tc.value)
			}
		})
	}
}

// TestTieredRollingWindow_TickFrequencyVariations tests different tick frequencies
func TestTieredRollingWindow_TickFrequencyVariations(t *testing.T) {
	tests := []struct {
		name          string
		tickFreqSec   int
		pushesPerTick int
		ticks         int
		expectedMean  float64
		description   string
	}{
		{
			name:          "1 second ticks",
			tickFreqSec:   1,
			pushesPerTick: 10,
			ticks:         60,
			expectedMean:  50.0,
			description:   "standard 1-second interval",
		},
		{
			name:          "5 second ticks",
			tickFreqSec:   5,
			pushesPerTick: 50,
			ticks:         12, // 60 seconds worth
			expectedMean:  50.0,
			description:   "slower tick rate",
		},
		{
			name:          "60 second ticks",
			tickFreqSec:   60,
			pushesPerTick: 600,
			ticks:         1, // 60 seconds worth
			expectedMean:  50.0,
			description:   "minute-based ticks",
		},
	}

	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			window, _ := NewTieredRollingWindow(1, tc.tickFreqSec)

			for i := 0; i < tc.ticks; i++ {
				for j := 0; j < tc.pushesPerTick; j++ {
					window.Push(50)
				}
				window.Tick()
			}

			mean := window.GetMean()
			if math.Abs(mean-tc.expectedMean) > 0.01 {
				t.Errorf("%s: Mean = %f, expected %f", tc.description, mean, tc.expectedMean)
			}
		})
	}
}

// TestTieredRollingWindow_StartupPhase tests partial data during startup
func TestTieredRollingWindow_StartupPhase(t *testing.T) {
	tests := []struct {
		name         string
		ticks        int
		value        int8
		expectedMean float64
		description  string
	}{
		{
			name:         "startup 10 ticks",
			ticks:        10,
			value:        75,
			expectedMean: 75.0,
			description:  "partial recent tier",
		},
		{
			name:         "startup 30 ticks",
			ticks:        30,
			value:        50,
			expectedMean: 50.0,
			description:  "half-filled recent tier",
		},
		{
			name:         "startup 65 ticks",
			ticks:        65,
			value:        80,
			expectedMean: 80.0,
			description:  "first aggregation to middle tier",
		},
		{
			name:         "startup 1 tick",
			ticks:        1,
			value:        90,
			expectedMean: 90.0,
			description:  "single tick only",
		},
	}

	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			window, _ := NewTieredRollingWindow(1, 1)

			for i := 0; i < tc.ticks; i++ {
				window.Push(tc.value)
				window.Tick()
			}

			mean := window.GetMean()
			if math.Abs(mean-tc.expectedMean) > 0.01 {
				t.Errorf("%s: Mean = %f, expected %f", tc.description, mean, tc.expectedMean)
			}

			// Verify all stats work with partial data
			max := window.GetMax()
			min := window.GetMin()
			p95 := window.GetP95()

			if max != tc.value || min != tc.value || p95 != tc.value {
				t.Errorf("Stats incorrect during startup: max=%d min=%d p95=%d, expected all %d",
					max, min, p95, tc.value)
			}
		})
	}
}

// TestTieredRollingWindow_TickAndAggregation tests tick mechanics and aggregation
func TestTieredRollingWindow_TickAndAggregation(t *testing.T) {
	tests := []struct {
		name         string
		setupFunc    func(*TieredRollingWindow)
		expectedMean float64
		description  string
	}{
		{
			name: "single tick with values",
			setupFunc: func(w *TieredRollingWindow) {
				w.Push(50)
				w.Push(60)
				w.Push(70)
				w.Tick()
			},
			expectedMean: 60.0,
			description:  "values should move to recent tier",
		},
		{
			name: "multiple ticks",
			setupFunc: func(w *TieredRollingWindow) {
				for i := 0; i < 10; i++ {
					w.Push(int8(10 * (i + 1)))
					w.Tick()
				}
			},
			expectedMean: 55.0, // (10+20+...+100)/10
			description:  "should maintain accuracy across ticks",
		},
		{
			name: "aggregation after 60 ticks",
			setupFunc: func(w *TieredRollingWindow) {
				for i := 0; i < 70; i++ {
					w.Push(50)
					w.Tick()
				}
			},
			expectedMean: 50.0,
			description:  "should aggregate to middle tier",
		},
		{
			name: "aggregation after 3600 ticks",
			setupFunc: func(w *TieredRollingWindow) {
				for i := 0; i < 3650; i++ {
					w.Push(85)
					w.Tick()
				}
			},
			expectedMean: 85.0,
			description:  "should aggregate to old tier",
		},
		{
			name: "empty ticks",
			setupFunc: func(w *TieredRollingWindow) {
				for i := 0; i < 10; i++ {
					w.Tick() // No pushes
				}
			},
			expectedMean: 0.0,
			description:  "empty ticks should not affect mean",
		},
		{
			name: "mixed empty and filled ticks",
			setupFunc: func(w *TieredRollingWindow) {
				for i := 0; i < 20; i++ {
					if i%2 == 0 {
						w.Push(50)
					}
					w.Tick()
				}
			},
			expectedMean: 50.0,
			description:  "should handle sparse data",
		},
	}

	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			window, _ := NewTieredRollingWindow(1, 1)
			tc.setupFunc(window)

			mean := window.GetMean()
			if math.Abs(mean-tc.expectedMean) > 0.01 {
				t.Errorf("%s: GetMean() = %f, expected %f", tc.description, mean, tc.expectedMean)
			}
		})
	}
}

// TestNarrowWindow_Basic tests narrow window basic functionality
func TestNarrowWindow_Basic(t *testing.T) {
	tests := []struct {
		name         string
		pushAndTick  func(*NarrowWindow) // Custom setup function
		expectedMean float64
		expectedMax  int8
		expectedMin  int8
		expectedP80  int8
	}{
		{
			name: "fill window exactly",
			pushAndTick: func(w *NarrowWindow) {
				// Push 5 values into 5 slots, tick between each
				w.Push(10)
				w.Tick() // Move to slot 1
				w.Push(20)
				w.Tick() // Move to slot 2
				w.Push(30)
				w.Tick() // Move to slot 3
				w.Push(40)
				w.Tick() // Move to slot 4
				w.Push(50)
				// Don't tick after last - keep 50 in current slot
			},
			expectedMean: 30.0,
			expectedMax:  50,
			expectedMin:  10,
			expectedP80:  42,
		},
		{
			name: "overflow window",
			pushAndTick: func(w *NarrowWindow) {
				// Push 7 values, window size 5 → overwrites first 2
				w.Push(10)
				w.Tick()
				w.Push(20)
				w.Tick()
				w.Push(30)
				w.Tick()
				w.Push(40)
				w.Tick()
				w.Push(50)
				w.Tick() // Wrap to slot 0
				w.Push(60)
				w.Tick() // Wrap to slot 1
				w.Push(70)
				// Result: [60, 70, 30, 40, 50]
			},
			expectedMean: 50.0,
			expectedMax:  70,
			expectedMin:  30,
			expectedP80:  62,
		},
		{
			name: "single value repeated",
			pushAndTick: func(w *NarrowWindow) {
				// Push multiple times per slot, tick between slots
				for i := 0; i < 5; i++ {
					w.Push(85)
					w.Push(85)
					if i < 4 {
						w.Tick()
					}
				}
			},
			expectedMean: 85.0,
			expectedMax:  85,
			expectedMin:  85,
			expectedP80:  85,
		},
	}

	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			window, _ := NewNarrowWindow(5, 1)
			tc.pushAndTick(window)

			mean := window.GetMean()
			if math.Abs(mean-tc.expectedMean) > 0.01 {
				t.Errorf("GetMean() = %f, expected %f", mean, tc.expectedMean)
			}

			if window.GetMax() != tc.expectedMax {
				t.Errorf("GetMax() = %d, expected %d", window.GetMax(), tc.expectedMax)
			}

			if window.GetMin() != tc.expectedMin {
				t.Errorf("GetMin() = %d, expected %d", window.GetMin(), tc.expectedMin)
			}

			// P80 within reasonable range
			p80 := window.GetP80()
			if math.Abs(float64(p80-tc.expectedP80)) > 5 {
				t.Errorf("GetP80() = %d, expected ~%d", p80, tc.expectedP80)
			}
		})
	}
}

// TestDualWindow_Coordination tests dual window coordination
func TestDualWindow_Coordination(t *testing.T) {
	window, _ := NewDualWindow(1, 5, 1)

	// Push same values to both
	values := []int8{10, 20, 30, 40, 50, 60, 70, 80, 90, 100}
	for _, v := range values {
		window.push(v)
	}
	window.tick()

	// Verify both windows see the data
	wideMean := window.GetWideMean()
	narrowMean := window.GetNarrowMean()

	if wideMean != narrowMean {
		t.Errorf("Wide mean (%f) != Narrow mean (%f) after same pushes", wideMean, narrowMean)
	}

	if window.GetWideLast() != window.GetNarrowLast() {
		t.Error("Last values differ between wide and narrow windows")
	}
}

// TestEmptyWindow tests behavior with no data (empty percentiles)
func TestEmptyWindow(t *testing.T) {
	tests := []struct {
		name        string
		setupFunc   func(*TieredRollingWindow)
		description string
	}{
		{
			name: "never pushed",
			setupFunc: func(w *TieredRollingWindow) {
				// Do nothing
			},
			description: "completely empty window",
		},
		{
			name: "pushed then ticked away",
			setupFunc: func(w *TieredRollingWindow) {
				w.Push(50)
				for i := 0; i < 4000; i++ {
					w.Tick() // Tick past all data
				}
			},
			description: "data aged out",
		},
	}

	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			window, _ := NewTieredRollingWindow(1, 1)
			tc.setupFunc(window)

			if window.GetMean() != 0 {
				t.Errorf("%s: Empty window mean should be 0, got %f", tc.description, window.GetMean())
			}
			if window.GetMax() != 0 {
				t.Errorf("%s: Empty window max should be 0, got %d", tc.description, window.GetMax())
			}
			if window.GetMin() != 0 {
				t.Errorf("%s: Empty window min should be 0, got %d", tc.description, window.GetMin())
			}
			if window.GetP95() != 0 {
				t.Errorf("%s: Empty window P95 should be 0, got %d", tc.description, window.GetP95())
			}
		})
	}
}

// TestMultipleDualWindows_Concurrency tests multiple windows with concurrent operations
func TestMultipleDualWindows_Concurrency(t *testing.T) {
	const numWindows = 10
	const numGoroutinesPerWindow = 5
	const operationsPerGoroutine = 100

	windows := make([]*DualWindow, numWindows)
	for i := 0; i < numWindows; i++ {
		w, err := NewDualWindow(1, 5, 1)
		if err != nil {
			t.Fatalf("Failed to create window %d: %v", i, err)
		}
		windows[i] = w
	}

	var wg sync.WaitGroup

	// Launch goroutines for each window
	for windowIdx := 0; windowIdx < numWindows; windowIdx++ {
		for goroutineIdx := 0; goroutineIdx < numGoroutinesPerWindow; goroutineIdx++ {
			wg.Add(1)
			go func(w *DualWindow, wIdx, gIdx int) {
				defer wg.Done()
				value := int8((wIdx*numGoroutinesPerWindow + gIdx) % 101)
				for i := 0; i < operationsPerGoroutine; i++ {
					w.push(value)
					if i%10 == 0 {
						w.tick()
					}
					// Read operations
					_ = w.GetWideMean()
					_ = w.GetWideP95()
					_ = w.GetNarrowP80()
				}
			}(windows[windowIdx], windowIdx, goroutineIdx)
		}
	}

	wg.Wait()

	// Verify all windows have reasonable values and didn't panic
	for i, w := range windows {
		mean := w.GetWideMean()
		if mean < 0 || mean > 100 {
			t.Errorf("Window %d: mean %f out of range after concurrent operations", i, mean)
		}
		max := w.GetWideMax()
		if max < 0 || max > 100 {
			t.Errorf("Window %d: max %d out of range after concurrent operations", i, max)
		}
	}
}

// TestConcurrency tests thread-safety on single window
func TestConcurrency(t *testing.T) {
	window, _ := NewTieredRollingWindow(1, 1)

	done := make(chan bool)

	// Multiple goroutines pushing
	for i := 0; i < 10; i++ {
		go func(val int8) {
			for j := 0; j < 100; j++ {
				window.Push(val)
			}
			done <- true
		}(int8(i * 10))
	}

	// Concurrent reader
	go func() {
		for i := 0; i < 100; i++ {
			_ = window.GetMean()
			_ = window.GetMax()
			_ = window.GetP95()
		}
		done <- true
	}()

	// Wait for all to complete
	for i := 0; i < 11; i++ {
		<-done
	}

	// Should not panic and should have reasonable values
	mean := window.GetMean()
	if mean < 0 || mean > 100 {
		t.Errorf("Mean after concurrent pushes = %f, out of valid range", mean)
	}
}

// Helper functions

func makeRepeated(value int8, count int) []int8 {
	result := make([]int8, count)
	for i := range result {
		result[i] = value
	}
	return result
}

func makeSequence(start, end int8) []int8 {
	result := make([]int8, end-start+1)
	for i := range result {
		result[i] = start + int8(i)
	}
	return result
}