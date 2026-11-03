package probe

import (
	"testing"
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
