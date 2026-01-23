package internal

import (
	"errors"
	"math"
	"math/rand"
	"sort"
	"time"

	"github.com/shirou/gopsutil/v4/cpu"
	"github.com/shirou/gopsutil/v4/mem"
)

type windowStat int

const (
	windowStatLst windowStat = 1 << iota
	windowStatMin
	windowStatMax
	windowStatAve
	windowStatP95
)

type lastValueCache struct {
	value    float64
	hasValue bool
}

func newLastValueCache() *lastValueCache {
	return &lastValueCache{}
}

func (cache *lastValueCache) push(value float64) {
	cache.value = value
	cache.hasValue = true
}

func (cache *lastValueCache) compute(stats windowStat) (lst float64, ave float64, min float64, max float64, p95 float64, err error) {
	if !cache.hasValue {
		err = errors.New("no data available in valueCache")
		return
	}
	if stats&windowStatLst == 0 {
		err = errors.New("only windowStatLst supported")
		return
	}
	lst = cache.value
	return
}

type windowedValueCache struct {
	size    int
	index   int
	count   int
	sum     float64
	max     float64
	min     float64
	buffer  []float64
	scratch []float64
}

func newWindowedValueCache(size int) *windowedValueCache {
	return &windowedValueCache{
		size:    size,
		min:     math.Inf(1),
		max:     math.Inf(-1),
		buffer:  make([]float64, size),
		scratch: make([]float64, size),
	}
}

func (cache *windowedValueCache) push(value float64) {
	var evicted float64
	var evictedWasMax, evictedWasMin bool
	if cache.count == cache.size {
		evicted = cache.buffer[cache.index]
		cache.sum -= evicted
		evictedWasMax = evicted == cache.max
		evictedWasMin = evicted == cache.min
	} else {
		cache.count++
	}
	cache.buffer[cache.index] = value
	cache.sum += value
	cache.index = (cache.index + 1) % cache.size
	if cache.count == 1 || value >= cache.max {
		cache.max = value
	} else if evictedWasMax {
		cache.max = cache.buffer[0]
		for i := 1; i < cache.count; i++ {
			if cache.buffer[i] > cache.max {
				cache.max = cache.buffer[i]
			}
		}
	}
	if cache.count == 1 || value <= cache.min {
		cache.min = value
	} else if evictedWasMin {
		cache.min = cache.buffer[0]
		for i := 1; i < cache.count; i++ {
			if cache.buffer[i] < cache.min {
				cache.min = cache.buffer[i]
			}
		}
	}
}

func (cache *windowedValueCache) compute(stats windowStat) (lst float64, ave float64, min float64, max float64, p95 float64, err error) {
	if cache.count == 0 {
		err = errors.New("no data available in valueCache")
		return
	}
	if stats&windowStatLst != 0 {
		lastIndex := cache.index - 1
		if lastIndex < 0 {
			lastIndex = cache.size - 1
		}
		lst = cache.buffer[lastIndex]
	}
	if stats&windowStatAve != 0 {
		ave = cache.sum / float64(cache.count)
	}
	if stats&windowStatMin != 0 {
		min = cache.min
	}
	if stats&windowStatMax != 0 {
		max = cache.max
	}
	if stats&windowStatP95 != 0 {
		for i := 0; i < cache.count; i++ {
			j := (cache.index + i) % cache.size
			cache.scratch[i] = cache.buffer[j]
		}
		sort.Float64s(cache.scratch[:cache.count])
		indexP95 := (cache.count*95+99)/100 - 1
		if indexP95 < 0 {
			indexP95 = 0
		}
		p95 = cache.scratch[indexP95]
	}
	return
}

func test() {

	processorUsedCache := newWindowedValueCache(60)
	value, _ := cpu.Percent(time.Second, false)
	processorUsedCache.push(value[0])
	_, _, _, _, processorUsedP95, _ := processorUsedCache.compute(windowStatP95)
	_ = processorUsedP95

	memoryUsedCache := newWindowedValueCache(60)
	memory, _ := mem.VirtualMemory()
	memoryUsedCache.push(memory.UsedPercent)
	_, _, _, memoryUsedMax, _, _ := memoryUsedCache.compute(windowStatMax)
	_ = memoryUsedMax

	memoryAllocatedCache := newLastValueCache()
	memoryAllocatedCache.push(rand.Float64())
	memoryAllocatedLast, _, _, _, _, _ := memoryAllocatedCache.compute(windowStatLst)
	_ = memoryAllocatedLast

	containerHasFailedCache := newWindowedValueCache(60)
	containerHasFailedCache.push(1)
	_, _, containerHasFailed, _, _, _ := containerHasFailedCache.compute(windowStatMin)
	_ = containerHasFailed == 0

	serviceIsFailingCache := newLastValueCache()
	serviceIsFailingCache.push(0)
	serviceIsFailing, _, _, _, _, _ := serviceIsFailingCache.compute(windowStatLst)
	_ = serviceIsFailing == 0

}
