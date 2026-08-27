package display

import (
	"context"
	"fmt"
	"log/slog"
	"slices"
	"strings"
	"supervisor/internal/config"
	"supervisor/internal/engine"
	"supervisor/internal/metric"
	"supervisor/internal/scribe"
	"sync"
	"time"

	"github.com/gdamore/tcell/v3"
	"github.com/mattn/go-runewidth"
)

type Format int

const (
	FormatAuto Format = iota
	FormatCompact
	FormatRelaxed
)

func (f Format) String() string {
	switch f {
	case FormatAuto:
		return "auto"
	case FormatCompact:
		return "compact"
	case FormatRelaxed:
		return "relaxed"
	default:
		return fmt.Sprintf("Format(%d)", int(f))
	}
}

type dimensions struct {
	rows int
	cols int
}

func (d dimensions) String() string {
	return fmt.Sprintf("[%d,%d]", d.rows, d.cols)
}

type Display struct {
	hosts           []string
	periods         config.Periods
	configPath      string
	isRemote        bool
	format          Format
	formatInit      Format
	useUnicode      bool
	dimsInit        dimensions
	dimsTerminal    dimensions
	boxes           []box
	serviceShown    []metric.ID
	maxServices     int
	dirty           dirtyBoxes
	terminal        Terminal
	factory         TerminalFactory
	cache           *metric.RecordCache
	singleHostIndex int
	refreshPeriod   time.Duration
	logBuffer       *scribe.LogBuffer
	logOverlay      bool
	logOverlayAuto  bool
	logGeneration   uint64
	logAnchor       uint64
	logNext         uint64
	logDropped      uint64
	logPaused       bool
	refreshSignal   chan struct{}
	force           bool
	tickPeriod      time.Duration
	tickStall       time.Duration
}

type dirtyBoxes struct {
	mutex      sync.Mutex
	indexes    map[int]struct{}
	generation uint64
}

func NewDisplay(
	cache *metric.RecordCache,
	factory TerminalFactory,
	hosts []string,
	width, height int,
	maxWidth, maxHeight int,
	format Format,
	useUnicode bool,
	periods config.Periods,
	isRemote bool,
	configPath string,
	logBuffer *scribe.LogBuffer,
	refreshPeriod time.Duration,
) (*Display, error) {
	initStart := time.Now()
	display := &Display{
		hosts:           hosts,
		dimsInit:        dimensions{rows: height, cols: width},
		dimsTerminal:    dimensions{rows: maxHeight, cols: maxWidth},
		useUnicode:      useUnicode,
		periods:         periods,
		configPath:      configPath,
		isRemote:        isRemote,
		format:          format,
		formatInit:      format,
		factory:         factory,
		cache:           cache,
		logBuffer:       logBuffer,
		refreshPeriod:   refreshPeriod,
		refreshSignal:   make(chan struct{}, 1),
		tickPeriod:      tickPeriod,
		tickStall:       tickStall,
		singleHostIndex: singleHostIndex(hosts),
	}
	scribe.Log(scribe.SourceDisplay, scribe.SubjectNone, scribe.ActionDiscover).Info("geometry", initStart, "layout [%v], rows [%d], cols [%d]", format, height, width)
	return display, nil
}

func singleHostIndex(hosts []string) int {
	if len(hosts) == 1 {
		return 0
	}
	return -1
}

func (d *Display) Close() {
	if d.terminal != nil {
		d.terminal.close()
	}
}

func (d *Display) compileHosts() []string {
	if d.singleHostIndex >= 0 && d.singleHostIndex < len(d.hosts) {
		return []string{d.hosts[d.singleHostIndex]}
	}
	return d.hosts
}

