package cmd

import (
	"encoding/json"
	"fmt"
	"os"
	"storage/internal/config"
	"storage/internal/display"
	"storage/internal/engine"
	"strings"
	"time"

	"github.com/spf13/cobra"
	"golang.org/x/term"
)

func init() {
	rootCmd.AddCommand(newSpaceCmd())
}

func newSpaceCmd() *cobra.Command {
	opts := &spaceOptions{}
	cmd := &cobra.Command{
		Use:     "space [filter ...]",
		Aliases: []string{"aspace"},
		Short:   spaceDescription,
		Long:    spaceDescription,
		Args:    cobra.ArbitraryArgs,
		RunE: func(cmd *cobra.Command, args []string) error {
			configPath, _ := cmd.Flags().GetString("config")
			var filters []string
			if cmd.Flags().Changed("filter") {
				filters = strings.Split(opts.filter, ",")
			}
			filters = append(filters, args...)
			if len(filters) == 0 {
				filters = engine.DefaultFilters
			}
			return executeSpace(configPath, opts, filters)
		},
	}
	cmd.Flags().StringVarP(&opts.mode, "mode", "m", engine.ModeAuto, "mode to operate in: local, remote, auto")
	cmd.Flags().StringVarP(&opts.filter, "filter", "f", strings.Join(engine.DefaultFilters, ","), "mounts to include: comma separated list of mount globs, also taken as arguments")
	cmd.Flags().StringVarP(&opts.symbols, "symbols", "s", "auto", "define output character set: auto, ascii or unicode")
	cmd.Flags().StringVarP(&opts.theme, "theme", "t", "auto", "colour theme: auto, colour or mono")
	cmd.Flags().BoolVarP(&opts.json, "json", "j", false, "output json not tabular text")
	cmd.Flags().SortFlags = false
	return cmd
}

func executeSpace(configPath string, opts *spaceOptions, filters []string) error {
	started := time.Now()
	cfg := config.Load(configPath)
	useUnicode, err := resolveSymbols(opts.symbols)
	if err != nil {
		return err
	}
	useColour, err := resolveTheme(opts.theme)
	if err != nil {
		return err
	}
	hosts, mode, err := engine.Collect(cfg, filters, opts.mode)
	if err != nil {
		return err
	}
	fault, unreachable := reportFaults(hosts, cfg.Version())
	if unreachable && !anyMeasured(hosts) {
		return fmt.Errorf("no reachable hosts")
	}
	if opts.json {
		document := engine.Document{
			Version:   cfg.Version(),
			Mode:      mode,
			StartedTS: started.Format(time.RFC3339),
			DurationS: int(time.Since(started).Seconds()),
			Hosts:     hosts,
		}
		encoded, err := json.MarshalIndent(document, "", "  ")
		if err != nil {
			return err
		}
		fmt.Println(string(encoded))
	} else {
		rows := rowsFor(hosts)
		if mode == engine.ModeRemote {
			rows = append(rows, estateRows(hosts, filters)...)
		}
		fmt.Print(display.Render(rows, useUnicode, useColour))
	}
	if fault {
		os.Exit(1)
	}
	return nil
}

func rowsFor(hosts []engine.HostDoc) []display.Row {
	var rows []display.Row
	for _, host := range hosts {
		firstOfHost := true
		lastClass := ""
		for _, mount := range host.Mounts {
			row := display.Row{Host: host.Label, Mount: mount.Mount}
			if !firstOfHost {
				row.Host = ""
			}
			if mount.Space != nil {
				row.Size = mount.Space.SizeBytes
				row.Used = mount.Space.UsedBytes
				row.Free = mount.Space.FreeBytes
				row.Percent = percentOf(row.Used, row.Size)
			} else {
				row.Unmeasured = true
			}
			row.NewHost = firstOfHost
			row.NewClass = firstOfHost || mount.Class != lastClass
			firstOfHost = false
			lastClass = mount.Class
			rows = append(rows, row)
		}
	}
	return rows
}

