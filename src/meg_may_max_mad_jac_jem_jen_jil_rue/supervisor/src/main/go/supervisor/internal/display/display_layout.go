package display

import (
	"math"
	"strconv"
	"strings"
	"supervisor/internal/metric"
	"unicode/utf8"
)

type Symbols struct {
	bar   string
	tick  string
	cross string
}

var (
	SymbolsASCII = Symbols{
		bar:   "|",
		tick:  "+",
		cross: "-",
	}
	SymbolsUnicode = Symbols{
		bar:   "█",
		tick:  "✔",
		cross: "✖",
	}
)

type boxKind int

const (
	boxDatum boxKind = iota
	boxTitle
	boxLabel
	boxSpacr
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
	lblLhs     string
	lblMid     string
	lblRhs     string
	valLen     int
	valOpt     bool
	valAln     boxAlign
	valSfx     string
	valKind    boxValKind
	position   *dimensions
	metricID   metric.ID
	recordGUID *metric.RecordGUID
	compiled   *compiled
	resizeCnt  int
	resizeInc  func(b *box, i int)
	resizeRem  func(b *box, r int)
}

type compiled struct {
	length    int
	lblLhsLen int
	lblMidLen int
	lblRhsLen int
	valSfxLen int
	valOffset int
}

/*
── host-numbe~ ─────────────────────────────────────────── ||
Used CPU 100%  Fail SVC 100%  Warn TEM 100%  Used SYS 100% ||
Used RAM  39%  Fail SHR 100%  Revs Fan 100%  Used SHR  10% ||
Aloc RAM   1%  Fail BCK   4%  Life SSD   3%  Used BKP  10% ||
---------------------------------------------------------- ||
SERVICE     CPU  RAM BKP AOK  SERVICE     CPU  RAM BKP AOK ||
homeassis~ 100% 100%  +   -   service2   100% 100%  -   -  ||
service3    11%  12%  -   -   service4    10% 100%  -   -  ||
service5    10% 100%  -   +   service6    10% 100%  +   -  ||
service7    20%  21%  -   +   service8    10% 100%  -   -  ||
service90~   0%   1%  -   -   ~             ~    ~  ~   ~  ||
*/
//noinspection GoSnakeCaseUsage
func compactDisplayLayout() [][]box {
	resizeService := func(b *box, i int) { b.valLen += i }
	resizeDivider := func(b *box, r int) { b.lblLhs = divider(b.lblLhs, r+len(b.lblLhs)) }
	resizeLblRhs1 := func(b *box, i int) { b.lblRhs += repeat(b.lblRhs, 0, 1, i) }
	resizeLblLhs1 := func(b *box, i int) { b.lblLhs += repeat(b.lblLhs, 0, 1, i) }

	t_0_0 := box{lblLhs: "── ", lblMid: "           ", lblRhs: " ───────────────────────────────────────────", resizeCnt: 3, kind: boxTitle, resizeInc: resizeLblRhs1}

	d_1_0 := box{lblMid: "Used CPU ", valLen: 3, valSfx: "%", metricID: metric.MetricHostUsedProcessor}
	d_1_1 := box{lblMid: "Fail LOG ", valLen: 3, valSfx: "%", lblLhs: "  ", metricID: metric.MetricHostFailedLogs, resizeInc: resizeLblLhs1}
	d_1_2 := box{lblMid: "Warn TEM ", valLen: 3, valSfx: "%", lblLhs: "  ", metricID: metric.MetricHostWarnTemperatureOfMax, resizeInc: resizeLblLhs1}
	d_1_3 := box{lblMid: "Used SYS ", valLen: 3, valSfx: "%", lblLhs: "  ", metricID: metric.MetricHostUsedSystemSpace, resizeInc: resizeLblLhs1}

	d_2_0 := box{lblMid: "Used RAM ", valLen: 3, valSfx: "%", metricID: metric.MetricHostUsedMemory}
	d_2_1 := box{lblMid: "Fail SHR ", valLen: 3, valSfx: "%", lblLhs: "  ", metricID: metric.MetricHostFailedShares, resizeInc: resizeLblLhs1}
	d_2_2 := box{lblMid: "Revs Fan ", valLen: 3, valSfx: "%", lblLhs: "  ", metricID: metric.MetricHostSpinFanSpeedOfMax, resizeInc: resizeLblLhs1}
	d_2_3 := box{lblMid: "Used SHR ", valLen: 3, valSfx: "%", lblLhs: "  ", metricID: metric.MetricHostUsedShareSpace, resizeInc: resizeLblLhs1}

	d_3_0 := box{lblMid: "Aloc RAM ", valLen: 3, valSfx: "%", metricID: metric.MetricHostAllocatedMemory}
	d_3_1 := box{lblMid: "Fail BCK ", valLen: 3, valSfx: "%", lblLhs: "  ", metricID: metric.MetricHostFailedBackups, resizeInc: resizeLblLhs1}
	d_3_2 := box{lblMid: "Life SSD ", valLen: 3, valSfx: "%", lblLhs: "  ", metricID: metric.MetricHostLifeUsedDrives, resizeInc: resizeLblLhs1}
	d_3_3 := box{lblMid: "Used BKP ", valLen: 3, valSfx: "%", lblLhs: "  ", metricID: metric.MetricHostUsedBackupSpace, resizeInc: resizeLblLhs1}

	s_4_0 := box{lblLhs: "----------------------------------------------------------", resizeCnt: 3, kind: boxSpacr, resizeInc: resizeLblLhs1}

	l_5_0 := box{lblMid: "SERVICE", lblRhs: "    ", kind: boxLabel, resizeInc: resizeLblRhs1}
	l_5_1 := box{lblMid: "CPU", lblLhs: " ", lblRhs: " ", kind: boxLabel}
	l_5_2 := box{lblMid: "RAM", lblLhs: " ", lblRhs: " ", kind: boxLabel}
	l_5_3 := box{lblMid: "BKP", lblRhs: " ", kind: boxLabel}
	l_5_4 := box{lblMid: "AOK", kind: boxLabel}

	d_X_0 := box{lblRhs: " ", valLen: 10, valAln: boxLhs, valOpt: true, metricID: metric.MetricServiceName, resizeInc: resizeService}
	d_X_1 := box{valSfx: "%", lblRhs: " ", valLen: 3, valOpt: true, metricID: metric.MetricServiceUsedProcessor}
	d_X_2 := box{valSfx: "%", lblRhs: " ", valLen: 3, valOpt: true, metricID: metric.MetricServiceUsedMemory}
	d_X_3 := box{lblLhs: " ", valLen: 1, lblRhs: "  ", valOpt: true, valKind: valBool, metricID: metric.MetricServiceBackupStatus}
	d_X_4 := box{lblLhs: " ", valLen: 1, lblRhs: " ", valOpt: true, valKind: valBool, metricID: metric.MetricService}

	s_X_5 := box{lblLhs: "  ", kind: boxSpacr, resizeInc: resizeLblLhs1}

	v_X_X := box{lblLhs: " ", kind: boxDivdr, resizeInc: resizeLblLhs1}
	v_Y_Y := box{lblLhs: "||", kind: boxDivdr, resizeRem: resizeDivider}

	return compile([][]box{
		{t_0_0, v_X_X, v_Y_Y, v_X_X},
		{d_1_0, d_1_1, d_1_2, d_1_3, v_X_X, v_Y_Y, v_X_X},
		{d_2_0, d_2_1, d_2_2, d_2_3, v_X_X, v_Y_Y, v_X_X},
		{d_3_0, d_3_1, d_3_2, d_3_3, v_X_X, v_Y_Y, v_X_X},
		{s_4_0, v_X_X, v_Y_Y, v_X_X},
		{l_5_0, l_5_1, l_5_2, l_5_3, l_5_4, s_X_5, l_5_0, l_5_1, l_5_2, l_5_3, l_5_4, v_X_X, v_Y_Y, v_X_X},
		{d_X_0, d_X_1, d_X_2, d_X_3, d_X_4, s_X_5, d_X_0, d_X_1, d_X_2, d_X_3, d_X_4, v_X_X, v_Y_Y, v_X_X},
		{d_X_0, d_X_1, d_X_2, d_X_3, d_X_4, s_X_5, d_X_0, d_X_1, d_X_2, d_X_3, d_X_4, v_X_X, v_Y_Y, v_X_X},
		{d_X_0, d_X_1, d_X_2, d_X_3, d_X_4, s_X_5, d_X_0, d_X_1, d_X_2, d_X_3, d_X_4, v_X_X, v_Y_Y, v_X_X},
		{d_X_0, d_X_1, d_X_2, d_X_3, d_X_4, s_X_5, d_X_0, d_X_1, d_X_2, d_X_3, d_X_4, v_X_X, v_Y_Y, v_X_X},
		{d_X_0, d_X_1, d_X_2, d_X_3, d_X_4, s_X_5, d_X_0, d_X_1, d_X_2, d_X_3, d_X_4, v_X_X, v_Y_Y, v_X_X},
	})
}

