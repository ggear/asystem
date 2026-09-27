package cmd

import (
	"os"
	"storage/internal/display"
	"storage/internal/engine"
	"testing"
)

func TestCmdSpace_ResolveSymbols(t *testing.T) {
	cases := []struct {
		name          string
		symbols       string
		environment   map[string]string
		want          bool
		expectedError bool
	}{
		{name: "ascii is always ascii", symbols: "ascii", environment: map[string]string{"TERM": "xterm-256color"}, want: false},
		{name: "unicode is always unicode", symbols: "unicode", environment: map[string]string{"TERM": "linux"}, want: true},
		{name: "case is not significant", symbols: "UNICODE", environment: map[string]string{"TERM": "linux"}, want: true},
		{name: "auto on a capable terminal", symbols: "auto", environment: map[string]string{"TERM": "xterm-256color"}, want: true},
		{name: "auto on a linux console", symbols: "auto", environment: map[string]string{"TERM": "linux"}, want: false},
		{name: "auto on a dumb terminal", symbols: "auto", environment: map[string]string{"TERM": "dumb"}, want: false},
		{name: "auto with NO_UTF8 set", symbols: "auto", environment: map[string]string{"TERM": "xterm-256color", "NO_UTF8": "1"}, want: false},
		{name: "an unknown value", symbols: "utf7", expectedError: true},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			setEnvironment(t, c.environment, "TERM", "NO_UTF8")
			got, err := resolveSymbols(c.symbols)
			if (err != nil) != c.expectedError {
				t.Fatalf("error: got %v want error %v", err, c.expectedError)
			}
			if err == nil && got != c.want {
				t.Errorf("useUnicode: got %v want %v", got, c.want)
			}
		})
	}
}

func TestCmdSpace_ResolveTheme(t *testing.T) {
	cases := []struct {
		name          string
		theme         string
		environment   map[string]string
		want          bool
		expectedError bool
	}{
		{name: "colour is always colour", theme: "colour", environment: map[string]string{"NO_COLOR": "1"}, want: true},
		{name: "the american spelling is accepted", theme: "color", want: true},
		{name: "mono is always mono", theme: "mono", environment: map[string]string{"TERM": "xterm-256color"}, want: false},
		{name: "auto off a terminal", theme: "auto", environment: map[string]string{"TERM": "xterm-256color"}, want: false},
		{name: "an unknown value", theme: "ansi", expectedError: true},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			setEnvironment(t, c.environment, "TERM", "NO_COLOR", "MONO")
			got, err := resolveTheme(c.theme)
			if (err != nil) != c.expectedError {
				t.Fatalf("error: got %v want error %v", err, c.expectedError)
			}
			if err == nil && got != c.want {
				t.Errorf("useColour: got %v want %v", got, c.want)
			}
		})
	}
}

func TestCmdSpace_RowsFor(t *testing.T) {
	rows := rowsFor([]engine.HostDoc{
		{Label: "mad", State: engine.HostStateMeasured, Mounts: []engine.MountDoc{
			{Mount: "/", Class: engine.ClassRoot, State: engine.MountStateMeasured, Space: &engine.SpaceFigures{SizeBytes: 400, UsedBytes: 100, FreeBytes: 300}},
			{Mount: "/share/10", Class: engine.ClassShare, State: engine.MountStateUnmounted},
			{Mount: "/backup", Class: engine.ClassBackup, State: engine.MountStateMeasured, Space: &engine.SpaceFigures{SizeBytes: 200, UsedBytes: 50, FreeBytes: 150}},
		}},
		{Label: "max", State: engine.HostStateUnreachable},
	})
	want := []display.Row{
		{Host: "mad", Mount: "/", Size: 400, Used: 100, Free: 300, Percent: 25, NewHost: true, NewClass: true},
		{Mount: "/share/10", Unmeasured: true, NewClass: true},
		{Mount: "/backup", Size: 200, Used: 50, Free: 150, Percent: 25, NewClass: true},
	}
	if len(rows) != len(want) {
		t.Fatalf("rows: got %d want %d, an unreachable host contributes none", len(rows), len(want))
	}
	for i, row := range rows {
		if row != want[i] {
			t.Errorf("row %d: got %+v want %+v", i, row, want[i])
		}
	}
}

