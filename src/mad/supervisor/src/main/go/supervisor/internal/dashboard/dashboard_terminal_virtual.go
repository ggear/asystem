package dashboard

import (
	"strings"

	"github.com/gdamore/tcell/v3"
)

type terminalVirtual struct {
	width  int
	height int
	cells  []terminalVirtualCell
	eventQ chan tcell.Event
}

type terminalVirtualCell struct {
	char   rune
	colour Colour
}

func newTerminalVirtual(rows, cols int) *terminalVirtual {
	terminal := &terminalVirtual{
		width:  cols,
		height: rows,
		cells:  make([]terminalVirtualCell, rows*cols),
		eventQ: make(chan tcell.Event, 16),
	}
	terminal.clear()
	return terminal
}

func (v *terminalVirtual) close() {
}

func (v *terminalVirtual) clear() {
	for i := range v.cells {
		v.cells[i] = terminalVirtualCell{char: ' ', colour: ColourDefault}
	}
}

func (v *terminalVirtual) draw(x int, y int, str string, colour Colour) {
	if v.width == 0 || v.height == 0 {
		return
	}
	for _, char := range []rune(str) {
		if char == '\n' {
			y++
			x = 0
			if y >= v.height {
				return
			}
			continue
		}
		if y < 0 || y >= v.height {
			return
		}
		if x < 0 {
			x++
			continue
		}
		if x >= v.width {
			return
		}
		v.cells[y*v.width+x] = terminalVirtualCell{char: char, colour: colour}
		x++
	}
}

func (v *terminalVirtual) show() {
}

func (v *terminalVirtual) sync() {
}

func (v *terminalVirtual) events() chan tcell.Event {
	return v.eventQ
}

func (v *terminalVirtual) cell(x, y int) (rune, Colour, bool) {
	if x < 0 || y < 0 || x >= v.width || y >= v.height {
		return 0, ColourDefault, false
	}
	cell := v.cells[y*v.width+x]
	return cell.char, cell.colour, true
}

func (v *terminalVirtual) string(inColour bool) string {
	var builder strings.Builder
	for y := 0; y < v.height; y++ {
		for x := 0; x < v.width; x++ {
			cell := v.cells[y*v.width+x]
			if inColour {
				builder.WriteString(colourToAnsi(cell.colour))
			}
			if cell.char == 0 {
				builder.WriteByte(' ')
			} else {
				builder.WriteRune(cell.char)
			}
		}
		if inColour {
			builder.WriteString("\033[0m")
		}
		builder.WriteByte('\n')
	}
	if inColour {
		builder.WriteString("\033[0m")
	}
	return builder.String()
}

func colourToAnsi(colour Colour) string {
	switch colour {
	case ColourGray:
		return "\033[90m"
	case ColourGreen:
		return "\033[32m"
	case ColourYellow:
		return "\033[93m"
	case ColourRed:
		return "\033[31m"
	default:
		return "\033[39m"
	}
}
