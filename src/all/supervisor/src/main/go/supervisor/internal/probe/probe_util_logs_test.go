package probe

import (
	"fmt"
	"os"
	"path/filepath"
	"regexp"
	"strings"
	"testing"
	"time"
)

func TestProbeUtilLogs_IsLogError(t *testing.T) {
	tests := []struct {
		name       string
		priority   int
		message    string
		expectedOK bool
	}{
		{
			name:       "happy_kernel_error_level",
			priority:   3,
			message:    "ata1.00: failed command",
			expectedOK: true,
		},
		{
			name:       "happy_kernel_critical_level",
			priority:   2,
			message:    "thermal shutdown imminent",
			expectedOK: true,
		},
		{
			name:       "happy_facility_bits_ignored",
			priority:   11,
			message:    "ata1.00: failed command",
			expectedOK: true,
		},
		{
			name:       "happy_warning_naming_an_error",
			priority:   4,
			message:    "EXT4-fs warning: Error reading block",
			expectedOK: true,
		},
		{
			name:       "happy_info_level_ignored",
			priority:   6,
			message:    "usb 1-1: new high-speed USB device",
			expectedOK: false,
		},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			ok := isLogError(testCase.priority, testCase.message)
			if ok != testCase.expectedOK {
				t.Fatalf("isLogError: got %v want %v", ok, testCase.expectedOK)
			}
		})
	}
}

func TestProbeUtilLogs_IgnoredMessages(t *testing.T) {
	original := logIgnore
	t.Cleanup(func() { logIgnore = original })
	logIgnore = []*regexp.Regexp{
		regexp.MustCompile(`pl2303 ttyUSB\d+: pl2303_get_line_request - failed`),
		regexp.MustCompile(`usb \d+-\d+: device descriptor read`),
	}
	tests := []struct {
		name       string
		message    string
		expectedOK bool
	}{
		{
			name:       "happy_first_pattern_matches",
			message:    "pl2303 ttyUSB0: pl2303_get_line_request - failed with -32",
			expectedOK: true,
		},
		{
			name:       "happy_second_pattern_matches",
			message:    "usb 1-1: device descriptor read/64, error -71",
			expectedOK: true,
		},
		{
			name:       "happy_unrelated_error_kept",
			message:    "ata1.00: failed command: READ FPDMA QUEUED",
			expectedOK: false,
		},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			if logIgnoring(testCase.message) != testCase.expectedOK {
				t.Fatalf("logIgnoring: got %v want %v", !testCase.expectedOK, testCase.expectedOK)
			}
		})
	}
}

func TestProbeUtilLogs_IgnoredMessagesAreNotErrors(t *testing.T) {
	original := logIgnore
	t.Cleanup(func() { logIgnore = original })
	logIgnore = []*regexp.Regexp{regexp.MustCompile(`pl2303 ttyUSB\d+: pl2303_get_line_request - failed`)}
	if isLogError(3, "pl2303 ttyUSB0: pl2303_get_line_request - failed with -32") {
		t.Fatalf("isLogError on an ignored message: got true want false")
	}
	if !isLogError(3, "ata1.00: failed command") {
		t.Fatalf("isLogError on a kept message: got false want true")
	}
}

func TestProbeUtilLogs_AnOOMKillCountsOnceAndItsStackDumpNotAtAll(t *testing.T) {
	captured := `CPU: 8 UID: 0 PID: 1327866 Comm: polars-0 Tainted: G S                 6.14.2-401.asahi.fc42.aarch64+16k #1
Tainted: [S]=CPU_OUT_OF_SPEC
Hardware name: Apple Mac mini (M2 Pro, 2023) (DT)
Call trace:
show_stack+0x30/0x98 (C)
dump_stack_lvl+0x7c/0xa0
dump_stack+0x18/0x2c
dump_header+0x48/0x190
oom_kill_process+0x2ac/0x350
out_of_memory+0xdc/0x350
mem_cgroup_out_of_memory+0x138/0x160
try_charge_memcg+0x3fc/0x6c0
charge_memcg+0x4c/0xa0
mem_cgroup_swapin_charge_folio+0x74/0x1c8
__read_swap_cache_async+0x27c/0x308
swap_vma_readahead+0x240/0x4a8
swapin_readahead+0x88/0x180
do_swap_page+0x56c/0xd60
handle_pte_fault+0x188/0x220
__handle_mm_fault+0x1b0/0x420
handle_mm_fault+0xbc/0x340
do_page_fault+0x148/0x630
do_translation_fault+0x54/0xa0
do_mem_abort+0x48/0xa0
el0_da+0x3c/0x160
el0t_64_sync_handler+0xc4/0x140
el0t_64_sync+0x1b0/0x1b8
Memory cgroup out of memory: Killed process 1327212 (wrangle) total-vm:8633456kB, anon-rss:2049920kB, file-rss:31008kB, shmem-rss:0kB, UID:0 pgtables:3520kB oom_score_adj:0
CIFS: VFS: \\macmini-max\share-20 Close interrupted close
CIFS: VFS: \\macmini-max\share-20 Close interrupted close`
	var counted []string
	for line := range strings.SplitSeq(captured, "\n") {
		if isLogError(3, line) {
			counted = append(counted, line)
		}
	}
	if len(counted) != 1 || !strings.HasPrefix(counted[0], "Memory cgroup out of memory: Killed process") {
		t.Errorf("counted %q, want the OOM kill alone", counted)
	}
	for _, kept := range []string{
		"BUG: kernel NULL pointer dereference, address: 0000000000000008",
		"WARNING: CPU: 3 PID: 1 at mm/page_alloc.c:4416 __alloc_pages+0x2d0/0x3c0",
		"systemd-journald[637]: Failed to create new system journal: No space left on device",
		"CIFS: VFS: \\\\macmini-max\\share-20 error -5 on ioctl to get interface list",
	} {
		if !isLogError(3, kept) {
			t.Errorf("isLogError(%q) = false, want a headline or a real share fault still counted", kept)
		}
	}
	if warning := "BTRFS warning (device sdd1): read-write for sector size 4096 with page size 16384 is experimental"; isLogError(4, warning) {
		t.Errorf("isLogError(4, %q) = true, want a warning-priority line without the word error left uncounted", warning)
	}
}

