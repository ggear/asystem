package dashboard

import (
	"strings"
	"supervisor/internal/metric"
	"sync/atomic"
	"unicode/utf8"
)

type boxKind int

const (
	boxDatum boxKind = iota
	boxTitle
	boxLabel
	boxSpace
	boxRline
	boxCline
)

type boxValKind int

const (
	valText boxValKind = iota
	valTime
	valHist
	valNone
)

type box struct {
	kind     boxKind
	lblLhs   string
	lblMid   string
	lblRhs   string
	valLen   int
	valOpt   bool
	valKind  boxValKind
	metric   metric.ID
	record   *metric.RecordGUID
	dirty    *atomic.Bool
	location *Dimensions
	resize   func(box *box, length int)
}

/*
── labnode-one ─────────────────────────────────────────── ||
Used CPU 100%  Fail SVC 100%  Warn TEM 100%  Used SYS 100% ||
Used RAM  39%  Fail SHR 100%  Revs Fan 100%  Used SHR  10% ||
Aloc RAM   1%  Fail BCK   4%  Life SSD   3%  Used BKP  10% ||
-  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  - ||
SERVICE     CPU  RAM BKP AOK  SERVICE     CPU  RAM BKP AOK ||
homeassis~ 100% 100%  O   X   service20~ 100% 100%  X   X  ||
service30~  11%  11%  X   X   service40~  10% 100%  X   X  ||
service50~  10% 100%  O   O   service60~  10% 100%  O   O  ||
service70~  20%  20%  X   O   service80~  10% 100%  X   X  ||
service90~   0%   0%  X   X   ~             ~    ~  ~   ~  ||
*/
//noinspection GoSnakeCaseUsage
func compactDashboardLayout() [][]box {
	resizeValLen := func(box *box, length int) { box.valLen += length }
	resizeCline := func(box *box, length int) { box.lblLhs = divider(box.lblRhs, length) }
	resizeLblRhs1 := func(box *box, length int) { box.lblRhs += repeat(box.lblRhs, 0, 1, length) }
	resizeLblLhs1 := func(box *box, length int) { box.lblLhs += repeat(box.lblLhs, 0, 1, length) }
	resizeLblLhs3 := func(box *box, length int) { box.lblLhs += repeat(box.lblLhs, 0, 3, length) }

	t_0_0 := box{lblLhs: "── ", valLen: 11, lblRhs: " ──", kind: boxTitle, resize: resizeLblRhs1}
	t_0_1 := box{lblLhs: "───", kind: boxTitle, resize: resizeLblLhs1}
	t_0_2 := box{lblLhs: "──────────────────────────────────────", kind: boxTitle, resize: resizeLblLhs1}

	d_1_0 := box{lblMid: "Used CPU ", valLen: 3, lblRhs: "%", metric: metric.MetricHostComputeUsedProcessor}
	d_1_1 := box{lblMid: "Fail SVC ", valLen: 3, lblRhs: "%", lblLhs: "  ", metric: metric.MetricHostHealthFailedServices, resize: resizeLblLhs1}
	d_1_2 := box{lblMid: "Warn TEM ", valLen: 3, lblRhs: "%", lblLhs: "  ", metric: metric.MetricHostRuntimeWarningTemperatureOfMax, resize: resizeLblLhs1}
	d_1_3 := box{lblMid: "Used SYS ", valLen: 3, lblRhs: "%", lblLhs: "  ", metric: metric.MetricHostStorageUsedSystemDrive, resize: resizeLblLhs1}

	d_2_0 := box{lblMid: "Used RAM ", valLen: 3, lblRhs: "%", metric: metric.MetricHostComputeUsedMemory}
	d_2_1 := box{lblMid: "Fail SHR ", valLen: 3, lblRhs: "%", lblLhs: "  ", metric: metric.MetricHostHealthFailedShares, resize: resizeLblLhs1}
	d_2_2 := box{lblMid: "Revs Fan ", valLen: 3, lblRhs: "%", lblLhs: "  ", metric: metric.MetricHostRuntimeRevsFanSpeedOfMax, resize: resizeLblLhs1}
	d_2_3 := box{lblMid: "Used SHR ", valLen: 3, lblRhs: "%", lblLhs: "  ", metric: metric.MetricHostStorageUsedShareDrives, resize: resizeLblLhs1}

	d_3_0 := box{lblMid: "Aloc RAM ", valLen: 3, lblRhs: "%", metric: metric.MetricHostComputeAllocatedMemory}
	d_3_1 := box{lblMid: "Fail BCK ", valLen: 3, lblRhs: "%", lblLhs: "  ", metric: metric.MetricHostHealthFailedBackups, resize: resizeLblLhs1}
	d_3_2 := box{lblMid: "Life SSD ", valLen: 3, lblRhs: "%", lblLhs: "  ", metric: metric.MetricHostRuntimeLifeUsedDrives, resize: resizeLblLhs1}
	d_3_3 := box{lblMid: "Used BKP ", valLen: 3, lblRhs: "%", lblLhs: "  ", metric: metric.MetricHostStorageUsedBackupDrives, resize: resizeLblLhs1}

	r_4_0 := box{lblLhs: "-  ", kind: boxRline, resize: resizeLblLhs3}
	r_4_1 := box{lblLhs: "-  ", kind: boxRline, resize: resizeLblLhs3}
	r_4_2 := box{lblLhs: "-  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -", kind: boxRline, resize: resizeLblLhs3}

	l_5_0 := box{lblMid: "SERVICE   ", lblRhs: " ", kind: boxLabel, resize: resizeLblRhs1}
	l_5_1 := box{lblMid: "CPU", lblLhs: " ", lblRhs: " ", kind: boxLabel}
	l_5_2 := box{lblMid: "RAM", lblLhs: " ", lblRhs: " ", kind: boxLabel}
	l_5_3 := box{lblMid: "BKP", lblRhs: " ", kind: boxLabel}
	l_5_4 := box{lblMid: "AOK", kind: boxLabel}

	d_X_0 := box{lblRhs: " ", valOpt: true, valLen: 10, metric: metric.MetricServiceName, resize: resizeValLen}
	d_X_1 := box{lblRhs: "% ", valOpt: true, valLen: 3, metric: metric.MetricServiceUsedProcessor}
	d_X_2 := box{lblRhs: "% ", valOpt: true, valLen: 3, metric: metric.MetricServiceUsedMemory}
	d_X_3 := box{lblLhs: " ", valOpt: true, valLen: 1, lblRhs: "  ", metric: metric.MetricServiceBackupStatus}
	d_X_4 := box{lblLhs: " ", valOpt: true, valLen: 1, lblRhs: " ", metric: metric.MetricService}

	s_X_5 := box{lblLhs: "  ", kind: boxSpace, resize: resizeLblLhs1}

	c_X_X := box{lblLhs: " ", kind: boxCline, resize: resizeLblLhs1}
	c_Y_Y := box{lblLhs: "||", kind: boxCline, resize: resizeCline}
	c_Z_Z := box{lblLhs: " ", kind: boxCline, resize: resizeLblLhs1}

	return [][]box{
		{t_0_0, t_0_1, t_0_2, c_X_X, c_Y_Y, c_Z_Z},
		{d_1_0, d_1_1, d_1_2, d_1_3, c_X_X, c_Y_Y, c_Z_Z},
		{d_2_0, d_2_1, d_2_2, d_2_3, c_X_X, c_Y_Y, c_Z_Z},
		{d_3_0, d_3_1, d_3_2, d_3_3, c_X_X, c_Y_Y, c_Z_Z},
		{r_4_0, r_4_1, r_4_2, c_X_X, c_Y_Y, c_Z_Z},
		{l_5_0, l_5_1, l_5_2, l_5_3, l_5_4, s_X_5, l_5_0, l_5_1, l_5_2, l_5_3, l_5_4, c_X_X, c_Y_Y, c_Z_Z},
		{d_X_0, d_X_1, d_X_2, d_X_3, d_X_4, s_X_5, d_X_0, d_X_1, d_X_2, d_X_3, d_X_4, c_X_X, c_Y_Y, c_Z_Z},
		{d_X_0, d_X_1, d_X_2, d_X_3, d_X_4, s_X_5, d_X_0, d_X_1, d_X_2, d_X_3, d_X_4, c_X_X, c_Y_Y, c_Z_Z},
		{d_X_0, d_X_1, d_X_2, d_X_3, d_X_4, s_X_5, d_X_0, d_X_1, d_X_2, d_X_3, d_X_4, c_X_X, c_Y_Y, c_Z_Z},
		{d_X_0, d_X_1, d_X_2, d_X_3, d_X_4, s_X_5, d_X_0, d_X_1, d_X_2, d_X_3, d_X_4, c_X_X, c_Y_Y, c_Z_Z},
		{d_X_0, d_X_1, d_X_2, d_X_3, d_X_4, s_X_5, d_X_0, d_X_1, d_X_2, d_X_3, d_X_4, c_X_X, c_Y_Y, c_Z_Z},
	}
}

