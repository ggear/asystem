package probe

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"supervisor/internal/config"
	"supervisor/internal/metric"
	"supervisor/internal/testutil"
	"sync"
	"testing"
	"time"

	mqtt "github.com/eclipse/paho.mqtt.golang"
)

func writeBackupRun(t *testing.T, root, timestamp string, host *backupSummary, tertiary *backupSummary, services map[string]bool) {
	t.Helper()
	runPath := filepath.Join(root, timestamp)
	if err := os.MkdirAll(runPath, 0o755); err != nil {
		t.Fatal(err)
	}
	write := func(path string, document backupSummary) {
		data, _ := json.MarshalIndent(document, "", "  ")
		if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
			t.Fatal(err)
		}
		if err := os.WriteFile(path, data, 0o644); err != nil {
			t.Fatal(err)
		}
	}
	if host != nil {
		write(filepath.Join(runPath, "status.json"), *host)
	}
	if tertiary != nil {
		write(stageStatusPath(runPath, "tertiary"), *tertiary)
	}
	for service, success := range services {
		write(filepath.Join(runPath, "stage", "primary", "service", service, "status.json"),
			backupSummary{RunID: timestamp, SuccessBool: success})
	}
}

func writeBackupStage(t *testing.T, root, timestamp string, stage metric.BackupStage, document backupSummary) {
	t.Helper()
	path := stageStatusPath(filepath.Join(root, timestamp), stage)
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		t.Fatal(err)
	}
	data, _ := json.MarshalIndent(document, "", "  ")
	if err := os.WriteFile(path, data, 0o644); err != nil {
		t.Fatal(err)
	}
}

func writeBackupScrub(t *testing.T, root, timestamp, state string) {
	t.Helper()
	path := filepath.Join(root, timestamp, "stage", string(metric.BackupStageTertiary), "scrub.json")
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		t.Fatal(err)
	}
	data, _ := json.MarshalIndent(backupSummary{State: state}, "", "  ")
	if err := os.WriteFile(path, data, 0o644); err != nil {
		t.Fatal(err)
	}
}

func TestProbeImplBackup_RunSummaryNamesTheFirstStageThatBroke(t *testing.T) {
	tests := []struct {
		name        string
		stages      map[metric.BackupStage]string
		scrub       string
		wantState   string
		wantSuccess bool
		wantFailed  int
		wantHalted  int
	}{
		{"every stage and a skipped scrub is success", map[metric.BackupStage]string{
			metric.BackupStagePrimary: metric.BackupStateSuccess, metric.BackupStageSecondary: metric.BackupStateSuccess,
			metric.BackupStageTertiary: metric.BackupStateSuccess}, metric.BackupStateSkipped, metric.BackupStateSuccess, true, 0, 0},
		{"secondary timed out ahead of a failed tertiary", map[metric.BackupStage]string{
			metric.BackupStagePrimary: metric.BackupStateSuccess, metric.BackupStageSecondary: metric.BackupStateTimeout,
			metric.BackupStageTertiary: metric.BackupStateFailure}, "", metric.BackupStateTimeout, false, 1, 1},
		{"a failed scrub still fails a fully successful run", map[metric.BackupStage]string{
			metric.BackupStagePrimary: metric.BackupStateSuccess, metric.BackupStageSecondary: metric.BackupStateSuccess,
			metric.BackupStageTertiary: metric.BackupStateSuccess}, metric.BackupStateFailure, metric.BackupStateFailure, false, 0, 0},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			root := t.TempDir()
			timestamp := time.Now().Format(backupTimestampFormat)
			for _, stage := range backupStages {
				state, ok := tt.stages[stage]
				if !ok {
					continue
				}
				writeBackupStage(t, root, timestamp, stage, backupSummary{State: state, SuccessBool: state == metric.BackupStateSuccess})
			}
			if tt.scrub != "" {
				writeBackupScrub(t, root, timestamp, tt.scrub)
			}
			document := finishRun(root, timestamp, time.Now())
			if document.State != tt.wantState || document.SuccessBool != tt.wantSuccess {
				t.Errorf("got (%s,%v) want (%s,%v)", document.State, document.SuccessBool, tt.wantState, tt.wantSuccess)
			}
			if document.StagesFailed != tt.wantFailed || document.StagesHalted != tt.wantHalted {
				t.Errorf("stages: got (failed %d, halted %d) want (failed %d, halted %d)",
					document.StagesFailed, document.StagesHalted, tt.wantFailed, tt.wantHalted)
			}
		})
	}
}

