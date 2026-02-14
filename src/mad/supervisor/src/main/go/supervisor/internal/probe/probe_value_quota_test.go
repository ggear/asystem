package probe

import (
	"math"
	"math/rand"
	"sync"
	"testing"
)

func TestProbeQuota_NewTrendWindow(t *testing.T) {
	tests := []struct {
		name          string
		durationDays  int
		tickFreqSec   int
		expectedSize  int
		expectedError bool
	}{
		{
			name:          "happy_minimum_config",
			durationDays:  1,
			tickFreqSec:   1,
			expectedError: false,
			expectedSize:  17,
		},
		{
			name:          "happy_default_config",
			durationDays:  1,
			tickFreqSec:   1,
			expectedError: false,
		},
		{
			name:          "happy_large_duration",
			durationDays:  7,
			tickFreqSec:   1,
			expectedError: false,
			expectedSize:  161,
		},
		{
			name:          "happy_slow_tick_frequency",
			durationDays:  1,
			tickFreqSec:   60,
			expectedError: false,
		},
		{
			name:          "sad_zero_duration",
			durationDays:  0,
			tickFreqSec:   1,
			expectedError: true,
		},
		{
			name:          "sad_negative_duration",
			durationDays:  -1,
			tickFreqSec:   1,
			expectedError: true,
		},
		{
			name:          "sad_zero_tick_frequency",
			durationDays:  1,
			tickFreqSec:   0,
			expectedError: true,
		},
		{
			name:          "sad_negative_tick_frequency",
			durationDays:  1,
			tickFreqSec:   -1,
			expectedError: true,
		},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			window, errorValue := newTrendWindow(testCase.durationDays, testCase.tickFreqSec)
			if (errorValue != nil) != testCase.expectedError {
				t.Fatalf("Got err = %v, expected error? %t", errorValue, testCase.expectedError)
			}
			if !testCase.expectedError {
				if window == nil {
					t.Fatal("Got window = nil, expected non-nil")
				}
				if testCase.expectedSize != 0 && window.geriatricCapacity != testCase.expectedSize {
					t.Fatalf("Got geriatricCapacity = %d, expected %d", window.geriatricCapacity, testCase.expectedSize)
				}
			}
		})
	}
}

func TestProbeQuota_NewPulseWindow(t *testing.T) {
	tests := []struct {
		name          string
		durationSec   int
		tickFreqSec   int
		expectedSize  int
		expectedError bool
	}{
		{
			name:          "happy_minimum_config",
			durationSec:   1,
			tickFreqSec:   1,
			expectedError: false,
			expectedSize:  1,
		},
		{
			name:          "happy_default_5_seconds",
			durationSec:   5,
			tickFreqSec:   1,
			expectedError: false,
			expectedSize:  5,
		},
		{
			name:          "happy_large_duration",
			durationSec:   60,
			tickFreqSec:   1,
			expectedError: false,
			expectedSize:  60,
		},
		{
			name:          "sad_zero_duration",
			durationSec:   0,
			tickFreqSec:   1,
			expectedError: true,
		},
		{
			name:          "sad_negative_duration",
			durationSec:   -1,
			tickFreqSec:   1,
			expectedError: true,
		},
		{
			name:          "sad_zero_tick_frequency",
			durationSec:   5,
			tickFreqSec:   0,
			expectedError: true,
		},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			window, errorValue := newPulseWindow(testCase.durationSec, testCase.tickFreqSec)
			if (errorValue != nil) != testCase.expectedError {
				t.Fatalf("Got err = %v, expected error? %t", errorValue, testCase.expectedError)
			}
			if !testCase.expectedError {
				if window == nil {
					t.Fatal("Got window = nil, expected non-nil")
				}
				if window.size != testCase.expectedSize {
					t.Fatalf("Got size = %d, expected %d", window.size, testCase.expectedSize)
				}
			}
		})
	}
}

func TestProbeQuota_NewQuotaWindow(t *testing.T) {
	tests := []struct {
		name          string
		trendDays     int
		pulseSec      int
		tickFreqSec   int
		expectedError bool
	}{
		{
			name:          "happy_default_config",
			trendDays:     1,
			pulseSec:      5,
			tickFreqSec:   1,
			expectedError: false,
		},
		{
			name:          "sad_trend_duration",
			trendDays:     0,
			pulseSec:      5,
			tickFreqSec:   1,
			expectedError: true,
		},
		{
			name:          "sad_pulse_duration",
			trendDays:     1,
			pulseSec:      0,
			tickFreqSec:   1,
			expectedError: true,
		},
		{
			name:          "sad_tick_frequency",
			trendDays:     1,
			pulseSec:      5,
			tickFreqSec:   0,
			expectedError: true,
		},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			window, errorValue := newQuotaValue(testCase.trendDays, testCase.pulseSec, testCase.tickFreqSec)
			if (errorValue != nil) != testCase.expectedError {
				t.Fatalf("Got err = %v, expected error? %t", errorValue, testCase.expectedError)
			}
			if !testCase.expectedError && window == nil {
				t.Fatal("Got window = nil, expected non-nil")
			}
		})
	}
}

