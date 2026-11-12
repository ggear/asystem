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
			colourChat:    {color.NewHexColor(0xc6c8c6), "\033[38;2;198;200;198m"}, // light grey
			colourCheer:   {color.NewHexColor(0x83beb1), "\033[38;2;131;190;177m"}, // seafoam
			colourWarn:    {color.NewHexColor(0xe1c65e), "\033[38;2;225;198;94m"},  // yellow
			colourAlert:   {color.NewHexColor(0xbf6c69), "\033[38;2;191;108;105m"}, // red
			colourWhisper: {color.XTerm240, "\033[38;5;240m"},                      // dark gray - mbtop TTY meter_bg \x1b[38;5;240m]
			colourMurmur:  {color.XTerm213, "\033[38;5;213m"},                      // bright pink - custom \x1b[38;5;213m]
			colourGrowl:   {color.NewHexColor(0x83a5d6), "\033[38;2;131;165;214m"}, // steel blue
			colourShout:   {color.NewHexColor(0xbf6c69), "\033[38;2;191;108;105m"}, // coral red
		},
	},
	ThemeLight: {
		modeASCII: {
			colourChat:    {color.XTerm235, "\033[38;5;235m"}, // very dark grey
			colourCheer:   {color.XTerm38, "\033[38;5;38m"},   // aqua
			colourWarn:    {color.XTerm178, "\033[38;5;178m"}, // mustard
			colourAlert:   {color.XTerm196, "\033[38;5;196m"}, // bright red
			colourWhisper: {color.XTerm188, "\033[38;5;188m"}, // light grey
			colourMurmur:  {color.XTerm207, "\033[38;5;207m"}, // magenta
			colourGrowl:   {color.XTerm235, "\033[38;5;235m"}, // very dark grey
			colourShout:   {color.XTerm196, "\033[38;5;196m"}, // bright red
		},
		modeUnicode: {
			colourChat:    {color.XTerm235, "\033[38;5;235m"}, // very dark grey
			colourCheer:   {color.XTerm38, "\033[38;5;38m"},   // aqua
			colourWarn:    {color.XTerm178, "\033[38;5;178m"}, // mustard
			colourAlert:   {color.XTerm196, "\033[38;5;196m"}, // bright red
			colourWhisper: {color.XTerm188, "\033[38;5;188m"}, // light grey
			colourMurmur:  {color.XTerm207, "\033[38;5;207m"}, // magenta
			colourGrowl:   {color.XTerm67, "\033[38;5;67m"},   // steel gray-blue
			colourShout:   {color.XTerm196, "\033[38;5;196m"}, // bright red
		},
	},
}
