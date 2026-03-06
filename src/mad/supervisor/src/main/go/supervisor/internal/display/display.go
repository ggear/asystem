package display

import (
	"fmt"
	"log/slog"
	"sort"
	"supervisor/internal/config"
	"supervisor/internal/engine"
	"supervisor/internal/metric"
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
	hosts       []string
	periods     config.Periods
	isRemote    bool
	format      Format
	dimensions  dimensions
	maxServices int
	boxes       []box
	dirty       dirtyBoxes
	terminal    Terminal
	factory     terminalFactory
	cache       *metric.RecordCache
}

type dirtyBoxes struct {
	mutex   sync.Mutex
	indexes map[int]struct{}
}

func NewDisplay(cache *metric.RecordCache, factory terminalFactory, hosts []string, width, height int, format Format, periods config.Periods, isRemote bool) (*Display, error) {
	return &Display{
		hosts:      hosts,
		dimensions: dimensions{rows: height, cols: width},
		periods:    periods,
		isRemote:   isRemote,
		format:     format,
		factory:    factory,
		cache:      cache,
	}, nil
}

func (d *Display) Close() error {
	if d.terminal != nil {
		d.terminal.close()
	}
	return nil
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
		if d.dimensions.rows < displayRowMin {
			return nil, fmt.Errorf("cannot compile display: "+
				"minimum [%d] rows required for [%d] hosts, only [%d] available for format [%s]",
				displayRowMin, hostCount, d.dimensions.rows, format)
		}
		addLayoutRowsCount := (d.dimensions.rows - displayRowMin) / ((hostCount + 1) / 2)
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
		displayResizeIncrement := (d.dimensions.cols - displayColMin) / displayResizeCount
		displayResizeRemainder := (d.dimensions.cols - displayColMin) % displayResizeCount

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
							b.position = &dimensions{layoutRowIndex + hostRowIndex*len(layout), rowColsCount}
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
			slog.Debug("Layout [relaxed] compilation failed, fallback to [compact]", "error", err)
		}
		d.format = FormatCompact
	}
}

func (d *Display) Load() error {
	d.subscribeDirtyUpdates()
	if len(d.hosts) < 1 {
		return fmt.Errorf("cannot load display: no hosts")
	} else if d.isRemote || len(d.hosts) > 1 {
		if !d.isRemote {
			slog.Debug("Local metricID polling requested for multiple hosts, falling back to remote metricID collection")
		}
		return engine.LoadListeningStreamLoop(d.cache, d.periods)
	}
	return engine.LoadListeningProbesLoop(d.cache, d.periods)
}

func (d *Display) Draw() error {
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
	for _, b := range d.boxes {
		b.drawLabels(d)
	}
	return nil
}

func (d *Display) Loop() error {
	if d.terminal == nil {
		return fmt.Errorf("display terminal not initialized")
	}
	ticker := time.NewTicker(250 * time.Millisecond)
	defer ticker.Stop()
	var wake bool
	var forceDrawAll bool
	for {
		select {
		case <-d.cache.Updates():
			wake = true
		case event, ok := <-d.terminal.events():
			if !ok {
				return nil
			}
			switch ev := event.(type) {
			case *tcell.EventResize:
				d.terminal.sync()

				// TODO: Implement state refresh

				forceDrawAll = true
				wake = true
			case *tcell.EventKey:
				if ev.Key() == tcell.KeyCtrlC {
					return d.Close()
				}
			}
		case <-ticker.C:
			dirtyIndices := d.takeDirtyIndexes()
			if !wake && len(dirtyIndices) == 0 && !forceDrawAll {
				continue
			}
			anyDrawn := forceDrawAll || len(dirtyIndices) > 0
			if forceDrawAll || len(dirtyIndices) == 0 {
				for i := range d.boxes {
					d.boxes[i].drawValue(d)
				}
			} else {
				for _, index := range dirtyIndices {
					if index < 0 || index >= len(d.boxes) {
						continue
					}
					d.boxes[index].drawValue(d)
				}
			}
			if anyDrawn {
				d.terminal.show()
			}
			wake = false
			forceDrawAll = false
		}
	}
}

func (d *Display) subscribeDirtyUpdates() {
	d.dirty.mutex.Lock()
	d.dirty.indexes = make(map[int]struct{}, len(d.boxes))
	d.dirty.mutex.Unlock()
	for i := range d.boxes {
		if d.boxes[i].recordGUID != nil {
			d.cache.SubscribeUpdates(*d.boxes[i].recordGUID, &boxListener{i, d})
		}
	}
}

func (d *Display) markDirty(index int) {
	d.dirty.mutex.Lock()
	if d.dirty.indexes == nil {
		d.dirty.indexes = make(map[int]struct{})
	}
	d.dirty.indexes[index] = struct{}{}
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
	sort.Ints(indexes)
	d.dirty.indexes = make(map[int]struct{}, len(indexes))
	d.dirty.mutex.Unlock()
	return indexes
}

type boxListener struct {
	index   int
	display *Display
}

func (l *boxListener) MarkDirty() {
	if l.display != nil {
		l.display.markDirty(l.index)
	}
}
