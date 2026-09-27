package display

import (
	"math"
	"strconv"
	"strings"

	"github.com/mattn/go-runewidth"
)

const (
	bytesContentWidth = 10
	pctContentWidth   = 6
	barContentWidth   = 20
	border            = 1

	severityAmber = 70.0
	severityRed   = 90.0
)

var (
	textVert  = text{ascii: "|", unicode: "│"}
	textBar   = text{ascii: "#", unicode: "■"}
	textHRule = text{ascii: "-", unicode: "─"}
	textDRule = text{ascii: "=", unicode: "─"}

	textTopLeft  = text{ascii: "+", unicode: "╭"}
	textTopMid   = text{ascii: "+", unicode: "┬"}
	textTopRight = text{ascii: "+", unicode: "╮"}

	textBotLeft  = text{ascii: "+", unicode: "╰"}
	textBotMid   = text{ascii: "+", unicode: "┴"}
	textBotRight = text{ascii: "+", unicode: "╯"}

	textMidLeft  = text{ascii: "+", unicode: "├"}
	textMidMid   = text{ascii: "+", unicode: "┼"}
	textMidRight = text{ascii: "+", unicode: "┤"}
)

const (
	colourGreen = "\033[32m"
	colourAmber = "\033[33m"
	colourRed   = "\033[31m"
	colourReset = "\033[0m"
)

func Render(rows []Row, useUnicode, useColour bool) string {
	hostWidth := columnWidth(headerHost, rowValues(rows, func(r Row) string { return r.Host }))
	mountWidth := columnWidth(headerMount, rowValues(rows, func(r Row) string { return r.Mount }))
	var b strings.Builder
	writeTopBorder(&b, useUnicode, hostWidth, mountWidth)
	writeHeaderLabels(&b, useUnicode, hostWidth, mountWidth)
	writeHeaderRule(&b, useUnicode, hostWidth, mountWidth)
	for index, row := range rows {
		if index > 0 {
			writeRowRule(&b, useUnicode, hostWidth, mountWidth, row)
		}
		writeDataRow(&b, useUnicode, useColour, hostWidth, mountWidth, row)
	}
	writeBottomBorder(&b, useUnicode, hostWidth, mountWidth)
	return b.String()
}

func rowValues(rows []Row, pick func(Row) string) []string {
	values := make([]string, len(rows))
	for i, row := range rows {
		values[i] = pick(row)
	}
	return values
}

func columnWidth(header string, values []string) int {
	width := runewidth.StringWidth(header)
	for _, value := range values {
		if w := runewidth.StringWidth(value); w > width {
			width = w
		}
	}
	return width + 2*border
}

func writeTopBorder(b *strings.Builder, useUnicode bool, hostWidth, mountWidth int) {
	rule := textHRule.pick(useUnicode)
	widths := []int{hostWidth, mountWidth, bytesContentWidth + 2*border, bytesContentWidth + 2*border, usedSpanWidth()}
	mid := textTopMid.pick(useUnicode)
	junctions := []string{mid, mid, mid, mid}
	writeRuleRow(b, textTopLeft.pick(useUnicode), junctions, textTopRight.pick(useUnicode), rule, widths)
}

func writeBottomBorder(b *strings.Builder, useUnicode bool, hostWidth, mountWidth int) {
	rule := textHRule.pick(useUnicode)
	mid := textBotMid.pick(useUnicode)
	junctions := []string{mid, mid, mid, mid, mid, mid}
	writeRuleRow(b, textBotLeft.pick(useUnicode), junctions, textBotRight.pick(useUnicode), rule, columnWidths(hostWidth, mountWidth))
}

func writeHeaderRule(b *strings.Builder, useUnicode bool, hostWidth, mountWidth int) {
	rule := textDRule.pick(useUnicode)
	cross := textMidMid.pick(useUnicode)
	down := textTopMid.pick(useUnicode)
	junctions := []string{cross, cross, cross, cross, down, down}
	writeRuleRow(b, textMidLeft.pick(useUnicode), junctions, textMidRight.pick(useUnicode), rule, columnWidths(hostWidth, mountWidth))
}

func writeRowRule(b *strings.Builder, useUnicode bool, hostWidth, mountWidth int, row Row) {
	rule := textHRule.pick(useUnicode)
	cross := textMidMid.pick(useUnicode)
	if row.NewHost {
		junctions := []string{cross, cross, cross, cross, cross, cross}
		writeRuleRow(b, textMidLeft.pick(useUnicode), junctions, textMidRight.pick(useUnicode), rule, columnWidths(hostWidth, mountWidth))
		return
	}
	if row.NewClass {
		b.WriteString(textVert.pick(useUnicode))
		b.WriteString(strings.Repeat(" ", hostWidth))
		junctions := []string{cross, cross, cross, cross, cross}
		widths := columnWidths(hostWidth, mountWidth)[1:]
		writeRuleRow(b, textMidLeft.pick(useUnicode), junctions, textMidRight.pick(useUnicode), rule, widths)
	}
}

func columnWidths(hostWidth, mountWidth int) []int {
	bytesWidth := bytesContentWidth + 2*border
	return []int{hostWidth, mountWidth, bytesWidth, bytesWidth, bytesWidth, barContentWidth + 2*border, pctContentWidth + 2*border}
}

