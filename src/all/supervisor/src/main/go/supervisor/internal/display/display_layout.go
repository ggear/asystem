package display

import (
	"math"
	"strconv"
	"strings"
	"supervisor/internal/metric"
	"supervisor/internal/scribe"
	"time"

	"github.com/mattn/go-runewidth"
)

var (
	textBar   = text{ascii: "|", unicode: "■"}
	textTick  = text{ascii: "+", unicode: "✔"}
	textCross = text{ascii: "-", unicode: "✖"}
	textUp    = text{ascii: "^", unicode: "↑"}
	textDown  = text{ascii: "v", unicode: "↓"}
	textRule  = text{ascii: "=", unicode: "─"}
	textEdge  = text{ascii: " =+", unicode: " ──"}
	textPaged = text{ascii: "UP/DOWN", unicode: "↑↓"}
)

type boxKind int

const (
	boxDatum boxKind = iota
	boxTitle
	boxLabel
	boxControls
	boxBorder
	boxDivider
)

type boxAlign int

const (
	boxRight boxAlign = iota
	boxLeft
	boxMiddle
)

type boxValueKind int

const (
	valueText boxValueKind = iota
	valueTime
	valueHistogram
	valueBool
)

type box struct {
	kind            boxKind
	labelLeft       text
	labelMiddle     text
	labelRight      text
	valueLength     int
	valueOptional   bool
	valueAlign      boxAlign
	valueSuffix     string
	valueKind       boxValueKind
	position        *dimensions
	isLast          bool
	metricID        metric.ID
	recordGUID      *metric.RecordGUID
	compiled        *compiled
	resizeCount     int
	resizeIncrement func(b *box, increment, hostCount int)
	resizeRemainder func(b *box, remainder, hostCount int)
}

type compiled struct {
	length            int
	labelLeftLength   int
	labelMiddleLength int
	labelRightLength  int
	valueSuffixLength int
	valueOffset       int
}

