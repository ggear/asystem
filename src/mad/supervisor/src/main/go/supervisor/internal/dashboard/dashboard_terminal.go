package dashboard

import (
	"github.com/gdamore/tcell/v3"
)

// TODO:
//   - hide tcell namespace completely - tcell.Event

type colour int

const (
	colourDefault colour = iota
	colourGray
	colourGreen
	colourYellow
	colourRed
)

type Terminal interface {
	close()
	clear()
	draw(row int, col int, str string, colour colour)
	show()
	sync()
	events() chan tcell.Event
}

var TerminalFactory terminalFactory = newTerminalWrapper

type terminalFactory func() (Terminal, error)
