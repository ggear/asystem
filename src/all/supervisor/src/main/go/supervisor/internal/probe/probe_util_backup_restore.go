package probe

import (
	"bytes"
	"cmp"
	"context"
	"fmt"
	"io"
	"os"
	"os/exec"
	"path/filepath"
	"slices"
	"strconv"
	"strings"
	"time"

	"supervisor/internal/config"
	"supervisor/internal/metric"
)

func BackupModuleRestore(ctx context.Context, request BackupModuleRequest, stdout, stderr io.Writer) int {
	return runBackupModuleRestore(ctx, request, backupRestoreModeReplace, stdout, stderr)
}

func BackupModuleDrill(ctx context.Context, request BackupModuleRequest, stdout, stderr io.Writer) int {
	return runBackupModuleRestore(ctx, request, backupRestoreModeDrill, stdout, stderr)
}

func BackupModuleMerge(ctx context.Context, request BackupModuleRequest, stdout, stderr io.Writer) int {
	return runBackupModuleRestore(ctx, request, backupRestoreModeMerge, stdout, stderr)
}

func BackupModuleReport(_ context.Context, request BackupModuleRequest, stdout, _ io.Writer) int {
	fmt.Fprintln(stdout, reportedRestoreLine(strings.Join(request.Arguments, " ")))
	return 0
}

func BackupModuleRestoreFiles(_ context.Context, request BackupModuleRequest, stdout, stderr io.Writer) int {
	if len(request.Arguments) != 1 || request.Target == "" || request.File == "" || request.Run == "" {
		fmt.Fprintln(stderr, "Restore files needs a module, a target, an artifact and a run")
		return 2
	}
	_, source, _, ok := resolveBackupModule(request, stderr, 1)
	if !ok {
		return 2
	}
	if info, err := os.Stat(request.Target); err != nil || !info.IsDir() {
		fmt.Fprintf(stderr, "No restore target [%s]\n", request.Target)
		return 1
	}
	replaced := filepath.Join(filepath.Dir(source), "replaced", request.Run)
	declared := slices.DeleteFunc(strings.Split(request.Paths, ":"), func(path string) bool { return path == "" })
	moved := false
	for _, path := range declared {
		from := filepath.Join(request.Target, path)
		if _, err := os.Lstat(from); err != nil {
			continue
		}
		to := filepath.Join(replaced, path)
		if err := os.MkdirAll(filepath.Dir(to), 0o755); err != nil {
			fmt.Fprintf(stderr, "Could not move [%s] aside to [%s] [%v]\n", from, replaced, err)
			return 1
		}
		if err := os.Rename(from, to); err != nil {
			fmt.Fprintf(stderr, "Could not move [%s] aside to [%s] [%v]\n", from, replaced, err)
			return 1
		}
		moved = true
	}
	if moved {
		fmt.Fprintln(stdout, reportedRestoreLine("moved ["+request.Paths+"] aside to ["+replaced+"]"))
	}
	if output, code, abandoned := bounded(context.Background(), moduleToolWait, "tar", "--extract", "--gzip", "--directory", request.Target, "--numeric-owner", "--preserve-permissions", "--file", request.File); abandoned || code != 0 {
		fmt.Fprintf(stderr, "Could not extract [%s] into [%s] [%s]\n", request.File, request.Target, strings.TrimSpace(output))
		return 1
	}
	extracted := request.Paths
	if extracted == "" {
		extracted = "archive"
	}
	fmt.Fprintln(stdout, reportedRestoreLine("extracted ["+extracted+"] into ["+request.Target+"]"))
	for _, pattern := range request.Carry {
		_ = filepath.WalkDir(replaced, func(path string, entry os.DirEntry, err error) error {
			if err != nil || entry.IsDir() {
				return nil
			}
			if matched, _ := filepath.Match(pattern, entry.Name()); !matched || strings.HasSuffix(path, "-wal") || strings.HasSuffix(path, "-shm") || strings.HasSuffix(path, "-journal") {
				return nil
			}
			relative, _ := filepath.Rel(replaced, path)
			to := filepath.Join(request.Target, relative)
			if _, statErr := os.Lstat(to); statErr == nil {
				return nil
			}
			if os.MkdirAll(filepath.Dir(to), 0o755) == nil && os.Rename(path, to) == nil {
				fmt.Fprintln(stdout, reportedRestoreLine("carried ["+relative+"] back from ["+replaced+"]"))
			}
			return nil
		})
	}
	return 0
}