func TestProbeQuota_TrendWindow_PushOutOfRange(t *testing.T) {
	tests := []struct {
		name  string
		value int8
	}{
		{
			name:  "sad_below_minimum_value",
			value: -1,
		},
		{
			name:  "sad_below_minimum_value_extreme",
			value: -128,
		},
		{
			name:  "sad_above_maximum_value",
			value: 101,
		},
		{
			name:  "sad_above_maximum_value_extreme",
			value: 127,
		},
		{
			name:  "sad_below_zero",
			value: -50,
		},
		{
			name:  "sad_way_above_maximum_value",
			value: 120,
		},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			window, _ := newTrendWindow(1, 1)
			window.push(testCase.value)
			if window.current.count != 0 {
				t.Fatalf("Got count = %d, expected %d", window.current.count, 0)
			}
			if window.mean() != 0 || window.max() != 0 || window.min() != 0 {
				t.Fatal("Got stats updated, expected defaults")
			}
		})
	}
}

func TestProbeQuota_TrendWindow_SingleValue(t *testing.T) {
	tests := []struct {
		name  string
		value int8
	}{
		{
			name:  "happy_single_value_0",
			value: 0,
		},
		{
			name:  "happy_single_value_50",
			value: 50,
		},
		{
			name:  "happy_single_value_100",
			value: 100,
		},
		{
			name:  "happy_single_value_boundary_1",
			value: 1,
		},
		{
			name:  "happy_single_value_boundary_99",
			value: 99,
		},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			window, _ := newTrendWindow(1, 1)
			window.push(testCase.value)
			if window.mean() != testCase.value {
				t.Fatalf("Got mean = %d, expected %d", window.mean(), testCase.value)
			}
			if window.max() != testCase.value {
				t.Fatalf("Got max = %d, expected %d", window.max(), testCase.value)
			}
			if window.min() != testCase.value {
				t.Fatalf("Got min = %d, expected %d", window.min(), testCase.value)
			}
			if window.p95() != testCase.value {
				t.Fatalf("Got p95 = %d, expected %d", window.p95(), testCase.value)
			}
		})
	}
}

func TestProbeQuota_TrendWindow_PushAndStats(t *testing.T) {
	tests := []struct {
		name         string
		values       []int8
		expectedMean int8
		expectedMax  int8
		expectedMin  int8
		expectedLast int8
	}{
		{
			name:         "happy_single_value",
			values:       []int8{50},
			expectedMean: 50,
			expectedMax:  50,
			expectedMin:  50,
			expectedLast: 50,
		},
		{
			name:         "happy_multiple_same_values",
			values:       []int8{75, 75, 75, 75},
			expectedMean: 75,
			expectedMax:  75,
			expectedMin:  75,
			expectedLast: 75,
		},
		{
			name:         "happy_ascending_values",
			values:       []int8{10, 20, 30, 40, 50},
			expectedMean: 30,
			expectedMax:  50,
			expectedMin:  10,
			expectedLast: 50,
		},
		{
			name:         "happy_descending_values",
			values:       []int8{90, 70, 50, 30, 10},
			expectedMean: 50,
			expectedMax:  90,
			expectedMin:  10,
			expectedLast: 10,
		},
		{
			name:         "happy_boundary_values",
			values:       []int8{0, 100, 0, 100},
			expectedMean: 50,
			expectedMax:  100,
			expectedMin:  0,
			expectedLast: 100,
		},
		{
			name:         "happy_all_zeros",
			values:       []int8{0, 0, 0, 0, 0},
			expectedMean: 0,
			expectedMax:  0,
			expectedMin:  0,
			expectedLast: 0,
		},
		{
			name:         "happy_all_maximum_value",
			values:       []int8{100, 100, 100, 100},
			expectedMean: 100,
			expectedMax:  100,
			expectedMin:  100,
			expectedLast: 100,
		},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			window, _ := newTrendWindow(1, 1)
			for _, value := range testCase.values {
				window.push(value)
			}
			mean := window.mean()
			if mean != testCase.expectedMean {
				t.Fatalf("Got mean = %d, expected %d", mean, testCase.expectedMean)
			}
			maximumValue := window.max()
			if maximumValue != testCase.expectedMax {
				t.Fatalf("Got max = %d, expected %d", maximumValue, testCase.expectedMax)
			}
			minimumValue := window.min()
			if minimumValue != testCase.expectedMin {
				t.Fatalf("Got min = %d, expected %d", minimumValue, testCase.expectedMin)
			}
		})
	}
}