func compactDisplayLayout(useUnicode bool) [][]box {
	resizeIncrementValueService := func(b *box, increment, hostCount int) { b.valueLength += increment }
	resizeIncrementLabelService := func(b *box, increment, hostCount int) {
		b.labelRight = b.labelRight.resize(increment, func(value string, length int) string {
			return value + repeat(value, 0, 1, length-runewidth.StringWidth(value))
		})
	}
	resizeIncrementSpacer := func(b *box, increment, hostCount int) {
		b.labelLeft = b.labelLeft.resize(increment, func(value string, length int) string {
			return value + repeat(value, 0, 1, length-runewidth.StringWidth(value))
		})
	}
	resizeIncrementBorder := func(b *box, increment, hostCount int) {
		b.labelRight = b.labelRight.resize(increment, func(value string, length int) string { return extend(value, 1, length) })
	}
	resizeRemainderSpacer := func(b *box, remainder, hostCount int) {
		resizeStart := time.Now()
		if hostCount == 1 {
			b.labelRight = b.labelRight.resize(remainder, func(value string, length int) string { return extend(value, 1, length) })
		} else {
			switch remainder {
			case 1, 2, 3, 6:
			case 4, 5:
				b.labelRight = b.labelRight.resize(2, func(value string, length int) string { return extend(value, 1, length) })
			default:
				logRemainder(resizeStart, remainder, hostCount)
			}
		}
	}
	resizeRemainderBorder := func(b *box, remainder, hostCount int) {
		resizeStart := time.Now()
		if hostCount == 1 {
			switch remainder {
			case 1, 3:
			case 2:
				b.labelMiddle = b.labelMiddle.resize(1, func(value string, length int) string { return " " })
			default:
				logRemainder(resizeStart, remainder, hostCount)
			}
		} else {
			switch remainder {
			case 1, 2, 3, 6:
			case 4, 5:
				b.labelMiddle = b.labelMiddle.resize(1, func(value string, length int) string { return " " })
			default:
				logRemainder(resizeStart, remainder, hostCount)
			}
		}
	}
	resizeRemainderColumn := func(b *box, remainder, hostCount int) {
		resizeStart := time.Now()
		if hostCount == 1 {
			switch remainder {
			case 1:
				b.labelRight = b.labelRight.resize(1, func(value string, length int) string { return extend(value, 0, length) })
			case 2, 3:
			default:
				logRemainder(resizeStart, remainder, hostCount)
			}
		}
	}
	resizeRemainderDivider := func(b *box, remainder, hostCount int) {
		resizeStart := time.Now()
		if hostCount > 1 {
			switch remainder {
			case 1, 2, 3:
				b.labelLeft = b.labelLeft.resize(1, func(value string, length int) string { return repeat(" ", 1, 0, remainder) })
			case 4, 6:
			case 5:
				b.labelLeft = b.labelLeft.resize(1, func(value string, length int) string { return repeat(" ", 1, 0, 1) })
			default:
				logRemainder(resizeStart, remainder, hostCount)
			}
		}
	}
	t_0_0 := box{labelLeft: text{
		ascii:   "+= ",
		unicode: "╭─┐",
	}, labelMiddle: text{
		ascii:   "           ",
		unicode: "           ",
	}, labelRight: text{
		ascii:   " =================================",
		unicode: "┌─────────────────────────────────",
	}, resizeCount: 3, kind: boxTitle, resizeIncrement: resizeIncrementBorder, resizeRemainder: resizeRemainderSpacer}
	t_0_1 := box{labelLeft: text{
		ascii:   "= ",
		unicode: "─┐",
	}, labelMiddle: text{
		ascii:   "    ",
		unicode: "    ",
	}, labelRight: text{
		ascii:   " =+",
		unicode: "┌─╮",
	}, kind: boxControls}
	b_X_Y := box{labelLeft: text{ascii: "|", unicode: "│"}, labelMiddle: text{ascii: "", unicode: ""}, labelRight: text{ascii: "", unicode: ""}, kind: boxBorder, resizeRemainder: resizeRemainderBorder}
	b_X_Z := box{labelRight: text{ascii: "|", unicode: "│"}, labelMiddle: text{ascii: "", unicode: ""}, labelLeft: text{ascii: "", unicode: ""}, kind: boxBorder, resizeRemainder: resizeRemainderBorder}
	d_1_0 := box{labelMiddle: text{ascii: metric.GetIDLabel(metric.MetricHostUsedProcessor) + " "}, valueLength: 3, valueSuffix: "%", metricID: metric.MetricHostUsedProcessor}
	d_1_1 := box{labelMiddle: text{ascii: metric.GetIDLabel(metric.MetricHostFailedLogs) + " "}, valueLength: 3, valueSuffix: "%", labelLeft: text{ascii: " "}, metricID: metric.MetricHostFailedLogs, resizeIncrement: resizeIncrementSpacer}
	d_1_2 := box{labelMiddle: text{ascii: metric.GetIDLabel(metric.MetricHostWarnTemperature) + " "}, valueLength: 3, valueSuffix: "%", metricID: metric.MetricHostWarnTemperature}
	d_1_3 := box{labelMiddle: text{ascii: metric.GetIDLabel(metric.MetricHostUsedHomeSpace) + " "}, valueLength: 3, valueSuffix: "%", labelLeft: text{ascii: " "}, metricID: metric.MetricHostUsedHomeSpace, resizeIncrement: resizeIncrementSpacer}
	d_2_0 := box{labelMiddle: text{ascii: metric.GetIDLabel(metric.MetricHostUsedMemory) + " "}, valueLength: 3, valueSuffix: "%", metricID: metric.MetricHostUsedMemory}
	d_2_1 := box{labelMiddle: text{ascii: metric.GetIDLabel(metric.MetricHostFailedShares) + " "}, valueLength: 3, valueSuffix: "%", labelLeft: text{ascii: " "}, metricID: metric.MetricHostFailedShares, resizeIncrement: resizeIncrementSpacer}
	d_2_2 := box{labelMiddle: text{ascii: metric.GetIDLabel(metric.MetricHostSpinFanSpeed) + " "}, valueLength: 3, valueSuffix: "%", metricID: metric.MetricHostSpinFanSpeed}
	d_2_3 := box{labelMiddle: text{ascii: metric.GetIDLabel(metric.MetricHostUsedShareSpace) + " "}, valueLength: 3, valueSuffix: "%", labelLeft: text{ascii: " "}, metricID: metric.MetricHostUsedShareSpace, resizeIncrement: resizeIncrementSpacer}
	d_3_0 := box{labelMiddle: text{ascii: metric.GetIDLabel(metric.MetricHostAllocatedMemory) + " "}, valueLength: 3, valueSuffix: "%", metricID: metric.MetricHostAllocatedMemory}
	d_3_1 := box{labelMiddle: text{ascii: metric.GetIDLabel(metric.MetricHostFailedBackupStages) + " "}, valueLength: 3, valueSuffix: "%", labelLeft: text{ascii: " "}, metricID: metric.MetricHostFailedBackupStages, resizeIncrement: resizeIncrementSpacer}
	d_3_2 := box{labelMiddle: text{ascii: metric.GetIDLabel(metric.MetricHostUsedDriveLife) + " "}, valueLength: 3, valueSuffix: "%", metricID: metric.MetricHostUsedDriveLife}
	d_3_3 := box{labelMiddle: text{ascii: metric.GetIDLabel(metric.MetricHostUsedBackupSpace) + " "}, valueLength: 3, valueSuffix: "%", labelLeft: text{ascii: " "}, metricID: metric.MetricHostUsedBackupSpace, resizeIncrement: resizeIncrementSpacer}
	s_X_0 := box{labelRight: text{
		ascii:   "+-------------------------------------------------------+",
		unicode: "├───────────────────────────────────────────────────────┤",
	}, kind: boxBorder, resizeCount: 3, resizeIncrement: resizeIncrementBorder, resizeRemainder: resizeRemainderSpacer}
	s_Y_Y := box{labelRight: text{ascii: " "}, kind: boxBorder, resizeIncrement: resizeIncrementBorder, resizeRemainder: resizeRemainderColumn}
	l_5_0 := box{labelMiddle: text{ascii: metric.GetIDLabel(metric.MetricServiceName)}, labelRight: text{ascii: "   "}, kind: boxLabel, resizeIncrement: resizeIncrementLabelService}
	l_5_1 := box{labelMiddle: text{ascii: metric.GetIDLabel(metric.MetricServiceUsedProcessor)}, labelLeft: text{ascii: " "}, labelRight: text{ascii: " "}, kind: boxLabel}
	l_5_2 := box{labelMiddle: text{ascii: metric.GetIDLabel(metric.MetricServiceUsedMemory)}, labelLeft: text{ascii: " "}, kind: boxLabel}
	l_5_3 := box{labelMiddle: text{ascii: metric.GetIDLabel(metric.MetricServiceBackupStatus)}, labelLeft: text{ascii: " "}, kind: boxLabel}
	l_5_4 := box{labelMiddle: text{ascii: metric.GetIDLabel(metric.MetricService)}, labelLeft: text{ascii: " "}, kind: boxLabel}
	d_X_0 := box{labelRight: text{ascii: " "}, valueLength: 9, valueAlign: boxLeft, valueOptional: true, metricID: metric.MetricServiceName, resizeIncrement: resizeIncrementValueService}
	d_X_1 := box{valueSuffix: "%", labelRight: text{ascii: " "}, valueLength: 3, valueOptional: true, metricID: metric.MetricServiceUsedProcessor}
	d_X_2 := box{valueSuffix: "%", labelRight: text{ascii: " "}, valueLength: 3, valueOptional: true, metricID: metric.MetricServiceUsedMemory}
	d_X_3 := box{labelLeft: text{ascii: " "}, valueLength: 1, labelRight: text{ascii: "  "}, valueOptional: true, valueKind: valueBool, metricID: metric.MetricServiceBackupStatus}
	d_X_4 := box{labelLeft: text{ascii: " "}, valueLength: 1, labelRight: text{ascii: " "}, valueOptional: true, valueKind: valueBool, metricID: metric.MetricService}
	s_X_Y := box{labelRight: text{
		ascii:   "                                                         ",
		unicode: "╰───────────────────────────────────────────────────────╯",
	}, kind: boxBorder, resizeCount: 3, resizeIncrement: resizeIncrementBorder, resizeRemainder: resizeRemainderSpacer}
	v_X_X := box{labelLeft: text{ascii: ""}, kind: boxDivider, resizeRemainder: resizeRemainderDivider}
	return compile(useUnicode, [][]box{
		{t_0_0, t_0_1, v_X_X},
		{b_X_Y, d_1_0, d_1_1, s_Y_Y, d_1_2, d_1_3, b_X_Z, v_X_X},
		{b_X_Y, d_2_0, d_2_1, s_Y_Y, d_2_2, d_2_3, b_X_Z, v_X_X},
		{b_X_Y, d_3_0, d_3_1, s_Y_Y, d_3_2, d_3_3, b_X_Z, v_X_X},
		{s_X_0, v_X_X},
		{b_X_Y, l_5_0, l_5_1, l_5_2, l_5_3, l_5_4, s_Y_Y, l_5_0, l_5_1, l_5_2, l_5_3, l_5_4, b_X_Z, v_X_X},
		{b_X_Y, d_X_0, d_X_1, d_X_2, d_X_3, d_X_4, s_Y_Y, d_X_0, d_X_1, d_X_2, d_X_3, d_X_4, b_X_Z, v_X_X},
		{b_X_Y, d_X_0, d_X_1, d_X_2, d_X_3, d_X_4, s_Y_Y, d_X_0, d_X_1, d_X_2, d_X_3, d_X_4, b_X_Z, v_X_X},
		{b_X_Y, d_X_0, d_X_1, d_X_2, d_X_3, d_X_4, s_Y_Y, d_X_0, d_X_1, d_X_2, d_X_3, d_X_4, b_X_Z, v_X_X},
		{b_X_Y, d_X_0, d_X_1, d_X_2, d_X_3, d_X_4, s_Y_Y, d_X_0, d_X_1, d_X_2, d_X_3, d_X_4, b_X_Z, v_X_X},
		{s_X_Y, v_X_X},
	})
}

