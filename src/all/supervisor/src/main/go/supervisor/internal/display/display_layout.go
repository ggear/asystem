package display

import (
	"math"
	"strconv"
	"strings"
	"supervisor/internal/metric"
	"unicode/utf8"
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
	lblLhs     text
	lblMid     text
	lblRhs     text
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

/* Optimised for for >2 host @ 120x33 ASCII
+= ahosts-one~ ===================================== ^1/2 =++= ahosts-two~ ===================================== ^2/2 =+
|Used CPU 100%  Fail SVC 100%  Warn TEM 100%  Used SYS 100%||Used CPU 100%  Fail SVC 100%  Warn TEM 100%  Used SYS 100%|
|Used RAM  39%  Fail SHR 100%  Revs Fan 100%  Used SHR  10%||Used RAM  39%  Fail SHR 100%  Revs Fan 100%  Used SHR  10%|
|Aloc RAM   1%  Fail BCK   4%  Life SSD   3%  Used BKP  10%||Aloc RAM   1%  Fail BCK   4%  Life SSD   3%  Used BKP  10%|
|----------------------------------------------------------||----------------------------------------------------------|
|SERVICE     CPU  RAM BKP AOK  SERVICE     CPU  RAM BKP AOK||SERVICE     CPU  RAM BKP AOK  SERVICE     CPU  RAM BKP AOK|
|homeassis~ 100% 100%  +   -   service2   100% 100%  -   - ||homeassis~ 100% 100%  +   -   service2   100% 100%  -   - |
|service3    11%  12%  -   -   service4    10% 100%  -   - ||service3    11%  12%  -   -   service4    10% 100%  -   - |
|service5    10% 100%  -   +   service6    10% 100%  +   - ||service5    10% 100%  -   +   service6    10% 100%  +   - |
|service70~   0%   1%  -   -   ~             ~    ~  ~   ~ ||service70~   0%   1%  -   -   ~             ~    ~  ~   ~ |
*/
/* Optimised for for >2 host @ 128x33 ASCII
+= ahosts-one~ ========================================= ^1/2 =++= ahosts-two~ ========================================= ^2/2 =+
|  Used CPU 100%  Fail SVC 100%  Warn TEM 100%  Used SYS 100%  ||  Used CPU 100%  Fail SVC 100%  Warn TEM 100%  Used SYS 100%  |
|  Used RAM  39%  Fail SHR 100%  Revs Fan 100%  Used SHR  10%  ||  Used RAM  39%  Fail SHR 100%  Revs Fan 100%  Used SHR  10%  |
|  Aloc RAM   1%  Fail BCK   4%  Life SSD   3%  Used BKP  10%  ||  Aloc RAM   1%  Fail BCK   4%  Life SSD   3%  Used BKP  10%  |
|--------------------------------------------------------------||--------------------------------------------------------------|
|  SERVICE     CPU  RAM BKP AOK  SERVICE     CPU  RAM BKP AOK  ||  SERVICE     CPU  RAM BKP AOK  SERVICE     CPU  RAM BKP AOK  |
|  homeassis~ 100% 100%  +   -   service2   100% 100%  -   -   ||  homeassis~ 100% 100%  +   -   service2   100% 100%  -   -   |
|  service3    11%  12%  -   -   service4    10% 100%  -   -   ||  service3    11%  12%  -   -   service4    10% 100%  -   -   |
|  service5    10% 100%  -   +   service6    10% 100%  +   -   ||  service5    10% 100%  -   +   service6    10% 100%  +   -   |
|  service70~   0%   1%  -   -   ~             ~    ~  ~   ~   ||  service70~   0%   1%  -   -   ~             ~    ~  ~   ~   |
*/
//noinspection GoSnakeCaseUsage
func compactDisplayLayout() [][]box {
	resizeIncService := func(b *box, i int) { b.valLen += i }
	resizeIncLblRhs1 := func(b *box, i int) {
		b.lblRhs = b.lblRhs.resize(i, func(value string, length int) string {
			return value + repeat(value, 0, 1, length-runeCount(value))
		})
	}
	resizeIncLblLhs1 := func(b *box, i int) {
		b.lblLhs = b.lblLhs.resize(i, func(value string, length int) string {
			return value + repeat(value, 0, 1, length-runeCount(value))
		})
	}
	resizeRemDivider := func(b *box, r int) { b.lblLhs = b.lblLhs.resize(r, divider) }

	t_0_0 := box{lblLhs: text{ascii: "── "}, lblMid: text{ascii: "           "}, lblRhs: text{ascii: " ───────────────────────────────────────────"}, resizeCnt: 3, kind: boxTitle, resizeInc: resizeIncLblRhs1}

	d_1_0 := box{lblMid: text{ascii: "Used CPU "}, valLen: 3, valSfx: "%", metricID: metric.MetricHostUsedProcessor}
	d_1_1 := box{lblMid: text{ascii: "Fail LOG "}, valLen: 3, valSfx: "%", lblLhs: text{ascii: "  "}, metricID: metric.MetricHostFailedLogs, resizeInc: resizeIncLblLhs1}
	d_1_2 := box{lblMid: text{ascii: "Warn TEM "}, valLen: 3, valSfx: "%", lblLhs: text{ascii: "  "}, metricID: metric.MetricHostWarnTemperatureOfMax, resizeInc: resizeIncLblLhs1}
	d_1_3 := box{lblMid: text{ascii: "Used SYS "}, valLen: 3, valSfx: "%", lblLhs: text{ascii: "  "}, metricID: metric.MetricHostUsedSystemSpace, resizeInc: resizeIncLblLhs1}

	d_2_0 := box{lblMid: text{ascii: "Used RAM "}, valLen: 3, valSfx: "%", metricID: metric.MetricHostUsedMemory}
	d_2_1 := box{lblMid: text{ascii: "Fail SHR "}, valLen: 3, valSfx: "%", lblLhs: text{ascii: "  "}, metricID: metric.MetricHostFailedShares, resizeInc: resizeIncLblLhs1}
	d_2_2 := box{lblMid: text{ascii: "Revs Fan "}, valLen: 3, valSfx: "%", lblLhs: text{ascii: "  "}, metricID: metric.MetricHostSpinFanSpeedOfMax, resizeInc: resizeIncLblLhs1}
	d_2_3 := box{lblMid: text{ascii: "Used SHR "}, valLen: 3, valSfx: "%", lblLhs: text{ascii: "  "}, metricID: metric.MetricHostUsedShareSpace, resizeInc: resizeIncLblLhs1}

	d_3_0 := box{lblMid: text{ascii: "Aloc RAM "}, valLen: 3, valSfx: "%", metricID: metric.MetricHostAllocatedMemory}
	d_3_1 := box{lblMid: text{ascii: "Fail BCK "}, valLen: 3, valSfx: "%", lblLhs: text{ascii: "  "}, metricID: metric.MetricHostFailedBackups, resizeInc: resizeIncLblLhs1}
	d_3_2 := box{lblMid: text{ascii: "Life SSD "}, valLen: 3, valSfx: "%", lblLhs: text{ascii: "  "}, metricID: metric.MetricHostLifeUsedDrives, resizeInc: resizeIncLblLhs1}
	d_3_3 := box{lblMid: text{ascii: "Used BKP "}, valLen: 3, valSfx: "%", lblLhs: text{ascii: "  "}, metricID: metric.MetricHostUsedBackupSpace, resizeInc: resizeIncLblLhs1}

	s_4_0 := box{lblLhs: text{ascii: "----------------------------------------------------------"}, resizeCnt: 3, kind: boxSpacr, resizeInc: resizeIncLblLhs1}

	l_5_0 := box{lblMid: text{ascii: "SERVICE"}, lblRhs: text{ascii: "    "}, kind: boxLabel, resizeInc: resizeIncLblRhs1}
	l_5_1 := box{lblMid: text{ascii: "CPU"}, lblLhs: text{ascii: " "}, lblRhs: text{ascii: " "}, kind: boxLabel}
	l_5_2 := box{lblMid: text{ascii: "RAM"}, lblLhs: text{ascii: " "}, lblRhs: text{ascii: " "}, kind: boxLabel}
	l_5_3 := box{lblMid: text{ascii: "BKP"}, lblRhs: text{ascii: " "}, kind: boxLabel}
	l_5_4 := box{lblMid: text{ascii: "AOK"}, kind: boxLabel}

	d_X_0 := box{lblRhs: text{ascii: " "}, valLen: 10, valAln: boxLhs, valOpt: true, metricID: metric.MetricServiceName, resizeInc: resizeIncService}
	d_X_1 := box{valSfx: "%", lblRhs: text{ascii: " "}, valLen: 3, valOpt: true, metricID: metric.MetricServiceUsedProcessor}
	d_X_2 := box{valSfx: "%", lblRhs: text{ascii: " "}, valLen: 3, valOpt: true, metricID: metric.MetricServiceUsedMemory}
	d_X_3 := box{lblLhs: text{ascii: " "}, valLen: 1, lblRhs: text{ascii: "  "}, valOpt: true, valKind: valBool, metricID: metric.MetricServiceBackupStatus}
	d_X_4 := box{lblLhs: text{ascii: " "}, valLen: 1, lblRhs: text{ascii: " "}, valOpt: true, valKind: valBool, metricID: metric.MetricService}

	s_X_5 := box{lblLhs: text{ascii: "  "}, kind: boxSpacr, resizeInc: resizeIncLblLhs1}

	v_X_X := box{lblLhs: text{ascii: " "}, kind: boxDivdr, resizeInc: resizeIncLblLhs1}
	v_Y_Y := box{lblLhs: text{ascii: "||"}, kind: boxDivdr, resizeRem: resizeRemDivider}

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

/* Optimised for 1 host @ 79x16 ASCII
+= ahosts-one~ ======================================================== vESC =+
| Used CPU ■■ 100%    Fail SVC ■■ 100%   Warn TEM ■■ 100%    Used SYS ■■ 100% |
| Used RAM ■■  39%    Fail SHR ■■ 100%   Revs Fan ■■ 100%    Used SHR ■■  10% |
| Aloc RAM ■■   1%    Fail BCK ■■   4%   Life SSD ■■   3%    Used BKP ■■  10% |
+-----------------------------------------------------------------------------+
| SERVICE          VERNUM      CPU       MEM       BKP  HLT  CFG  RST  UPTIME |
+-----------------------------------------------------------------------------+
| homeassistant 10.100.10001   ■■ 100%   ■■ 100%    -    -    -    0     156d |
| service2      10.100.10001   ■■  65%   ■■  11%    +    -    -    0      10y |
| service3      10.100.10001   ■■  11%   ■■  51%    +    +    -    0       1y |
| service4      10.100.10001   ■■  65%   ■■  65%    +    -    -    0       2y |
| service5      10.100.10001   ■■  51%   ■■  11%    -    +    -    0      10d |
| service6      10.100.10001   ■■  51%   ■■  11%    +    -    -    0       1h |
| service70000~ 10.100.10001   ■■  11%   ■■  65%    +    -    -    ~     100d |
| ~                        ~         ~         ~    ~    ~    ~    ~        ~ |
+=============================================================================+
*/
/* Optimised for 1 host @ 88 (scaled 120/128)x16 ASCII
+= ahosts-one~ ================================================================= vESC =+
| Used CPU ■■■■ 100%    Fail SVC ■■■■ 100%    Warn TEM ■■■■ 100%    Used SYS ■■■■ 100% |
| Used RAM ■■■■  39%    Fail SHR ■■■■ 100%    Revs Fan ■■■■ 100%    Used SHR ■■■■  10% |
| Aloc RAM ■■■■   1%    Fail BCK ■■■■   4%    Life SSD ■■■■   3%    Used BKP ■■■■  10% |
+--------------------------------------------------------------------------------------+
| SERVICE          VERNUM          CPU            MEM       BKP  HLT  CFG  RST  UPTIME |
+--------------------------------------------------------------------------------------+
| homeassistant 10.100.10001   ■■■■■■ 100%    ■■■■■■ 100%    -    -    -    0     156d |
| service2      10.100.10001   ■■■■■■  65%    ■■■■■■  11%    +    -    -    0      10y |
| service3      10.100.10001   ■■■■■■  11%    ■■■■■■  51%    +    +    -    0       1y |
| service4      10.100.10001   ■■■■■■  65%    ■■■■■■  65%    +    -    -    0       2y |
| service5      10.100.10001   ■■■■■■  51%    ■■■■■■  11%    -    +    -    0      10d |
| service6      10.100.10001   ■■■■■■  51%    ■■■■■■  11%    +    -    -    0       1h |
| service70000~ 10.100.10001   ■■■■■■  11%    ■■■■■■  65%    +    -    -    ~     100d |
| ~                        ~             ~              ~    ~    ~    ~    ~        ~ |
+======================================================================================+
*/
/* Optimised for 1 host @ 91(scaled 287)x48 Unicode
╭─┐ahosts-one~┌────────────────────────────────────────────────────────────────────┐↓ESC┌─╮
│  Used CPU ■■■■ 100%    Fail SVC ■■■■ 100%     Warn TEM ■■■■ 100%    Used SYS ■■■■ 100%  │
│  Used RAM ■■■■  39%    Fail SHR ■■■■ 100%     Revs Fan ■■■■ 100%    Used SHR ■■■■  10%  │
│  Aloc RAM ■■■■   1%    Fail BCK ■■■■   4%     Life SSD ■■■■   3%    Used BKP ■■■■  10%  │
├─────────────────────────────────────────────────────────────────────────────────────────┤
│  SERVICE          VERNUM          CPU             MEM       BKP  HLT  CFG  RST  UPTIME  │
├─────────────────────────────────────────────────────────────────────────────────────────┤
│  homeassistant 10.100.10001   ■■■■■■ 100%     ■■■■■■ 100%    -    -    -    0     156d  │
│  service2      10.100.10001   ■■■■■■  65%     ■■■■■■  11%    +    -    -    0      10y  │
│  service3      10.100.10001   ■■■■■■  11%     ■■■■■■  51%    +    +    -    0       1y  │
│  service4      10.100.10001   ■■■■■■  65%     ■■■■■■  65%    +    -    -    0       2y  │
│  service5      10.100.10001   ■■■■■■  51%     ■■■■■■  11%    -    +    -    0      10d  │
│  service6      10.100.10001   ■■■■■■  51%     ■■■■■■  11%    +    -    -    0       1h  │
│  service70000~ 10.100.10001   ■■■■■■  11%     ■■■■■■  65%    +    -    -    ~     100d  │
│  ~                        ~             ~               ~    ~    ~    ~    ~        ~  │
╰─────────────────────────────────────────────────────────────────────────────────────────╯
*/
/* Optimised for >2 hosts @ 183(scaled 287)x48 Unicode
╭─┐ahosts-one~┌────────────────────────────────────────────────────────────────────┐↑1/2┌─╮ ╭─┐ahosts-two~┌────────────────────────────────────────────────────────────────────┐↑2/2┌─╮
│  Used CPU ■■■■ 100%    Fail SVC ■■■■ 100%     Warn TEM ■■■■ 100%    Used SYS ■■■■ 100%  │ │  Used CPU ■■■■ 100%    Fail SVC ■■■■ 100%     Warn TEM ■■■■ 100%    Used SYS ■■■■ 100%  │
│  Used RAM ■■■■  39%    Fail SHR ■■■■ 100%     Revs Fan ■■■■ 100%    Used SHR ■■■■  10%  │ │  Used RAM ■■■■  39%    Fail SHR ■■■■ 100%     Revs Fan ■■■■ 100%    Used SHR ■■■■  10%  │
│  Aloc RAM ■■■■   1%    Fail BCK ■■■■   4%     Life SSD ■■■■   3%    Used BKP ■■■■  10%  │ │  Aloc RAM ■■■■   1%    Fail BCK ■■■■   4%     Life SSD ■■■■   3%    Used BKP ■■■■  10%  │
├─────────────────────────────────────────────────────────────────────────────────────────┤ ├─────────────────────────────────────────────────────────────────────────────────────────┤
│  SERVICE          VERNUM          CPU             MEM       BKP  HLT  CFG  RST  UPTIME  │ │  SERVICE          VERNUM          CPU             MEM       BKP  HLT  CFG  RST  UPTIME  │
├─────────────────────────────────────────────────────────────────────────────────────────┤ ├─────────────────────────────────────────────────────────────────────────────────────────┤
│  homeassistant 10.100.10001   ■■■■■■ 100%     ■■■■■■ 100%    -    -    -    0     156d  │ │  homeassistant 10.100.10001   ■■■■■■ 100%     ■■■■■■ 100%    -    -    -    0     156d  │
│  service2      10.100.10001   ■■■■■■  65%     ■■■■■■  11%    +    -    -    0      10y  │ │  service2      10.100.10001   ■■■■■■  65%     ■■■■■■  11%    +    -    -    0      10y  │
│  service3      10.100.10001   ■■■■■■  11%     ■■■■■■  51%    +    +    -    0       1y  │ │  service3      10.100.10001   ■■■■■■  11%     ■■■■■■  51%    +    +    -    0       1y  │
│  service4      10.100.10001   ■■■■■■  65%     ■■■■■■  65%    +    -    -    0       2y  │ │  service4      10.100.10001   ■■■■■■  65%     ■■■■■■  65%    +    -    -    0       2y  │
│  service5      10.100.10001   ■■■■■■  51%     ■■■■■■  11%    -    +    -    0      10d  │ │  service5      10.100.10001   ■■■■■■  51%     ■■■■■■  11%    -    +    -    0      10d  │
│  service6      10.100.10001   ■■■■■■  51%     ■■■■■■  11%    +    -    -    0       1h  │ │  service6      10.100.10001   ■■■■■■  51%     ■■■■■■  11%    +    -    -    0       1h  │
│  service70000~ 10.100.10001   ■■■■■■  11%     ■■■■■■  65%    +    -    -    ~     100d  │ │  service70000~ 10.100.10001   ■■■■■■  11%     ■■■■■■  65%    +    -    -    ~     100d  │
│  ~                        ~             ~               ~    ~    ~    ~    ~        ~  │ │  ~                        ~             ~               ~    ~    ~    ~    ~        ~  │
╰─────────────────────────────────────────────────────────────────────────────────────────╯ ╰─────────────────────────────────────────────────────────────────────────────────────────╯
*/
//noinspection GoSnakeCaseUsage
func relaxedDisplayLayout() [][]box {
	resizeIncHistVal := func(b *box, i int) { b.valLen += i }
	resizeIncHistLbl := func(b *box, i int) {
		b.lblMid = b.lblMid.resize(i, func(value string, length int) string {
			return pad(value, boxMid, length)
		})
	}
	resizeIncHdrRhs1 := func(b *box, i int) {
		b.lblRhs = b.lblRhs.resize(i, func(value string, length int) string {
			return extend(value, 1, length)
		})
	}
	resizeIncLblLhs1 := func(b *box, i int) {
		b.lblLhs = b.lblLhs.resize(i, func(value string, length int) string {
			return value + repeat(value, 0, 1, length-runeCount(value))
		})
	}
	resizeRemDivider := func(b *box, r int) { b.lblLhs = b.lblLhs.resize(r, divider) }

	t_0_0 := box{lblLhs: text{
		ascii:   "+- ",
		unicode: "╭─┐",
	}, lblMid: text{
		ascii:   "           ",
		unicode: "           ",
	}, lblRhs: text{
		ascii:   " --------------------------------------------------------------------+",
		unicode: "┌────────────────────────────────────────────────────────────────────╮",
	}, resizeCnt: 4, kind: boxTitle, resizeInc: resizeIncHdrRhs1}

	d_1_0 := box{lblMid: text{ascii: "Used CPU "}, valLen: 8, valSfx: "%", valKind: valHist, metricID: metric.MetricHostUsedProcessor, resizeInc: resizeIncHistVal}
	d_1_1 := box{lblMid: text{ascii: "Fail LOG "}, valLen: 8, valSfx: "%", valKind: valHist, lblLhs: text{ascii: "    "}, metricID: metric.MetricHostFailedLogs, resizeInc: resizeIncHistVal}
	d_1_2 := box{lblMid: text{ascii: "Warn TEM "}, valLen: 8, valSfx: "%", valKind: valHist, lblLhs: text{ascii: "    "}, metricID: metric.MetricHostWarnTemperatureOfMax, resizeInc: resizeIncHistVal}
	d_1_3 := box{lblMid: text{ascii: "Used SYS "}, valLen: 8, valSfx: "%", valKind: valHist, lblLhs: text{ascii: "    "}, metricID: metric.MetricHostUsedSystemSpace, resizeInc: resizeIncHistVal}

	d_2_0 := box{lblMid: text{ascii: "Used RAM "}, valLen: 8, valSfx: "%", valKind: valHist, metricID: metric.MetricHostUsedMemory, resizeInc: resizeIncHistVal}
	d_2_1 := box{lblMid: text{ascii: "Fail SHR "}, valLen: 8, valSfx: "%", valKind: valHist, lblLhs: text{ascii: "    "}, metricID: metric.MetricHostFailedShares, resizeInc: resizeIncHistVal}
	d_2_2 := box{lblMid: text{ascii: "Revs Fan "}, valLen: 8, valSfx: "%", valKind: valHist, lblLhs: text{ascii: "    "}, metricID: metric.MetricHostSpinFanSpeedOfMax, resizeInc: resizeIncHistVal}
	d_2_3 := box{lblMid: text{ascii: "Used SHR "}, valLen: 8, valSfx: "%", valKind: valHist, lblLhs: text{ascii: "    "}, metricID: metric.MetricHostUsedShareSpace, resizeInc: resizeIncHistVal}

	d_3_0 := box{lblMid: text{ascii: "Aloc RAM "}, valLen: 8, valSfx: "%", valKind: valHist, metricID: metric.MetricHostAllocatedMemory, resizeInc: resizeIncHistVal}
	d_3_1 := box{lblMid: text{ascii: "Fail BCK "}, valLen: 8, valSfx: "%", valKind: valHist, lblLhs: text{ascii: "    "}, metricID: metric.MetricHostFailedBackups, resizeInc: resizeIncHistVal}
	d_3_2 := box{lblMid: text{ascii: "Life SSD "}, valLen: 8, valSfx: "%", valKind: valHist, lblLhs: text{ascii: "    "}, metricID: metric.MetricHostLifeUsedDrives, resizeInc: resizeIncHistVal}
	d_3_3 := box{lblMid: text{ascii: "Used BKP "}, valLen: 8, valSfx: "%", valKind: valHist, lblLhs: text{ascii: "    "}, metricID: metric.MetricHostUsedBackupSpace, resizeInc: resizeIncHistVal}

	s_X_0 := box{lblLhs: text{ascii: "------------------------------------------------------------------------------------"}, kind: boxSpacr, resizeCnt: 4, resizeInc: resizeIncLblLhs1}

	l_5_0 := box{lblMid: text{ascii: "SERVICE"}, lblRhs: text{ascii: "       "}, kind: boxLabel}
	l_5_1 := box{lblMid: text{ascii: "VERNUM"}, lblLhs: text{ascii: "   "}, lblRhs: text{ascii: "   "}, kind: boxLabel}
	l_5_2 := box{lblMid: text{ascii: "CPU"}, lblLhs: text{ascii: "       "}, lblRhs: text{ascii: "    "}, kind: boxLabel, resizeCnt: 2, resizeInc: resizeIncHistLbl}
	l_5_3 := box{lblMid: text{ascii: "MEM"}, lblLhs: text{ascii: "        "}, lblRhs: text{ascii: "    "}, kind: boxLabel, resizeCnt: 2, resizeInc: resizeIncHistLbl}
	l_5_4 := box{lblMid: text{ascii: "BKP"}, lblLhs: text{ascii: "   "}, kind: boxLabel}
	l_5_5 := box{lblMid: text{ascii: "HLT"}, lblLhs: text{ascii: "  "}, kind: boxLabel}
	l_5_6 := box{lblMid: text{ascii: "CFG"}, lblLhs: text{ascii: "  "}, kind: boxLabel}
	l_5_7 := box{lblMid: text{ascii: "RST"}, lblLhs: text{ascii: "  "}, kind: boxLabel}
	l_5_8 := box{lblMid: text{ascii: "UPTIME"}, lblLhs: text{ascii: "  "}, kind: boxLabel}

	d_X_0 := box{valLen: 13, lblRhs: text{ascii: " "}, valAln: boxLhs, valOpt: true, valKind: valText, metricID: metric.MetricServiceName}
	d_X_1 := box{valLen: 12, valOpt: true, valKind: valText, metricID: metric.MetricServiceVersion}
	d_X_2 := box{lblLhs: text{ascii: "   "}, valSfx: "%", valLen: 10, valOpt: true, valKind: valHist, metricID: metric.MetricServiceUsedProcessor, resizeCnt: 2, resizeInc: resizeIncHistVal}
	d_X_3 := box{lblLhs: text{ascii: "   "}, valSfx: "%", valLen: 10, valOpt: true, valKind: valHist, metricID: metric.MetricServiceUsedMemory, resizeCnt: 2, resizeInc: resizeIncHistVal}
	d_X_4 := box{lblLhs: text{ascii: "   "}, lblRhs: text{ascii: " "}, valLen: 1, valOpt: true, valKind: valBool, metricID: metric.MetricServiceBackupStatus}
	d_X_5 := box{lblLhs: text{ascii: "   "}, lblRhs: text{ascii: " "}, valLen: 1, valOpt: true, valKind: valBool, metricID: metric.MetricServiceHealthStatus}
	d_X_6 := box{lblLhs: text{ascii: "   "}, lblRhs: text{ascii: " "}, valLen: 1, valOpt: true, valKind: valBool, metricID: metric.MetricServiceConfiguredStatus}
	d_X_7 := box{lblLhs: text{ascii: "   "}, lblRhs: text{ascii: " "}, valLen: 1, valOpt: true, metricID: metric.MetricServiceRestartCount}
	d_X_8 := box{lblLhs: text{ascii: "   "}, valLen: 4, valOpt: true, valKind: valTime, metricID: metric.MetricServiceUpTime}

	s_X_7 := box{lblLhs: text{ascii: " "}, kind: boxSpacr}

	v_X_X := box{lblLhs: text{ascii: "   "}, kind: boxDivdr}
	v_Y_Y := box{lblLhs: text{ascii: "||"}, kind: boxDivdr, resizeRem: resizeRemDivider}

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

type text struct {
	ascii   string
	unicode string
}

func (t text) pick(unicode bool) string {
	switch {
	case t.ascii == "":
		return t.unicode
	case t.unicode == "":
		return t.ascii
	case unicode:
		return t.unicode
	default:
		return t.ascii
	}
}

func (t text) resize(increment int, resizeFunc func(value string, length int) string) text {
	ascii := resizeFunc(t.ascii, increment+runeCount(t.ascii))
	unicode := resizeFunc(t.unicode, increment+runeCount(t.unicode))
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

func columns(layout [][]box, unicode bool, hostCount int) int {
	if hostCount == 0 || len(layout) == 0 {
		return 0
	}
	count := 0
	for _, b := range layout[0] {
		if b.kind != boxDivdr {
			count += b.length(unicode)
		}
		if hostCount > 1 {
			count += b.length(unicode)
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
			layout[row][col].compile(false, true)
		}
	}
	return layout
}

func (b *box) compile(unicode, force bool) {
	if b.compiled != nil && !force {
		return
	}
	if b.compiled == nil {
		b.compiled = &compiled{}
	}
	b.compiled.lblLhsLen = runeCount(b.lblLhs.pick(unicode))
	b.compiled.lblMidLen = runeCount(b.lblMid.pick(unicode))
	b.compiled.lblRhsLen = runeCount(b.lblRhs.pick(unicode))
	b.compiled.valSfxLen = runeCount(b.valSfx)
	b.compiled.valOffset = b.compiled.lblLhsLen + b.compiled.lblMidLen
	b.compiled.length = b.compiled.valOffset + b.valLen + b.compiled.lblRhsLen + b.compiled.valSfxLen
}

func (b *box) resizes() int {
	if b.resizeCnt == 0 && b.resizeInc != nil {
		return 1
	}
	return b.resizeCnt
}

func (b *box) resize(unicode bool, increment, remainder int) {
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
		b.compile(unicode, true)
	}
}

func (b *box) set(
	unicode bool,
	lblLhs text, lblLhsAln boxAlign, lblLhsLen int,
	lblMid text, lblMidAln boxAlign, lblMidLen int,
	lblRhs text, lblRhsAln boxAlign, lblRhsLen int,
) {
	lhs := pad(lblLhs.pick(unicode), lblLhsAln, lblLhsLen)
	mid := pad(lblMid.pick(unicode), lblMidAln, lblMidLen)
	rhs := pad(lblRhs.pick(unicode), lblRhsAln, lblRhsLen)
	b.lblLhs = text{lhs, lhs}
	b.lblMid = text{mid, mid}
	b.lblRhs = text{rhs, rhs}
	b.compile(unicode, true)
}

func (b *box) length(unicode bool) int {
	b.compile(unicode, false)
	return b.compiled.length
}

func (b *box) draw(display *Display, force bool) {
	if display.terminal == nil {
		return
	}
	b.compile(display.unicode, false)
	row, col := b.position.rows, b.position.cols
	draw := func(label string, length int) {
		if label != "" && force == b.valOpt {
			display.terminal.draw(col, row, label, colourDefault)
		}
		col += length
	}
	draw(b.lblLhs.pick(display.unicode), b.compiled.lblLhsLen)
	draw(b.lblMid.pick(display.unicode), b.compiled.lblMidLen)
	draw("", b.valLen)
	draw(b.lblRhs.pick(display.unicode), b.compiled.lblRhsLen)
}

func (b *box) drawLabels(display *Display) {
	b.draw(display, false)
	b.drawValue(display)
}

func (b *box) drawValue(display *Display) {
	if b.recordGUID == nil || display.terminal == nil || display.cache == nil {
		return
	}
	b.compile(display.unicode, false)
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
		symbol := textCross.pick(display.unicode)
		if record.Value.Pulse.OK {
			symbol = textTick.pick(display.unicode)
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
		bar := strings.Repeat(textBar.pick(display.unicode), filled) + strings.Repeat(" ", barWidth-filled)
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

func extend(base string, offset, length int) string {
	if length <= 0 || base == "" {
		return ""
	}
	baseRunes := []rune(base)
	if len(baseRunes) == 0 {
		return ""
	}
	if length <= len(baseRunes) {
		return string(baseRunes)
	}
	if offset < 0 {
		offset = 0
	}
	if offset >= len(baseRunes) {
		offset = len(baseRunes) - 1
	}
	insertCount := length - len(baseRunes)
	prefix := string(baseRunes[:offset])
	suffix := string(baseRunes[offset:])
	return prefix + strings.Repeat(string(baseRunes[offset]), insertCount) + suffix
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

func runeCount(value string) int {
	return utf8.RuneCountInString(value)
}