func TestProbeUtilLogs_ParseLogRecord(t *testing.T) {
	boot := time.Now().Add(-time.Hour)
	tests := []struct {
		name            string
		line            string
		expectedMessage string
		expectedElapsed time.Duration
		expectedOK      bool
	}{
		{
			name:            "happy_error_record",
			line:            "3,2547,1500000000,-;ata1.00: failed command",
			expectedMessage: "ata1.00: failed command",
			expectedElapsed: 1500 * time.Second,
			expectedOK:      true,
		},
		{
			name:            "happy_continuation_line_skipped",
			line:            " SUBSYSTEM=acpi",
			expectedMessage: "",
			expectedElapsed: 0,
			expectedOK:      false,
		},
		{
			name:            "happy_info_record_skipped",
			line:            "6,2548,1600000000,-;usb 1-1: new device",
			expectedMessage: "",
			expectedElapsed: 0,
			expectedOK:      false,
		},
		{
			name:            "sad_malformed_record_skipped",
			line:            "not-a-record",
			expectedMessage: "",
			expectedElapsed: 0,
			expectedOK:      false,
		},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			timestamp, message, ok := parseLogRecord(testCase.line, boot)
			if ok != testCase.expectedOK {
				t.Fatalf("parseLogRecord ok: got %v want %v", ok, testCase.expectedOK)
			}
			if !ok {
				return
			}
			if message != testCase.expectedMessage {
				t.Fatalf("parseLogRecord message: got %q want %q", message, testCase.expectedMessage)
			}
			if elapsed := timestamp.Sub(boot); elapsed != testCase.expectedElapsed {
				t.Fatalf("parseLogRecord elapsed: got %v want %v", elapsed, testCase.expectedElapsed)
			}
		})
	}
}

func TestProbeUtilLogs_ErrorsWithin(t *testing.T) {
	tests := []struct {
		name            string
		records         []string
		uptimeSeconds   float64
		window          time.Duration
		expectedCount   int
		expectedPresent bool
	}{
		{
			name:            "happy_quiet_kernel",
			records:         []string{"6,1,1000000,-;usb 1-1: new device"},
			uptimeSeconds:   7200,
			window:          24 * time.Hour,
			expectedCount:   0,
			expectedPresent: true,
		},
		{
			name:            "happy_single_error",
			records:         []string{"3,1,1000000,-;ata1.00: failed command"},
			uptimeSeconds:   7200,
			window:          24 * time.Hour,
			expectedCount:   1,
			expectedPresent: true,
		},
		{
			name: "happy_several_errors_with_continuations",
			records: []string{
				"3,1,1000000,-;ata1.00: failed command",
				" SUBSYSTEM=block",
				"2,2,2000000,-;thermal shutdown imminent",
				"6,3,3000000,-;usb 1-1: new device",
			},
			uptimeSeconds:   7200,
			window:          24 * time.Hour,
			expectedCount:   2,
			expectedPresent: true,
		},
		{
			name: "happy_error_outside_window_evicted",
			records: []string{
				"3,1,1000000,-;ata1.00: failed command",
				"3,2,7000000000,-;ata1.00: failed command",
			},
			uptimeSeconds:   7200,
			window:          time.Hour,
			expectedCount:   1,
			expectedPresent: true,
		},
		{
			name:            "sad_kernel_log_absent",
			records:         nil,
			uptimeSeconds:   7200,
			window:          24 * time.Hour,
			expectedCount:   0,
			expectedPresent: false,
		},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			root := writeLogTree(t, testCase.records, testCase.uptimeSeconds)
			set := &logSet{roots: []string{root}, buffer: make([]byte, logBufferBytes)}
			t.Cleanup(set.close)
			count, present := set.errorsWithin(testCase.window)
			if present != testCase.expectedPresent {
				t.Fatalf("errorsWithin present: got %v want %v", present, testCase.expectedPresent)
			}
			if count != testCase.expectedCount {
				t.Fatalf("errorsWithin count: got %d want %d", count, testCase.expectedCount)
			}
		})
	}
}

