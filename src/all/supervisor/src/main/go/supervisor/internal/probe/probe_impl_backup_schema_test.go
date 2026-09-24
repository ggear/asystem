package probe

import (
	"encoding/json"
	"os"
	"path/filepath"
	"regexp"
	"slices"
	"sort"
	"strings"
	"supervisor/internal/metric"
	"supervisor/internal/schema"
	"testing"
	"time"
)

func declaredPayloadKeys(t *testing.T, match string) []string {
	t.Helper()
	for _, payload := range metric.Payloads() {
		if payload.Match != match {
			continue
		}
		var keys []string
		for _, member := range payload.Root.Members {
			keys = append(keys, member.Key)
		}
		sort.Strings(keys)
		return keys
	}
	t.Fatalf("declared payloads: got no entry matching %q, want one", match)
	return nil
}

func marshalledKeys(t *testing.T, data []byte) []string {
	t.Helper()
	var fields map[string]json.RawMessage
	if err := json.Unmarshal(data, &fields); err != nil {
		t.Fatalf("unmarshal: %v", err)
	}
	keys := make([]string, 0, len(fields))
	for key := range fields {
		keys = append(keys, key)
	}
	sort.Strings(keys)
	return keys
}

func TestProbeImplBackupSchema_ClusterDocumentWritesWhatItDeclares(t *testing.T) {
	document := backupClusterSummary{
		RunID: "2026-09-18_01-00-00", State: metric.BackupStateSuccess,
		StartedTS: time.Now().Format(time.RFC3339), FinishedTS: time.Now().Format(time.RFC3339),
		DurationS: 1, SuccessBool: true, PowerBool: true,
		HostsExpected: 2, HostsReported: 2, HostsFailed: 0,
		LeaderHost: "mad", LeaderEpoch: 7,
	}
	payload, err := json.Marshal(document)
	if err != nil {
		t.Fatalf("marshal: %v", err)
	}
	written := marshalledKeys(t, payload)
	declared := declaredPayloadKeys(t, "*/"+metric.HostAll+"/backup/status")
	if !slices.Equal(written, declared) {
		t.Errorf("cluster payload: got written %v want declared %v", written, declared)
	}
}

func TestProbeImplBackupSchema_HostDocumentWritesWhatItDeclares(t *testing.T) {
	root := t.TempDir()
	timestamp := time.Now().Format(backupTimestampFormat)
	states := map[metric.BackupStage]string{
		metric.BackupStagePrimary: metric.BackupStateFailure, metric.BackupStageSecondary: metric.BackupStateStopped,
		metric.BackupStageTertiary: metric.BackupStateSuccess,
	}
	for _, stage := range backupStages {
		writeBackupStage(t, root, timestamp, stage, backupSummary{
			State: states[stage], Trigger: metric.BackupTriggerSystem, SuccessBool: states[stage] == metric.BackupStateSuccess, DiskUsagePerc: 61,
			FileCount: 3, SizeMB: 4, FilesHeld: 5, FilesCreated: 6, FilesDeleted: 7,
			SizeHeldMB: 8, SentMB: 9,
		})
	}
	runPath := filepath.Join(root, timestamp)
	finishRun(root, timestamp, time.Now().Add(-time.Minute))
	data, err := os.ReadFile(filepath.Join(runPath, "status.json"))
	if err != nil {
		t.Fatalf("read run document: %v", err)
	}
	written := marshalledKeys(t, data)
	declared := declaredPayloadKeys(t, "*/backup/status")
	for _, key := range written {
		if !slices.Contains(declared, key) {
			t.Errorf("host payload: go writes undeclared key %q", key)
		}
	}
	if !slices.Equal(written, declared) {
		t.Errorf("host payload: got written %v want declared %v", written, declared)
	}
}