func TestCmdSpace_EstateRows(t *testing.T) {
	measured := func(size, used uint64) *engine.SpaceFigures {
		return &engine.SpaceFigures{SizeBytes: size, UsedBytes: used, FreeBytes: size - used}
	}
	host := func(label string, mounts ...engine.MountDoc) engine.HostDoc {
		return engine.HostDoc{Label: label, State: engine.HostStateMeasured, Mounts: mounts}
	}
	cases := []struct {
		name          string
		hosts         []engine.HostDoc
		filters       []string
		want          []display.Row
		expectedError bool
	}{
		{
			name:  "a single host renders no estate block",
			hosts: []engine.HostDoc{host("mad", engine.MountDoc{Mount: "/", Class: engine.ClassRoot, State: engine.MountStateMeasured, Space: measured(100, 50)})},
			want:  nil,
		},
		{
			name: "only the subtotal row of each class is summed",
			hosts: []engine.HostDoc{
				host("mad",
					engine.MountDoc{Mount: "/", Class: engine.ClassRoot, State: engine.MountStateMeasured, Space: measured(100, 40)},
					engine.MountDoc{Mount: "/share/10", Class: engine.ClassShare, State: engine.MountStateMeasured, Space: measured(600, 300)},
					engine.MountDoc{Mount: "/share", Class: engine.ClassShare, State: engine.MountStateMeasured, Space: measured(600, 300)},
					engine.MountDoc{Mount: "/backup", Class: engine.ClassBackup, State: engine.MountStateMeasured, Space: measured(200, 100)}),
				host("max",
					engine.MountDoc{Mount: "/", Class: engine.ClassRoot, State: engine.MountStateMeasured, Space: measured(100, 60)},
					engine.MountDoc{Mount: "/share/20", Class: engine.ClassShare, State: engine.MountStateUnmounted},
					engine.MountDoc{Mount: "/share", Class: engine.ClassShare, State: engine.MountStateMeasured, Space: measured(400, 100)}),
			},
			want: []display.Row{
				{Mount: "/", Size: 200, Used: 100, Free: 100, Percent: 50, NewHost: true, NewClass: true},
				{Mount: "/share", Size: 1000, Used: 400, Free: 600, Percent: 40, NewClass: true},
				{Mount: "/backup", Size: 200, Used: 100, Free: 100, Percent: 50, NewClass: true},
				{Mount: "", Size: 1400, Used: 600, Free: 800, Percent: 600.0 / 1400 * 100, NewClass: true},
			},
		},
		{
			name: "a host carrying no subtotal contributes its share rows directly",
			hosts: []engine.HostDoc{
				host("mad",
					engine.MountDoc{Mount: "/share/10", Class: engine.ClassShare, State: engine.MountStateMeasured, Space: measured(300, 100)},
					engine.MountDoc{Mount: "/share/11", Class: engine.ClassShare, State: engine.MountStateMeasured, Space: measured(300, 200)}),
				host("max",
					engine.MountDoc{Mount: "/share/20", Class: engine.ClassShare, State: engine.MountStateMeasured, Space: measured(400, 100)}),
			},
			want: []display.Row{
				{Mount: "/share", Size: 1000, Used: 400, Free: 600, Percent: 40, NewHost: true, NewClass: true},
			},
		},
		{
			name:    "a filter naming the share level keeps its rollup and drops the grand total",
			filters: []string{"/share"},
			hosts: []engine.HostDoc{
				host("mad",
					engine.MountDoc{Mount: "/share/10", Class: engine.ClassShare, State: engine.MountStateMeasured, Space: measured(600, 300)},
					engine.MountDoc{Mount: "/share", Class: engine.ClassShare, State: engine.MountStateMeasured, Space: measured(600, 300)}),
				host("max",
					engine.MountDoc{Mount: "/share", Class: engine.ClassShare, State: engine.MountStateMeasured, Space: measured(400, 100)}),
			},
			want: []display.Row{
				{Mount: "/share", Size: 1000, Used: 400, Free: 600, Percent: 40, NewHost: true, NewClass: true},
			},
		},
		{
			name:    "a filter naming one share claims no rollup and no grand total",
			filters: []string{"/share/10"},
			hosts: []engine.HostDoc{
				host("mad", engine.MountDoc{Mount: "/share/10", Class: engine.ClassShare, State: engine.MountStateMeasured, Space: measured(600, 300)}),
				host("max", engine.MountDoc{Mount: "/share/10", Class: engine.ClassShare, State: engine.MountStateMeasured, Space: measured(400, 100)}),
			},
			want: nil,
		},
		{
			name: "an unreachable host contributes nothing",
			hosts: []engine.HostDoc{
				host("mad", engine.MountDoc{Mount: "/", Class: engine.ClassRoot, State: engine.MountStateMeasured, Space: measured(100, 40)}),
				{Label: "max", State: engine.HostStateUnreachable},
			},
			want: []display.Row{
				{Mount: "/", Size: 100, Used: 40, Free: 60, Percent: 40, NewHost: true, NewClass: true},
			},
		},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			filters := c.filters
			if filters == nil {
				filters = engine.DefaultFilters
			}
			got := estateRows(c.hosts, filters)
			if len(got) != len(c.want) {
				t.Fatalf("rows: got %d want %d, got %+v", len(got), len(c.want), got)
			}
			for i, row := range got {
				if row != c.want[i] {
					t.Errorf("row %d: got %+v want %+v", i, row, c.want[i])
				}
			}
		})
	}
}

