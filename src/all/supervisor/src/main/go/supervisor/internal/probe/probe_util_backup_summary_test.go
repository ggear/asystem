package probe

import (
	"encoding/json"
	"os"
	"path/filepath"
	"reflect"
	"strings"
	"testing"
	"time"

	"supervisor/internal/metric"
)

func fixturesDir(t *testing.T) string {
	t.Helper()
	dir, err := filepath.Abs(filepath.Join("..", "..", "..", "..", "..", "test", "resources", "backup", "documents"))
	if err != nil {
		t.Fatalf("resolve fixtures dir: %v", err)
	}
	entries, err := os.ReadDir(dir)
	if err != nil {
		t.Fatalf("fixtures dir: %v", err)
	}
	if len(entries) == 0 {
		t.Fatalf("fixtures dir %s is empty, this test would assert nothing", dir)
	}
	return dir
}

func TestProbeUtilBackupSummary_RoundTripsCapturedFixtures(t *testing.T) {
	dir := fixturesDir(t)
	entries, err := os.ReadDir(dir)
	if err != nil {
		t.Fatalf("read fixtures dir: %v", err)
	}
	checked := 0
	for _, entry := range entries {
		if entry.IsDir() || !strings.HasSuffix(entry.Name(), ".json") {
			continue
		}
		t.Run(entry.Name(), func(t *testing.T) {
			path := filepath.Join(dir, entry.Name())
			original, err := os.ReadFile(path)
			if err != nil {
				t.Fatalf("read fixture: %v", err)
			}
			var expected map[string]any
			if err := json.Unmarshal(original, &expected); err != nil {
				t.Fatalf("parse fixture as map: %v", err)
			}
			var actual map[string]any
			var declared map[string]bool
			switch {
			case strings.HasPrefix(entry.Name(), "run-"), strings.HasPrefix(entry.Name(), "stage-"):
				document := readBackupSummary(path)
				if document == nil {
					t.Fatalf("readSummary returned nil for %s", entry.Name())
				}
				remarshal(t, *document, &actual)
				declared = jsonFields(backupSummary{})
			case strings.HasPrefix(entry.Name(), "scrub-"):
				document := readScrubSummary(path)
				if document == nil {
					t.Fatalf("readScrubSummary returned nil for %s", entry.Name())
				}
				remarshal(t, *document, &actual)
				declared = jsonFields(scrubSummary{})
			case strings.HasPrefix(entry.Name(), "service-"):
				document := readSummary[serviceSummary](path)
				if document == nil {
					t.Fatalf("readSummary[serviceSummary] returned nil for %s", entry.Name())
				}
				remarshal(t, *document, &actual)
				declared = jsonFields(serviceSummary{})
			default:
				t.Fatalf("fixture %s matches no known document shape", entry.Name())
			}
			checked++
			for key, value := range expected {
				if !declared[key] {
					t.Errorf("field [%s] present in fixture but absent from the Go declaration", key)
					continue
				}
				got, present := actual[key]
				if !present {
					if !isZeroJSON(value) {
						t.Errorf("field [%s] dropped by the round trip, fixture has %v", key, value)
					}
					continue
				}
				if !equalJSON(value, got) {
					t.Errorf("field [%s] = %v, fixture has %v", key, got, value)
				}
			}
		})
	}
	if checked == 0 {
		t.Fatalf("no fixture matched a document shape, this test asserted nothing")
	}
}

func isZeroJSON(value any) bool {
	switch typed := value.(type) {
	case float64:
		return typed == 0
	case string:
		return typed == ""
	case bool:
		return !typed
	case nil:
		return true
	}
	return false
}

func remarshal(t *testing.T, document any, out *map[string]any) {
	t.Helper()
	data, err := json.Marshal(document)
	if err != nil {
		t.Fatalf("marshal: %v", err)
	}
	if err := json.Unmarshal(data, out); err != nil {
		t.Fatalf("unmarshal back to map: %v", err)
	}
}

func jsonFields(document any) map[string]bool {
	fields := map[string]bool{}
	kind := reflect.TypeOf(document)
	for field := range kind.Fields() {
		tag := field.Tag.Get("json")
		name, _, _ := strings.Cut(tag, ",")
		if name != "" {
			fields[name] = true
		}
	}
	return fields
}

func equalJSON(a, b any) bool {
	af, aok := a.(float64)
	bf, bok := b.(float64)
	if aok && bok {
		return af == bf
	}
	return a == b
}