/*
── host-numbe~ ─────────────────────────────────────────────────────────────────────   ||
Used CPU ■■■■ 100%    Fail SVC ■■■■ 100%    Warn TEM ■■■■ 100%    Used SYS ■■■■ 100%   ||
Used RAM ■■■■  39%    Fail SHR ■■■■ 100%    Revs Fan ■■■■ 100%    Used SHR ■■■■  10%   ||
Aloc RAM ■■■■   1%    Fail BCK ■■■■   4%    Life SSD ■■■■   3%    Used BKP ■■■■  10%   ||
------------------------------------------------------------------------------------   ||
SERVICE          VERNUM          CPU            MEM       BKP  HLT  CFG  RST  UPTIME   ||
------------------------------------------------------------------------------------   ||
homeassistant 10.100.10001   ■■■■■■ 100%    ■■■■■■ 100%    -    -    -    0     156d   ||
service2      10.100.10001   ■■■■■■  65%    ■■■■■■  11%    +    -    -    0      10y   ||
service3      10.100.10001   ■■■■■■  11%    ■■■■■■  51%    +    +    -    0       1y   ||
service4      10.100.10001   ■■■■■■  65%    ■■■■■■  65%    +    -    -    0       2y   ||
service5      10.100.10001   ■■■■■■  51%    ■■■■■■  11%    -    +    -    0      10d   ||
service6      10.100.10001   ■■■■■■  51%    ■■■■■■  11%    +    -    -    0       1h   ||
service7      10.100.10001   ■■■■■■   1%    ■■■■■■  51%    +    -    -    0      34m   ||
service8      10.100.10001   ■■■■■■  65%    ■■■■■■  11%    +    +    +    0      10y   ||
service90000~ 10.100.10001   ■■■■■■  11%    ■■■■■■  65%    +    -    -    ~     100d   ||
~              ~                       ~              ~    ~    ~    ~    ~        ~   ||
*/
//noinspection GoSnakeCaseUsage
func relaxedDisplayLayout() [][]box {
	resizeHistVal := func(b *box, i int) { b.valLen += i }
	resizeHistLbl := func(b *box, r int) { b.lblMid = pad(b.lblMid, boxMid, r+len(b.lblMid)) }
	resizeDivider := func(b *box, r int) { b.lblLhs = divider(b.lblLhs, r+len(b.lblLhs)) }
	resizeLblRhs1 := func(b *box, i int) { b.lblRhs += repeat(b.lblRhs, 0, 1, i) }
	resizeLblLhs1 := func(b *box, i int) { b.lblLhs += repeat(b.lblLhs, 0, 1, i) }

	t_0_0 := box{lblLhs: "── ", lblMid: "           ", lblRhs: " ─────────────────────────────────────────────────────────────────────", resizeCnt: 4, kind: boxTitle, resizeInc: resizeLblRhs1}

	d_1_0 := box{lblMid: "Used CPU ", valLen: 8, valSfx: "%", valKind: valHist, metricID: metric.MetricHostUsedProcessor, resizeInc: resizeHistVal}
	d_1_1 := box{lblMid: "Fail LOG ", valLen: 8, valSfx: "%", valKind: valHist, lblLhs: "    ", metricID: metric.MetricHostFailedLogs, resizeInc: resizeHistVal}
	d_1_2 := box{lblMid: "Warn TEM ", valLen: 8, valSfx: "%", valKind: valHist, lblLhs: "    ", metricID: metric.MetricHostWarnTemperatureOfMax, resizeInc: resizeHistVal}
	d_1_3 := box{lblMid: "Used SYS ", valLen: 8, valSfx: "%", valKind: valHist, lblLhs: "    ", metricID: metric.MetricHostUsedSystemSpace, resizeInc: resizeHistVal}

	d_2_0 := box{lblMid: "Used RAM ", valLen: 8, valSfx: "%", valKind: valHist, metricID: metric.MetricHostUsedMemory, resizeInc: resizeHistVal}
	d_2_1 := box{lblMid: "Fail SHR ", valLen: 8, valSfx: "%", valKind: valHist, lblLhs: "    ", metricID: metric.MetricHostFailedShares, resizeInc: resizeHistVal}
	d_2_2 := box{lblMid: "Revs Fan ", valLen: 8, valSfx: "%", valKind: valHist, lblLhs: "    ", metricID: metric.MetricHostSpinFanSpeedOfMax, resizeInc: resizeHistVal}
	d_2_3 := box{lblMid: "Used SHR ", valLen: 8, valSfx: "%", valKind: valHist, lblLhs: "    ", metricID: metric.MetricHostUsedShareSpace, resizeInc: resizeHistVal}

	d_3_0 := box{lblMid: "Aloc RAM ", valLen: 8, valSfx: "%", valKind: valHist, metricID: metric.MetricHostAllocatedMemory, resizeInc: resizeHistVal}
	d_3_1 := box{lblMid: "Fail BCK ", valLen: 8, valSfx: "%", valKind: valHist, lblLhs: "    ", metricID: metric.MetricHostFailedBackups, resizeInc: resizeHistVal}
	d_3_2 := box{lblMid: "Life SSD ", valLen: 8, valSfx: "%", valKind: valHist, lblLhs: "    ", metricID: metric.MetricHostLifeUsedDrives, resizeInc: resizeHistVal}
	d_3_3 := box{lblMid: "Used BKP ", valLen: 8, valSfx: "%", valKind: valHist, lblLhs: "    ", metricID: metric.MetricHostUsedBackupSpace, resizeInc: resizeHistVal}

	s_X_0 := box{lblLhs: "------------------------------------------------------------------------------------", kind: boxSpacr, resizeCnt: 4, resizeInc: resizeLblLhs1}

	l_5_0 := box{lblMid: "SERVICE", lblRhs: "       ", kind: boxLabel}
	l_5_1 := box{lblMid: "VERNUM", lblLhs: "   ", lblRhs: "   ", kind: boxLabel}
	l_5_2 := box{lblMid: "CPU", lblLhs: "       ", lblRhs: "    ", kind: boxLabel, resizeCnt: 2, resizeInc: resizeHistLbl}
	l_5_3 := box{lblMid: "MEM", lblLhs: "        ", lblRhs: "    ", kind: boxLabel, resizeCnt: 2, resizeInc: resizeHistLbl}
	l_5_4 := box{lblMid: "BKP", lblLhs: "   ", kind: boxLabel}
	l_5_5 := box{lblMid: "HLT", lblLhs: "  ", kind: boxLabel}
	l_5_6 := box{lblMid: "CFG", lblLhs: "  ", kind: boxLabel}
	l_5_7 := box{lblMid: "RST", lblLhs: "  ", kind: boxLabel}
	l_5_8 := box{lblMid: "UPTIME", lblLhs: "  ", kind: boxLabel}

	d_X_0 := box{valLen: 13, lblRhs: " ", valAln: boxLhs, valOpt: true, valKind: valText, metricID: metric.MetricServiceName}
	d_X_1 := box{valLen: 12, valOpt: true, valKind: valText, metricID: metric.MetricServiceVersion}
	d_X_2 := box{lblLhs: "   ", valSfx: "%", valLen: 10, valOpt: true, valKind: valHist, metricID: metric.MetricServiceUsedProcessor, resizeCnt: 2, resizeInc: resizeHistVal}
	d_X_3 := box{lblLhs: "   ", valSfx: "%", valLen: 10, valOpt: true, valKind: valHist, metricID: metric.MetricServiceUsedMemory, resizeCnt: 2, resizeInc: resizeHistVal}
	d_X_4 := box{lblLhs: "   ", lblRhs: " ", valLen: 1, valOpt: true, valKind: valBool, metricID: metric.MetricServiceBackupStatus}
	d_X_5 := box{lblLhs: "   ", lblRhs: " ", valLen: 1, valOpt: true, valKind: valBool, metricID: metric.MetricServiceHealthStatus}
	d_X_6 := box{lblLhs: "   ", lblRhs: " ", valLen: 1, valOpt: true, valKind: valBool, metricID: metric.MetricServiceConfiguredStatus}
	d_X_7 := box{lblLhs: "   ", lblRhs: " ", valLen: 1, valOpt: true, metricID: metric.MetricServiceRestartCount}
	d_X_8 := box{lblLhs: "   ", valLen: 4, valOpt: true, valKind: valTime, metricID: metric.MetricServiceUpTime}

	s_X_7 := box{lblLhs: " ", kind: boxSpacr}

	v_X_X := box{lblLhs: "   ", kind: boxDivdr}
	v_Y_Y := box{lblLhs: "||", kind: boxDivdr, resizeRem: resizeDivider}

	return compile([][]box{
		{t_0_0, v_X_X, v_Y_Y, v_X_X},
		{d_1_0, d_1_1, d_1_2, d_1_3, v_X_X, v_Y_Y, v_X_X},
		{d_2_0, d_2_1, d_2_2, d_2_3, v_X_X, v_Y_Y, v_X_X},
		{d_3_0, d_3_1, d_3_2, d_3_3, v_X_X, v_Y_Y, v_X_X},
		{s_X_0, v_X_X, v_Y_Y, v_X_X},
		{l_5_0, l_5_1, l_5_2, l_5_3, l_5_4, l_5_5, l_5_6, l_5_7, l_5_8, v_X_X, v_Y_Y, v_X_X},
		{s_X_0, v_X_X, v_Y_Y, v_X_X},
		{d_X_0, d_X_1, d_X_2, s_X_7, d_X_3, s_X_7, d_X_4, d_X_5, d_X_6, d_X_7, s_X_7, d_X_8, v_X_X, v_Y_Y, v_X_X},
		{d_X_0, d_X_1, d_X_2, s_X_7, d_X_3, s_X_7, d_X_4, d_X_5, d_X_6, d_X_7, s_X_7, d_X_8, v_X_X, v_Y_Y, v_X_X},
		{d_X_0, d_X_1, d_X_2, s_X_7, d_X_3, s_X_7, d_X_4, d_X_5, d_X_6, d_X_7, s_X_7, d_X_8, v_X_X, v_Y_Y, v_X_X},
		{d_X_0, d_X_1, d_X_2, s_X_7, d_X_3, s_X_7, d_X_4, d_X_5, d_X_6, d_X_7, s_X_7, d_X_8, v_X_X, v_Y_Y, v_X_X},
		{d_X_0, d_X_1, d_X_2, s_X_7, d_X_3, s_X_7, d_X_4, d_X_5, d_X_6, d_X_7, s_X_7, d_X_8, v_X_X, v_Y_Y, v_X_X},
		{d_X_0, d_X_1, d_X_2, s_X_7, d_X_3, s_X_7, d_X_4, d_X_5, d_X_6, d_X_7, s_X_7, d_X_8, v_X_X, v_Y_Y, v_X_X},
		{d_X_0, d_X_1, d_X_2, s_X_7, d_X_3, s_X_7, d_X_4, d_X_5, d_X_6, d_X_7, s_X_7, d_X_8, v_X_X, v_Y_Y, v_X_X},
		{d_X_0, d_X_1, d_X_2, s_X_7, d_X_3, s_X_7, d_X_4, d_X_5, d_X_6, d_X_7, s_X_7, d_X_8, v_X_X, v_Y_Y, v_X_X},
		{d_X_0, d_X_1, d_X_2, s_X_7, d_X_3, s_X_7, d_X_4, d_X_5, d_X_6, d_X_7, s_X_7, d_X_8, v_X_X, v_Y_Y, v_X_X},
		{d_X_0, d_X_1, d_X_2, s_X_7, d_X_3, s_X_7, d_X_4, d_X_5, d_X_6, d_X_7, s_X_7, d_X_8, v_X_X, v_Y_Y, v_X_X},
	})
}