func (d *Display) Compile() (Format, error) {
	compileStart := time.Now()
	compileHosts := d.compileHosts()
	hostCount := len(compileHosts)
	compile := func(format Format, layout [][]box) ([]box, error) {

		displayRowMin := 0
		if len(layout) < 2 || len(layout[0]) < 2 {
			return nil, fmt.Errorf("cannot compile display: layout is empty")
		}
		if hostCount < 1 {
			return nil, fmt.Errorf("cannot compile display: no hosts")
		}

		displayRowMin = len(layout) * ((hostCount + 1) / 2)
		if displayRowMin <= 0 {
			return nil, fmt.Errorf("cannot compile display: "+
				"invalid minimum rows [%d] for format [%s]", displayRowMin, format)
		}
		if d.dimsInit.rows < displayRowMin {
			return nil, fmt.Errorf("cannot compile display: "+
				"minimum [%d] rows required for [%d] hosts, only [%d] available for format [%s]",
				displayRowMin, hostCount, d.dimsInit.rows, format)
		}
		addLayoutRowsCount := (d.dimsInit.rows - displayRowMin) / ((hostCount + 1) / 2)
		penultimateRow := layout[len(layout)-2]
		for range addLayoutRowsCount {
			newRow := make([]box, len(penultimateRow))
			for j := range penultimateRow {
				newRow[j] = *penultimateRow[j].clone()
			}
			lastRow := layout[len(layout)-1]
			layout = append(layout[:len(layout)-1], newRow, lastRow)
		}

		displayColMin := 0
		displayResizeCount := 0
		displayBoxSkip := func(i int, b box) bool { return (hostCount == 1 || (i+1)%2 == 0) && b.kind == boxDivdr }
		for hostIndex := range compileHosts {
			hostColMin := 0
			hostResizeCount := 0
			for layoutRowIndex, layoutRow := range layout {
				rowCols := 0
				rowResizeCount := 0
				for _, layoutBox := range layoutRow {
					if !displayBoxSkip(hostIndex, layoutBox) {
						rowCols += layoutBox.length(d.useUnicode)
						rowResizeCount += layoutBox.resizes()
					}
				}
				if hostColMin == 0 {
					hostColMin = rowCols
				} else if rowCols != hostColMin {
					return nil, fmt.Errorf("cannot compile display: "+
						"pre-resize row column width must be [%d], but got [%d] in zero-indexed row [%d] of layout [%v]",
						hostColMin, rowCols, layoutRowIndex, format)
				}
				if rowResizeCount < 1 {
					return nil, fmt.Errorf("cannot compile display: "+
						"no box resize functions set in zero-indexed row [%d] of layout [%v]", layoutRowIndex, format)
				}
				if hostResizeCount == 0 {
					hostResizeCount = rowResizeCount
				} else if rowResizeCount != hostResizeCount {
					return nil, fmt.Errorf("cannot compile display: "+
						"the number of box resize functions per row must be [%d], but got [%d] in zero-indexed row [%d] of layout [%v]",
						hostResizeCount, rowResizeCount, layoutRowIndex, format)
				}
			}
			if hostIndex < 2 {
				displayColMin += hostColMin
				displayResizeCount += hostResizeCount
			}
		}
		if displayResizeCount == 0 {
			return nil, fmt.Errorf("cannot compile display: "+
				"no box resize functions set layout [%v]", format)
		}
		displayResizeIncrement := (d.dimsInit.cols - displayColMin) / displayResizeCount
		displayResizeRemainder := (d.dimsInit.cols - displayColMin) % displayResizeCount

		boxesColsCount := 0
		boxes := make([]box, 0, hostCount*50)
		hostServiceIndex := make([]int, len(compileHosts))
		for i := range hostServiceIndex {
			hostServiceIndex[i] = metric.ServiceIndexUnset
		}
		for hostRowIndex := 0; hostRowIndex < (hostCount+1)/2; hostRowIndex++ {
			for layoutRowIndex, layoutRow := range layout {
				rowColsCount := 0
				if len(layoutRow) < 1 ||
					layoutRow[0].kind == boxDivdr {
					return nil, fmt.Errorf("cannot compile display: "+
						"row starts with [cline] in zero-indexed row [%d] of layout [%v]", layoutRowIndex, format)
				}
				if len(layoutRow) < 2 ||
					layoutRow[len(layoutRow)-1].kind != boxDivdr {
					return nil, fmt.Errorf("cannot compile display: "+
						"row is not terminated by at least one [cline] in zero-indexed row [%d] of layout [%v]",
						layoutRowIndex, format)
				}
				for hostColIndex := range 2 {
					hostIndex := hostRowIndex*2 + hostColIndex
					if hostIndex >= hostCount {
						continue
					}
					hostName := compileHosts[hostIndex]
					for _, layoutBox := range layoutRow {
						if displayBoxSkip(hostIndex, layoutBox) {
							continue
						}
						b := layoutBox.clone()
						if b.kind == boxDatum && (b.metricID < metric.ID(0) || b.metricID >= metric.MetricMax) {
							return nil, fmt.Errorf("cannot compile display: "+
								"invalid metricID ID [%v] in zero-indexed row [%d] of layout [%v]", layoutRow, b.metricID, format)
						}
						if b.kind == boxDatum && b.valLen < 1 {
							return nil, fmt.Errorf("cannot compile display: "+
								"invalid value columns [%d] in zero-indexed row [%d] of layout [%v]", b.valLen, b.metricID, format)
						}
						if b.kind == boxTitle {
							b.set(
								d.useUnicode,
								b.lblLhs, boxLhs, runewidth.StringWidth(b.lblLhs.pick(d.useUnicode)),
								text{hostName, hostName}, boxLhs, runewidth.StringWidth(b.lblMid.pick(d.useUnicode)),
								b.lblRhs, boxLhs, runewidth.StringWidth(b.lblRhs.pick(d.useUnicode)),
							)
						} else if b.kind == boxCtrls {
							var ctrlText text
							if d.singleHostIndex >= 0 {
								ctrlText = text{
									ascii:   fmt.Sprintf("%sESC", textDown.ascii),
									unicode: fmt.Sprintf("%sESC", textDown.unicode),
								}
							} else {
								actualHostIndex := hostRowIndex*2 + hostColIndex
								ctrlText = text{
									ascii:   fmt.Sprintf("%s%d/%d", textUp.ascii, actualHostIndex+1, len(d.hosts)),
									unicode: fmt.Sprintf("%s%d/%d", textUp.unicode, actualHostIndex+1, len(d.hosts)),
								}
							}
							b.set(
								d.useUnicode,
								b.lblLhs, boxLhs, runewidth.StringWidth(b.lblLhs.pick(d.useUnicode)),
								ctrlText, boxLhs, runewidth.StringWidth(b.lblMid.pick(d.useUnicode)),
								b.lblRhs, boxLhs, runewidth.StringWidth(b.lblRhs.pick(d.useUnicode)),
							)
						}
						if b.metricID == metric.MetricServiceName {
							hostServiceIndex[hostIndex]++
						}
						if b.kind == boxDatum && b.valLen > 0 {
							recordGUID := metric.NewServiceSchemaRecordGUID(b.metricID, hostName, hostServiceIndex[hostIndex])
							b.recordGUID = &recordGUID
						}
						b.position = &dimensions{layoutRowIndex + hostRowIndex*(len(layout)), rowColsCount}
						b.resize(d.useUnicode, displayResizeIncrement, displayResizeRemainder, hostCount)
						rowColsCount += b.length(d.useUnicode)
						boxes = append(boxes, *b)
					}
				}
				if hostCount == 1 || hostRowIndex*2+1 < hostCount {
					if boxesColsCount == 0 {
						boxesColsCount = rowColsCount
					} else if rowColsCount != boxesColsCount {
						return nil, fmt.Errorf("cannot compile display: "+
							"post-resize, row column width must be [%d], but got [%d] in layout zero-indexed row [%d] and [%v]",
							boxesColsCount, rowColsCount, layoutRowIndex, format)
					}
				}
			}
		}

		if len(boxes) > 0 {
			rowWidth := 0
			expectedCol := 0
			expectedRow := -1
			positioningErr := fmt.Errorf("cannot compile display: invalid box positioning in layout [%v]", format)
			for _, b := range boxes {
				if b.position == nil {
					return nil, positioningErr
				}
				if expectedRow == -1 {
					expectedRow = b.position.rows
				}
				if b.position.rows < expectedRow {
					return nil, positioningErr
				}
				if b.position.rows != expectedRow {
					expectedRow = b.position.rows
					expectedCol = 0
					rowWidth = 0
				}
				if b.position.cols != expectedCol {
					return nil, positioningErr
				}
				length := b.length(d.useUnicode)
				expectedCol += length
				rowWidth += length
			}
		}

		return boxes, nil
	}
	var layout [][]box
	for {
		var attemptedFormat Format
		switch d.format {
		case FormatAuto, FormatRelaxed:
			attemptedFormat = FormatRelaxed
			layout = relaxedDisplayLayout(d.useUnicode)
		case FormatCompact:
			attemptedFormat = FormatCompact
			layout = compactDisplayLayout(d.useUnicode)
		default:
			return d.format, fmt.Errorf("cannot compile display: invalid formats [%v]", d.format)
		}
		boxes, err := compile(attemptedFormat, layout)
		if err == nil {
			d.boxes = boxes
			d.serviceShown = shownServiceMetrics(boxes)
			serviceSlots := 0
			if len(compileHosts) > 0 {
				for _, b := range boxes {
					if b.metricID == metric.MetricServiceName && b.recordGUID != nil && b.recordGUID.Host == compileHosts[0] {
						serviceSlots++
					}
				}
			}
			d.maxServices = serviceSlots
			if serviceSlots > 0 {
				lastIdx := serviceSlots - 1
				for i := range d.boxes {
					if d.boxes[i].recordGUID != nil && d.boxes[i].recordGUID.ServiceIndex == lastIdx {
						d.boxes[i].isLast = true
					}
				}
			}
			scribe.Log(scribe.SourceDisplay, scribe.SubjectNone, scribe.ActionDiscover).Info("geometry", compileStart, "layout [%v], rows [%d], cols [%d]", attemptedFormat, d.dimsInit.rows, d.dimsInit.cols)
			return attemptedFormat, nil
		}
		if d.format == FormatCompact {
			return d.format, err
		}
		if d.format == FormatRelaxed {
			scribe.Log(scribe.SourceDisplay, scribe.SubjectNone, scribe.ActionDiscover).Warn("fallback", compileStart, "[compact], relaxed layout failed with [%v]", err)
		}
		d.format = FormatCompact
	}
}