func TestProbeImplBackup_FailedBackups(t *testing.T) {
	fresh := time.Now().Format(backupTimestampFormat)
	stale := time.Now().Add(-40 * time.Hour).Format(backupTimestampFormat)
	abandoned := time.Now().Add(-6 * time.Hour).Format(backupTimestampFormat)
	rolled := time.Now().Add(-7 * time.Hour).Format(backupTimestampFormat)
	tests := []struct {
		name          string
		setup         func(root string)
		wantValue     int8
		wantInert     bool
		expectedError bool
	}{
		{"run in flight is inert until it writes its roll-up", func(root string) {
			writeBackupStage(t, root, fresh, "primary", backupSummary{State: "complete"})
		}, 0, true, false},
		{"run abandoned beyond the ceiling with no roll-up ever cannot be measured", func(root string) {
			writeBackupStage(t, root, abandoned, "primary", backupSummary{State: "running"})
		}, 0, false, true},
		{"no runs at all cannot be measured", func(string) {}, 0, false, true},
		{"an abandoned run on a host that has rolled up before reads fully failed", func(root string) {
			writeBackupRun(t, root, stale, &backupSummary{StagesRun: 3, StagesFailed: 0}, nil, nil)
			writeBackupStage(t, root, abandoned, "primary", backupSummary{State: "running"})
		}, 100, false, false},
		{"stale run reads fully failed", func(root string) {
			writeBackupRun(t, root, stale, &backupSummary{StagesRun: 3, StagesFailed: 0}, nil, nil)
		}, 100, false, false},
		{"clean current run reads zero", func(root string) {
			writeBackupRun(t, root, fresh, &backupSummary{StagesRun: 3, StagesFailed: 0}, nil, nil)
		}, 0, false, false},
		{"one failed stage of three", func(root string) {
			writeBackupRun(t, root, fresh, &backupSummary{StagesRun: 3, StagesFailed: 1}, nil, nil)
		}, 33, false, false},
		{"failed secondary on edge host", func(root string) {
			writeBackupRun(t, root, fresh, &backupSummary{StagesRun: 2, StagesFailed: 1}, nil, nil)
		}, 50, false, false},
		{"a hand stage newer than the last roll-up does not mask it", func(root string) {
			writeBackupRun(t, root, rolled, &backupSummary{StagesRun: 3, StagesFailed: 0}, nil, nil)
			writeBackupStage(t, root, abandoned, "secondary", backupSummary{State: "complete"})
		}, 0, false, false},
		{"a hand stage newer than a stale roll-up still reads fully failed", func(root string) {
			writeBackupRun(t, root, stale, &backupSummary{StagesRun: 3, StagesFailed: 0}, nil, nil)
			writeBackupStage(t, root, abandoned, "secondary", backupSummary{State: "complete"})
		}, 100, false, false},
		{"a stage in flight reports the last roll-up rather than hiding it", func(root string) {
			writeBackupRun(t, root, rolled, &backupSummary{StagesRun: 3, StagesFailed: 0}, nil, nil)
			writeBackupStage(t, root, fresh, "secondary", backupSummary{State: "running"})
		}, 0, false, false},
		{"a stage in flight cannot mask a roll-up that failed", func(root string) {
			writeBackupRun(t, root, rolled, &backupSummary{StagesRun: 3, StagesFailed: 3}, nil, nil)
			writeBackupStage(t, root, fresh, "secondary", backupSummary{State: "running"})
		}, 100, false, false},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			root := t.TempDir()
			tt.setup(root)
			p := &backupProbe{root: root}
			value, derived, err := p.failedBackupStages()
			if (err != nil) != tt.expectedError {
				t.Fatalf("err: got %v want error %v", err, tt.expectedError)
			}
			if value != tt.wantValue {
				t.Errorf("value: got %d want %d", value, tt.wantValue)
			}
			if derived.inert != tt.wantInert {
				t.Errorf("inert: got %v want %v", derived.inert, tt.wantInert)
			}
		})
	}
}

func TestProbeImplBackup_UsedBackupSpace(t *testing.T) {
	fresh := time.Now().Format(backupTimestampFormat)
	tests := []struct {
		name          string
		serverHost    bool
		setup         func(root string)
		wantValue     int8
		wantInert     bool
		expectedError bool
	}{
		{"no tertiary document on a server errors", true, func(root string) {
			writeBackupRun(t, root, fresh, &backupSummary{StagesRun: 2}, nil, nil)
		}, 0, false, true},
		{"no tertiary document on an edge host is inert", false, func(root string) {
			writeBackupRun(t, root, fresh, &backupSummary{StagesRun: 2}, nil, nil)
		}, 0, true, false},
		{"reads tertiary disk usage", true, func(root string) {
			writeBackupRun(t, root, fresh, &backupSummary{StagesRun: 3}, &backupSummary{DiskUsagePerc: 72}, nil)
		}, 72, false, false},
		{"run in flight on a server is inert", true, func(root string) {
			writeBackupStage(t, root, fresh, "primary", backupSummary{State: "complete"})
		}, 0, true, false},
		{"tertiary still running is inert rather than zero", true, func(root string) {
			writeBackupStage(t, root, fresh, "tertiary", backupSummary{State: "running", DiskUsagePerc: 0})
		}, 0, true, false},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			root := t.TempDir()
			tt.setup(root)
			p := &backupProbe{root: root, serverHost: tt.serverHost}
			value, derived, err := p.usedBackupSpace()
			if (err != nil) != tt.expectedError {
				t.Fatalf("err: got %v want error %v", err, tt.expectedError)
			}
			if value != tt.wantValue {
				t.Errorf("value: got %d want %d", value, tt.wantValue)
			}
			if derived.inert != tt.wantInert {
				t.Errorf("inert: got %v want %v", derived.inert, tt.wantInert)
			}
		})
	}
}