func relaxedDisplayLayout(useUnicode bool) [][]box {
	resizeIncrementHistogramValue := func(b *box, increment, hostCount int) { b.valueLength += increment }
	resizeIncrementHistogramLabel := func(b *box, increment, hostCount int) {
		b.labelMiddle = b.labelMiddle.resize(increment, func(value string, length int) string { return pad(value, boxMiddle, length) })
	}
	resizeIncrementBorder := func(b *box, increment, hostCount int) {
		b.labelRight = b.labelRight.resize(increment, func(value string, length int) string { return extend(value, 1, length) })
	}
	resizeRemainderSpacer := func(b *box, remainder, hostCount int) {
		resizeStart := time.Now()
		if hostCount == 1 {
			b.labelRight = b.labelRight.resize(remainder, func(value string, length int) string { return extend(value, 1, length) })
		} else {
			switch remainder {
			case 1:
			case 2, 3, 4, 5, 6, 7:
				b.labelRight = b.labelRight.resize(remainder/2, func(value string, length int) string { return extend(value, 1, length) })
			default:
				logRemainder(resizeStart, remainder, hostCount)
			}
		}
	}
	resizeRemainderBorder := func(b *box, remainder, hostCount int) {
		resizeStart := time.Now()
		if hostCount == 1 {
			switch remainder {
			case 1:
			case 2, 3:
				b.labelMiddle = b.labelMiddle.resize(1, func(value string, length int) string { return extend(value, 0, length) })
			default:
				logRemainder(resizeStart, remainder, hostCount)
			}
		} else {
			switch remainder {
			case 1, 2, 3:
			case 4, 5, 6, 7:
				b.labelMiddle = b.labelMiddle.resize(1, func(value string, length int) string { return extend(value, 0, length) })
			default:
				logRemainder(resizeStart, remainder, hostCount)
			}
		}
	}
	resizeRemainderColumn := func(b *box, remainder, hostCount int) {
		resizeStart := time.Now()
		if hostCount == 1 {
			switch remainder {
			case 1, 3:
				b.labelRight = b.labelRight.resize(1, func(value string, length int) string { return extend(value, 0, length) })
			case 2:
			default:
				logRemainder(resizeStart, remainder, hostCount)
			}
		} else {
			switch remainder {
			case 1, 4, 5:
			case 2, 3, 6, 7:
				b.labelRight = b.labelRight.resize(1, func(value string, length int) string { return extend(value, 0, length) })
			default:
				logRemainder(resizeStart, remainder, hostCount)
			}
		}
	}
	resizeRemainderDivider := func(b *box, remainder, hostCount int) {
		resizeStart := time.Now()
		if hostCount > 1 {
			switch remainder {
			case 1, 3, 5, 7:
				b.labelLeft = b.labelLeft.resize(1, func(value string, length int) string { return " " })
			case 2, 4, 6:
			default:
				logRemainder(resizeStart, remainder, hostCount)
			}
		}
	}
	t_0_0 := box{labelLeft: text{
		ascii:   "+= ",
		unicode: "╭─┐",
	}, labelMiddle: text{
		ascii:   "           ",
		unicode: "           ",
	}, labelRight: text{
		ascii:   " ================================================================",
		unicode: "┌────────────────────────────────────────────────────────────────",
	}, resizeCount: 4, kind: boxTitle, resizeIncrement: resizeIncrementBorder, resizeRemainder: resizeRemainderSpacer}
	t_0_1 := box{labelLeft: text{
		ascii:   "= ",
		unicode: "─┐",
	}, labelMiddle: text{
		ascii:   "    ",
		unicode: "    ",
	}, labelRight: text{
		ascii:   " =+",
		unicode: "┌─╮",
	}, kind: boxControls}
	b_X_Y := box{labelLeft: text{ascii: "|", unicode: "│"}, labelMiddle: text{ascii: " ", unicode: " "}, labelRight: text{ascii: "", unicode: ""}, kind: boxBorder, resizeRemainder: resizeRemainderBorder}
	b_X_Z := box{labelRight: text{ascii: "|", unicode: "│"}, labelMiddle: text{ascii: " ", unicode: " "}, labelLeft: text{ascii: "", unicode: ""}, kind: boxBorder, resizeRemainder: resizeRemainderBorder}
	d_1_0 := box{labelMiddle: text{ascii: metric.GetIDLabel(metric.MetricHostUsedProcessor) + " "}, valueLength: 8, valueSuffix: "%", valueKind: valueHistogram, metricID: metric.MetricHostUsedProcessor, resizeIncrement: resizeIncrementHistogramValue}
	d_1_1 := box{labelMiddle: text{ascii: metric.GetIDLabel(metric.MetricHostFailedLogs) + " "}, valueLength: 8, valueSuffix: "%", valueKind: valueHistogram, labelLeft: text{ascii: "    "}, metricID: metric.MetricHostFailedLogs, resizeIncrement: resizeIncrementHistogramValue}
	d_1_2 := box{labelMiddle: text{ascii: metric.GetIDLabel(metric.MetricHostWarnTemperature) + " "}, valueLength: 8, valueSuffix: "%", valueKind: valueHistogram, metricID: metric.MetricHostWarnTemperature, resizeIncrement: resizeIncrementHistogramValue}
	d_1_3 := box{labelMiddle: text{ascii: metric.GetIDLabel(metric.MetricHostUsedHomeSpace) + " "}, valueLength: 8, valueSuffix: "%", valueKind: valueHistogram, labelLeft: text{ascii: "    "}, metricID: metric.MetricHostUsedHomeSpace, resizeIncrement: resizeIncrementHistogramValue}
	d_2_0 := box{labelMiddle: text{ascii: metric.GetIDLabel(metric.MetricHostUsedMemory) + " "}, valueLength: 8, valueSuffix: "%", valueKind: valueHistogram, metricID: metric.MetricHostUsedMemory, resizeIncrement: resizeIncrementHistogramValue}
	d_2_1 := box{labelMiddle: text{ascii: metric.GetIDLabel(metric.MetricHostFailedShares) + " "}, valueLength: 8, valueSuffix: "%", valueKind: valueHistogram, labelLeft: text{ascii: "    "}, metricID: metric.MetricHostFailedShares, resizeIncrement: resizeIncrementHistogramValue}
	d_2_2 := box{labelMiddle: text{ascii: metric.GetIDLabel(metric.MetricHostSpinFanSpeed) + " "}, valueLength: 8, valueSuffix: "%", valueKind: valueHistogram, metricID: metric.MetricHostSpinFanSpeed, resizeIncrement: resizeIncrementHistogramValue}
	d_2_3 := box{labelMiddle: text{ascii: metric.GetIDLabel(metric.MetricHostUsedShareSpace) + " "}, valueLength: 8, valueSuffix: "%", valueKind: valueHistogram, labelLeft: text{ascii: "    "}, metricID: metric.MetricHostUsedShareSpace, resizeIncrement: resizeIncrementHistogramValue}
	d_3_0 := box{labelMiddle: text{ascii: metric.GetIDLabel(metric.MetricHostAllocatedMemory) + " "}, valueLength: 8, valueSuffix: "%", valueKind: valueHistogram, metricID: metric.MetricHostAllocatedMemory, resizeIncrement: resizeIncrementHistogramValue}
	d_3_1 := box{labelMiddle: text{ascii: metric.GetIDLabel(metric.MetricHostFailedBackupStages) + " "}, valueLength: 8, valueSuffix: "%", valueKind: valueHistogram, labelLeft: text{ascii: "    "}, metricID: metric.MetricHostFailedBackupStages, resizeIncrement: resizeIncrementHistogramValue}
	d_3_2 := box{labelMiddle: text{ascii: metric.GetIDLabel(metric.MetricHostUsedDriveLife) + " "}, valueLength: 8, valueSuffix: "%", valueKind: valueHistogram, metricID: metric.MetricHostUsedDriveLife, resizeIncrement: resizeIncrementHistogramValue}
	d_3_3 := box{labelMiddle: text{ascii: metric.GetIDLabel(metric.MetricHostUsedBackupSpace) + " "}, valueLength: 8, valueSuffix: "%", valueKind: valueHistogram, labelLeft: text{ascii: "    "}, metricID: metric.MetricHostUsedBackupSpace, resizeIncrement: resizeIncrementHistogramValue}
	s_X_0 := box{labelRight: text{
		ascii:   "+--------------------------------------------------------------------------------------+",
		unicode: "├──────────────────────────────────────────────────────────────────────────────────────┤",
	}, kind: boxBorder, resizeCount: 4, resizeIncrement: resizeIncrementBorder, resizeRemainder: resizeRemainderSpacer}
	s_Y_Y := box{labelRight: text{ascii: "    "}, kind: boxBorder, resizeRemainder: resizeRemainderColumn}
	l_5_0 := box{labelMiddle: text{ascii: metric.GetIDLabel(metric.MetricServiceName)}, labelRight: text{ascii: "        "}, kind: boxLabel}
	l_5_1 := box{labelMiddle: text{ascii: metric.GetIDLabel(metric.MetricServiceVersion)}, labelLeft: text{ascii: "  "}, labelRight: text{ascii: "  "}, kind: boxLabel}
	l_5_2 := box{labelMiddle: text{ascii: metric.GetIDLabel(metric.MetricServiceUsedProcessor)}, labelLeft: text{ascii: "       "}, labelRight: text{ascii: "    "}, kind: boxLabel, resizeCount: 2, resizeIncrement: resizeIncrementHistogramLabel}
	l_5_3 := box{labelMiddle: text{ascii: metric.GetIDLabel(metric.MetricServiceUsedMemory)}, labelLeft: text{ascii: "    "}, labelRight: text{ascii: "    "}, kind: boxLabel, resizeCount: 2, resizeIncrement: resizeIncrementHistogramLabel}
	l_5_4 := box{labelMiddle: text{ascii: metric.GetIDLabel(metric.MetricServiceBackupStatus)}, labelLeft: text{ascii: "   "}, kind: boxLabel}
	l_5_5 := box{labelMiddle: text{ascii: metric.GetIDLabel(metric.MetricServiceHealthStatus)}, labelLeft: text{ascii: "  "}, kind: boxLabel}
	l_5_6 := box{labelMiddle: text{ascii: metric.GetIDLabel(metric.MetricServiceConfiguredStatus)}, labelLeft: text{ascii: "  "}, kind: boxLabel}
	l_5_7 := box{labelMiddle: text{ascii: metric.GetIDLabel(metric.MetricServiceRestartCount)}, labelLeft: text{ascii: "  "}, kind: boxLabel}
	l_5_8 := box{labelMiddle: text{ascii: metric.GetIDLabel(metric.MetricServiceUpTime)}, labelLeft: text{ascii: "  "}, kind: boxLabel}
	d_X_0 := box{valueLength: 14, labelRight: text{ascii: " "}, valueAlign: boxLeft, valueOptional: true, valueKind: valueText, metricID: metric.MetricServiceName}
	d_X_1 := box{valueLength: 11, labelRight: text{ascii: " "}, valueOptional: true, valueKind: valueText, metricID: metric.MetricServiceVersion}
	d_X_2 := box{labelLeft: text{ascii: "  "}, valueSuffix: "%", valueLength: 10, valueOptional: true, valueKind: valueHistogram, metricID: metric.MetricServiceUsedProcessor, resizeCount: 2, resizeIncrement: resizeIncrementHistogramValue}
	d_X_3 := box{labelLeft: text{ascii: ""}, valueSuffix: "%", valueLength: 10, valueOptional: true, valueKind: valueHistogram, metricID: metric.MetricServiceUsedMemory, resizeCount: 2, resizeIncrement: resizeIncrementHistogramValue}
	d_X_4 := box{labelLeft: text{ascii: "    "}, labelRight: text{ascii: " "}, valueLength: 1, valueOptional: true, valueKind: valueBool, metricID: metric.MetricServiceBackupStatus}
	d_X_5 := box{labelLeft: text{ascii: "   "}, labelRight: text{ascii: " "}, valueLength: 1, valueOptional: true, valueKind: valueBool, metricID: metric.MetricServiceHealthStatus}
	d_X_6 := box{labelLeft: text{ascii: "   "}, labelRight: text{ascii: " "}, valueLength: 1, valueOptional: true, valueKind: valueBool, metricID: metric.MetricServiceConfiguredStatus}
	d_X_7 := box{labelLeft: text{ascii: "   "}, labelRight: text{ascii: " "}, valueLength: 1, valueOptional: true, metricID: metric.MetricServiceRestartCount}
	d_X_8 := box{labelLeft: text{ascii: "    "}, labelRight: text{ascii: ""}, valueLength: 4, valueOptional: true, valueKind: valueTime, metricID: metric.MetricServiceUpTime}
	s_X_Y := box{labelRight: text{
		ascii:   "                                                                                        ",
		unicode: "╰──────────────────────────────────────────────────────────────────────────────────────╯",
	}, kind: boxBorder, resizeCount: 4, resizeIncrement: resizeIncrementBorder, resizeRemainder: resizeRemainderSpacer}
	v_X_X := box{labelLeft: text{ascii: ""}, kind: boxDivider, resizeRemainder: resizeRemainderDivider}
	return compile(useUnicode, [][]box{
		{t_0_0, t_0_1, v_X_X},
		{b_X_Y, d_1_0, d_1_1, s_Y_Y, d_1_2, d_1_3, b_X_Z, v_X_X},
		{b_X_Y, d_2_0, d_2_1, s_Y_Y, d_2_2, d_2_3, b_X_Z, v_X_X},
		{b_X_Y, d_3_0, d_3_1, s_Y_Y, d_3_2, d_3_3, b_X_Z, v_X_X},
		{s_X_0, v_X_X},
		{b_X_Y, l_5_0, l_5_1, l_5_2, s_Y_Y, l_5_3, l_5_4, l_5_5, l_5_6, l_5_7, l_5_8, b_X_Z, v_X_X},
		{s_X_0, v_X_X},
		{b_X_Y, d_X_0, d_X_1, d_X_2, s_Y_Y, d_X_3, d_X_4, d_X_5, d_X_6, d_X_7, d_X_8, b_X_Z, v_X_X},
		{b_X_Y, d_X_0, d_X_1, d_X_2, s_Y_Y, d_X_3, d_X_4, d_X_5, d_X_6, d_X_7, d_X_8, b_X_Z, v_X_X},
		{b_X_Y, d_X_0, d_X_1, d_X_2, s_Y_Y, d_X_3, d_X_4, d_X_5, d_X_6, d_X_7, d_X_8, b_X_Z, v_X_X},
		{b_X_Y, d_X_0, d_X_1, d_X_2, s_Y_Y, d_X_3, d_X_4, d_X_5, d_X_6, d_X_7, d_X_8, b_X_Z, v_X_X},
		{b_X_Y, d_X_0, d_X_1, d_X_2, s_Y_Y, d_X_3, d_X_4, d_X_5, d_X_6, d_X_7, d_X_8, b_X_Z, v_X_X},
		{b_X_Y, d_X_0, d_X_1, d_X_2, s_Y_Y, d_X_3, d_X_4, d_X_5, d_X_6, d_X_7, d_X_8, b_X_Z, v_X_X},
		{b_X_Y, d_X_0, d_X_1, d_X_2, s_Y_Y, d_X_3, d_X_4, d_X_5, d_X_6, d_X_7, d_X_8, b_X_Z, v_X_X},
		{s_X_Y, v_X_X},
	})
}

