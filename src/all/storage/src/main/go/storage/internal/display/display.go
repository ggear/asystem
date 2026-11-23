package display

import (
	"math"
	"strconv"
	"strings"

	"github.com/mattn/go-runewidth"
)

func Render(rows []Row, useUnicode, useColour bool) string {
	var builder strings.Builder
	writeRuleRow(&builder, textTopLeft, textTopMiddle, textTopRight, textHorizontalRule, useUnicode, widthsSpanned)
	writeHeaderLabels(&builder, useUnicode)
	writeHeaderRule(&builder, useUnicode)
	for index, row := range rows {
		if index > 0 {
			writeRowRule(&builder, useUnicode, row)
		}
		writeDataRow(&builder, useUnicode, useColour, row)
	}
	writeRuleRow(&builder, textBottomLeft, textBottomMiddle, textBottomRight, textHorizontalRule, useUnicode, widthsColumns)
	return builder.String()
}

func writeHeaderRule(builder *strings.Builder, useUnicode bool) {
	builder.WriteString(textMiddleLeft.pick(useUnicode))
	for index, width := range widthsColumns {
		if index > 0 {
			divider := textMiddleMiddle
			if index >= len(widthsSpanned) {
				divider = textTopMiddle
			}
			builder.WriteString(divider.pick(useUnicode))
		}
		builder.WriteString(strings.Repeat(textDoubleRule.pick(useUnicode), width))
	}
	builder.WriteString(textMiddleRight.pick(useUnicode))
	builder.WriteString("\n")
}

func writeRowRule(builder *strings.Builder, useUnicode bool, row Row) {
	switch {
	case row.NewBlock:
		writeRuleRow(builder, textMiddleLeft, textMiddleMiddle, textMiddleRight, textHorizontalRule, useUnicode, widthsColumns)
	case row.NewGroup:
		builder.WriteString(textVertical.pick(useUnicode))
		builder.WriteString(strings.Repeat(" ", hostCellWidth))
		writeRuleRow(builder, textMiddleLeft, textMiddleMiddle, textMiddleRight, textHorizontalRule, useUnicode, widthsColumns[1:])
	}
}

func writeRuleRow(builder *strings.Builder, left, junction, right, fill text, useUnicode bool, widths []int) {
	builder.WriteString(left.pick(useUnicode))
	for index, width := range widths {
		if index > 0 {
			builder.WriteString(junction.pick(useUnicode))
		}
		builder.WriteString(strings.Repeat(fill.pick(useUnicode), width))
	}
	builder.WriteString(right.pick(useUnicode))
	builder.WriteString("\n")
}