func TestProbeUtilBackupSummary_WriteAtomicLeavesNoTemporaryBehind(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "status.json")
	if err := writeAtomic(path, backupSummary{RunID: "2026-09-22_01-00-00", State: "success", SuccessBool: true}); err != nil {
		t.Fatalf("writeAtomic() error = %v", err)
	}
	if _, err := os.Stat(path + ".tmp"); !os.IsNotExist(err) {
		t.Errorf("temporary file left behind: %v", err)
	}
	document := readBackupSummary(path)
	if document == nil || document.RunID != "2026-09-22_01-00-00" || document.State != "success" {
		t.Errorf("round trip mismatch: %+v", document)
	}
}

func TestProbeUtilBackupSummary_ResolvedState(t *testing.T) {
	tests := []struct {
		name     string
		stages   map[metric.BackupStage]string
		scrub    string
		expected string
	}{
		{name: "all_success_no_scrub", stages: map[metric.BackupStage]string{metric.BackupStagePrimary: metric.BackupStateSuccess, metric.BackupStageSecondary: metric.BackupStateSuccess, metric.BackupStageTertiary: metric.BackupStateSuccess}, expected: metric.BackupStateSuccess},
		{name: "any_stage_running_outranks_everything", stages: map[metric.BackupStage]string{metric.BackupStagePrimary: metric.BackupStateSuccess, metric.BackupStageSecondary: metric.BackupStateRunning}, scrub: metric.BackupStateFailure, expected: metric.BackupStateRunning},
		{name: "scrub_running_outranks_finished_stages", stages: map[metric.BackupStage]string{metric.BackupStagePrimary: metric.BackupStateSuccess, metric.BackupStageSecondary: metric.BackupStateSuccess, metric.BackupStageTertiary: metric.BackupStateSuccess}, scrub: metric.BackupStateRunning, expected: metric.BackupStateRunning},
		{name: "first_non_success_stage_in_declared_order", stages: map[metric.BackupStage]string{metric.BackupStagePrimary: metric.BackupStateSuccess, metric.BackupStageSecondary: metric.BackupStateFailure, metric.BackupStageTertiary: metric.BackupStateStopped}, expected: metric.BackupStateFailure},
		{name: "scrub_skipped_does_not_taint_success", stages: map[metric.BackupStage]string{metric.BackupStagePrimary: metric.BackupStateSuccess, metric.BackupStageSecondary: metric.BackupStateSuccess, metric.BackupStageTertiary: metric.BackupStateSuccess}, scrub: metric.BackupStateSkipped, expected: metric.BackupStateSuccess},
		{name: "scrub_failure_taints_an_otherwise_successful_run", stages: map[metric.BackupStage]string{metric.BackupStagePrimary: metric.BackupStateSuccess, metric.BackupStageSecondary: metric.BackupStateSuccess, metric.BackupStageTertiary: metric.BackupStateSuccess}, scrub: metric.BackupStateFailure, expected: metric.BackupStateFailure},
		{name: "no_stages_no_scrub", stages: map[metric.BackupStage]string{}, expected: metric.BackupStateSuccess},
		{name: "a_skipped_stage_does_not_taint_success", stages: map[metric.BackupStage]string{metric.BackupStagePrimary: metric.BackupStateSuccess, metric.BackupStageSecondary: metric.BackupStateSuccess, metric.BackupStageTertiary: metric.BackupStateSkipped}, expected: metric.BackupStateSuccess},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			if got := resolvedState(testCase.stages, testCase.scrub); got != testCase.expected {
				t.Errorf("resolvedState() = %q, want %q", got, testCase.expected)
			}
		})
	}
}