func TestProbeQuota_TrendWindow_ExtremeFrequency(t *testing.T) {
	tests := []struct {
		name            string
		value           int8
		pushesPerSecond int
		seconds         int
		expectedMean    int8
	}{
		{
			name:            "happy_1000_pushes_per_second_same_value",
			value:           85,
			pushesPerSecond: 1000,
			seconds:         1,
			expectedMean:    85,
		},
		{
			name:            "happy_10000_pushes_per_second",
			value:           50,
			pushesPerSecond: 10000,
			seconds:         1,
			expectedMean:    50,
		},
		{
			name:            "happy_32000_pushes_near_bucket_limit",
			value:           75,
			pushesPerSecond: 32000,
			seconds:         1,
			expectedMean:    75,
		},
		{
			name:            "happy_50000_pushes_exceeds_bucket_limit",
			value:           90,
			pushesPerSecond: 50000,
			seconds:         1,
			expectedMean:    90,
		},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			window, _ := newTrendWindow(1, 1)
			totalPushes := testCase.pushesPerSecond * testCase.seconds
			for index := 0; index < totalPushes; index++ {
				window.push(testCase.value)
			}
			mean := window.mean()
			if mean != testCase.expectedMean {
				t.Fatalf("Got mean = %d, expected %d after %d pushes", mean, testCase.expectedMean, totalPushes)
			}
			if window.max() != testCase.value {
				t.Fatalf("Got max = %d, expected %d", window.max(), testCase.value)
			}
			if window.min() != testCase.value {
				t.Fatalf("Got min = %d, expected %d", window.min(), testCase.value)
			}
			if window.current.buckets[testCase.value] < 0 {
				t.Fatalf("Got bucket = %d, expected >= 0", window.current.buckets[testCase.value])
			}
			if window.current.count < 0 {
				t.Fatalf("Got count = %d, expected >= 0", window.current.count)
			}
		})
	}
}

func TestProbeQuota_TrendWindow_Percentiles(t *testing.T) {
	tests := []struct {
		name        string
		values      []int8
		expectedP95 int8
	}{
		{
			name:        "happy_uniform_distribution",
			values:      []int8{10, 20, 30, 40, 50, 60, 70, 80, 90, 100},
			expectedP95: 100,
		},
		{
			name:        "happy_all_same_value",
			values:      makeRepeated(50, 100),
			expectedP95: 50,
		},
		{
			name:        "happy_spike_at_end",
			values:      append(makeRepeated(10, 95), 100, 100, 100, 100, 100, 100),
			expectedP95: 100,
		},
		{
			name:        "happy_linear_0_100",
			values:      makeSequence(0, 100),
			expectedP95: 95,
		},
		{
			name:        "happy_single_value_percentile",
			values:      []int8{42},
			expectedP95: 42,
		},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			window, _ := newTrendWindow(1, 1)
			for _, value := range testCase.values {
				window.push(value)
			}
			p95 := window.p95()
			if p95 != testCase.expectedP95 {
				t.Fatalf("Got p95 = %d, expected %d", p95, testCase.expectedP95)
			}
		})
	}
}

func TestProbeQuota_TrendWindow_Median(t *testing.T) {
	tests := []struct {
		name           string
		values         []int8
		expectedMedian int8
	}{
		{
			name:           "happy_odd_count_uniform",
			values:         makeSequence(0, 100),
			expectedMedian: 50,
		},
		{
			name:           "happy_even_count_middle_low",
			values:         []int8{10, 20, 30, 40},
			expectedMedian: 20,
		},
		{
			name:           "happy_single_value",
			values:         []int8{42},
			expectedMedian: 42,
		},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			window, _ := newTrendWindow(1, 1)
			for _, value := range testCase.values {
				window.push(value)
			}
			median := window.median()
			if median != testCase.expectedMedian {
				t.Fatalf("Got median = %d, expected %d", median, testCase.expectedMedian)
			}
		})
	}
}