type text struct {
	ascii   string
	unicode string
}

func logRemainder(started time.Time, remainder, hostCount int) {
	scribe.Log(scribe.SourceDisplayLayout, scribe.SubjectNone, scribe.ActionDiscover).Errorf("unusable", started, "[%2d] remainder across [%2d] hosts", remainder, hostCount)
}

func (t text) pick(useUnicode bool) string {
	switch {
	case t.ascii == "":
		return t.unicode
	case t.unicode == "":
		return t.ascii
	case useUnicode:
		return t.unicode
	default:
		return t.ascii
	}
}

func (t text) resize(increment int, resizeFunc func(value string, length int) string) text {
	ascii := resizeFunc(t.ascii, increment+runewidth.StringWidth(t.ascii))
	unicode := resizeFunc(t.unicode, increment+runewidth.StringWidth(t.unicode))
	if t.unicode == "" {
		unicode = ascii
	}
	if t.ascii == "" {
		ascii = unicode
	}
	return text{ascii: ascii, unicode: unicode}
}

func compile(useUnicode bool, layout [][]box) [][]box {
	result := make([][]box, 0, len(layout))
	for row := range layout {
		var rowLabels strings.Builder
		for column := range layout[row] {
			layout[row][column].compile(false, true)
			labelled := &layout[row][column]
			rowLabels.WriteString(strings.TrimSpace(labelled.labelLeft.pick(useUnicode) + labelled.labelMiddle.pick(useUnicode) + labelled.labelRight.pick(useUnicode)))
		}
		if rowLabels.Len() > 0 {
			result = append(result, layout[row])
		}
	}
	return result
}

