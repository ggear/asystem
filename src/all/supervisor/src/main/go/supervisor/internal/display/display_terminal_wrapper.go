package display

import (
	"github.com/gdamore/tcell/v3"
	"github.com/mattn/go-runewidth"
)

type terminalWrapper struct {
	screen  tcell.Screen
	palette *colourPalette
}

func (w *terminalWrapper) close() {
	w.screen.Fini()
}

func (w *terminalWrapper) clear() {
	w.screen.Clear()
}

func (w *terminalWrapper) draw(x int, y int, value string, c colour) {
	screenW, screenH := w.screen.Size()
	if x < 0 || y < 0 || x >= screenW || y >= screenH || value == "" {
		return
	}
	remaining := screenW - x
	if remaining <= 0 {
		return
	}
	if runewidth.StringWidth(value) > remaining {
		value = runewidth.Truncate(value, remaining, "")
		if value == "" {
			return
		}
	}
	w.screen.PutStrStyled(x, y, value, tcell.StyleDefault.Foreground(w.palette[c].tcell))
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