func TestProbeQuota_TrendWindow_OverlappingValues(t *testing.T) {
	tests := []struct {
		name string
		run  func(*trendWindow) []int8
	}{
		{
			name: "happy_overlapping_values_across_tiers",
			run: func(window *trendWindow) []int8 {
				values := make([]int8, 0, 200)
				for index := 0; index < ticksPerMinute; index++ {
					window.push(10)
					values = append(values, 10)
					window.tick()
				}
				for index := 0; index < ticksPerMinute/2; index++ {
					window.push(90)
					window.push(10)
					values = append(values, 90, 10)
					window.tick()
				}
				window.push(50)
				window.push(10)
				values = append(values, 50, 10)
				return values
			},
		},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			window, _ := newTrendWindow(1, 1)
			values := testCase.run(window)
			mean, minimumValue, maximumValue, p95 := expectedStats(values, 0.95)
			if window.mean() != mean {
				t.Fatalf("Got mean = %d, expected %d", window.mean(), mean)
			}
			if window.min() != minimumValue {
				t.Fatalf("Got min = %d, expected %d", window.min(), minimumValue)
			}
			if window.max() != maximumValue {
				t.Fatalf("Got max = %d, expected %d", window.max(), maximumValue)
			}
			if window.p95() != p95 {
				t.Fatalf("Got p95 = %d, expected %d", window.p95(), p95)
			}
		})
	}
}

func TestProbeQuota_TrendWindow_PartialAggregationAcrossTiers(t *testing.T) {
	tests := []struct {
		name string
		run  func(*trendWindow) []int8
	}{
		{
			name: "happy_partial_aggregation_across_tiers",
			run: func(window *trendWindow) []int8 {
				values := make([]int8, 0, ticksPerMinute*2+10)
				for index := 0; index < ticksPerMinute*2+10; index++ {
					window.push(20)
					values = append(values, 20)
					window.tick()
				}
				return values
			},
		},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			window, _ := newTrendWindow(1, 1)
			values := testCase.run(window)
			if window.middleCount == 0 {
				t.Fatalf("Got middleCount = %d, expected > 0", window.middleCount)
			}
			if window.youngCount == 0 {
				t.Fatalf("Got youngCount = %d, expected > 0", window.youngCount)
			}
			if window.geriatricCount != 0 {
				t.Fatalf("Got geriatricCount = %d, expected 0", window.geriatricCount)
			}
			mean, minimumValue, maximumValue, p95 := expectedStats(values, 0.95)
			if window.mean() != mean {
				t.Fatalf("Got mean = %d, expected %d", window.mean(), mean)
			}
			if window.min() != minimumValue || window.max() != maximumValue || window.p95() != p95 {
				t.Fatalf("Got min/max/p95 = %d/%d/%d, expected %d/%d/%d",
					window.min(), window.max(), window.p95(), minimumValue, maximumValue, p95)
			}
		})
	}
}

func TestProbeQuota_TrendWindow_SparseTraffic(t *testing.T) {
	tests := []struct {
		name         string
		idleTicks    int
		expectedMean int8
		expectedMin  int8
		expectedMax  int8
		expectedP95  int8
	}{
		{
			name:         "happy_idle_ticks_preserve_last_value",
			idleTicks:    5000,
			expectedMean: 42,
			expectedMin:  42,
			expectedMax:  42,
			expectedP95:  42,
		},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			window, _ := newTrendWindow(1, 1)
			window.push(42)
			window.tick()
			for index := 0; index < testCase.idleTicks; index++ {
				window.tick()
			}
			if window.mean() != testCase.expectedMean {
				t.Fatalf("Got mean = %d, expected %d", window.mean(), testCase.expectedMean)
			}
			if window.min() != testCase.expectedMin {
				t.Fatalf("Got min = %d, expected %d", window.min(), testCase.expectedMin)
			}
			if window.max() != testCase.expectedMax {
				t.Fatalf("Got max = %d, expected %d", window.max(), testCase.expectedMax)
			}
			if window.p95() != testCase.expectedP95 {
				t.Fatalf("Got p95 = %d, expected %d", window.p95(), testCase.expectedP95)
			}
		})
	}
}

func TestProbeQuota_TrendWindow_EvictionOrder(t *testing.T) {
	tests := []struct {
		name       string
		extraTicks int
	}{
		{
			name:       "happy_full_eviction_with_rollover",
			extraTicks: 5000,
		},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			window, _ := newTrendWindow(1, 1)
			totalTicks := window.youngCapacity + window.middleCapacity*ticksPerMinute + window.geriatricCapacity*ticksPerHour
			runTicks := totalTicks + testCase.extraTicks
			ring := make([]int8, totalTicks)
			head := 0
			count := 0
			var sum int64
			var counts [maxValidValue + 1]int
			for index := 0; index < runTicks; index++ {
				value := int8(index % (maxValidValue + 1))
				window.push(value)
				window.tick()
				if count < totalTicks {
					ring[count] = value
					count++
				} else {
					geriatric := ring[head]
					counts[int(geriatric)]--
					sum -= int64(geriatric)
					ring[head] = value
					head = (head + 1) % totalTicks
				}
				counts[int(value)]++
				sum += int64(value)
			}
			mean, minimumValue, maximumValue, p95 := expectedStatsFromCounts(counts, count, sum, 0.95)
			if window.mean() != mean {
				t.Fatalf("Got mean = %d, expected %d", window.mean(), mean)
			}
			if window.min() != minimumValue {
				t.Fatalf("Got min = %d, expected %d", window.min(), minimumValue)
			}
			if window.max() != maximumValue {
				t.Fatalf("Got max = %d, expected %d", window.max(), maximumValue)
			}
			if window.p95() != p95 {
				t.Fatalf("Got p95 = %d, expected %d", window.p95(), p95)
			}
		})
	}
}

