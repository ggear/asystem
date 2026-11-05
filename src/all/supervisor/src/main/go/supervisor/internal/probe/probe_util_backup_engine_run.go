package probe

import (
	"context"
	"errors"
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
)

const (
	backupFullSuffix       = "_full"
	backupDeltaSuffix      = "_delta"
	backupShrinkDefault    = 20
	backupLockWaitDefault  = 300
	backupLockLeaf         = ".lock"
	backupLockHeldVariable = "ASYSTEM_LOCK_HELD"
	backupTargetLeaf       = "target"
	backupIncludesLeaf     = "includes"
	backupEngineContract   = 2
	backupVerifyWait       = 30 * time.Minute
)

type backupEngineEnv struct {
	module     string
	source     string
	script     string
	skipHours  int
	forceFull  bool
	timeout    time.Duration
	shrink     int
	lockWait   int
	runStamp   string
	stateDir   string
	engineBin  string
	sourceBase string
}

func backupEngineEnvOf(getenv func(string) string, now time.Time) (backupEngineEnv, error) {
	env := backupEngineEnv{
		module: getenv("BACKUP_MODULE_NAME"), source: getenv("BACKUP_INTERNAL_SOURCE_DIR"), script: getenv("BACKUP_SCRIPT"),
		forceFull: getenv("BACKUP_FORCE_FULL") == "true", skipHours: 1, shrink: backupShrinkDefault, lockWait: backupLockWaitDefault,
		runStamp: now.Format(backupTimestampFormat),
	}
	if env.module == "" || env.source == "" || env.script == "" {
		return env, errors.New("BACKUP_MODULE_NAME, BACKUP_INTERNAL_SOURCE_DIR and BACKUP_SCRIPT must all be set")
	}
	for name, target := range map[string]*int{"BACKUP_SKIP_HOURS": &env.skipHours, "BACKUP_SHRINK_PERCENT": &env.shrink, "BACKUP_LOCK_WAIT": &env.lockWait} {
		if text := getenv(name); text != "" {
			value, err := strconv.Atoi(text)
			if err != nil || value < 0 {
				return env, fmt.Errorf("%s [%s] is not a whole number", name, text)
			}
			*target = value
		}
	}
	hours := 1
	if text := getenv("BACKUP_TIMEOUT_HOURS"); text != "" {
		if value, err := strconv.Atoi(text); err == nil && value > 0 {
			hours = value
		}
	}
	env.timeout = time.Duration(hours+1) * time.Hour
	env.sourceBase = filepath.Base(env.source)
	return env, nil
}

func (e backupEngineEnv) root() string {
	return filepath.Join(filepath.Dir(e.source), treeBackupDirectory)
}

