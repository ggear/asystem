package engine

import (
	"sync"
	"time"
)

func newHostLiveness() *hostLiveness {
	return &hostLiveness{status: make(map[string]bool), offlineAt: make(map[string]int64), heardAt: make(map[string]time.Time), retainedAt: make(map[string]time.Time), openedAt: time.Now()}
}

func (h *hostLiveness) assertOnline(hostName string) bool {
	online, known := h.statusOf(hostName)
	return !known || online
}

func (h *hostLiveness) statusOf(hostName string) (online, known bool) {
	h.mutex.RLock()
	defer h.mutex.RUnlock()
	online, known = h.status[hostName]
	return online, known
}

func (h *hostLiveness) store(hostName string, online bool) {
	h.mutex.Lock()
	defer h.mutex.Unlock()
	if !online {
		h.offlineAt[hostName] = time.Now().Unix()
	}
	h.status[hostName] = online
}

func (h *hostLiveness) offlineAtOf(hostName string) int64 {
	h.mutex.RLock()
	defer h.mutex.RUnlock()
	return h.offlineAt[hostName]
}

func (h *hostLiveness) hear(hostName string) {
	h.mutex.Lock()
	defer h.mutex.Unlock()
	h.heardAt[hostName] = time.Now()
}

func (h *hostLiveness) hearRetained(hostName string, published int64, at time.Time) {
	h.mutex.Lock()
	defer h.mutex.Unlock()
	h.floodAt = at
	if published <= 0 {
		return
	}
	if stamped := time.Unix(published, 0); stamped.After(h.retainedAt[hostName]) {
		h.retainedAt[hostName] = stamped
	}
}

func (h *hostLiveness) reset(opened time.Time) {
	h.mutex.Lock()
	defer h.mutex.Unlock()
	clear(h.status)
	clear(h.offlineAt)
	clear(h.retainedAt)
	h.openedAt = opened
	h.floodAt = time.Time{}
}

func (h *hostLiveness) quietAmong(hostNames []string, now time.Time, limits quietLimits) map[string]time.Duration {
	h.mutex.RLock()
	defer h.mutex.RUnlock()
	quiet := make(map[string]time.Duration)
	for _, hostName := range hostNames {
		online, known := h.status[hostName]
		if known && !online {
			continue
		}
		last, window := h.heardAt[hostName], limits.provenAfter
		if !last.After(h.openedAt) {
			last, window = h.openedAt, limits.unprovenAfter
			freshest := h.retainedAt[hostName]
			flooded := !h.floodAt.IsZero() && now.Sub(h.floodAt) >= hostFloodQuiet
			if limits.staleAfter > 0 && flooded && !freshest.IsZero() && h.openedAt.Sub(freshest) > limits.staleAfter {
				quiet[hostName] = now.Sub(freshest)
				continue
			}
		}
		if silence := now.Sub(last); silence > window {
			quiet[hostName] = silence
		}
	}
	return quiet
}

type hostLiveness struct {
	mutex      sync.RWMutex
	status     map[string]bool
	offlineAt  map[string]int64
	heardAt    map[string]time.Time
	retainedAt map[string]time.Time
	openedAt   time.Time
	floodAt    time.Time
}

type quietLimits struct {
	provenAfter   time.Duration
	unprovenAfter time.Duration
	staleAfter    time.Duration
}

const hostFloodQuiet = 150 * time.Millisecond
