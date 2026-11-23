package display

import (
	"regexp"
	"strings"
	"testing"
)

func TestDisplay_LocalASCII(t *testing.T) {
	assertLayout(t, fixtureLocal(), false, displayLocalASCII)
}

func TestDisplay_LocalUnicode(t *testing.T) {
	assertLayout(t, fixtureLocal(), true, displayLocalUnicode)
}

func TestDisplay_LocalSharesASCII(t *testing.T) {
	assertLayout(t, fixtureLocalShares(), false, displayLocalSharesASCII)
}

func TestDisplay_LocalSharesUnicode(t *testing.T) {
	assertLayout(t, fixtureLocalShares(), true, displayLocalSharesUnicode)
}

func TestDisplay_RemoteASCII(t *testing.T) {
	assertLayout(t, fixtureRemote(), false, displayRemoteASCII)
}

func TestDisplay_RemoteUnicode(t *testing.T) {
	assertLayout(t, fixtureRemote(), true, displayRemoteUnicode)
}

func TestDisplay_UnmeasuredASCII(t *testing.T) {
	assertLayout(t, fixtureUnmeasured(), false, displayUnmeasuredASCII)
}

func TestDisplay_UnmeasuredUnicode(t *testing.T) {
	assertLayout(t, fixtureUnmeasured(), true, displayUnmeasuredUnicode)
}

func TestDisplay_SeverityBoundaries(t *testing.T) {
	tests := []struct {
		name           string
		percent        float64
		expectedColour string
		expectedError  bool
	}{
		{name: "empty is green", percent: 0.0, expectedColour: colourGreen},
		{name: "just below amber is green", percent: 79.9, expectedColour: colourGreen},
		{name: "the amber threshold is amber", percent: 80.0, expectedColour: colourAmber},
		{name: "just below red is amber", percent: 89.9, expectedColour: colourAmber},
		{name: "the red threshold is red", percent: 90.0, expectedColour: colourRed},
		{name: "full is red", percent: 100.0, expectedColour: colourRed},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			rows := []Row{{Host: "meg", Mount: "/", Percent: testCase.percent, NewBlock: true, NewGroup: true}}
			if got := ansiPattern.FindString(Render(rows, false, true)); got != testCase.expectedColour {
				t.Errorf("colour: got %q want %q", got, testCase.expectedColour)
			}
		})
	}
}

func TestDisplay_MonoHasNoEscapes(t *testing.T) {
	rendered := Render(fixtureRemote(), false, false)
	if strings.Contains(rendered, "\033") {
		t.Errorf("mono rendering contains an escape sequence")
	}
}

func TestDisplay_ColourStripsToMono(t *testing.T) {
	mono := Render(fixtureRemote(), false, false)
	colour := Render(fixtureRemote(), false, true)
	if stripped := ansiPattern.ReplaceAllString(colour, ""); stripped != mono {
		t.Errorf("colour rendering does not reduce to mono once escapes are stripped")
	}
}

func TestDisplay_ClipsRatherThanStretches(t *testing.T) {
	rows := []Row{
		{Host: "meg", Mount: "/", Size: tebibytes(123456.7), Free: tebibytes(0.1), Used: tebibytes(123456.6), Percent: 100.0, NewBlock: true, NewGroup: true},
		{Mount: "/share", Size: tebibytes(0.0), Free: tebibytes(0.0), Used: tebibytes(0.0), Percent: 0.0, NewGroup: true},
		{Mount: "/backup", Size: tebibytes(1.0), Free: tebibytes(0.0), Used: tebibytes(12345.0), Percent: 1234567.8, NewGroup: true},
	}
	rendered := Render(rows, false, false)
	lines := strings.Split(strings.TrimRight(rendered, "\n"), "\n")
	width := len([]rune(lines[0]))
	for _, line := range lines {
		if got := len([]rune(line)); got != width {
			t.Errorf("row width drifted [%d] want [%d] on line [%q]", got, width, line)
		}
	}
	if !strings.Contains(rendered, "...") {
		t.Errorf("an oversized value should be clipped with an ellipsis rather than widening the column")
	}
}

func tebibytes(value float64) uint64 {
	return uint64(value * (1 << 40))
}

func fixtureLocal() []Row {
	return []Row{
		{Host: "mad", Mount: "/", Size: tebibytes(0.6), Free: tebibytes(0.2), Used: tebibytes(0.4), Percent: 66.7, NewBlock: true, NewGroup: true},
		{Mount: "/share/10", Size: tebibytes(4.0), Free: tebibytes(1.0), Used: tebibytes(3.0), Percent: 75.0, NewGroup: true},
		{Mount: "/share/11", Size: tebibytes(4.0), Free: tebibytes(1.5), Used: tebibytes(2.5), Percent: 62.5},
		{Mount: "/share/12", Size: tebibytes(4.0), Free: tebibytes(1.2), Used: tebibytes(2.8), Percent: 70.0},
		{Mount: "/share", Size: tebibytes(12.0), Free: tebibytes(3.7), Used: tebibytes(8.3), Percent: 69.2},
		{Mount: "/backup", Size: tebibytes(24.0), Free: tebibytes(15.0), Used: tebibytes(9.0), Percent: 37.5, NewGroup: true},
	}
}

