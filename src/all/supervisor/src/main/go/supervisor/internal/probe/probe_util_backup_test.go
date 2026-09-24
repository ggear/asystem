package probe

import (
	"os"
	"path/filepath"
	"regexp"
	"strconv"
	"strings"
	"syscall"
	"testing"
	"time"

	"supervisor/internal/config"
	"supervisor/internal/metric"
	"supervisor/internal/scribe"
)

func TestProbeUtilBackup_ExpiryPrefersTheFlagThenTheEnvironmentThenTheConfig(t *testing.T) {
	started := time.Date(2026, 9, 22, 1, 0, 0, 0, time.Local)
	tests := []struct {
		name        string
		configHours int
		environment string
		timeout     time.Duration
		expected    time.Duration
		expectedNil bool
	}{
		{name: "the_configured_timeout_alone", configHours: 3, expected: 3 * time.Hour},
		{name: "the_environment_overrides_the_config", configHours: 3, environment: "10", expected: 10 * time.Hour},
		{name: "the_flag_overrides_both", configHours: 3, environment: "10", timeout: 90 * time.Minute, expected: 90 * time.Minute},
		{name: "an_unparseable_environment_is_ignored", configHours: 3, environment: "soon", expected: 3 * time.Hour},
		{name: "a_zero_environment_is_ignored", configHours: 3, environment: "0", expected: 3 * time.Hour},
		{name: "nothing_declared_leaves_no_deadline", expectedNil: true},
		{name: "the_environment_alone_still_bounds_the_run", environment: "6", expected: 6 * time.Hour},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			dir := t.TempDir()
			path := filepath.Join(dir, "config.json")
			body := `{"asystem":{"host":"testhost","backup":{"timeout_hours":` + strconv.Itoa(testCase.configHours) + `}}}`
			if err := os.WriteFile(path, []byte(body), 0o644); err != nil {
				t.Fatalf("write config: %v", err)
			}
			t.Setenv(backupTimeoutVariable, testCase.environment)
			expires := backupExpiry(path, started, testCase.timeout)
			if testCase.expectedNil {
				if !expires.IsZero() {
					t.Errorf("backupExpiry() = %s, want no deadline", expires)
				}
				return
			}
			if got := expires.Sub(started); got != testCase.expected {
				t.Errorf("backupExpiry() = started plus %s, want %s", got, testCase.expected)
			}
		})
	}
}

func TestProbeUtilBackup_PruneRunsKeepsTheNewestAndNothingElse(t *testing.T) {
	root := t.TempDir()
	var runs []string
	for index := range backupRunsKept + 5 {
		run := time.Date(2026, 1, 1, 0, 0, 0, 0, time.Local).AddDate(0, 0, index).Format(backupTimestampFormat)
		runs = append(runs, run)
		if err := os.MkdirAll(backupRunPath(root, run), 0o755); err != nil {
			t.Fatalf("mkdir run: %v", err)
		}
	}
	if err := os.MkdirAll(filepath.Join(root, "not-a-run"), 0o755); err != nil {
		t.Fatalf("mkdir stray: %v", err)
	}
	pruneRuns(root, scribe.SubjectNone, time.Now())
	kept := backupRuns(root)
	if len(kept) != backupRunsKept {
		t.Fatalf("kept %d runs, want %d", len(kept), backupRunsKept)
	}
	if kept[len(kept)-1] != runs[len(runs)-1] || kept[0] != runs[len(runs)-backupRunsKept] {
		t.Errorf("kept %s to %s, want the newest %d ending at %s", kept[0], kept[len(kept)-1], backupRunsKept, runs[len(runs)-1])
	}
	if _, err := os.Stat(filepath.Join(root, "not-a-run")); err != nil {
		t.Errorf("a directory that is not a run was pruned: %v", err)
	}
}

func TestProbeUtilBackup_PruneRunsLeavesFewerRunsThanTheWindowAlone(t *testing.T) {
	root := t.TempDir()
	for index := range 3 {
		run := time.Date(2026, 1, 1, 0, 0, 0, 0, time.Local).AddDate(0, 0, index).Format(backupTimestampFormat)
		if err := os.MkdirAll(backupRunPath(root, run), 0o755); err != nil {
			t.Fatalf("mkdir run: %v", err)
		}
	}
	pruneRuns(root, scribe.SubjectNone, time.Now())
	if kept := backupRuns(root); len(kept) != 3 {
		t.Errorf("kept %d runs, want all 3", len(kept))
	}
}

