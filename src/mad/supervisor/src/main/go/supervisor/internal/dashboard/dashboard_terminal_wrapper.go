package dashboard

import (
	"github.com/gdamore/tcell/v3"
	"github.com/gdamore/tcell/v3/color"
)

type terminalWrapper struct {
	screen tcell.Screen
}

func newTerminalWrapper() (Terminal, error) {
	screen, err := tcell.NewScreen()
	if err != nil {
		return nil, err
	}
	if err := screen.Init(); err != nil {
		return nil, err
	}
	return &terminalWrapper{screen: screen}, nil
}

func (w *terminalWrapper) close() {
	w.screen.Fini()
}

func (w *terminalWrapper) clear() {
	w.screen.Clear()
}

func (w *terminalWrapper) draw(x int, y int, str string, colour Colour) {
	if colour == ColourDefault {
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

func colourToTcell(colour Colour) tcell.Color {
	switch colour {
	case ColourGray:
		return color.Gray
	case ColourGreen:
		return color.Green
	case ColourYellow:
		return color.Yellow
	case ColourRed:
		return color.Red
	default:
		return color.Default
	}
}
