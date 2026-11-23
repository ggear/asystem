package cmd

import (
	"bytes"
	"strings"
	"testing"
)

func TestCmdCompletion_BindsEachHostCommandToItsVerb(t *testing.T) {
	var out bytes.Buffer
	rootCmd.SetOut(&out)
	rootCmd.SetArgs([]string{"completion"})
	t.Cleanup(func() {
		rootCmd.SetOut(nil)
		rootCmd.SetArgs(nil)
	})
	Execute()
	script := out.String()
	tests := []struct {
		name     string
		expected string
	}{
		{name: "the storage completion", expected: "__start_storage()"},
		{name: "aspace completes space", expected: "_aspace() { __storage_alias space; }\ncomplete -o default -F _aspace aspace\n"},
		{name: "amount completes mount", expected: "_amount() { __storage_alias mount; }\ncomplete -o default -F _amount amount\n"},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			if !strings.Contains(script, testCase.expected) {
				t.Errorf("script: got %q want it to contain %q", script, testCase.expected)
			}
		})
	}
}
