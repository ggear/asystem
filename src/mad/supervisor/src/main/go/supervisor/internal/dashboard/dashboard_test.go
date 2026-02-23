package dashboard

import (
	"fmt"
	"log/slog"
	"strings"
	"supervisor/internal/metric"
	"supervisor/internal/probe"
	"supervisor/internal/scribe"
	"testing"
	"time"

	"github.com/divan/num2words"
)

var (
	compact      = compactDashboardLayout()
	compactRows1 = rows(compact, 1)
	compactRows3 = rows(compact, 3)
	compactRows6 = rows(compact, 6)
	compactCols1 = columns(compact, 1)
	compactCols3 = columns(compact, 3)
	compactCols6 = columns(compact, 6)
	compactRszs1 = resizes(compact, 1)
	compactRszs3 = resizes(compact, 3)
	compactRszs6 = resizes(compact, 6)

	relaxed      = relaxedDashboardLayout()
	relaxedRows1 = rows(relaxed, 1)
	relaxedRows3 = rows(relaxed, 3)
	relaxedRows6 = rows(relaxed, 6)
	relaxedCols1 = columns(relaxed, 1)
	relaxedCols3 = columns(relaxed, 3)
	relaxedCols6 = columns(relaxed, 6)
	relaxedRszs1 = resizes(relaxed, 1)
	relaxedRszs3 = resizes(relaxed, 3)
	relaxedRszs6 = resizes(relaxed, 6)

	hosts = func() []string {
		result := make([]string, 0, 6)
		for i := 1; i <= 9; i++ {
			result = append(result, "labnode-"+num2words.Convert(i))
		}
		return result
	}()
)