func TestProbeUtilLogs_ErrorsWithinFollowsIncrementally(t *testing.T) {
	root := writeLogTree(t, []string{"3,1,1000000,-;ata1.00: failed command"}, 7200)
	set := &logSet{roots: []string{root}, buffer: make([]byte, logBufferBytes)}
	t.Cleanup(set.close)
	count, present := set.errorsWithin(24 * time.Hour)
	if !present || count != 1 {
		t.Fatalf("errorsWithin first: got %d present %v want 1 true", count, present)
	}
	appendLogRecords(t, root, []string{"3,2,2000000,-;ata1.00: failed command"})
	count, present = set.errorsWithin(24 * time.Hour)
	if !present || count != 2 {
		t.Fatalf("errorsWithin second: got %d present %v want 2 true", count, present)
	}
}

func writeLogTree(t *testing.T, records []string, uptimeSeconds float64) string {
	t.Helper()
	root := t.TempDir()
	if err := os.MkdirAll(filepath.Join(root, "proc"), 0o755); err != nil {
		t.Fatalf("write uptime dir: %v", err)
	}
	uptime := fmt.Sprintf("%.2f %.2f\n", uptimeSeconds, uptimeSeconds)
	if err := os.WriteFile(filepath.Join(root, logUptimePath), []byte(uptime), 0o644); err != nil {
		t.Fatalf("write uptime: %v", err)
	}
	if records == nil {
		return root
	}
	if err := os.MkdirAll(filepath.Join(root, "dev"), 0o755); err != nil {
		t.Fatalf("write kmsg dir: %v", err)
	}
	if err := os.WriteFile(filepath.Join(root, logDevicePath), []byte(joinLogRecords(records)), 0o644); err != nil {
		t.Fatalf("write kmsg: %v", err)
	}
	return root
}

func appendLogRecords(t *testing.T, root string, records []string) {
	t.Helper()
	file, err := os.OpenFile(filepath.Join(root, logDevicePath), os.O_APPEND|os.O_WRONLY, 0o644)
	if err != nil {
		t.Fatalf("append kmsg: %v", err)
	}
	defer func() { _ = file.Close() }()
	if _, err := file.WriteString(joinLogRecords(records)); err != nil {
		t.Fatalf("append kmsg: %v", err)
	}
}

func joinLogRecords(records []string) string {
	joined := ""
	for _, record := range records {
		joined += record + "\n"
	}
	return joined
}

func TestProbeUtilLogs_Suppression(t *testing.T) {
	tests := []struct {
		name          string
		message       string
		expected      string
		expectedError bool
	}{
		{
			name:          "happy_standalone_numbers_generalise",
			message:       "EXT4-fs warning: Error reading block 12345",
			expected:      "regexp.MustCompile(`^EXT4-fs warning: Error reading block \\d+`)",
			expectedError: false,
		},
		{
			name:          "happy_device_names_are_kept_whole",
			message:       "nvme0n1: I/O error, dev nvme0n1, sector 998",
			expected:      "regexp.MustCompile(`^nvme0n1: I/O error, dev nvme0n1, sector \\d+`)",
			expectedError: false,
		},
		{
			name:          "happy_delimited_numbers_generalise_but_identifiers_do_not",
			message:       "usb 1-1: device descriptor read/64, error -110",
			expected:      "regexp.MustCompile(`^usb \\d+-\\d+: device descriptor read/\\d+, error -\\d+`)",
			expectedError: false,
		},
		{
			name:          "happy_clipped_message_drops_its_ellipsis",
			message:       "mce: [Hardware Error]: Machine check events logged...",
			expected:      "regexp.MustCompile(`^mce: \\[Hardware Error\\]: Machine check events logged`)",
			expectedError: false,
		},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			if got := logSuppression(testCase.message); got != testCase.expected {
				t.Fatalf("logSuppression(%q):\n got %s\nwant %s", testCase.message, got, testCase.expected)
			}
		})
	}
}
