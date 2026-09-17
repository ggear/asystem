package probe

import (
	"encoding/json"
	"fmt"
	"go/ast"
	"go/parser"
	"go/token"
	"os"
	"path/filepath"
	"regexp"
	"sort"
	"strings"
	"supervisor/internal/config"
	"supervisor/internal/metric"
	"supervisor/internal/testutil"
	"sync"
	"testing"
	"time"

	mqtt "github.com/eclipse/paho.mqtt.golang"
)

func writeBackupRun(t *testing.T, root, stamp string, host *backupDocument, tertiary *backupDocument, services map[string]bool) {
	t.Helper()
	runPath := filepath.Join(root, stamp)
	if err := os.MkdirAll(runPath, 0o755); err != nil {
		t.Fatal(err)
	}
	write := func(path string, document backupDocument) {
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
			backupDocument{RunID: stamp, SuccessBool: success})
	}
}

func writeBackupStage(t *testing.T, root, stamp, stage string, document backupDocument) {
	t.Helper()
	path := stageStatusPath(filepath.Join(root, stamp), stage)
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		t.Fatal(err)
	}
	data, _ := json.MarshalIndent(document, "", "  ")
	if err := os.WriteFile(path, data, 0o644); err != nil {
		t.Fatal(err)
	}
}

func TestProbeImplBackup_FailedBackups(t *testing.T) {
	fresh := time.Now().Format(backupRunStamp)
	stale := time.Now().Add(-40 * time.Hour).Format(backupRunStamp)
	abandoned := time.Now().Add(-6 * time.Hour).Format(backupRunStamp)
	rolled := time.Now().Add(-7 * time.Hour).Format(backupRunStamp)
	tests := []struct {
		name          string
		setup         func(root string)
		wantValue     int8
		wantInert     bool
		expectedError bool
	}{
		{"run in flight is inert until it writes its roll-up", func(root string) {
			writeBackupStage(t, root, fresh, "primary", backupDocument{State: "complete"})
		}, 0, true, false},
		{"run abandoned beyond the ceiling with no roll-up ever cannot be measured", func(root string) {
			writeBackupStage(t, root, abandoned, "primary", backupDocument{State: "running"})
		}, 0, false, true},
		{"no runs at all cannot be measured", func(string) {}, 0, false, true},
		{"an abandoned run on a host that has rolled up before reads fully failed", func(root string) {
			writeBackupRun(t, root, stale, &backupDocument{StagesRun: 3, StagesFailed: 0}, nil, nil)
			writeBackupStage(t, root, abandoned, "primary", backupDocument{State: "running"})
		}, 100, false, false},
		{"stale run reads fully failed", func(root string) {
			writeBackupRun(t, root, stale, &backupDocument{StagesRun: 3, StagesFailed: 0}, nil, nil)
		}, 100, false, false},
		{"clean current run reads zero", func(root string) {
			writeBackupRun(t, root, fresh, &backupDocument{StagesRun: 3, StagesFailed: 0}, nil, nil)
		}, 0, false, false},
		{"one failed stage of three", func(root string) {
			writeBackupRun(t, root, fresh, &backupDocument{StagesRun: 3, StagesFailed: 1}, nil, nil)
		}, 33, false, false},
		{"failed secondary on edge host", func(root string) {
			writeBackupRun(t, root, fresh, &backupDocument{StagesRun: 2, StagesFailed: 1}, nil, nil)
		}, 50, false, false},
		{"a hand stage newer than the last roll-up does not mask it", func(root string) {
			writeBackupRun(t, root, rolled, &backupDocument{StagesRun: 3, StagesFailed: 0}, nil, nil)
			writeBackupStage(t, root, abandoned, "secondary", backupDocument{State: "complete"})
		}, 0, false, false},
		{"a hand stage newer than a stale roll-up still reads fully failed", func(root string) {
			writeBackupRun(t, root, stale, &backupDocument{StagesRun: 3, StagesFailed: 0}, nil, nil)
			writeBackupStage(t, root, abandoned, "secondary", backupDocument{State: "complete"})
		}, 100, false, false},
		{"a hand stage in flight is still inert over an older roll-up", func(root string) {
			writeBackupRun(t, root, rolled, &backupDocument{StagesRun: 3, StagesFailed: 0}, nil, nil)
			writeBackupStage(t, root, fresh, "secondary", backupDocument{State: "running"})
		}, 0, true, false},
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
	fresh := time.Now().Format(backupRunStamp)
	tests := []struct {
		name          string
		serverHost    bool
		setup         func(root string)
		wantValue     int8
		wantInert     bool
		expectedError bool
	}{
		{"no tertiary document on a server errors", true, func(root string) {
			writeBackupRun(t, root, fresh, &backupDocument{StagesRun: 2}, nil, nil)
		}, 0, false, true},
		{"no tertiary document on an edge host is inert", false, func(root string) {
			writeBackupRun(t, root, fresh, &backupDocument{StagesRun: 2}, nil, nil)
		}, 0, true, false},
		{"reads tertiary disk usage", true, func(root string) {
			writeBackupRun(t, root, fresh, &backupDocument{StagesRun: 3}, &backupDocument{DiskUsagePerc: 72}, nil)
		}, 72, false, false},
		{"run in flight on a server is inert", true, func(root string) {
			writeBackupStage(t, root, fresh, "primary", backupDocument{State: "complete"})
		}, 0, true, false},
		{"tertiary still running is inert rather than zero", true, func(root string) {
			writeBackupStage(t, root, fresh, "tertiary", backupDocument{State: "running", DiskUsagePerc: 0})
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
	fresh := time.Now().Format(backupRunStamp)
	writeBackupRun(t, root, fresh, &backupDocument{StagesRun: 3}, nil, map[string]bool{"postgres": true, "plex": false})
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
	rolled := time.Now().Add(-7 * time.Hour).Format(backupRunStamp)
	handed := time.Now().Add(-6 * time.Hour).Format(backupRunStamp)
	writeBackupRun(t, root, rolled, &backupDocument{StagesRun: 3}, nil, map[string]bool{"mariadb": true})
	writeBackupStage(t, root, handed, "secondary", backupDocument{State: "complete"})
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
	rolled := time.Now().Add(-30 * time.Hour).Format(backupRunStamp)
	writeBackupRun(t, root, rolled, &backupDocument{StagesRun: 3}, nil, nil)
	yesterday := time.Now().Add(-25 * time.Hour).Format(backupRunStamp)
	writeBackupRun(t, root, yesterday, &backupDocument{StagesRun: 3}, nil, nil)
	stuck := time.Now().Add(-8 * time.Hour).Format(backupRunStamp)
	writeBackupStage(t, root, stuck, "primary", backupDocument{
		State: metric.BackupStateComplete, Trigger: metric.BackupTriggerScheduled})
	writeBackupStage(t, root, stuck, "tertiary", backupDocument{
		State: metric.BackupStateRunning, Trigger: metric.BackupTriggerScheduled, DiskUsagePerc: 26})
	p := &backupProbe{root: root, serverHost: true, periods: config.Periods{CacheMins: 60}}
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
	rolled := time.Now().Add(-9 * time.Hour).Format(backupRunStamp)
	writeBackupRun(t, root, rolled, &backupDocument{StagesRun: 3}, nil, nil)
	handed := time.Now().Add(-8 * time.Hour).Format(backupRunStamp)
	writeBackupStage(t, root, handed, "tertiary", backupDocument{
		State: metric.BackupStateRunning, Trigger: metric.BackupTriggerManual})
	p := &backupProbe{root: root, serverHost: true, periods: config.Periods{CacheMins: 60}}
	value, _, err := p.failedBackupStages()
	if err != nil || value != 0 {
		t.Errorf("failedBackupStages: got (%v,%v) want (0,nil)", value, err)
	}
}

func TestProbeImplBackup_SnapshotFollowsAHandRunWithinTheCacheWindow(t *testing.T) {
	root := t.TempDir()
	stale := time.Now().Add(-3 * time.Hour).Format(backupRunStamp)
	writeBackupRun(t, root, stale, &backupDocument{StagesRun: 3, StagesFailed: 1}, nil, nil)
	p := &backupProbe{root: root, serverHost: true, periods: config.Periods{CacheMins: 60}}
	value, _, err := p.failedBackupStages()
	if err != nil || value != 33 {
		t.Fatalf("before: got (%v,%v) want (33,nil)", value, err)
	}
	handed := time.Now().Format(backupRunStamp)
	writeBackupRun(t, root, handed, &backupDocument{StagesRun: 3}, nil, nil)
	value, _, err = p.failedBackupStages()
	if err != nil || value != 0 {
		t.Errorf("after hand run: got (%v,%v) want (0,nil), the snapshot did not follow the tree", value, err)
	}
}

func TestProbeImplBackup_HaltedBackupStages(t *testing.T) {
	fresh := time.Now().Format(backupRunStamp)
	tests := []struct {
		name          string
		setup         func(root string)
		wantValue     int8
		wantInert     bool
		expectedError bool
	}{
		{"no runs is inert rather than a fault", func(string) {}, 0, true, false},
		{"a clean run reads zero", func(root string) {
			writeBackupRun(t, root, fresh, &backupDocument{StagesRun: 3, StagesFailed: 0}, nil, nil)
		}, 0, false, false},
		{"one stage halted of three", func(root string) {
			writeBackupRun(t, root, fresh, &backupDocument{StagesRun: 3, StagesHalted: 1}, nil, nil)
		}, 33, false, false},
		{"every stage halted", func(root string) {
			writeBackupRun(t, root, fresh, &backupDocument{StagesRun: 3, StagesHalted: 3}, nil, nil)
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
			reaper := backupReaper{State: tt.state, ExpiresTS: tt.expiresTS}
			if got := reaper.paused(); got != tt.wantPaused {
				t.Errorf("paused: got %v want %v", got, tt.wantPaused)
			}
		})
	}
}

func TestProbeImplBackup_RunnerInvocationsSpeakTheRunnerCli(t *testing.T) {
	script, err := os.ReadFile(filepath.Join("..", "..", "..", "..", "resources", "image", "backup.sh"))
	if err != nil {
		t.Fatalf("read backup.sh: %v", err)
	}
	commands := map[string]bool{}
	dispatch := regexp.MustCompile(`case "\$\{BACKUP_COMMAND\}" in\n((?:[a-z]+ \| )+[a-z]+)\) ;;`)
	match := dispatch.FindStringSubmatch(string(script))
	if match == nil {
		t.Fatal("found no BACKUP_COMMAND dispatch in backup.sh, the parse has rotted")
	}
	for word := range strings.SplitSeq(match[1], " | ") {
		commands[word] = true
	}
	for _, required := range []string{"start", "stop", "tail", "list"} {
		if !commands[required] {
			t.Fatalf("parsed no [%s] out of the backup.sh dispatch, the parse has rotted", required)
		}
	}
	parsed, err := parser.ParseFile(token.NewFileSet(), "probe_impl_backup.go", nil, 0)
	if err != nil {
		t.Fatalf("parse probe_impl_backup.go: %v", err)
	}
	invocations := 0
	ast.Inspect(parsed, func(node ast.Node) bool {
		call, isCall := node.(*ast.CallExpr)
		if !isCall {
			return true
		}
		if function, isFunction := call.Fun.(*ast.SelectorExpr); !isFunction ||
			!strings.HasPrefix(function.Sel.Name, "Command") {
			return true
		}
		for index, argument := range call.Args {
			selector, isSelector := argument.(*ast.SelectorExpr)
			if !isSelector || selector.Sel.Name != "runner" || index+1 >= len(call.Args) {
				continue
			}
			invocations++
			literal, isLiteral := call.Args[index+1].(*ast.BasicLit)
			if !isLiteral || literal.Kind != token.STRING {
				t.Errorf("invocation of the runner passes a non-literal command, want one of %v", sortedKeys(commands))
				continue
			}
			command := strings.Trim(literal.Value, `"`)
			if !commands[command] {
				t.Errorf("invocation of the runner passes the command [%s], want one of %v", command, sortedKeys(commands))
			}
		}
		return true
	})
	if invocations == 0 {
		t.Fatal("found no runner invocations to check, the walk has rotted")
	}
}

func sortedKeys(set map[string]bool) []string {
	keys := make([]string, 0, len(set))
	for key := range set {
		keys = append(keys, key)
	}
	sort.Strings(keys)
	return keys
}

func TestProbeImplBackup_ReportedForRunIdentifiesAPeerByWindowNotRunID(t *testing.T) {
	runStart := time.Date(2026, 9, 13, 1, 0, 25, 0, time.Local)
	earliest := runStart.Add(-backupRunSkew)
	cases := []struct {
		name      string
		startedTS string
		expected  bool
	}{
		{"the leader's own run", runStart.Format(time.RFC3339), true},
		{"a peer that minted its own id seconds later", runStart.Add(30 * time.Second).Format(time.RFC3339), true},
		{"a peer at the far edge of the skew", earliest.Format(time.RFC3339), true},
		{"a peer that started before the skew", earliest.Add(-time.Second).Format(time.RFC3339), false},
		{"yesterday's run still retained", runStart.Add(-24 * time.Hour).Format(time.RFC3339), false},
		{"a document carrying no start", "", false},
		{"a document carrying an unparseable start", "not a timestamp", false},
	}
	for _, test := range cases {
		t.Run(test.name, func(t *testing.T) {
			got := reportedForRun(backupDocument{RunID: "whatever", StartedTS: test.startedTS}, earliest)
			if got != test.expected {
				t.Errorf("reportedForRun(%q): got %v want %v", test.startedTS, got, test.expected)
			}
		})
	}
}

func TestProbeImplBackup_ReaperTopicMatchesTheShell(t *testing.T) {
	script, err := os.ReadFile(filepath.Join("..", "..", "..", "..", "resources", "image", "backup.sh"))
	if err != nil {
		t.Fatalf("read backup.sh: %v", err)
	}
	match := regexp.MustCompile(`(?m)^BACKUP_REAPER_TOPIC="([^"]+)"$`).FindSubmatch(script)
	if match == nil {
		t.Fatal("found no BACKUP_REAPER_TOPIC in backup.sh, the parse has rotted")
	}
	if shell := string(match[1]); shell != allReaperTopic {
		t.Errorf("reaper topic: got %s in backup.sh want %s", shell, allReaperTopic)
	}
}

func TestProbeImplBackup_ClusterRunDecision(t *testing.T) {
	now := time.Now().Truncate(time.Second)
	expected := []string{"mad", "max"}
	doc := func(state, trigger string, started time.Time, success bool) string {
		payload, _ := json.Marshal(backupDocument{State: state, Trigger: trigger, StartedTS: started.Format(time.RFC3339), SuccessBool: success,
			ExpiresTS: now.Add(time.Hour).Format(time.RFC3339)})
		return string(payload)
	}
	stageOf := func(run, started, expires time.Time) string {
		payload, _ := json.Marshal(backupDocument{RunID: run.Format(backupRunStamp), State: metric.BackupStateRunning, Trigger: metric.BackupTriggerScheduled,
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
				stage("mad"): doc(metric.BackupStateRunning, metric.BackupTriggerScheduled, tonight.Add(time.Minute), false),
				stage("max"): doc(metric.BackupStateRunning, metric.BackupTriggerScheduled, tonight, false),
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
			retained:       map[string]string{stage("jen"): doc(metric.BackupStateRunning, metric.BackupTriggerScheduled, tonight, false)},
			expectedAction: backupClusterRunIdle,
			expectedError:  false,
		},
		{
			name:           "stage_running_past_the_ceiling_is_ignored",
			retained:       map[string]string{stage("mad"): doc(metric.BackupStateRunning, metric.BackupTriggerScheduled, now.Add(-backupRunCeiling-time.Minute), false)},
			expectedAction: backupClusterRunIdle,
			expectedError:  false,
		},
		{
			name: "closed_run_is_not_reopened_by_its_own_stuck_stage",
			retained: map[string]string{
				allBackupStatusTopic: doc(metric.BackupStateComplete, "", tonight, true),
				stage("mad"):         doc(metric.BackupStateRunning, metric.BackupTriggerScheduled, tonight.Add(time.Minute), false),
			},
			expectedAction: backupClusterRunIdle,
			expectedError:  false,
		},
		{
			name: "closed_run_from_last_night_lets_tonight_open",
			retained: map[string]string{
				allBackupStatusTopic: doc(metric.BackupStateComplete, "", tonight.Add(-24*time.Hour), true),
				stage("mad"):         doc(metric.BackupStateRunning, metric.BackupTriggerScheduled, tonight, false),
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
				host("mad"):     doc(metric.BackupStateComplete, metric.BackupTriggerScheduled, tonight, true),
				host("max"):     doc(metric.BackupStateComplete, metric.BackupTriggerScheduled, tonight, true),
			},
			expectedAction:   backupClusterRunClose,
			expectedState:    metric.BackupStateComplete,
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
				allBackupStatusTopic: doc(metric.BackupStateTimedout, "", tonight, false),
				tertiary("max"):      stageOf(tonight, tonight.Add(15*time.Minute), now.Add(time.Hour)),
			},
			expectedAction: backupClusterRunIdle,
			expectedError:  false,
		},
		{
			name: "running_cluster_backup_run_with_a_partial_report_is_refreshed",
			retained: map[string]string{
				allBackupStatusTopic: doc(metric.BackupStateRunning, "", tonight, false),
				host("mad"):          doc(metric.BackupStateComplete, metric.BackupTriggerScheduled, tonight, true),
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
				allBackupStatusTopic: doc(metric.BackupStateRunning, "", tonight, false),
				host("mad"):          doc(metric.BackupStateComplete, metric.BackupTriggerScheduled, tonight, true),
				host("max"):          doc(metric.BackupStateComplete, metric.BackupTriggerScheduled, tonight.Add(time.Minute), true),
			},
			expectedAction:   backupClusterRunClose,
			expectedState:    metric.BackupStateComplete,
			expectedStarted:  tonight,
			expectedReported: 2,
			expectedError:    false,
		},
		{
			name: "a_failed_report_closes_failed",
			retained: map[string]string{
				allBackupStatusTopic: doc(metric.BackupStateRunning, "", tonight, false),
				host("mad"):          doc(metric.BackupStateFailed, metric.BackupTriggerScheduled, tonight, false),
				host("max"):          doc(metric.BackupStateComplete, metric.BackupTriggerScheduled, tonight, true),
			},
			expectedAction:   backupClusterRunClose,
			expectedState:    metric.BackupStateFailed,
			expectedStarted:  tonight,
			expectedReported: 2,
			expectedError:    false,
		},
		{
			name: "run_past_its_ceiling_closes_timedout",
			retained: map[string]string{
				allBackupStatusTopic: doc(metric.BackupStateRunning, "", now.Add(-backupRunCeiling-time.Minute), false),
			},
			expectedAction:  backupClusterRunClose,
			expectedState:   metric.BackupStateTimedout,
			expectedStarted: now.Add(-backupRunCeiling - time.Minute),
			expectedError:   false,
		},
		{
			name: "last_nights_report_does_not_count_for_tonight",
			retained: map[string]string{
				allBackupStatusTopic: doc(metric.BackupStateRunning, "", tonight, false),
				host("mad"):          doc(metric.BackupStateComplete, metric.BackupTriggerScheduled, tonight.Add(-24*time.Hour), true),
				host("max"):          doc(metric.BackupStateComplete, metric.BackupTriggerScheduled, tonight, true),
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
	for _, topic := range []string{plug, allBackupStatusTopic} {
		if token := observer.Subscribe(topic, 1, record); !token.WaitTimeout(2*time.Second) || token.Error() != nil {
			t.Fatalf("subscribe %s: got %v want nil", topic, token.Error())
		}
	}
	publish := func(topic string, document backupDocument) {
		payload, _ := json.Marshal(document)
		if token := observer.Publish(topic, 1, true, payload); !token.WaitTimeout(2*time.Second) || token.Error() != nil {
			t.Fatalf("publish %s: got %v want nil", topic, token.Error())
		}
	}
	observer.Publish(allBackupStatusTopic, 1, true, []byte{}).WaitTimeout(2 * time.Second)
	started := time.Now().Add(-5 * time.Minute).Truncate(time.Second)
	for _, host := range []string{"mad", "max"} {
		publish("supervisor/"+host+"/backup/stage/primary/status", backupDocument{RunID: started.Format(backupRunStamp), State: metric.BackupStateRunning, Trigger: metric.BackupTriggerScheduled,
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
	cluster := func() backupDocument {
		var document backupDocument
		_ = json.Unmarshal([]byte(seen[allBackupStatusTopic]), &document)
		return document
	}
	await("opened", func() bool { return cluster().State == metric.BackupStateRunning })
	if seen[plug] != "" {
		t.Fatalf("plug: got %q want nothing sent while hosts are still running", seen[plug])
	}
	publish("supervisor/mad/backup/status", backupDocument{State: metric.BackupStateComplete, Trigger: metric.BackupTriggerScheduled, StartedTS: started.Format(time.RFC3339), SuccessBool: true})
	time.Sleep(time.Second)
	probe.lead()
	mutex.Lock()
	partial := cluster().State
	mutex.Unlock()
	if partial != metric.BackupStateRunning {
		t.Fatalf("partial state: got %s want running until every expected server reports", partial)
	}
	publish("supervisor/max/backup/status", backupDocument{State: metric.BackupStateComplete, Trigger: metric.BackupTriggerScheduled, StartedTS: started.Format(time.RFC3339), SuccessBool: true})
	await("closed", func() bool { return cluster().State == metric.BackupStateComplete && seen[plug] == metric.CommandOff })
	var closed map[string]any
	mutex.Lock()
	_ = json.Unmarshal([]byte(seen[allBackupStatusTopic]), &closed)
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
	publish("supervisor/max/backup/stage/primary/status", backupDocument{RunID: time.Now().Format(backupRunStamp), State: metric.BackupStateRunning, Trigger: metric.BackupTriggerScheduled,
		StartedTS: time.Now().Format(time.RFC3339), ExpiresTS: time.Now().Add(time.Hour).Format(time.RFC3339)})
	time.Sleep(time.Second)
	probe.lead()
	mutex.Lock()
	defer mutex.Unlock()
	if seen[plug] != "" || cluster().State != metric.BackupStateComplete {
		t.Errorf("deposed holder: got plug [%q] state [%s] want no action from a host that no longer leads", seen[plug], cluster().State)
	}
}

func TestProbeImplBackup_LeadClosesItsWatchWhenNotLeading(t *testing.T) {
	stub := &leaderStubClient{open: true}
	probe := &backupProbe{serverHost: true, leadWatch: &brokerWatcher{brokerPayloads: brokerPayloads{payloads: map[string]string{}}, client: stub}, leadStale: 3}
	probe.lead()
	if probe.leadWatch != nil || probe.leadStale != 0 {
		t.Errorf("watch: got kept [%v] stale [%d] want closed once this host does not lead", probe.leadWatch != nil, probe.leadStale)
	}
	if stub.IsConnectionOpen() {
		t.Errorf("session: got open want disconnected")
	}
}