func runBackupModuleRestore(ctx context.Context, request BackupModuleRequest, mode string, stdout, stderr io.Writer) int {
	module, source, root, ok := resolveBackupModule(request, stderr, 1)
	if !ok {
		return 2
	}
	if request.Script == "" {
		fmt.Fprintln(stderr, "Restore needs the script holding the module hooks")
		return 2
	}
	if request.Record != "" && request.Record != string(metric.BackupStagePrimary) && request.Record != string(metric.BackupStageSecondary) {
		fmt.Fprintf(stderr, "Record takes [primary] or [secondary], not [%s]\n", request.Record)
		return 2
	}
	release, locked := lockBackupModule(stderr, module, source, request.LockPeriod)
	if !locked {
		return 1
	}
	defer release()
	roots := []string{request.Runs}
	if request.Runs == "" {
		shares, _ := filepath.Glob(filepath.Join(config.DirShare, "*", treeBackupDirectory, module))
		roots = append([]string{root}, shares...)
	}
	session := &restoreSession{ctx: ctx, request: request, mode: mode, module: module, source: source, stdout: stdout, stderr: stderr, roots: roots}
	return session.execute()
}

type restoreSession struct {
	ctx      context.Context
	request  BackupModuleRequest
	mode     string
	module   string
	source   string
	roots    []string
	chain    []restoreLink
	run      string
	hooks    moduleHooks
	defined  map[string]bool
	software string
	stdout   io.Writer
	stderr   io.Writer
	faults   int
	changed  int
}

func (s *restoreSession) report(text string) { fmt.Fprintln(s.stdout, reportedRestoreLine(text)) }

func (s *restoreSession) fault(text string) {
	s.faults++
	fmt.Fprintf(s.stderr, "❌ %s\n", text)
}

func (s *restoreSession) change(text string) {
	s.changed++
	s.report(text)
}

func (s *restoreSession) finish() int {
	fmt.Fprintln(s.stdout)
	if s.faults != 0 {
		fmt.Fprintf(s.stdout, "❌ Restore found [%d] fault(s), changed [%d]\n\n", s.faults, s.changed)
		return 1
	}
	return 0
}

func (s *restoreSession) scratchDir() string {
	return filepath.Join(filepath.Dir(s.source), "restore", s.run)
}

func (s *restoreSession) hooked(name string, input string, arguments ...string) (string, error) {
	timeout, cancel := context.WithTimeout(s.ctx, restoreHookWait)
	defer cancel()
	command := s.hooks.command(timeout, name, arguments...)
	var output bytes.Buffer
	command.Stdout, command.Stderr = &output, s.stderr
	if !restoreCaptured[name] {
		command.Stdout = io.MultiWriter(&output, s.stdout)
	}
	if input != "" {
		command.Stdin = strings.NewReader(input)
	}
	err := command.Run()
	return output.String(), err
}

func (s *restoreSession) fingerprinted(address string) ([]backupFingerprintUnit, error) {
	output, err := s.hooked(moduleHookFingerprint, "", address)
	return parseBackupFingerprint(output), err
}

