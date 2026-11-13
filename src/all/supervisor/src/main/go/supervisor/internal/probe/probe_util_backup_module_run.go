package probe

import (
	"bytes"
	"context"
	"fmt"
	"io"
	"os"
	"os/exec"
	"os/signal"
	"path/filepath"
	"slices"
	"strconv"
	"strings"
	"syscall"
	"time"

	"supervisor/internal/metric"
)

func BackupModuleRun(ctx context.Context, request BackupModuleRequest, stdout, stderr io.Writer) int {
	module, source, root, ok := resolveBackupModule(request, stderr, 1)
	if !ok {
		return 2
	}
	if request.Script == "" {
		fmt.Fprintln(stderr, "Backup needs the script holding the module hooks")
		return 2
	}
	stamp, version := time.Now().Format(backupTimestampFormat), filepath.Base(source)
	release, locked := lockBackupModule(stderr, module, source, request.LockPeriod)
	if !locked {
		return 1
	}
	defer release()
	_ = filepath.WalkDir(root, func(path string, entry os.DirEntry, err error) error {
		if err == nil && !entry.IsDir() && strings.HasSuffix(path, ".tmp") {
			_ = os.Remove(path)
		}
		return nil
	})
	existing := backupRuns(root)
	newest := "none"
	if len(existing) > 0 {
		newest = existing[len(existing)-1]
		age := time.Since(backupRunTime(newest))
		if age < request.SkipPeriod {
			_, newestVersion := parseBackupArtefact(module, filepath.Join(root, newest))
			fmt.Fprintf(stdout, "Backup skipped, newest backup [%s] of version [%s] is [%d] seconds old, skipping given within [%s]\n", newest, newestVersion, int(age.Seconds()), request.SkipPeriod)
			return 0
		}
	}
	fmt.Fprintf(stdout, "Starting backup from version [%s] holding [%d] backups, newest [%s]\n", version, len(existing), newest)
	state, err := os.MkdirTemp("", "backup-module-")
	if err != nil {
		fmt.Fprintf(stderr, "Backup state directory could not be created [%v]\n", err)
		return 1
	}
	defer func() { _ = os.RemoveAll(state) }()
	binary, _ := os.Executable()
	hooks := moduleHooks{script: request.Script, env: []string{
		"BACKUP_RUN_TIMESTAMP=" + stamp, "BACKUP_STATE_DIR=" + state, "BACKUP_SUPERVISOR=" + binary,
		"BACKUP_FORCE_FULL=" + strconv.FormatBool(request.ForceFull), "BACKUP_SKIP_HOURS=" + strconv.Itoa(int(request.SkipPeriod.Hours())),
		"BACKUP_TIMEOUT_HOURS=" + strconv.Itoa(int(request.TimeoutPeriod.Hours())), "BACKUP_SERVICE_RESTART=" + strconv.FormatBool(!request.NoRestart),
		"BACKUP_SOURCE_PATH=" + source,
	}}
	defined := map[string]bool{}
	declared, _ := hooks.command(ctx, "declare", "-F", moduleHookInterrupted, moduleHookCompleted, moduleHookFingerprint, moduleHookPrunedStore).Output()
	for line := range strings.SplitSeq(string(declared), "\n") {
		if fields := strings.Fields(line); len(fields) > 0 {
			defined[fields[len(fields)-1]] = true
		}
	}
	targeted := func() string {
		data, readErr := os.ReadFile(filepath.Join(state, moduleTargetLeaf))
		if readErr != nil {
			return ""
		}
		return strings.TrimSpace(string(data))
	}
	discarded := func(target string) {
		if target == "" {
			return
		}
		_ = os.Remove(target + ".tmp")
		if _, statErr := os.Stat(target); statErr != nil {
			_ = os.Remove(filepath.Join(root, stamp))
		}
	}
	signals := make(chan os.Signal, 1)
	signal.Notify(signals, syscall.SIGINT, syscall.SIGTERM, syscall.SIGHUP)
	defer signal.Stop(signals)
	hookCtx, cancelHook := context.WithTimeout(ctx, max(request.TimeoutPeriod, time.Hour)+time.Hour)
	defer cancelHook()
	received := make(chan os.Signal, 1)
	go func() {
		select {
		case caught := <-signals:
			received <- caught
			cancelHook()
		case <-hookCtx.Done():
		}
	}()
	started := time.Now()
	written := hooks.run(hookCtx, stdout, stderr, moduleHookWritten) == nil
	select {
	case caught := <-received:
		if defined[moduleHookInterrupted] {
			_ = hooks.run(context.WithoutCancel(ctx), stdout, stderr, moduleHookInterrupted)
		}
		discarded(targeted())
		return map[os.Signal]int{syscall.SIGINT: 130, syscall.SIGTERM: 143, syscall.SIGHUP: 129}[caught]
	default:
	}
	target := targeted()
	verified := func() bool {
		if target == "" {
			fmt.Fprintln(stderr, "Nothing named the backup, call backup_target in backup_written")
			return false
		}
		info, statErr := os.Stat(target + ".tmp")
		if statErr != nil || info.Size() == 0 {
			fmt.Fprintf(stderr, "Backup [%s] was written empty, discarding it\n", target)
			return false
		}
		var tool string
		switch {
		case strings.HasSuffix(target, ".gz"):
			tool = "gzip"
		case strings.HasSuffix(target, ".zip"):
			tool = "unzip"
		}
		if tool == "" {
			return true
		}
		if _, lookErr := exec.LookPath(tool); lookErr != nil {
			fmt.Fprintf(stderr, "Backup [%s] cannot be checked, [%s] is not installed, discarding it\n", target, tool)
			return false
		}
		if _, code, abandoned := bounded(context.Background(), moduleToolWait, tool, "-t", target+".tmp"); abandoned || code != 0 {
			fmt.Fprintf(stderr, "Backup [%s] failed its integrity check, discarding it\n", target)
			return false
		}
		return true
	}
	judged := ""
	manifested := func() error {
		kind, parent := backupKindFull, ""
		if backupArtefactKind(filepath.Base(target)) == backupKindDelta {
			kind, parent = backupKindDelta, previousBackupRun([]string{root}, stamp)
		}
		var current []backupFingerprintUnit
		if defined[moduleHookFingerprint] {
			fingerprintCtx, cancel := context.WithTimeout(ctx, moduleToolWait)
			command := hooks.command(fingerprintCtx, moduleHookFingerprint, target)
			var output bytes.Buffer
			command.Stdout, command.Stderr = &output, stderr
			if command.Run() == nil {
				current = parseBackupFingerprint(output.String())
			}
			cancel()
		} else {
			var includes []string
			if data, readErr := os.ReadFile(filepath.Join(state, moduleIncludesLeaf)); readErr == nil {
				includes = strings.Split(strings.TrimSuffix(string(data), "\n"), "\n")
			}
			if units, fingerprintErr := fingerprintBackupArtefact(target, includes); fingerprintErr == nil {
				current = units
			}
		}
		baselineRun := ""
		var baseline backupManifest
		for _, name := range slices.Backward(backupRuns(root)) {
			if candidate, found := readBackupManifest(root, name); name < stamp && found && candidate.Verdict == metric.BackupStateSuccess && len(candidate.Fingerprint) > 0 {
				baselineRun, baseline = name, candidate
				break
			}
		}
		verdict := judgeBackupRegression(current, baseline, baselineRun, request.ShrinkPercent)
		judged = verdict.verdict
		manifest := backupManifest{
			Kind: kind, Parent: parent, SourceVersion: version, SourceSoftware: versionedModule(ctx, hooks, stderr, version), Verdict: verdict.verdict, Baseline: baselineRun, Evidence: verdict.evidence, Fingerprint: current,
		}
		if err := writeBackupManifest(root, stamp, manifest); err != nil {
			return err
		}
		for _, line := range verdict.evidence {
			fmt.Fprintf(stderr, "Backup %s\n", line)
		}
		shownParent := parent
		if shownParent == "" {
			shownParent = "none"
		}
		fmt.Fprintf(stdout, "Manifest [%s] kind [%s] parent [%s] units [%d]\n", verdict.verdict, kind, shownParent, len(current))
		return nil
	}
	status := 0
	kept := written && verified()
	if kept {
		if renameErr := os.Rename(target+".tmp", target); renameErr != nil {
			fmt.Fprintf(stderr, "Backup [%s] could not be named [%v]\n", target, renameErr)
			kept = false
		}
	}
	if kept {
		var megabytes int64
		if info, statErr := os.Stat(target); statErr == nil {
			megabytes = (info.Size() + (1 << 20) - 1) >> 20
		}
		fmt.Fprintf(stdout, "Finished backup [%d] MB in [%d] seconds to [%s]\n", megabytes, int(time.Since(started).Seconds()), target)
		if manifestErr := manifested(); manifestErr != nil {
			fmt.Fprintf(stderr, "Manifest for [%s] could not be written [%v]\n", stamp, manifestErr)
			status = 1
		}
		if defined[moduleHookPrunedStore] {
			_ = hooks.run(hookCtx, stdout, stderr, moduleHookPrunedStore)
		}
		if judged == metric.BackupStateSuccess {
			_ = os.RemoveAll(filepath.Join(filepath.Dir(source), "replaced"))
		}
	} else {
		fmt.Fprintf(stderr, "Failed backup in [%d] seconds\n", int(time.Since(started).Seconds()))
		status = 1
		discarded(target)
	}
	if defined[moduleHookCompleted] {
		if err := hooks.run(context.WithoutCancel(ctx), stdout, stderr, moduleHookCompleted); err != nil {
			status = 1
		}
	}
	var directories []string
	_ = filepath.WalkDir(root, func(path string, entry os.DirEntry, err error) error {
		if err == nil && entry.IsDir() {
			directories = append(directories, path)
		}
		return nil
	})
	for _, directory := range slices.Backward(directories) {
		_ = os.Remove(directory)
	}
	return status
}