func TestDashboard(t *testing.T) {
	tests := []struct {
		name              string
		hosts             []string
		formats           []Format
		terminalDims      dimensions
		expectedDimsDelta dimensions
		expectedFormat    Format
		expectedError     bool
	}{
		{
			name:              "happy_compact_host1_rows+0_colsx0+0",
			hosts:             hosts[:1],
			formats:           []Format{FormatAuto, FormatCompact},
			terminalDims:      dimensions{compactRows1 + 0, compactCols1 + compactRszs1*0 + 0},
			expectedDimsDelta: dimensions{0, 0},
			expectedFormat:    FormatCompact,
			expectedError:     false,
		},
		{
			name:              "happy_compact_host1_rows+1_colsx8+2",
			hosts:             hosts[:1],
			formats:           []Format{FormatAuto, FormatCompact},
			terminalDims:      dimensions{compactRows1 + 1, compactCols1 + compactRszs1*8 + 1},
			expectedDimsDelta: dimensions{0, -1},
			expectedFormat:    FormatCompact,
			expectedError:     false,
		},
		{
			name:              "happy_compact_host3_rows+0_colsx0+0",
			hosts:             hosts[:3],
			formats:           []Format{FormatAuto, FormatCompact},
			terminalDims:      dimensions{compactRows3, compactCols3 + compactRszs3*0 + 0},
			expectedDimsDelta: dimensions{0, 0},
			expectedFormat:    FormatCompact,
			expectedError:     false,
		},
		{
			name:              "happy_compact_host3_rows+1_colsx0+7",
			hosts:             hosts[:3],
			formats:           []Format{FormatAuto, FormatCompact},
			terminalDims:      dimensions{compactRows3 + 2, compactCols3 + compactRszs3*0 + 7},
			expectedDimsDelta: dimensions{0, 0},
			expectedFormat:    FormatCompact,
			expectedError:     false,
		},
		{
			name:              "happy_compact_host3_rows+0_colsx1+0",
			hosts:             hosts[:3],
			formats:           []Format{FormatAuto, FormatCompact},
			terminalDims:      dimensions{compactRows3 + 0, compactCols3 + compactRszs3*1 + 0},
			expectedDimsDelta: dimensions{0, 0},
			expectedFormat:    FormatCompact,
			expectedError:     false,
		},
		{
			name:              "happy_compact_host3_rows+1_colsx1+0",
			hosts:             hosts[:3],
			formats:           []Format{FormatAuto, FormatCompact},
			terminalDims:      dimensions{compactRows3 + 1, compactCols3 + compactRszs3*1 + 0},
			expectedDimsDelta: dimensions{-1, 0},
			expectedFormat:    FormatCompact,
			expectedError:     false,
		},
		{
			name:              "happy_compact_host6_rows+0_colsx0+0",
			hosts:             hosts[:6],
			formats:           []Format{FormatAuto, FormatCompact},
			terminalDims:      dimensions{compactRows6 + 0, compactCols6 + compactRszs6*0 + 0},
			expectedDimsDelta: dimensions{0, 0},
			expectedFormat:    FormatCompact,
			expectedError:     false,
		},
		{
			name:              "happy_compact_host6_rows+0_colsx0+2",
			hosts:             hosts[:6],
			formats:           []Format{FormatAuto, FormatCompact},
			terminalDims:      dimensions{compactRows6 + 0, compactCols6 + compactRszs6*0 + 2},
			expectedDimsDelta: dimensions{0, 0},
			expectedFormat:    FormatCompact,
			expectedError:     false,
		},
		{
			name:              "happy_compact_host6_rows+0_colsx0+7",
			hosts:             hosts[:6],
			formats:           []Format{FormatAuto, FormatCompact},
			terminalDims:      dimensions{compactRows6 + 0, compactCols6 + compactRszs6*0 + 7},
			expectedDimsDelta: dimensions{0, 0},
			expectedFormat:    FormatCompact,
			expectedError:     false,
		},
		{
			name:              "happy_compact_host6_rows+0_colsx1+0",
			hosts:             hosts[:6],
			formats:           []Format{FormatAuto, FormatCompact},
			terminalDims:      dimensions{compactRows6 + 0, compactCols6 + compactRszs6*1 + 0},
			expectedDimsDelta: dimensions{0, 0},
			expectedFormat:    FormatCompact,
			expectedError:     false,
		},
		{
			name:              "happy_compact_host6_rows+0_colsx10+0",
			hosts:             hosts[:6],
			formats:           []Format{FormatAuto, FormatCompact},
			terminalDims:      dimensions{compactRows6 + 7, compactCols6 + compactRszs6*7 + 5},
			expectedDimsDelta: dimensions{-1, 0},
			expectedFormat:    FormatCompact,
			expectedError:     false,
		},
		{
			name:              "happy_relaxed_host1_rows+0_colsx0+0",
			hosts:             hosts[:1],
			formats:           []Format{FormatAuto, FormatRelaxed},
			terminalDims:      dimensions{relaxedRows1 + 0, relaxedCols1 + relaxedRszs1*0 + 0},
			expectedDimsDelta: dimensions{0, 0},
			expectedFormat:    FormatRelaxed,
			expectedError:     false,
		},
		{
			name:              "happy_relaxed_host1_rows+1_colsx8+2",
			hosts:             hosts[:1],
			formats:           []Format{FormatAuto, FormatRelaxed},
			terminalDims:      dimensions{relaxedRows1 + 1, relaxedCols1 + relaxedRszs1*8 + 1},
			expectedDimsDelta: dimensions{0, -1},
			expectedFormat:    FormatRelaxed,
			expectedError:     false,
		},

		{
			name:              "happy_relaxed_host3_rows+0_colsx0+0",
			hosts:             hosts[:3],
			formats:           []Format{FormatAuto, FormatRelaxed},
			terminalDims:      dimensions{relaxedRows3, relaxedCols3 + relaxedRszs3*0 + 0},
			expectedDimsDelta: dimensions{0, 0},
			expectedFormat:    FormatRelaxed,
			expectedError:     false,
		},
		{
			name:              "happy_relaxed_host3_rows+1_colsx0+7",
			hosts:             hosts[:3],
			formats:           []Format{FormatAuto, FormatRelaxed},
			terminalDims:      dimensions{relaxedRows3 + 2, relaxedCols3 + relaxedRszs3*0 + 7},
			expectedDimsDelta: dimensions{0, 0},
			expectedFormat:    FormatRelaxed,
			expectedError:     false,
		},
		{
			name:              "happy_relaxed_host3_rows+0_colsx1+0",
			hosts:             hosts[:3],
			formats:           []Format{FormatAuto, FormatRelaxed},
			terminalDims:      dimensions{relaxedRows3 + 0, relaxedCols3 + relaxedRszs3*1 + 0},
			expectedDimsDelta: dimensions{0, 0},
			expectedFormat:    FormatRelaxed,
			expectedError:     false,
		},
		{
			name:              "happy_relaxed_host3_rows+1_colsx1+0",
			hosts:             hosts[:3],
			formats:           []Format{FormatAuto, FormatRelaxed},
			terminalDims:      dimensions{relaxedRows3 + 1, relaxedCols3 + relaxedRszs3*1 + 0},
			expectedDimsDelta: dimensions{-1, 0},
			expectedFormat:    FormatRelaxed,
			expectedError:     false,
		},
		{
			name:              "happy_relaxed_host6_rows+0_colsx0+0",
			hosts:             hosts[:6],
			formats:           []Format{FormatAuto, FormatRelaxed},
			terminalDims:      dimensions{relaxedRows6 + 0, relaxedCols6 + relaxedRszs6*0 + 0},
			expectedDimsDelta: dimensions{0, 0},
			expectedFormat:    FormatRelaxed,
			expectedError:     false,
		},
		{
			name:              "happy_relaxed_host6_rows+0_colsx0+2",
			hosts:             hosts[:6],
			formats:           []Format{FormatAuto, FormatRelaxed},
			terminalDims:      dimensions{relaxedRows6 + 0, relaxedCols6 + relaxedRszs6*0 + 2},
			expectedDimsDelta: dimensions{0, 0},
			expectedFormat:    FormatRelaxed,
			expectedError:     false,
		},
		{
			name:              "happy_relaxed_host6_rows+0_colsx0+7",
			hosts:             hosts[:6],
			formats:           []Format{FormatAuto, FormatRelaxed},
			terminalDims:      dimensions{relaxedRows6 + 0, relaxedCols6 + relaxedRszs6*0 + 7},
			expectedDimsDelta: dimensions{0, 0},
			expectedFormat:    FormatRelaxed,
			expectedError:     false,
		},
		{
			name:              "happy_relaxed_host6_rows+0_colsx1+0",
			hosts:             hosts[:6],
			formats:           []Format{FormatAuto, FormatRelaxed},
			terminalDims:      dimensions{relaxedRows6 + 0, relaxedCols6 + relaxedRszs6*1 + 0},
			expectedDimsDelta: dimensions{0, 0},
			expectedFormat:    FormatRelaxed,
			expectedError:     false,
		},
		{
			name:              "happy_relaxed_host6_rows+0_colsx20+2",
			hosts:             hosts[:6],
			formats:           []Format{FormatAuto, FormatRelaxed},
			terminalDims:      dimensions{relaxedRows6 + 0, relaxedCols6 + relaxedRszs6*20 + 2},
			expectedDimsDelta: dimensions{0, 0},
			expectedFormat:    FormatRelaxed,
			expectedError:     false,
		},
		{
			name:              "happy_relaxed_host6_rows+32_colsx20+5",
			hosts:             hosts[:6],
			formats:           []Format{FormatAuto, FormatRelaxed},
			terminalDims:      dimensions{relaxedRows6 + 32, relaxedCols6 + relaxedRszs6*20 + 5},
			expectedDimsDelta: dimensions{-2, 0},
			expectedFormat:    FormatRelaxed,
			expectedError:     false,
		},
		{
			name:          "sad_host1_rows-1_cols-1",
			hosts:         hosts[:1],
			formats:       []Format{FormatAuto, FormatRelaxed, FormatCompact},
			terminalDims:  dimensions{compactRows1 - 1, compactCols1 - 1},
			expectedError: true,
		},
		{
			name:          "sad_host3_rows-1_cols-1",
			hosts:         hosts[:3],
			formats:       []Format{FormatAuto, FormatRelaxed, FormatCompact},
			terminalDims:  dimensions{compactRows3 - 1, compactCols3 - 1},
			expectedError: true,
		},
		{
			name:          "sad_host6_rows-1_cols-1",
			hosts:         hosts[:6],
			formats:       []Format{FormatAuto, FormatRelaxed, FormatCompact},
			terminalDims:  dimensions{compactRows6 - 1, compactCols6 - 1},
			expectedError: true,
		},
		{
			name:          "sad_host0",
			hosts:         nil,
			formats:       []Format{FormatAuto, FormatRelaxed, FormatCompact},
			terminalDims:  dimensions{compactRows6, compactCols6},
			expectedError: true,
		},
	}
	for _, testCase := range tests {
		scribe.EnableStdout(slog.LevelDebug)
		t.Run(testCase.name, func(t *testing.T) {
			for _, attemptedFormat := range testCase.formats {
				fmt.Printf("Terminal [%dx%d] attempting [%s] ", testCase.terminalDims.cols, testCase.terminalDims.rows, attemptedFormat)
				terminal := newTerminalVirtual(testCase.terminalDims.rows, testCase.terminalDims.cols)
				dashboard, newErr := NewDashboard(
					metric.NewRecordCache(),
					func() (Terminal, error) { return terminal, nil },
					testCase.hosts,
					testCase.terminalDims.cols,
					testCase.terminalDims.rows,
					attemptedFormat,
					probe.Periods{},
					true,
				)
				if newErr != nil {
					t.Fatalf("New Dashboard err = %v, expected nil", newErr)
				}
				renderedFormat, compileErr := dashboard.Compile()
				if testCase.expectedError {
					if compileErr == nil {
						t.Fatalf("expected error but got nil")
					}
					return
				}
				if compileErr != nil {
					t.Fatalf("unexpected error: %v", compileErr)
				}
				if renderedFormat != testCase.expectedFormat {
					t.Fatalf("Compile Dashboard renderedFormat = %v, expected renderedFormat %v", renderedFormat, testCase.expectedFormat)
				}
				loadErr := dashboard.Load()
				if (loadErr != nil) != testCase.expectedError {
					fmt.Print("... failed\n")
					t.Fatalf("Load Dashboard err = %v, expected error? %t", loadErr, testCase.expectedError)
				}
				displayErr := dashboard.Display()
				if (displayErr != nil) != testCase.expectedError {
					fmt.Print("... failed\n")
					t.Fatalf("Display Dashboard err = %v, expected error? %t", displayErr, testCase.expectedError)
				}
				updateErrs := make(chan error, 1)
				go func() {
					updateErrs <- dashboard.Update()
				}()
				_ = dashboard.Close()
				select {
				case updateErr := <-updateErrs:
					if (updateErr != nil) != testCase.expectedError {
						fmt.Print("... failed\n")
						t.Fatalf("Update Dashboard err = %v, expected error? %t", updateErr, testCase.expectedError)
					}
				case <-time.After(250 * time.Millisecond):
					fmt.Print("... failed\n")
					t.Fatalf("Update Dashboard did not return after close")
				}
				dims := terminal.dimensions()
				fmt.Printf("-> Dashboard [%dx%d] rendered [%s]:\n", dims.cols, dims.rows, renderedFormat)
				fmt.Print(terminal.string(true))
				expectedDims := dimensions{
					testCase.expectedDimsDelta.rows + testCase.terminalDims.rows,
					testCase.expectedDimsDelta.cols + testCase.terminalDims.cols,
				}
				if dims != expectedDims {
					t.Fatalf("Got dims = %q, expected %q", dims, expectedDims)
				}
			}
		})
	}
}