func backupEngineRun(ctx context.Context, env backupEngineEnv, stdout, stderr io.Writer) int {
	root := env.root()
	if code := backupEngineLocked(env, stderr); code != 0 {
		return code
	}
	_ = filepath.WalkDir(root, func(path string, entry os.DirEntry, err error) error {
		if err == nil && !entry.IsDir() && strings.HasSuffix(path, ".tmp") {
			_ = os.Remove(path)
		}
		return nil
	})
	existing := backupRuns(root)
	newest := ""
	if len(existing) > 0 {
		newest = existing[len(existing)-1]
		age := time.Since(backupRunTime(newest))
		if age < time.Duration(env.skipHours)*time.Hour {
			_, version := parseBackupArtefact(env.module, filepath.Join(root, newest))
			fmt.Fprintf(stdout, "Backup skipped, newest backup [%s] of version [%s] is [%d] seconds old, skipping given within [%d] hours\n", newest, version, int(age.Seconds()), env.skipHours)
			return 0
		}
	}
	fmt.Fprintf(stdout, "Starting backup from version [%s] holding [%d] backups, newest [%s]\n", env.sourceBase, len(existing), orDefault(newest, "none"))
	state, err := os.MkdirTemp("", "backup-engine-")
	if err != nil {
		fmt.Fprintf(stderr, "Backup state directory could not be created [%v]\n", err)
		return 1
	}
	defer func() { _ = os.RemoveAll(state) }()
	binary, _ := os.Executable()
	env.stateDir, env.engineBin = state, binary
	hooks := backupHooks{script: env.script, env: []string{
		"BACKUP_RUN_TIMESTAMP=" + env.runStamp, "BACKUP_STATE_DIR=" + state, "BACKUP_ENGINE=" + binary,
		"BACKUP_FORCE_FULL=" + strconv.FormatBool(env.forceFull),
	}}
	defined := hooks.defined(ctx)
	signals := make(chan os.Signal, 1)
	signal.Notify(signals, syscall.SIGINT, syscall.SIGTERM, syscall.SIGHUP)
	defer signal.Stop(signals)
	hookCtx, cancelHook := context.WithTimeout(ctx, env.timeout)
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
	written := hooks.run(hookCtx, stdout, stderr, backupHookWritten) == nil
	select {
	case caught := <-received:
		if defined[backupHookInterrupted] {
			_ = hooks.run(context.WithoutCancel(ctx), stdout, stderr, backupHookInterrupted)
		}
		backupEngineDiscard(root, env.runStamp, backupEngineTarget(state))
		return map[os.Signal]int{syscall.SIGINT: 130, syscall.SIGTERM: 143, syscall.SIGHUP: 129}[caught]
	default:
	}
	target := backupEngineTarget(state)
	status := 0
	accepted := false
	if written {
		accepted = backupEngineVerified(target, stderr)
	}
	if accepted {
		if err := os.Rename(target+".tmp", target); err != nil {
			fmt.Fprintf(stderr, "Backup [%s] could not be named [%v]\n", target, err)
			accepted = false
		}
	}
	if accepted {
		size := backupEngineMegabytes(target)
		fmt.Fprintf(stdout, "Finished backup [%d] MB in [%d] seconds to [%s]\n", size, int(time.Since(started).Seconds()), target)
		if manifestErr := backupEngineManifested(ctx, env, hooks, defined[backupHookFingerprint], target, stdout, stderr); manifestErr != nil {
			fmt.Fprintf(stderr, "Manifest for [%s] could not be written [%v]\n", env.runStamp, manifestErr)
		}
		if defined[backupHookPrunedStore] {
			_ = hooks.run(hookCtx, stdout, stderr, backupHookPrunedStore)
		}
		_ = os.RemoveAll(filepath.Join(filepath.Dir(env.source), "replaced"))
	} else {
		fmt.Fprintf(stderr, "Failed backup in [%d] seconds\n", int(time.Since(started).Seconds()))
		status = 1
		backupEngineDiscard(root, env.runStamp, target)
	}
	if defined[backupHookCompleted] {
		if err := hooks.run(context.WithoutCancel(ctx), stdout, stderr, backupHookCompleted); err != nil {
			status = 1
		}
	}
	backupEngineSweep(root)
	return status
}

