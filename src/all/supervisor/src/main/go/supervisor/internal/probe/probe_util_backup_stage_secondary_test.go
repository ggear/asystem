package probe

import (
	"fmt"
	"os"
	"path/filepath"
	"testing"
	"time"

	"supervisor/internal/config"
)

func TestProbeUtilBackupStageSecondary_RsyncFieldAgainstCapturedTertiaryMirror(t *testing.T) {
	output := fixtureStages(t, "rsync/output-tertiary-mirror.log")
	tests := []struct {
		prefix   string
		expected int
	}{
		{"Number of files: ", 14827},
		{"Number of created files: ", 27},
		{"Number of deleted files: ", 21},
		{"Number of regular files transferred: ", 22},
		{"Total file size: ", 1123246170567},
		{"Total transferred file size: ", 1355617},
		{"Total bytes sent: ", 1949185},
	}
	for _, testCase := range tests {
		if got := rsyncField(output, testCase.prefix); got != testCase.expected {
			t.Errorf("rsyncField(%q) = %d, want %d", testCase.prefix, got, testCase.expected)
		}
	}
}

func TestProbeUtilBackupStageSecondary_RsyncFieldMissingPrefixIsZero(t *testing.T) {
	if got := rsyncField("some unrelated output\n", "Number of files: "); got != 0 {
		t.Errorf("rsyncField() = %d, want 0", got)
	}
}

func TestProbeUtilBackupStageSecondary_OnlyDigitsStripsCommasAndUnits(t *testing.T) {
	tests := map[string]string{
		"9.44M":     "944",
		"1,355,617": "1355617",
		"":          "0",
		"no-digits": "0",
		"22":        "22",
	}
	for input, expected := range tests {
		if got := onlyDigits(input); got != expected {
			t.Errorf("onlyDigits(%q) = %q, want %q", input, got, expected)
		}
	}
}

func loadedWithKeep(t *testing.T, daily, weekly, monthly int) *config.Config {
	t.Helper()
	dir := t.TempDir()
	path := filepath.Join(dir, "config.json")
	body := fmt.Sprintf(`{"asystem":{"host":"testhost","backup":{"keep_daily":%d,"keep_weekly":%d,"keep_monthly":%d}}}`,
		daily, weekly, monthly)
	if err := os.WriteFile(path, []byte(body), 0644); err != nil {
		t.Fatalf("write config: %v", err)
	}
	return config.Load(path)
}

func TestProbeUtilBackupStageSecondary_GFSThinKeepsTheDailyWeeklyAndMonthlyWindows(t *testing.T) {
	dir := t.TempDir()
	var timestamps []string
	base := time.Date(2026, 8, 1, 1, 0, 0, 0, time.UTC)
	for day := range 40 {
		timestamp := base.AddDate(0, 0, day).Format(backupTimestampFormat)
		timestamps = append(timestamps, timestamp)
		if err := os.MkdirAll(filepath.Join(dir, timestamp), 0755); err != nil {
			t.Fatalf("mkdir: %v", err)
		}
	}

	gfsThin(t.Context(), dir, loadedWithKeep(t, 3, 2, 2))

	survived := map[string]bool{}
	remaining, err := os.ReadDir(dir)
	if err != nil {
		t.Fatalf("read dir: %v", err)
	}
	for _, entry := range remaining {
		survived[entry.Name()] = true
	}
	for _, timestamp := range timestamps[len(timestamps)-3:] {
		if !survived[timestamp] {
			t.Errorf("newest daily entry [%s] was pruned, the daily window must keep it", timestamp)
		}
	}
	weeks, months := map[string]bool{}, map[string]bool{}
	for name := range survived {
		parsed, err := time.Parse("2006-01-02", name[:10])
		if err != nil {
			t.Fatalf("survivor [%s] is not a run timestamp", name)
		}
		year, week := parsed.ISOWeek()
		weeks[fmt.Sprintf("%04d-%02d", year, week)] = true
		months[name[:7]] = true
	}
	if len(weeks) < 2 {
		t.Errorf("survivors span [%d] ISO weeks, want the weekly window to keep at least 2", len(weeks))
	}
	if len(months) < 2 {
		t.Errorf("survivors span [%d] months, want the monthly window to keep at least 2", len(months))
	}
	if len(survived) >= len(timestamps) {
		t.Errorf("survivors = %d, want fewer than the %d planted", len(survived), len(timestamps))
	}
	if len(survived) > 8 {
		t.Errorf("survivors = %d, want the three windows to bound it well below the %d planted", len(survived), len(timestamps))
	}
}

