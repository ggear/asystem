package dashboard

import (
	"github.com/gdamore/tcell/v3"
)

// TODO:
//   - hide tcell namespace completely - tcell.Event

type Colour int

const (
	ColourDefault Colour = iota
	ColourGray
	ColourGreen
	ColourYellow
	ColourRed
)

type Terminal interface {
	close()
	clear()
	draw(x int, y int, str string, colour Colour)
	show()
	sync()
	events() chan tcell.Event
}

var TerminalFactory terminalFactory = newTerminalWrapper

type terminalFactory func() (Terminal, error)