func TestDashboard_VirtualTerminal(t *testing.T) {
	tests := []struct {
		name          string
		text          string
		colour        colour
		expectedError bool
	}{
		{
			name:          "happy_string",
			text:          "Hello world!",
			colour:        colourDefault,
			expectedError: false,
		},
		{
			name:          "happy_percentage",
			text:          "60%",
			colour:        colourYellow,
			expectedError: false,
		},
		{
			name:          "happy_bar_unicode",
			text:          "[███  ]  60%",
			colour:        colourYellow,
			expectedError: false,
		},
		{
			name:          "happy_bar_ascii",
			text:          "[###  ]  60%",
			colour:        colourYellow,
			expectedError: false,
		},
		{
			name:          "happy_tick_unicode",
			text:          "✔",
			colour:        colourGreen,
			expectedError: false,
		},
		{
			name:          "happy_tick_ascii",
			text:          "O",
			colour:        colourGreen,
			expectedError: false,
		},
		{
			name:          "happy_cross_unicode",
			text:          "✖",
			colour:        colourRed,
			expectedError: false,
		},
		{
			name:          "happy_cross_ascii",
			text:          "X",
			colour:        colourRed,
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
			base:        "string",
			prefixCount: 2,
			suffixCount: 2,
			length:      6,
			expected:    "stngst",
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

func TestDashboard_Pad(t *testing.T) {
	tests := []struct {
		name     string
		base     string
		align    boxAlign
		length   int
		expected string
	}{
		{
			name:     "happy_left_align",
			base:     "abc",
			align:    boxLhs,
			length:   5,
			expected: "abc  ",
		},
		{
			name:     "happy_right_align",
			base:     "abc",
			align:    boxRhs,
			length:   5,
			expected: "  abc",
		},
		{
			name:     "happy_no_padding",
			base:     "abc",
			align:    boxLhs,
			length:   3,
			expected: "abc",
		},
		{
			name:     "happy_mid_align_hostname",
			base:     "node-one",
			align:    boxMid,
			length:   11,
			expected: " node-one  ",
		},
		{
			name:     "happy_mid_align_even_padding",
			base:     "abc",
			align:    boxMid,
			length:   7,
			expected: "  abc  ",
		},
		{
			name:     "happy_mid_align_odd_padding",
			base:     "abc",
			align:    boxMid,
			length:   6,
			expected: " abc  ",
		},
		{
			name:     "happy_truncate",
			base:     "abcdefg",
			align:    boxLhs,
			length:   6,
			expected: "abcde~",
		},
		{
			name:     "happy_truncate_short_length",
			base:     "abcdefg",
			align:    boxLhs,
			length:   2,
			expected: "a~",
		},
		{
			name:     "happy_empty_base",
			base:     "",
			align:    boxLhs,
			length:   4,
			expected: "    ",
		},
		{
			name:     "happy_zero_length",
			base:     "abc",
			align:    boxLhs,
			length:   0,
			expected: "",
		},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			rendered := pad(testCase.base, testCase.align, testCase.length)
			if rendered != testCase.expected {
				t.Fatalf("Got render = %q, expected %q", rendered, testCase.expected)
			}
		})
	}
}

func TestDashboard_Highlight(t *testing.T) {
	tests := []struct {
		name     string
		pulse    *bool
		trend    *bool
		expected colour
	}{
		{
			name:     "happy_pulse_trend",
			pulse:    boolPtr(true),
			trend:    boolPtr(true),
			expected: colourGreen,
		},
		{
			name:     "happy_pulse_only",
			pulse:    boolPtr(true),
			trend:    boolPtr(false),
			expected: colourYellow,
		},
		{
			name:     "happy_no_pulse",
			pulse:    boolPtr(false),
			trend:    boolPtr(true),
			expected: colourRed,
		},
		{
			name:     "happy_no_pulse_no_trend",
			pulse:    boolPtr(false),
			trend:    boolPtr(false),
			expected: colourRed,
		},
		{
			name:     "happy_nil_pulse",
			pulse:    nil,
			trend:    boolPtr(true),
			expected: colourDefault,
		},
		{
			name:     "happy_nil_trend",
			pulse:    boolPtr(true),
			trend:    nil,
			expected: colourDefault,
		},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			rendered := highlight(testCase.pulse, testCase.trend)
			if rendered != testCase.expected {
				t.Fatalf("Got render = %v, expected %v", rendered, testCase.expected)
			}
		})
	}
}

func boolPtr(value bool) *bool {
	return &value
}