func TestProbeQuota_TrendWindow_RandomPushTickSequences(t *testing.T) {
	tests := []struct {
		name      string
		seed      int64
		ticks     int
		maxPushes int
	}{
		{
			name:      "happy_random_pushes_with_invariants",
			seed:      1,
			ticks:     200,
			maxPushes: 5,
		},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			window, _ := newTrendWindow(1, 1)
			rng := rand.New(rand.NewSource(testCase.seed))
			values := make([]int8, 0, 1000)
			for index := 0; index < testCase.ticks; index++ {
				pushes := 1 + rng.Intn(testCase.maxPushes)
				for innerIndex := 0; innerIndex < pushes; innerIndex++ {
					value := int8(rng.Intn(maxValidValue + 1))
					window.push(value)
					values = append(values, value)
				}
				window.tick()
			}
			mean, minimumValue, maximumValue, p95 := expectedStats(values, 0.95)
			if window.mean() != mean {
				t.Fatalf("Got mean = %d, expected %d", window.mean(), mean)
			}
			if window.min() != minimumValue || window.max() != maximumValue {
				t.Fatalf("Got min/max = %d/%d, expected %d/%d", window.min(), window.max(), minimumValue, maximumValue)
			}
			if window.p95() != p95 {
				t.Fatalf("Got p95 = %d, expected %d", window.p95(), p95)
			}
			if window.mean() < window.min() || window.mean() > window.max() {
				t.Fatalf("Got mean = %d, expected between %d and %d", window.mean(), window.min(), window.max())
			}
			if window.p95() < window.min() || window.p95() > window.max() {
				t.Fatalf("Got p95 = %d, expected between %d and %d", window.p95(), window.min(), window.max())
			}
		})
	}
}

func TestProbeQuota_TrendWindow_OverflowProtection(t *testing.T) {
	tests := []struct {
		name        string
		description string
		value       int8
		pushCount   int
	}{
		{
			name:        "happy_bucket_saturation_at_32767",
			value:       85,
			pushCount:   35000,
			description: "should saturate bucket at 32767",
		},
		{
			name:        "happy_high_frequency_identical_values",
			value:       50,
			pushCount:   50000,
			description: "should handle 50K identical samples",
		},
		{
			name:        "happy_extreme_frequency_100k_pushes",
			value:       95,
			pushCount:   100000,
			description: "should handle 100K samples with saturation",
		},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			window, _ := newTrendWindow(1, 1)
			for index := 0; index < testCase.pushCount; index++ {
				window.push(testCase.value)
			}
			mean := window.mean()
			if mean != testCase.value {
				t.Fatalf("Got mean = %d, expected %d", mean, testCase.value)
			}
			if window.max() != testCase.value {
				t.Fatalf("Got max = %d, expected %d", window.max(), testCase.value)
			}
			if window.min() != testCase.value {
				t.Fatalf("Got min = %d, expected %d", window.min(), testCase.value)
			}
			if window.current.buckets[testCase.value] < 0 {
				t.Fatalf("Got bucket = %d, expected >= 0", window.current.buckets[testCase.value])
			}
			p95 := window.p95()
			if p95 != testCase.value {
				t.Fatalf("Got p95 = %d, expected %d", p95, testCase.value)
			}
		})
	}
}

func TestProbeQuota_TrendWindow_TickFrequencyVariations(t *testing.T) {
	tests := []struct {
		name          string
		description   string
		tickFreqSec   int
		pushesPerTick int
		ticks         int
		expectedMean  int8
	}{
		{
			name:          "happy_1_second_ticks",
			tickFreqSec:   1,
			pushesPerTick: 10,
			ticks:         60,
			expectedMean:  50,
			description:   "standard 1-second interval",
		},
		{
			name:          "happy_5_second_ticks",
			tickFreqSec:   5,
			pushesPerTick: 50,
			ticks:         12,
			expectedMean:  50,
			description:   "slower Tick rate",
		},
		{
			name:          "happy_60_second_ticks",
			tickFreqSec:   60,
			pushesPerTick: 600,
			ticks:         1,
			expectedMean:  50,
			description:   "minute-based ticks",
		},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			window, _ := newTrendWindow(1, testCase.tickFreqSec)
			for index := 0; index < testCase.ticks; index++ {
				for innerIndex := 0; innerIndex < testCase.pushesPerTick; innerIndex++ {
					window.push(50)
				}
				window.tick()
			}
			mean := window.mean()
			if mean != testCase.expectedMean {
				t.Fatalf("Got mean = %d, expected %d", mean, testCase.expectedMean)
			}
		})
	}
}

