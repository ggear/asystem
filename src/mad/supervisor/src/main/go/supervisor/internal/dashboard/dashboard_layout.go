package dashboard

import (
	"strings"
	"supervisor/internal/metric"
	"unicode/utf8"
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
	kind      boxKind
	lblLhs    string
	lblMid    string
	lblRhs    string
	valLen    int
	valOpt    bool
	valAln    boxAlign
	valKind   boxValKind
	position  *dimensions
	metric    metric.ID
	record    *metric.RecordGUID
	compiled  *compiled
	resizeCnt int
	resizeInc func(b *box, i int)
	resizeRem func(b *box, r int)
}

type compiled struct {
	length    int
	lblLhsLen int
	lblMidLen int
	lblRhsLen int
	valOffset int
}

/*
── host-numbe~ ─────────────────────────────────────────── ||
Used CPU 100%  Fail SVC 100%  Warn TEM 100%  Used SYS 100% ||
Used RAM  39%  Fail SHR 100%  Revs Fan 100%  Used SHR  10% ||
Aloc RAM   1%  Fail BCK   4%  Life SSD   3%  Used BKP  10% ||
---------------------------------------------------------- ||
SERVICE     CPU  RAM BKP AOK  SERVICE     CPU  RAM BKP AOK ||
homeassis~ 100% 100%  O   X   service2   100% 100%  X   X  ||
service3    11%  11%  X   X   service4    10% 100%  X   X  ||
service5    10% 100%  O   O   service6    10% 100%  O   O  ||
service7    20%  20%  X   O   service8    10% 100%  X   X  ||
service90~   0%   0%  X   X   ~             ~    ~  ~   ~  ||
*/
//noinspection GoSnakeCaseUsage
func compactDashboardLayout() [][]box {
	resizeService := func(b *box, i int) { b.valLen += i }
	resizeDivider := func(b *box, r int) { b.lblLhs = divider(b.lblLhs, r+len(b.lblLhs)) }
	resizeLblRhs1 := func(b *box, i int) { b.lblRhs += repeat(b.lblRhs, 0, 1, i) }
	resizeLblLhs1 := func(b *box, i int) { b.lblLhs += repeat(b.lblLhs, 0, 1, i) }

	t_0_0 := box{lblLhs: "── ", lblMid: "           ", lblRhs: " ───────────────────────────────────────────", resizeCnt: 3, kind: boxTitle, resizeInc: resizeLblRhs1}

	d_1_0 := box{lblMid: "Used CPU ", valLen: 3, lblRhs: "%", metric: metric.MetricHostComputeUsedProcessor}
	d_1_1 := box{lblMid: "Fail SVC ", valLen: 3, lblRhs: "%", lblLhs: "  ", metric: metric.MetricHostHealthFailedServices, resizeInc: resizeLblLhs1}
	d_1_2 := box{lblMid: "Warn TEM ", valLen: 3, lblRhs: "%", lblLhs: "  ", metric: metric.MetricHostRuntimeWarningTemperatureOfMax, resizeInc: resizeLblLhs1}
	d_1_3 := box{lblMid: "Used SYS ", valLen: 3, lblRhs: "%", lblLhs: "  ", metric: metric.MetricHostStorageUsedSystemDrive, resizeInc: resizeLblLhs1}

	d_2_0 := box{lblMid: "Used RAM ", valLen: 3, lblRhs: "%", metric: metric.MetricHostComputeUsedMemory}
	d_2_1 := box{lblMid: "Fail SHR ", valLen: 3, lblRhs: "%", lblLhs: "  ", metric: metric.MetricHostHealthFailedShares, resizeInc: resizeLblLhs1}
	d_2_2 := box{lblMid: "Revs Fan ", valLen: 3, lblRhs: "%", lblLhs: "  ", metric: metric.MetricHostRuntimeRevsFanSpeedOfMax, resizeInc: resizeLblLhs1}
	d_2_3 := box{lblMid: "Used SHR ", valLen: 3, lblRhs: "%", lblLhs: "  ", metric: metric.MetricHostStorageUsedShareDrives, resizeInc: resizeLblLhs1}

	d_3_0 := box{lblMid: "Aloc RAM ", valLen: 3, lblRhs: "%", metric: metric.MetricHostComputeAllocatedMemory}
	d_3_1 := box{lblMid: "Fail BCK ", valLen: 3, lblRhs: "%", lblLhs: "  ", metric: metric.MetricHostHealthFailedBackups, resizeInc: resizeLblLhs1}
	d_3_2 := box{lblMid: "Life SSD ", valLen: 3, lblRhs: "%", lblLhs: "  ", metric: metric.MetricHostRuntimeLifeUsedDrives, resizeInc: resizeLblLhs1}
	d_3_3 := box{lblMid: "Used BKP ", valLen: 3, lblRhs: "%", lblLhs: "  ", metric: metric.MetricHostStorageUsedBackupDrives, resizeInc: resizeLblLhs1}

	s_4_0 := box{lblLhs: "----------------------------------------------------------", resizeCnt: 3, kind: boxSpacr, resizeInc: resizeLblLhs1}

	l_5_0 := box{lblMid: "SERVICE", lblRhs: "    ", kind: boxLabel, resizeInc: resizeLblRhs1}
	l_5_1 := box{lblMid: "CPU", lblLhs: " ", lblRhs: " ", kind: boxLabel}
	l_5_2 := box{lblMid: "RAM", lblLhs: " ", lblRhs: " ", kind: boxLabel}
	l_5_3 := box{lblMid: "BKP", lblRhs: " ", kind: boxLabel}
	l_5_4 := box{lblMid: "AOK", kind: boxLabel}

	d_X_0 := box{lblRhs: " ", valLen: 10, valAln: boxLhs, valOpt: true, metric: metric.MetricServiceName, resizeInc: resizeService}
	d_X_1 := box{lblRhs: "% ", valLen: 3, valOpt: true, metric: metric.MetricServiceUsedProcessor}
	d_X_2 := box{lblRhs: "% ", valLen: 3, valOpt: true, metric: metric.MetricServiceUsedMemory}
	d_X_3 := box{lblLhs: " ", valLen: 1, lblRhs: "  ", valOpt: true, metric: metric.MetricServiceBackupStatus}
	d_X_4 := box{lblLhs: " ", valLen: 1, lblRhs: " ", valOpt: true, metric: metric.MetricService}

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
Used CPU [##] 100%    Fail SVC [##] 100%    Warn TEM [##] 100%    Used SYS [##] 100%   ||
Used RAM [# ]  39%    Fail SHR [##] 100%    Revs Fan [##] 100%    Used SHR [# ]  10%   ||
Aloc RAM [# ]   1%    Fail BCK [# ]   4%    Life SSD [# ]   3%    Used BKP [# ]  10%   ||
------------------------------------------------------------------------------------   ||
SERVICE          VERNUM          CPU            MEM       BKP  HLT  CFG  RST  RUNTME   ||
------------------------------------------------------------------------------------   ||
homeassistant 10.100.10001   [####] 100%    [####] 100%    X    X    X    0     156d   ||
service2      10.100.10001   [### ]  65%    [#   ]  11%    O    X    X    0      10y   ||
service3      10.100.10001   [#   ]  11%    [##  ]  51%    O    O    X    0       1y   ||
service4      10.100.10001   [### ]  65%    [### ]  65%    O    X    X    0       2y   ||
service5      10.100.10001   [##  ]  51%    [#   ]  11%    X    O    X    0      10d   ||
service6      10.100.10001   [##  ]  51%    [#   ]  11%    O    X    X    0       1h   ||
service7      10.100.10001   [#   ]   1%    [##  ]  51%    O    X    X    0      34m   ||
service8      10.100.10001   [### ]  65%    [#   ]  11%    O    O    O    0      10y   ||
service90000~ 10.100.10001   [#   ]  11%    [### ]  65%    O    X    X    ~     100d   ||
~              ~                       ~              ~    ~    ~    ~    ~        ~   ||
*/
//noinspection GoSnakeCaseUsage
func relaxedDashboardLayout() [][]box {
	resizeHistVal := func(b *box, i int) { b.valLen += i }
	resizeHistLbl := func(b *box, r int) { b.lblMid = pad(b.lblMid, boxMid, r+len(b.lblMid)) }
	resizeDivider := func(b *box, r int) { b.lblLhs = divider(b.lblLhs, r+len(b.lblLhs)) }
	resizeLblRhs1 := func(b *box, i int) { b.lblRhs += repeat(b.lblRhs, 0, 1, i) }
	resizeLblLhs1 := func(b *box, i int) { b.lblLhs += repeat(b.lblLhs, 0, 1, i) }

	t_0_0 := box{lblLhs: "── ", lblMid: "           ", lblRhs: " ─────────────────────────────────────────────────────────────────────", resizeCnt: 4, kind: boxTitle, resizeInc: resizeLblRhs1}

	d_1_0 := box{lblMid: "Used CPU ", valLen: 8, lblRhs: "%", valKind: valHist, metric: metric.MetricHostComputeUsedProcessor, resizeInc: resizeHistVal}
	d_1_1 := box{lblMid: "Fail SVC ", valLen: 8, lblRhs: "%", valKind: valHist, lblLhs: "    ", metric: metric.MetricHostHealthFailedServices, resizeInc: resizeHistVal}
	d_1_2 := box{lblMid: "Warn TEM ", valLen: 8, lblRhs: "%", valKind: valHist, lblLhs: "    ", metric: metric.MetricHostRuntimeWarningTemperatureOfMax, resizeInc: resizeHistVal}
	d_1_3 := box{lblMid: "Used SYS ", valLen: 8, lblRhs: "%", valKind: valHist, lblLhs: "    ", metric: metric.MetricHostStorageUsedSystemDrive, resizeInc: resizeHistVal}

	d_2_0 := box{lblMid: "Used RAM ", valLen: 8, lblRhs: "%", valKind: valHist, metric: metric.MetricHostComputeUsedMemory, resizeInc: resizeHistVal}
	d_2_1 := box{lblMid: "Fail SHR ", valLen: 8, lblRhs: "%", valKind: valHist, lblLhs: "    ", metric: metric.MetricHostHealthFailedShares, resizeInc: resizeHistVal}
	d_2_2 := box{lblMid: "Revs Fan ", valLen: 8, lblRhs: "%", valKind: valHist, lblLhs: "    ", metric: metric.MetricHostRuntimeRevsFanSpeedOfMax, resizeInc: resizeHistVal}
	d_2_3 := box{lblMid: "Used SHR ", valLen: 8, lblRhs: "%", valKind: valHist, lblLhs: "    ", metric: metric.MetricHostStorageUsedShareDrives, resizeInc: resizeHistVal}

	d_3_0 := box{lblMid: "Aloc RAM ", valLen: 8, lblRhs: "%", valKind: valHist, metric: metric.MetricHostComputeAllocatedMemory, resizeInc: resizeHistVal}
	d_3_1 := box{lblMid: "Fail BCK ", valLen: 8, lblRhs: "%", valKind: valHist, lblLhs: "    ", metric: metric.MetricHostHealthFailedBackups, resizeInc: resizeHistVal}
	d_3_2 := box{lblMid: "Life SSD ", valLen: 8, lblRhs: "%", valKind: valHist, lblLhs: "    ", metric: metric.MetricHostRuntimeLifeUsedDrives, resizeInc: resizeHistVal}
	d_3_3 := box{lblMid: "Used BKP ", valLen: 8, lblRhs: "%", valKind: valHist, lblLhs: "    ", metric: metric.MetricHostStorageUsedBackupDrives, resizeInc: resizeHistVal}

	s_X_0 := box{lblLhs: "------------------------------------------------------------------------------------", kind: boxSpacr, resizeCnt: 4, resizeInc: resizeLblLhs1}

	l_5_0 := box{lblMid: "SERVICE", lblRhs: "       ", kind: boxLabel}
	l_5_1 := box{lblMid: "VERNUM", lblLhs: "   ", lblRhs: "   ", kind: boxLabel}
	l_5_2 := box{lblMid: "CPU", lblLhs: "       ", lblRhs: "    ", kind: boxLabel, resizeCnt: 2, resizeInc: resizeHistLbl}
	l_5_3 := box{lblMid: "MEM", lblLhs: "        ", lblRhs: "    ", kind: boxLabel, resizeCnt: 2, resizeInc: resizeHistLbl}
	l_5_4 := box{lblMid: "BKP", lblLhs: "   ", kind: boxLabel}
	l_5_5 := box{lblMid: "HLT", lblLhs: "  ", kind: boxLabel}
	l_5_6 := box{lblMid: "CFG", lblLhs: "  ", kind: boxLabel}
	l_5_7 := box{lblMid: "RST", lblLhs: "  ", kind: boxLabel}
	l_5_8 := box{lblMid: "RUNTME", lblLhs: "  ", kind: boxLabel}

	d_X_0 := box{valLen: 13, lblRhs: " ", valAln: boxLhs, valOpt: true, valKind: valText, metric: metric.MetricServiceName}
	d_X_1 := box{valLen: 12, valOpt: true, valKind: valText, metric: metric.MetricServiceVersion}
	d_X_2 := box{lblLhs: "   ", lblRhs: "%", valLen: 10, valOpt: true, valKind: valHist, metric: metric.MetricServiceUsedProcessor, resizeCnt: 2, resizeInc: resizeHistVal}
	d_X_3 := box{lblLhs: "   ", lblRhs: "%", valLen: 10, valOpt: true, valKind: valHist, metric: metric.MetricServiceUsedMemory, resizeCnt: 2, resizeInc: resizeHistVal}
	d_X_4 := box{lblLhs: "   ", lblRhs: " ", valLen: 1, valOpt: true, valKind: valBool, metric: metric.MetricServiceBackupStatus}
	d_X_5 := box{lblLhs: "   ", lblRhs: " ", valLen: 1, valOpt: true, valKind: valBool, metric: metric.MetricServiceHealthStatus}
	d_X_6 := box{lblLhs: "   ", lblRhs: " ", valLen: 1, valOpt: true, valKind: valBool, metric: metric.MetricServiceConfiguredStatus}
	d_X_7 := box{lblLhs: "   ", lblRhs: " ", valLen: 1, valOpt: true, metric: metric.MetricServiceRestartCount}
	d_X_8 := box{lblLhs: "   ", valLen: 4, valOpt: true, valKind: valTime, metric: metric.MetricServiceRuntime}

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
	if hostCount == 0 {
		return 0
	}
	if hostCount == 1 && count > 0 {
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
	b.compiled.valOffset = b.compiled.lblLhsLen + b.compiled.lblMidLen
	b.compiled.length = b.compiled.valOffset + b.valLen + b.compiled.lblRhsLen
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

func (b *box) draw(terminal Terminal, force bool) {
	b.compile(false)
	row, col := b.position.rows, b.position.cols
	draw := func(label string, length int) {
		if label != "" && force == b.valOpt {
			terminal.draw(col, row, label, colourDefault)
		}
		col += length
	}
	draw(b.lblLhs, b.compiled.lblLhsLen)
	draw(b.lblMid, b.compiled.lblMidLen)
	draw("", b.valLen)
	draw(b.lblRhs, b.compiled.lblRhsLen)
}

func (b *box) drawLabels(terminal Terminal, cache *metric.RecordCache) {
	b.draw(terminal, false)
	b.drawValue(terminal, cache)
}

func (b *box) drawValue(terminal Terminal, cache *metric.RecordCache) {
	if b.record == nil {
		return
	}
	b.compile(false)
	record, ok := cache.Get(*b.record)
	if !ok || record == nil {
		return
	}
	if record.Pulse.Datum == "" || record.Pulse.OK == nil || record.Trend.OK == nil {
		return
	}
	location := dimensions{b.position.rows, b.position.cols + b.compiled.valOffset}
	b.draw(terminal, true)
	terminal.draw(
		location.rows,
		location.cols,
		pad(record.Pulse.Datum, b.valAln, b.valLen),
		highlight(record.Pulse.OK, record.Trend.OK),
	)
}

func (b *box) clone() *box {
	clone := *b
	if b.record != nil {
		recordClone := *b.record
		clone.record = &recordClone
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
		return colourYellow
	}
	return colourRed
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