func TestProbeUtilBackupSummary_ResolvedStateInvariantsHoldAcrossEveryCombination(t *testing.T) {
	words := []string{"", metric.BackupStateRunning, metric.BackupStateSuccess, metric.BackupStateSkipped,
		metric.BackupStateStopped, metric.BackupStateTimeout, metric.BackupStateFailure}
	for _, primary := range words {
		for _, secondary := range words {
			for _, tertiary := range words {
				for _, scrub := range words {
					stages := map[metric.BackupStage]string{}
					if primary != "" {
						stages[metric.BackupStagePrimary] = primary
					}
					if secondary != "" {
						stages[metric.BackupStageSecondary] = secondary
					}
					if tertiary != "" {
						stages[metric.BackupStageTertiary] = tertiary
					}
					result := resolvedState(stages, scrub)

					anyRunning := primary == metric.BackupStateRunning || secondary == metric.BackupStateRunning ||
						tertiary == metric.BackupStateRunning || scrub == metric.BackupStateRunning
					if anyRunning && result != metric.BackupStateRunning {
						t.Fatalf("primary=%q secondary=%q tertiary=%q scrub=%q: got %q, want running whenever any stage or scrub is running",
							primary, secondary, tertiary, scrub, result)
					}
					if !anyRunning {
						clean := func(state string) bool {
							return state == "" || state == metric.BackupStateSuccess || state == metric.BackupStateSkipped
						}
						allClean := clean(primary) && clean(secondary) && clean(tertiary) &&
							clean(scrub)
						if allClean && result != metric.BackupStateSuccess {
							t.Fatalf("primary=%q secondary=%q tertiary=%q scrub=%q: got %q, want success when every stage succeeded or skipped and scrub was success or skipped",
								primary, secondary, tertiary, scrub, result)
						}
					}
				}
			}
		}
	}
}

func TestProbeUtilBackupSummary_Terminal(t *testing.T) {
	tests := []struct {
		state    string
		expected bool
	}{
		{state: "", expected: false},
		{state: metric.BackupStateRunning, expected: false},
		{state: metric.BackupStateSuccess, expected: true},
		{state: metric.BackupStateStopped, expected: true},
		{state: metric.BackupStateTimeout, expected: true},
		{state: metric.BackupStateFailure, expected: true},
		{state: metric.BackupStateSkipped, expected: true},
	}
	for _, testCase := range tests {
		t.Run(testCase.state+"_expected", func(t *testing.T) {
			if got := backupTerminal(testCase.state); got != testCase.expected {
				t.Errorf("backupTerminal(%q) = %v, want %v", testCase.state, got, testCase.expected)
			}
		})
	}
}

func TestProbeUtilBackupSummary_RunStarted(t *testing.T) {
	tests := []struct {
		name       string
		document   backupSummary
		expectedOK bool
		expectYear int
	}{
		{name: "run_id_stamp", document: backupSummary{RunID: "2026-09-22_01-00-00"}, expectedOK: true, expectYear: 2026},
		{name: "falls_back_to_started_ts", document: backupSummary{RunID: "not-a-timestamp", StartedTS: "2026-09-22T01:00:00+08:00"}, expectedOK: true, expectYear: 2026},
		{name: "neither_parses", document: backupSummary{RunID: "not-a-timestamp", StartedTS: "also-not-a-timestamp"}, expectedOK: false},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			started, ok := runStarted(testCase.document)
			if ok != testCase.expectedOK {
				t.Fatalf("runStarted() ok = %v, want %v", ok, testCase.expectedOK)
			}
			if ok && started.Year() != testCase.expectYear {
				t.Errorf("runStarted() year = %d, want %d", started.Year(), testCase.expectYear)
			}
		})
	}
}

func TestProbeUtilBackupSummary_ReportedForRun(t *testing.T) {
	earliest := time.Date(2026, 9, 22, 1, 0, 0, 0, time.UTC)
	tests := []struct {
		name     string
		document backupSummary
		expected bool
	}{
		{name: "after_earliest", document: backupSummary{StartedTS: earliest.Add(time.Minute).Format(time.RFC3339)}, expected: true},
		{name: "equal_to_earliest", document: backupSummary{StartedTS: earliest.Format(time.RFC3339)}, expected: true},
		{name: "before_earliest", document: backupSummary{StartedTS: earliest.Add(-time.Minute).Format(time.RFC3339)}, expected: false},
		{name: "unparseable", document: backupSummary{StartedTS: "not-a-timestamp"}, expected: false},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			if got := reportedForRun(testCase.document, earliest); got != testCase.expected {
				t.Errorf("reportedForRun() = %v, want %v", got, testCase.expected)
			}
		})
	}
}

