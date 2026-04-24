package display

import (
	"github.com/gdamore/tcell/v3"
	"github.com/gdamore/tcell/v3/color"
)

type Theme int

const (
	ThemeDark Theme = iota
	ThemeLight
	themeMax
)

type renderMode int

const (
	modeASCII renderMode = iota
	modeUnicode
	modeMax
)

type colour int

const (
	colourChat colour = iota
	colourCheer
	colourWarn
	colourAlert
	colourWhisper
	colourMurmur
	colourGrowl
	colourShout
)

type colourSpec struct {
	tcell tcell.Color
	ansi  string
}

type colourPalette [colourShout + 1]colourSpec

func (t Theme) palette(useUnicode bool) *colourPalette {
	if t < 0 || t >= themeMax {
		panic("invalid theme")
	}
	if useUnicode {
		return &palettes[t][modeUnicode]
	}
	return &palettes[t][modeASCII]
}

var palettes = [themeMax][modeMax]colourPalette{
	ThemeDark: {
		modeASCII: {
			colourChat:    {color.XTerm7, "\033[37m"},         // white
			colourCheer:   {color.XTerm14, "\033[96m"},        // bright cyan
			colourWarn:    {color.XTerm11, "\033[93m"},        // bright yellow
			colourAlert:   {color.XTerm1, "\033[31m"},         // dark red
			colourWhisper: {color.XTerm240, "\033[38;5;240m"}, // dark gray
			colourMurmur:  {color.XTerm213, "\033[38;5;213m"}, // bright pink
			colourGrowl:   {color.XTerm7, "\033[37m"},         // white
			colourShout:   {color.XTerm9, "\033[91m"},         // bright red
		},
		modeUnicode: {
			colourChat:    {color.XTerm7, "\033[37m"},         // white - mbtop TTY main_fg \x1b[37m]
			colourCheer:   {color.XTerm14, "\033[96m"},        // bright cyan - mbtop TTY cached_end \x1b[96m]
			colourWarn:    {color.XTerm11, "\033[93m"},        // bright yellow - mbtop TTY available_end \x1b[93m]
			colourAlert:   {color.XTerm1, "\033[31m"},         // dark red - mbtop TTY used_start \x1b[31m]
			colourWhisper: {color.XTerm240, "\033[38;5;240m"}, // dark gray - mbtop TTY meter_bg \x1b[38;5;240m]
			colourMurmur:  {color.XTerm213, "\033[38;5;213m"}, // bright pink - custom \x1b[38;5;213m]
			colourGrowl:   {color.XTerm12, "\033[94m"},        // bright blue - mbtop TTY \x1b[94m]
			colourShout:   {color.XTerm9, "\033[91m"},         // bright red - mbtop TTY hi_fg \x1b[91m]
		},
	},
	ThemeLight: {
		modeASCII: {
			colourChat:    {color.XTerm235, "\033[38;5;235m"}, // very dark grey
			colourCheer:   {color.XTerm38, "\033[38;5;38m"},   // aqua
			colourWarn:    {color.XTerm178, "\033[38;5;178m"}, // mustard
			colourAlert:   {color.XTerm9, "\033[91m"},         // bright red
			colourWhisper: {color.XTerm188, "\033[38;5;188m"}, // light gray
			colourMurmur:  {color.XTerm13, "\033[95m"},        // bright magenta
			colourGrowl:   {color.XTerm235, "\033[38;5;235m"}, // very dark grey
			colourShout:   {color.XTerm9, "\033[91m"},         // bright red
		},
		modeUnicode: {
			colourChat:    {color.XTerm235, "\033[38;5;235m"}, // very dark grey
			colourCheer:   {color.XTerm38, "\033[38;5;38m"},   // aqua
			colourWarn:    {color.XTerm178, "\033[38;5;178m"}, // mustard
			colourAlert:   {color.XTerm9, "\033[91m"},         // bright red
			colourWhisper: {color.XTerm188, "\033[38;5;188m"}, // light gray
			colourMurmur:  {color.XTerm13, "\033[95m"},        // bright magenta
			colourGrowl:   {color.XTerm67, "\033[38;5;67m"},   // steel gray-blue
			colourShout:   {color.XTerm9, "\033[91m"},         // bright red
		},
	},
}
