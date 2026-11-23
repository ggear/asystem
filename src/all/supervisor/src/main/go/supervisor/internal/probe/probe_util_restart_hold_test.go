package probe

import (
	"os"
	"path/filepath"
	"testing"
)

func TestProbeUtilRestartHold_Held(t *testing.T) {
	tests := []struct {
		name         string
		content      *string
		expectedHeld bool
	}{
		{name: "no_record_holds_nothing", expectedHeld: false},
		{name: "an_empty_record_holds_nothing", content: new(""), expectedHeld: false},
		{name: "a_record_in_progress_holds_the_host", content: new("mode deep\ncontainer abc\n"), expectedHeld: true},
		{name: "a_completed_shed_still_holds_the_host", content: new("mode deep\ncontainer abc\ncomplete 1700000000 status 0 reason ok\n"), expectedHeld: true},
		{name: "a_failed_wake_that_kept_its_record_releases_the_host", content: new("mode deep\ncomplete 1700000000 status 0 reason ok\nawoke 1700000900 6\n"), expectedHeld: false},
		{name: "an_awoke_line_that_is_not_the_last_does_not_release_a_later_shed", content: new("awoke 1700000900 6\nmode deep\ncontainer abc\n"), expectedHeld: true},
		{name: "trailing_blank_lines_are_ignored", content: new("mode deep\nawoke 1700000900 6\n\n\n"), expectedHeld: false},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			path := filepath.Join(t.TempDir(), "asleep.state")
			if testCase.content != nil {
				if err := os.WriteFile(path, []byte(*testCase.content), 0o644); err != nil {
					t.Fatalf("write failed with [%v]", err)
				}
			}
			if got := restartHostHeld(path); got != testCase.expectedHeld {
				t.Fatalf("held: got %v want %v", got, testCase.expectedHeld)
			}
		})
	}
}
