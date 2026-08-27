package display

import (
	"log/slog"
	"testing"
	"time"

	"supervisor/internal/config"
	"supervisor/internal/metric"
	"supervisor/internal/scribe"
)

func BenchmarkPagination(b *testing.B) {
	layout := compactDisplayLayout(false)
	caseRows := rows(layout, 1)
	caseCols := columns(layout, false, 1)
	buffer := scribe.EnableBuffer(slog.LevelDebug, scribe.BufferLines(caseRows))
	b.Cleanup(scribe.Disable)
	terminal := newTerminalVirtual(caseRows, caseCols, ThemeLight, false)
	display, _ := NewDisplay(metric.NewRecordCache(),
		func(bool) (Terminal, error) { return terminal, nil },
		hosts[:1], caseCols, caseRows, 0, 0, FormatCompact, false,
		config.Periods{}, true, "", buffer, 0)
	display.Compile()
	display.Load()
	display.logOverlay = true
	for range caseRows * 50 {
		scribe.Log(scribe.SourceDisplay, scribe.SubjectNone, scribe.ActionRender).Info("received", time.Now(), "examined [sdb] life [ 1] pct, computed [0.9] pct from [26.4] TB written of [3000] TB rated as [Lexar SSD NM790 4TB]")
	}
	display.logRewind()
	display.Logging()
	b.Run("cold", func(b *testing.B) {
		for range b.N {
			clear(display.logHeights)
			display.logPagination()
		}
	})
	b.Run("warm", func(b *testing.B) {
		for range b.N {
			display.logPagination()
		}
	})
	b.Run("warm_with_a_new_line", func(b *testing.B) {
		for range b.N {
			scribe.Log(scribe.SourceDisplay, scribe.SubjectNone, scribe.ActionRender).Info("received", time.Now(), "one more line arriving on the tail")
			display.logPagination()
		}
	})
}
