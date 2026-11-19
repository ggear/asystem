package probe

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"
)

func TestProbeUtilRestartLog_Write(t *testing.T) {
	home := t.TempDir()
	log := newRestartLog(home)
	log.now = func() time.Time { return time.Date(2026, 11, 19, 10, 0, 0, 0, time.UTC) }
	log.write("plex", "state [%s] reason [%s]", "waiting", "a prerequisite is not met")
	log.write("plex", "state [%s]", "restarting")
	data, err := os.ReadFile(filepath.Join(home, "plex", "restart", "restart.log"))
	if err != nil {
		t.Fatalf("read failed with [%v]", err)
	}
	want := "2026-11-19T10:00:00.000Z state [waiting] reason [a prerequisite is not met]\n2026-11-19T10:00:00.000Z state [restarting]\n"
	if string(data) != want {
		t.Fatalf("log: got %q want %q", data, want)
	}
}

func TestProbeUtilRestartLog_Rotate(t *testing.T) {
	home := t.TempDir()
	log := newRestartLog(home)
	line := strings.Repeat("x", 1024)
	for range 8 * 1024 {
		log.write("plex", "%s", line)
	}
	entries, err := os.ReadDir(filepath.Join(home, "plex", "restart"))
	if err != nil {
		t.Fatalf("read failed with [%v]", err)
	}
	if got := len(entries); got != restartLogKeep {
		t.Fatalf("files: got %d want %d", got, restartLogKeep)
	}
	for _, entry := range entries {
		info, _ := entry.Info()
		if info.Size() > restartLogSize+2048 {
			t.Fatalf("file [%s] is [%d] bytes, over its limit", entry.Name(), info.Size())
		}
	}
}

func TestProbeUtilRestartLog_Unwritable(t *testing.T) {
	blocker := filepath.Join(t.TempDir(), "file")
	if err := os.WriteFile(blocker, nil, 0o644); err != nil {
		t.Fatalf("write failed with [%v]", err)
	}
	newRestartLog(blocker).write("plex", "state [ok]")
}
