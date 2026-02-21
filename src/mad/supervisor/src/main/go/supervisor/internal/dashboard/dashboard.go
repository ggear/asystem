package dashboard

import (
	"fmt"
	"log/slog"
	"sort"
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

type Dashboard struct {
	hosts      []string
	format     Format
	isRemote   bool
	dimensions dimensions
	boxes      []box
	dirty      dirtyBoxes
	terminal   Terminal
	factory    terminalFactory
	cache      *metric.RecordCache
}

type dirtyBoxes struct {
	mutex   sync.Mutex
	indexes map[int]struct{}
}

func NewDashboard(cache *metric.RecordCache, factory terminalFactory, hosts []string, width, height int, format Format, isRemote bool) (*Dashboard, error) {
	return &Dashboard{
		hosts:      hosts,
		dimensions: dimensions{rows: height, cols: width},
		format:     format,
		isRemote:   isRemote,
		factory:    factory,
		cache:      cache,
	}, nil
}

func (d *Dashboard) Close() error {
	if d.terminal != nil {
		d.terminal.close()
	}
	return nil
}

func (d *Dashboard) Compile() (Format, error) {
	hostCount := len(d.hosts)
	compile := func(format Format, layout [][]box) ([]box, error) {

		// Assert and resize layout box rows
		dashboardRowMin := 0
		dashboardRowSkip := 0
		if len(layout) < 2 || len(layout[0]) < 4 {
			return nil, fmt.Errorf("cannot compile dashboard: layout is empty")
		}
		if hostCount < 1 {
			return nil, fmt.Errorf("cannot compile dashboard: no hosts")
		} else if hostCount == 1 {
			dashboardRowSkip = 1
			dashboardRowMin = len(layout) - 1
		} else {
			dashboardRowMin = len(layout) * ((hostCount + 1) / 2)
		}
		if dashboardRowMin <= 0 {
			return nil, fmt.Errorf("cannot compile dashboard: "+
				"invalid minimum rows [%d] for format [%s]", dashboardRowMin, format)
		}
		if d.dimensions.rows < dashboardRowMin {
			return nil, fmt.Errorf("cannot compile dashboard: "+
				"minimum [%d] rows required for [%d] hosts, only [%d] available for format [%s]",
				dashboardRowMin, hostCount, d.dimensions.rows, format)
		}
		addLayoutRowsCount := (d.dimensions.rows - dashboardRowMin) / ((hostCount + 1) / 2)
		lastRow := layout[len(layout)-1]
		for i := 0; i < addLayoutRowsCount; i++ {
			newRow := make([]box, len(lastRow))
			for j := range lastRow {
				newRow[j] = *lastRow[j].clone()
			}
			layout = append(layout, newRow)
		}

		// Assert and resize layout box columns
		dashboardColMin := 0
		dashboardResizeCount := 0
		dashboardBoxSkip := func(i int, b box) bool { return (hostCount == 1 || (i+1)%2 == 0) && b.kind == boxDivdr }
		for hostIndex := range d.hosts {
			hostColMin := 0
			hostResizeCount := 0
			for layoutRowIndex, layoutRow := range layout {
				if layoutRowIndex >= dashboardRowSkip {
					rowCols := 0
					rowResizeCount := 0
					for _, layoutBox := range layoutRow {
						if !dashboardBoxSkip(hostIndex, layoutBox) {
							rowCols += layoutBox.length()
							rowResizeCount += layoutBox.resizes()
						}
					}
					if hostColMin == 0 {
						hostColMin = rowCols
					} else if rowCols != hostColMin {
						return nil, fmt.Errorf("cannot compile dashboard: "+
							"pre-resize row column width must be [%d], but got [%d] in zero-indexed row [%d] of layout [%v]",
							hostColMin, rowCols, layoutRowIndex, format)
					}
					if rowResizeCount < 1 {
						return nil, fmt.Errorf("cannot compile dashboard: "+
							"no box resize functions set in zero-indexed row [%d] of layout [%v]", layoutRowIndex, format)
					}
					if hostResizeCount == 0 {
						hostResizeCount = rowResizeCount
					} else if rowResizeCount != hostResizeCount {
						return nil, fmt.Errorf("cannot compile dashboard: "+
							"the number of box resize functions per row must be [%d], but got [%d] in zero-indexed row [%d] of layout [%v]",
							hostResizeCount, rowResizeCount, layoutRowIndex, format)
					}
				}
			}
			if hostIndex < 2 {
				dashboardColMin += hostColMin
				dashboardResizeCount += hostResizeCount
			}
		}
		if dashboardResizeCount == 0 {
			return nil, fmt.Errorf("cannot compile dashboard: "+
				"no box resize functions set layout [%v]", format)
		}
		dashboardResizeIncrement := (d.dimensions.cols - dashboardColMin) / dashboardResizeCount
		dashboardResizeRemainder := (d.dimensions.cols - dashboardColMin) % dashboardResizeCount

		// Build, resize, assert and compile dashboard boxes
		boxesColsCount := 0
		boxes := make([]box, 0, hostCount*50)
		hostServiceIndex := make([]int, len(d.hosts))
		for hostRowIndex := 0; hostRowIndex < (hostCount+1)/2; hostRowIndex++ {
			for layoutRowIndex, layoutRow := range layout {
				if layoutRowIndex >= dashboardRowSkip {
					rowColsCount := 0
					if len(layoutRow) < 1 ||
						layoutRow[0].kind == boxDivdr {
						return nil, fmt.Errorf("cannot compile dashboard: "+
							"row starts with [cline] in zero-indexed row [%d] of layout [%v]", layoutRowIndex, format)
					}
					if len(layoutRow) < 3 ||
						layoutRow[len(layoutRow)-1].kind != boxDivdr ||
						layoutRow[len(layoutRow)-2].kind != boxDivdr ||
						layoutRow[len(layoutRow)-3].kind != boxDivdr {
						return nil, fmt.Errorf("cannot compile dashboard: "+
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
							if dashboardBoxSkip(hostIndex, layoutBox) {
								continue
							}
							b := layoutBox.clone()
							if b.kind == boxDatum && (b.metric <= metric.MetricAll || b.metric >= metric.MetricMax) {
								return nil, fmt.Errorf("cannot compile dashboard: "+
									"invalid metric ID [%v] in zero-indexed row [%d] of layout [%v]", layoutRow, b.metric, format)
							}
							if b.kind == boxDatum && b.valLen < 1 {
								return nil, fmt.Errorf("cannot compile dashboard: "+
									"invalid value columns [%d] in zero-indexed row [%d] of layout [%v]", b.valLen, b.metric, format)
							}
							if b.kind == boxTitle {
								b.set(
									b.lblLhs, boxLhs, utf8.RuneCountInString(b.lblLhs),
									hostName, boxLhs, utf8.RuneCountInString(b.lblMid),
									b.lblRhs, boxLhs, utf8.RuneCountInString(b.lblRhs),
								)
							}
							serviceCountSubrow := hostServiceIndex[hostIndex]
							if b.metric == metric.MetricServiceName {
								hostServiceIndex[hostIndex]++
							}
							if b.metric != metric.MetricAll {
								b.record = &metric.RecordGUID{ID: b.metric, Host: hostName, ServiceIndex: serviceCountSubrow}
							}
							b.position = &dimensions{layoutRowIndex + hostRowIndex*len(layout), rowColsCount}
							b.resize(dashboardResizeIncrement, dashboardResizeRemainder)
							rowColsCount += b.length()
							boxes = append(boxes, *b)
						}
					}
					if hostCount == 1 || hostRowIndex*2+1 < hostCount {
						if boxesColsCount == 0 {
							boxesColsCount = rowColsCount
						} else if rowColsCount != boxesColsCount {
							return nil, fmt.Errorf("cannot compile dashboard: "+
								"post-resize, row column width must be [%d], but got [%d] in layout zero-indexed row [%d] and [%v]",
								boxesColsCount, rowColsCount, layoutRowIndex, format)
						}
					}
				}
			}
		}

		// Assert dashboard boxes positions and lengths
		if len(boxes) > 0 {
			rowWidth := 0
			expectedCol := 0
			expectedRow := -1
			positioningErr := fmt.Errorf("cannot compile dashboard: invalid box positioning in layout [%v]", format)
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
			layout = relaxedDashboardLayout()
		case FormatCompact:
			attemptedFormat = FormatCompact
			layout = compactDashboardLayout()
		default:
			return d.format, fmt.Errorf("cannot compile dashboard: invalid formats [%v]", d.format)
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

func (d *Dashboard) Load() error {
	d.subscribeDirtyUpdates()
	if len(d.hosts) < 1 {
		return fmt.Errorf("cannot load dashboard: no hosts")
	} else if d.isRemote || len(d.hosts) > 1 {
		if !d.isRemote {
			slog.Debug("Local metric polling requested for multiple hosts, falling back to remote metric collection")
		}
		return d.cache.LoadRemoteListeners()
	}
	return d.cache.LoadLocalListeners()
}

func (d *Dashboard) Display() error {
	if d.terminal == nil {
		if d.factory == nil {
			return fmt.Errorf("cannot display dashboard: terminal factory is nil")
		}
		terminal, err := d.factory()
		if err != nil {
			return err
		}
		d.terminal = terminal
	}
	for _, b := range d.boxes {
		b.drawLabels(d.terminal, d.cache)
	}
	return nil
}

func (d *Dashboard) Update() error {
	if d.terminal == nil {
		return fmt.Errorf("dashboard terminal not initialized")
	}
	ticker := time.NewTicker(33 * time.Millisecond)
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
			var anyDrawn bool
			if forceDrawAll || len(dirtyIndices) == 0 {
				for i := range d.boxes {
					d.boxes[i].drawValue(d.terminal, d.cache)
				}
				anyDrawn = true
			} else {
				for _, index := range dirtyIndices {
					if index < 0 || index >= len(d.boxes) {
						continue
					}
					d.boxes[index].drawValue(d.terminal, d.cache)
				}
				anyDrawn = true
			}
			if anyDrawn {
				d.terminal.show()
			}
			wake = false
			forceDrawAll = false
		}
	}
}

func (d *Dashboard) subscribeDirtyUpdates() {
	d.dirty.mutex.Lock()
	d.dirty.indexes = make(map[int]struct{}, len(d.boxes))
	d.dirty.mutex.Unlock()
	for i := range d.boxes {
		if d.boxes[i].record != nil {
			d.cache.SubscribeUpdates(*d.boxes[i].record, &boxListener{i, d})
		}
	}
}

func (d *Dashboard) markDirty(index int) {
	d.dirty.mutex.Lock()
	if d.dirty.indexes == nil {
		d.dirty.indexes = make(map[int]struct{})
	}
	d.dirty.indexes[index] = struct{}{}
	d.dirty.mutex.Unlock()
}

func (d *Dashboard) takeDirtyIndexes() []int {
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
	index     int
	dashboard *Dashboard
}

func (l *boxListener) MarkDirty() {
	if l.dashboard != nil {
		l.dashboard.markDirty(l.index)
	}
}
