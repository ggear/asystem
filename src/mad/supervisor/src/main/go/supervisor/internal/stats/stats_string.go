package stats

import (
	"fmt"
	"math"
	"sort"
)

// StringStats tracks pulse values over a fixed window and trend values using
// constant-memory exponential decay (time constant = trendHours). Trend stats
// report the dominant recent value (decayed mode).
type StringStats struct {
	pulseIndex      int
	pulseFilled   int
	pulsePresent  []bool
	pulseWindow   []string
	lastValue     string
	lastHasValue  bool
	trendValue    string
	trendHasValue bool
	trendWeight   float64
	trendOther    float64
	trendDecay    float64
	trendOff      bool
}

func NewStringStats(trendHours int, pulseSecs float64, tickFreqSecs float64) *StringStats {
	if trendHours < 0 {
		panic(fmt.Sprintf("trendHours must be >= 0, got [%d]", trendHours))
	}
	if pulseSecs <= 0 {
		panic(fmt.Sprintf("pulseSecs must be > 0, got [%g]", pulseSecs))
	}
	if tickFreqSecs <= 0 {
		panic(fmt.Sprintf("tickFreqSecs must be > 0, got [%g]", tickFreqSecs))
	}
	trendOff := trendHours == 0
	var decay float64
	if !trendOff {
		pulseSecsRounded := math.Round(pulseSecs)
		tickFreqSecsRounded := math.Round(tickFreqSecs)
		if pulseSecsRounded < 1 {
			panic(fmt.Sprintf("pulseSecs must be >= 1 when trend enabled, got [%g]", pulseSecs))
		}
		if tickFreqSecsRounded < 1 {
			panic(fmt.Sprintf("tickFreqSecs must be >= 1 when trend enabled, got [%g]", tickFreqSecs))
		}
		decay = math.Exp(-tickFreqSecsRounded / (float64(trendHours) * 3600.0))
		pulseSecs = pulseSecsRounded
		tickFreqSecs = tickFreqSecsRounded
	}
	pulseSize := int(math.Round(pulseSecs / tickFreqSecs))
	if pulseSize < 1 {
		pulseSize = 1
	}
	return &StringStats{
		pulseWindow:  make([]string, pulseSize),
		pulsePresent: make([]bool, pulseSize),
		trendDecay:   decay,
		trendOff:     trendOff,
	}
}

func (v *StringStats) Tick() {
	v.pulseIndex = (v.pulseIndex + 1) % len(v.pulseWindow)
	if v.pulsePresent[v.pulseIndex] {
		v.pulsePresent[v.pulseIndex] = false
		v.pulseFilled--
	}
}

func (v *StringStats) Push(value string) {
	if !v.pulsePresent[v.pulseIndex] {
		v.pulsePresent[v.pulseIndex] = true
		v.pulseFilled++
	}
	v.pulseWindow[v.pulseIndex] = value
	v.lastValue = value
	v.lastHasValue = true
	if v.trendOff {
		return
	}
	if v.trendHasValue {
		v.trendWeight *= v.trendDecay
		v.trendOther *= v.trendDecay
		if value == v.trendValue {
			v.trendWeight += 1.0
		} else {
			v.trendOther += 1.0
			if v.trendOther > v.trendWeight {
				v.trendValue, value = value, v.trendValue
				v.trendWeight, v.trendOther = v.trendOther, v.trendWeight
			}
		}
	} else {
		v.trendValue = value
		v.trendHasValue = true
		v.trendWeight = 1.0
	}
}

func (v *StringStats) PushAndTick(value string) {
	v.Push(value)
	v.Tick()
}

func (v *StringStats) PulseLast() string {
	if !v.lastHasValue {
		return ""
	}
	return v.lastValue
}

func (v *StringStats) PulseDominant() string {
	return pulseMode(v.pulseWindow, v.pulsePresent)
}

func (v *StringStats) PulseMedian() string {
	return pulseMedian(v.pulseWindow, v.pulsePresent)
}

func (v *StringStats) PulseMax() string {
	return pulseMax(v.pulseWindow, v.pulsePresent)
}

func (v *StringStats) PulseMin() string {
	return pulseMin(v.pulseWindow, v.pulsePresent)
}

func (v *StringStats) PulseHasChanged() bool {
	seen := ""
	seenSet := false
	for i, present := range v.pulsePresent {
		if !present {
			continue
		}
		if !seenSet {
			seen = v.pulseWindow[i]
			seenSet = true
			continue
		}
		if v.pulseWindow[i] != seen {
			return true
		}
	}
	return false
}

func (v *StringStats) TrendDominant() string {
	if v.trendOff || !v.trendHasValue {
		return ""
	}
	return v.trendValue
}

func (v *StringStats) TrendMax() string {
	return v.TrendDominant()
}

func (v *StringStats) TrendMin() string {
	return v.TrendDominant()
}

func (v *StringStats) TrendHasChanged() bool {
	return !v.trendOff && v.trendWeight > 0 && v.trendOther > 0
}

func pulseMode(values []string, present []bool) string {
	counts := make(map[string]int)
	var bestValue string
	bestCount := 0
	for i, ok := range present {
		if !ok {
			continue
		}
		value := values[i]
		counts[value]++
		if counts[value] > bestCount {
			bestCount = counts[value]
			bestValue = value
		}
	}
	return bestValue
}

func pulseMedian(values []string, present []bool) string {
	collected := make([]string, 0, len(values))
	for i, ok := range present {
		if ok {
			collected = append(collected, values[i])
		}
	}
	if len(collected) == 0 {
		return ""
	}
	sort.Strings(collected)
	return collected[len(collected)/2]
}

func pulseMax(values []string, present []bool) string {
	hasValue := false
	maxValue := ""
	for i, ok := range present {
		if !ok {
			continue
		}
		value := values[i]
		if !hasValue || value > maxValue {
			maxValue = value
			hasValue = true
		}
	}
	return maxValue
}

func pulseMin(values []string, present []bool) string {
	hasValue := false
	minValue := ""
	for i, ok := range present {
		if !ok {
			continue
		}
		value := values[i]
		if !hasValue || value < minValue {
			minValue = value
			hasValue = true
		}
	}
	return minValue
}