func TestProbeUtilBackup_TheModuleContractIsSpelledInTheGeneratedBackupScript(t *testing.T) {
	path, err := filepath.Abs(filepath.Join("..", "..", "..", "..", "..", "..", "..", "_",
		"src", "build", "python", "asystem", "container.py"))
	if err != nil {
		t.Fatalf("resolve container.py: %v", err)
	}
	source, err := os.ReadFile(path)
	if err != nil {
		t.Fatalf("read the shared build library at %s: %v", path, err)
	}
	generated := regexp.MustCompile(`(?s)def write_container_backup\(.*?\ndef `).Find(source)
	if generated == nil {
		t.Fatalf("found no write_container_backup in %s, the parse has rotted", path)
	}
	for _, token := range []string{moduleSkipHoursVariable, moduleRestartVariable, backupTimeoutVariable, moduleBackupPruneFlag} {
		if !strings.Contains(string(generated), token) {
			t.Errorf("the generated module backup.sh names no [%s], which the primary stage passes it", token)
		}
	}
}

func TestProbeUtilBackup_PreparedRefusesARequestTheRunCannotHonour(t *testing.T) {
	tests := []struct {
		name          string
		request       BackupRequest
		expectedError bool
	}{
		{name: "a_scheduled_start", request: BackupRequest{Command: BackupCommandStart, Trigger: metric.BackupTriggerSystem}},
		{name: "a_hand_start_of_one_stage", request: BackupRequest{Command: BackupCommandStart, Trigger: metric.BackupTriggerManual, Stage: metric.BackupStageSecondary}},
		{name: "a_scrub_against_the_tertiary_stage", request: BackupRequest{Command: BackupCommandStart, Trigger: metric.BackupTriggerManual, Stage: metric.BackupStageTertiary, Scrub: true}},
		{name: "a_scrub_against_a_whole_run", request: BackupRequest{Command: BackupCommandStart, Trigger: metric.BackupTriggerManual, Scrub: true}},
		{name: "a_scrub_against_a_stage_that_cannot_scrub", request: BackupRequest{Command: BackupCommandStart, Trigger: metric.BackupTriggerManual, Stage: metric.BackupStagePrimary, Scrub: true},
			expectedError: true},
		{name: "a_stage_against_a_verb_that_runs_none", request: BackupRequest{Command: BackupCommandList, Trigger: metric.BackupTriggerManual, Stage: metric.BackupStagePrimary},
			expectedError: true},
		{name: "a_stage_that_is_not_one_of_the_three", request: BackupRequest{Command: BackupCommandStart, Trigger: metric.BackupTriggerManual, Stage: "quaternary"},
			expectedError: true},
		{name: "a_command_out_of_range", request: BackupRequest{Command: BackupCommand(99), Trigger: metric.BackupTriggerManual},
			expectedError: true},
		{name: "a_trigger_that_is_neither", request: BackupRequest{Command: BackupCommandList, Trigger: "cron"},
			expectedError: true},
		{name: "auto_read_with_no_word", request: BackupRequest{Command: BackupCommandAuto, Trigger: metric.BackupTriggerManual}},
		{name: "auto_turned_on", request: BackupRequest{Command: BackupCommandAuto, Trigger: metric.BackupTriggerManual, Argument: backupAutoOn}},
		{name: "auto_turned_off", request: BackupRequest{Command: BackupCommandAuto, Trigger: metric.BackupTriggerManual, Argument: backupAutoOff}},
		{name: "auto_given_a_word_it_cannot_act_on", request: BackupRequest{Command: BackupCommandAuto, Trigger: metric.BackupTriggerManual, Argument: "maybe"},
			expectedError: true},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			_, err := BackupPrepared(testCase.request)
			if (err != nil) != testCase.expectedError {
				t.Errorf("BackupPrepared() error = %v, expectedError %v", err, testCase.expectedError)
			}
		})
	}
}

func TestProbeUtilBackup_PreparedResolvesTheArgumentIntoTheRunIdOnce(t *testing.T) {
	named := "2026-09-22_01-00-35"
	tests := []struct {
		name     string
		command  BackupCommand
		argument string
		expected string
		minted   bool
	}{
		{name: "start_takes_the_run_it_was_given", command: BackupCommandStart, argument: named, expected: named},
		{name: "start_mints_one_when_given_none", command: BackupCommandStart, minted: true},
		{name: "stop_takes_the_run_it_was_given", command: BackupCommandStop, argument: named, expected: named},
		{name: "stop_leaves_the_newest_to_be_resolved", command: BackupCommandStop},
		{name: "tail_takes_the_run_it_was_given", command: BackupCommandTail, argument: named, expected: named},
		{name: "list_names_no_run_at_all", command: BackupCommandList, argument: named},
		{name: "auto_names_no_run_at_all", command: BackupCommandAuto, argument: backupAutoOn},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			request, err := BackupPrepared(BackupRequest{Command: testCase.command, Trigger: metric.BackupTriggerManual, Argument: testCase.argument})
			if err != nil {
				t.Fatalf("BackupPrepared() error = %v", err)
			}
			if testCase.minted {
				if !treeRunPattern.MatchString(request.RunID) {
					t.Errorf("RunID = %q, want a minted run stamp", request.RunID)
				}
				return
			}
			if request.RunID != testCase.expected {
				t.Errorf("RunID = %q, want %q", request.RunID, testCase.expected)
			}
		})
	}
}

