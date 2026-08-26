package stats

import (
	"fmt"
	"math"
	"sync"
)

// BoolStats keeps a fixed pulse window and decayed true and false weights.
//
// MEMORY:
//   - the pulse window of max(round(pulseSecs/tickFreqSecs), 2) int8s, with running true and false counts
//   - the trend is two float64 weights, sharing FloatStats' decay
//
// CPU:
//   - push, tick and every read O(1)
//
// ACCURACY:
//   - the trend reports the greater weight, and whether either is non-zero, so one flip inside it shows as changed
//   - decay is applied per sample; trendHours 0 disables the trend
type BoolStats struct {
	mutex            sync.RWMutex
	pulseIndex       int
	pulseFilled      int
	pulseTrueCount   int
	pulseFalseCount  int
	pulseWindow      []int8
	lastValue        int8
	trendTrueWeight  float64
	trendFalseWeight float64
	trendDecay       float64
	trendOff         bool
}

func NewBoolStats(trendHours int, pulseSecs float64, tickFreqSecs float64) *BoolStats {
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
	pulse := make([]int8, pulseSize)
	for i := range pulse {
		pulse[i] = boolEmpty
	}
	return &BoolStats{
		pulseWindow: pulse,
		lastValue:   boolEmpty,
		trendDecay:  decay,
		trendOff:    trendOff,
	}
}

func (v *BoolStats) Tick() {
	v.mutex.Lock()
	defer v.mutex.Unlock()
	v.pulseIndex = (v.pulseIndex + 1) % len(v.pulseWindow)
	previous := v.pulseWindow[v.pulseIndex]
	if previous != boolEmpty {
		v.pulseFilled--
		if previous == boolTrue {
			v.pulseTrueCount--
		} else {
			v.pulseFalseCount--
		}
	}
	v.pulseWindow[v.pulseIndex] = boolEmpty
}

func (v *BoolStats) Push(value bool) {
	v.mutex.Lock()
	defer v.mutex.Unlock()
	stored := boolFalse
	if value {
		stored = boolTrue
	}
	previous := v.pulseWindow[v.pulseIndex]
	if previous == boolEmpty {
		v.pulseFilled++
	} else if previous == boolTrue {
		v.pulseTrueCount--
	} else {
		v.pulseFalseCount--
	}
	v.pulseWindow[v.pulseIndex] = stored
	if stored == boolTrue {
		v.pulseTrueCount++
	} else {
		v.pulseFalseCount++
	}
	v.lastValue = stored
	if v.trendOff {
		return
	}
	v.trendTrueWeight *= v.trendDecay
	v.trendFalseWeight *= v.trendDecay
	if stored == boolTrue {
		v.trendTrueWeight += 1.0
	} else {
		v.trendFalseWeight += 1.0
	}
}

func (v *BoolStats) PushAndTick(value bool) {
	v.Push(value)
	v.Tick()
}

func (v *BoolStats) PulseLast() bool {
	v.mutex.RLock()
	defer v.mutex.RUnlock()
	if v.lastValue == boolEmpty {
		return false
	}
	return v.lastValue == boolTrue
}

func (v *BoolStats) PulseMedian() bool {
	v.mutex.RLock()
	defer v.mutex.RUnlock()
	if v.pulseFilled == 0 {
		return false
	}
	return v.pulseTrueCount*2 >= v.pulseFilled
}

func (v *BoolStats) PulseHasTrue() bool {
	v.mutex.RLock()
	defer v.mutex.RUnlock()
	return v.pulseTrueCount > 0
}

func (v *BoolStats) PulseHasFalse() bool {
	v.mutex.RLock()
	defer v.mutex.RUnlock()
	return v.pulseFalseCount > 0
}

func (v *BoolStats) PulseHasChanged() bool {
	v.mutex.RLock()
	defer v.mutex.RUnlock()
	return v.pulseTrueCount > 0 && v.pulseFalseCount > 0
}

func (v *BoolStats) TrendMean() bool {
	v.mutex.RLock()
	defer v.mutex.RUnlock()
	if v.trendOff {
		return false
	}
	total := v.trendTrueWeight + v.trendFalseWeight
	if total == 0 {
		return false
	}
	return v.trendTrueWeight >= v.trendFalseWeight
}

func (v *BoolStats) TrendHasTrue() bool {
	v.mutex.RLock()
	defer v.mutex.RUnlock()
	return !v.trendOff && v.trendTrueWeight > 0
}

func (v *BoolStats) TrendHasFalse() bool {
	v.mutex.RLock()
	defer v.mutex.RUnlock()
	return !v.trendOff && v.trendFalseWeight > 0
}

func (v *BoolStats) TrendHasChanged() bool {
	v.mutex.RLock()
	defer v.mutex.RUnlock()
	return !v.trendOff && v.trendTrueWeight > 0 && v.trendFalseWeight > 0
}

const (
	boolEmpty int8 = -1
	boolFalse int8 = 0
	boolTrue  int8 = 1
)