func writeRuleRow(b *strings.Builder, left string, junctions []string, right, fill string, widths []int) {
	b.WriteString(left)
	for i, width := range widths {
		b.WriteString(strings.Repeat(fill, width))
		if i < len(widths)-1 {
			b.WriteString(junctions[i])
		}
	}
	b.WriteString(right)
	b.WriteString("\n")
}

func usedSpanWidth() int {
	bytesWidth := bytesContentWidth + 2*border
	barWidth := barContentWidth + 2*border
	pctWidth := pctContentWidth + 2*border
	return bytesWidth + 1 + barWidth + 1 + pctWidth
}

func writeHeaderLabels(b *strings.Builder, useUnicode bool, hostWidth, mountWidth int) {
	vert := textVert.pick(useUnicode)
	sizeWidth := bytesContentWidth + 2*border
	usedWidth := usedSpanWidth()
	b.WriteString(vert)
	b.WriteString(center(headerHost, hostWidth))
	b.WriteString(vert)
	b.WriteString(center(headerMount, mountWidth))
	b.WriteString(vert)
	b.WriteString(center(headerSize, sizeWidth))
	b.WriteString(vert)
	b.WriteString(center(headerFree, sizeWidth))
	b.WriteString(vert)
	b.WriteString(center(headerUsed, usedWidth))
	b.WriteString(vert)
	b.WriteString("\n")
}

func center(text string, width int) string {
	extra := width - runewidth.StringWidth(text)
	if extra <= 0 {
		return text
	}
	left := extra / 2
	right := extra - left
	return strings.Repeat(" ", left) + text + strings.Repeat(" ", right)
}

func writeDataRow(b *strings.Builder, useUnicode, useColour bool, hostWidth, mountWidth int, row Row) {
	vert := textVert.pick(useUnicode)
	b.WriteString(vert)
	b.WriteString(leftCell(row.Host, hostWidth))
	b.WriteString(vert)
	b.WriteString(leftCell(row.Mount, mountWidth))
	b.WriteString(vert)
	b.WriteString(rightCell(clip(formatTiB(row.Size), bytesContentWidth), bytesContentWidth))
	b.WriteString(vert)
	b.WriteString(rightCell(clip(formatTiB(row.Free), bytesContentWidth), bytesContentWidth))
	b.WriteString(vert)
	b.WriteString(rightCell(clip(formatTiB(row.Used), bytesContentWidth), bytesContentWidth))
	b.WriteString(vert)
	b.WriteString(barCell(useUnicode, useColour, row.Percent))
	b.WriteString(vert)
	b.WriteString(pctCell(useColour, row.Percent))
	b.WriteString(vert)
	b.WriteString("\n")
}

func leftCell(value string, width int) string {
	content := width - 2*border
	return strings.Repeat(" ", border) + padRight(value, content) + strings.Repeat(" ", border)
}

func rightCell(value string, content int) string {
	return strings.Repeat(" ", border) + padLeft(value, content) + strings.Repeat(" ", border)
}

func padRight(value string, width int) string {
	if pad := width - runewidth.StringWidth(value); pad > 0 {
		return value + strings.Repeat(" ", pad)
	}
	return value
}

func padLeft(value string, width int) string {
	if pad := width - runewidth.StringWidth(value); pad > 0 {
		return strings.Repeat(" ", pad) + value
	}
	return value
}

func clip(value string, width int) string {
	if runewidth.StringWidth(value) <= width || width <= 3 {
		return value
	}
	return runewidth.Truncate(value, width-3, "") + "..."
}

func formatTiB(bytes uint64) string {
	tib := float64(bytes) / (1 << 40)
	return strconv.FormatFloat(tib, 'f', 1, 64) + " TiB"
}

func barCell(useUnicode, useColour bool, percent float64) string {
	filled := min(max(roundHalfEven(percent/5), 0), barContentWidth)
	bar := strings.Repeat(textBar.pick(useUnicode), filled) + strings.Repeat(" ", barContentWidth-filled)
	if useColour {
		bar = severityColour(percent) + bar + colourReset
	}
	return strings.Repeat(" ", border) + bar + strings.Repeat(" ", border)
}

func pctCell(useColour bool, percent float64) string {
	value := strconv.FormatFloat(percent, 'f', 1, 64) + "%"
	padded := padLeft(value, pctContentWidth)
	if useColour {
		padded = severityColour(percent) + padded + colourReset
	}
	return strings.Repeat(" ", border) + padded + strings.Repeat(" ", border)
}

func roundHalfEven(value float64) int {
	floor := math.Floor(value)
	switch diff := value - floor; {
	case diff < 0.5:
		return int(floor)
	case diff > 0.5:
		return int(floor) + 1
	case int64(floor)%2 == 0:
		return int(floor)
	default:
		return int(floor) + 1
	}
}

func severityColour(percent float64) string {
	switch {
	case percent > severityRed:
		return colourRed
	case percent >= severityAmber:
		return colourAmber
	default:
		return colourGreen
	}
}

type text struct {
	ascii   string
	unicode string
}

func (t text) pick(useUnicode bool) string {
	if useUnicode {
		return t.unicode
	}
	return t.ascii
}