func writeHeaderLabels(builder *strings.Builder, useUnicode bool) {
	vert := textVertical.pick(useUnicode)
	builder.WriteString(vert)
	for index, header := range []string{headerHost, headerMount, headerSize, headerFree, headerUsed} {
		builder.WriteString(center(header, widthsSpanned[index]))
		builder.WriteString(vert)
	}
	builder.WriteString("\n")
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

func writeDataRow(builder *strings.Builder, useUnicode, useColour bool, row Row) {
	vert := textVertical.pick(useUnicode)
	measured := func(value string) string {
		if row.Unmeasured {
			return textUnmeasured
		}
		return value
	}
	builder.WriteString(vert)
	for _, cell := range []string{
		leftCell(row.Host, hostContentWidth),
		leftCell(row.Mount, mountContentWidth),
		rightCell(measured(formatTiB(row.Size)), bytesContentWidth),
		rightCell(measured(formatTiB(row.Free)), bytesContentWidth),
		rightCell(measured(formatTiB(row.Used)), bytesContentWidth),
		barCell(useUnicode, useColour, row),
		percentCell(useColour, row),
	} {
		builder.WriteString(cell)
		builder.WriteString(vert)
	}
	builder.WriteString("\n")
}

func leftCell(value string, content int) string {
	return wrapBorder(padRight(clip(value, content), content))
}

func rightCell(value string, content int) string {
	return wrapBorder(padLeft(clip(value, content), content))
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
	tebibytes := float64(bytes) / (1 << 40)
	return strconv.FormatFloat(tebibytes, 'f', 1, 64) + " TiB"
}

func barCell(useUnicode, useColour bool, row Row) string {
	if row.Unmeasured {
		return leftCell(textUnmeasured, barContentWidth)
	}
	filled := min(max(int(math.RoundToEven(row.Percent/5)), 0), barContentWidth)
	bar := strings.Repeat(textBar.pick(useUnicode), filled) + strings.Repeat(" ", barContentWidth-filled)
	if useColour {
		bar = severityColour(row.Percent) + bar + colourReset
	}
	return wrapBorder(bar)
}

func percentCell(useColour bool, row Row) string {
	if row.Unmeasured {
		return rightCell(textUnmeasured, percentContentWidth)
	}
	padded := padLeft(clip(strconv.FormatFloat(row.Percent, 'f', 1, 64)+"%", percentContentWidth), percentContentWidth)
	if useColour {
		padded = severityColour(row.Percent) + padded + colourReset
	}
	return wrapBorder(padded)
}

func severityColour(percent float64) string {
	switch {
	case percent >= severityRed:
		return colourRed
	case percent >= severityAmber:
		return colourAmber
	default:
		return colourGreen
	}
}

type Row struct {
	Host       string
	Mount      string
	Size       uint64
	Free       uint64
	Used       uint64
	Percent    float64
	Unmeasured bool
	NewBlock   bool
	NewGroup   bool
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
	headerHost  = "HST"
	headerMount = "MOUNT"
	headerSize  = "SIZE"
	headerFree  = "FREE"
	headerUsed  = "USED"

	hostContentWidth    = 3
	mountContentWidth   = 9
	bytesContentWidth   = 10
	percentContentWidth = 6
	barContentWidth     = 20
	border              = 1

	hostCellWidth    = hostContentWidth + 2*border
	mountCellWidth   = mountContentWidth + 2*border
	bytesCellWidth   = bytesContentWidth + 2*border
	barCellWidth     = barContentWidth + 2*border
	percentCellWidth = percentContentWidth + 2*border
	usedSpanWidth    = bytesCellWidth + 1 + barCellWidth + 1 + percentCellWidth

	severityAmber = 80.0
	severityRed   = 90.0

	textUnmeasured = "--"

	colourGreen = "\033[32m"
	colourAmber = "\033[33m"
	colourRed   = "\033[31m"
	colourReset = "\033[0m"
)

var (
	widthsSpanned = []int{hostCellWidth, mountCellWidth, bytesCellWidth, bytesCellWidth, usedSpanWidth}
	widthsColumns = []int{hostCellWidth, mountCellWidth, bytesCellWidth, bytesCellWidth, bytesCellWidth, barCellWidth, percentCellWidth}
)

var (
	textVertical       = text{ascii: "|", unicode: "│"}
	textBar            = text{ascii: "#", unicode: "■"}
	textHorizontalRule = text{ascii: "-", unicode: "─"}
	textDoubleRule     = text{ascii: "=", unicode: "─"}

	textTopLeft   = text{ascii: "+", unicode: "╭"}
	textTopMiddle = text{ascii: "+", unicode: "┬"}
	textTopRight  = text{ascii: "+", unicode: "╮"}

	textBottomLeft   = text{ascii: "+", unicode: "╰"}
	textBottomMiddle = text{ascii: "+", unicode: "┴"}
	textBottomRight  = text{ascii: "+", unicode: "╯"}

	textMiddleLeft   = text{ascii: "+", unicode: "├"}
	textMiddleMiddle = text{ascii: "+", unicode: "┼"}
	textMiddleRight  = text{ascii: "+", unicode: "┤"}
)
