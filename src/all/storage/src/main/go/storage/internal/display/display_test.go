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
		{Host: "meg", Mount: "/", Size: tib(123456.7), Free: tib(0.1), Used: tib(123456.6), Percent: 100.0, NewHost: true, NewClass: true},
		{Mount: "/share", Size: tib(0.0), Free: tib(0.0), Used: tib(0.0), Percent: 0.0, NewClass: true},
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

func tib(value float64) uint64 {
	return uint64(value * (1 << 40))
}

func fixtureLocal() []Row {
	return []Row{
		{Host: "mad", Mount: "/", Size: tib(0.6), Free: tib(0.2), Used: tib(0.4), Percent: 66.7, NewHost: true, NewClass: true},
		{Mount: "/share/10", Size: tib(4.0), Free: tib(1.0), Used: tib(3.0), Percent: 75.0, NewClass: true},
		{Mount: "/share/11", Size: tib(4.0), Free: tib(1.5), Used: tib(2.5), Percent: 62.5},
		{Mount: "/share/12", Size: tib(4.0), Free: tib(1.2), Used: tib(2.8), Percent: 70.0},
		{Mount: "/share", Size: tib(12.0), Free: tib(3.7), Used: tib(8.3), Percent: 69.2},
		{Mount: "/backup", Size: tib(24.0), Free: tib(15.0), Used: tib(9.0), Percent: 37.5, NewClass: true},
	}
}

func fixtureLocalShares() []Row {
	return []Row{
		{Host: "mad", Mount: "/share/10", Size: tib(4.0), Free: tib(1.0), Used: tib(3.0), Percent: 75.0, NewHost: true, NewClass: true},
		{Mount: "/share/11", Size: tib(4.0), Free: tib(1.5), Used: tib(2.5), Percent: 62.5},
		{Mount: "/share/12", Size: tib(4.0), Free: tib(1.2), Used: tib(2.8), Percent: 70.0},
	}
}

func fixtureRemote() []Row {
	rows := []Row{{Host: "jen", Mount: "/", Size: tib(0.2), Free: tib(0.1), Used: tib(0.1), Percent: 50.0, NewHost: true, NewClass: true}}
	rows = append(rows, fixtureLocal()...)
	rows = append(rows,
		Row{Host: "max", Mount: "/", Size: tib(99.9), Free: tib(0.0), Used: tib(99.9), Percent: 100.0, NewHost: true, NewClass: true},
		Row{Mount: "/share/20", Size: tib(2.0), Free: tib(1.0), Used: tib(1.0), Percent: 50.0, NewClass: true},
		Row{Mount: "/share/21", Size: tib(0.6), Free: tib(0.2), Used: tib(0.4), Percent: 66.7},
		Row{Mount: "/share", Size: tib(2.6), Free: tib(1.2), Used: tib(1.4), Percent: 53.8},
		Row{Mount: "/backup", Size: tib(4.0), Free: tib(3.0), Used: tib(1.0), Percent: 25.0, NewClass: true},

		Row{Host: "may", Mount: "/", Size: tib(0.6), Free: tib(0.2), Used: tib(0.4), Percent: 66.7, NewHost: true, NewClass: true},
		Row{Mount: "/share/30", Size: tib(4.0), Free: tib(2.0), Used: tib(2.0), Percent: 50.0, NewClass: true},
		Row{Mount: "/share/31", Size: tib(4.0), Free: tib(1.5), Used: tib(2.5), Percent: 62.5},
		Row{Mount: "/share/32", Size: tib(0.5), Free: tib(0.1), Used: tib(0.4), Percent: 80.0},
		Row{Mount: "/share", Size: tib(8.5), Free: tib(3.6), Used: tib(4.9), Percent: 57.6},
		Row{Mount: "/backup", Size: tib(10.0), Free: tib(5.0), Used: tib(5.0), Percent: 50.0, NewClass: true},

		Row{Host: "meg", Mount: "/", Size: tib(0.6), Free: tib(0.2), Used: tib(0.4), Percent: 66.7, NewHost: true, NewClass: true},
		Row{Mount: "/share/40", Size: tib(1.5), Free: tib(0.4), Used: tib(1.1), Percent: 73.3, NewClass: true},
		Row{Mount: "/share/41", Size: tib(4.0), Free: tib(0.8), Used: tib(3.2), Percent: 80.0},
		Row{Mount: "/share/42", Size: tib(0.5), Free: tib(0.1), Used: tib(0.4), Percent: 80.0},
		Row{Mount: "/share", Size: tib(6.0), Free: tib(1.3), Used: tib(4.7), Percent: 78.3},
		Row{Mount: "/backup", Size: tib(6.0), Free: tib(1.4), Used: tib(4.6), Percent: 76.7, NewClass: true},

		Row{Mount: "/", Size: tib(101.9), Free: tib(0.7), Used: tib(101.2), Percent: 99.3, NewHost: true, NewClass: true},
		Row{Mount: "/share", Size: tib(29.1), Free: tib(9.8), Used: tib(19.3), Percent: 66.3, NewClass: true},
		Row{Mount: "/backup", Size: tib(44.0), Free: tib(24.4), Used: tib(19.6), Percent: 44.5, NewClass: true},
		Row{Mount: "", Size: tib(175.0), Free: tib(34.9), Used: tib(140.1), Percent: 80.1, NewClass: true},
	)
	return rows
}

func assertLayout(t *testing.T, rows []Row, useUnicode bool, want string) {
	t.Helper()
	got := Render(rows, useUnicode, false)
	if trimmed := strings.TrimPrefix(want, "\n"); got != trimmed {
		t.Errorf("layout mismatch\ngot:\n%s\nwant:\n%s", got, trimmed)
	}
}

var ansiPattern = regexp.MustCompile("\033\\[[0-9;]*m")
