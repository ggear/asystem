package dashboard

import (
	"fmt"
	"strings"
	"testing"
)

func TestDashboard(t *testing.T) {
	tests := []struct {
		name          string
		format        Format
		hosts         []string
		terminalDims  Dimensions
		expectedDims  Dimensions
		expectedError bool
	}{
		{
			name:          "happy_compact_1_host_1",
			format:        FormatCompact,
			hosts:         []string{"labnode-one"},
			terminalDims:  Dimensions{10 + 2, 58 + 6 + 2},
			expectedDims:  Dimensions{10 + 2, 58 + 6},
			expectedError: false,
		},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			terminal := newTerminalVirtual(testCase.terminalDims.Rows, testCase.terminalDims.Cols)
			dashboard, err := NewDashboard(nil, func() (Terminal, error) { return terminal, nil })
			if err != nil {
				t.Fatalf("Got err = %v, expected nil", err)
			}
			err = dashboard.Compile(testCase.hosts, testCase.terminalDims, testCase.format)
			if (err != nil) != testCase.expectedError {
				t.Fatalf("Got err = %v, expected error? %t", err, testCase.expectedError)
			}
			_ = dashboard.Create()

			// TODO: Fix?
			//dashboard.Update()

			dashboard.Close()

			// TODO: draw boxes, assert expectedDims rows/cols output

			// TODO:
			//   - Maybe make a dashboardTerminalVirtual.blocks() - tokenise on space, or double-space into strings, delimittered by "|", [][][] string return for assertions? compare to length of box's?

			fmt.Print(terminal.string(true))
		})
	}
}

func TestDashboard_TerminalVirtual(t *testing.T) {
	tests := []struct {
		name          string
		text          string
		colour        Colour
		expectedError bool
	}{
		{
			name:          "happy_string",
			text:          "Hello world!",
			colour:        ColourDefault,
			expectedError: false,
		},
		{
			name:          "happy_percentage",
			text:          "60%",
			colour:        ColourYellow,
			expectedError: false,
		},
		{
			name:          "happy_bar_unicode",
			text:          "[███  ]  60%",
			colour:        ColourYellow,
			expectedError: false,
		},
		{
			name:          "happy_bar_ascii",
			text:          "[###  ]  60%",
			colour:        ColourYellow,
			expectedError: false,
		},
		{
			name:          "happy_tick_unicode",
			text:          "✔",
			colour:        ColourGreen,
			expectedError: false,
		},
		{
			name:          "happy_tick_ascii",
			text:          "O",
			colour:        ColourGreen,
			expectedError: false,
		},
		{
			name:          "happy_cross_unicode",
			text:          "✖",
			colour:        ColourRed,
			expectedError: false,
		},
		{
			name:          "happy_cross_ascii",
			text:          "X",
			colour:        ColourRed,
			expectedError: false,
		},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			screen := newTerminalVirtual(1, 15)
			screen.draw(0, 0, testCase.text, testCase.colour)
			fmt.Print(screen.string(true))
			rendered := strings.TrimSpace(screen.string(false))
			if !testCase.expectedError && rendered != testCase.text {
				t.Fatalf("Got render = %q, expected %q", rendered, testCase.text)
			} else if testCase.expectedError && rendered == testCase.text {
				t.Fatalf("Got render = %q, expected not to be %q", rendered, testCase.text)
			}
		})
	}

}

func TestDashboard_Repeat(t *testing.T) {
	tests := []struct {
		name        string
		base        string
		prefixCount int
		suffixCount int
		length      int
		expected    string
	}{
		{
			name:        "happy_prefix_suffix",
			base:        "abcdef",
			prefixCount: 2,
			suffixCount: 2,
			length:      6,
			expected:    "abefab",
		},
		{
			name:        "happy_suffix_only",
			base:        "abcdef",
			prefixCount: 0,
			suffixCount: 2,
			length:      5,
			expected:    "efefe",
		},
		{
			name:        "happy_prefix_only",
			base:        "abcdef",
			prefixCount: 3,
			suffixCount: 0,
			length:      4,
			expected:    "abca",
		},
		{
			name:        "happy_counts_clamped",
			base:        "abcd",
			prefixCount: 3,
			suffixCount: 3,
			length:      5,
			expected:    "abcda",
		},
		{
			name:        "happy_negative_counts",
			base:        "abcd",
			prefixCount: -1,
			suffixCount: -2,
			length:      3,
			expected:    "",
		},
		{
			name:        "happy_zero_length",
			base:        "abcd",
			prefixCount: 1,
			suffixCount: 1,
			length:      0,
			expected:    "",
		},
		{
			name:        "happy_empty_base",
			base:        "",
			prefixCount: 1,
			suffixCount: 1,
			length:      3,
			expected:    "",
		},
		{
			name:        "happy_zero_slice",
			base:        "abcd",
			prefixCount: 0,
			suffixCount: 0,
			length:      3,
			expected:    "",
		},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			rendered := repeat(testCase.base, testCase.prefixCount, testCase.suffixCount, testCase.length)
			if rendered != testCase.expected {
				t.Fatalf("Got render = %q, expected %q", rendered, testCase.expected)
			}
		})
	}
}

func TestDashboard_Divider(t *testing.T) {
	tests := []struct {
		name     string
		base     string
		length   int
		expected string
	}{
		{
			name:     "happy_odd_length",
			base:     "|",
			length:   5,
			expected: "  |  ",
		},
		{
			name:     "happy_even_length",
			base:     "|",
			length:   6,
			expected: "  ||  ",
		},
		{
			name:     "happy_length_one",
			base:     "|",
			length:   1,
			expected: "|",
		},
		{
			name:     "happy_length_two",
			base:     "|",
			length:   2,
			expected: "||",
		},
		{
			name:     "happy_empty_base",
			base:     "",
			length:   3,
			expected: "",
		},
		{
			name:     "happy_zero_length",
			base:     "|",
			length:   0,
			expected: "",
		},
		{
			name:     "happy_base_first_rune_only",
			base:     "||",
			length:   3,
			expected: " | ",
		},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			rendered := divider(testCase.base, testCase.length)
			if rendered != testCase.expected {
				t.Fatalf("Got render = %q, expected %q", rendered, testCase.expected)
			}
		})
	}
}