func (d *Display) Load() error {
	if len(d.hosts) < 1 {
		return fmt.Errorf("cannot load display: no hosts")
	}
	if d.terminal == nil {
		if d.factory == nil {
			return fmt.Errorf("cannot draw display: terminal factory is nil")
		}
		terminal, err := d.factory(d.useUnicode)
		if err != nil {
			return err
		}
		d.terminal = terminal
	}
	d.subscribeUpdates()
	d.cache.SubscribeRefresh(d)
	return nil
}

func (d *Display) MarkRefresh() {
	if d == nil || d.refreshSignal == nil {
		return
	}
	select {
	case d.refreshSignal <- struct{}{}:
	default:
	}
}

func (d *Display) Run(ctx context.Context) {
	if d.isRemote || len(d.hosts) > 1 {
		engine.RunListeningStreamLoop(ctx, d.configPath, d.cache, d.periods)
	} else {
		engine.RunListeningProbesLoop(ctx, d.configPath, d.cache, d.periods)
	}
}

func (d *Display) Logging() {
	if d.logBuffer == nil || d.terminal == nil {
		return
	}
	maxLines := d.dimsInit.rows
	if maxLines < 1 {
		return
	}
	clip := func(text string) string {
		if runewidth.StringWidth(text) <= d.dimsInit.cols {
			return text
		}
		tail := ""
		if d.dimsInit.cols >= 2 {
			tail = "~"
		}
		return runewidth.Truncate(text, d.dimsInit.cols, tail)
	}
	capacity := maxLines - 2
	rows, consumed, anchor := d.paged(capacity)
	d.logDropped = anchor - min(anchor, d.logAnchor)
	d.logAnchor = anchor
	d.logNext = anchor + uint64(consumed)
	d.logPaused = d.logBuffer.Version() > d.logNext
	d.drawOverlayBar()
	d.terminal.draw(0, 1, clip(scribe.OverlayHeader()), colourChat)
	for row, line := range rows {
		row += 2
		c := colourChat
		switch {
		case line.level >= slog.LevelError:
			c = colourAlert
		case line.level >= slog.LevelWarn:
			c = colourWarn
		case line.level >= slog.LevelInfo:
			c = colourCheer
		}
		d.terminal.draw(0, row, clip(line.text), c)
	}
}

