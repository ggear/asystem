package engine

import (
	"sync"
	"time"
)

func newHostLiveness() *hostLiveness {
	return &hostLiveness{status: make(map[string]bool), offlineAt: make(map[string]int64), heardAt: make(map[string]time.Time), openedAt: time.Now()}
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

func (h *hostLiveness) offlineStamp(hostName string) int64 {
	h.mutex.RLock()
	defer h.mutex.RUnlock()
	return h.offlineAt[hostName]
}

func (h *hostLiveness) hear(hostName string) {
	h.mutex.Lock()
	defer h.mutex.Unlock()
	h.heardAt[hostName] = time.Now()
}

func (h *hostLiveness) reset(opened time.Time) {
	h.mutex.Lock()
	defer h.mutex.Unlock()
	clear(h.status)
	clear(h.offlineAt)
	h.openedAt = opened
}

func (h *hostLiveness) quietAmong(hostNames []string, now time.Time, after time.Duration) map[string]time.Duration {
	h.mutex.RLock()
	defer h.mutex.RUnlock()
	quiet := make(map[string]time.Duration)
	for _, hostName := range hostNames {
		online, known := h.status[hostName]
		if known && !online {
			continue
		}
		last := h.heardAt[hostName]
		if h.openedAt.After(last) {
			last = h.openedAt
		}
		if silence := now.Sub(last); silence > after {
			quiet[hostName] = silence
		}
	}
	return quiet
}

type hostLiveness struct {
	mutex     sync.RWMutex
	status    map[string]bool
	offlineAt map[string]int64
	heardAt   map[string]time.Time
	openedAt  time.Time
}
