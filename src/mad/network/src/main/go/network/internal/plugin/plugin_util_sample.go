package plugin

import (
	"math"
	"slices"
)

func latestReading[T any](samples []Sample) T {
	var empty T
	for _, sample := range slices.Backward(samples) {
		if readings, ok := sample.Readings.(T); ok {
			return readings
		}
	}
	return empty
}

func allReadings[T any](samples []Sample) []T {
	all := make([]T, 0, len(samples))
	for _, sample := range samples {
		if readings, ok := sample.Readings.(T); ok {
			all = append(all, readings)
		}
	}
	return all
}

func round(v float64, places int) float64 {
	factor := math.Pow(10, float64(places))
	return math.Round(v*factor) / factor
}

type deltaTracker struct {
	previous map[string]int64
}

func newDeltaTracker() *deltaTracker {
	return &deltaTracker{previous: map[string]int64{}}
}

func (d *deltaTracker) Delta(key string, cumulative int64) (int64, bool) {
	previous, seen := d.previous[key]
	d.previous[key] = cumulative
	if !seen || cumulative < previous {
		return 0, false
	}
	return cumulative - previous, true
}