func (s *restoreSession) staged() (string, error) {
	if s.defined[restoreHookStaged] {
		output, err := s.hooked(restoreHookStaged, "")
		return strings.TrimSpace(output), err
	}
	scratch := s.scratchDir()
	_ = os.RemoveAll(scratch)
	if err := os.MkdirAll(scratch, 0o755); err != nil {
		return "", err
	}
	for _, link := range s.chain {
		var name string
		var arguments []string
		switch {
		case strings.HasSuffix(link.file, ".tar.gz"):
			name, arguments = "tar", []string{"--extract", "--gzip", "--directory", scratch, "--file", link.file}
		case strings.HasSuffix(link.file, ".zip"):
			name, arguments = "unzip", []string{"-q", link.file, "-d", scratch}
		default:
			continue
		}
		if output, code, abandoned := bounded(s.ctx, moduleToolWait, name, arguments...); abandoned || code != 0 {
			return "", fmt.Errorf("could not extract [%s] [%s]", link.file, strings.TrimSpace(output))
		}
	}
	return scratch, nil
}

func (s *restoreSession) sealed(scratch string) error {
	if s.defined[restoreHookSealed] {
		_, err := s.hooked(restoreHookSealed, "", scratch)
		return err
	}
	_, _, _ = bounded(s.ctx, stageBoundedWait, "chmod", "-R", "a-w", scratch)
	return nil
}

func (s *restoreSession) tornDown(scratch string) {
	if scratch == "" {
		return
	}
	if s.defined[restoreHookTeardown] {
		_, _ = s.hooked(restoreHookTeardown, "", scratch)
		return
	}
	_, _, _ = bounded(s.ctx, stageBoundedWait, "chmod", "-R", "u+w", scratch)
	_ = os.RemoveAll(scratch)
}

func (s *restoreSession) swept() {
	parent := filepath.Dir(s.scratchDir())
	entries, _ := os.ReadDir(parent)
	for _, entry := range entries {
		stale := filepath.Join(parent, entry.Name())
		if entry.IsDir() && stale != s.scratchDir() {
			s.report("sweeping stale scratch [" + stale + "]")
			s.tornDown(stale)
		}
	}
}

func (s *restoreSession) settled(units []backupFingerprintUnit) []backupFingerprintUnit {
	if !s.defined[restoreHookSettled] {
		return units
	}
	var input strings.Builder
	for _, unit := range units {
		fmt.Fprintf(&input, "%s %d\n", unit.name, unit.count)
	}
	output, err := s.hooked(restoreHookSettled, input.String())
	if err != nil {
		return units
	}
	return parseBackupFingerprint(output)
}

func (s *restoreSession) serviceRunning() bool {
	names, _, _ := bounded(s.ctx, stageBoundedWait, "docker", "ps", "--format", "{{.Names}}")
	return slices.Contains(strings.Fields(names), s.module)
}

func (s *restoreSession) backedUp() bool {
	if s.request.NoBackup {
		s.report("backup skipped, [--no-backup] given")
		return true
	}
	script := filepath.Join(filepath.Dir(s.request.Script), scriptLeaf)
	if _, err := os.Stat(script); err != nil {
		s.report("backup skipped, no [backup.sh] beside this script")
		return true
	}
	s.report("backup taking a safety backup of the current data first ...")
	command := exec.CommandContext(s.ctx, "bash", script)
	command.Env = append(os.Environ(), "BACKUP_PRUNE=false", "BACKUP_SKIP_HOURS=0", "BACKUP_SERVICE_RESTART=false", moduleLockHeldVariable+"="+s.module)
	command.Stdout, command.Stderr = s.stdout, s.stderr
	if err := command.Run(); err != nil {
		s.fault("the safety backup failed, abandoning the restore")
		return false
	}
	s.changed++
	return true
}

func (s *restoreSession) record(verdict, detail string) {
	if s.request.Record == "" {
		return
	}
	dir, found := restoreRunDir(s.roots, s.run)
	if !found {
		return
	}
	path := backupDrillPath(dir, s.request.Record)
	if os.MkdirAll(filepath.Dir(path), 0o755) == nil {
		_ = writeAtomic(path, backupDrill{Verdict: verdict, Run: s.run, Detail: detail})
	}
}