func TestProbeUtilBackupSummary_FinishRunRollsUpEveryStageItFinds(t *testing.T) {
	root := t.TempDir()
	run := "2026-09-22_01-00-00"
	runPath := backupRunPath(root, run)
	staged := map[metric.BackupStage]backupSummary{
		metric.BackupStagePrimary: {State: metric.BackupStateSuccess, Trigger: metric.BackupTriggerSystem,
			FileCount: 4, SizeMB: 40, FilesCreated: 4, SentMB: 41},
		metric.BackupStageSecondary: {State: metric.BackupStateStopped, Trigger: metric.BackupTriggerSystem,
			FileCount: 2, SizeMB: 20, FilesDeleted: 1, SentMB: 21},
		metric.BackupStageTertiary: {State: metric.BackupStateSuccess, Trigger: metric.BackupTriggerSystem,
			FileCount: 1, SizeMB: 10, DiskUsagePerc: 61.5, FilesHeld: 9, SizeHeldMB: 90},
	}
	for stage, document := range staged {
		if err := os.MkdirAll(stageDir(runPath, stage), 0o755); err != nil {
			t.Fatalf("mkdir [%s]: %v", stage, err)
		}
		if err := writeAtomic(stageStatusPath(runPath, stage), document); err != nil {
			t.Fatalf("write [%s]: %v", stage, err)
		}
	}
	started := time.Now().Add(-90 * time.Second)
	document := finishRun(root, run, started)

	if document.State != metric.BackupStateStopped || document.SuccessBool {
		t.Errorf("state = (%q, %t), want the first stage that was not a success", document.State, document.SuccessBool)
	}
	if document.StagesRun != 3 || document.StagesHalted != 1 || document.StagesFailed != 0 {
		t.Errorf("stages run [%d] halted [%d] failed [%d], want 3, 1 and 0",
			document.StagesRun, document.StagesHalted, document.StagesFailed)
	}
	if document.FileCount != 7 || document.SizeMB != 70 || document.SentMB != 62 {
		t.Errorf("files [%d] size [%d] sent [%d], want the sum of every stage", document.FileCount, document.SizeMB, document.SentMB)
	}
	if document.FilesCreated != 4 || document.FilesDeleted != 1 {
		t.Errorf("created [%d] deleted [%d], want the sum of every stage", document.FilesCreated, document.FilesDeleted)
	}
	if document.DiskUsagePerc != 61.5 || document.FilesHeld != 9 || document.SizeHeldMB != 90 {
		t.Errorf("disk [%.1f] held [%d] files of [%d] MiB, want the tertiary stage's own reading",
			document.DiskUsagePerc, document.FilesHeld, document.SizeHeldMB)
	}
	if document.Trigger != metric.BackupTriggerSystem {
		t.Errorf("trigger = %q, want it filled from the first stage carrying one", document.Trigger)
	}
	if document.RunID != run || document.DurationS < 90 {
		t.Errorf("run [%q] lasted [%d] seconds, want [%q] and at least 90", document.RunID, document.DurationS, run)
	}
	if reread := readBackupSummary(statusPath(runPath)); reread == nil || reread.State != document.State {
		t.Errorf("the roll-up was not written to [%s]", statusPath(runPath))
	}
}

func TestProbeUtilBackupSummary_FinishRunOverAStageThatWroteNothing(t *testing.T) {
	root := t.TempDir()
	run := "2026-09-22_01-00-00"
	if err := os.MkdirAll(backupRunPath(root, run), 0o755); err != nil {
		t.Fatalf("mkdir run: %v", err)
	}
	document := finishRun(root, run, time.Now())
	if document.StagesRun != 0 || document.State != metric.BackupStateFailure {
		t.Errorf("state = (%q, %d stages), want a failure rather than a success over nothing",
			document.State, document.StagesRun)
	}
}

func TestProbeUtilBackupSummary_ASkippedStageIsNeitherFailedNorHalted(t *testing.T) {
	root, run := t.TempDir(), "2026-09-22_01-00-00"
	states := map[metric.BackupStage]string{
		metric.BackupStagePrimary:   metric.BackupStateSuccess,
		metric.BackupStageSecondary: metric.BackupStateSuccess,
		metric.BackupStageTertiary:  metric.BackupStateSkipped,
	}
	for stage, state := range states {
		path := stageStatusPath(backupRunPath(root, run), stage)
		if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
			t.Fatalf("mkdir stage: %v", err)
		}
		if err := writeAtomic(path, backupSummary{RunID: run, State: state, Trigger: metric.BackupTriggerSystem}); err != nil {
			t.Fatalf("write stage: %v", err)
		}
	}
	document := finishRun(root, run, time.Now())
	if document.StagesRun != 3 || document.StagesFailed != 0 || document.StagesHalted != 0 {
		t.Errorf("finishRun() = (run %d, failed %d, halted %d), want a host mirroring nowhere to read no fault",
			document.StagesRun, document.StagesFailed, document.StagesHalted)
	}
	if document.State != metric.BackupStateSuccess {
		t.Errorf("finishRun() state = %q, want %q", document.State, metric.BackupStateSuccess)
	}
}
