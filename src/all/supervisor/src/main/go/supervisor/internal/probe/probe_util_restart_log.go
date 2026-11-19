package probe

import (
	"fmt"
	"os"
	"path/filepath"
	"sync"
	"time"
)

func newRestartLog(home string) *restartLog {
	return &restartLog{home: home, directory: "restart", leaf: restartLogLeaf, now: time.Now}
}

func newSwitchLog(home string) *restartLog {
	return &restartLog{home: home, directory: "switch", leaf: "switch.log", now: time.Now}
}

func (l *restartLog) write(service string, format string, args ...any) {
	l.mutex.Lock()
	defer l.mutex.Unlock()
	directory := filepath.Join(l.home, service, l.directory)
	if os.MkdirAll(directory, 0o755) != nil {
		return
	}
	path := filepath.Join(directory, l.leaf)
	if info, err := os.Stat(path); err == nil && info.Size() >= restartLogSize {
		for index := restartLogKeep - 1; index >= 1; index-- {
			_ = os.Rename(fmt.Sprintf("%s.%d", path, index), fmt.Sprintf("%s.%d", path, index+1))
		}
		_ = os.Rename(path, path+".1")
		_ = os.Remove(fmt.Sprintf("%s.%d", path, restartLogKeep))
	}
	file, err := os.OpenFile(path, os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0o644)
	if err != nil {
		return
	}
	defer func() { _ = file.Close() }()
	_, _ = fmt.Fprintf(file, "%s %s\n", l.now().Format("2006-01-02T15:04:05.000Z07:00"), fmt.Sprintf(format, args...))
}

type restartLog struct {
	mutex     sync.Mutex
	home      string
	directory string
	leaf      string
	now       func() time.Time
}

const (
	restartLogLeaf = "restart.log"
	restartLogSize = 1 << 20
	restartLogKeep = 5
)