func (s *restoreSession) execute() int {
	fmt.Fprintf(s.stdout, "\nRestore %s [%s] mode [%s] against [%s] forced [%t]\n\n", map[bool]string{true: "apply", false: "plan"}[s.request.Force], s.module, s.mode, s.source, s.request.Force)
	s.hooks = moduleHooks{script: s.request.Script}
	defined := map[string]bool{}
	declared, _ := s.hooks.command(s.ctx, "declare", "-F", restoreHookStaged, restoreHookSealed, restoreHookTeardown, restoreHookChecked, restoreHookMerged,
		restoreHookPlanned, restoreHookApplied, restoreHookSettled, moduleHookFingerprint).Output()
	for line := range strings.SplitSeq(string(declared), "\n") {
		if fields := strings.Fields(line); len(fields) > 0 {
			defined[fields[len(fields)-1]] = true
		}
	}
	s.defined = defined
	if s.request.File != "" {
		s.run = filepath.Base(filepath.Dir(s.request.File))
		s.chain = []restoreLink{{run: s.run, file: s.request.File}}
	} else {
		s.run = s.request.From
		if s.run == "" {
			s.run = restoreDefaultRun(s.roots)
		}
		if s.run == "" {
			s.fault(fmt.Sprintf("no accepted backup run under %v", s.roots))
			return s.finish()
		}
		if manifest, read := s.manifest(); read && manifest.Verdict == metric.BackupStateRegressed && !s.request.Force {
			s.fault(fmt.Sprintf("refusing to restore the regressed run [%s] without [--force], a regressed backup holds less than the one before it", s.run))
			return s.finish()
		}
		chain, err := restoreChain(s.roots, s.run)
		if err != nil {
			s.fault(err.Error())
			return s.finish()
		}
		s.chain = chain
	}
	files := make([]string, 0, len(s.chain))
	for _, link := range s.chain {
		files = append(files, link.file)
	}
	binary, _ := os.Executable()
	s.hooks.env = []string{
		"RESTORE_RUN_TIMESTAMP=" + s.run, "RESTORE_CHAIN_LIST=" + strings.Join(files, "\n"), "RESTORE_SUPERVISOR=" + binary,
		"RESTORE_SOURCE_PATH=" + s.source, "RESTORE_FORCE=" + strconv.FormatBool(s.request.Force),
		"RESTORE_KEEP_SCRATCH=" + strconv.FormatBool(s.request.KeepScratch),
	}
	last := s.chain[len(s.chain)-1].file
	kind := cmp.Or(backupArtefactKind(filepath.Base(last)), backupKindFull)
	var megabytes int64
	if info, err := os.Stat(last); err == nil {
		megabytes = info.Size() >> 20
	}
	s.report("artifact  [" + last + "]")
	s.report(fmt.Sprintf("taken     [%s] kind [%s] chain [%d]", s.run, kind, len(s.chain)))
	s.report(fmt.Sprintf("size      [%d] MB", megabytes))
	for _, link := range s.chain {
		if err := restoreIntact(link.file); err != nil {
			s.fault(fmt.Sprintf("the artifact failed its integrity check [%s] [%v]", link.file, err))
		}
	}
	if s.faults > 0 {
		if s.mode == backupRestoreModeDrill {
			s.record(metric.BackupStateFailure, "artifact failed its integrity check")
		}
		return s.finish()
	}
	s.report("integrity passed")
	fmt.Fprintln(s.stdout)
	switch s.mode {
	case backupRestoreModeDrill:
		s.drill()
	case backupRestoreModeMerge:
		s.merge()
		if !s.request.Force && s.faults == 0 {
			fmt.Fprintf(s.stdout, "\n✅ Merge plan resolved, rerun with [--force] to apply, changed [%d]\n\n", s.changed)
			return 0
		}
	default:
		if s.replace() {
			return 0
		}
	}
	if code := s.finish(); code != 0 {
		return code
	}
	verb := "applied"
	if s.mode == backupRestoreModeDrill {
		verb = "drilled"
	}
	fmt.Fprintf(s.stdout, "✅ Restore %s from [%s], changed [%d]\n\n", verb, s.run, s.changed)
	return 0
}