func estateRows(hosts []engine.HostDoc, filters []string) []display.Row {
	if len(hosts) < 2 {
		return nil
	}
	type total struct{ size, used uint64 }
	totals := map[string]*total{}
	order := []string{engine.ClassRoot, engine.ClassShare, engine.ClassBackup}
	for _, host := range hosts {
		subtotalled := false
		for _, mount := range host.Mounts {
			subtotalled = subtotalled || (mount.Class == engine.ClassShare && mount.Mount == "/share")
		}
		for _, mount := range host.Mounts {
			if mount.State != engine.MountStateMeasured || mount.Space == nil {
				continue
			}
			if mount.Class == engine.ClassShare && subtotalled != (mount.Mount == "/share") {
				continue
			}
			if mount.Class == engine.ClassRoot && mount.Mount != "/" {
				continue
			}
			t, ok := totals[mount.Class]
			if !ok {
				t = &total{}
				totals[mount.Class] = t
			}
			t.size += mount.Space.SizeBytes
			t.used += mount.Space.UsedBytes
		}
	}
	var rows []display.Row
	var grandSize, grandUsed uint64
	first := true
	mountName := map[string]string{engine.ClassRoot: "/", engine.ClassShare: "/share", engine.ClassBackup: "/backup"}
	for _, class := range order {
		t, ok := totals[class]
		if !ok || !engine.Claims(filters, mountName[class], class) {
			continue
		}
		rows = append(rows, display.Row{Mount: mountName[class], Size: t.size, Used: t.used, Free: t.size - t.used, Percent: percentOf(t.used, t.size), NewHost: first, NewClass: true})
		first = false
		grandSize += t.size
		grandUsed += t.used
	}
	if len(rows) < 2 {
		return rows
	}
	rows = append(rows, display.Row{Mount: "", Size: grandSize, Used: grandUsed, Free: grandSize - grandUsed, Percent: percentOf(grandUsed, grandSize), NewClass: true})
	return rows
}

func percentOf(used, size uint64) float64 {
	if size == 0 {
		return 0
	}
	return float64(used) / float64(size) * 100
}

func reportFaults(hosts []engine.HostDoc, envelopeVersion string) (fault, anyUnreachable bool) {
	for _, host := range hosts {
		if host.State != "" && host.State != engine.HostStateMeasured {
			_, _ = fmt.Fprintf(os.Stderr, "%s%s\n", prefixError, host.Error)
			fault = true
			anyUnreachable = true
			continue
		}
		if host.Version != "" && host.Version != envelopeVersion {
			_, _ = fmt.Fprintf(os.Stderr, "%sversion skew [%s] running [%s] against [%s]\n", prefixWarning, host.Name, host.Version, envelopeVersion)
		}
		for _, mount := range host.Mounts {
			if mount.State != "" && mount.State != engine.MountStateMeasured {
				_, _ = fmt.Fprintf(os.Stderr, "%s%s\n", prefixError, mount.Error)
				fault = true
			}
		}
	}
	return fault, anyUnreachable
}

func anyMeasured(hosts []engine.HostDoc) bool {
	for _, host := range hosts {
		if host.State == engine.HostStateMeasured || host.State == "" {
			return true
		}
	}
	return false
}

func resolveSymbols(symbols string) (bool, error) {
	switch strings.ToLower(symbols) {
	case "auto":
		return !(os.Getenv("TERM") == "linux" || os.Getenv("TERM") == "dumb" || os.Getenv("NO_UTF8") != ""), nil
	case "ascii":
		return false, nil
	case "unicode":
		return true, nil
	default:
		return false, fmt.Errorf("invalid symbols [%s]", symbols)
	}
}

func resolveTheme(theme string) (bool, error) {
	switch strings.ToLower(theme) {
	case "auto":
		isTerminal := term.IsTerminal(int(os.Stdout.Fd()))
		termVar := os.Getenv("TERM")
		return isTerminal && termVar != "" && termVar != "dumb" && os.Getenv("NO_COLOR") == "" && os.Getenv("MONO") == "", nil
	case "colour", "color":
		return true, nil
	case "mono":
		return false, nil
	default:
		return false, fmt.Errorf("invalid theme [%s]", theme)
	}
}

type spaceOptions struct {
	mode    string
	filter  string
	symbols string
	theme   string
	json    bool
}

const spaceDescription = "Show storage metrics"