func TestProbeQuota_TrendWindow_StartupPhase(t *testing.T) {
	tests := []struct {
		name         string
		description  string
		ticks        int
		value        int8
		expectedMean int8
	}{
		{
			name:         "happy_startup_10_ticks",
			ticks:        10,
			value:        75,
			expectedMean: 75,
			description:  "partial young tier",
		},
		{
			name:         "happy_startup_30_ticks",
			ticks:        30,
			value:        50,
			expectedMean: 50,
			description:  "half-filled young tier",
		},
		{
			name:         "happy_startup_65_ticks",
			ticks:        65,
			value:        80,
			expectedMean: 80,
			description:  "first aggregation to middle tier",
		},
		{
			name:         "happy_startup_1_tick",
			ticks:        1,
			value:        90,
			expectedMean: 90,
			description:  "single Tick only",
		},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			window, _ := newTrendWindow(1, 1)
			for index := 0; index < testCase.ticks; index++ {
				window.push(testCase.value)
				window.tick()
			}
			mean := window.mean()
			if mean != testCase.expectedMean {
				t.Fatalf("Got mean = %d, expected %d", mean, testCase.expectedMean)
			}
			maximumValue := window.max()
			minimumValue := window.min()
			p95 := window.p95()
			if maximumValue != testCase.value || minimumValue != testCase.value || p95 != testCase.value {
				t.Fatalf("Got max/min/p95 = %d/%d/%d, expected %d",
					maximumValue, minimumValue, p95, testCase.value)
			}
		})
	}
}

func TestProbeQuota_TrendWindow_TickAndAggregation(t *testing.T) {
	tests := []struct {
		name         string
		description  string
		setupFunc    func(*trendWindow)
		expectedMean int8
	}{
		{
			name:        "happy_single_tick_with_values",
			description: "values should move to young tier",
			setupFunc: func(window *trendWindow) {
				window.push(50)
				window.push(60)
				window.push(70)
				window.tick()
			},
			expectedMean: 60,
		},
		{
			name:        "happy_multiple_ticks",
			description: "should maintain accuracy across ticks",
			setupFunc: func(window *trendWindow) {
				for index := 0; index < 10; index++ {
					window.push(int8(10 * (index + 1)))
					window.tick()
				}
			},
			expectedMean: 55,
		},
		{
			name:        "happy_aggregation_after_60_ticks",
			description: "should aggregate to middle tier",
			setupFunc: func(window *trendWindow) {
				for index := 0; index < 70; index++ {
					window.push(50)
					window.tick()
				}
			},
			expectedMean: 50,
		},
		{
			name:        "happy_aggregation_after_3600_ticks",
			description: "should aggregate to geriatric tier",
			setupFunc: func(window *trendWindow) {
				for index := 0; index < 3650; index++ {
					window.push(85)
					window.tick()
				}
			},
			expectedMean: 85,
		},
		{
			name:        "happy_empty_ticks",
			description: "empty ticks should not affect mean",
			setupFunc: func(window *trendWindow) {
				for index := 0; index < 10; index++ {
					window.tick()
				}
			},
			expectedMean: 0,
		},
		{
			name:        "happy_mixed_empty_and_filled_ticks",
			description: "should handle sparse data",
			setupFunc: func(window *trendWindow) {
				for index := 0; index < 20; index++ {
					if index%2 == 0 {
						window.push(50)
					}
					window.tick()
				}
			},
			expectedMean: 50,
		},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			window, _ := newTrendWindow(1, 1)
			testCase.setupFunc(window)
			mean := window.mean()
			if mean != testCase.expectedMean {
				t.Fatalf("Got mean = %d, expected %d", mean, testCase.expectedMean)
			}
		})
	}
}