func TestProbeImplBackup_ServiceSuccess(t *testing.T) {
	root := t.TempDir()
	fresh := time.Now().Format(backupTimestampFormat)
	writeBackupRun(t, root, fresh, &backupSummary{StagesRun: 3}, nil, map[string]bool{"postgres": true, "plex": false})
	p := &backupProbe{root: root}
	tests := []struct {
		service   string
		wantValue bool
		wantFound bool
	}{
		{"postgres", true, true},
		{"plex", false, true},
		{"mariadb", false, false},
	}
	for _, tt := range tests {
		t.Run(tt.service, func(t *testing.T) {
			value, found, run := p.serviceSuccess(tt.service)
			if value != tt.wantValue || found != tt.wantFound {
				t.Errorf("got (%v,%v) want (%v,%v)", value, found, tt.wantValue, tt.wantFound)
			}
			if run != fresh {
				t.Errorf("run: got %q want %q", run, fresh)
			}
		})
	}
}

func TestProbeImplBackup_ServiceSuccessSurvivesAHandRun(t *testing.T) {
	root := t.TempDir()
	rolled := time.Now().Add(-7 * time.Hour).Format(backupTimestampFormat)
	handed := time.Now().Add(-6 * time.Hour).Format(backupTimestampFormat)
	writeBackupRun(t, root, rolled, &backupSummary{StagesRun: 3}, nil, map[string]bool{"mariadb": true})
	writeBackupStage(t, root, handed, "secondary", backupSummary{State: "complete"})
	p := &backupProbe{root: root}
	value, found, run := p.serviceSuccess("mariadb")
	if !value || !found {
		t.Errorf("mariadb: got (%v,%v) want (true,true)", value, found)
	}
	if run != rolled {
		t.Errorf("run: got %q want %q", run, rolled)
	}
}

func TestProbeImplBackup_AbandonedScheduledRunIsNotWalkedPast(t *testing.T) {
	root := t.TempDir()
	rolled := time.Now().Add(-30 * time.Hour).Format(backupTimestampFormat)
	writeBackupRun(t, root, rolled, &backupSummary{StagesRun: 3}, nil, nil)
	yesterday := time.Now().Add(-25 * time.Hour).Format(backupTimestampFormat)
	writeBackupRun(t, root, yesterday, &backupSummary{StagesRun: 3}, nil, nil)
	stuck := time.Now().Add(-8 * time.Hour).Format(backupTimestampFormat)
	writeBackupStage(t, root, stuck, "primary", backupSummary{
		State: metric.BackupStateSuccess, Trigger: metric.BackupTriggerSystem})
	writeBackupStage(t, root, stuck, "tertiary", backupSummary{
		State: metric.BackupStateRunning, Trigger: metric.BackupTriggerSystem, DiskUsagePerc: 26})
	p := &backupProbe{root: root, serverHost: true}
	value, _, err := p.failedBackupStages()
	if err != nil || value != 100 {
		t.Fatalf("failedBackupStages: got (%v,%v) want (100,nil)", value, err)
	}
	if _, _, err = p.usedBackupSpace(); err == nil {
		t.Error("usedBackupSpace: got nil error, want a fault rather than a frozen reading")
	}
}

func TestProbeImplBackup_AbandonedHandRunIsStillWalkedPast(t *testing.T) {
	root := t.TempDir()
	rolled := time.Now().Add(-9 * time.Hour).Format(backupTimestampFormat)
	writeBackupRun(t, root, rolled, &backupSummary{StagesRun: 3}, nil, nil)
	handed := time.Now().Add(-8 * time.Hour).Format(backupTimestampFormat)
	writeBackupStage(t, root, handed, "tertiary", backupSummary{
		State: metric.BackupStateRunning, Trigger: metric.BackupTriggerManual})
	p := &backupProbe{root: root, serverHost: true}
	value, _, err := p.failedBackupStages()
	if err != nil || value != 0 {
		t.Errorf("failedBackupStages: got (%v,%v) want (0,nil)", value, err)
	}
}