func (b *box) compile(useUnicode, force bool) {
	if b.compiled != nil && !force {
		return
	}
	if b.compiled == nil {
		b.compiled = &compiled{}
	}
	b.compiled.labelLeftLength = runewidth.StringWidth(b.labelLeft.pick(useUnicode))
	b.compiled.labelMiddleLength = runewidth.StringWidth(b.labelMiddle.pick(useUnicode))
	b.compiled.labelRightLength = runewidth.StringWidth(b.labelRight.pick(useUnicode))
	b.compiled.valueSuffixLength = runewidth.StringWidth(b.valueSuffix)
	b.compiled.valueOffset = b.compiled.labelLeftLength + b.compiled.labelMiddleLength
	b.compiled.length = b.compiled.valueOffset + b.valueLength + b.compiled.labelRightLength + b.compiled.valueSuffixLength
}

func (b *box) resizes() int {
	if b.resizeCount == 0 && b.resizeIncrement != nil {
		return 1
	}
	return b.resizeCount
}

func (b *box) resize(useUnicode bool, increment, remainder, hostCount int) {
	resized := false
	if b.resizeIncrement != nil && increment > 0 {
		b.resizeIncrement(b, increment*b.resizes(), hostCount)
		resized = true
	}
	if b.resizeRemainder != nil && remainder > 0 {
		b.resizeRemainder(b, remainder, hostCount)
		resized = true
	}
	if resized {
		b.compile(useUnicode, true)
	}
}