func TestProbeUtilBackupStageSecondary_GFSThinLeavesASingleEntryAlone(t *testing.T) {
	dir := t.TempDir()
	timestamp := "2026-09-22_01-00-00"
	if err := os.MkdirAll(filepath.Join(dir, timestamp), 0755); err != nil {
		t.Fatalf("mkdir: %v", err)
	}
	gfsThin(t.Context(), dir, loadedWithKeep(t, 1, 1, 1))
	if _, err := os.Stat(filepath.Join(dir, timestamp)); err != nil {
		t.Errorf("a single entry must never be pruned, count <= 1 is a no-op")
	}
}

func TestProbeUtilBackupStageSecondary_PromotionTargetScopesSupervisorByHost(t *testing.T) {
	tests := []struct {
		service  string
		expected string
	}{
		{service: "supervisor", expected: "/share/10/backup/supervisor/macmini-mad"},
		{service: "plex", expected: "/share/10/backup/plex"},
	}
	for _, testCase := range tests {
		if got := promotionTarget(testCase.service, "/share/10", "macmini-mad"); got != testCase.expected {
			t.Errorf("promotionTarget(%q) = %q, want %q", testCase.service, got, testCase.expected)
		}
	}
}

func TestProbeUtilBackupStageSecondary_GFSThinPrunesNothingWithNoDeclaredWindow(t *testing.T) {
	dir := t.TempDir()
	for _, name := range []string{"2026-01-01_01-00-00", "2026-02-01_01-00-00", "2026-03-01_01-00-00"} {
		if err := os.MkdirAll(filepath.Join(dir, name), 0o755); err != nil {
			t.Fatalf("mkdir %s: %v", name, err)
		}
	}
	gfsThin(t.Context(), dir, loadedWithKeep(t, 0, 0, 0))
	entries, err := os.ReadDir(dir)
	if err != nil {
		t.Fatalf("read dir: %v", err)
	}
	if len(entries) != 3 {
		t.Errorf("kept %d directories, want all 3 left alone when no window is declared", len(entries))
	}
}

func TestProbeUtilBackupStageSecondary_GFSThinPrunesNothingWithNoConfigAtAll(t *testing.T) {
	dir := t.TempDir()
	for _, name := range []string{"2026-01-01_01-00-00", "2026-02-01_01-00-00"} {
		if err := os.MkdirAll(filepath.Join(dir, name), 0o755); err != nil {
			t.Fatalf("mkdir %s: %v", name, err)
		}
	}
	gfsThin(t.Context(), dir, nil)
	entries, err := os.ReadDir(dir)
	if err != nil {
		t.Fatalf("read dir: %v", err)
	}
	if len(entries) != 2 {
		t.Errorf("kept %d directories, want both left alone against an unreadable config", len(entries))
	}
}

func TestProbeUtilBackupStageSecondary_GFSThinPrunesOnlyDatedDirectories(t *testing.T) {
	dir := t.TempDir()
	kept := []string{"latest", "2026-09", "20260922_010000", "notes.txt"}
	dated := []string{"2026-09-01_01-00-00", "2026-09-22_01-00-00"}
	for _, name := range append(append([]string{}, kept...), dated...) {
		if err := os.MkdirAll(filepath.Join(dir, name), 0o755); err != nil {
			t.Fatalf("mkdir [%s]: %v", name, err)
		}
	}
	gfsThin(t.Context(), dir, loadedWithKeep(t, 1, 0, 0))
	for _, name := range kept {
		if _, err := os.Stat(filepath.Join(dir, name)); err != nil {
			t.Errorf("[%s] was pruned, want a name outside the dated form left alone", name)
		}
	}
	if _, err := os.Stat(filepath.Join(dir, dated[1])); err != nil {
		t.Errorf("[%s] was pruned, want the newest dated directory kept by the daily window", dated[1])
	}
	if _, err := os.Stat(filepath.Join(dir, dated[0])); err == nil {
		t.Errorf("[%s] survived, want a dated directory outside every window pruned", dated[0])
	}
}