func TestProbeImplBackup_SnapshotFlagsBelongToTheRunItNames(t *testing.T) {
	root := t.TempDir()
	rolled := time.Now().Add(-25 * time.Hour).Format(backupTimestampFormat)
	writeBackupRun(t, root, rolled, &backupSummary{StagesRun: 3, StagesFailed: 0}, nil, nil)
	inflight := time.Now().Add(-10 * time.Minute).Format(backupTimestampFormat)
	writeBackupStage(t, root, inflight, "primary", backupSummary{
		State: metric.BackupStateRunning, Trigger: metric.BackupTriggerSystem})
	snapshot := readNewestRun(root)
	if snapshot.running && snapshot.dir != inflight {
		t.Fatalf("running: got dir %s want %s, the flag must describe the run it is stamped on", snapshot.dir, inflight)
	}
	if snapshot.dir != rolled {
		t.Fatalf("dir: got %s want %s, the walk-back must surface the run that rolled up", snapshot.dir, rolled)
	}
}

func TestProbeImplBackup_SnapshotFollowsTheTreeRatherThanAClock(t *testing.T) {
	root := t.TempDir()
	stale := time.Now().Add(-3 * time.Hour).Format(backupTimestampFormat)
	writeBackupRun(t, root, stale, &backupSummary{StagesRun: 3, StagesFailed: 1}, nil, nil)
	p := &backupProbe{root: root, serverHost: true}
	value, _, err := p.failedBackupStages()
	if err != nil || value != 33 {
		t.Fatalf("before: got (%v,%v) want (33,nil)", value, err)
	}
	handed := time.Now().Format(backupTimestampFormat)
	writeBackupRun(t, root, handed, &backupSummary{StagesRun: 3}, nil, nil)
	value, _, err = p.failedBackupStages()
	if err != nil || value != 0 {
		t.Errorf("after hand run: got (%v,%v) want (0,nil), the snapshot did not follow the tree", value, err)
	}
}

func TestProbeImplBackup_HaltedBackupStages(t *testing.T) {
	fresh := time.Now().Format(backupTimestampFormat)
	tests := []struct {
		name          string
		setup         func(root string)
		wantValue     int8
		wantInert     bool
		expectedError bool
	}{
		{"no runs is inert rather than a fault", func(string) {}, 0, true, false},
		{"a clean run reads zero", func(root string) {
			writeBackupRun(t, root, fresh, &backupSummary{StagesRun: 3, StagesFailed: 0}, nil, nil)
		}, 0, false, false},
		{"one stage halted of three", func(root string) {
			writeBackupRun(t, root, fresh, &backupSummary{StagesRun: 3, StagesHalted: 1}, nil, nil)
		}, 33, false, false},
		{"every stage halted", func(root string) {
			writeBackupRun(t, root, fresh, &backupSummary{StagesRun: 3, StagesHalted: 3}, nil, nil)
		}, 100, false, false},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			root := t.TempDir()
			tt.setup(root)
			probe := &backupProbe{root: root}
			value, derived, err := probe.haltedBackupStages()
			if (err != nil) != tt.expectedError {
				t.Fatalf("err: got %v want error %v", err, tt.expectedError)
			}
			if value != tt.wantValue {
				t.Errorf("value: got %d want %d", value, tt.wantValue)
			}
			if derived.inert != tt.wantInert {
				t.Errorf("inert: got %v want %v", derived.inert, tt.wantInert)
			}
		})
	}
}

func TestProbeImplBackup_ReapQuietRestatesAStandingCondition(t *testing.T) {
	probe := &backupProbe{}
	probe.reapIdle = 7
	spoken := 0
	for tick := range reaperNoticeTicks * 3 {
		if probe.reapQuiet() {
			spoken++
		}
		if probe.reapIdle != 0 {
			t.Fatalf("tick %d idle: got %v want 0", tick, probe.reapIdle)
		}
	}
	if spoken != 3 {
		t.Errorf("spoken: got %v want %v", spoken, 3)
	}
}

func TestProbeImplBackup_ReaperPausedFailsSafeToArmed(t *testing.T) {
	tests := []struct {
		name       string
		state      string
		expiresTS  string
		wantPaused bool
	}{
		{"off with a future deadline is paused", "OFF", time.Now().Add(time.Hour).Format(time.RFC3339), true},
		{"off with a passed deadline is armed", "OFF", time.Now().Add(-time.Hour).Format(time.RFC3339), false},
		{"off with an unparseable deadline is armed", "OFF", "tomorrow", false},
		{"off with no deadline is armed", "OFF", "", false},
		{"on is armed", "ON", time.Now().Add(time.Hour).Format(time.RFC3339), false},
		{"an empty document is armed", "", "", false},
		{"an unknown state is armed", "PAUSED", time.Now().Add(time.Hour).Format(time.RFC3339), false},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			reaper := backupReaperSummary{State: tt.state, ExpiresTS: tt.expiresTS}
			if got := reaper.Paused(); got != tt.wantPaused {
				t.Errorf("paused: got %v want %v", got, tt.wantPaused)
			}
		})
	}
}

