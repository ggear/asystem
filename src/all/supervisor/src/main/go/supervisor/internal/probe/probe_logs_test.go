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

func TestProbeLogs_IsLogError(t *testing.T) {
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

func TestProbeLogs_IgnorePatternsAllCompile(t *testing.T) {
	declared := 0
	for _, pattern := range strings.Split(logIgnorePatterns, "\n") {
		if strings.TrimSpace(pattern) == "" {
			continue
		}
		declared++
		if _, err := regexp.Compile(strings.TrimSpace(pattern)); err != nil {
			t.Fatalf("logIgnorePatterns %q: %v", pattern, err)
		}
	}
	if len(logIgnore) != declared {
		t.Fatalf("logIgnore compiled: got %d want %d", len(logIgnore), declared)
	}
}

func TestProbeLogs_IgnoredMessages(t *testing.T) {
	patterns := compileLog(`
pl2303 ttyUSB\d+: pl2303_get_line_request - failed
usb \d+-\d+: device descriptor read
`)
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
			if matchedLog(patterns, testCase.message) != testCase.expectedOK {
				t.Fatalf("matchedLog: got %v want %v", !testCase.expectedOK, testCase.expectedOK)
			}
		})
	}
}

func TestProbeLogs_IgnoredMessagesAreNotErrors(t *testing.T) {
	original := logIgnore
	t.Cleanup(func() { logIgnore = original })
	logIgnore = compileLog("pl2303 ttyUSB\\d+: pl2303_get_line_request - failed")
	if isLogError(3, "pl2303 ttyUSB0: pl2303_get_line_request - failed with -32") {
		t.Fatalf("isLogError on an ignored message: got true want false")
	}
	if !isLogError(3, "ata1.00: failed command") {
		t.Fatalf("isLogError on a kept message: got false want true")
	}
}

func TestProbeLogs_ParseLogRecord(t *testing.T) {
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
			stamp, message, ok := parseLogRecord(testCase.line, boot)
			if ok != testCase.expectedOK {
				t.Fatalf("parseLogRecord ok: got %v want %v", ok, testCase.expectedOK)
			}
			if !ok {
				return
			}
			if message != testCase.expectedMessage {
				t.Fatalf("parseLogRecord message: got %q want %q", message, testCase.expectedMessage)
			}
			if elapsed := stamp.Sub(boot); elapsed != testCase.expectedElapsed {
				t.Fatalf("parseLogRecord elapsed: got %v want %v", elapsed, testCase.expectedElapsed)
			}
		})
	}
}

func TestProbeLogs_ErrorsWithin(t *testing.T) {
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

func TestProbeLogs_ErrorsWithinFollowsIncrementally(t *testing.T) {
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
