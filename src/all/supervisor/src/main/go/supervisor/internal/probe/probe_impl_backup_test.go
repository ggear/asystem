package probe

import (
	"encoding/json"
	"os"
	"path/filepath"
	"testing"
	"time"
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
		{"run abandoned beyond the ceiling reads fully failed", func(root string) {
			writeBackupStage(t, root, abandoned, "primary", backupDocument{State: "running"})
		}, 100, false, false},
		{"no runs reads fully failed", func(string) {}, 100, false, false},
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
			value, found := p.serviceSuccess(tt.service)
			if value != tt.wantValue || found != tt.wantFound {
				t.Errorf("got (%v,%v) want (%v,%v)", value, found, tt.wantValue, tt.wantFound)
			}
		})
	}
}

func TestProbeImplBackup_LeaseExpired(t *testing.T) {
	tests := []struct {
		name        string
		expiresTS   string
		wantExpired bool
	}{
		{"future is live", time.Now().Add(time.Hour).Format(time.RFC3339), false},
		{"past is expired", time.Now().Add(-time.Hour).Format(time.RFC3339), true},
		{"unparseable is expired", "not-a-time", true},
		{"empty is expired", "", true},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			if got := (backupLease{ExpiresTS: tt.expiresTS}).expired(); got != tt.wantExpired {
				t.Errorf("expired: got %v want %v", got, tt.wantExpired)
			}
		})
	}
}