func TestProbeImplBackupSchema_ReapingAStageKeepsEveryFieldItCarried(t *testing.T) {
	root := t.TempDir()
	timestamp := time.Now().Format(backupTimestampFormat)
	carried := backupSummary{
		RunID: timestamp, State: metric.BackupStateRunning, Trigger: metric.BackupTriggerSystem,
		StartedTS: "s", FinishedTS: "f", ExpiresTS: "e", TimeoutHours: 3, DurationS: 2,
		SuccessBool: true, DiskUsagePerc: 61, DiskUsedMB: 11, DiskTotalMB: 22, DiskUncleanBool: true,
		TotalMB: 33, FileCount: 44, SizeMB: 55, FilesHeld: 66, FilesCreated: 77,
		FilesDeleted: 88, SizeHeldMB: 99, SentMB: 100,
	}
	writeBackupStage(t, root, timestamp, "primary", carried)
	runPath := filepath.Join(root, timestamp)
	reread := readBackupSummary(stageStatusPath(runPath, "primary"))
	if reread == nil {
		t.Fatal("read back: got nil, want the document just written")
	}
	stale := *reread
	stale.State = metric.BackupStateTimeout
	stale.ExpiresTS = ""
	_ = writeAtomic(stageStatusPath(runPath, "primary"), stale)
	data, err := os.ReadFile(stageStatusPath(runPath, "primary"))
	if err != nil {
		t.Fatalf("read reaped document: %v", err)
	}
	kept := marshalledKeys(t, data)
	for _, key := range declaredPayloadKeys(t, "*/backup/stage/*/status") {
		if key == "expires_ts" {
			continue
		}
		if !slices.Contains(kept, key) {
			t.Errorf("reaped stage document dropped %q, which the STAGE payload declares", key)
		}
	}
}

func TestProbeImplBackupSchema_DocumentedShapeMatchesTheDeclaration(t *testing.T) {
	source, err := os.ReadFile("probe_util_backup_summary.go")
	if err != nil {
		t.Fatalf("read probe_util_backup_summary.go: %v", err)
	}
	block := regexp.MustCompile(`(?s)//\t\{\n(.*?)//\t\}\n`).FindSubmatch(source)
	if block == nil {
		t.Fatal("found no documented shape on backupSummary, the parse has rotted")
	}
	documented := map[string][]string{}
	field := regexp.MustCompile(`"([a-z_]+)":\s*\S+?,?\s+((?:ALL|RUN|STAGE|SERVICE|SCRUB)(?: (?:ALL|RUN|STAGE|SERVICE|SCRUB))*)`)
	for _, line := range field.FindAllStringSubmatch(string(block[1]), -1) {
		names := strings.Fields(line[2])
		if slices.Contains(names, "ALL") {
			names = []string{"RUN", "STAGE", "SERVICE", "SCRUB"}
		}
		for _, name := range names {
			documented[name] = append(documented[name], line[1])
		}
	}
	if len(documented) != 4 {
		t.Fatalf("documented shape: got %d documents want 4, the parse has rotted", len(documented))
	}
	for name, match := range map[string]string{
		"RUN": "*/backup/status", "STAGE": "*/backup/stage/*/status",
		"SERVICE": "*/backup/stage/*/service/*/status", "SCRUB": "*/backup/stage/tertiary/scrub/status",
	} {
		keys := documented[name]
		sort.Strings(keys)
		if declared := declaredPayloadKeys(t, match); !slices.Equal(keys, declared) {
			t.Errorf("%s: got documented %v want declared %v", name, keys, declared)
		}
	}
}

func globPattern(glob string) *regexp.Regexp {
	parts := strings.Split(glob, "*")
	for index, part := range parts {
		parts[index] = regexp.QuoteMeta(part)
	}
	return regexp.MustCompile("^" + strings.Join(parts, ".*") + "$")
}

func TestProbeImplBackupSchema_EveryBackupTopicResolvesToItsOwnPayload(t *testing.T) {
	tests := []struct {
		name  string
		topic string
		match string
	}{
		{"cluster", metric.TopicBackupStatus(metric.HostAll), "*/" + metric.HostAll + "/backup/status"},
		{"host", metric.TopicBackupStatus("macmini-mad"), "*/backup/status"},
		{"stage", metric.TopicBackupStage("macmini-mad", "primary"), "*/backup/stage/*/status"},
		{"service", metric.TopicBackupService("macmini-mad", "plex"), "*/backup/stage/*/service/*/status"},
		{"scrub", metric.TopicBackupScrub("macmini-mad"), "*/backup/stage/tertiary/scrub/status"},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			resolved := ""
			for _, payload := range metric.Payloads() {
				if payload.Role != schema.RoleState || payload.Match == "" {
					continue
				}
				if globPattern(payload.Match).MatchString(tt.topic) {
					resolved = payload.Match
					break
				}
			}
			if resolved != tt.match {
				t.Errorf("topic %s: got payload %q want %q", tt.topic, resolved, tt.match)
			}
		})
	}
}