func fixtureLocalShares() []Row {
	return []Row{
		{Host: "mad", Mount: "/share/10", Size: tebibytes(4.0), Free: tebibytes(1.0), Used: tebibytes(3.0), Percent: 75.0, NewBlock: true, NewGroup: true},
		{Mount: "/share/11", Size: tebibytes(4.0), Free: tebibytes(1.5), Used: tebibytes(2.5), Percent: 62.5},
		{Mount: "/share/12", Size: tebibytes(4.0), Free: tebibytes(1.2), Used: tebibytes(2.8), Percent: 70.0},
	}
}

func fixtureUnmeasured() []Row {
	return []Row{
		{Host: "meg", Mount: "/", Size: tebibytes(0.6), Free: tebibytes(0.2), Used: tebibytes(0.4), Percent: 66.7, NewBlock: true, NewGroup: true},
		{Mount: "/share/41", Unmeasured: true, NewGroup: true},
		{Mount: "/share/42", Size: tebibytes(0.5), Free: tebibytes(0.1), Used: tebibytes(0.4), Percent: 80.0},
	}
}

func fixtureRemote() []Row {
	rows := []Row{{Host: "jen", Mount: "/", Size: tebibytes(0.2), Free: tebibytes(0.1), Used: tebibytes(0.1), Percent: 50.0, NewBlock: true, NewGroup: true}}
	rows = append(rows, fixtureLocal()...)
	rows = append(rows,
		Row{Host: "max", Mount: "/", Size: tebibytes(99.9), Free: tebibytes(0.0), Used: tebibytes(99.9), Percent: 100.0, NewBlock: true, NewGroup: true},
		Row{Mount: "/share/20", Size: tebibytes(2.0), Free: tebibytes(1.0), Used: tebibytes(1.0), Percent: 50.0, NewGroup: true},
		Row{Mount: "/share/21", Size: tebibytes(0.6), Free: tebibytes(0.2), Used: tebibytes(0.4), Percent: 66.7},
		Row{Mount: "/share", Size: tebibytes(2.6), Free: tebibytes(1.2), Used: tebibytes(1.4), Percent: 53.8},
		Row{Mount: "/backup", Size: tebibytes(4.0), Free: tebibytes(3.0), Used: tebibytes(1.0), Percent: 25.0, NewGroup: true},

		Row{Host: "may", Mount: "/", Size: tebibytes(0.6), Free: tebibytes(0.2), Used: tebibytes(0.4), Percent: 66.7, NewBlock: true, NewGroup: true},
		Row{Mount: "/share/30", Size: tebibytes(4.0), Free: tebibytes(2.0), Used: tebibytes(2.0), Percent: 50.0, NewGroup: true},
		Row{Mount: "/share/31", Size: tebibytes(4.0), Free: tebibytes(1.5), Used: tebibytes(2.5), Percent: 62.5},
		Row{Mount: "/share/32", Size: tebibytes(0.5), Free: tebibytes(0.1), Used: tebibytes(0.4), Percent: 80.0},
		Row{Mount: "/share", Size: tebibytes(8.5), Free: tebibytes(3.6), Used: tebibytes(4.9), Percent: 57.6},
		Row{Mount: "/backup", Size: tebibytes(10.0), Free: tebibytes(5.0), Used: tebibytes(5.0), Percent: 50.0, NewGroup: true},

		Row{Host: "meg", Mount: "/", Size: tebibytes(0.6), Free: tebibytes(0.2), Used: tebibytes(0.4), Percent: 66.7, NewBlock: true, NewGroup: true},
		Row{Mount: "/share/40", Size: tebibytes(1.5), Free: tebibytes(0.4), Used: tebibytes(1.1), Percent: 73.3, NewGroup: true},
		Row{Mount: "/share/41", Size: tebibytes(4.0), Free: tebibytes(0.8), Used: tebibytes(3.2), Percent: 80.0},
		Row{Mount: "/share/42", Size: tebibytes(0.5), Free: tebibytes(0.1), Used: tebibytes(0.4), Percent: 80.0},
		Row{Mount: "/share", Size: tebibytes(6.0), Free: tebibytes(1.3), Used: tebibytes(4.7), Percent: 78.3},
		Row{Mount: "/backup", Size: tebibytes(6.0), Free: tebibytes(1.4), Used: tebibytes(4.6), Percent: 76.7, NewGroup: true},

		Row{Mount: "/", Size: tebibytes(101.9), Free: tebibytes(0.7), Used: tebibytes(101.2), Percent: 99.3, NewBlock: true, NewGroup: true},
		Row{Mount: "/share", Size: tebibytes(29.1), Free: tebibytes(9.8), Used: tebibytes(19.3), Percent: 66.3, NewGroup: true},
		Row{Mount: "/backup", Size: tebibytes(44.0), Free: tebibytes(24.4), Used: tebibytes(19.6), Percent: 44.5, NewGroup: true},
		Row{Mount: "", Size: tebibytes(175.0), Free: tebibytes(34.9), Used: tebibytes(140.1), Percent: 80.1, NewGroup: true},
	)
	return rows
}

func assertLayout(t *testing.T, rows []Row, useUnicode bool, expected string) {
	t.Helper()
	got := Render(rows, useUnicode, false)
	if trimmed := strings.TrimPrefix(expected, "\n"); got != trimmed {
		t.Errorf("layout mismatch\ngot:\n%s\nwant:\n%s", got, trimmed)
	}
}

var ansiPattern = regexp.MustCompile("\033\\[[0-9;]*m")