func (b *box) set(
	useUnicode bool,
	labelLeft text, labelLeftAlign boxAlign, labelLeftLength int,
	labelMiddle text, labelMiddleAlign boxAlign, labelMiddleLength int,
	labelRight text, labelRightAlign boxAlign, labelRightLength int,
) {
	lhs := pad(labelLeft.pick(useUnicode), labelLeftAlign, labelLeftLength)
	mid := pad(labelMiddle.pick(useUnicode), labelMiddleAlign, labelMiddleLength)
	rhs := pad(labelRight.pick(useUnicode), labelRightAlign, labelRightLength)
	b.labelLeft = text{lhs, lhs}
	b.labelMiddle = text{mid, mid}
	b.labelRight = text{rhs, rhs}
	b.compile(useUnicode, true)
}

func (b *box) length(useUnicode bool) int {
	b.compile(useUnicode, false)
	return b.compiled.length
}

func (b *box) draw(display *Display, force bool) {
	if display.terminal == nil {
		return
	}
	b.compile(display.useUnicode, false)
	row, column := b.position.rows, b.position.columns
	draw := func(label string, c colour) {
		if label != "" && force == b.valueOptional {
			display.terminal.draw(column, row, label, c)
		}
		column += runewidth.StringWidth(label)
	}
	advance := func(label string) {
		column += runewidth.StringWidth(label)
	}
	borderColour := colourChat
	if b.kind == boxBorder || b.kind == boxTitle || b.kind == boxControls {
		borderColour = colourGrowl
	}
	draw(b.labelLeft.pick(display.useUnicode), borderColour)
	if b.kind == boxControls && force == b.valueOptional {
		mid := b.labelMiddle.pick(display.useUnicode)
		parts := tokens(mid)
		if len(parts) > 1 {
			arrow := parts[0]
			rest := strings.Join(parts[1:], "")
			display.terminal.draw(column, row, arrow, colourGrowl)
			arrowLength := runewidth.StringWidth(arrow)
			beforeSlash, slashAndAfter, hasSlash := strings.Cut(rest, "/")
			if hasSlash && beforeSlash != "" {
				display.terminal.draw(column+arrowLength, row, beforeSlash, colourGrowl)
				display.terminal.draw(column+arrowLength+runewidth.StringWidth(beforeSlash), row, "/"+slashAndAfter, colourChat)
			} else {
				display.terminal.draw(column+arrowLength, row, rest, colourGrowl)
			}
		}
		column += runewidth.StringWidth(mid)
	} else if b.kind == boxTitle {
		draw(b.labelMiddle.pick(display.useUnicode), colourMurmur)
	} else if b.kind == boxBorder {
		draw(b.labelMiddle.pick(display.useUnicode), colourGrowl)
	} else {
		draw(b.labelMiddle.pick(display.useUnicode), colourChat)
	}
	advance(strings.Repeat(" ", b.valueLength+b.compiled.valueSuffixLength))
	draw(b.labelRight.pick(display.useUnicode), borderColour)
}

