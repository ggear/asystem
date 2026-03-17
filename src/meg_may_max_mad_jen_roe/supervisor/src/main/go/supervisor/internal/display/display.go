package display

import (
	"context"
	"fmt"
	"log/slog"
	"supervisor/internal/config"
	"supervisor/internal/engine"
	"supervisor/internal/metric"
	"supervisor/internal/scribe"
	"sync"
	"time"
	"unicode/utf8"

	"github.com/gdamore/tcell/v3"
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
	hosts         []string
	periods       config.Periods
	configPath    string
	isRemote      bool
	format        Format
	formatInit    Format
	symbols       Symbols
	dimsInit      dimensions
	dimsTerminal  dimensions
	maxServices   int
	boxes         []box
	dirty         dirtyBoxes
	terminal      Terminal
	factory       terminalFactory
	cache         *metric.RecordCache
	logBuffer     *scribe.LogBuffer
	logOverlay    bool
	logGeneration uint64
	refreshPeriod time.Duration
}

type dirtyBoxes struct {
	mutex      sync.Mutex
	indexes    map[int]struct{}
	generation uint64
}

func NewDisplay(
	cache *metric.RecordCache,
	factory terminalFactory,
	hosts []string,
	width, height int,
	maxWidth, maxHeight int,
	format Format,
	symbols Symbols,
	periods config.Periods,
	isRemote bool,
	configPath string,
	logBuffer *scribe.LogBuffer,
	refreshPeriod time.Duration,
) (*Display, error) {
	return &Display{
		hosts:         hosts,
		dimsInit:      dimensions{rows: height, cols: width},
		dimsTerminal:  dimensions{rows: maxHeight, cols: maxWidth},
		symbols:       symbols,
		periods:       periods,
		configPath:    configPath,
		isRemote:      isRemote,
		format:        format,
		formatInit:    format,
		factory:       factory,
		cache:         cache,
		logBuffer:     logBuffer,
		refreshPeriod: refreshPeriod,
	}, nil
}

func (d *Display) Close() {
	if d.terminal != nil {
		d.terminal.close()
	}
}