func (d *Display) Draw(ctx context.Context, cancel context.CancelFunc) {
	for _, b := range d.boxes {
		b.drawLabels(d)
	}
	ticker := time.NewTicker(d.tickPeriod)
	defer ticker.Stop()
	ticked := config.NowIncludingSuspend()
	var refreshC <-chan time.Time
	if d.refreshPeriod > 0 {
		refreshTicker := time.NewTicker(d.refreshPeriod)
		defer refreshTicker.Stop()
		refreshC = refreshTicker.C
	}
	for {
		select {
		case <-ctx.Done():
			return
		case <-refreshC:
			d.refresh("period")
		case <-d.refreshSignal:
			d.refresh("stream")
		case event, ok := <-d.terminal.events():
			if !ok {
				return
			}
			switch ev := event.(type) {
			case *tcell.EventResize:
				resizeStart := time.Now()
				cols, rows := ev.Size()
				if d.dimsTerminal.cols > 0 && cols > d.dimsTerminal.cols {
					cols = d.dimsTerminal.cols
				}
				if d.dimsTerminal.rows > 0 && rows > d.dimsTerminal.rows {
					rows = d.dimsTerminal.rows
				}
				dims := dimensions{rows: rows, cols: cols}
				if dims == d.dimsInit {
					continue
				}
				d.dimsInit = dims
				if d.logOverlay {
					d.logRewind()
				}
				d.rebuild("resize")
				scribe.Log(scribe.SourceDisplay, scribe.SubjectNone, scribe.ActionRender).Info("geometry", resizeStart, "[%d] cols, [%d] rows", cols, rows)
			case *tcell.EventKey:
				if ev.Key() == tcell.KeyCtrlC {
					cancel()
					return
				}
				if ev.Key() == tcell.KeyCtrlR {
					if d.logOverlay {
						d.logRewind()
					}
					d.refresh("manual")
				}
				if ev.Key() == tcell.KeyEscape {
					if d.singleHostIndex >= 0 && len(d.hosts) > 1 {
						d.singleHostIndex = -1
						d.rebuild("select")
					} else if d.logBuffer != nil {
						d.logOverlay = !d.logOverlay
						d.logOverlayAuto = false
						if d.logOverlay {
							d.logRewind()
						}
						d.refresh("toggle")
					}
				}
				if d.logOverlay && ev.Str() == " " {
					if d.logPaused {
						d.logAnchor = d.logNext
					}
					d.logRepaint()
				}
				if !d.logOverlay && len(d.hosts) > 1 && ev.Key() == tcell.KeyRune {
					hostIndex := -1
					r := ev.Str()
					if len(r) == 1 && r[0] >= '1' && r[0] <= '9' {
						hostIndex = int(r[0] - '1')
					}
					if hostIndex >= 0 && hostIndex < len(d.hosts) {
						if d.singleHostIndex >= 0 {
							if hostIndex == d.singleHostIndex {
								d.singleHostIndex = -1
							}
						} else {
							d.singleHostIndex = hostIndex
						}
						d.rebuild("select")
					}
				}
			}
		case <-ticker.C:
			if elapsed := config.SinceIncludingSuspend(ticked); elapsed > d.tickStall {
				scribe.Log(scribe.SourceDisplay, scribe.SubjectNone, scribe.ActionDisconnect).Warn("exceeded", ticked, "[%d] ms since the last draw tick", d.tickStall.Milliseconds())
				d.cache.Wake(elapsed)
				d.refresh("wake")
			}
			ticked = config.NowIncludingSuspend()
			drawStart := time.Now()
			dirtyIndexes := d.takeDirtyIndexes()
			drawnCount := 0
			if d.logOverlay {
				if d.logBuffer != nil && !d.logPaused && d.logBuffer.Version() != d.logGeneration {
					d.logRepaint()
				}
			} else if d.force || len(dirtyIndexes) > 0 {
				drawnCount = len(dirtyIndexes)
				if d.force {
					drawnCount = len(d.boxes)
					for i := range d.boxes {
						d.boxes[i].drawValue(d)
					}
				} else {
					for _, index := range dirtyIndexes {
						if index < len(d.boxes) {
							d.boxes[index].drawValue(d)
						}
					}
				}
				d.terminal.show()
			}
			if len(dirtyIndexes) > 0 || drawnCount > 0 {
				scribe.Log(scribe.SourceDisplay, scribe.SubjectNone, scribe.ActionRender).Debug("received", drawStart, "[%3d] updates, drawn [%3d] boxes", len(dirtyIndexes), drawnCount)
			}
			d.force = false
		}
	}
}