func TestProbeUtilBackup_StageLogSitsUnderTheRunItNames(t *testing.T) {
	t.Setenv(config.BackupHomeEnvVar, "/tmp/home")
	request := BackupRequest{Command: BackupCommandStart, Trigger: metric.BackupTriggerManual, RunID: "2026-09-22_01-00-35", Stage: metric.BackupStageTertiary}
	expected := filepath.Join("/tmp/home", treeModule, treeBackupDirectory, "2026-09-22_01-00-35", treeStageDirectory, "tertiary", treeLogLeaf)
	if got := BackupStageLog(request); got != expected {
		t.Errorf("BackupStageLog() = %q, want %q", got, expected)
	}
}

func TestProbeUtilBackup_DispatchesEachVerbAgainstAnEmptyRoot(t *testing.T) {
	tests := []struct {
		name          string
		command       BackupCommand
		expectedError bool
	}{
		{name: "list_reports_no_runs_without_failing", command: BackupCommandList},
		{name: "stop_has_no_run_to_stop", command: BackupCommandStop, expectedError: true},
		{name: "tail_has_no_run_to_follow", command: BackupCommandTail, expectedError: true},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			t.Setenv(config.BackupHomeEnvVar, t.TempDir())
			err := Backup(t.Context(), BackupRequest{Command: testCase.command, Trigger: metric.BackupTriggerManual, Config: "config.json"})
			if (err != nil) != testCase.expectedError {
				t.Errorf("Backup(%s) error = %v, expectedError %v", testCase.command, err, testCase.expectedError)
			}
		})
	}
}

func TestProbeUtilBackup_CommandNamesItself(t *testing.T) {
	if got := BackupCommandAuto.String(); got != "auto" {
		t.Errorf("BackupCommandAuto.String() = %q, want auto", got)
	}
	if got := BackupCommand(99).String(); got != backupCommandUnnamed {
		t.Errorf("BackupCommand(99).String() = %q, want %q", got, backupCommandUnnamed)
	}
}

func TestProbeUtilBackup_TheShippedConfigDeclaresAThinningWindow(t *testing.T) {
	path, err := filepath.Abs(filepath.Join("..", "..", "..", "..", "resources", "image", "config.json"))
	if err != nil {
		t.Fatalf("resolve config.json: %v", err)
	}
	loaded := config.Load(path)
	if loaded == nil {
		t.Fatalf("read the shipped config at %s: got nil", path)
	}
	daily, weekly, monthly := loaded.BackupKeepDaily(), loaded.BackupKeepWeekly(), loaded.BackupKeepMonthly()
	if daily+weekly+monthly <= 0 {
		t.Errorf("the shipped config declares keep_daily [%d] keep_weekly [%d] keep_monthly [%d], so gfsThin would prune nothing at all",
			daily, weekly, monthly)
	}
}

func TestProbeUtilBackup_ASecondRunIsRefusedWhileTheLockIsHeld(t *testing.T) {
	home := t.TempDir()
	t.Setenv(config.BackupHomeEnvVar, home)
	root := backupRunRoot()
	if err := os.MkdirAll(root, 0o755); err != nil {
		t.Fatalf("mkdir root: %v", err)
	}
	held, err := os.OpenFile(lockPath(root), os.O_CREATE|os.O_RDWR, 0o644)
	if err != nil {
		t.Fatalf("open lock: %v", err)
	}
	defer func() { _ = held.Close() }()
	if err := syscall.Flock(int(held.Fd()), syscall.LOCK_EX|syscall.LOCK_NB); err != nil {
		t.Fatalf("hold lock: %v", err)
	}
	defer func() { _ = syscall.Flock(int(held.Fd()), syscall.LOCK_UN) }()

	configPath := filepath.Join(home, "config.json")
	if err := os.WriteFile(configPath, []byte(`{"asystem":{"host":"testhost"}}`), 0o644); err != nil {
		t.Fatalf("write config: %v", err)
	}
	err = Backup(t.Context(), BackupRequest{Command: BackupCommandStart, Trigger: metric.BackupTriggerManual,
		Config: configPath, RunID: "2026-09-22_01-00-00"})
	if err == nil || !strings.Contains(err.Error(), "refusing to start") {
		t.Errorf("Backup() error = %v, want a refusal naming the held lock", err)
	}
	if runs := backupRuns(root); len(runs) != 0 {
		t.Errorf("backupRuns() = %v, want a refused run to mint no directory", runs)
	}
}
