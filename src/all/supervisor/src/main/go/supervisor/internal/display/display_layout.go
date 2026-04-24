package display

import (
	"log/slog"
	"math"
	"strconv"
	"strings"
	"supervisor/internal/metric"

	"github.com/mattn/go-runewidth"
)

var (
	textBar   = text{ascii: "|", unicode: "■"}
	textTick  = text{ascii: "+", unicode: "✔"}
	textCross = text{ascii: "-", unicode: "✖"}
	textUp    = text{ascii: "^", unicode: "↑"}
	textDown  = text{ascii: "v", unicode: "↓"}
)

type boxKind int

const (
	boxDatum boxKind = iota
	boxTitle
	boxLabel
	boxCtrls
	boxBordr
	boxDivdr
)

type boxAlign int

const (
	boxRhs boxAlign = iota
	boxLhs
	boxMid
)

type boxValKind int

const (
	valText boxValKind = iota
	valTime
	valHist
	valBool
)

type box struct {
	kind       boxKind
	lblLhs     text
	lblMid     text
	lblRhs     text
	valLen     int
	valOpt     bool
	valAln     boxAlign
	valSfx     string
	valKind    boxValKind
	position   *dimensions
	isLast     bool
	metricID   metric.ID
	recordGUID *metric.RecordGUID
	compiled   *compiled
	resizeCnt  int
	resizeInc  func(b *box, inc, hostCount int)
	resizeRem  func(b *box, rem, hostCount int)
}

type compiled struct {
	length    int
	lblLhsLen int
	lblMidLen int
	lblRhsLen int
	valSfxLen int
	valOffset int
}

