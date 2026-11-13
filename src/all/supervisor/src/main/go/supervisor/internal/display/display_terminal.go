package display

import (
	"os"

	"github.com/gdamore/tcell/v3"
)

type Terminal interface {
	close()
	clear()
	draw(row int, col int, str string, colour colour)
	show()
	sync()
	events() chan tcell.Event
}

func NewTerminalFactory(theme Theme) TerminalFactory {
	return func(useUnicode bool) (Terminal, error) {
		if os.Getenv("TERM_PROGRAM") == "" {
			err := os.Setenv("TERM_PROGRAM", "Apple_Terminal")
			if err != nil {
				return nil, err
			}
		}
		var options []tcell.TerminfoScreenOption
		if !useUnicode {
			options = append(options, tcell.OptColors(16))
		}
		screen, err := tcell.NewScreen(options...)
		if err != nil {
			return nil, err
		}
		if err := screen.Init(); err != nil {
			return nil, err
		}
		screen.DisableMouse()
		return &terminalWrapper{screen: screen, palette: theme.palette(useUnicode)}, nil
	}
}

type TerminalFactory func(useUnicode bool) (Terminal, error)