func TestProbeImplBackup_ClusterRunDecision(t *testing.T) {
	now := time.Now().Truncate(time.Second)
	expected := []string{"mad", "max"}
	doc := func(state, trigger string, started time.Time, success bool) string {
		payload, _ := json.Marshal(backupSummary{State: state, Trigger: trigger, StartedTS: started.Format(time.RFC3339), SuccessBool: success,
			ExpiresTS: now.Add(time.Hour).Format(time.RFC3339)})
		return string(payload)
	}
	stageOf := func(run, started, expires time.Time) string {
		payload, _ := json.Marshal(backupSummary{RunID: run.Format(backupTimestampFormat), State: metric.BackupStateRunning, Trigger: metric.BackupTriggerSystem,
			StartedTS: started.Format(time.RFC3339), ExpiresTS: expires.Format(time.RFC3339)})
		return string(payload)
	}
	tertiary := func(host string) string { return "supervisor/" + host + "/backup/stage/tertiary/status" }
	stage := func(host string) string { return "supervisor/" + host + "/backup/stage/primary/status" }
	host := func(host string) string { return "supervisor/" + host + "/backup/status" }
	tonight := now.Add(-20 * time.Minute)
	tests := []struct {
		name             string
		retained         map[string]string
		expectedAction   backupClusterRunAction
		expectedState    string
		expectedStarted  time.Time
		expectedReported int
		expectedError    bool
	}{
		{
			name:           "nothing_retained_is_idle",
			retained:       map[string]string{},
			expectedAction: backupClusterRunIdle,
			expectedError:  false,
		},
		{
			name: "scheduled_stage_running_opens_the_run_at_the_earliest_start",
			retained: map[string]string{
				stage("mad"): doc(metric.BackupStateRunning, metric.BackupTriggerSystem, tonight.Add(time.Minute), false),
				stage("max"): doc(metric.BackupStateRunning, metric.BackupTriggerSystem, tonight, false),
			},
			expectedAction:  backupClusterRunOpen,
			expectedState:   metric.BackupStateRunning,
			expectedStarted: tonight,
			expectedError:   false,
		},
		{
			name:           "manual_stage_never_opens_a_cluster_backup_run",
			retained:       map[string]string{stage("mad"): doc(metric.BackupStateRunning, metric.BackupTriggerManual, tonight, false)},
			expectedAction: backupClusterRunIdle,
			expectedError:  false,
		},
		{
			name:           "stage_of_a_host_outside_the_expected_servers_is_ignored",
			retained:       map[string]string{stage("jen"): doc(metric.BackupStateRunning, metric.BackupTriggerSystem, tonight, false)},
			expectedAction: backupClusterRunIdle,
			expectedError:  false,
		},
		{
			name:           "stage_running_past_the_ceiling_is_ignored",
			retained:       map[string]string{stage("mad"): doc(metric.BackupStateRunning, metric.BackupTriggerSystem, now.Add(-backupRunCeiling-time.Minute), false)},
			expectedAction: backupClusterRunIdle,
			expectedError:  false,
		},
		{
			name: "closed_run_is_not_reopened_by_its_own_stuck_stage",
			retained: map[string]string{
				backupAllStatusTopic: doc(metric.BackupStateSuccess, "", tonight, true),
				stage("mad"):         doc(metric.BackupStateRunning, metric.BackupTriggerSystem, tonight.Add(time.Minute), false),
			},
			expectedAction: backupClusterRunIdle,
			expectedError:  false,
		},
		{
			name: "closed_run_from_last_night_lets_tonight_open",
			retained: map[string]string{
				backupAllStatusTopic: doc(metric.BackupStateSuccess, "", tonight.Add(-24*time.Hour), true),
				stage("mad"):         doc(metric.BackupStateRunning, metric.BackupTriggerSystem, tonight, false),
			},
			expectedAction:  backupClusterRunOpen,
			expectedState:   metric.BackupStateRunning,
			expectedStarted: tonight,
			expectedError:   false,
		},
		{
			name: "reopened_after_a_flush_dates_from_the_run_and_closes_on_its_reports",
			retained: map[string]string{
				tertiary("max"): stageOf(tonight, tonight.Add(15*time.Minute), now.Add(time.Hour)),
				host("mad"):     doc(metric.BackupStateSuccess, metric.BackupTriggerSystem, tonight, true),
				host("max"):     doc(metric.BackupStateSuccess, metric.BackupTriggerSystem, tonight, true),
			},
			expectedAction:   backupClusterRunClose,
			expectedState:    metric.BackupStateSuccess,
			expectedStarted:  tonight,
			expectedReported: 2,
			expectedError:    false,
		},
		{
			name:           "expired_running_stage_never_opens_a_run",
			retained:       map[string]string{tertiary("max"): stageOf(tonight, tonight, now.Add(-time.Minute))},
			expectedAction: backupClusterRunIdle,
			expectedError:  false,
		},
		{
			name: "late_stage_of_a_closed_run_does_not_reopen_it",
			retained: map[string]string{
				backupAllStatusTopic: doc(metric.BackupStateTimeout, "", tonight, false),
				tertiary("max"):      stageOf(tonight, tonight.Add(15*time.Minute), now.Add(time.Hour)),
			},
			expectedAction: backupClusterRunIdle,
			expectedError:  false,
		},
		{
			name: "running_cluster_backup_run_with_a_partial_report_is_refreshed",
			retained: map[string]string{
				backupAllStatusTopic: doc(metric.BackupStateRunning, "", tonight, false),
				host("mad"):          doc(metric.BackupStateSuccess, metric.BackupTriggerSystem, tonight, true),
			},
			expectedAction:   backupClusterRunRefresh,
			expectedState:    metric.BackupStateRunning,
			expectedStarted:  tonight,
			expectedReported: 1,
			expectedError:    false,
		},
		{
			name: "every_expected_server_reported_closes_complete",
			retained: map[string]string{
				backupAllStatusTopic: doc(metric.BackupStateRunning, "", tonight, false),
				host("mad"):          doc(metric.BackupStateSuccess, metric.BackupTriggerSystem, tonight, true),
				host("max"):          doc(metric.BackupStateSuccess, metric.BackupTriggerSystem, tonight.Add(time.Minute), true),
			},
			expectedAction:   backupClusterRunClose,
			expectedState:    metric.BackupStateSuccess,
			expectedStarted:  tonight,
			expectedReported: 2,
			expectedError:    false,
		},
		{
			name: "a_stopped_report_still_counts_as_a_report",
			retained: map[string]string{
				backupAllStatusTopic: doc(metric.BackupStateRunning, "", tonight, false),
				host("mad"):          doc(metric.BackupStateStopped, metric.BackupTriggerSystem, tonight, false),
				host("max"):          doc(metric.BackupStateSkipped, metric.BackupTriggerSystem, tonight, true),
			},
			expectedAction:   backupClusterRunClose,
			expectedState:    metric.BackupStateFailure,
			expectedStarted:  tonight,
			expectedReported: 2,
			expectedError:    false,
		},
		{
			name: "a_host_still_running_is_not_a_report",
			retained: map[string]string{
				backupAllStatusTopic: doc(metric.BackupStateRunning, "", tonight, false),
				host("mad"):          doc(metric.BackupStateSuccess, metric.BackupTriggerSystem, tonight, true),
				host("max"):          doc(metric.BackupStateRunning, metric.BackupTriggerSystem, tonight, false),
			},
			expectedAction:   backupClusterRunRefresh,
			expectedState:    metric.BackupStateRunning,
			expectedStarted:  tonight,
			expectedReported: 1,
			expectedError:    false,
		},
		{
			name: "a_failed_report_closes_failed",
			retained: map[string]string{
				backupAllStatusTopic: doc(metric.BackupStateRunning, "", tonight, false),
				host("mad"):          doc(metric.BackupStateFailure, metric.BackupTriggerSystem, tonight, false),
				host("max"):          doc(metric.BackupStateSuccess, metric.BackupTriggerSystem, tonight, true),
			},
			expectedAction:   backupClusterRunClose,
			expectedState:    metric.BackupStateFailure,
			expectedStarted:  tonight,
			expectedReported: 2,
			expectedError:    false,
		},
		{
			name: "run_past_its_ceiling_closes_timedout",
			retained: map[string]string{
				backupAllStatusTopic: doc(metric.BackupStateRunning, "", now.Add(-backupRunCeiling-time.Minute), false),
			},
			expectedAction:  backupClusterRunClose,
			expectedState:   metric.BackupStateTimeout,
			expectedStarted: now.Add(-backupRunCeiling - time.Minute),
			expectedError:   false,
		},
		{
			name: "last_nights_report_does_not_count_for_tonight",
			retained: map[string]string{
				backupAllStatusTopic: doc(metric.BackupStateRunning, "", tonight, false),
				host("mad"):          doc(metric.BackupStateSuccess, metric.BackupTriggerSystem, tonight.Add(-24*time.Hour), true),
				host("max"):          doc(metric.BackupStateSuccess, metric.BackupTriggerSystem, tonight, true),
			},
			expectedAction:   backupClusterRunRefresh,
			expectedState:    metric.BackupStateRunning,
			expectedStarted:  tonight,
			expectedReported: 1,
			expectedError:    false,
		},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			decision := backupClusterRunDecision(tt.retained, expected, now)
			if decision.action != tt.expectedAction {
				t.Fatalf("action: got %v want %v", decision.action, tt.expectedAction)
			}
			if decision.action == backupClusterRunIdle {
				return
			}
			if decision.state != tt.expectedState {
				t.Errorf("state: got %s want %s", decision.state, tt.expectedState)
			}
			if !decision.started.Equal(tt.expectedStarted) {
				t.Errorf("started: got %v want %v", decision.started, tt.expectedStarted)
			}
			if decision.reported != tt.expectedReported {
				t.Errorf("reported: got %d want %d", decision.reported, tt.expectedReported)
			}
		})
	}
}

