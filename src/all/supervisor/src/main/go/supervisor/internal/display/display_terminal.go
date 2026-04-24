package display

import (
	"github.com/gdamore/tcell/v3"
)

// TODO:
//   - hide tcell namespace completely - tcell.Event

type Terminal interface {
	close()
	clear()
	draw(row int, col int, str string, colour colour)
	show()
	sync()
	events() chan tcell.Event
}

func TerminalFactory(theme Theme) terminalFactory {
	return newTerminalWrapper(theme)
}

type terminalFactory func(useUnicode bool) (Terminal, error)