func (d *Display) rebuild(trigger string) {
	rebuildStart := time.Now()
	d.format = d.formatInit
	d.boxes = nil
	d.serviceShown = nil
	if _, err := d.Compile(); err != nil {
		scribe.Log(scribe.SourceDisplay, scribe.SubjectNone, scribe.ActionRender).Error("faulting", rebuildStart, "[%v] rebuilding the display", err)
		if !d.logOverlay {
			d.logRewind()
		}
		d.logOverlay = true
		d.logOverlayAuto = true
	} else if d.logOverlayAuto {
		d.logOverlay = false
		d.logOverlayAuto = false
	}
	d.refresh(trigger)
}

func (d *Display) refresh(trigger string) {
	refreshStart := time.Now()
	d.subscribeUpdates()
	d.terminal.sync()
	d.terminal.clear()
	if d.logOverlay {
		d.Logging()
	} else {
		for _, b := range d.boxes {
			b.drawLabels(d)
		}
	}
	d.terminal.show()
	d.force = true
	if trigger == "period" {
		scribe.Log(scribe.SourceDisplay, scribe.SubjectNone, scribe.ActionRender).Debug("triggers", refreshStart, "[%s], refreshed [%4d] boxes", trigger, len(d.boxes))
		return
	}
	scribe.Log(scribe.SourceDisplay, scribe.SubjectNone, scribe.ActionRender).Info("triggers", refreshStart, "[%s], refreshed [%4d] boxes", trigger, len(d.boxes))
}