func TestProbeImplBackup_LeaderOpensAndClosesTheClusterBackupRun(t *testing.T) {
	testutil.RequiresDocker(t)
	_, observer, err := testutil.SetupBrokerContainer(t)
	if err != nil {
		t.Fatalf("setup broker container failed: %v", err)
	}
	t.Cleanup(config.Reset)
	plug := fmt.Sprintf("test/plug-%d/cmnd/POWER", time.Now().UnixNano())
	configFile := filepath.Join(t.TempDir(), "config.json")
	content := fmt.Sprintf(`{"asystem":{"version":"10.100.6000","host":"mad","broker":{"host":%q,"port":%q},"backup":{"command_topic":%q},"schema":[{"host":"mad","stages":["primary","secondary","tertiary"]},{"host":"max","stages":["primary","secondary","tertiary"]}]}}`,
		os.Getenv("VERNEMQ_HOST"), os.Getenv("VERNEMQ_API_PORT"), plug)
	if err := os.WriteFile(configFile, []byte(content), 0644); err != nil {
		t.Fatalf("write config file failed: %v", err)
	}
	holder := leaderStubCampaign([]string{"mad", "max"}, "mad")
	holder.election.name = metric.LeaderElection
	holder.attached, holder.standing, holder.leading, holder.epoch = true, true, true, 7
	holder.lastAck, holder.lastLease = time.Now().Add(time.Hour), time.Now().Add(time.Hour)
	holder.lease, holder.leaseArrived = leaderLease{Host: "mad", Epoch: 7}, time.Now()
	leaderCampaignsMu.Lock()
	leaderCampaigns[metric.LeaderDutyBackup] = holder
	leaderCampaignsMu.Unlock()
	t.Cleanup(func() {
		leaderCampaignsMu.Lock()
		delete(leaderCampaigns, metric.LeaderDutyBackup)
		leaderCampaignsMu.Unlock()
	})
	var mutex sync.Mutex
	seen := map[string]string{}
	record := func(_ mqtt.Client, message mqtt.Message) {
		mutex.Lock()
		seen[message.Topic()] = string(message.Payload())
		mutex.Unlock()
	}
	for _, topic := range []string{plug, backupAllStatusTopic} {
		if token := observer.Subscribe(topic, 1, record); !token.WaitTimeout(2*time.Second) || token.Error() != nil {
			t.Fatalf("subscribe %s: got %v want nil", topic, token.Error())
		}
	}
	publish := func(topic string, document backupSummary) {
		payload, _ := json.Marshal(document)
		if token := observer.Publish(topic, 1, true, payload); !token.WaitTimeout(2*time.Second) || token.Error() != nil {
			t.Fatalf("publish %s: got %v want nil", topic, token.Error())
		}
	}
	observer.Publish(backupAllStatusTopic, 1, true, []byte{}).WaitTimeout(2 * time.Second)
	started := time.Now().Add(-5 * time.Minute).Truncate(time.Second)
	for _, host := range []string{"mad", "max"} {
		publish("supervisor/"+host+"/backup/stage/primary/status", backupSummary{RunID: started.Format(backupTimestampFormat), State: metric.BackupStateRunning, Trigger: metric.BackupTriggerSystem,
			StartedTS: started.Format(time.RFC3339), ExpiresTS: time.Now().Add(time.Hour).Format(time.RFC3339)})
	}
	probe := &backupProbe{configPath: configFile, hostName: "mad", serverHost: true}
	t.Cleanup(func() { probe.leadWatch.close() })
	await := func(phase string, done func() bool) {
		deadline := time.Now().Add(30 * time.Second)
		for time.Now().Before(deadline) {
			probe.lead()
			mutex.Lock()
			finished := done()
			mutex.Unlock()
			if finished {
				return
			}
			time.Sleep(time.Second)
		}
		mutex.Lock()
		defer mutex.Unlock()
		t.Fatalf("%s: got %v want the phase reached", phase, seen)
	}
	cluster := func() backupSummary {
		var document backupSummary
		_ = json.Unmarshal([]byte(seen[backupAllStatusTopic]), &document)
		return document
	}
	await("opened", func() bool { return cluster().State == metric.BackupStateRunning })
	if seen[plug] != "" {
		t.Fatalf("plug: got %q want nothing sent while hosts are still running", seen[plug])
	}
	publish("supervisor/mad/backup/status", backupSummary{State: metric.BackupStateSuccess, Trigger: metric.BackupTriggerSystem, StartedTS: started.Format(time.RFC3339), SuccessBool: true})
	time.Sleep(time.Second)
	probe.lead()
	mutex.Lock()
	partial := cluster().State
	mutex.Unlock()
	if partial != metric.BackupStateRunning {
		t.Fatalf("partial state: got %s want running until every expected server reports", partial)
	}
	publish("supervisor/max/backup/status", backupSummary{State: metric.BackupStateSuccess, Trigger: metric.BackupTriggerSystem, StartedTS: started.Format(time.RFC3339), SuccessBool: true})
	await("closed", func() bool { return cluster().State == metric.BackupStateSuccess && seen[plug] == metric.CommandOff })
	var closed map[string]any
	mutex.Lock()
	_ = json.Unmarshal([]byte(seen[backupAllStatusTopic]), &closed)
	mutex.Unlock()
	if closed["leader_host"] != "mad" || closed["leader_epoch"] != float64(7) {
		t.Errorf("closed by: got [%v] epoch [%v] want mad at epoch 7", closed["leader_host"], closed["leader_epoch"])
	}
	mutex.Lock()
	seen[plug] = ""
	mutex.Unlock()
	holder.mutex.Lock()
	holder.leading = false
	holder.mutex.Unlock()
	publish("supervisor/max/backup/stage/primary/status", backupSummary{RunID: time.Now().Format(backupTimestampFormat), State: metric.BackupStateRunning, Trigger: metric.BackupTriggerSystem,
		StartedTS: time.Now().Format(time.RFC3339), ExpiresTS: time.Now().Add(time.Hour).Format(time.RFC3339)})
	time.Sleep(time.Second)
	probe.lead()
	mutex.Lock()
	defer mutex.Unlock()
	if seen[plug] != "" || cluster().State != metric.BackupStateSuccess {
		t.Errorf("deposed holder: got plug [%q] state [%s] want no action from a host that no longer leads", seen[plug], cluster().State)
	}
}

