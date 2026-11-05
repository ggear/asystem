package probe

import (
	"context"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"strings"
	"syscall"
	"time"
)

type BackupModuleRequest struct {
	Arguments     []string
	Source        string
	Script        string
	Run           string
	State         string
	Root          string
	Live          string
	Includes      []string
	Excludes      []string
	SkipHours     int
	TimeoutHours  int
	ShrinkPercent int
	LockWait      int
	Pinned        string
	From          string
	File          string
	Mode          string
	Record        string
	Target        string
	Paths         string
	Carry         []string
	ForceFull     bool
	Restart       bool
	Force         bool
	NoBackup      bool
	KeepScratch   bool
}

func BackupModuleAccept(_ context.Context, request BackupModuleRequest, stdout, stderr io.Writer) int {
	_, _, root, ok := resolveBackupModule(request, stderr, 2)
	if !ok {
		return 2
	}
	run := request.Arguments[1]
	path := backupManifestPath(root, run)
	data, err := os.ReadFile(path)
	if err != nil {
		fmt.Fprintf(stderr, "No manifest for run [%s] under [%s]\n", run, root)
		return 1
	}
	lines := strings.Split(string(data), "\n")
	for index, line := range lines {
		switch {
		case strings.HasPrefix(line, `  "verdict": "`) && strings.HasSuffix(line, `",`):
			lines[index] = `  "verdict": "success",`
		case line == `  "accepted": false,`:
			lines[index] = `  "accepted": true,`
		}
	}
	if err := os.WriteFile(path+".tmp", []byte(strings.Join(lines, "\n")), 0o644); err != nil {
		fmt.Fprintf(stderr, "Backup failed [%v]\n", err)
		return 1
	}
	if err := os.Rename(path+".tmp", path); err != nil {
		fmt.Fprintf(stderr, "Backup failed [%v]\n", err)
		return 1
	}
	fmt.Fprintf(stdout, "Accepted run [%s]\n", run)
	return 0
}

func BackupModuleParent(_ context.Context, request BackupModuleRequest, stdout, stderr io.Writer) int {
	_, _, root, ok := resolveBackupModule(request, stderr, 1)
	if !ok {
		return 2
	}
	fmt.Fprintln(stdout, parentBackupRun(root, request.Run))
	return 0
}

func BackupModuleEpoch(_ context.Context, request BackupModuleRequest, stdout, _ io.Writer) int {
	if len(request.Arguments) != 1 || len(request.Arguments[0]) < len(backupTimestampFormat) {
		fmt.Fprintln(stdout, 0)
		return 0
	}
	stamp := request.Arguments[0]
	fmt.Fprintln(stdout, backupRunTime(stamp[len(stamp)-len(backupTimestampFormat):]).Unix())
	return 0
}

func lockBackupModule(stderr io.Writer, module, source string, wait int) bool {
	if os.Getenv(moduleLockHeldVariable) == module {
		return true
	}
	parent := filepath.Dir(source)
	if os.MkdirAll(parent, 0o755) != nil {
		return true
	}
	lock, err := os.OpenFile(filepath.Join(parent, treeLockLeaf), os.O_CREATE|os.O_RDWR, 0o644)
	if err != nil {
		return true
	}
	deadline := time.Now().Add(time.Duration(wait) * time.Second)
	for syscall.Flock(int(lock.Fd()), syscall.LOCK_EX|syscall.LOCK_NB) != nil {
		if time.Now().After(deadline) {
			fmt.Fprintf(stderr, "Another actor holds the lock for [%s] at [%s], giving up after [%d] seconds\n", module, lock.Name(), wait)
			_ = lock.Close()
			return false
		}
		time.Sleep(time.Second)
	}
	_ = os.Setenv(moduleLockHeldVariable, module)
	return true
}

func resolveBackupModule(request BackupModuleRequest, stderr io.Writer, arguments int) (module, source, root string, ok bool) {
	if len(request.Arguments) != arguments {
		fmt.Fprintf(stderr, "Backup needs [%d] arguments, given [%d]\n", arguments, len(request.Arguments))
		return "", "", "", false
	}
	module = request.Arguments[0]
	path := request.Source
	if path == "" {
		path = filepath.Join(filepath.Dir(serviceHomeDir(module)), "latest")
	}
	source, err := filepath.EvalSymlinks(path)
	if err != nil {
		fmt.Fprintf(stderr, "Source [%s] could not be resolved [%v]\n", path, err)
		return "", "", "", false
	}
	return module, source, filepath.Join(filepath.Dir(source), treeBackupDirectory), true
}