func (d *Display) subscribeUpdates() {
	d.cache.ClearUpdateListeners()
	d.dirty.mutex.Lock()
	d.dirty.generation++
	d.dirty.indexes = make(map[int]struct{}, len(d.boxes))
	gen := d.dirty.generation
	d.dirty.mutex.Unlock()
	runStateInputs := []metric.ID{metric.MetricServiceName, metric.MetricServiceHealthStatus, metric.MetricServiceConfiguredStatus}
	for i := range d.boxes {
		guid := d.boxes[i].recordGUID
		if guid == nil {
			continue
		}
		listener := &boxListener{i, gen, d}
		d.cache.SubscribeUpdates(*guid, listener)
		if metric.GetIDKind(guid.ID) == metric.MetricKindService {
			for _, id := range runStateInputs {
				if id == guid.ID {
					continue
				}
				input := *guid
				input.ID = id
				d.cache.SubscribeUpdates(input, listener)
			}
		}
	}
}

func (d *Display) markDirty(index int, generation uint64) {
	d.dirty.mutex.Lock()
	if generation == d.dirty.generation {
		d.dirty.indexes[index] = struct{}{}
	}
	d.dirty.mutex.Unlock()
}

func (d *Display) takeDirtyIndexes() []int {
	d.dirty.mutex.Lock()
	if len(d.dirty.indexes) == 0 {
		d.dirty.mutex.Unlock()
		return nil
	}
	indexes := make([]int, 0, len(d.dirty.indexes))
	for index := range d.dirty.indexes {
		indexes = append(indexes, index)
	}
	d.dirty.indexes = make(map[int]struct{}, len(indexes))
	d.dirty.mutex.Unlock()
	return indexes
}

