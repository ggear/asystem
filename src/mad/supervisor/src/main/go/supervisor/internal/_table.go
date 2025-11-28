package internal

import (
	"fmt"
	"time"

	"github.com/gdamore/tcell/v2"
)

// Service represents a single service row
type Service struct {
	Name    string
	CPU     int
	RAM     int
	Backup  string
	Healthy string
	Reboots int
	Alive   string
	Version string
}

// Draw a progress bar of given width
func progressBar(val int, width int) string {
	if val > 100 {
		val = 100
	} else if val < 0 {
		val = 0
	}
	full := val * width / 100
	empty := width - full
	bar := ""
	for i := 0; i < full; i++ {
		bar += "█"
	}
	for i := 0; i < empty; i++ {
		bar += " "
	}
	return "[" + bar + "]"
}

// Draw a single row at (x, y) with given column widths
func drawRow(s tcell.Screen, x, y int, row []string, colWidths []int, style tcell.Style) {
	sX := x
	for i, cell := range row {
		// draw cell content
		for j, r := range cell {
			if j >= colWidths[i] {
				break
			}
			s.SetContent(sX+j, y, r, nil, style)
		}
		// fill remaining space
		for j := len([]rune(cell)); j < colWidths[i]; j++ {
			s.SetContent(sX+j, y, ' ', nil, style)
		}
		sX += colWidths[i] + 1 // +1 for separator
	}
}

// Draw table borders (top + bottom + separator)
func drawBorder(s tcell.Screen, x, y int, colWidths []int, style tcell.Style) {
	sX := x
	for _, w := range colWidths {
		s.SetContent(sX, y, '+', nil, style)
		for i := 0; i < w; i++ {
			s.SetContent(sX+i+1, y, '-', nil, style)
		}
		sX += w + 1
	}
	s.SetContent(sX, y, '+', nil, style)
}

// Draw headers
func drawHeader(s tcell.Screen, x, y int, headers []string, colWidths []int, style tcell.Style) {
	drawRow(s, x, y, headers, colWidths, style)
}

// Copy slice of services
func copyServices(src []Service) []Service {
	dst := make([]Service, len(src))
	copy(dst, src)
	return dst
}

func main() {
	s, err := tcell.NewScreen()
	if err != nil {
		panic(err)
	}
	if err := s.Init(); err != nil {
		panic(err)
	}
	defer s.Fini()

	style := tcell.StyleDefault.Foreground(tcell.ColorWhite)
	s.Clear()

	// ----- Compute Table -----
	computeHeaders := []string{"COMPUTE", "HEALTH", "RUNTIME", "STORAGE"}
	computeRows := [][]string{
		{
			fmt.Sprintf("Used CPU %s %3d%%", progressBar(100, 5), 100),
			fmt.Sprintf("Fail SVC %s %3d%%", progressBar(100, 6), 100),
			fmt.Sprintf("Peak TEM %s %3d%%", progressBar(75, 5), 75),
			fmt.Sprintf("Used SYS %s %3d%%", progressBar(100, 5), 100),
		},
		{
			fmt.Sprintf("Used RAM %s %3d%%", progressBar(75, 5), 75),
			fmt.Sprintf("Fail SHR %s %3d%%", progressBar(1, 5), 1),
			fmt.Sprintf("Peak FAN %s %3d%%", progressBar(100, 5), 100),
			fmt.Sprintf("Used SHR %s %3d%%", progressBar(75, 5), 75),
		},
		{
			fmt.Sprintf("Aloc RAM %s %3d%%", progressBar(150, 5), 150),
			fmt.Sprintf("Fail BKP %s %3d%%", progressBar(100, 5), 100),
			fmt.Sprintf("Life SSD %s %3d%%", progressBar(75, 5), 75),
			fmt.Sprintf("Used BKP %s %3d%%", progressBar(75, 5), 75),
		},
	}
	computeColWidths := []int{26, 26, 26, 26}

	// Draw compute table (full refresh)
	drawBorder(s, 0, 0, computeColWidths, style)
	drawHeader(s, 1, 1, computeHeaders, computeColWidths, style)
	drawBorder(s, 0, 2, computeColWidths, style)
	for i, row := range computeRows {
		drawRow(s, 1, 3+i, row, computeColWidths, style)
	}
	drawBorder(s, 0, 3+len(computeRows), computeColWidths, style)

	// ----- Service Table -----
	serviceHeaders := []string{"SERVICE", "PROCESSOR", "MEMORY", "BACK-UP", "HEALTHY", "REBOOTS", "ALIVE", "VERSION"}
	serviceColWidths := []int{17, 17, 17, 9, 9, 9, 7, 15}

	services := []Service{
		{"monitor", 100, 100, "✔", "✔", 5, "1y", "10.100.5191"},
		{"homeassistant", 75, 75, "✖", "✖", 0, "120d", "10.100.5190"},
		{"nginx", 100, 75, "✖", "✖", 0, "100d", "10.100.3192"},
		{"averyrealylon~", 100, 1, "✖", "✖", 0, "0d", "10.100.1193"},
		{"alongishname", 75, 75, "✖", "✖", 0, "0d", "10.100.4194"},
		{"ashortername", 1, 75, "✖", "✖", 0, "100d", "10.100.5095"},
		{"shortname", 1, 75, "✖", "✖", 0, "100d", "10.100.5096"},
	}

	// Draw header
	startY := 3 + len(computeRows) + 2
	drawBorder(s, 0, startY, serviceColWidths, style)
	drawHeader(s, 1, startY+1, serviceHeaders, serviceColWidths, style)
	drawBorder(s, 0, startY+2, serviceColWidths, style)

	prevServices := copyServices(services)

	for i, svc := range services {
		row := []string{
			svc.Name,
			progressBar(svc.CPU, 6) + fmt.Sprintf(" %3d%%", svc.CPU),
			progressBar(svc.RAM, 6) + fmt.Sprintf(" %3d%%", svc.RAM),
			svc.Backup,
			svc.Healthy,
			fmt.Sprintf("%d", svc.Reboots),
			svc.Alive,
			svc.Version,
		}
		drawRow(s, 1, startY+3+i, row, serviceColWidths, style)
	}
	drawBorder(s, 0, startY+3+len(services), serviceColWidths, style)

	s.Show()

	// ----- Update loop (partial refresh) -----
	tick := time.NewTicker(2 * time.Second)
	defer tick.Stop()

	for i := 0; i < 50; i++ {
		<-tick.C

		// Simulate updates
		services[1].CPU = (services[1].CPU + 7) % 100
		services[1].RAM = (services[1].RAM + 5) % 100
		services[4].CPU = (services[4].CPU + 3) % 100

		// Compare previous state and update only changed rows
		for rowIdx, svc := range services {
			prev := prevServices[rowIdx]
			if svc != prev {
				row := []string{
					svc.Name,
					progressBar(svc.CPU, 6) + fmt.Sprintf(" %3d%%", svc.CPU),
					progressBar(svc.RAM, 6) + fmt.Sprintf(" %3d%%", svc.RAM),
					svc.Backup,
					svc.Healthy,
					fmt.Sprintf("%d", svc.Reboots),
					svc.Alive,
					svc.Version,
				}
				drawRow(s, 1, startY+3+rowIdx, row, serviceColWidths, style)
			}
		}

		prevServices = copyServices(services)
		s.Show()
	}
}
