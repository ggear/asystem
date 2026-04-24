package display

import (
	"os"

	"github.com/gdamore/tcell/v3"
	"github.com/mattn/go-runewidth"
)

type terminalWrapper struct {
	screen  tcell.Screen
	palette *colourPalette
}

func newTerminalWrapper(theme Theme) terminalFactory {
	return func(useUnicode bool) (Terminal, error) {
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
		return &terminalWrapper{screen: screen, palette: theme.palette(useUnicode)}, nil
	}
}

func (w *terminalWrapper) close() {
	w.screen.Fini()
}

func (w *terminalWrapper) clear() {
	w.screen.Clear()
}

func (w *terminalWrapper) draw(x int, y int, str string, c colour) {
	screenW, screenH := w.screen.Size()
	if x < 0 || y < 0 || x >= screenW || y >= screenH || str == "" {
		return
	}
	remaining := screenW - x
	if remaining <= 0 {
		return
	}
	if runewidth.StringWidth(str) > remaining {
		str = runewidth.Truncate(str, remaining, "")
		if str == "" {
			return
		}
	}
	w.screen.PutStrStyled(x, y, str, tcell.StyleDefault.Foreground(w.palette[c].tcell))
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
