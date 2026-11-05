package probe

import (
	"bytes"
	"context"
	"io"
	"os"
	"os/exec"
	"strings"
	"syscall"
	"time"
)

const (
	backupHookInterrupted = "backup_interrupted"
	backupHookCompleted   = "backup_completed"
	backupHookFingerprint = "backup_fingerprinted"
	backupHookPrunedStore = "backup_pruned_store"
	backupHookWritten     = "backup_written"
	backupHookGrace       = 30 * time.Second
)

type backupHooks struct {
	script string
	env    []string
}

func (h backupHooks) command(ctx context.Context, name string, arguments ...string) *exec.Cmd {
	command := exec.CommandContext(ctx, "bash", append([]string{"-c", `set -o pipefail; . "$1" || exit 1; shift; "$@"`, "backup", h.script, name}, arguments...)...)
	command.Env = append(os.Environ(), h.env...)
	command.SysProcAttr = &syscall.SysProcAttr{Setpgid: true}
	command.Cancel = func() error { return syscall.Kill(-command.Process.Pid, syscall.SIGTERM) }
	command.WaitDelay = backupHookGrace
	return command
}

func (h backupHooks) defined(ctx context.Context) map[string]bool {
	command := h.command(ctx, "declare", "-F", backupHookInterrupted, backupHookCompleted, backupHookFingerprint, backupHookPrunedStore)
	output, err := command.Output()
	defined := map[string]bool{}
	if err != nil && len(output) == 0 {
		return defined
	}
	for line := range strings.SplitSeq(string(output), "\n") {
		if fields := strings.Fields(line); len(fields) > 0 {
			defined[fields[len(fields)-1]] = true
		}
	}
	return defined
}

func (h backupHooks) run(ctx context.Context, stdout, stderr io.Writer, name string, arguments ...string) error {
	command := h.command(ctx, name, arguments...)
	command.Stdout, command.Stderr = stdout, stderr
	return command.Run()
}

func (h backupHooks) capture(ctx context.Context, stderr io.Writer, name string, arguments ...string) (string, error) {
	command := h.command(ctx, name, arguments...)
	var output bytes.Buffer
	command.Stdout, command.Stderr = &output, stderr
	err := command.Run()
	return output.String(), err
}
