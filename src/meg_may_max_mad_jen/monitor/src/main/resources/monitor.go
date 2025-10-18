package main

import (
	"fmt"
	"os"
	"os/exec"
	"regexp"
	"sort"
	"strconv"
	"strings"

	"github.com/olekukonko/tablewriter"
)

const (
	red   = "\033[0;31m"
	green = "\033[0;32m"
	nc    = "\033[0m"
)

func runCommand(name string, args ...string) string {
	out, _ := exec.Command(name, args...).Output()
	return string(out)
}

func percentUsed(total, free float64) float64 {
	if total == 0 {
		return 0
	}
	return (total - free) / total * 100
}

func colorPercent(value float64) string {
	if value >= 80 {
		return fmt.Sprintf("%s%.1f%%%s", red, value, nc)
	}
	return fmt.Sprintf("%s%.1f%%%s", green, value, nc)
}

func readMemSwap() (memPercent, swapPercent float64) {
	memInfo := runCommand("awk", "/MemAvailable/ {mem=$2} /SwapFree/ {swap=$2} END {print mem, swap}", "/proc/meminfo")
	var memFree, swapFree float64
	fmt.Sscanf(memInfo, "%f %f", &memFree, &swapFree)

	memTotal := 0.0
	fmt.Sscanf(runCommand("awk", "/MemTotal/ {print $2}", "/proc/meminfo"), "%f", &memTotal)
	memPercent = percentUsed(memTotal, memFree)

	swapTotal := 0.0
	fmt.Sscanf(runCommand("awk", "/SwapTotal/ {print $2}", "/proc/meminfo"), "%f", &swapTotal)
	swapPercent = percentUsed(swapTotal, swapFree)
	return
}

func readDiskUsage() float64 {
	df := runCommand("df", "/")
	lines := strings.Split(df, "\n")
	if len(lines) < 2 {
		return 0
	}
	fields := strings.Fields(lines[1])
	if len(fields) < 5 {
		return 0
	}
	usedPercent, _ := strconv.ParseFloat(strings.TrimSuffix(fields[4], "%"), 64)
	return usedPercent
}

func readCPU() float64 {
	mpstat := runCommand("mpstat", "1", "2")
	lines := strings.Split(mpstat, "\n")
	for _, line := range lines {
		if strings.Contains(line, "Average") {
			fields := strings.Fields(line)
			if len(fields) >= 12 {
				cpu, _ := strconv.ParseFloat(fields[len(fields)-1], 64)
				return 100 - cpu
			}
		}
	}
	return 0
}

func readMaxTemp() float64 {
	sensors := runCommand("sensors")
	var temps []float64
	re := regexp.MustCompile(`\+?([0-9]+(?:\.[0-9]+)?)°C`)
	for _, line := range strings.Split(sensors, "\n") {
		matches := re.FindStringSubmatch(line)
		if len(matches) > 1 {
			val, _ := strconv.ParseFloat(matches[1], 64)
			temps = append(temps, val)
		}
	}
	if len(temps) == 0 {
		return 0
	}
	sort.Sort(sort.Reverse(sort.Float64Slice(temps)))
	return temps[0]
}

func readDowntimePercent() float64 {
	tuptime := runCommand("tuptime")
	re := regexp.MustCompile(`System uptime:\s+([0-9.]+)%`)
	match := re.FindStringSubmatch(tuptime)
	if len(match) < 2 {
		return 0
	}
	up, _ := strconv.ParseFloat(match[1], 64)
	dp := 100 - up
	if dp < 0 {
		dp = 0
	} else if dp > 100 {
		dp = 100
	}
	return dp
}

func readDockerStats() [][]string {
	out := runCommand("docker", "ps", "--format", "{{.Names}}\t{{.Status}}")
	lines := strings.Split(strings.TrimSpace(out), "\n")
	var rows [][]string
	for _, line := range lines {
		parts := strings.SplitN(line, "\t", 2)
		if len(parts) == 2 {
			status := parts[1]
			if strings.Contains(strings.ToLower(status), "unhealthy") {
				status = fmt.Sprintf("%s%s%s", red, status, nc)
			} else {
				status = fmt.Sprintf("%s%s%s", green, status, nc)
			}
			rows = append(rows, []string{parts[0], status})
		}
	}
	return rows
}

func main() {
	memPercent, swapPercent := readMemSwap()
	diskUsed := readDiskUsage()
	cpu := readCPU()
	maxTemp := readMaxTemp()
	tempPercent := maxTemp / 90 * 100
	downtimePercent := readDowntimePercent()

	hostStats := [][]string{
		{"Down Tme", colorPercent(downtimePercent)},
		{"Used Mem", colorPercent(memPercent)},
		{"Temp Max", colorPercent(tempPercent)},
		{"Used Swp", colorPercent(swapPercent)},
		{"Used CPU", colorPercent(cpu)},
		{"Used Dsk", colorPercent(diskUsed)},
	}

	containerStats := readDockerStats()

	// Host stats table
	fmt.Println("Host Stats")
	hostTable := tablewriter.NewWriter(os.Stdout)
	hostTable.SetHeader([]string{"Metric", "Value"})
	hostTable.SetBorders(tablewriter.Border{Left: true, Top: false, Right: true, Bottom: false})
	hostTable.SetCenterSeparator("|")
	hostTable.AppendBulk(hostStats)
	hostTable.Render()

	fmt.Println(strings.Repeat("-", 60))

	// Container stats table
	fmt.Println("Container Stats")
	containerTable := tablewriter.NewWriter(os.Stdout)
	containerTable.SetHeader([]string{"Container", "Status"})
	containerTable.SetBorders(tablewriter.Border{Left: true, Top: false, Right: true, Bottom: false})
	containerTable.SetCenterSeparator("|")
	containerTable.AppendBulk(containerStats)
	containerTable.Render()
}
