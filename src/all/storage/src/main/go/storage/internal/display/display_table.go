package display

import (
	"math"
	"strconv"
	"strings"

	"github.com/mattn/go-runewidth"
)

func Render(rows []Row, useUnicode, useColour bool) string {
	var b strings.Builder
	writeTopBorder(&b, useUnicode)
	writeHeaderLabels(&b, useUnicode)
	writeHeaderRule(&b, useUnicode)
	for index, row := range rows {
		if index > 0 {
			writeRowRule(&b, useUnicode, row)
		}
		writeDataRow(&b, useUnicode, useColour, row)
	}
	writeBottomBorder(&b, useUnicode)
	return b.String()
}

func writeTopBorder(b *strings.Builder, useUnicode bool) {
	writeRuleRow(b, textTopLeft, textTopMid, textTopRight, textHRule, useUnicode, widthsSpanned)
}

func writeBottomBorder(b *strings.Builder, useUnicode bool) {
	writeRuleRow(b, textBotLeft, textBotMid, textBotRight, textHRule, useUnicode, widthsColumns)
}

func writeHeaderRule(b *strings.Builder, useUnicode bool) {
	b.WriteString(textMidLeft.pick(useUnicode))
	for index, width := range widthsColumns {
		if index > 0 {
			divider := textMidMid
			if index >= len(widthsSpanned) {
				divider = textTopMid
			}
			b.WriteString(divider.pick(useUnicode))
		}
		b.WriteString(strings.Repeat(textDRule.pick(useUnicode), width))
	}
	b.WriteString(textMidRight.pick(useUnicode))
	b.WriteString("\n")
}

func writeRowRule(b *strings.Builder, useUnicode bool, row Row) {
	widths := widthsColumns
	switch {
	case row.NewHost:
	case row.NewClass:
		b.WriteString(textVert.pick(useUnicode))
		b.WriteString(strings.Repeat(" ", hostCellWidth))
		widths = widthsColumns[1:]
	default:
		return
	}
	writeRuleRow(b, textMidLeft, textMidMid, textMidRight, textHRule, useUnicode, widths)
}

func writeRuleRow(b *strings.Builder, left, junction, right, fill text, useUnicode bool, widths []int) {
	b.WriteString(left.pick(useUnicode))
	for index, width := range widths {
		if index > 0 {
			b.WriteString(junction.pick(useUnicode))
		}
		b.WriteString(strings.Repeat(fill.pick(useUnicode), width))
	}
	b.WriteString(right.pick(useUnicode))
	b.WriteString("\n")
}

func writeHeaderLabels(b *strings.Builder, useUnicode bool) {
	vert := textVert.pick(useUnicode)
	b.WriteString(vert)
	for index, header := range []string{headerHost, headerMount, headerSize, headerFree, headerUsed} {
		b.WriteString(center(header, widthsSpanned[index]))
		b.WriteString(vert)
	}
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

func writeDataRow(b *strings.Builder, useUnicode, useColour bool, row Row) {
	vert := textVert.pick(useUnicode)
	b.WriteString(vert)
	b.WriteString(leftCell(row.Host, hostContentWidth))
	b.WriteString(vert)
	b.WriteString(leftCell(row.Mount, mountContentWidth))
	b.WriteString(vert)
	b.WriteString(rightCell(bytesOrDash(row.Unmeasured, row.Size), bytesContentWidth))
	b.WriteString(vert)
	b.WriteString(rightCell(bytesOrDash(row.Unmeasured, row.Free), bytesContentWidth))
	b.WriteString(vert)
	b.WriteString(rightCell(bytesOrDash(row.Unmeasured, row.Used), bytesContentWidth))
	b.WriteString(vert)
	b.WriteString(barCell(useUnicode, useColour, row))
	b.WriteString(vert)
	b.WriteString(pctCell(useColour, row))
	b.WriteString(vert)
	b.WriteString("\n")
}

func bytesOrDash(unmeasured bool, bytes uint64) string {
	if unmeasured {
		return "--"
	}
	return clip(formatTiB(bytes), bytesContentWidth)
}

func leftCell(value string, content int) string {
	return wrapBorder(padRight(clip(value, content), content))
}

func rightCell(value string, content int) string {
	return wrapBorder(padLeft(value, content))
}

func wrapBorder(content string) string {
	return strings.Repeat(" ", border) + content + strings.Repeat(" ", border)
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

func barCell(useUnicode, useColour bool, row Row) string {
	if row.Unmeasured {
		return wrapBorder(strings.Repeat(" ", barContentWidth))
	}
	filled := min(max(roundHalfEven(row.Percent/5), 0), barContentWidth)
	bar := strings.Repeat(textBar.pick(useUnicode), filled) + strings.Repeat(" ", barContentWidth-filled)
	if useColour {
		bar = severityColour(row.Percent) + bar + colourReset
	}
	return wrapBorder(bar)
}

func pctCell(useColour bool, row Row) string {
	if row.Unmeasured {
		return wrapBorder(padLeft("--", pctContentWidth))
	}
	value := strconv.FormatFloat(row.Percent, 'f', 1, 64) + "%"
	padded := padLeft(value, pctContentWidth)
	if useColour {
		padded = severityColour(row.Percent) + padded + colourReset
	}
	return wrapBorder(padded)
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

const (
	hostContentWidth  = 3
	mountContentWidth = 9
	bytesContentWidth = 10
	pctContentWidth   = 6
	barContentWidth   = 20
	border            = 1

	hostCellWidth  = hostContentWidth + 2*border
	mountCellWidth = mountContentWidth + 2*border
	bytesCellWidth = bytesContentWidth + 2*border
	barCellWidth   = barContentWidth + 2*border
	pctCellWidth   = pctContentWidth + 2*border
	usedSpanWidth  = bytesCellWidth + 1 + barCellWidth + 1 + pctCellWidth

	severityAmber = 70.0
	severityRed   = 90.0

	colourGreen = "\033[32m"
	colourAmber = "\033[33m"
	colourRed   = "\033[31m"
	colourReset = "\033[0m"
)

var (
	widthsSpanned = []int{hostCellWidth, mountCellWidth, bytesCellWidth, bytesCellWidth, usedSpanWidth}
	widthsColumns = []int{hostCellWidth, mountCellWidth, bytesCellWidth, bytesCellWidth, bytesCellWidth, barCellWidth, pctCellWidth}
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