type boxListener struct {
	index      int
	generation uint64
	display    *Display
}

func (l *boxListener) MarkDirty() {
	l.display.markDirty(l.index, l.generation)
}

const (
	tickPeriod = 250 * time.Millisecond
	tickStall  = 5 * time.Second
)

func (d *Display) paged(capacity int) ([]overlayRow, int, uint64) {
	if capacity < 1 {
		return nil, 0, d.logBuffer.Version()
	}
	lines, anchor := d.logBuffer.From(d.logAnchor, capacity)
	var rows []overlayRow
	consumed := 0
	for _, line := range lines {
		texts := scribe.OverlayLines(line, d.dimsInit.cols)
		if len(rows) > 0 && len(rows)+len(texts) > capacity {
			break
		}
		for _, text := range texts {
			rows = append(rows, overlayRow{text: text, level: line.Level})
		}
		consumed++
		if len(rows) >= capacity {
			break
		}
	}
	if len(rows) > capacity {
		rows = rows[:capacity]
	}
	return rows, consumed, anchor
}

func (d *Display) drawOverlayBar() {
	arrow := " " + textDown.ascii
	esc := "ESC"
	suffix := " =+"
	status := ""
	if d.logPaused {
		status = fmt.Sprintf(" PAUSED %d/%d SPACE", d.logNext-d.logBuffer.Oldest(), d.logBuffer.Version()-d.logBuffer.Oldest())
	}
	if d.logDropped > 0 {
		status = fmt.Sprintf(" DROPPED %d%s", d.logDropped, status)
	}
	statusWidth := runewidth.StringWidth(status)
	arrowWidth := runewidth.StringWidth(arrow)
	escWidth := runewidth.StringWidth(esc)
	suffixWidth := runewidth.StringWidth(suffix)
	padLen := max(d.dimsInit.cols-statusWidth-arrowWidth-escWidth-suffixWidth, 0)
	d.terminal.draw(0, 0, strings.Repeat("=", padLen), colourChat)
	d.terminal.draw(padLen, 0, status, colourWarn)
	d.terminal.draw(padLen+statusWidth, 0, arrow, colourChat)
	d.terminal.draw(padLen+statusWidth+arrowWidth, 0, esc, colourShout)
	d.terminal.draw(padLen+statusWidth+arrowWidth+escWidth, 0, suffix, colourChat)
}

func (d *Display) logRewind() {
	if d.logBuffer == nil {
		return
	}
	capacity := max(d.dimsInit.rows-2, 1)
	lines, start := d.logBuffer.From(d.logBuffer.Rewind(capacity), capacity)
	used, kept := 0, 0
	for _, line := range slices.Backward(lines) {
		height := len(scribe.OverlayLines(line, d.dimsInit.cols))
		if kept > 0 && used+height > capacity {
			break
		}
		used += height
		kept++
	}
	d.logAnchor = start + uint64(len(lines)-kept)
	d.logDropped = 0
	d.logPaused = false
}

func (d *Display) logRepaint() {
	if d.logBuffer == nil || d.terminal == nil {
		return
	}
	d.logGeneration = d.logBuffer.Version()
	d.terminal.clear()
	d.Logging()
	d.terminal.show()
}

type overlayRow struct {
	text  string
	level slog.Level
}

const (
	surfaceTerminal = "terminal"
	surfaceGrid     = "grid"
	surfaceLayout   = "layout"
)