func TestCmdSpace_ReportFaults(t *testing.T) {
	cases := []struct {
		name            string
		hosts           []engine.HostDoc
		wantFault       bool
		wantUnreachable bool
		wantMeasured    bool
		expectedError   bool
	}{
		{
			name:         "every host measured",
			hosts:        []engine.HostDoc{{Label: "mad", State: engine.HostStateMeasured, Version: "10.200.1725"}},
			wantMeasured: true,
		},
		{
			name:         "a version skew is reported but is not a fault",
			hosts:        []engine.HostDoc{{Label: "mad", State: engine.HostStateMeasured, Version: "10.200.1700"}},
			wantMeasured: true,
		},
		{
			name: "a faulted mount faults the run and leaves the host measured",
			hosts: []engine.HostDoc{{Label: "mad", State: engine.HostStateMeasured, Version: "10.200.1725", Mounts: []engine.MountDoc{
				{Mount: "/share/10", State: engine.MountStateTimedout, Error: "statfs failed [/share/10]"},
			}}},
			wantFault:    true,
			wantMeasured: true,
		},
		{
			name: "one unreachable host among reachable ones",
			hosts: []engine.HostDoc{
				{Label: "mad", State: engine.HostStateMeasured, Version: "10.200.1725"},
				{Label: "max", State: engine.HostStateUnreachable, Error: "ssh dial failed [macmini-max]"},
			},
			wantFault:       true,
			wantUnreachable: true,
			wantMeasured:    true,
		},
		{
			name:            "every host unreachable",
			hosts:           []engine.HostDoc{{Label: "max", State: engine.HostStateUnreachable, Error: "ssh dial failed [macmini-max]"}},
			wantFault:       true,
			wantUnreachable: true,
		},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			silenceStderr(t)
			fault, unreachable := reportFaults(c.hosts, "10.200.1725")
			if fault != c.wantFault {
				t.Errorf("fault: got %v want %v", fault, c.wantFault)
			}
			if unreachable != c.wantUnreachable {
				t.Errorf("unreachable: got %v want %v", unreachable, c.wantUnreachable)
			}
			if got := anyMeasured(c.hosts); got != c.wantMeasured {
				t.Errorf("anyMeasured: got %v want %v", got, c.wantMeasured)
			}
		})
	}
}

func setEnvironment(t *testing.T, environment map[string]string, names ...string) {
	t.Helper()
	for _, name := range names {
		t.Setenv(name, environment[name])
	}
}

func silenceStderr(t *testing.T) {
	t.Helper()
	sink, err := os.OpenFile(os.DevNull, os.O_WRONLY, 0)
	if err != nil {
		t.Fatal(err)
	}
	original := os.Stderr
	os.Stderr = sink
	t.Cleanup(func() {
		os.Stderr = original
		_ = sink.Close()
	})
}