func TestProbeQuota_PulseWindow_Basic(t *testing.T) {
	tests := []struct {
		name         string
		pushAndTick  func(*pulseWindow)
		expectedMean int8
		expectedMax  int8
		expectedMin  int8
	}{
		{
			name: "happy_fill_window_exactly",
			pushAndTick: func(window *pulseWindow) {
				window.push(10)
				window.tick()
				window.push(20)
				window.tick()
				window.push(30)
				window.tick()
				window.push(40)
				window.tick()
				window.push(50)
			},
			expectedMean: 30,
			expectedMax:  50,
			expectedMin:  10,
		},
		{
			name: "happy_overflow_window",
			pushAndTick: func(window *pulseWindow) {
				window.push(10)
				window.tick()
				window.push(20)
				window.tick()
				window.push(30)
				window.tick()
				window.push(40)
				window.tick()
				window.push(50)
				window.tick()
				window.push(60)
				window.tick()
				window.push(70)
			},
			expectedMean: 50,
			expectedMax:  70,
			expectedMin:  30,
		},
		{
			name: "happy_single_value_repeated",
			pushAndTick: func(window *pulseWindow) {
				for index := 0; index < 5; index++ {
					window.push(85)
					window.push(85)
					if index < 4 {
						window.tick()
					}
				}
			},
			expectedMean: 85,
			expectedMax:  85,
			expectedMin:  85,
		},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			window, _ := newPulseWindow(5, 1)
			testCase.pushAndTick(window)
			mean := window.mean()
			if mean != testCase.expectedMean {
				t.Fatalf("Got mean = %d, expected %d", mean, testCase.expectedMean)
			}
			if window.max() != testCase.expectedMax {
				t.Fatalf("Got max = %d, expected %d", window.max(), testCase.expectedMax)
			}
			if window.min() != testCase.expectedMin {
				t.Fatalf("Got min = %d, expected %d", window.min(), testCase.expectedMin)
			}
		})
	}
}

func TestProbeQuota_PulseWindow_Median(t *testing.T) {
	tests := []struct {
		name           string
		windowSize     int
		pushAndTick    func(*pulseWindow)
		expectedMedian int8
	}{
		{
			name:       "happy_odd_count",
			windowSize: 5,
			pushAndTick: func(window *pulseWindow) {
				window.push(10)
				window.tick()
				window.push(20)
				window.tick()
				window.push(30)
				window.tick()
				window.push(40)
				window.tick()
				window.push(50)
			},
			expectedMedian: 30,
		},
		{
			name:       "happy_even_count_low_middle",
			windowSize: 4,
			pushAndTick: func(window *pulseWindow) {
				window.push(10)
				window.tick()
				window.push(20)
				window.tick()
				window.push(30)
				window.tick()
				window.push(40)
			},
			expectedMedian: 20,
		},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			window, _ := newPulseWindow(testCase.windowSize, 1)
			testCase.pushAndTick(window)
			median := window.median()
			if median != testCase.expectedMedian {
				t.Fatalf("Got median = %d, expected %d", median, testCase.expectedMedian)
			}
		})
	}
}

func TestProbeQuota_Coordination(t *testing.T) {
	tests := []struct {
		name string
	}{
		{
			name: "happy_shared_values",
		},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			window, _ := newQuotaValue(1, 5, 1)
			values := []int8{10, 20, 30, 40, 50, 60, 70, 80, 90, 100}
			for _, value := range values {
				window.Push(value)
			}
			window.Tick()
			trendMean := window.TrendMean()
			pulseMean := window.PulseMean()
			if trendMean != pulseMean {
				t.Fatalf("Got trend mean = %d, expected %d", trendMean, pulseMean)
			}
		})
	}
}

func TestProbeQuota_EmptyWindow(t *testing.T) {
	tests := []struct {
		name         string
		description  string
		setupFunc    func(*trendWindow)
		expectedMean int8
		expectedMax  int8
		expectedMin  int8
		expectedP95  int8
	}{
		{
			name:        "happy_never_pushed",
			description: "completely empty window",
			setupFunc: func(window *trendWindow) {
			},
			expectedMean: 0,
			expectedMax:  0,
			expectedMin:  0,
			expectedP95:  0,
		},
		{
			name:        "happy_pushed_then_idle",
			description: "data retained without new samples",
			setupFunc: func(window *trendWindow) {
				window.push(50)
				for index := 0; index < 4000; index++ {
					window.tick()
				}
			},
			expectedMean: 50,
			expectedMax:  50,
			expectedMin:  50,
			expectedP95:  50,
		},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			window, _ := newTrendWindow(1, 1)
			testCase.setupFunc(window)
			if window.mean() != testCase.expectedMean {
				t.Fatalf("Got mean = %d, expected %d", window.mean(), testCase.expectedMean)
			}
			if window.max() != testCase.expectedMax {
				t.Fatalf("Got max = %d, expected %d", window.max(), testCase.expectedMax)
			}
			if window.min() != testCase.expectedMin {
				t.Fatalf("Got min = %d, expected %d", window.min(), testCase.expectedMin)
			}
			if window.p95() != testCase.expectedP95 {
				t.Fatalf("Got p95 = %d, expected %d", window.p95(), testCase.expectedP95)
			}
		})
	}
}