// noinspection GoSnakeCaseUsage
func compactDisplayLayout(useUnicode bool) [][]box {
	resizeIncValService := func(b *box, inc, hostCount int) { b.valLen += inc }
	resizeIncLblService := func(b *box, inc, hostCount int) {
		b.lblRhs = b.lblRhs.resize(inc, func(value string, length int) string {
			return value + repeat(value, 0, 1, length-runewidth.StringWidth(value))
		})
	}
	resizeIncSpacer := func(b *box, inc, hostCount int) {
		b.lblLhs = b.lblLhs.resize(inc, func(value string, length int) string {
			return value + repeat(value, 0, 1, length-runewidth.StringWidth(value))
		})
	}
	resizeIncBorder := func(b *box, inc, hostCount int) {
		b.lblRhs = b.lblRhs.resize(inc, func(value string, length int) string { return extend(value, 1, length) })
	}
	resizeRemSpacer := func(b *box, rem, hostCount int) {
		if hostCount == 1 {
			b.lblRhs = b.lblRhs.resize(rem, func(value string, length int) string { return extend(value, 1, length) })
		} else {
			switch rem {
			case 1, 2, 3, 6:
			case 4, 5:
				b.lblRhs = b.lblRhs.resize(2, func(value string, length int) string { return extend(value, 1, length) })
			default:
				slog.Error("layout resize failed, invalid remainder", "hosts", hostCount, "remainder", rem)
			}
		}
	}
	resizeRemBorder := func(b *box, rem, hostCount int) {
		if hostCount == 1 {
			switch rem {
			case 1, 3:
			case 2:
				b.lblMid = b.lblMid.resize(1, func(value string, length int) string { return " " })
			default:
				slog.Error("layout resize failed, invalid remainder", "hosts", hostCount, "remainder", rem)
			}
		} else {
			switch rem {
			case 1, 2, 3, 6:
			case 4, 5:
				b.lblMid = b.lblMid.resize(1, func(value string, length int) string { return " " })
			default:
				slog.Error("layout resize failed, invalid remainder", "hosts", hostCount, "remainder", rem)
			}
		}
	}
	resizeRemColumn := func(b *box, rem, hostCount int) {
		if hostCount == 1 {
			switch rem {
			case 1:
				b.lblRhs = b.lblRhs.resize(1, func(value string, length int) string { return extend(value, 0, length) })
			case 2, 3:
			default:
				slog.Error("layout resize failed, invalid remainder", "hosts", hostCount, "remainder", rem)
			}
		}
	}
	resizeRemDivider := func(b *box, rem, hostCount int) {
		if hostCount > 1 {
			switch rem {
			case 1, 2, 3:
				b.lblLhs = b.lblLhs.resize(1, func(value string, length int) string { return repeat(" ", 1, 0, rem) })
			case 4, 6:
			case 5:
				b.lblLhs = b.lblLhs.resize(1, func(value string, length int) string { return repeat(" ", 1, 0, 1) })
			default:
				slog.Error("layout resize failed, invalid remainder", "hosts", hostCount, "remainder", rem)
			}
		}
	}

	t_0_0 := box{lblLhs: text{
		ascii:   "+= ",
		unicode: "╭─┐",
	}, lblMid: text{
		ascii:   "           ",
		unicode: "           ",
	}, lblRhs: text{
		ascii:   " =================================",
		unicode: "┌─────────────────────────────────",
	}, resizeCnt: 3, kind: boxTitle, resizeInc: resizeIncBorder, resizeRem: resizeRemSpacer}
	t_0_1 := box{lblLhs: text{
		ascii:   "= ",
		unicode: "─┐",
	}, lblMid: text{
		ascii:   "    ",
		unicode: "    ",
	}, lblRhs: text{
		ascii:   " =+",
		unicode: "┌─╮",
	}, kind: boxCtrls}
	b_X_Y := box{lblLhs: text{ascii: "|", unicode: "│"}, lblMid: text{ascii: "", unicode: ""}, lblRhs: text{ascii: "", unicode: ""}, kind: boxBordr, resizeRem: resizeRemBorder}
	b_X_Z := box{lblRhs: text{ascii: "|", unicode: "│"}, lblMid: text{ascii: "", unicode: ""}, lblLhs: text{ascii: "", unicode: ""}, kind: boxBordr, resizeRem: resizeRemBorder}

	d_1_0 := box{lblMid: text{ascii: "Used CPU "}, valLen: 3, valSfx: "%", metricID: metric.MetricHostUsedProcessor}
	d_1_1 := box{lblMid: text{ascii: "Fail LOG "}, valLen: 3, valSfx: "%", lblLhs: text{ascii: " "}, metricID: metric.MetricHostFailedLogs, resizeInc: resizeIncSpacer}
	d_1_2 := box{lblMid: text{ascii: "Warn TEM "}, valLen: 3, valSfx: "%", metricID: metric.MetricHostWarnTemperatureOfMax}
	d_1_3 := box{lblMid: text{ascii: "Used SYS "}, valLen: 3, valSfx: "%", lblLhs: text{ascii: " "}, metricID: metric.MetricHostUsedSystemSpace, resizeInc: resizeIncSpacer}

	d_2_0 := box{lblMid: text{ascii: "Used RAM "}, valLen: 3, valSfx: "%", metricID: metric.MetricHostUsedMemory}
	d_2_1 := box{lblMid: text{ascii: "Fail SHR "}, valLen: 3, valSfx: "%", lblLhs: text{ascii: " "}, metricID: metric.MetricHostFailedShares, resizeInc: resizeIncSpacer}
	d_2_2 := box{lblMid: text{ascii: "Revs Fan "}, valLen: 3, valSfx: "%", metricID: metric.MetricHostSpinFanSpeedOfMax}
	d_2_3 := box{lblMid: text{ascii: "Used SHR "}, valLen: 3, valSfx: "%", lblLhs: text{ascii: " "}, metricID: metric.MetricHostUsedShareSpace, resizeInc: resizeIncSpacer}

	d_3_0 := box{lblMid: text{ascii: "Aloc RAM "}, valLen: 3, valSfx: "%", metricID: metric.MetricHostAllocatedMemory}
	d_3_1 := box{lblMid: text{ascii: "Fail BCK "}, valLen: 3, valSfx: "%", lblLhs: text{ascii: " "}, metricID: metric.MetricHostFailedBackups, resizeInc: resizeIncSpacer}
	d_3_2 := box{lblMid: text{ascii: "Life SSD "}, valLen: 3, valSfx: "%", metricID: metric.MetricHostLifeUsedDrives}
	d_3_3 := box{lblMid: text{ascii: "Used BKP "}, valLen: 3, valSfx: "%", lblLhs: text{ascii: " "}, metricID: metric.MetricHostUsedBackupSpace, resizeInc: resizeIncSpacer}

	s_X_0 := box{lblRhs: text{
		ascii:   "+-------------------------------------------------------+",
		unicode: "├───────────────────────────────────────────────────────┤",
	}, kind: boxBordr, resizeCnt: 3, resizeInc: resizeIncBorder, resizeRem: resizeRemSpacer}
	s_Y_Y := box{lblRhs: text{ascii: " "}, kind: boxBordr, resizeInc: resizeIncBorder, resizeRem: resizeRemColumn}

	l_5_0 := box{lblMid: text{ascii: "SERVICE"}, lblRhs: text{ascii: "   "}, kind: boxLabel, resizeInc: resizeIncLblService}
	l_5_1 := box{lblMid: text{ascii: "CPU"}, lblLhs: text{ascii: " "}, lblRhs: text{ascii: " "}, kind: boxLabel}
	l_5_2 := box{lblMid: text{ascii: "RAM"}, lblLhs: text{ascii: " "}, kind: boxLabel}
	l_5_3 := box{lblMid: text{ascii: "BKP"}, lblLhs: text{ascii: " "}, kind: boxLabel}
	l_5_4 := box{lblMid: text{ascii: "AOK"}, lblLhs: text{ascii: " "}, kind: boxLabel}

	d_X_0 := box{lblRhs: text{ascii: " "}, valLen: 9, valAln: boxLhs, valOpt: true, metricID: metric.MetricServiceName, resizeInc: resizeIncValService}
	d_X_1 := box{valSfx: "%", lblRhs: text{ascii: " "}, valLen: 3, valOpt: true, metricID: metric.MetricServiceUsedProcessor}
	d_X_2 := box{valSfx: "%", lblRhs: text{ascii: " "}, valLen: 3, valOpt: true, metricID: metric.MetricServiceUsedMemory}
	d_X_3 := box{lblLhs: text{ascii: " "}, valLen: 1, lblRhs: text{ascii: "  "}, valOpt: true, valKind: valBool, metricID: metric.MetricServiceBackupStatus}
	d_X_4 := box{lblLhs: text{ascii: " "}, valLen: 1, lblRhs: text{ascii: " "}, valOpt: true, valKind: valBool, metricID: metric.MetricService}

	s_X_Y := box{lblRhs: text{
		ascii:   "                                                         ",
		unicode: "╰───────────────────────────────────────────────────────╯",
	}, kind: boxBordr, resizeCnt: 3, resizeInc: resizeIncBorder, resizeRem: resizeRemSpacer}

	v_X_X := box{lblLhs: text{ascii: ""}, kind: boxDivdr, resizeRem: resizeRemDivider}

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

// noinspection GoSnakeCaseUsage
func relaxedDisplayLayout(useUnicode bool) [][]box {
	resizeIncHistVal := func(b *box, inc, hostCount int) { b.valLen += inc }
	resizeIncHistLbl := func(b *box, inc, hostCount int) {
		b.lblMid = b.lblMid.resize(inc, func(value string, length int) string { return pad(value, boxMid, length) })
	}
	resizeIncBorder := func(b *box, inc, hostCount int) {
		b.lblRhs = b.lblRhs.resize(inc, func(value string, length int) string { return extend(value, 1, length) })
	}
	resizeRemSpacer := func(b *box, rem, hostCount int) {
		if hostCount == 1 {
			b.lblRhs = b.lblRhs.resize(rem, func(value string, length int) string { return extend(value, 1, length) })
		} else {
			switch rem {
			case 1:
			case 2, 3, 4, 5, 6, 7:
				b.lblRhs = b.lblRhs.resize(rem/2, func(value string, length int) string { return extend(value, 1, length) })
			default:
				slog.Error("layout resize failed, invalid remainder", "hosts", hostCount, "remainder", rem)
			}
		}
	}
	resizeRemBorder := func(b *box, rem, hostCount int) {
		if hostCount == 1 {
			switch rem {
			case 1:
			case 2, 3:
				b.lblMid = b.lblMid.resize(1, func(value string, length int) string { return extend(value, 0, length) })
			default:
				slog.Error("layout resize failed, invalid remainder", "hosts", hostCount, "remainder", rem)
			}
		} else {
			switch rem {
			case 1, 2, 3:
			case 4, 5, 6, 7:
				b.lblMid = b.lblMid.resize(1, func(value string, length int) string { return extend(value, 0, length) })
			default:
				slog.Error("layout resize failed, invalid remainder", "hosts", hostCount, "remainder", rem)
			}
		}
	}
	resizeRemColumn := func(b *box, rem, hostCount int) {
		if hostCount == 1 {
			switch rem {
			case 1, 3:
				b.lblRhs = b.lblRhs.resize(1, func(value string, length int) string { return extend(value, 0, length) })
			case 2:
			default:
				slog.Error("layout resize failed, invalid remainder", "hosts", hostCount, "remainder", rem)
			}
		} else {
			switch rem {
			case 1, 4, 5:
			case 2, 3, 6, 7:
				b.lblRhs = b.lblRhs.resize(1, func(value string, length int) string { return extend(value, 0, length) })
			default:
				slog.Error("layout resize failed, invalid remainder", "hosts", hostCount, "remainder", rem)
			}
		}
	}
	resizeRemDivider := func(b *box, rem, hostCount int) {
		if hostCount > 1 {
			switch rem {
			case 1, 3, 5, 7:
				b.lblLhs = b.lblLhs.resize(1, func(value string, length int) string { return " " })
			case 2, 4, 6:
			default:
				slog.Error("layout resize failed, invalid remainder", "hosts", hostCount, "remainder", rem)
			}
		}
	}

	t_0_0 := box{lblLhs: text{
		ascii:   "+= ",
		unicode: "╭─┐",
	}, lblMid: text{
		ascii:   "           ",
		unicode: "           ",
	}, lblRhs: text{
		ascii:   " ================================================================",
		unicode: "┌────────────────────────────────────────────────────────────────",
	}, resizeCnt: 4, kind: boxTitle, resizeInc: resizeIncBorder, resizeRem: resizeRemSpacer}
	t_0_1 := box{lblLhs: text{
		ascii:   "= ",
		unicode: "─┐",
	}, lblMid: text{
		ascii:   "    ",
		unicode: "    ",
	}, lblRhs: text{
		ascii:   " =+",
		unicode: "┌─╮",
	}, kind: boxCtrls}
	b_X_Y := box{lblLhs: text{ascii: "|", unicode: "│"}, lblMid: text{ascii: " ", unicode: " "}, lblRhs: text{ascii: "", unicode: ""}, kind: boxBordr, resizeRem: resizeRemBorder}
	b_X_Z := box{lblRhs: text{ascii: "|", unicode: "│"}, lblMid: text{ascii: " ", unicode: " "}, lblLhs: text{ascii: "", unicode: ""}, kind: boxBordr, resizeRem: resizeRemBorder}

	d_1_0 := box{lblMid: text{ascii: "Used CPU "}, valLen: 8, valSfx: "%", valKind: valHist, metricID: metric.MetricHostUsedProcessor, resizeInc: resizeIncHistVal}
	d_1_1 := box{lblMid: text{ascii: "Fail LOG "}, valLen: 8, valSfx: "%", valKind: valHist, lblLhs: text{ascii: "    "}, metricID: metric.MetricHostFailedLogs, resizeInc: resizeIncHistVal}
	d_1_2 := box{lblMid: text{ascii: "Warn TEM "}, valLen: 8, valSfx: "%", valKind: valHist, metricID: metric.MetricHostWarnTemperatureOfMax, resizeInc: resizeIncHistVal}
	d_1_3 := box{lblMid: text{ascii: "Used SYS "}, valLen: 8, valSfx: "%", valKind: valHist, lblLhs: text{ascii: "    "}, metricID: metric.MetricHostUsedSystemSpace, resizeInc: resizeIncHistVal}

	d_2_0 := box{lblMid: text{ascii: "Used RAM "}, valLen: 8, valSfx: "%", valKind: valHist, metricID: metric.MetricHostUsedMemory, resizeInc: resizeIncHistVal}
	d_2_1 := box{lblMid: text{ascii: "Fail SHR "}, valLen: 8, valSfx: "%", valKind: valHist, lblLhs: text{ascii: "    "}, metricID: metric.MetricHostFailedShares, resizeInc: resizeIncHistVal}
	d_2_2 := box{lblMid: text{ascii: "Revs Fan "}, valLen: 8, valSfx: "%", valKind: valHist, metricID: metric.MetricHostSpinFanSpeedOfMax, resizeInc: resizeIncHistVal}
	d_2_3 := box{lblMid: text{ascii: "Used SHR "}, valLen: 8, valSfx: "%", valKind: valHist, lblLhs: text{ascii: "    "}, metricID: metric.MetricHostUsedShareSpace, resizeInc: resizeIncHistVal}

	d_3_0 := box{lblMid: text{ascii: "Aloc RAM "}, valLen: 8, valSfx: "%", valKind: valHist, metricID: metric.MetricHostAllocatedMemory, resizeInc: resizeIncHistVal}
	d_3_1 := box{lblMid: text{ascii: "Fail BCK "}, valLen: 8, valSfx: "%", valKind: valHist, lblLhs: text{ascii: "    "}, metricID: metric.MetricHostFailedBackups, resizeInc: resizeIncHistVal}
	d_3_2 := box{lblMid: text{ascii: "Life SSD "}, valLen: 8, valSfx: "%", valKind: valHist, metricID: metric.MetricHostLifeUsedDrives, resizeInc: resizeIncHistVal}
	d_3_3 := box{lblMid: text{ascii: "Used BKP "}, valLen: 8, valSfx: "%", valKind: valHist, lblLhs: text{ascii: "    "}, metricID: metric.MetricHostUsedBackupSpace, resizeInc: resizeIncHistVal}

	s_X_0 := box{lblRhs: text{
		ascii:   "+--------------------------------------------------------------------------------------+",
		unicode: "├──────────────────────────────────────────────────────────────────────────────────────┤",
	}, kind: boxBordr, resizeCnt: 4, resizeInc: resizeIncBorder, resizeRem: resizeRemSpacer}
	s_Y_Y := box{lblRhs: text{ascii: "    "}, kind: boxBordr, resizeRem: resizeRemColumn}

	l_5_0 := box{lblMid: text{ascii: "SERVICE"}, lblRhs: text{ascii: "        "}, kind: boxLabel}
	l_5_1 := box{lblMid: text{ascii: "VERSION"}, lblLhs: text{ascii: "  "}, lblRhs: text{ascii: "  "}, kind: boxLabel}
	l_5_2 := box{lblMid: text{ascii: "CPU"}, lblLhs: text{ascii: "       "}, lblRhs: text{ascii: "    "}, kind: boxLabel, resizeCnt: 2, resizeInc: resizeIncHistLbl}
	l_5_3 := box{lblMid: text{ascii: "MEM"}, lblLhs: text{ascii: "    "}, lblRhs: text{ascii: "    "}, kind: boxLabel, resizeCnt: 2, resizeInc: resizeIncHistLbl}
	l_5_4 := box{lblMid: text{ascii: "BKP"}, lblLhs: text{ascii: "   "}, kind: boxLabel}
	l_5_5 := box{lblMid: text{ascii: "HLT"}, lblLhs: text{ascii: "  "}, kind: boxLabel}
	l_5_6 := box{lblMid: text{ascii: "CFG"}, lblLhs: text{ascii: "  "}, kind: boxLabel}
	l_5_7 := box{lblMid: text{ascii: "RST"}, lblLhs: text{ascii: "  "}, kind: boxLabel}
	l_5_8 := box{lblMid: text{ascii: "UPTIME"}, lblLhs: text{ascii: "  "}, kind: boxLabel}

	d_X_0 := box{valLen: 14, lblRhs: text{ascii: " "}, valAln: boxLhs, valOpt: true, valKind: valText, metricID: metric.MetricServiceName}
	d_X_1 := box{valLen: 11, lblRhs: text{ascii: " "}, valOpt: true, valKind: valText, metricID: metric.MetricServiceVersion}
	d_X_2 := box{lblLhs: text{ascii: "  "}, valSfx: "%", valLen: 10, valOpt: true, valKind: valHist, metricID: metric.MetricServiceUsedProcessor, resizeCnt: 2, resizeInc: resizeIncHistVal}
	d_X_3 := box{lblLhs: text{ascii: ""}, valSfx: "%", valLen: 10, valOpt: true, valKind: valHist, metricID: metric.MetricServiceUsedMemory, resizeCnt: 2, resizeInc: resizeIncHistVal}
	d_X_4 := box{lblLhs: text{ascii: "    "}, lblRhs: text{ascii: " "}, valLen: 1, valOpt: true, valKind: valBool, metricID: metric.MetricServiceBackupStatus}
	d_X_5 := box{lblLhs: text{ascii: "   "}, lblRhs: text{ascii: " "}, valLen: 1, valOpt: true, valKind: valBool, metricID: metric.MetricServiceHealthStatus}
	d_X_6 := box{lblLhs: text{ascii: "   "}, lblRhs: text{ascii: " "}, valLen: 1, valOpt: true, valKind: valBool, metricID: metric.MetricServiceConfiguredStatus}
	d_X_7 := box{lblLhs: text{ascii: "   "}, lblRhs: text{ascii: " "}, valLen: 1, valOpt: true, metricID: metric.MetricServiceRestartCount}
	d_X_8 := box{lblLhs: text{ascii: "    "}, lblRhs: text{ascii: ""}, valLen: 4, valOpt: true, valKind: valTime, metricID: metric.MetricServiceUpTime}

	s_X_Y := box{lblRhs: text{
		ascii:   "                                                                                        ",
		unicode: "╰──────────────────────────────────────────────────────────────────────────────────────╯",
	}, kind: boxBordr, resizeCnt: 4, resizeInc: resizeIncBorder, resizeRem: resizeRemSpacer}

	v_X_X := box{lblLhs: text{ascii: ""}, kind: boxDivdr, resizeRem: resizeRemDivider}

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
		{b_X_Y, d_X_0, d_X_1, d_X_2, s_Y_Y, d_X_3, d_X_4, d_X_5, d_X_6, d_X_7, d_X_8, b_X_Z, v_X_X},
		{s_X_Y, v_X_X},
	})
}