func rows(layout [][]box, hostCount int) int {
	if hostCount == 0 || len(layout) == 0 {
		return 0
	}
	count := len(layout)
	if hostCount == 1 {
		count--
	}
	return count * ((hostCount + 1) / 2)
}

func columns(layout [][]box, hostCount int) int {
	if hostCount == 0 || len(layout) == 0 {
		return 0
	}
	count := 0
	for _, b := range layout[0] {
		if b.kind != boxDivdr {
			count += b.length()
		}
		if hostCount > 1 {
			count += b.length()
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

func compile(layout [][]box) [][]box {
	for row := range layout {
		for col := range layout[row] {
			layout[row][col].compile(true)
		}
	}
	return layout
}

func (b *box) compile(force bool) {
	if b.compiled != nil && !force {
		return
	}
	if b.compiled == nil {
		b.compiled = &compiled{}
	}
	b.compiled.lblLhsLen = utf8.RuneCountInString(b.lblLhs)
	b.compiled.lblMidLen = utf8.RuneCountInString(b.lblMid)
	b.compiled.lblRhsLen = utf8.RuneCountInString(b.lblRhs)
	b.compiled.valSfxLen = utf8.RuneCountInString(b.valSfx)
	b.compiled.valOffset = b.compiled.lblLhsLen + b.compiled.lblMidLen
	b.compiled.length = b.compiled.valOffset + b.valLen + b.compiled.lblRhsLen + b.compiled.valSfxLen
}

func (b *box) resizes() int {
	if b.resizeCnt == 0 && b.resizeInc != nil {
		return 1
	}
	return b.resizeCnt
}

func (b *box) resize(increment, remainder int) {
	resized := false
	if b.resizeInc != nil && increment > 0 {
		b.resizeInc(b, increment*b.resizes())
		resized = true
	}
	if b.resizeRem != nil && remainder > 0 {
		b.resizeRem(b, remainder)
		resized = true
	}
	if resized {
		b.compile(true)
	}
}

func (b *box) set(
	lblLhs string, lblLhsAln boxAlign, lblLhsLen int,
	lblMid string, lblMidAln boxAlign, lblMidLen int,
	lblRhs string, lblRhsAln boxAlign, lblRhsLen int,
) {
	b.lblLhs = pad(lblLhs, lblLhsAln, lblLhsLen)
	b.lblMid = pad(lblMid, lblMidAln, lblMidLen)
	b.lblRhs = pad(lblRhs, lblRhsAln, lblRhsLen)
	b.compile(true)
}

func (b *box) length() int {
	b.compile(false)
	return b.compiled.length
}

func (b *box) draw(display *Display, force bool) {
	if display.terminal == nil {
		return
	}
	b.compile(false)
	row, col := b.position.rows, b.position.cols
	draw := func(label string, length int) {
		if label != "" && force == b.valOpt {
			display.terminal.draw(col, row, label, colourDefault)
		}
		col += length
	}
	draw(b.lblLhs, b.compiled.lblLhsLen)
	draw(b.lblMid, b.compiled.lblMidLen)
	draw("", b.valLen)
	draw(b.lblRhs, b.compiled.lblRhsLen)
}

func (b *box) drawLabels(display *Display) {
	b.draw(display, false)
	b.drawValue(display)
}

func (b *box) drawValue(display *Display) {
	if b.recordGUID == nil || display.terminal == nil || display.cache == nil {
		return
	}
	b.compile(false)
	var record *metric.Record
	var ok bool
	if metric.GetIDKind(b.recordGUID.ID) == metric.MetricKindService {
		record, ok = display.cache.LoadByID(b.recordGUID.ID, b.recordGUID.Host, b.recordGUID.ServiceIndex)
	} else {
		record, ok = display.cache.Load(*b.recordGUID)
	}
	if !ok || record == nil || record.Value.Pulse == nil || record.Value.Pulse.IsZero() {
		display.terminal.draw(b.position.cols+b.compiled.valOffset, b.position.rows, strings.Repeat(" ", b.valLen+b.compiled.valSfxLen), colourDefault)
		return
	}
	location := dimensions{b.position.rows, b.position.cols + b.compiled.valOffset}
	b.draw(display, true)
	var trendOK *bool
	if record.Value.Trend != nil {
		trendOK = &record.Value.Trend.OK
	}
	valueString := ""
	switch b.valKind {
	case valBool:
		symbol := display.symbols.cross
		if record.Value.Pulse.OK {
			symbol = display.symbols.tick
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
		barWidth := b.valLen - 6
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
		bar := strings.Repeat(display.symbols.bar, filled) + strings.Repeat(" ", barWidth-filled)
		valueString = "|" + bar + "| " + pad(strconv.Itoa(percentInt), boxRhs, 3) + b.valSfx
	default:
		valueString = pad(record.Value.Pulse.Value(), b.valAln, b.valLen) + b.valSfx
	}
	display.terminal.draw(
		location.cols,
		location.rows,
		valueString,
		highlight(&record.Value.Pulse.OK, trendOK),
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
	if pulse == nil || trend == nil {
		return colourDefault
	}
	if *pulse && *trend {
		return colourGreen
	}
	if *pulse {
		return colourBlue
	}
	return colourRed
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
	baseRunes := []rune(base)
	if len(baseRunes) == 0 {
		return strings.Repeat(" ", length)
	}
	if len(baseRunes) > length {
		if length >= 2 {
			baseRunes = append(baseRunes[:length-1], '~')
		} else {
			baseRunes = baseRunes[:length]
		}
		return string(baseRunes)
	}
	padding := length - len(baseRunes)
	if padding == 0 {
		return string(baseRunes)
	}
	spaces := strings.Repeat(" ", padding)
	if align == boxRhs {
		return spaces + string(baseRunes)
	}
	if align == boxMid {
		leftPad := padding / 2
		rightPad := padding - leftPad
		return strings.Repeat(" ", leftPad) + string(baseRunes) + strings.Repeat(" ", rightPad)
	}
	return string(baseRunes) + spaces
}

func repeat(base string, prefixCount, suffixCount, length int) string {
	if length <= 0 || base == "" {
		return ""
	}
	baseRunes := []rune(base)
	if len(baseRunes) == 0 {
		return ""
	}
	if prefixCount < 0 {
		prefixCount = 0
	}
	if suffixCount < 0 {
		suffixCount = 0
	}
	if prefixCount > len(baseRunes) {
		prefixCount = len(baseRunes)
	}
	if suffixCount > len(baseRunes)-prefixCount {
		suffixCount = len(baseRunes) - prefixCount
	}
	sliceRunes := append([]rune(nil), baseRunes[:prefixCount]...)
	sliceRunes = append(sliceRunes, baseRunes[len(baseRunes)-suffixCount:]...)
	if len(sliceRunes) == 0 {
		return ""
	}
	repeatedRunes := make([]rune, length)
	for i := 0; i < length; i++ {
		repeatedRunes[i] = sliceRunes[i%len(sliceRunes)]
	}
	return string(repeatedRunes)
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
	baseRune, _ := utf8.DecodeRuneInString(base)
	center := strings.Repeat(string(baseRune), centerCount)
	spaces := strings.Repeat(" ", spaceCount)
	return spaces + center + spaces
}
