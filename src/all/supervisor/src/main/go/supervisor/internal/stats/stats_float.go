package stats

import (
	"fmt"
	"math"
	"sort"
	"sync"
)

// FloatStats keeps a fixed pulse window and a decayed trend.
//
// MEMORY:
//   - the pulse window of max(round(pulseSecs/tickFreqSecs), 2) float64s, and nothing else
//   - trendHours sizes the decay, exp(-tickFreqSecs/(trendHours*3600)), never the footprint
//
// CPU:
//   - push, tick and every trend read O(1); pulse mean O(window), median sorts a copy
//
// ACCURACY:
//   - the trend mean is an EWMA; min and max decay toward the recent value, so one old extreme cannot pin them
//   - decay is applied per sample, so it is a true time constant only at one sample per tick
//   - NaN and Inf are kept in the pulse window but excluded from the trend; trendHours 0 disables the trend
type FloatStats struct {
	mutex         sync.RWMutex
	pulseIndex    int
	pulseFilled   int
	pulseWindow   []float64
	lastValue     float64
	trendWeight   float64
	trendSum      float64
	trendMin      float64
	trendMax      float64
	trendDecay    float64
	trendHasValue bool
	trendOff      bool
}

func NewFloatStats(trendHours int, pulseSecs float64, tickFreqSecs float64) *FloatStats {
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
	pulseSize := max(int(math.Round(pulseSecs/tickFreqSecs)), 2)
	pulse := make([]float64, pulseSize)
	for i := range pulse {
		pulse[i] = math.NaN()
	}
	return &FloatStats{
		pulseWindow: pulse,
		lastValue:   math.NaN(),
		trendDecay:  decay,
		trendOff:    trendOff,
	}
}

func (v *FloatStats) Tick() {
	v.mutex.Lock()
	defer v.mutex.Unlock()
	v.pulseIndex = (v.pulseIndex + 1) % len(v.pulseWindow)
	if !math.IsNaN(v.pulseWindow[v.pulseIndex]) {
		v.pulseFilled--
	}
	v.pulseWindow[v.pulseIndex] = math.NaN()
}

func (v *FloatStats) Push(value float64) {
	v.mutex.Lock()
	defer v.mutex.Unlock()
	if math.IsNaN(v.pulseWindow[v.pulseIndex]) && !math.IsNaN(value) {
		v.pulseFilled++
	}
	v.pulseWindow[v.pulseIndex] = value
	v.lastValue = value
	if v.trendOff || math.IsNaN(value) || math.IsInf(value, 0) {
		return
	}
	if v.trendHasValue {
		v.trendWeight *= v.trendDecay
		v.trendSum *= v.trendDecay
		decayedMin := v.trendMin*v.trendDecay + value*(1.0-v.trendDecay)
		decayedMax := v.trendMax*v.trendDecay + value*(1.0-v.trendDecay)
		v.trendMin = math.Min(value, decayedMin)
		v.trendMax = math.Max(value, decayedMax)
	} else {
		v.trendMin = value
		v.trendMax = value
		v.trendHasValue = true
	}
	v.trendWeight += 1.0
	v.trendSum += value
}

func (v *FloatStats) PushAndTick(value float64) {
	v.Push(value)
	v.Tick()
}

func (v *FloatStats) PulseLast() float64 {
	v.mutex.RLock()
	defer v.mutex.RUnlock()
	if math.IsNaN(v.lastValue) {
		return 0
	}
	return v.lastValue
}

func (v *FloatStats) PulseMean() float64 {
	v.mutex.RLock()
	defer v.mutex.RUnlock()
	return meanOfValues(v.pulseWindow, v.pulseFilled)
}

func (v *FloatStats) PulseMedian() float64 {
	v.mutex.RLock()
	defer v.mutex.RUnlock()
	return medianOfValues(v.pulseWindow, v.pulseFilled)
}

func (v *FloatStats) PulseMax() float64 {
	v.mutex.RLock()
	defer v.mutex.RUnlock()
	return maxOfValues(v.pulseWindow, v.pulseFilled)
}

func (v *FloatStats) PulseMin() float64 {
	v.mutex.RLock()
	defer v.mutex.RUnlock()
	return minOfValues(v.pulseWindow, v.pulseFilled)
}

func (v *FloatStats) TrendMean() float64 {
	v.mutex.RLock()
	defer v.mutex.RUnlock()
	if v.trendOff || v.trendWeight == 0 {
		return 0
	}
	return v.trendSum / v.trendWeight
}

func (v *FloatStats) TrendMax() float64 {
	v.mutex.RLock()
	defer v.mutex.RUnlock()
	if v.trendOff || !v.trendHasValue {
		return 0
	}
	return v.trendMax
}

func (v *FloatStats) TrendMin() float64 {
	v.mutex.RLock()
	defer v.mutex.RUnlock()
	if v.trendOff || !v.trendHasValue {
		return 0
	}
	return v.trendMin
}

func meanOfValues(values []float64, filled int) float64 {
	if filled == 0 {
		return 0
	}
	sum := 0.0
	count := 0
	for _, value := range values {
		if math.IsNaN(value) || math.IsInf(value, 0) {
			continue
		}
		sum += value
		count++
	}
	if count == 0 {
		return 0
	}
	return sum / float64(count)
}

func medianOfValues(values []float64, filled int) float64 {
	if filled == 0 {
		return 0
	}
	collected := make([]float64, 0, filled)
	for _, value := range values {
		if math.IsNaN(value) || math.IsInf(value, 0) {
			continue
		}
		collected = append(collected, value)
	}
	if len(collected) == 0 {
		return 0
	}
	sort.Float64s(collected)
	mid := len(collected) / 2
	if len(collected)%2 == 0 {
		return (collected[mid-1] + collected[mid]) / 2
	}
	return collected[mid]
}

func maxOfValues(values []float64, filled int) float64 {
	if filled == 0 {
		return 0
	}
	var maxValue float64
	found := false
	for _, value := range values {
		if math.IsNaN(value) || math.IsInf(value, 0) {
			continue
		}
		if !found || value > maxValue {
			maxValue = value
			found = true
		}
	}
	if !found {
		return 0
	}
	return maxValue
}

func minOfValues(values []float64, filled int) float64 {
	if filled == 0 {
		return 0
	}
	var minValue float64
	found := false
	for _, value := range values {
		if math.IsNaN(value) || math.IsInf(value, 0) {
			continue
		}
		if !found || value < minValue {
			minValue = value
			found = true
		}
	}
	if !found {
		return 0
	}
	return minValue
}