func (b *box) drawLabels(display *Display) {
	b.draw(display, false)
	b.drawValue(display)
}

func (b *box) drawValue(display *Display) {
	if b.recordGUID == nil || display.terminal == nil || display.cache == nil {
		return
	}
	b.compile(display.useUnicode, false)
	var record *metric.Record
	var ok bool
	if metric.GetIDKind(b.recordGUID.ID) == metric.MetricKindService {
		record, ok = display.cache.LoadByID(b.recordGUID.ID, b.recordGUID.Host, b.recordGUID.ServiceIndex)
	} else {
		record, ok = display.cache.Load(*b.recordGUID)
	}
	failed := ok && record != nil && record.Value.Failed
	named := b.recordGUID.ID == metric.MetricServiceName
	overflow := false
	if b.isLast {
		nextRecord, nextOk := display.cache.LoadByID(b.recordGUID.ID, b.recordGUID.Host, display.maxServices)
		overflow = nextOk && nextRecord != nil && nextRecord.Value.Pulse != nil && !nextRecord.Value.Pulse.IsZero()
	}
	if !ok || record == nil || record.Value.Pulse == nil || record.Value.Pulse.IsZero() || failed && !named && !overflow {
		display.terminal.draw(
			b.position.columns+b.compiled.valueOffset,
			b.position.rows,
			strings.Repeat(" ", b.valueLength+b.compiled.valueSuffixLength),
			colourChat,
		)
		if label := b.labelMiddle.pick(display.useUnicode); failed && label != "" {
			display.terminal.draw(b.position.columns+b.compiled.labelLeftLength, b.position.rows, label, colourAlert)
		}
		return
	}
	if label := b.labelMiddle.pick(display.useUnicode); !b.valueOptional && label != "" {
		display.terminal.draw(b.position.columns+b.compiled.labelLeftLength, b.position.rows, label, colourChat)
	}
	if overflow {
		b.draw(display, true)
		display.terminal.draw(
			b.position.columns+b.compiled.valueOffset+b.compiled.valueSuffixLength,
			b.position.rows,
			pad("~", b.valueAlign, b.valueLength)+strings.Repeat(" ", b.compiled.valueSuffixLength),
			colourChat,
		)
		return
	}
	location := dimensions{b.position.rows, b.position.columns + b.compiled.valueOffset}
	b.draw(display, true)
	c := colourWarn
	if !record.Value.Pulse.OK {
		c = colourAlert
	} else if record.Value.Trend != nil && record.Value.Trend.OK {
		c = colourCheer
	}
	sleeping := metric.GetIDKind(b.recordGUID.ID) == metric.MetricKindService && resolveServiceRunState(display, b.recordGUID) == serviceRunStateSleeping
	if sleeping {
		c = colourChat
	}
	valueString := ""
	switch b.valueKind {
	case valueBool:
		symbol := textCross.pick(display.useUnicode)
		if record.Value.Pulse.OK {
			symbol = textTick.pick(display.useUnicode)
		}
		valueString = pad(symbol, b.valueAlign, b.valueLength)
	case valueTime:
		secondsRaw := record.Value.Pulse.Value()
		secondsValue, err := strconv.ParseFloat(secondsRaw, 64)
		if err != nil {
			valueString = pad(secondsRaw, b.valueAlign, b.valueLength) + b.valueSuffix
			break
		}
		valueString = pad(duration(secondsValue), b.valueAlign, b.valueLength) + b.valueSuffix
	case valueHistogram:
		value := record.Value.Pulse.Value()
		fallback := pad(value, b.valueAlign, b.valueLength) + b.valueSuffix
		if b.valueLength < 6 {
			valueString = fallback
			break
		}
		percent, err := strconv.ParseFloat(value, 64)
		if err != nil {
			valueString = fallback
			break
		}
		if percent < 0 {
			percent = 0
		}
		if percent > 100 {
			percent = 100
		}
		barWidth := b.valueLength - 4
		barChar := textBar.pick(display.useUnicode)
		barSuffix := " "
		unfilledChar := barChar
		if !display.useUnicode {
			barWidth = b.valueLength - 6
			barSuffix = "| "
			unfilledChar = " "
		}
		filled := int(math.Round(percent * float64(barWidth) / 100))
		if percent > 0 && filled == 0 {
			filled = 1
		}
		filled = min(max(filled, 0), barWidth)
		percentInt := min(max(int(math.Round(percent)), 0), 100)
		column := location.columns
		if !display.useUnicode {
			display.terminal.draw(column, location.rows, "|", c)
			column++
		}
		if filled > 0 {
			display.terminal.draw(column, location.rows, strings.Repeat(barChar, filled), c)
		}
		if filled < barWidth {
			display.terminal.draw(column+filled, location.rows, strings.Repeat(unfilledChar, barWidth-filled), colourWhisper)
		}
		display.terminal.draw(column+barWidth, location.rows, barSuffix+pad(strconv.Itoa(percentInt), boxRight, 3)+b.valueSuffix, c)
		return
	default:
		valueString = pad(record.Value.Pulse.Value(), b.valueAlign, b.valueLength) + b.valueSuffix
	}
	isServiceLabel := b.recordGUID.ID == metric.MetricServiceName || b.recordGUID.ID == metric.MetricServiceVersion
	metricKind := metric.GetIDKind(b.recordGUID.ID)
	if metricKind != metric.MetricKindService && metricKind != metric.MetricKindHost {
		if c != colourWarn && c != colourAlert {
			c = colourChat
		}
	} else if display.useUnicode && isServiceLabel {
		if c == colourCheer {
			c = colourChat
		}
	}
	if named && !sleeping {
		for _, id := range display.serviceShown {
			sibling, siblingOK := display.cache.LoadByID(id, b.recordGUID.Host, b.recordGUID.ServiceIndex)
			if siblingOK && sibling != nil && sibling.Value.Failed {
				c = colourAlert
				break
			}
		}
	}
	display.terminal.draw(
		location.columns,
		location.rows,
		valueString,
		c,
	)
}

