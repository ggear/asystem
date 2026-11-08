package probe

import (
	"context"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"syscall"
	"time"

	"supervisor/internal/metric"
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
	SkipPeriod    time.Duration
	TimeoutPeriod time.Duration
	ShrinkPercent int
	LockPeriod    time.Duration
	Runs          string
	From          string
	File          string
	Record        string
	Target        string
	Paths         string
	Carry         []string
	ForceFull     bool
	NoRestart     bool
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
	manifest, found := readBackupManifest(root, run)
	if !found {
		fmt.Fprintf(stderr, "No manifest for run [%s] under [%s]\n", run, root)
		return 1
	}
	manifest.Verdict, manifest.Accepted = metric.BackupStateSuccess, true
	if err := writeBackupManifest(root, run, manifest); err != nil {
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

func lockBackupModule(stderr io.Writer, module, source string, period time.Duration) (release func(), ok bool) {
	held, wasHeld := os.LookupEnv(moduleLockHeldVariable)
	if held == module {
		return func() {}, true
	}
	parent := filepath.Dir(source)
	if err := os.MkdirAll(parent, 0o755); err != nil {
		fmt.Fprintf(stderr, "Lock directory [%s] could not be created [%v]\n", parent, err)
		return nil, false
	}
	lock, err := os.OpenFile(filepath.Join(parent, treeLockLeaf), os.O_CREATE|os.O_RDWR, 0o644)
	if err != nil {
		fmt.Fprintf(stderr, "Lock for [%s] could not be opened [%v]\n", module, err)
		return nil, false
	}
	deadline := time.Now().Add(period)
	for syscall.Flock(int(lock.Fd()), syscall.LOCK_EX|syscall.LOCK_NB) != nil {
		if time.Now().After(deadline) {
			fmt.Fprintf(stderr, "Another actor holds the lock for [%s] at [%s], giving up after [%s]\n", module, lock.Name(), period)
			_ = lock.Close()
			return nil, false
		}
		time.Sleep(time.Second)
	}
	_ = os.Setenv(moduleLockHeldVariable, module)
	return func() {
		if wasHeld {
			_ = os.Setenv(moduleLockHeldVariable, held)
		} else {
			_ = os.Unsetenv(moduleLockHeldVariable)
		}
		_ = lock.Close()
	}, true
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