func TestProbeQuota_MultipleWindows_Concurrency(t *testing.T) {
	tests := []struct {
		name string
	}{
		{
			name: "happy_multi_window_concurrency",
		},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			const numberOfWindows = 10
			const numberOfGoroutinesPerWindow = 5
			const operationsPerGoroutine = 100
			windows := make([]*quotaValue, numberOfWindows)
			for index := 0; index < numberOfWindows; index++ {
				window, err := newQuotaValue(1, 5, 1)
				if err != nil {
					t.Fatalf("Got err = %v, expected nil", err)
				}
				windows[index] = window
			}
			var waitGroup sync.WaitGroup
			for windowIndex := 0; windowIndex < numberOfWindows; windowIndex++ {
				for goroutineIndex := 0; goroutineIndex < numberOfGoroutinesPerWindow; goroutineIndex++ {
					waitGroup.Add(1)
					go func(window *quotaValue, windowIndex, goroutineIndex int) {
						defer waitGroup.Done()
						value := int8((windowIndex*numberOfGoroutinesPerWindow + goroutineIndex) % 101)
						for index := 0; index < operationsPerGoroutine; index++ {
							window.Push(value)
							if index%10 == 0 {
								window.Tick()
							}
							_ = window.TrendMean()
							_ = window.TrendP95()
						}
					}(windows[windowIndex], windowIndex, goroutineIndex)
				}
			}
			waitGroup.Wait()
			for index, window := range windows {
				mean := window.TrendMean()
				if mean < 0 || mean > 100 {
					t.Fatalf("Got mean = %d for window %d, expected between 0 and 100", mean, index)
				}
				maximumValue := window.TrendMax()
				if maximumValue < 0 || maximumValue > 100 {
					t.Fatalf("Got max = %d for window %d, expected between 0 and 100", maximumValue, index)
				}
			}
		})
	}
}

func TestProbeQuota_Concurrency(t *testing.T) {
	tests := []struct {
		name string
	}{
		{
			name: "happy_single_window_concurrency",
		},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			window, _ := newTrendWindow(1, 1)
			done := make(chan bool)
			for index := 0; index < 10; index++ {
				go func(val int8) {
					for innerIndex := 0; innerIndex < 100; innerIndex++ {
						window.push(val)
					}
					done <- true
				}(int8(index * 10))
			}
			go func() {
				for index := 0; index < 100; index++ {
					_ = window.mean()
					_ = window.max()
					_ = window.p95()
				}
				done <- true
			}()
			for index := 0; index < 11; index++ {
				<-done
			}
			mean := window.mean()
			if mean < 0 || mean > 100 {
				t.Fatalf("Got mean = %d, expected between 0 and 100", mean)
			}
		})
	}
}

func makeRepeated(value int8, count int) []int8 {
	result := make([]int8, count)
	for index := range result {
		result[index] = value
	}
	return result
}

func makeSequence(start, end int8) []int8 {
	result := make([]int8, end-start+1)
	for index := range result {
		result[index] = start + int8(index)
	}
	return result
}

func expectedStats(values []int8, percentile float64) (int8, int8, int8, int8) {
	var counts [maxValidValue + 1]int
	var sum int64
	for _, value := range values {
		counts[int(value)]++
		sum += int64(value)
	}
	return expectedStatsFromCounts(counts, len(values), sum, percentile)
}

func expectedStatsFromCounts(counts [maxValidValue + 1]int, count int, sum int64, percentile float64) (int8, int8, int8, int8) {
	if count == 0 {
		return 0, 0, 0, 0
	}
	minimumValue := int8(uninitialisedMin)
	maximumValue := int8(uninitialisedMax)
	for index := 0; index <= maxValidValue; index++ {
		if counts[index] > 0 {
			if minimumValue == uninitialisedMin || int8(index) < minimumValue {
				minimumValue = int8(index)
			}
			if maximumValue == uninitialisedMax || int8(index) > maximumValue {
				maximumValue = int8(index)
			}
		}
	}
	target := int(math.Ceil(float64(count) * percentile))
	cumulative := 0
	pct := int8(0)
	for index := 0; index <= maxValidValue; index++ {
		cumulative += counts[index]
		if cumulative >= target {
			pct = int8(index)
			break
		}
	}
	mean := int8((sum + int64(count/2)) / int64(count))
	return mean, minimumValue, maximumValue, pct
}
