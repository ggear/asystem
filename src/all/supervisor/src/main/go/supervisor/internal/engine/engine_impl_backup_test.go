package engine

import (
	"path/filepath"
	"testing"

	"supervisor/internal/config"
	"supervisor/internal/metric"
	"supervisor/internal/probe"
)

var (
	_ = BackupRequest{}
	_ = BackupCommandStart
	_ = metric.BackupStagePrimary
)

func TestEngineImplBackup_EveryCommandInRangeIsNamed(t *testing.T) {
	named := map[string]BackupCommand{}
	for command := BackupCommandStart; command <= BackupCommandAuto; command++ {
		word := command.String()
		if word == "" || word == BackupCommand(-1).String() {
			t.Errorf("command [%d] renders as [%s], so a command was added without a verb to name it", command, word)
		}
		if first, taken := named[word]; taken {
			t.Errorf("commands [%d] and [%d] both render as [%s]", first, command, word)
		}
		named[word] = command
	}
	if len(named) != int(BackupCommandAuto-BackupCommandStart)+1 {
		t.Errorf("named %d commands, want one name per command in range", len(named))
	}
}

func TestEngineImplBackup_StageOfTakesTheThreeStagesAndRefusesAnythingElse(t *testing.T) {
	tests := []struct {
		name          string
		text          string
		expected      metric.BackupStage
		expectedError bool
	}{
		{name: "primary", text: "primary", expected: metric.BackupStagePrimary},
		{name: "secondary_in_any_case", text: "SECONDARY", expected: metric.BackupStageSecondary},
		{name: "tertiary", text: "tertiary", expected: metric.BackupStageTertiary},
		{name: "a_stage_that_does_not_exist", text: "quaternary", expectedError: true},
		{name: "no_stage_at_all", text: "", expectedError: true},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			stage, err := BackupStageOf(testCase.text)
			if (err != nil) != testCase.expectedError {
				t.Fatalf("BackupStageOf(%q) error = %v, expectedError %v", testCase.text, err, testCase.expectedError)
			}
			if stage != testCase.expected {
				t.Errorf("BackupStageOf(%q) = %q, want %q", testCase.text, stage, testCase.expected)
			}
		})
	}
}

func TestEngineImplBackup_PreparedRefusesAtTheBoundaryRatherThanInTheRun(t *testing.T) {
	tests := []struct {
		name          string
		request       BackupRequest
		expectedError bool
	}{
		{name: "a_hand_start", request: BackupRequest{Command: BackupCommandStart, Trigger: metric.BackupTriggerManual}},
		{name: "a_scrub_against_a_stage_that_cannot_scrub",
			request:       BackupRequest{Command: BackupCommandStart, Trigger: metric.BackupTriggerManual, Stage: metric.BackupStagePrimary, Scrub: true},
			expectedError: true},
		{name: "an_auto_word_that_is_neither_on_nor_off",
			request:       BackupRequest{Command: BackupCommandAuto, Trigger: metric.BackupTriggerManual, Argument: "maybe"},
			expectedError: true},
		{name: "a_trigger_that_is_neither",
			request:       BackupRequest{Command: BackupCommandList, Trigger: "cron"},
			expectedError: true},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			prepared, err := BackupPrepared(testCase.request)
			if (err != nil) != testCase.expectedError {
				t.Fatalf("BackupPrepared() error = %v, expectedError %v", err, testCase.expectedError)
			}
			if err != nil {
				return
			}
			expected, _ := probe.BackupPrepared(testCase.request)
			if prepared.Command != expected.Command || prepared.Stage != expected.Stage {
				t.Errorf("BackupPrepared() = %+v, want what probe prepares", prepared)
			}
		})
	}
}

func TestEngineImplBackup_StageLogNamesThePathTheRunWillWrite(t *testing.T) {
	root := t.TempDir()
	t.Setenv(config.BackupHomeEnvVar, root)
	request, err := BackupPrepared(BackupRequest{
		Command: BackupCommandStart, Trigger: metric.BackupTriggerManual,
		Argument: "2026-09-22_01-00-35", Stage: metric.BackupStageSecondary,
	})
	if err != nil {
		t.Fatalf("BackupPrepared() error = %v", err)
	}
	expected := filepath.Join(root, "supervisor", "backup", "2026-09-22_01-00-35", "stage", "secondary", "output.log")
	if got := BackupStageLog(request); got != expected {
		t.Errorf("BackupStageLog() = %q, want %q", got, expected)
	}
}

func TestEngineImplBackup_RunBackupReachesTheRunItself(t *testing.T) {
	tests := []struct {
		name          string
		command       BackupCommand
		expectedError bool
	}{
		{name: "list_reports_no_runs_without_failing", command: BackupCommandList},
		{name: "stop_has_no_run_to_stop", command: BackupCommandStop, expectedError: true},
		{name: "tail_has_no_run_to_follow", command: BackupCommandTail, expectedError: true},
		{name: "a_command_out_of_range_is_refused", command: BackupCommand(99), expectedError: true},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			t.Setenv(config.BackupHomeEnvVar, t.TempDir())
			err := RunBackup(BackupRequest{Command: testCase.command, Trigger: metric.BackupTriggerManual, Config: "config.json"})
			if (err != nil) != testCase.expectedError {
				t.Errorf("RunBackup(%s) error = %v, expectedError %v", testCase.command, err, testCase.expectedError)
			}
		})
	}
}
