package display

import (
	"os"

	"github.com/gdamore/tcell/v3"
	"github.com/gdamore/tcell/v3/color"
)

type terminalWrapper struct {
	screen tcell.Screen
}

func newTerminalWrapper() (Terminal, error) {
	if os.Getenv("TERM_PROGRAM") == "" {
		os.Setenv("TERM_PROGRAM", "Apple_Terminal")
	}
	screen, err := tcell.NewScreen()
	if err != nil {
		return nil, err
	}
	if err := screen.Init(); err != nil {
		return nil, err
	}
	screen.DisableMouse()
	return &terminalWrapper{screen: screen}, nil
}

func (w *terminalWrapper) close() {
	w.screen.Fini()
}

func (w *terminalWrapper) clear() {
	w.screen.Clear()
}

func (w *terminalWrapper) draw(x int, y int, str string, colour colour) {
	if colour == colourDefault {
		w.screen.PutStr(x, y, str)
	} else {
		w.screen.PutStrStyled(x, y, str, tcell.StyleDefault.Foreground(colourToTcell(colour)))
	}
}

func (w *terminalWrapper) show() {
	w.screen.Show()
}

func (w *terminalWrapper) sync() {
	w.screen.Sync()
}

func (w *terminalWrapper) events() chan tcell.Event {
	return w.screen.EventQ()
}

func colourToTcell(colour colour) tcell.Color {
	switch colour {
	case colourGreen:
		return color.XTerm34
	case colourYellow:
		return color.XTerm136
	case colourOrange:
		return color.XTerm166
	case colourBlue:
		return color.XTerm33
	case colourRed:
		return color.XTerm124
	default:
		return color.Default
	}
}
