package scribe

import (
	"bytes"
	"log/slog"
	"os"
	"path/filepath"
	"testing"
	"time"
)

func TestScribeBackup_RenderPadsLevelAndStageIntoFixedColumns(t *testing.T) {
	timestamp := time.Date(2026, 9, 22, 10, 20, 30, 0, time.UTC)
	tests := []struct {
		name     string
		level    slog.Level
		subject  string
		detail   string
		expected string
	}{
		{name: "info_with_stage", level: slog.LevelInfo, subject: "stage/primary",
			detail: "backup run over [3] stages", expected: "[INFO primary   10:20:30] backup run over [3] stages"},
		{name: "warn_with_stage", level: slog.LevelWarn, subject: "stage/tertiary",
			detail: "share [plex] not mounted", expected: "[WARN tertiary  10:20:30] share [plex] not mounted"},
		{name: "error_renders_as_errs", level: slog.LevelError, subject: "stage/secondary",
			detail: "promotion failed", expected: "[ERRS secondary 10:20:30] promotion failed"},
		{name: "blank_stage_for_whole_run", level: slog.LevelInfo, subject: "",
			detail: "run [2026-09-22_01-00-00] started", expected: "[INFO           10:20:30] run [2026-09-22_01-00-00] started"},
		{name: "debug_keeps_its_own_word", level: slog.LevelDebug, subject: "stage/primary",
			detail: "polled", expected: "[DEBG primary   10:20:30] polled"},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			line := LogLine{Time: timestamp, Level: testCase.level, Subject: testCase.subject, Detail: testCase.detail}
			if got := renderBackup(line); got != testCase.expected {
				t.Errorf("renderBackup() = %q, want %q", got, testCase.expected)
			}
		})
	}
}

func TestScribeBackup_EveryLevelFitsItsColumn(t *testing.T) {
	timestamp := time.Date(2026, 9, 22, 10, 20, 30, 0, time.UTC)
	for _, level := range []slog.Level{slog.LevelDebug, slog.LevelInfo, slog.LevelWarn, slog.LevelError} {
		line := LogLine{Time: timestamp, Level: level, Subject: "stage/primary", Detail: "x"}
		if got := renderBackup(line); len(got) != len("[INFO primary   10:20:30] x") {
			t.Errorf("renderBackup(%v) = %q, want every level to render the same width", level, got)
		}
	}
}

func TestScribeBackup_SubjectStageIsNamespacedAndStrippedForTheColumn(t *testing.T) {
	if got := SubjectStage("primary").String(); got != "stage/primary" {
		t.Errorf("SubjectStage().String() = %q, want %q", got, "stage/primary")
	}
	if got := SubjectStage("").String(); got != SubjectNone.String() {
		t.Errorf("SubjectStage().String() = %q, want the none subject against an unstaged line", got)
	}
	line := LogLine{Time: time.Now(), Level: slog.LevelInfo, Subject: SubjectStage("primary").String(), Detail: "x"}
	if got := renderBackup(line); got[6:13] != "primary" {
		t.Errorf("renderBackup() stage column = %q, want the bare stage name", got[6:13])
	}
}

func TestScribeBackup_EnableBackupAndFileWritesTheStageLogAndStdout(t *testing.T) {
	stageLog, stdout, stderr := enableBackupFixture(t, false)
	Log(SourceBackup, SubjectStage("primary"), ActionStart).Infof("started", time.Now(), "run [%s]", "2026-09-22_01-00-00")
	Log(SourceBackup, SubjectStage("primary"), ActionStop).Errorf("faulting", time.Now(), "run [%s] failed", "2026-09-22_01-00-00")

	data, err := os.ReadFile(stageLog)
	if err != nil {
		t.Fatalf("stage log not written: %v", err)
	}
	if !bytes.Contains(data, []byte("run [2026-09-22_01-00-00]")) {
		t.Errorf("stage log = %q, want it to carry the logged detail", data)
	}
	if stdout.Len() == 0 {
		t.Errorf("stdout is empty, want the info line copied to it")
	}
	if stderr.Len() == 0 {
		t.Errorf("stderr is empty, want the error line copied to it")
	}
}

func TestScribeBackup_QuietDropsStdoutAndStderrNotTheFile(t *testing.T) {
	stageLog, stdout, stderr := enableBackupFixture(t, true)
	Log(SourceBackup, SubjectStage("primary"), ActionStart).Infof("started", time.Now(), "quiet run")
	Log(SourceBackup, SubjectStage("primary"), ActionStop).Errorf("faulting", time.Now(), "quiet fault")

	data, err := os.ReadFile(stageLog)
	if err != nil {
		t.Fatalf("stage log not written: %v", err)
	}
	if !bytes.Contains(data, []byte("quiet run")) || !bytes.Contains(data, []byte("quiet fault")) {
		t.Errorf("stage log = %q, want both lines under --quiet", data)
	}
	if stdout.Len() != 0 {
		t.Errorf("stdout = %q, want nothing under --quiet", stdout.String())
	}
	if stderr.Len() != 0 {
		t.Errorf("stderr = %q, want nothing under --quiet", stderr.String())
	}
}

func enableBackupFixture(t *testing.T, quiet bool) (stageLog string, stdout, stderr *bytes.Buffer) {
	t.Helper()
	t.Cleanup(func() { Disable() })
	dir := t.TempDir()
	t.Setenv("HOME", dir)
	stageLog = filepath.Join(dir, "stage", "output.log")
	closer, err := EnableBackupAndFile(slog.LevelInfo, "backup", "1.0.0", stageLog, quiet, 1, 1, 1)
	if err != nil {
		t.Fatalf("EnableBackupAndFile() error = %v", err)
	}
	t.Cleanup(func() { _ = closer.Close() })
	stdout, stderr = &bytes.Buffer{}, &bytes.Buffer{}
	scribeLoggerMu.Lock()
	defer scribeLoggerMu.Unlock()
	multi, ok := scribeLoggerInstance.Handler().(*multiHandler)
	if !ok {
		t.Fatalf("installed handler = %T, want a multiHandler carrying the backup sinks", scribeLoggerInstance.Handler())
	}
	retargeted := 0
	for _, handler := range multi.handlers {
		if backup, isBackup := handler.(*backupHandler); isBackup && backup.writer == nil {
			backup.stdout, backup.stderr = stdout, stderr
			retargeted++
		}
	}
	if retargeted != 1 && !quiet {
		t.Fatalf("retargeted %d stdout sinks, want 1", retargeted)
	}
	return stageLog, stdout, stderr
}
