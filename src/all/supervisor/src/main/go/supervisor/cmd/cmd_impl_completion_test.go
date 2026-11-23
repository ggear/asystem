package cmd

import (
	"bytes"
	"strings"
	"testing"
)

func TestCmdImplCompletion_BindsEachHostCommandToItsVerb(t *testing.T) {
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
		{name: "the supervisor completion", expected: "__start_supervisor()"},
		{name: "atop completes watch", expected: "_atop() { __supervisor_alias watch; }\ncomplete -o default -F _atop atop\n"},
		{name: "atops completes watch", expected: "_atops() { __supervisor_alias watch; }\ncomplete -o default -F _atops atops\n"},
		{name: "abackup completes backup", expected: "_abackup() { __supervisor_alias backup; }\ncomplete -o default -F _abackup abackup\n"},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			if !strings.Contains(script, testCase.expected) {
				t.Errorf("script: got %q want it to contain %q", script, testCase.expected)
			}
		})
	}
}
