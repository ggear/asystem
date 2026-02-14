package dashboard

import (
	"fmt"
	"sort"
	"supervisor/internal/metric"
	"time"

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

type Dimensions struct {
	Rows int
	Cols int
}

func (d Dimensions) String() string {
	return fmt.Sprintf("[%d,%d]", d.Rows, d.Cols)
}

type Dashboard struct {
	grid   [][]box
	screen Terminal
	cache  *metric.RecordCache
}

func NewDashboard(cache *metric.RecordCache, factory terminalFactory) (*Dashboard, error) {
	screen, err := factory()
	if err != nil {
		return nil, err
	}
	return &Dashboard{
		screen: screen,
		cache:  cache,
	}, nil
}

func (d *Dashboard) Close() {
	if d.screen != nil {
		d.screen.close()
	}
}

func (d *Dashboard) Compile(hostNames []string, terminalDims Dimensions, format Format) error {
	sort.Strings(hostNames)
	compile := func(hostNames []string, terminalDims Dimensions, format Format, layout [][]box) ([][]box, error) {

		// Assert and resize rows
		minGridRows := 0
		hostCount := len(hostNames)
		if len(layout) == 0 || layout[0] == nil {
			return nil, fmt.Errorf("cannot compile grid: layout is empty")
		}
		if hostCount < 1 {
			return nil, fmt.Errorf("cannot compile grid: no hosts")
		} else if hostCount == 1 {
			minGridRows = len(layout) - 1
		} else {
			minGridRows = len(layout) * (hostCount + 1) / 2
		}
		if minGridRows <= 0 {
			return nil, fmt.Errorf("cannot compile grid: invalid minimum rows [%d]", minGridRows)
		}
		if terminalDims.Rows < minGridRows {
			return nil, fmt.Errorf("cannot compile grid: mininum [%d] rows required for [%d] hosts, only [%d] available", minGridRows, hostCount, terminalDims.Rows)
		}
		addLayoutRowsCount := (terminalDims.Rows - minGridRows) / ((hostCount + 1) / 2)
		lastRow := layout[len(layout)-1]
		for i := 0; i < addLayoutRowsCount; i++ {
			newRow := make([]box, len(lastRow))
			for j := range lastRow {
				newRow[j] = *lastRow[j].clone()
			}
			layout = append(layout, newRow)
		}

		// Assert and resize columns
		minGridCols := 0
		resizeCount := 0
		skipBox := func(i int, b box) bool { return (hostCount == 1 || (i+1)%2 == 0) && b.kind == boxCline }
		for hostIdx := range hostNames {
			for layoutRowIdx, layoutRow := range layout {
				rowCols := 0
				rowResizeCount := 0
				for _, layoutBox := range layoutRow {
					if !skipBox(hostIdx, layoutBox) {
						rowCols += layoutBox.length()
						if layoutBox.resize != nil {
							rowResizeCount++
						}
					}
				}
				if minGridCols == 0 {
					minGridCols = rowCols
				} else if rowCols != minGridCols {
					return nil, fmt.Errorf("cannot compile grid: pre-resize row column width must be [%d], but got [%d] in row [%d] of layout [%v]", minGridCols, rowCols, layoutRowIdx, format)
				}
				if rowResizeCount < 1 {
					return nil, fmt.Errorf("cannot compile grid: no box resize functions set in row [%d] of layout [%v]", layoutRowIdx, format)
				}
				if resizeCount == 0 {
					resizeCount = rowResizeCount
				} else if rowResizeCount != resizeCount {
					return nil, fmt.Errorf("cannot compile grid: the number of box resize functions per row must be [%d], but got [%d] in row [%d] of layout [%v]", resizeCount, rowResizeCount, layoutRowIdx, format)
				}
			}
		}
		if resizeCount == 0 {
			return nil, fmt.Errorf("cannot compile grid: no box resize functions set layout [%v]", format)
		}
		resizeIncrement := (terminalDims.Cols - minGridCols) / resizeCount
		resizeRemainder := (terminalDims.Cols - minGridCols) % resizeCount

		// Assert and compile grid
		var (
			grid     [][]box
			hostRow  []box
			gridCols int
		)
		for hostIdx, hostName := range hostNames {
			gridServiceIdx := 0
			for layoutRowIdx, layoutRow := range layout {
				if len(layoutRow) < 1 ||
					layoutRow[0].kind == boxCline {
					return nil, fmt.Errorf("cannot compile grid: row starts with [cline] in row [%d] of layout [%v]", layoutRowIdx, format)
				}
				if len(layoutRow) < 3 ||
					layoutRow[len(layoutRow)-1].kind != boxCline ||
					layoutRow[len(layoutRow)-2].kind != boxCline ||
					layoutRow[len(layoutRow)-3].kind != boxCline {
					return nil, fmt.Errorf("cannot compile grid: row is not terminated by [3 x cline] in row [%d] of layout [%v]", layoutRowIdx, format)
				}
				gridRowCols := 0
				for _, layoutBox := range layoutRow {
					if skipBox(hostIdx, layoutBox) {
						continue
					}
					gridBox := layoutBox.clone()
					if gridBox.kind == boxDatum && (gridBox.metric <= metric.MetricAll || gridBox.metric >= metric.MetricMax) {
						return nil, fmt.Errorf("cannot compile grid: invalid metric ID [%v] in row [%d] of layout [%v]", layoutRow, gridBox.metric, format)
					}
					if gridBox.kind == boxDatum && gridBox.valLen < 1 {
						return nil, fmt.Errorf("cannot compile grid: invalid value length [%d] in row [%d] of layout [%v]", gridBox.valLen, gridBox.metric, format)
					}
					if gridBox.resize != nil {
						if gridBox.kind == boxCline {
							gridBox.resize(gridBox, resizeRemainder)
						} else {
							gridBox.resize(gridBox, resizeIncrement)
						}
					}
					serviceIdx := 0
					if gridBox.metric == metric.MetricServiceName {
						serviceIdx = gridServiceIdx
						gridServiceIdx++
					}
					gridBox.record = &metric.RecordGUID{ID: gridBox.metric, Host: hostName, ServiceIndex: serviceIdx}
					gridBox.location = &Dimensions{layoutRowIdx, gridRowCols}
					gridRowCols += gridBox.length()

					// TODO:
					//   - Subscribe each datum box as listener using RecordCache.AddUpdatesListener, insert into cache
					//fmt.Printf("%s[%d]: layout[%d,%d]\n\n", hostName, hostIdx, layoutRowIdx, layoutColIdx)

					hostRow = append(hostRow, *gridBox)
				}
				if gridCols == 0 {
					gridCols = gridRowCols
				} else if gridRowCols != gridCols {
					return nil, fmt.Errorf("cannot compile grid: post-resize, row column width must be [%d], but got [%d] in row [%d] of layout [%v]", gridCols, gridRowCols, layoutRowIdx, format)
				}
			}
			if (hostIdx+1)%2 == 0 || hostIdx == len(hostNames)-1 {
				grid = append(grid, hostRow)
				hostRow = []box{}
			}
		}
		return grid, nil
	}
	var layout [][]box
	for {
		var formatAttempt Format
		switch format {
		case FormatAuto, FormatRelaxed:
			formatAttempt = FormatRelaxed
			layout = relaxedDashboardLayout()
		case FormatCompact:
			formatAttempt = FormatCompact
			layout = compactDashboardLayout()
		default:
			return fmt.Errorf("cannot compile grid: invalid format [%v]", format)
		}
		grid, err := compile(hostNames, terminalDims, formatAttempt, layout)
		if err == nil {
			d.grid = grid
			return nil
		}
		if format != FormatAuto {
			return err
		}
		format = FormatCompact
	}
}

func (d *Dashboard) Create() error {

	// TODO:
	//   - draw static/dynamic by looping over grid

	return nil
}

func (d *Dashboard) Update() error {
	ticker := time.NewTicker(33 * time.Millisecond)
	defer ticker.Stop()
	var wake bool
	for {
		select {
		case <-d.cache.Updates():
			wake = true
		case ev := <-d.screen.events():
			switch ev := ev.(type) {
			case *tcell.EventResize:
				d.screen.sync()

				// TODO: Implement

				wake = true
			case *tcell.EventKey:
				if ev.Key() == tcell.KeyCtrlC || ev.Key() == 'q' {
					return nil
				}
			}
		case <-ticker.C:
			if !wake {
				continue
			}
			var anyDrawn bool
			for row := range d.grid {
				for col := range d.grid[row] {
					box := &d.grid[row][col]
					if !box.TakeDirty() || box.record == nil {
						continue
					}
					record, ok := d.cache.Get(*box.record)
					if !ok || record == nil {
						continue
					}

					// TODO: Implement
					// drawBox(Terminal, box, record)

					anyDrawn = true
				}
			}

			if anyDrawn {
				d.screen.show()
			}
			wake = false
		}
	}
}