type text struct {
	ascii   string
	unicode string
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

func rows(layout [][]box, hostCount int) int {
	if hostCount == 0 || len(layout) == 0 {
		return 0
	}
	return len(layout) * ((hostCount + 1) / 2)
}

func columns(layout [][]box, useUnicode bool, hostCount int) int {
	if hostCount == 0 || len(layout) == 0 {
		return 0
	}
	count := 0
	for _, b := range layout[0] {
		if b.kind != boxDivdr {
			count += b.length(useUnicode)
		}
		if hostCount > 1 {
			count += b.length(useUnicode)
		}
	}
	return count
}

func resizes(layout [][]box, hostCount int) int {
	if hostCount == 0 || len(layout) == 0 {
		return 0
	}
	count := 0
	for _, b := range layout[0] {
		if b.kind != boxDivdr {
			count += b.resizes()
		}
		if hostCount > 1 {
			count += b.resizes()
		}
	}
	return count
}

func compile(useUnicode bool, layout [][]box) [][]box {
	result := make([][]box, 0, len(layout))
	for row := range layout {
		rowLabels := ""
		for col := range layout[row] {
			layout[row][col].compile(false, true)
			rowLabels += layout[row][col].trim(useUnicode)
		}
		if rowLabels != "" {
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
	b.compiled.lblLhsLen = runewidth.StringWidth(b.lblLhs.pick(useUnicode))
	b.compiled.lblMidLen = runewidth.StringWidth(b.lblMid.pick(useUnicode))
	b.compiled.lblRhsLen = runewidth.StringWidth(b.lblRhs.pick(useUnicode))
	b.compiled.valSfxLen = runewidth.StringWidth(b.valSfx)
	b.compiled.valOffset = b.compiled.lblLhsLen + b.compiled.lblMidLen
	b.compiled.length = b.compiled.valOffset + b.valLen + b.compiled.lblRhsLen + b.compiled.valSfxLen
}

func (b *box) resizes() int {
	if b.resizeCnt == 0 && b.resizeInc != nil {
		return 1
	}
	return b.resizeCnt
}

func (b *box) resize(useUnicode bool, increment, remainder, hostCount int) {
	resized := false
	if b.resizeInc != nil && increment > 0 {
		b.resizeInc(b, increment*b.resizes(), hostCount)
		resized = true
	}
	if b.resizeRem != nil && remainder > 0 {
		b.resizeRem(b, remainder, hostCount)
		resized = true
	}
	if resized {
		b.compile(useUnicode, true)
	}
}

func (b *box) set(
	useUnicode bool,
	lblLhs text, lblLhsAln boxAlign, lblLhsLen int,
	lblMid text, lblMidAln boxAlign, lblMidLen int,
	lblRhs text, lblRhsAln boxAlign, lblRhsLen int,
) {
	lhs := pad(lblLhs.pick(useUnicode), lblLhsAln, lblLhsLen)
	mid := pad(lblMid.pick(useUnicode), lblMidAln, lblMidLen)
	rhs := pad(lblRhs.pick(useUnicode), lblRhsAln, lblRhsLen)
	b.lblLhs = text{lhs, lhs}
	b.lblMid = text{mid, mid}
	b.lblRhs = text{rhs, rhs}
	b.compile(useUnicode, true)
}

func (b *box) length(useUnicode bool) int {
	b.compile(useUnicode, false)
	return b.compiled.length
}

func (b *box) trim(useUnicode bool) string {
	result := b.lblLhs.pick(useUnicode) + b.lblMid.pick(useUnicode) + b.lblRhs.pick(useUnicode)
	return strings.TrimSpace(result)
}

func (b *box) draw(display *Display, force bool) {
	if display.terminal == nil {
		return
	}
	b.compile(display.useUnicode, false)
	row, col := b.position.rows, b.position.cols
	draw := func(label string, c colour) {
		if label != "" && force == b.valOpt {
			display.terminal.draw(col, row, label, c)
		}
		col += runewidth.StringWidth(label)
	}
	advance := func(label string) {
		col += runewidth.StringWidth(label)
	}
	borderColour := colourChat
	if b.kind == boxBordr || b.kind == boxTitle || b.kind == boxCtrls {
		borderColour = colourGrowl
	}
	draw(b.lblLhs.pick(display.useUnicode), borderColour)
	if b.kind == boxCtrls && force == b.valOpt {
		mid := b.lblMid.pick(display.useUnicode)
		parts := tokens(mid)
		if len(parts) > 1 {
			arrow := parts[0]
			rest := strings.Join(parts[1:], "")
			display.terminal.draw(col, row, arrow, colourGrowl)
			arrowLen := runewidth.StringWidth(arrow)
			beforeSlash, slashAndAfter, hasSlash := strings.Cut(rest, "/")
			if hasSlash && beforeSlash != "" {
				display.terminal.draw(col+arrowLen, row, beforeSlash, colourShout)
				display.terminal.draw(col+arrowLen+runewidth.StringWidth(beforeSlash), row, "/"+slashAndAfter, colourChat)
			} else {
				display.terminal.draw(col+arrowLen, row, rest, colourShout)
			}
		}
		col += runewidth.StringWidth(mid)
	} else if b.kind == boxTitle {
		draw(b.lblMid.pick(display.useUnicode), colourMurmur)
	} else if b.kind == boxBordr {
		draw(b.lblMid.pick(display.useUnicode), colourGrowl)
	} else {
		draw(b.lblMid.pick(display.useUnicode), colourChat)
	}
	advance(strings.Repeat(" ", b.valLen+b.compiled.valSfxLen))
	draw(b.lblRhs.pick(display.useUnicode), borderColour)
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
	if !ok || record == nil || record.Value.Pulse == nil || record.Value.Pulse.IsZero() {
		display.terminal.draw(
			b.position.cols+b.compiled.valOffset,
			b.position.rows,
			strings.Repeat(" ", b.valLen+b.compiled.valSfxLen),
			colourChat,
		)
		return
	}
	if b.isLast {
		nextRecord, nextOk := display.cache.LoadByID(b.recordGUID.ID, b.recordGUID.Host, display.maxServices)
		if nextOk && nextRecord != nil && nextRecord.Value.Pulse != nil && !nextRecord.Value.Pulse.IsZero() {
			b.draw(display, true)
			display.terminal.draw(
				b.position.cols+b.compiled.valOffset+b.compiled.valSfxLen,
				b.position.rows,
				pad("~", b.valAln, b.valLen)+strings.Repeat(" ", b.compiled.valSfxLen),
				colourChat,
			)
			return
		}
	}
	location := dimensions{b.position.rows, b.position.cols + b.compiled.valOffset}
	b.draw(display, true)
	var trendOK *bool
	if record.Value.Trend != nil {
		trendOK = &record.Value.Trend.OK
	}
	c := highlight(&record.Value.Pulse.OK, trendOK)
	valueString := ""
	switch b.valKind {
	case valBool:
		symbol := textCross.pick(display.useUnicode)
		if record.Value.Pulse.OK {
			symbol = textTick.pick(display.useUnicode)
		}
		valueString = pad(symbol, b.valAln, b.valLen)
	case valTime:
		secondsRaw := record.Value.Pulse.Value()
		secondsValue, err := strconv.ParseFloat(secondsRaw, 64)
		if err != nil {
			valueString = pad(secondsRaw, b.valAln, b.valLen) + b.valSfx
			break
		}
		valueString = pad(duration(secondsValue), b.valAln, b.valLen) + b.valSfx
	case valHist:
		value := record.Value.Pulse.Value()
		fallback := pad(value, b.valAln, b.valLen) + b.valSfx
		if b.valLen < 6 {
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
		barWidth := b.valLen - 4
		barChar := textBar.pick(display.useUnicode)
		barSuffix := " "
		unfilledChar := barChar
		if !display.useUnicode {
			barWidth = b.valLen - 6
			barSuffix = "| "
			unfilledChar = " "
		}
		filled := int(math.Round(percent * float64(barWidth) / 100))
		if percent > 0 && filled == 0 {
			filled = 1
		}
		if filled < 0 {
			filled = 0
		}
		if filled > barWidth {
			filled = barWidth
		}
		percentInt := int(math.Round(percent))
		if percentInt < 0 {
			percentInt = 0
		}
		if percentInt > 100 {
			percentInt = 100
		}
		col := location.cols
		if !display.useUnicode {
			display.terminal.draw(col, location.rows, "|", c)
			col++
		}
		if filled > 0 {
			display.terminal.draw(col, location.rows, strings.Repeat(barChar, filled), c)
		}
		if filled < barWidth {
			display.terminal.draw(col+filled, location.rows, strings.Repeat(unfilledChar, barWidth-filled), colourWhisper)
		}
		display.terminal.draw(col+barWidth, location.rows, barSuffix+pad(strconv.Itoa(percentInt), boxRhs, 3)+b.valSfx, c)
		return
	default:
		valueString = pad(record.Value.Pulse.Value(), b.valAln, b.valLen) + b.valSfx
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
	display.terminal.draw(
		location.cols,
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
	return &clone
}

func highlight(pulse, trend *bool) colour {
	if pulse == nil {
		return colourChat
	}
	if !*pulse {
		return colourAlert
	}
	if trend != nil && *trend {
		return colourCheer
	}
	return colourWarn
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
	if align == boxRhs {
		return spaces + base
	}
	if align == boxMid {
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

func divider(base string, length int) string {
	if length <= 0 || base == "" {
		return ""
	}
	centerCount := 1
	if length%2 == 0 {
		centerCount = 2
	}
	spaceCount := (length - 1) / 2
	tokens := tokens(base)
	if len(tokens) == 0 {
		return ""
	}
	center := strings.Repeat(tokens[0], centerCount)
	spaces := strings.Repeat(" ", spaceCount)
	return spaces + center + spaces
}

func tokens(value string) []string {
	tokens := make([]string, 0, len(value))
	for _, r := range value {
		tokens = append(tokens, string(r))
	}
	return tokens
}