func (b *box) clone() *box {
	clone := *b
	if b.recordGUID != nil {
		recordClone := *b.recordGUID
		clone.recordGUID = &recordClone
	}
	if b.position != nil {
		posClone := *b.position
		clone.position = &posClone
	}
	if b.compiled != nil {
		compiledClone := *b.compiled
		clone.compiled = &compiledClone
	}
	return &clone
}

type serviceRunState int

const (
	serviceRunStateUnknown serviceRunState = iota
	serviceRunStateRunning
	serviceRunStateStopped
	serviceRunStateSleeping
)

func resolveServiceRunState(display *Display, guid *metric.RecordGUID) serviceRunState {
	isOK := func(id metric.ID) (bool, bool) {
		record, ok := display.cache.LoadByID(id, guid.Host, guid.ServiceIndex)
		if !ok || record == nil || record.Value.Pulse == nil || record.Value.Pulse.IsZero() {
			return false, false
		}
		return record.Value.Pulse.OK, true
	}
	aggregateOK, aggregateKnown := isOK(metric.MetricServiceName)
	healthOK, healthKnown := isOK(metric.MetricServiceHealthStatus)
	configuredOK, configuredKnown := isOK(metric.MetricServiceConfiguredStatus)
	if !aggregateKnown || !healthKnown || !configuredKnown {
		return serviceRunStateUnknown
	}
	if !aggregateOK {
		return serviceRunStateStopped
	}
	if healthOK && configuredOK {
		return serviceRunStateRunning
	}
	return serviceRunStateSleeping
}

func duration(seconds float64) string {
	if math.IsNaN(seconds) || math.IsInf(seconds, 0) || seconds < 0 {
		return "~"
	}
	if seconds < 1 {
		return "0s"
	}
	type unit struct {
		label   string
		seconds float64
	}
	units := []unit{
		{label: "y", seconds: 365 * 24 * 60 * 60},
		{label: "d", seconds: 24 * 60 * 60},
		{label: "h", seconds: 60 * 60},
		{label: "m", seconds: 60},
		{label: "s", seconds: 1},
	}
	for _, u := range units {
		value := int64(seconds / u.seconds)
		if value == 0 {
			continue
		}
		if value > 999 {
			return "~"
		}
		return strconv.FormatInt(value, 10) + u.label
	}
	return "0s"
}

func pad(base string, align boxAlign, length int) string {
	if length <= 0 {
		return repeat(" ", 1, 0, length)
	}
	baseWidth := runewidth.StringWidth(base)
	if baseWidth == 0 {
		return strings.Repeat(" ", length)
	}
	if baseWidth > length {
		return runewidth.Truncate(base, length, "~")
	}
	padding := length - baseWidth
	if padding == 0 {
		return base
	}
	spaces := strings.Repeat(" ", padding)
	if align == boxRight {
		return spaces + base
	}
	if align == boxMiddle {
		leftPad := padding / 2
		rightPad := padding - leftPad
		return strings.Repeat(" ", leftPad) + base + strings.Repeat(" ", rightPad)
	}
	return base + spaces
}

func extend(base string, offset, length int) string {
	if length <= 0 || base == "" {
		return ""
	}
	baseWidth := runewidth.StringWidth(base)
	if baseWidth == 0 {
		return ""
	}
	if baseWidth > length {
		return base
	}
	if baseWidth == length {
		return base
	}
	tokens := tokens(base)
	if len(tokens) == 0 {
		return ""
	}
	if offset < 0 {
		offset = 0
	}
	if offset >= len(tokens) {
		offset = len(tokens) - 1
	}
	repeatToken := tokens[offset]
	repeatWidth := runewidth.StringWidth(repeatToken)
	if repeatWidth <= 0 {
		return base
	}
	insertWidth := length - baseWidth
	insertCount := insertWidth / repeatWidth
	if insertCount <= 0 || insertCount*repeatWidth != insertWidth {
		return base
	}
	var builder strings.Builder
	for i, token := range tokens {
		if i == offset {
			builder.WriteString(strings.Repeat(repeatToken, insertCount))
		}
		builder.WriteString(token)
	}
	return builder.String()
}

func repeat(base string, prefixCount, suffixCount, length int) string {
	if length <= 0 || base == "" {
		return ""
	}
	tokens := tokens(base)
	if len(tokens) == 0 {
		return ""
	}
	if prefixCount < 0 {
		prefixCount = 0
	}
	if suffixCount < 0 {
		suffixCount = 0
	}
	if prefixCount > len(tokens) {
		prefixCount = len(tokens)
	}
	if suffixCount > len(tokens)-prefixCount {
		suffixCount = len(tokens) - prefixCount
	}
	pattern := make([]string, 0, prefixCount+suffixCount)
	for i := 0; i < prefixCount; i++ {
		pattern = append(pattern, tokens[i])
	}
	for i := len(tokens) - suffixCount; i < len(tokens); i++ {
		pattern = append(pattern, tokens[i])
	}
	if len(pattern) == 0 {
		return ""
	}
	patternWidth := 0
	for _, token := range pattern {
		patternWidth += runewidth.StringWidth(token)
	}
	if patternWidth <= 0 {
		return ""
	}
	var builder strings.Builder
	currentWidth := 0
	for currentWidth < length {
		for _, token := range pattern {
			tokenWidth := runewidth.StringWidth(token)
			if tokenWidth <= 0 {
				continue
			}
			if currentWidth+tokenWidth > length {
				break
			}
			builder.WriteString(token)
			currentWidth += tokenWidth
			if currentWidth >= length {
				break
			}
		}
	}
	return builder.String()
}

func tokens(value string) []string {
	tokens := make([]string, 0, len(value))
	for _, r := range value {
		tokens = append(tokens, string(r))
	}
	return tokens
}