func (s *restoreSession) replace() bool {
	if manifest, read := s.manifest(); read && manifest.SourceSoftware != "" && !s.compatible(manifest) {
		s.report(fmt.Sprintf("warning   [%s] was taken from software [%s], now [%s], restore it under the release that took it if this fails", s.run, manifest.SourceSoftware, s.software))
	}
	if !s.request.Force {
		if s.defined[restoreHookPlanned] {
			_, _ = s.hooked(restoreHookPlanned, "")
		} else {
			s.report("would apply [" + s.chain[len(s.chain)-1].file + "]")
		}
		fmt.Fprintf(s.stdout, "\n✅ Restore plan resolved, rerun with [--force] to apply, changed [%d]\n\n", s.changed)
		return true
	}
	if !s.defined[restoreHookApplied] {
		s.fault("nothing to restore, define restore_applied in the module snippet")
		return false
	}
	if !s.backedUp() {
		return false
	}
	applied := func() {
		if _, err := s.hooked(restoreHookApplied, ""); err != nil {
			s.fault(fmt.Sprintf("the restore of [%s] failed [%v]", s.run, err))
			return
		}
		s.changed++
	}
	state, _ := s.hooked("restore_service_state", "")
	if strings.TrimSpace(state) == "running" {
		if !s.serviceRunning() {
			s.fault(fmt.Sprintf("[%s] must be running to restore, start it first", s.module))
			return false
		}
		applied()
		return false
	}
	stopped := false
	if s.serviceRunning() {
		if _, code, abandoned := bounded(s.ctx, restoreHookWait, "docker", "stop", s.module); abandoned || code != 0 {
			s.fault(fmt.Sprintf("could not stop [%s]", s.module))
			return false
		}
		stopped = true
		s.change("stopped [" + s.module + "]")
	}
	applied()
	if stopped {
		if _, code, abandoned := bounded(s.ctx, restoreHookWait, "docker", "start", s.module); abandoned || code != 0 {
			s.fault(fmt.Sprintf("could not start [%s]", s.module))
		} else {
			s.change("started [" + s.module + "]")
		}
	}
	return false
}

func reportedRestoreLine(text string) string {
	word, rest, _ := strings.Cut(text, " ")
	if restoreLabels[word] {
		return fmt.Sprintf("   %-10s%s", word, strings.TrimLeft(rest, " "))
	}
	return fmt.Sprintf("   %-10s%s", "", text)
}

var restoreCaptured = map[string]bool{restoreHookStaged: true, restoreHookSettled: true, moduleHookFingerprint: true, "restore_service_state": true, "restore_live_address": true}

var restoreLabels = map[string]bool{
	"artifact": true, "taken": true, "size": true, "service": true, "integrity": true, "chain": true, "drill": true, "merge": true, "plan": true,
	"staging": true, "counting": true, "sealing": true, "verify": true, "short": true, "backup": true, "would": true, "extracted": true, "moved": true,
	"carried": true, "stopped": true, "started": true, "unzipped": true, "loaded": true, "restored": true, "check": true,
}

const (
	backupRestoreModeReplace = "replace"
	backupRestoreModeDrill   = "drill"
	backupRestoreModeMerge   = "merge"

	restoreHookStaged   = "restore_staged"
	restoreHookSealed   = "restore_sealed"
	restoreHookTeardown = "restore_teardown"
	restoreHookChecked  = "restore_checked"
	restoreHookMerged   = "restore_merged"
	restoreHookPlanned  = "restore_planned"
	restoreHookApplied  = "restore_applied"
	restoreHookSettled  = "restore_settled"
	restoreHookWait     = 2 * time.Hour
)
