package probe

import (
	"encoding/json"
	"maps"
	"os"
	"path/filepath"
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

func (l *restartLedger) count(service string, container string) int {
	if l == nil {
		return 0
	}
	l.mutex.Lock()
	defer l.mutex.Unlock()
	record := l.document.Services[service]
	if record.Container != container {
		return 0
	}
	return record.Count
}

func (l *restartLedger) history(service string, container string) restartHistory {
	l.mutex.Lock()
	defer l.mutex.Unlock()
	record := l.document.Services[service]
	if record.Container != container {
		return restartHistory{}
	}
	attempts := make([]time.Time, 0, len(record.Attempts))
	for _, attempt := range record.Attempts {
		attempts = append(attempts, time.Unix(attempt, 0))
	}
	return restartHistory{attempts: attempts, streak: record.Streak}
}

func (l *restartLedger) record(service string, container string, at time.Time) error {
	return l.update(service, container, func(record *restartRecord) {
		record.Count++
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
		record.Count = max(record.Count-1, 0)
		record.Streak = max(record.Streak-1, 0)
	})
}

func (l *restartLedger) settled(service string, container string) error {
	return l.update(service, container, func(record *restartRecord) { record.Streak = 0 })
}

func (l *restartLedger) booted(boot string) error {
	l.mutex.Lock()
	defer l.mutex.Unlock()
	if l.document.Boot == boot {
		return nil
	}
	updated := restartDocument{Boot: boot, Services: make(map[string]restartRecord, len(l.document.Services))}
	for name, record := range l.document.Services {
		record.Streak = 0
		record.Attempts = nil
		updated.Services[name] = record
	}
	return l.persist(updated)
}

func (l *restartLedger) update(service string, container string, change func(*restartRecord)) error {
	l.mutex.Lock()
	defer l.mutex.Unlock()
	record := l.document.Services[service]
	if record.Container != container {
		record = restartRecord{Container: container}
	}
	change(&record)
	updated := restartDocument{Boot: l.document.Boot, Services: make(map[string]restartRecord, len(l.document.Services)+1)}
	maps.Copy(updated.Services, l.document.Services)
	updated.Services[service] = record
	return l.persist(updated)
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
	Count     int     `json:"count"`
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
