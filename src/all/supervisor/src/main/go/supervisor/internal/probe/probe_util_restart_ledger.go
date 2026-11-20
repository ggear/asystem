package probe

import (
	"encoding/json"
	"maps"
	"os"
	"path/filepath"
	"slices"
	"sync"
	"time"

	"supervisor/internal/config"
)

func newRestartLedger(path string) *restartLedger {
	ledger := &restartLedger{path: path, document: restartDocument{Services: make(map[string]restartRecord)}}
	var document restartDocument
	if data, err := os.ReadFile(path); err == nil && json.Unmarshal(data, &document) == nil && document.Services != nil {
		ledger.document = document
	}
	return ledger
}

func (l *restartLedger) observed(service string, container string, dockerCount int, now time.Time) (int, int, error) {
	l.mutex.Lock()
	defer l.mutex.Unlock()
	record, current := l.recordOf(service, container)
	changed := !current
	seen := dockerCount
	if record.Seen != nil {
		seen = *record.Seen
	}
	for range max(dockerCount-seen, 0) {
		record.Rises = append(record.Rises, now.Unix())
		changed = true
	}
	cutoff := now.Add(-restartWindow).Unix()
	rises := slices.DeleteFunc(slices.Clone(record.Rises), func(at int64) bool { return at <= cutoff })
	if record.Seen == nil || *record.Seen != dockerCount || len(rises) != len(record.Rises) {
		changed = true
	}
	record.Seen, record.Rises = &dockerCount, rises
	if changed {
		if err := l.persist(l.replaced(service, record)); err != nil {
			return 0, 0, err
		}
	}
	supervised := 0
	for _, attempt := range record.Attempts {
		if attempt > cutoff {
			supervised++
		}
	}
	return len(rises), supervised, nil
}

func (l *restartLedger) history(service string, container string) restartHistory {
	l.mutex.Lock()
	defer l.mutex.Unlock()
	record, _ := l.recordOf(service, container)
	attempts := make([]time.Time, 0, len(record.Attempts))
	for _, attempt := range record.Attempts {
		attempts = append(attempts, time.Unix(attempt, 0))
	}
	return restartHistory{attempts: attempts, streak: record.Streak, image: record.Image}
}

func (l *restartLedger) record(service string, container string, at time.Time) error {
	return l.update(service, container, func(record *restartRecord) {
		record.Streak++
		record.Attempts = append(record.Attempts, at.Unix())
		if len(record.Attempts) > restartAttemptsKept {
			record.Attempts = record.Attempts[len(record.Attempts)-restartAttemptsKept:]
		}
	})
}

func (l *restartLedger) refund(service string, container string) error {
	return l.update(service, container, func(record *restartRecord) {
		if len(record.Attempts) == 0 {
			return
		}
		record.Attempts = record.Attempts[:len(record.Attempts)-1]
		record.Streak = max(record.Streak-1, 0)
	})
}

func (l *restartLedger) settled(service string, container string) error {
	return l.update(service, container, func(record *restartRecord) { record.Streak = 0 })
}

func (l *restartLedger) imaged(service string, container string, image string) error {
	return l.update(service, container, func(record *restartRecord) { record.Image = image })
}

func (l *restartLedger) booted(boot string) error {
	l.mutex.Lock()
	defer l.mutex.Unlock()
	if l.document.Boot == boot {
		return nil
	}
	return l.persist(l.clearedDocument(boot))
}

func (l *restartLedger) woken() error {
	l.mutex.Lock()
	defer l.mutex.Unlock()
	return l.persist(l.clearedDocument(l.document.Boot))
}

func (l *restartLedger) clearedDocument(boot string) restartDocument {
	updated := restartDocument{Boot: boot, Services: make(map[string]restartRecord, len(l.document.Services))}
	for name, record := range l.document.Services {
		record.Streak = 0
		record.Attempts = nil
		updated.Services[name] = record
	}
	return updated
}

func (l *restartLedger) update(service string, container string, change func(*restartRecord)) error {
	l.mutex.Lock()
	defer l.mutex.Unlock()
	record, _ := l.recordOf(service, container)
	change(&record)
	return l.persist(l.replaced(service, record))
}

func (l *restartLedger) recordOf(service string, container string) (restartRecord, bool) {
	record, found := l.document.Services[service]
	if !found || record.Container != container {
		return restartRecord{Container: container, Image: record.Image}, false
	}
	return record, true
}

func (l *restartLedger) replaced(service string, record restartRecord) restartDocument {
	updated := restartDocument{Boot: l.document.Boot, Services: make(map[string]restartRecord, len(l.document.Services)+1)}
	maps.Copy(updated.Services, l.document.Services)
	updated.Services[service] = record
	return updated
}

func (l *restartLedger) persist(updated restartDocument) error {
	data, err := json.Marshal(updated)
	if err != nil {
		return err
	}
	if err := os.MkdirAll(filepath.Dir(l.path), 0o755); err != nil {
		return err
	}
	temporary := l.path + ".tmp"
	if err := os.WriteFile(temporary, data, 0o644); err != nil {
		return err
	}
	if err := os.Rename(temporary, l.path); err != nil {
		return err
	}
	l.document = updated
	return nil
}

type restartRecord struct {
	Container string  `json:"container"`
	Image     string  `json:"image,omitempty"`
	Seen      *int    `json:"seen,omitempty"`
	Rises     []int64 `json:"rises,omitempty"`
	Streak    int     `json:"streak"`
	Attempts  []int64 `json:"attempts"`
}

type restartDocument struct {
	Boot     string                   `json:"boot"`
	Services map[string]restartRecord `json:"services"`
}

type restartHistory struct {
	attempts []time.Time
	streak   int
	image    string
}

type restartLedger struct {
	path     string
	mutex    sync.Mutex
	document restartDocument
}

const (
	restartAttemptsKept = 16
)

var (
	restartLedgerPath = filepath.Join(config.DirServiceHome, "supervisor", "restart", "ledger.json")
)