type moduleHooks struct {
	script string
	env    []string
}

func (h moduleHooks) command(ctx context.Context, name string, arguments ...string) *exec.Cmd {
	command := exec.CommandContext(ctx, "bash", append([]string{"-c", `set -o pipefail; . "$1" || exit 1; shift; "$@"`, "backup", h.script, name}, arguments...)...)
	command.Env = append(os.Environ(), h.env...)
	killWithGroup(command, moduleHookGrace)
	return command
}

func (h moduleHooks) run(ctx context.Context, stdout, stderr io.Writer, name string, arguments ...string) error {
	command := h.command(ctx, name, arguments...)
	command.Stdout, command.Stderr = stdout, stderr
	return command.Run()
}

const (
	moduleHookInterrupted  = "backup_interrupted"
	moduleHookCompleted    = "backup_completed"
	moduleHookFingerprint  = "backup_fingerprinted"
	moduleHookVersioned    = "backup_versioned"
	moduleHookPrunedStore  = "backup_pruned_store"
	moduleHookWritten      = "backup_written"
	moduleHookGrace        = 30 * time.Second
	moduleLockHeldVariable = "ASYSTEM_LOCK_HELD"
	moduleTargetLeaf       = "target"
	moduleIncludesLeaf     = "includes"
	moduleToolWait         = 30 * time.Minute
)
