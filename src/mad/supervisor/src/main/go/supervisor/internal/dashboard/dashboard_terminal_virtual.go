package dashboard

import (
	"strings"
	"sync/atomic"

	"github.com/gdamore/tcell/v3"
)

type terminalVirtual struct {
	width  int
	height int
	cells  []terminalVirtualCell
	eventQ chan tcell.Event
	closed atomic.Bool
}

type terminalVirtualCell struct {
	char    rune
	colour  colour
	written bool
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
	if v == nil || v.closed.Swap(true) {
		return
	}
	if v.eventQ != nil {
		close(v.eventQ)
	}
}

func (v *terminalVirtual) clear() {
	for i := range v.cells {
		v.cells[i] = terminalVirtualCell{char: ' ', colour: colourDefault, written: false}
	}
}

func (v *terminalVirtual) draw(x int, y int, str string, colour colour) {
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
		v.cells[y*v.width+x] = terminalVirtualCell{char: char, colour: colour, written: true}
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

func (v *terminalVirtual) cell(x, y int) (rune, colour, bool) {
	if x < 0 || y < 0 || x >= v.width || y >= v.height {
		return 0, colourDefault, false
	}
	cell := v.cells[y*v.width+x]
	return cell.char, cell.colour, true
}

func (v *terminalVirtual) dimensions() dimensions {
	maxCol := -1
	maxRow := -1
	for row := 0; row < v.height; row++ {
		rowIndex := row * v.width
		for col := 0; col < v.width; col++ {
			cell := v.cells[rowIndex+col]
			if cell.written {
				if row > maxRow {
					maxRow = row
				}
				if col > maxCol {
					maxCol = col
				}
			}
		}
	}
	if maxRow < 0 || maxCol < 0 {
		return dimensions{rows: 0, cols: 0}
	}
	return dimensions{rows: maxRow + 1, cols: maxCol + 1}
}

func (v *terminalVirtual) string(inColour bool) string {
	var builder strings.Builder
	var lastColour colour
	wroteRow := false
	for y := 0; y < v.height; y++ {
		rowHasContent := false
		rowIndex := y * v.width
		for x := 0; x < v.width; x++ {
			cell := v.cells[rowIndex+x]
			if cell.written {
				rowHasContent = true
				break
			}
		}
		if !rowHasContent {
			continue
		}
		wroteRow = true
		lastColour = colourDefault
		for x := 0; x < v.width; x++ {
			cell := v.cells[rowIndex+x]
			if inColour && cell.colour != lastColour {
				builder.WriteString(colourToAnsi(cell.colour))
				lastColour = cell.colour
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
	if inColour && wroteRow {
		builder.WriteString("\033[0m")
	}
	return builder.String()
}

func colourToAnsi(colour colour) string {
	switch colour {
	case colourGray:
		return "\033[90m"
	case colourGreen:
		return "\033[32m"
	case colourYellow:
		return "\033[93m"
	case colourRed:
		return "\033[31m"
	default:
		return "\033[39m"
	}
}