func (d *Display) Compile() (Format, error) {
	hostCount := len(d.hosts)
	compile := func(format Format, layout [][]box) ([]box, error) {

		// Assert and resize layout box rows
		displayRowMin := 0
		displayRowSkip := 0
		if len(layout) < 2 || len(layout[0]) < 4 {
			return nil, fmt.Errorf("cannot compile display: layout is empty")
		}
		if hostCount < 1 {
			return nil, fmt.Errorf("cannot compile display: no hosts")
		} else if hostCount == 1 {
			displayRowSkip = 1
			displayRowMin = len(layout) - 1
		} else {
			displayRowMin = len(layout) * ((hostCount + 1) / 2)
		}
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
		lastRow := layout[len(layout)-1]
		for i := 0; i < addLayoutRowsCount; i++ {
			newRow := make([]box, len(lastRow))
			for j := range lastRow {
				newRow[j] = *lastRow[j].clone()
			}
			layout = append(layout, newRow)
		}
		d.maxServices = displayRowMin + addLayoutRowsCount

		// Assert and resize layout box columns
		displayColMin := 0
		displayResizeCount := 0
		displayBoxSkip := func(i int, b box) bool { return (hostCount == 1 || (i+1)%2 == 0) && b.kind == boxDivdr }
		for hostIndex := range d.hosts {
			hostColMin := 0
			hostResizeCount := 0
			for layoutRowIndex, layoutRow := range layout {
				if layoutRowIndex >= displayRowSkip {
					rowCols := 0
					rowResizeCount := 0
					for _, layoutBox := range layoutRow {
						if !displayBoxSkip(hostIndex, layoutBox) {
							rowCols += layoutBox.length()
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

		// Build, resize, assert and compile display boxes
		boxesColsCount := 0
		boxes := make([]box, 0, hostCount*50)
		hostServiceIndex := make([]int, len(d.hosts))
		for i := range hostServiceIndex {
			hostServiceIndex[i] = metric.ServiceIndexUnset
		}
		for hostRowIndex := 0; hostRowIndex < (hostCount+1)/2; hostRowIndex++ {
			for layoutRowIndex, layoutRow := range layout {
				if layoutRowIndex >= displayRowSkip {
					rowColsCount := 0
					if len(layoutRow) < 1 ||
						layoutRow[0].kind == boxDivdr {
						return nil, fmt.Errorf("cannot compile display: "+
							"row starts with [cline] in zero-indexed row [%d] of layout [%v]", layoutRowIndex, format)
					}
					if len(layoutRow) < 3 ||
						layoutRow[len(layoutRow)-1].kind != boxDivdr ||
						layoutRow[len(layoutRow)-2].kind != boxDivdr ||
						layoutRow[len(layoutRow)-3].kind != boxDivdr {
						return nil, fmt.Errorf("cannot compile display: "+
							"row is not terminated by [3 x cline] in zero-indexed row [%d] of layout [%v]",
							layoutRowIndex, format)
					}
					for hostColIndex := 0; hostColIndex < 2; hostColIndex++ {
						hostIndex := hostRowIndex*2 + hostColIndex
						if hostIndex >= hostCount {
							continue
						}
						hostName := d.hosts[hostIndex]
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
									b.lblLhs, boxLhs, utf8.RuneCountInString(b.lblLhs),
									hostName, boxLhs, utf8.RuneCountInString(b.lblMid),
									b.lblRhs, boxLhs, utf8.RuneCountInString(b.lblRhs),
								)
							}
							if b.metricID == metric.MetricServiceName {
								hostServiceIndex[hostIndex]++
							}
							recordGUID := metric.NewServiceSchemaRecordGUID(b.metricID, hostName, hostServiceIndex[hostIndex])
							b.recordGUID = &recordGUID
							b.position = &dimensions{layoutRowIndex - displayRowSkip + hostRowIndex*(len(layout)-displayRowSkip), rowColsCount}
							b.resize(displayResizeIncrement, displayResizeRemainder)
							rowColsCount += b.length()
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
		}

		// Assert display boxes positions and lengths
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
				length := b.length()
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
			layout = relaxedDisplayLayout()
		case FormatCompact:
			attemptedFormat = FormatCompact
			layout = compactDisplayLayout()
		default:
			return d.format, fmt.Errorf("cannot compile display: invalid formats [%v]", d.format)
		}
		boxes, err := compile(attemptedFormat, layout)
		if err == nil {
			d.boxes = boxes
			return attemptedFormat, nil
		}
		if d.format == FormatCompact {
			return d.format, err
		}
		if d.format == FormatRelaxed {
			slog.Debug("layout relaxed compilation failed, fallback to compact", "error", err)
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
		terminal, err := d.factory()
		if err != nil {
			return err
		}
		d.terminal = terminal
	}
	d.subscribeUpdates()
	return nil
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
	lines := d.logBuffer.Tail(maxLines)
	for row, line := range lines {
		ts := line.Time.Format("15:04:05")
		lvl := line.Level.String()
		text := fmt.Sprintf("%s %-5s %s", ts, lvl, line.Message)
		runes := []rune(text)
		if len(runes) > d.dimsInit.cols {
			if d.dimsInit.cols >= 2 {
				runes = append(runes[:d.dimsInit.cols-1], '~')
			} else {
				runes = runes[:d.dimsInit.cols]
			}
			text = string(runes)
		}
		c := colourDefault
		switch {
		case line.Level >= slog.LevelError:
			c = colourRed
		case line.Level >= slog.LevelWarn:
			c = colourBlue
		case line.Level >= slog.LevelInfo:
			c = colourGreen
		}
		d.terminal.draw(0, row, text, c)
	}
}

func (d *Display) Draw(ctx context.Context, cancel context.CancelFunc) {
	for _, b := range d.boxes {
		b.drawLabels(d)
	}
	ticker := time.NewTicker(250 * time.Millisecond)
	defer ticker.Stop()
	var refreshC <-chan time.Time
	if d.refreshPeriod > 0 {
		refreshTicker := time.NewTicker(d.refreshPeriod)
		defer refreshTicker.Stop()
		refreshC = refreshTicker.C
	}
	var force bool
	for {
		select {
		case <-ctx.Done():
			return
		case <-refreshC:
			refreshStart := time.Now()
			d.terminal.sync()
			d.terminal.clear()
			if d.logOverlay {
				d.Logging()
			} else {
				for _, b := range d.boxes {
					b.drawLabels(d)
				}
			}
			force = true
			slog.Debug("profiling", "engine", "display", "phase", "refresh", "duration", time.Since(refreshStart).Truncate(time.Millisecond))
		case <-d.cache.Updates():
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
				d.format = d.formatInit
				d.boxes = nil
				if _, err := d.Compile(); err != nil {
					slog.Error("resize recompile failed", "error", err)
				} else {
					d.subscribeUpdates()
				}
				d.terminal.sync()
				d.terminal.clear()
				if d.logOverlay {
					d.Logging()
				} else {
					for _, b := range d.boxes {
						b.drawLabels(d)
					}
				}
				force = true
				slog.Debug("profiling", "engine", "display", "phase", "resize", "duration", time.Since(resizeStart).Truncate(time.Millisecond), "cols", cols, "rows", rows)
			case *tcell.EventKey:
				if ev.Key() == tcell.KeyCtrlC {
					cancel()
					return
				}
				if ev.Key() == tcell.KeyCtrlR {
					refreshStart := time.Now()
					d.terminal.sync()
					d.terminal.clear()
					if d.logOverlay {
						d.Logging()
					} else {
						for _, b := range d.boxes {
							b.drawLabels(d)
						}
					}
					force = true
					slog.Debug("profiling", "engine", "display", "phase", "refresh", "duration", time.Since(refreshStart).Truncate(time.Millisecond))
				}
				if ev.Key() == tcell.KeyEscape && d.logBuffer != nil {
					d.logOverlay = !d.logOverlay
					d.terminal.clear()
					if d.logOverlay {
						d.Logging()
					} else {
						for _, b := range d.boxes {
							b.drawLabels(d)
						}
						force = true
					}
					d.terminal.show()
				}
			}
		case <-ticker.C:
			if d.logOverlay {
				if d.logBuffer != nil {
					v := d.logBuffer.Version()
					if v != d.logGeneration {
						d.logGeneration = v
						d.terminal.clear()
						d.Logging()
						d.terminal.show()
					}
				}
				force = false
				continue
			}
			dirtyIndexes := d.takeDirtyIndexes()
			if !force && len(dirtyIndexes) == 0 {
				continue
			}
			drawStart := time.Now()
			drawnCount := len(dirtyIndexes)
			if force {
				drawnCount = len(d.boxes)
				for i := range d.boxes {
					d.boxes[i].drawValue(d)
				}
			} else {
				for _, index := range dirtyIndexes {
					d.boxes[index].drawValue(d)
				}
			}
			d.terminal.show()
			slog.Debug("profiling", "engine", "display", "phase", "draw", "duration", time.Since(drawStart).Truncate(time.Millisecond), "boxes", drawnCount)
			force = false
		}
	}
}

func (d *Display) subscribeUpdates() {
	d.cache.ClearUpdateListeners()
	d.dirty.mutex.Lock()
	d.dirty.generation++
	d.dirty.indexes = make(map[int]struct{}, len(d.boxes))
	gen := d.dirty.generation
	d.dirty.mutex.Unlock()
	for i := range d.boxes {
		if d.boxes[i].recordGUID != nil {
			d.cache.SubscribeUpdates(*d.boxes[i].recordGUID, &boxListener{i, gen, d})
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