func backupEngineVerified(target string, stderr io.Writer) bool {
	if target == "" {
		fmt.Fprintln(stderr, "Nothing named the backup, call backup_target in backup_written")
		return false
	}
	info, err := os.Stat(target + ".tmp")
	if err != nil || info.Size() == 0 {
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
	if _, err := exec.LookPath(tool); err != nil {
		fmt.Fprintf(stderr, "Backup [%s] cannot be checked, [%s] is not installed, discarding it\n", target, tool)
		return false
	}
	if _, code, abandoned := bounded(context.Background(), backupVerifyWait, tool, "-t", target+".tmp"); abandoned || code != 0 {
		fmt.Fprintf(stderr, "Backup [%s] failed its integrity check, discarding it\n", target)
		return false
	}
	return true
}

func backupEngineManifested(ctx context.Context, env backupEngineEnv, hooks backupHooks, custom bool, target string, stdout, stderr io.Writer) error {
	root := env.root()
	kind := "full"
	if strings.Contains(filepath.Base(target), backupDeltaSuffix+".") {
		kind = "delta"
	}
	parent := ""
	if kind == "delta" {
		parent = backupPrevious(root, env.runStamp)
	}
	var current []fingerprintUnit
	if custom {
		fingerprintCtx, cancel := context.WithTimeout(ctx, backupVerifyWait)
		output, err := hooks.capture(fingerprintCtx, stderr, backupHookFingerprint, target)
		cancel()
		if err == nil {
			current = parseFingerprintLines(output)
		}
	} else if units, err := fingerprintBackupArchive(target, backupEngineIncludes(env.stateDir)); err == nil {
		current = units
	}
	baselineRun := backupBaseline(root, env.runStamp)
	var baseline backupManifest
	if baselineRun != "" {
		baseline, _ = readBackupManifest(root, baselineRun)
	}
	verdict := backupRegression(current, baseline, baselineRun, env.shrink)
	manifest := backupManifest{
		Kind: kind, Parent: parent, SourceVersion: env.sourceBase, Verdict: verdict.verdict, Baseline: baselineRun,
		Evidence: verdict.evidence, Fingerprint: current,
	}
	if err := writeBackupManifest(root, env.runStamp, manifest); err != nil {
		return err
	}
	for _, line := range verdict.evidence {
		fmt.Fprintf(stderr, "Backup %s\n", line)
	}
	fmt.Fprintf(stdout, "Manifest [%s] kind [%s] parent [%s] units [%d]\n", verdict.verdict, kind, orDefault(parent, "none"), len(current))
	return nil
}

func backupEngineLocked(env backupEngineEnv, stderr io.Writer) int {
	if os.Getenv(backupLockHeldVariable) == env.module {
		return 0
	}
	parent := filepath.Dir(env.source)
	if err := os.MkdirAll(parent, 0o755); err != nil {
		return 0
	}
	file, err := os.OpenFile(filepath.Join(parent, backupLockLeaf), os.O_CREATE|os.O_RDWR, 0o644)
	if err != nil {
		return 0
	}
	deadline := time.Now().Add(time.Duration(env.lockWait) * time.Second)
	for {
		if syscall.Flock(int(file.Fd()), syscall.LOCK_EX|syscall.LOCK_NB) == nil {
			_ = os.Setenv(backupLockHeldVariable, env.module)
			return 0
		}
		if time.Now().After(deadline) {
			fmt.Fprintf(stderr, "Another actor holds the lock for [%s] at [%s], giving up after [%d] seconds\n", env.module, file.Name(), env.lockWait)
			_ = file.Close()
			return 1
		}
		time.Sleep(time.Second)
	}
}

func backupEngineTarget(state string) string {
	data, err := os.ReadFile(filepath.Join(state, backupTargetLeaf))
	if err != nil {
		return ""
	}
	return strings.TrimSpace(string(data))
}

func backupEngineIncludes(state string) []string {
	data, err := os.ReadFile(filepath.Join(state, backupIncludesLeaf))
	if err != nil {
		return nil
	}
	return strings.Split(strings.TrimSuffix(string(data), "\n"), "\n")
}

func backupEngineDiscard(root, run, target string) {
	if target == "" {
		return
	}
	_ = os.Remove(target + ".tmp")
	if _, err := os.Stat(target); err != nil {
		_ = os.Remove(filepath.Join(root, run))
	}
}

func backupEngineSweep(root string) {
	var directories []string
	_ = filepath.WalkDir(root, func(path string, entry os.DirEntry, err error) error {
		if err == nil && entry.IsDir() {
			directories = append(directories, path)
		}
		return nil
	})
	for _, directorie := range slices.Backward(directories) {
		_ = os.Remove(directorie)
	}
}

func backupEngineMegabytes(path string) int64 {
	info, err := os.Stat(path)
	if err != nil {
		return 0
	}
	return (info.Size() + (1 << 20) - 1) >> 20
}

func backupRunTime(run string) time.Time {
	parsed, _ := time.ParseInLocation(backupTimestampFormat, run, time.Local)
	return parsed
}

func backupIsFull(dir string) bool {
	return backupHoldsSuffix(dir, backupFullSuffix+".")
}

func backupHoldsSuffix(dir string, marker string) bool {
	entries, err := os.ReadDir(dir)
	if err != nil {
		return false
	}
	for _, entry := range entries {
		if !entry.IsDir() && strings.Contains(entry.Name(), marker) {
			return true
		}
	}
	return false
}

func backupPrevious(root, run string) string {
	names := backupRuns(root)
	for _, name := range slices.Backward(names) {
		if name < run && (backupHoldsSuffix(filepath.Join(root, name), backupFullSuffix+".") || backupHoldsSuffix(filepath.Join(root, name), backupDeltaSuffix+".")) {
			return name
		}
	}
	return ""
}

func backupParent(root, run string) string {
	names := backupRuns(root)
	for _, name := range slices.Backward(names) {
		if name < run && backupIsFull(filepath.Join(root, name)) {
			return name
		}
	}
	return ""
}

func backupEngineName(module, run, version, suffix, extension string) string {
	return fmt.Sprintf("%s_at_%s_from_%s%s.%s", module, run, version, suffix, extension)
}

func orDefault(value, fallback string) string {
	if value == "" {
		return fallback
	}
	return value
}