/*
── labnode-one ────────────────────────────────────────────────────────────────────────   ||
Used CPU [##] 100%     Fail SVC [##] 100%     Warn TEM [##] 100%     Used SYS [##] 100%   ||
Used RAM [# ]  39%     Fail SHR [##] 100%     Revs Fan [##] 100%     Used SHR [# ]  10%   ||
Aloc RAM [# ]   1%     Fail BCK [# ]   4%     Life SSD [# ]   3%     Used BKP [# ]  10%   ||
- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -   ||
SERVICE              CPU           MEM       BKP   HLT   CFG   RST   RUN      VERNUM      ||
- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -   ||
homeassistant    [####] 100%   [####] 100%    X     X     X      0    1y   10.100.10001   ||
service20000000~ [#   ]  11%   [#   ]  11%    O     O     O     12   10d   10.100.10002   ||
service30000000~ [####] 100%   [####] 100%    O     O     O     99   10y   10.100.10003   ||
service40000000~ [#   ]  22%   [#   ]  22%    O     O     O      0    1y   10.100.10004   ||
service50000000~ [####] 100%   [##  ]  50%    O     O     O      0    1y   10.100.10005   ||
service60000000~ [####] 100%   [##  ]  50%    X     O     O      0    1y   10.100.10006   ||
service70000000~ [##  ]  50%   [####] 100%    O     O     O      0    1y   10.100.10007   ||
service80000000~ [####] 100%   [####] 100%    X     X     X      0    1y   10.100.10008   ||
service90000000~ [#   ]  33%   [#   ]  33%    O     O     O      0    1y   10.100.10009   ||
~                          ~             ~    ~     ~     ~      ~     ~              ~   ||
*/
//noinspection GoSnakeCaseUsage
func relaxedDashboardLayout() [][]box {

	// TODO: Provide implementation

	return compactDashboardLayout()
}

func (b *box) length() int {
	return utf8.RuneCountInString(b.lblLhs) + utf8.RuneCountInString(b.lblMid) + utf8.RuneCountInString(b.lblRhs) + b.valLen
}

func (b *box) valueLocation() Dimensions {
	return Dimensions{b.location.Rows, b.location.Cols + utf8.RuneCountInString(b.lblLhs) + utf8.RuneCountInString(b.lblMid)}
}

func (b *box) clone() *box {
	if b == nil {
		return nil
	}
	clone := *b
	clone.dirty = &atomic.Bool{}
	if b.record != nil {
		recordClone := *b.record
		clone.record = &recordClone
	}
	if b.location != nil {
		posClone := *b.location
		clone.location = &posClone
	}
	return &clone
}

func (b *box) MarkDirty() {
	if b.dirty == nil {
		b.dirty = &atomic.Bool{}
	}
	b.dirty.Store(true)
}

func (b *box) TakeDirty() bool {
	if b.dirty == nil {
		return false
	}
	return b.dirty.Swap(false)
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