func TestProbeImplBackup_LeadClosesItsWatchWhenNotLeading(t *testing.T) {
	stub := &leaderStubClient{open: true}
	probe := &backupProbe{serverHost: true, leadWatch: brokerWatcherWith(stub, map[string]string{}), leadStale: 3}
	probe.lead()
	if probe.leadWatch != nil || probe.leadStale != 0 {
		t.Errorf("watch: got kept [%v] stale [%d] want closed once this host does not lead", probe.leadWatch != nil, probe.leadStale)
	}
	if stub.IsConnectionOpen() {
		t.Errorf("session: got open want disconnected")
	}
}

func TestProbeImplBackup_ReapLocalStaleKeepsEveryFieldItRewrites(t *testing.T) {
	original := stageStream
	t.Cleanup(func() { stageStream = original })
	stageStream = func(_ context.Context, _ io.Writer, _ string, _ ...string) (string, int, bool) { return "", 0, false }

	root := t.TempDir()
	run := "2026-09-22_01-00-00"
	runPath := backupRunPath(root, run)
	if err := os.MkdirAll(stageDir(runPath, metric.BackupStagePrimary), 0o755); err != nil {
		t.Fatalf("mkdir primary: %v", err)
	}
	wedged := backupSummary{
		RunID: run, State: metric.BackupStateRunning, Trigger: metric.BackupTriggerSystem,
		StartedTS:    time.Now().Add(-2 * time.Hour).Format(time.RFC3339),
		ExpiresTS:    time.Now().Add(-time.Hour).Format(time.RFC3339),
		TimeoutHours: 3, DurationS: 7200, FileCount: 12, SizeMB: 340, TotalMB: 900,
		FilesCreated: 12, SizeHeldMB: 80, SentMB: 341, DiskUsedMB: 700, DiskTotalMB: 900, DiskUsagePerc: 77.8,
	}
	if err := writeAtomic(stageStatusPath(runPath, metric.BackupStagePrimary), wedged); err != nil {
		t.Fatalf("write primary: %v", err)
	}
	probe := &backupProbe{root: root, configPath: filepath.Join(root, "config.json"), hostName: "testhost"}
	snapshot := readNewestRun(root)
	if snapshot == nil {
		t.Fatalf("readNewestRun() found no run under [%s]", root)
	}
	probe.reapLocalStale(t.Context(), snapshot)

	reaped := readBackupSummary(stageStatusPath(runPath, metric.BackupStagePrimary))
	if reaped == nil {
		t.Fatalf("the reaped stage document is gone from [%s]", runPath)
	}
	if reaped.State != metric.BackupStateTimeout || reaped.ExpiresTS != "" || reaped.FinishedTS == "" {
		t.Errorf("reaped = (%q, expires %q, finished %q), want a timeout with its liveness cleared and a finish stamped",
			reaped.State, reaped.ExpiresTS, reaped.FinishedTS)
	}
	expected := wedged
	expected.State, expected.ExpiresTS, expected.FinishedTS = reaped.State, reaped.ExpiresTS, reaped.FinishedTS
	if *reaped != expected {
		t.Errorf("reaped document = %+v, want every other field carried over from %+v", *reaped, expected)
	}
}
