package main

import (
	"bufio"
	"context"
	"fmt"
	"io/ioutil"
	"os"
	"path/filepath"
	"sort"
	"strconv"
	"strings"
	"syscall"
	"time"

	"github.com/docker/docker/api/types"
	"github.com/docker/docker/client"
	"github.com/olekukonko/tablewriter"
)

const (
	red     = "\033[0;31m"
	green   = "\033[0;32m"
	nc      = "\033[0m"
	maxTemp = 90.0
	yearSec = 365 * 24 * 60 * 60
)

type HostMetrics struct {
	Name  string
	Value string
}

func main() {
	hostMetrics, err := gatherHostMetrics()
	if err != nil {
		fmt.Fprintf(os.Stderr, "Error gathering host metrics: %v\n", err)
		os.Exit(1)
	}

	containerMetrics, err := gatherContainerMetrics()
	if err != nil {
		fmt.Fprintf(os.Stderr, "Error gathering container metrics: %v\n", err)
		os.Exit(1)
	}

	renderTable("Host Stats", []string{"Metric", "Value"}, hostMetrics)
	fmt.Println(strings.Repeat("-", 60))
	renderTable("Container Stats", []string{"Container", "Status"}, containerMetrics)
}

// gatherHostMetrics collects memory, swap, CPU, disk, temp, and downtime
func gatherHostMetrics() ([]HostMetrics, error) {
	memPercent, swapPercent, err := readMemSwap()
	if err != nil {
		return nil, err
	}
	diskPercent, err := readDiskUsage("/")
	if err != nil {
		return nil, err
	}
	cpuPercent, err := readCPU()
	if err != nil {
		return nil, err
	}
	temp := readMaxTemp()
	tempPercent := temp / maxTemp * 100
	downtimePercent := readDowntimePercent()

	return []HostMetrics{
		{"Down Tme", colorPercent(downtimePercent)},
		{"Used Mem", colorPercent(memPercent)},
		{"Temp Max", colorPercent(tempPercent)},
		{"Used Swp", colorPercent(swapPercent)},
		{"Used CPU", colorPercent(cpuPercent)},
		{"Used Dsk", colorPercent(diskPercent)},
	}, nil
}

// gatherContainerMetrics collects Docker container statuses
func gatherContainerMetrics() ([]HostMetrics, error) {
	cli, err := client.NewClientWithOpts(client.FromEnv, client.WithAPIVersionNegotiation())
	if err != nil {
		return nil, err
	}

	containers, err := cli.ContainerList(context.Background(), types.ContainerListOptions{})
	if err != nil {
		return nil, err
	}

	var metrics []HostMetrics
	for _, c := range containers {
		status := c.State
		if status == "running" && strings.Contains(strings.ToLower(c.Status), "unhealthy") {
			status = "unhealthy"
		}
		metrics = append(metrics, HostMetrics{strings.TrimPrefix(c.Names[0], "/"), colorStatus(status)})
	}
	return metrics, nil
}

func colorPercent(value float64) string {
	if value >= 80 {
		return fmt.Sprintf("%s%.1f%%%s", red, value, nc)
	}
	return fmt.Sprintf("%s%.1f%%%s", green, value, nc)
}

func colorStatus(status string) string {
	if strings.ToLower(status) == "unhealthy" {
		return fmt.Sprintf("%s%s%s", red, status, nc)
	}
	return fmt.Sprintf("%s%s%s", green, status, nc)
}

func readMemSwap() (memPercent, swapPercent float64, err error) {
	file, err := os.Open("/proc/meminfo")
	if err != nil {
		return
	}
	defer file.Close()

	var memTotal, memAvailable, swapTotal, swapFree float64
	scanner := bufio.NewScanner(file)
	for scanner.Scan() {
		line := scanner.Text()
		fields := strings.Fields(line)
		if len(fields) < 2 {
			continue
		}
		key := strings.TrimSuffix(fields[0], ":")
		val, e := strconv.ParseFloat(fields[1], 64)
		if e != nil {
			continue
		}
		switch key {
		case "MemTotal":
			memTotal = val
		case "MemAvailable":
			memAvailable = val
		case "SwapTotal":
			swapTotal = val
		case "SwapFree":
			swapFree = val
		}
	}
	if memTotal > 0 {
		memPercent = (memTotal - memAvailable) / memTotal * 100
	}
	if swapTotal > 0 {
		swapPercent = (swapTotal - swapFree) / swapTotal * 100
	}
	return
}

func readDiskUsage(path string) (float64, error) {
	var stat syscall.Statfs_t
	if err := syscall.Statfs(path, &stat); err != nil {
		return 0, err
	}
	total := float64(stat.Blocks * uint64(stat.Bsize))
	free := float64(stat.Bfree * uint64(stat.Bsize))
	if total == 0 {
		return 0, nil
	}
	return (total - free) / total * 100, nil
}

func readCPU() (float64, error) {
	idle0, total0, err := cpuTimes()
	if err != nil {
		return 0, err
	}
	time.Sleep(1 * time.Second)
	idle1, total1, err := cpuTimes()
	if err != nil {
		return 0, err
	}
	if total1-total0 == 0 {
		return 0, nil
	}
	return 100 * float64(total1-total0-(idle1-idle0)) / float64(total1-total0), nil
}

func cpuTimes() (idle, total uint64, err error) {
	file, err := os.Open("/proc/stat")
	if err != nil {
		return
	}
	defer file.Close()
	scanner := bufio.NewScanner(file)
	for scanner.Scan() {
		line := scanner.Text()
		if strings.HasPrefix(line, "cpu ") {
			fields := strings.Fields(line)[1:]
			var sum uint64
			var idleVal uint64
			for i, f := range fields {
				v, e := strconv.ParseUint(f, 10, 64)
				if e != nil {
					continue
				}
				sum += v
				if i == 3 {
					idleVal = v
				}
			}
			return idleVal, sum, nil
		}
	}
	return
}

func readMaxTemp() float64 {
	files, _ := filepath.Glob("/sys/class/thermal/thermal_zone*/temp")
	var temps []float64
	for _, f := range files {
		data, err := ioutil.ReadFile(f)
		if err != nil {
			continue
		}
		val, err := strconv.ParseFloat(strings.TrimSpace(string(data)), 64)
		if err != nil {
			continue
		}
		temps = append(temps, val/1000) // millidegree to degree
	}
	if len(temps) == 0 {
		return 0
	}
	sort.Sort(sort.Reverse(sort.Float64Slice(temps)))
	return temps[0]
}

func readDowntimePercent() float64 {
	data, err := ioutil.ReadFile("/proc/uptime")
	if err != nil {
		return 0
	}
	fields := strings.Fields(string(data))
	if len(fields) < 1 {
		return 0
	}
	uptimeSeconds, _ := strconv.ParseFloat(fields[0], 64)
	dp := 100 * (1 - uptimeSeconds/yearSec)
	if dp < 0 {
		dp = 0
	} else if dp > 100 {
		dp = 100
	}
	return dp
}

func renderTable(title string, headers []string, rows []HostMetrics) {
	fmt.Println(title)
	table := tablewriter.NewWriter(os.Stdout)
	table.SetHeader(headers)
	table.SetBorders(tablewriter.Border{Left: true, Top: false, Right: true, Bottom: false})
	table.SetCenterSeparator("|")
	for _, r := range rows {
		table.Append([]string{r.Name, r.Value})
	}
	table.Render()
}
