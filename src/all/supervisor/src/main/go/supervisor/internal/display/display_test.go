package display

import (
	"context"
	_ "embed"
	"fmt"
	"log/slog"
	"math"
	"slices"
	"strings"
	"supervisor/internal/config"
	"supervisor/internal/metric"
	"supervisor/internal/scribe"
	"testing"
	"time"

	"github.com/divan/num2words"
	"github.com/mattn/go-runewidth"
	"github.com/sergi/go-diff/diffmatchpatch"
)

func TestDisplay_Happy(t *testing.T) {
	type dimsSpec struct {
		layout    func(bool) [][]box
		rowsDelta int
		colsScale int
		colsDelta int
	}
	terminalDims := func(spec dimsSpec, useUnicode bool, hostCount int) dimensions {
		layout := spec.layout(useUnicode)
		return dimensions{
			rows(layout, hostCount) + spec.rowsDelta,
			columns(layout, useUnicode, hostCount) + resizes(layout, hostCount)*spec.colsScale + spec.colsDelta,
		}
	}
	tests := []struct {
		name              string
		dimsSpec          dimsSpec
		hostCount         int
		formats           []Format
		useUnicode        bool
		expectedDimsDelta dimensions
		expectedFormat    Format
		expectedOutput    string
	}{
		// See: displayCompactASCIISoloHost_57x10_0_3
		{
			name:              "happy_compact_host1_rows+0_colsx0+0_ascii",
			dimsSpec:          dimsSpec{layout: compactDisplayLayout},
			hostCount:         1,
			formats:           []Format{FormatCompact, FormatAuto},
			useUnicode:        false,
			expectedDimsDelta: dimensions{0, 0},
			expectedFormat:    FormatCompact,
			expectedOutput:    displayCompactASCIISoloHost_57x10_0_3,
		},
		// See: displayCompactASCIISoloHost_58x10_1_3
		{
			name:              "happy_compact_host1_rows+0_colsx0+1_ascii",
			dimsSpec:          dimsSpec{layout: compactDisplayLayout, colsDelta: 1},
			hostCount:         1,
			formats:           []Format{FormatCompact, FormatAuto},
			useUnicode:        false,
			expectedDimsDelta: dimensions{0, 0},
			expectedFormat:    FormatCompact,
			expectedOutput:    displayCompactASCIISoloHost_58x10_1_3,
		},
		// See: displayCompactASCIISoloHost_59x10_2_3
		{
			name:              "happy_compact_host1_rows+0_colsx0+2_ascii",
			dimsSpec:          dimsSpec{layout: compactDisplayLayout, colsDelta: 2},
			hostCount:         1,
			formats:           []Format{FormatCompact, FormatAuto},
			useUnicode:        false,
			expectedDimsDelta: dimensions{0, 0},
			expectedFormat:    FormatCompact,
			expectedOutput:    displayCompactASCIISoloHost_59x10_2_3,
		},
		// See: displayCompactASCIISoloHost_60x10_3_3
		{
			name:              "happy_compact_host1_rows+0_colsx0+3_ascii",
			dimsSpec:          dimsSpec{layout: compactDisplayLayout, colsDelta: 3},
			hostCount:         1,
			formats:           []Format{FormatCompact, FormatAuto},
			useUnicode:        false,
			expectedDimsDelta: dimensions{0, 0},
			expectedFormat:    FormatCompact,
			expectedOutput:    displayCompactASCIISoloHost_60x10_3_3,
		},
		// See: displayCompactASCIISoloHost_87x10
		{
			name:              "happy_compact_host1_rows+0_colsx10+0_ascii",
			dimsSpec:          dimsSpec{layout: compactDisplayLayout, colsScale: 10},
			hostCount:         1,
			formats:           []Format{FormatCompact, FormatAuto},
			useUnicode:        false,
			expectedDimsDelta: dimensions{0, 0},
			expectedFormat:    FormatCompact,
			expectedOutput:    displayCompactASCIISoloHost_87x10,
		},
		// See: displayCompactASCIIMultiHost_114x30_0_6
		{
			name:              "happy_compact_host6_rows+0_colsx0+1_ascii",
			dimsSpec:          dimsSpec{layout: compactDisplayLayout, colsDelta: 0},
			hostCount:         6,
			formats:           []Format{FormatCompact, FormatAuto},
			useUnicode:        false,
			expectedDimsDelta: dimensions{0, 0},
			expectedFormat:    FormatCompact,
			expectedOutput:    displayCompactASCIIMultiHost_114x30_0_6,
		},
		// See: displayCompactASCIIMultiHost_115x30_1_6
		{
			name:              "happy_compact_host6_rows+0_colsx0+1_ascii",
			dimsSpec:          dimsSpec{layout: compactDisplayLayout, colsDelta: 1},
			hostCount:         6,
			formats:           []Format{FormatCompact, FormatAuto},
			useUnicode:        false,
			expectedDimsDelta: dimensions{0, 0},
			expectedFormat:    FormatCompact,
			expectedOutput:    displayCompactASCIIMultiHost_115x30_1_6,
		},
		// See: displayCompactASCIIMultiHost_116x30_2_6
		{
			name:              "happy_compact_host6_rows+0_colsx0+2_ascii",
			dimsSpec:          dimsSpec{layout: compactDisplayLayout, colsDelta: 2},
			hostCount:         6,
			formats:           []Format{FormatCompact, FormatAuto},
			useUnicode:        false,
			expectedDimsDelta: dimensions{0, 0},
			expectedFormat:    FormatCompact,
			expectedOutput:    displayCompactASCIIMultiHost_116x30_2_6,
		},
		// See: displayCompactASCIIMultiHost_117x30_3_6
		{
			name:              "happy_compact_host6_rows+0_colsx0+3_ascii",
			dimsSpec:          dimsSpec{layout: compactDisplayLayout, colsDelta: 3},
			hostCount:         6,
			formats:           []Format{FormatCompact, FormatAuto},
			useUnicode:        false,
			expectedDimsDelta: dimensions{0, 0},
			expectedFormat:    FormatCompact,
			expectedOutput:    displayCompactASCIIMultiHost_117x30_3_6,
		},
		// See: displayCompactASCIIMultiHost_118x30_4_6
		{
			name:              "happy_compact_host6_rows+0_colsx0+4_ascii",
			dimsSpec:          dimsSpec{layout: compactDisplayLayout, colsDelta: 4},
			hostCount:         6,
			formats:           []Format{FormatCompact, FormatAuto},
			useUnicode:        false,
			expectedDimsDelta: dimensions{0, 0},
			expectedFormat:    FormatCompact,
			expectedOutput:    displayCompactASCIIMultiHost_118x30_4_6,
		},
		// See: displayCompactASCIIMultiHost_119x30_5_6
		{
			name:              "happy_compact_host6_rows+0_colsx0+5_ascii",
			dimsSpec:          dimsSpec{layout: compactDisplayLayout, colsDelta: 5},
			hostCount:         6,
			formats:           []Format{FormatCompact, FormatAuto},
			useUnicode:        false,
			expectedDimsDelta: dimensions{0, 0},
			expectedFormat:    FormatCompact,
			expectedOutput:    displayCompactASCIIMultiHost_119x30_5_6,
		},
		// See: displayCompactASCIIMultiHost_120x30_6_6_Scales120x33
		{
			name:              "happy_compact_host6_rows+0_colsx0+6_ascii",
			dimsSpec:          dimsSpec{layout: compactDisplayLayout, colsDelta: 6},
			hostCount:         6,
			formats:           []Format{FormatCompact, FormatAuto},
			useUnicode:        false,
			expectedDimsDelta: dimensions{0, 0},
			expectedFormat:    FormatCompact,
			expectedOutput:    displayCompactASCIIMultiHost_120x30_6_6_Scales120x33,
		},
		{
			name:              "happy_compact_host6_rows+3_colsx0+6_ascii",
			dimsSpec:          dimsSpec{layout: compactDisplayLayout, rowsDelta: 3, colsDelta: 6},
			hostCount:         6,
			formats:           []Format{FormatCompact, FormatAuto},
			useUnicode:        false,
			expectedDimsDelta: dimensions{0, 0},
			expectedFormat:    FormatCompact,
		},
		// See: displayCompactASCIIMultiHost_128x30_Scales128x33
		{
			name:              "happy_compact_host6_rows+0_colsx0+14_ascii",
			dimsSpec:          dimsSpec{layout: compactDisplayLayout, colsDelta: 14},
			hostCount:         6,
			formats:           []Format{FormatCompact, FormatAuto},
			useUnicode:        false,
			expectedDimsDelta: dimensions{0, 0},
			expectedFormat:    FormatCompact,
			expectedOutput:    displayCompactASCIIMultiHost_128x30_Scales128x33,
		},
		{
			name:              "happy_compact_host6_rows+3_colsx0+14_ascii",
			dimsSpec:          dimsSpec{layout: compactDisplayLayout, rowsDelta: 3, colsDelta: 14},
			hostCount:         6,
			formats:           []Format{FormatCompact, FormatAuto},
			useUnicode:        false,
			expectedDimsDelta: dimensions{0, 0},
			expectedFormat:    FormatCompact,
		},
		// See: displayCompactASCIIMultiHost_175x30
		{
			name:              "happy_compact_host6_rows+0_colsx0+61_ascii",
			dimsSpec:          dimsSpec{layout: compactDisplayLayout, colsDelta: 61},
			hostCount:         6,
			formats:           []Format{FormatCompact, FormatAuto},
			useUnicode:        false,
			expectedDimsDelta: dimensions{0, 0},
			expectedFormat:    FormatCompact,
			expectedOutput:    displayCompactASCIIMultiHost_175x30,
		},
		{
			name:              "happy_compact_host3_rows+0_colsx0+61_ascii",
			dimsSpec:          dimsSpec{layout: compactDisplayLayout, colsDelta: 61},
			hostCount:         3,
			formats:           []Format{FormatCompact, FormatAuto},
			useUnicode:        false,
			expectedDimsDelta: dimensions{0, 0},
			expectedFormat:    FormatCompact,
		},
		{
			name:              "happy_compact_host7_rows+0_colsx0+61_ascii",
			dimsSpec:          dimsSpec{layout: compactDisplayLayout, colsDelta: 61},
			hostCount:         7,
			formats:           []Format{FormatCompact, FormatAuto},
			useUnicode:        false,
			expectedDimsDelta: dimensions{0, 0},
			expectedFormat:    FormatCompact,
		},
		// See: displayRelaxedASCIISoloHost_88x14_0_4_Scales120128x33
		{
			name:              "happy_relaxed_host1_rows+0_colsx0+0_ascii",
			dimsSpec:          dimsSpec{layout: relaxedDisplayLayout},
			hostCount:         1,
			formats:           []Format{FormatRelaxed, FormatAuto},
			useUnicode:        false,
			expectedDimsDelta: dimensions{0, 0},
			expectedFormat:    FormatRelaxed,
			expectedOutput:    displayRelaxedASCIISoloHost_88x14_0_4_Scales120128x33,
		},
		{
			name:              "happy_relaxed_host1_rows+0_colsx0+0_unicode",
			dimsSpec:          dimsSpec{layout: relaxedDisplayLayout},
			hostCount:         1,
			formats:           []Format{FormatRelaxed, FormatAuto},
			useUnicode:        true,
			expectedDimsDelta: dimensions{0, 0},
			expectedFormat:    FormatRelaxed,
			expectedOutput:    displayRelaxedUnicodeSoloHost_88x15_0_4,
		},
		{
			name:              "happy_relaxed_host1_rows+18_colsx8+0_ascii",
			dimsSpec:          dimsSpec{layout: relaxedDisplayLayout, rowsDelta: 18, colsScale: 8},
			hostCount:         1,
			formats:           []Format{FormatRelaxed, FormatAuto},
			useUnicode:        false,
			expectedDimsDelta: dimensions{0, 0},
			expectedFormat:    FormatRelaxed,
		},
		{
			name:              "happy_relaxed_host1_rows+18_colsx8+0_unicode",
			dimsSpec:          dimsSpec{layout: relaxedDisplayLayout, rowsDelta: 18, colsScale: 8},
			hostCount:         1,
			formats:           []Format{FormatRelaxed, FormatAuto},
			useUnicode:        true,
			expectedDimsDelta: dimensions{0, 0},
			expectedFormat:    FormatRelaxed,
		},
		{
			name:              "happy_relaxed_host1_rows+18_colsx10+0_ascii",
			dimsSpec:          dimsSpec{layout: relaxedDisplayLayout, rowsDelta: 18, colsScale: 10},
			hostCount:         1,
			formats:           []Format{FormatRelaxed, FormatAuto},
			useUnicode:        false,
			expectedDimsDelta: dimensions{0, 0},
			expectedFormat:    FormatRelaxed,
		},
		{
			name:              "happy_relaxed_host1_rows+18_colsx10+0_unicode",
			dimsSpec:          dimsSpec{layout: relaxedDisplayLayout, rowsDelta: 18, colsScale: 10},
			hostCount:         1,
			formats:           []Format{FormatRelaxed, FormatAuto},
			useUnicode:        true,
			expectedDimsDelta: dimensions{0, 0},
			expectedFormat:    FormatRelaxed,
		},
		// See: displayRelaxedUnicodeSoloHost_89x16_1_4
		{
			name:              "happy_relaxed_host1_rows+0_colsx0+1_unicode",
			dimsSpec:          dimsSpec{layout: relaxedDisplayLayout, colsDelta: 1},
			hostCount:         1,
			formats:           []Format{FormatRelaxed, FormatAuto},
			useUnicode:        true,
			expectedDimsDelta: dimensions{0, 0},
			expectedFormat:    FormatRelaxed,
			expectedOutput:    displayRelaxedUnicodeSoloHost_89x16_1_4,
		},
		{
			name:              "happy_relaxed_host1_rows+0_colsx0+1_ascii",
			dimsSpec:          dimsSpec{layout: relaxedDisplayLayout, colsDelta: 1},
			hostCount:         1,
			formats:           []Format{FormatRelaxed, FormatAuto},
			useUnicode:        false,
			expectedDimsDelta: dimensions{0, 0},
			expectedFormat:    FormatRelaxed,
		},
		// See: displayRelaxedUnicodeSoloHost_90x16_2_4
		{
			name:              "happy_relaxed_host1_rows+0_colsx0+2_unicode",
			dimsSpec:          dimsSpec{layout: relaxedDisplayLayout, colsDelta: 2},
			hostCount:         1,
			formats:           []Format{FormatRelaxed, FormatAuto},
			useUnicode:        true,
			expectedDimsDelta: dimensions{0, 0},
			expectedFormat:    FormatRelaxed,
			expectedOutput:    displayRelaxedUnicodeSoloHost_90x16_2_4,
		},
		{
			name:              "happy_relaxed_host1_rows+0_colsx0+2_ascii",
			dimsSpec:          dimsSpec{layout: relaxedDisplayLayout, colsDelta: 2},
			hostCount:         1,
			formats:           []Format{FormatRelaxed, FormatAuto},
			useUnicode:        false,
			expectedDimsDelta: dimensions{0, 0},
			expectedFormat:    FormatRelaxed,
		},
		// See: displayRelaxedUnicodeSoloHost_91x16_3_4_Scales287x55
		{
			name:              "happy_relaxed_host1_rows+0_colsx0+3_unicode",
			dimsSpec:          dimsSpec{layout: relaxedDisplayLayout, colsDelta: 3},
			hostCount:         1,
			formats:           []Format{FormatRelaxed, FormatAuto},
			useUnicode:        true,
			expectedDimsDelta: dimensions{0, 0},
			expectedFormat:    FormatRelaxed,
			expectedOutput:    displayRelaxedUnicodeSoloHost_91x16_3_4_Scales287x55,
		},
		{
			name:              "happy_relaxed_host1_rows+0_colsx0+3_ascii",
			dimsSpec:          dimsSpec{layout: relaxedDisplayLayout, colsDelta: 3},
			hostCount:         1,
			formats:           []Format{FormatRelaxed, FormatAuto},
			useUnicode:        false,
			expectedDimsDelta: dimensions{0, 0},
			expectedFormat:    FormatRelaxed,
		},
		{
			name:              "happy_relaxed_host1_rows+39_colsx49+3_unicode",
			dimsSpec:          dimsSpec{layout: relaxedDisplayLayout, rowsDelta: 39, colsDelta: 3, colsScale: 49},
			hostCount:         1,
			formats:           []Format{FormatRelaxed, FormatAuto},
			useUnicode:        true,
			expectedDimsDelta: dimensions{0, 0},
			expectedFormat:    FormatRelaxed,
		},
		{
			name:              "happy_relaxed_host1_rows+39_colsx49+3_ascii",
			dimsSpec:          dimsSpec{layout: relaxedDisplayLayout, rowsDelta: 39, colsDelta: 3, colsScale: 49},
			hostCount:         1,
			formats:           []Format{FormatRelaxed, FormatAuto},
			useUnicode:        false,
			expectedDimsDelta: dimensions{0, 0},
			expectedFormat:    FormatRelaxed,
		},
		// See: displayRelaxedUnicodeSoloHost_92x16_4_4
		{
			name:              "happy_relaxed_host1_rows+0_colsx0+4_unicode",
			dimsSpec:          dimsSpec{layout: relaxedDisplayLayout, colsDelta: 4},
			hostCount:         1,
			formats:           []Format{FormatRelaxed, FormatAuto},
			useUnicode:        true,
			expectedDimsDelta: dimensions{0, 0},
			expectedFormat:    FormatRelaxed,
			expectedOutput:    displayRelaxedUnicodeSoloHost_92x16_4_4,
		},
		{
			name:              "happy_relaxed_host1_rows+0_colsx0+4_ascii",
			dimsSpec:          dimsSpec{layout: relaxedDisplayLayout, colsDelta: 4},
			hostCount:         1,
			formats:           []Format{FormatRelaxed, FormatAuto},
			useUnicode:        false,
			expectedDimsDelta: dimensions{0, 0},
			expectedFormat:    FormatRelaxed,
		},
		// See: displayRelaxedASCIIMultiHost_176x45_0_8
		{
			name:              "happy_relaxed_host6_rows+0_colsx0+0_ascii",
			dimsSpec:          dimsSpec{layout: relaxedDisplayLayout},
			hostCount:         6,
			formats:           []Format{FormatRelaxed, FormatAuto},
			useUnicode:        false,
			expectedDimsDelta: dimensions{0, 0},
			expectedFormat:    FormatRelaxed,
			expectedOutput:    displayRelaxedASCIIMultiHost_176x45_0_8,
		},
		{
			name:              "happy_relaxed_host6_rows+0_colsx0+0_unicode",
			dimsSpec:          dimsSpec{layout: relaxedDisplayLayout},
			hostCount:         6,
			formats:           []Format{FormatRelaxed, FormatAuto},
			useUnicode:        true,
			expectedDimsDelta: dimensions{0, 0},
			expectedFormat:    FormatRelaxed,
		},
		// See: displayRelaxedUnicodeMultiHost_176x48_0_8
		{
			name:              "happy_relaxed_host6_rows+0_colsx0+0_unicode",
			dimsSpec:          dimsSpec{layout: relaxedDisplayLayout},
			hostCount:         6,
			formats:           []Format{FormatRelaxed, FormatAuto},
			useUnicode:        true,
			expectedDimsDelta: dimensions{0, 0},
			expectedFormat:    FormatRelaxed,
			expectedOutput:    displayRelaxedUnicodeMultiHost_176x48_0_8,
		},
		{
			name:              "happy_relaxed_host6_rows+0_colsx0+0_ascii",
			dimsSpec:          dimsSpec{layout: relaxedDisplayLayout},
			hostCount:         6,
			formats:           []Format{FormatRelaxed, FormatAuto},
			useUnicode:        false,
			expectedDimsDelta: dimensions{0, 0},
			expectedFormat:    FormatRelaxed,
		},
		// See: displayRelaxedUnicodeMultiHost_177x48_1_8
		{
			name:              "happy_relaxed_host6_rows+0_colsx0+1_unicode",
			dimsSpec:          dimsSpec{layout: relaxedDisplayLayout, colsDelta: 1},
			hostCount:         6,
			formats:           []Format{FormatRelaxed, FormatAuto},
			useUnicode:        true,
			expectedDimsDelta: dimensions{0, 0},
			expectedFormat:    FormatRelaxed,
			expectedOutput:    displayRelaxedUnicodeMultiHost_177x48_1_8,
		},
		{
			name:              "happy_relaxed_host6_rows+0_colsx0+1_ascii",
			dimsSpec:          dimsSpec{layout: relaxedDisplayLayout, colsDelta: 1},
			hostCount:         6,
			formats:           []Format{FormatRelaxed, FormatAuto},
			useUnicode:        false,
			expectedDimsDelta: dimensions{0, 0},
			expectedFormat:    FormatRelaxed,
		},
		// See: displayRelaxedUnicodeMultiHost_178x48_2_8
		{
			name:              "happy_relaxed_host6_rows+0_colsx0+2_unicode",
			dimsSpec:          dimsSpec{layout: relaxedDisplayLayout, colsDelta: 2},
			hostCount:         6,
			formats:           []Format{FormatRelaxed, FormatAuto},
			useUnicode:        true,
			expectedDimsDelta: dimensions{0, 0},
			expectedFormat:    FormatRelaxed,
			expectedOutput:    displayRelaxedUnicodeMultiHost_178x48_2_8,
		},
		{
			name:              "happy_relaxed_host6_rows+0_colsx0+2_ascii",
			dimsSpec:          dimsSpec{layout: relaxedDisplayLayout, colsDelta: 2},
			hostCount:         6,
			formats:           []Format{FormatRelaxed, FormatAuto},
			useUnicode:        false,
			expectedDimsDelta: dimensions{0, 0},
			expectedFormat:    FormatRelaxed,
		},
		// See: displayRelaxedUnicodeMultiHost_179x48_3_8
		{
			name:              "happy_relaxed_host6_rows+0_colsx0+3_unicode",
			dimsSpec:          dimsSpec{layout: relaxedDisplayLayout, colsDelta: 3},
			hostCount:         6,
			formats:           []Format{FormatRelaxed, FormatAuto},
			useUnicode:        true,
			expectedDimsDelta: dimensions{0, 0},
			expectedFormat:    FormatRelaxed,
			expectedOutput:    displayRelaxedUnicodeMultiHost_179x48_3_8,
		},
		{
			name:              "happy_relaxed_host6_rows+0_colsx0+3_ascii",
			dimsSpec:          dimsSpec{layout: relaxedDisplayLayout, colsDelta: 3},
			hostCount:         6,
			formats:           []Format{FormatRelaxed, FormatAuto},
			useUnicode:        false,
			expectedDimsDelta: dimensions{0, 0},
			expectedFormat:    FormatRelaxed,
		},
		// See: displayRelaxedUnicodeMultiHost_180x48_4_8
		{
			name:              "happy_relaxed_host6_rows+0_colsx0+4_unicode",
			dimsSpec:          dimsSpec{layout: relaxedDisplayLayout, colsDelta: 4},
			hostCount:         6,
			formats:           []Format{FormatRelaxed, FormatAuto},
			useUnicode:        true,
			expectedDimsDelta: dimensions{0, 0},
			expectedFormat:    FormatRelaxed,
			expectedOutput:    displayRelaxedUnicodeMultiHost_180x48_4_8,
		},
		{
			name:              "happy_relaxed_host6_rows+0_colsx0+4_ascii",
			dimsSpec:          dimsSpec{layout: relaxedDisplayLayout, colsDelta: 4},
			hostCount:         6,
			formats:           []Format{FormatRelaxed, FormatAuto},
			useUnicode:        false,
			expectedDimsDelta: dimensions{0, 0},
			expectedFormat:    FormatRelaxed,
		},
		// See: displayRelaxedUnicodeMultiHost_181x48_5_8
		{
			name:              "happy_relaxed_host6_rows+0_colsx0+5_unicode",
			dimsSpec:          dimsSpec{layout: relaxedDisplayLayout, colsDelta: 5},
			hostCount:         6,
			formats:           []Format{FormatRelaxed, FormatAuto},
			useUnicode:        true,
			expectedDimsDelta: dimensions{0, 0},
			expectedFormat:    FormatRelaxed,
			expectedOutput:    displayRelaxedUnicodeMultiHost_181x48_5_8,
		},
		{
			name:              "happy_relaxed_host6_rows+0_colsx0+5_ascii",
			dimsSpec:          dimsSpec{layout: relaxedDisplayLayout, colsDelta: 5},
			hostCount:         6,
			formats:           []Format{FormatRelaxed, FormatAuto},
			useUnicode:        false,
			expectedDimsDelta: dimensions{0, 0},
			expectedFormat:    FormatRelaxed,
		},
		// See: displayRelaxedUnicodeMultiHost_182x48_6_8
		{
			name:              "happy_relaxed_host6_rows+0_colsx0+6_unicode",
			dimsSpec:          dimsSpec{layout: relaxedDisplayLayout, colsDelta: 6},
			hostCount:         6,
			formats:           []Format{FormatRelaxed, FormatAuto},
			useUnicode:        true,
			expectedDimsDelta: dimensions{0, 0},
			expectedFormat:    FormatRelaxed,
			expectedOutput:    displayRelaxedUnicodeMultiHost_182x48_6_8,
		},
		{
			name:              "happy_relaxed_host6_rows+0_colsx0+6_ascii",
			dimsSpec:          dimsSpec{layout: relaxedDisplayLayout, colsDelta: 6},
			hostCount:         6,
			formats:           []Format{FormatRelaxed, FormatAuto},
			useUnicode:        false,
			expectedDimsDelta: dimensions{0, 0},
			expectedFormat:    FormatRelaxed,
		},
		// See: displayRelaxedUnicodeMultiHost_183x48_7_8_Scales287x55
		{
			name:              "happy_relaxed_host6_rows+0_colsx0+7_unicode",
			dimsSpec:          dimsSpec{layout: relaxedDisplayLayout, colsDelta: 7},
			hostCount:         6,
			formats:           []Format{FormatRelaxed, FormatAuto},
			useUnicode:        true,
			expectedDimsDelta: dimensions{0, 0},
			expectedFormat:    FormatRelaxed,
			expectedOutput:    displayRelaxedUnicodeMultiHost_183x48_7_8_Scales287x55,
		},
		{
			name:              "happy_relaxed_host6_rows+0_colsx0+7_ascii",
			dimsSpec:          dimsSpec{layout: relaxedDisplayLayout, colsDelta: 7},
			hostCount:         6,
			formats:           []Format{FormatRelaxed, FormatAuto},
			useUnicode:        false,
			expectedDimsDelta: dimensions{0, 0},
			expectedFormat:    FormatRelaxed,
		},
		{
			name:              "happy_relaxed_host6_rows+24_colsx13+7_unicode",
			dimsSpec:          dimsSpec{layout: relaxedDisplayLayout, rowsDelta: 24, colsDelta: 7, colsScale: 13},
			hostCount:         6,
			formats:           []Format{FormatRelaxed, FormatAuto},
			useUnicode:        true,
			expectedDimsDelta: dimensions{0, 0},
			expectedFormat:    FormatRelaxed,
		},
		{
			name:              "happy_relaxed_host6_rows+27_colsx13+10_ascii",
			dimsSpec:          dimsSpec{layout: relaxedDisplayLayout, rowsDelta: 27, colsDelta: 7, colsScale: 13},
			hostCount:         6,
			formats:           []Format{FormatRelaxed, FormatAuto},
			useUnicode:        false,
			expectedDimsDelta: dimensions{0, 0},
			expectedFormat:    FormatRelaxed,
		},
		// See: displayRelaxedUnicodeMultiHost_184x48_8_8
		{
			name:              "happy_relaxed_host6_rows+0_colsx0+8_unicode",
			dimsSpec:          dimsSpec{layout: relaxedDisplayLayout, colsDelta: 8},
			hostCount:         6,
			formats:           []Format{FormatRelaxed, FormatAuto},
			useUnicode:        true,
			expectedDimsDelta: dimensions{0, 0},
			expectedFormat:    FormatRelaxed,
			expectedOutput:    displayRelaxedUnicodeMultiHost_184x48_8_8,
		},
		{
			name:              "happy_relaxed_host6_rows+0_colsx0+8_ascii",
			dimsSpec:          dimsSpec{layout: relaxedDisplayLayout, colsDelta: 8},
			hostCount:         6,
			formats:           []Format{FormatRelaxed, FormatAuto},
			useUnicode:        false,
			expectedDimsDelta: dimensions{0, 0},
			expectedFormat:    FormatRelaxed,
		},
		{
			name:              "happy_relaxed_host3_rows+0_colsx0+8_unicode",
			dimsSpec:          dimsSpec{layout: relaxedDisplayLayout, colsDelta: 8},
			hostCount:         3,
			formats:           []Format{FormatRelaxed, FormatAuto},
			useUnicode:        true,
			expectedDimsDelta: dimensions{0, 0},
			expectedFormat:    FormatRelaxed,
		},
		{
			name:              "happy_relaxed_host7_rows+0_colsx0+8_unicode",
			dimsSpec:          dimsSpec{layout: relaxedDisplayLayout, colsDelta: 8},
			hostCount:         7,
			formats:           []Format{FormatRelaxed, FormatAuto},
			useUnicode:        true,
			expectedDimsDelta: dimensions{0, 0},
			expectedFormat:    FormatRelaxed,
		},
	}
	for _, testCase := range tests {
		scribe.EnableStdout(slog.LevelDebug)
		t.Run(testCase.name, func(t *testing.T) {
			caseHosts := []string(nil)
			if testCase.hostCount > 0 {
				caseHosts = hosts[:testCase.hostCount]
			}
			caseTerminalDims := terminalDims(testCase.dimsSpec, testCase.useUnicode, testCase.hostCount)
			for _, attemptedFormat := range testCase.formats {
				cache := metric.NewRecordCache()
				terminal := newTerminalVirtual(caseTerminalDims.rows, caseTerminalDims.cols, ThemeLight, testCase.useUnicode)
				display, newErr := NewDisplay(
					caseHosts,
					config.Periods{},
					"",
					true,
					testCase.useUnicode,
					attemptedFormat,
					caseTerminalDims.cols,
					caseTerminalDims.rows,
					0,
					0,
					0,
					func(useUnicode bool) (Terminal, error) { return terminal, nil },
					cache,
					nil,
				)
				if newErr != nil {
					t.Fatalf("New Display err = %v, expected nil", newErr)
				}
				renderedFormat, compileErr := display.Compile()
				if compileErr != nil {
					t.Fatalf("unexpected error: %v", compileErr)
				}
				if renderedFormat != testCase.expectedFormat {
					t.Fatalf("Compile Display renderedFormat = %v, expected renderedFormat %v", renderedFormat, testCase.expectedFormat)
				}
				ctx, cancel := context.WithCancel(context.Background())
				defer cancel()
				loadErr := display.Load()
				if loadErr != nil {
					fmt.Print("... failed\n")
					t.Fatalf("Get Display err = %v, expected nil", loadErr)
				}
				services := []string{
					"homeassistant",
					"influxdb3",
					"internet",
					"mariadb",
					"mylongnamedservice",
					"mlflow",
					"mlserver",
					"nginx",
					"openra",
					"plex",
					"postgres",
					"wrangle",
					"zigbee2mqtt",
				}
				record := func(id metric.ID, i int) metric.Record {
					switch id {
					case metric.MetricServiceName:
						return metric.NewRecord(*metric.NewStringValue(true, services[i], true, services[i]))
					case metric.MetricServiceVersion:
						return metric.NewRecord(*metric.NewStringValue(true, fmt.Sprintf("10.100.%d", 1001+i), true, fmt.Sprintf("10.100.%d", 1001+i)))
					case metric.MetricServiceBackupStatus:
						return metric.NewRecord(*metric.NewBoolValue(false, true))
					case metric.MetricServiceHealthStatus, metric.MetricServiceConfiguredStatus, metric.MetricService:
						return metric.NewRecord(*metric.NewBoolValue(true, true))
					case metric.MetricServiceRestartCount:
						return metric.NewRecord(*metric.NewIntValue(true, 0, true, 0))
					case metric.MetricServiceUpTime:
						return metric.NewRecord(*metric.NewFloatValue(true, float64((i+1)*2000000), false, float64((i+1)*2000000)))
					default:
						value := []int8{100, 50, 0}[i%3]
						return metric.NewRecord(*metric.NewIntValue(true, value, true, value))
					}
				}
				for host, ids := range cache.ListenerIDs() {
					slices.Sort(ids)
					for _, id := range ids {
						if metric.GetIDKind(id) != metric.MetricKindService {
							value := []int8{0, 100, 50}[int(id)%3]
							record := metric.NewRecord(*metric.NewIntValue(true, value, true, value))
							cache.Store(metric.NewRecordGUID(id, host), &record)
						}
					}
					for i := range services {
						for _, id := range metric.GetIDsByKind([]metric.MetricKind{metric.MetricKindService}) {
							record := record(id, i)
							cache.Store(metric.NewServiceRecordGUID(id, host, fmt.Sprintf("test-svc-%02d", i)), &record)
						}
					}
				}
				drawn := make(chan struct{})
				go func() {
					display.Draw(ctx, cancel)
					close(drawn)
				}()
				display.Close()
				<-drawn
				dims := terminal.dimensions()
				if attemptedFormat == testCase.formats[0] {
					fmt.Printf("Terminal [%dx%d] attempting [%s] -> Display [%dx%d] rendered [%s]:\n", caseTerminalDims.cols, caseTerminalDims.rows, attemptedFormat, dims.cols, dims.rows, renderedFormat)
					fmt.Print(terminal.string(true))
				}
				expectedDims := dimensions{
					testCase.expectedDimsDelta.rows + caseTerminalDims.rows,
					testCase.expectedDimsDelta.cols + caseTerminalDims.cols,
				}
				if dims != expectedDims {
					t.Fatalf("Got dims = %q, expected %q", dims, expectedDims)
				}
				terminalOutput := terminal.string(false)
				for _, line := range strings.SplitN(terminalOutput, "\n", 11) {
					trimmed := strings.TrimRight(line, " \t")
					trailing := len(line) - len(trimmed)
					if trailing != 0 && trailing != len(line)/2 {
						t.Fatalf("Display not expanded to terminal dimensions")
					}
				}
				if attemptedFormat == testCase.formats[0] && testCase.expectedOutput != "" {
					if strings.TrimSpace(terminalOutput) != strings.TrimSpace(testCase.expectedOutput) {
						fmt.Printf("---\nUnexpected display output:\n%s", diffDisplay(strings.TrimSpace(testCase.expectedOutput), strings.TrimSpace(terminalOutput)))
						t.FailNow()
					}
				}
			}
		})
	}
}

func TestDisplay_Sad(t *testing.T) {
	tests := []struct {
		name       string
		hosts      []string
		format     Format
		useUnicode bool
		dims       dimensions
	}{
		{
			name:       "sad_host1_rows-1_cols-1_ascii",
			hosts:      hosts[:1],
			format:     FormatAuto,
			useUnicode: false,
			dims:       dimensions{rows(compactDisplayLayout(false), 1) - 1, columns(compactDisplayLayout(false), false, 1) - 1},
		},
		{
			name:       "sad_host1_rows-1_cols_ok_ascii",
			hosts:      hosts[:1],
			format:     FormatAuto,
			useUnicode: false,
			dims:       dimensions{rows(compactDisplayLayout(false), 1) - 1, columns(compactDisplayLayout(false), false, 1)},
		},
		{
			name:       "sad_host1_rows0_ascii",
			hosts:      hosts[:1],
			format:     FormatAuto,
			useUnicode: false,
			dims:       dimensions{0, columns(compactDisplayLayout(false), false, 1)},
		},
		{
			name:       "sad_host1_rows-1_cols-1_unicode",
			hosts:      hosts[:1],
			format:     FormatAuto,
			useUnicode: true,
			dims:       dimensions{rows(compactDisplayLayout(true), 1) - 1, columns(compactDisplayLayout(true), true, 1) - 1},
		},
		{
			name:       "sad_host1_rows-1_cols_ok_unicode",
			hosts:      hosts[:1],
			format:     FormatAuto,
			useUnicode: true,
			dims:       dimensions{rows(compactDisplayLayout(true), 1) - 1, columns(compactDisplayLayout(true), true, 1)},
		},
		{
			name:       "sad_host1_rows0_unicode",
			hosts:      hosts[:1],
			format:     FormatAuto,
			useUnicode: true,
			dims:       dimensions{0, columns(compactDisplayLayout(true), true, 1)},
		},
		{
			name:       "sad_host3_rows-1_cols-1_ascii",
			hosts:      hosts[:3],
			format:     FormatAuto,
			useUnicode: false,
			dims:       dimensions{rows(compactDisplayLayout(false), 3) - 1, columns(compactDisplayLayout(false), false, 3) - 1},
		},
		{
			name:       "sad_host3_rows-1_cols-1_unicode",
			hosts:      hosts[:3],
			format:     FormatAuto,
			useUnicode: true,
			dims:       dimensions{rows(compactDisplayLayout(true), 3) - 1, columns(compactDisplayLayout(true), true, 3) - 1},
		},
		{
			name:       "sad_host6_rows-1_cols-1_ascii",
			hosts:      hosts[:6],
			format:     FormatAuto,
			useUnicode: false,
			dims:       dimensions{rows(compactDisplayLayout(false), 6) - 1, columns(compactDisplayLayout(false), false, 6) - 1},
		},
		{
			name:       "sad_host6_rows-1_cols-1_unicode",
			hosts:      hosts[:6],
			format:     FormatAuto,
			useUnicode: true,
			dims:       dimensions{rows(compactDisplayLayout(true), 6) - 1, columns(compactDisplayLayout(true), true, 6) - 1},
		},
		{
			name:       "sad_host0_ascii",
			hosts:      nil,
			format:     FormatAuto,
			useUnicode: false,
			dims:       dimensions{1, 1},
		},
		{
			name:       "sad_host0_unicode",
			hosts:      nil,
			format:     FormatAuto,
			useUnicode: true,
			dims:       dimensions{1, 1},
		},
		{
			name:       "sad_invalid_format_ascii",
			hosts:      hosts[:1],
			format:     Format(-1),
			useUnicode: false,
			dims:       dimensions{rows(compactDisplayLayout(false), 1), columns(compactDisplayLayout(false), false, 1)},
		},
		{
			name:       "sad_invalid_format_unicode",
			hosts:      hosts[:1],
			format:     Format(999),
			useUnicode: true,
			dims:       dimensions{rows(compactDisplayLayout(true), 1), columns(compactDisplayLayout(true), true, 1)},
		},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			display, err := NewDisplay(
				testCase.hosts,
				config.Periods{},
				"",
				true,
				testCase.useUnicode,
				testCase.format,
				testCase.dims.cols,
				testCase.dims.rows,
				0,
				0,
				0,
				func(useUnicode bool) (Terminal, error) {
					return newTerminalVirtual(testCase.dims.rows, testCase.dims.cols, ThemeDark, useUnicode), nil
				},
				metric.NewRecordCache(),
				nil,
			)
			if err != nil {
				t.Fatalf("New Display err = %v, expected nil", err)
			}
			if _, err = display.Compile(); err == nil {
				t.Fatalf("expected error but got nil")
			}
		})
	}
}

func TestDisplay_FormatDurationShort(t *testing.T) {
	year := 365.0 * 24 * 60 * 60
	tests := []struct {
		name     string
		seconds  float64
		expected string
	}{
		{
			name:     "happy_sub_second",
			seconds:  0.5,
			expected: "0s",
		},
		{
			name:     "happy_one_second",
			seconds:  1,
			expected: "1s",
		},
		{
			name:     "happy_seconds_floor",
			seconds:  1.9,
			expected: "1s",
		},
		{
			name:     "happy_seconds_max",
			seconds:  59,
			expected: "59s",
		},
		{
			name:     "happy_one_minute",
			seconds:  60,
			expected: "1m",
		},
		{
			name:     "happy_minutes_max",
			seconds:  59*60 + 59,
			expected: "59m",
		},
		{
			name:     "happy_one_hour",
			seconds:  60 * 60,
			expected: "1h",
		},
		{
			name:     "happy_hours_max",
			seconds:  23*60*60 + 59*60,
			expected: "23h",
		},
		{
			name:     "happy_one_day",
			seconds:  24 * 60 * 60,
			expected: "1d",
		},
		{
			name:     "happy_three_days",
			seconds:  24*60*60*3 + 13,
			expected: "3d",
		},
		{
			name:     "happy_one_year",
			seconds:  year,
			expected: "1y",
		},
		{
			name:     "happy_max_year",
			seconds:  999 * year,
			expected: "999y",
		},
		{
			name:     "sad_nan",
			seconds:  math.NaN(),
			expected: "~",
		},
		{
			name:     "sad_pos_inf",
			seconds:  math.Inf(1),
			expected: "~",
		},
		{
			name:     "sad_neg_inf",
			seconds:  math.Inf(-1),
			expected: "~",
		},
		{
			name:     "sad_negative",
			seconds:  -1,
			expected: "~",
		},
		{
			name:     "sad_over_max_year",
			seconds:  1000 * year,
			expected: "~",
		},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			if got := duration(testCase.seconds); got != testCase.expected {
				t.Fatalf("Got duration = %q, expected %q", got, testCase.expected)
			}
		})
	}
}

func TestDisplay_VirtualTerminal(t *testing.T) {
	tests := []struct {
		name          string
		text          string
		colour        colour
		expectedError bool
	}{
		{
			name:          "happy_string",
			text:          "Hello world!",
			colour:        colourChat,
			expectedError: false,
		},
		{
			name:          "happy_percentage",
			text:          "60%",
			colour:        colourWarn,
			expectedError: false,
		},
		{
			name:          "happy_percentage_orange",
			text:          "60%",
			colour:        colourCheer,
			expectedError: false,
		},
		{
			name:          "happy_bar_unicode",
			text:          "[███  ]  60%",
			colour:        colourWarn,
			expectedError: false,
		},
		{
			name:          "happy_bar_ascii",
			text:          "[###  ]  60%",
			colour:        colourWarn,
			expectedError: false,
		},
		{
			name:          "happy_tick_unicode",
			text:          "✔",
			colour:        colourCheer,
			expectedError: false,
		},
		{
			name:          "happy_tick_ascii",
			text:          "+",
			colour:        colourCheer,
			expectedError: false,
		},
		{
			name:          "happy_cross_unicode",
			text:          "✖",
			colour:        colourAlert,
			expectedError: false,
		},
		{
			name:          "happy_cross_ascii",
			text:          "-",
			colour:        colourAlert,
			expectedError: false,
		},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			screen := newTerminalVirtual(1, 15, ThemeDark, false)
			screen.draw(0, 0, testCase.text, testCase.colour)
			fmt.Print(screen.string(true))
			rendered := strings.TrimSpace(screen.string(false))
			if !testCase.expectedError && rendered != testCase.text {
				t.Fatalf("Got render = %q, expected %q", rendered, testCase.text)
			} else if testCase.expectedError && rendered == testCase.text {
				t.Fatalf("Got render = %q, expected not to be %q", rendered, testCase.text)
			}
		})
	}

}

func TestDisplay_Repeat(t *testing.T) {
	tests := []struct {
		name        string
		base        string
		prefixCount int
		suffixCount int
		length      int
		expected    string
	}{
		{
			name:        "happy_prefix_suffix",
			base:        "string",
			prefixCount: 2,
			suffixCount: 2,
			length:      6,
			expected:    "stngst",
		},
		{
			name:        "happy_suffix_only",
			base:        "abcdef",
			prefixCount: 0,
			suffixCount: 2,
			length:      5,
			expected:    "efefe",
		},
		{
			name:        "happy_prefix_only",
			base:        "abcdef",
			prefixCount: 3,
			suffixCount: 0,
			length:      4,
			expected:    "abca",
		},
		{
			name:        "happy_counts_clamped",
			base:        "abcd",
			prefixCount: 3,
			suffixCount: 3,
			length:      5,
			expected:    "abcda",
		},
		{
			name:        "happy_negative_counts",
			base:        "abcd",
			prefixCount: -1,
			suffixCount: -2,
			length:      3,
			expected:    "",
		},
		{
			name:        "happy_zero_length",
			base:        "abcd",
			prefixCount: 1,
			suffixCount: 1,
			length:      0,
			expected:    "",
		},
		{
			name:        "happy_empty_base",
			base:        "",
			prefixCount: 1,
			suffixCount: 1,
			length:      3,
			expected:    "",
		},
		{
			name:        "happy_zero_slice",
			base:        "abcd",
			prefixCount: 0,
			suffixCount: 0,
			length:      3,
			expected:    "",
		},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			rendered := repeat(testCase.base, testCase.prefixCount, testCase.suffixCount, testCase.length)
			if rendered != testCase.expected {
				t.Fatalf("Got render = %q, expected %q", rendered, testCase.expected)
			}
		})
	}
}

func TestDisplay_ExtendInsert(t *testing.T) {
	tests := []struct {
		name     string
		base     string
		offset   int
		length   int
		expected string
	}{
		{
			name:     "happy_offset_zero",
			base:     "abcd",
			offset:   0,
			length:   6,
			expected: "aaabcd",
		},
		{
			name:     "happy_offset_mid",
			base:     "abcd",
			offset:   2,
			length:   6,
			expected: "abcccd",
		},
		{
			name:     "happy_offset_last",
			base:     "abcd",
			offset:   3,
			length:   5,
			expected: "abcdd",
		},
		{
			name:     "happy_offset_clamped_high",
			base:     "abcd",
			offset:   99,
			length:   5,
			expected: "abcdd",
		},
		{
			name:     "happy_negative_offset",
			base:     "abcd",
			offset:   -3,
			length:   5,
			expected: "aabcd",
		},
		{
			name:     "happy_unicode_runes",
			base:     "ab✓",
			offset:   2,
			length:   4,
			expected: "ab✓✓",
		},
		{
			name:     "happy_length_not_expanded",
			base:     "abcd",
			offset:   1,
			length:   3,
			expected: "abcd",
		},
		{
			name:     "happy_zero_length",
			base:     "abcd",
			offset:   1,
			length:   0,
			expected: "",
		},
		{
			name:     "happy_empty_base",
			base:     "",
			offset:   1,
			length:   3,
			expected: "",
		},
		{
			name:     "happy_header",
			base:     "┌──────╮",
			offset:   2,
			length:   25,
			expected: "┌───────────────────────╮",
		},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			rendered := extend(testCase.base, testCase.offset, testCase.length)
			if rendered != testCase.expected {
				t.Fatalf("Got render = %q, expected %q", rendered, testCase.expected)
			}
		})
	}
}

func TestDisplay_Divider(t *testing.T) {
	tests := []struct {
		name     string
		base     string
		length   int
		expected string
	}{
		{
			name:     "happy_odd_length",
			base:     "|",
			length:   5,
			expected: "  |  ",
		},
		{
			name:     "happy_even_length",
			base:     "|",
			length:   6,
			expected: "  ||  ",
		},
		{
			name:     "happy_length_one",
			base:     "|",
			length:   1,
			expected: "|",
		},
		{
			name:     "happy_length_two",
			base:     "|",
			length:   2,
			expected: "||",
		},
		{
			name:     "happy_empty_base",
			base:     "",
			length:   3,
			expected: "",
		},
		{
			name:     "happy_zero_length",
			base:     "|",
			length:   0,
			expected: "",
		},
		{
			name:     "happy_base_first_rune_only",
			base:     "||",
			length:   3,
			expected: " | ",
		},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			rendered := divider(testCase.base, testCase.length)
			if rendered != testCase.expected {
				t.Fatalf("Got render = %q, expected %q", rendered, testCase.expected)
			}
		})
	}
}

func TestDisplay_TextResizeHelpers(t *testing.T) {
	tests := []struct {
		name     string
		resize   func(value text) text
		base     text
		expected text
	}{
		{
			name: "happy_divider_ascii_unicode",
			resize: func(value text) text {
				return value.resize(2, divider)
			},
			base:     text{ascii: "|", unicode: "│"},
			expected: text{ascii: " | ", unicode: " │ "},
		},
		{
			name: "happy_expand_ascii_unicode",
			resize: func(value text) text {
				return value.resize(2, func(base string, length int) string {
					return extend(base, 1, length)
				})
			},
			base:     text{ascii: " ---", unicode: "─┐"},
			expected: text{ascii: " -----", unicode: "─┐┐┐"},
		},
		{
			name: "happy_repeat_suffix_ascii_unicode",
			resize: func(value text) text {
				return value.resize(2, func(base string, length int) string {
					return base + repeat(base, 0, 1, length-runewidth.StringWidth(base))
				})
			},
			base:     text{ascii: "ab", unicode: "xy"},
			expected: text{ascii: "abbb", unicode: "xyyy"},
		},
		{
			name: "happy_pad_mid_ascii_unicode",
			resize: func(value text) text {
				return value.resize(2, func(base string, length int) string {
					return pad(base, boxMid, length)
				})
			},
			base:     text{ascii: "cpu", unicode: "cpu"},
			expected: text{ascii: " cpu ", unicode: " cpu "},
		},
		{
			name: "happy_fallback_empty_unicode",
			resize: func(value text) text {
				return value.resize(2, func(base string, length int) string {
					return base + repeat(base, 0, 1, length-runewidth.StringWidth(base))
				})
			},
			base:     text{ascii: "ab"},
			expected: text{ascii: "abbb", unicode: "abbb"},
		},
		{
			name: "happy_fallback_empty_ascii",
			resize: func(value text) text {
				return value.resize(2, func(base string, length int) string {
					return base + repeat(base, 0, 1, length-runewidth.StringWidth(base))
				})
			},
			base:     text{unicode: "xy"},
			expected: text{ascii: "xyyy", unicode: "xyyy"},
		},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			resized := testCase.resize(testCase.base)
			if resized != testCase.expected {
				t.Fatalf("Got text = %#v, expected %#v", resized, testCase.expected)
			}
		})
	}
}

func TestDisplay_Pad(t *testing.T) {
	tests := []struct {
		name     string
		base     string
		align    boxAlign
		length   int
		expected string
	}{
		{
			name:     "happy_left_align",
			base:     "abc",
			align:    boxLhs,
			length:   5,
			expected: "abc  ",
		},
		{
			name:     "happy_right_align",
			base:     "abc",
			align:    boxRhs,
			length:   5,
			expected: "  abc",
		},
		{
			name:     "happy_no_padding",
			base:     "abc",
			align:    boxLhs,
			length:   3,
			expected: "abc",
		},
		{
			name:     "happy_mid_align_hostname",
			base:     "node-one",
			align:    boxMid,
			length:   11,
			expected: " node-one  ",
		},
		{
			name:     "happy_mid_align_even_padding",
			base:     "abc",
			align:    boxMid,
			length:   7,
			expected: "  abc  ",
		},
		{
			name:     "happy_mid_align_odd_padding",
			base:     "abc",
			align:    boxMid,
			length:   6,
			expected: " abc  ",
		},
		{
			name:     "happy_truncate",
			base:     "abcdefg",
			align:    boxLhs,
			length:   6,
			expected: "abcde~",
		},
		{
			name:     "happy_truncate_short_length",
			base:     "abcdefg",
			align:    boxLhs,
			length:   2,
			expected: "a~",
		},
		{
			name:     "happy_empty_base",
			base:     "",
			align:    boxLhs,
			length:   4,
			expected: "    ",
		},
		{
			name:     "happy_zero_length",
			base:     "abc",
			align:    boxLhs,
			length:   0,
			expected: "",
		},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			rendered := pad(testCase.base, testCase.align, testCase.length)
			if rendered != testCase.expected {
				t.Fatalf("Got render = %q, expected %q", rendered, testCase.expected)
			}
		})
	}
}

func TestDisplay_Refresh(t *testing.T) {
	tests := []struct {
		name            string
		refresh         bool
		stall           time.Duration
		expectedRefresh bool
		expectedError   bool
	}{
		{
			name:            "happy_refresh_signalled",
			refresh:         true,
			stall:           defaultTickStall,
			expectedRefresh: true,
			expectedError:   false,
		},
		{
			name:            "happy_refresh_not_signalled",
			refresh:         false,
			stall:           defaultTickStall,
			expectedRefresh: false,
			expectedError:   false,
		},
		{
			name:            "happy_refresh_stall_detected",
			refresh:         false,
			stall:           time.Nanosecond,
			expectedRefresh: true,
			expectedError:   false,
		},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			layout := compactDisplayLayout(false)
			caseRows := rows(layout, 1)
			caseCols := columns(layout, false, 1)
			cache := metric.NewRecordCache()
			terminal := newTerminalVirtual(caseRows, caseCols, ThemeLight, false)
			display, err := NewDisplay(
				hosts[:1],
				config.Periods{},
				"",
				true,
				false,
				FormatCompact,
				caseCols,
				caseRows,
				0,
				0,
				0,
				func(useUnicode bool) (Terminal, error) { return terminal, nil },
				cache,
				nil,
			)
			if err != nil {
				t.Fatalf("New Display err = %v, expected nil", err)
			}
			if _, err = display.Compile(); err != nil {
				t.Fatalf("Compile Display err = %v, expected nil", err)
			}
			if err = display.Load(); err != nil {
				t.Fatalf("Load Display err = %v, expected nil", err)
			}
			display.tickStall = testCase.stall
			ctx, cancel := context.WithCancel(context.Background())
			defer cancel()
			drawn := make(chan struct{})
			go func() {
				display.Draw(ctx, cancel)
				close(drawn)
			}()
			time.Sleep(500 * time.Millisecond)
			cache.ClearUpdateListeners()
			for host, ids := range cache.ListenerIDs() {
				for _, id := range ids {
					if metric.GetIDKind(id) == metric.MetricKindService {
						continue
					}
					record := metric.NewRecord(*metric.NewIntValue(true, 42, true, 42))
					cache.Store(metric.NewRecordGUID(id, host), &record)
				}
			}
			time.Sleep(500 * time.Millisecond)
			if testCase.refresh {
				cache.Refresh()
				time.Sleep(500 * time.Millisecond)
			}
			display.Close()
			<-drawn
			rendered := terminal.string(false)
			fmt.Print(terminal.string(true))
			if got := strings.Contains(rendered, "42%"); got != testCase.expectedRefresh {
				t.Fatalf("Got rendered values = %v, expected %v", got, testCase.expectedRefresh)
			}
		})
	}
}

func diffDisplay(this, that string) string {
	dmp := diffmatchpatch.New()
	expLines := strings.Split(strings.TrimRight(this, "\n"), "\n")
	gotLines := strings.Split(strings.TrimRight(that, "\n"), "\n")
	var b strings.Builder
	for i := range max(len(expLines), len(gotLines)) {
		e, g := "", ""
		if i < len(expLines) {
			e = expLines[i]
		}
		if i < len(gotLines) {
			g = gotLines[i]
		}
		if e == g {
			continue
		}
		diffs := dmp.DiffMain(e, g, false)
		dmp.DiffCleanupSemantic(diffs)
		b.WriteString(dmp.DiffPrettyText(diffs) + "\n")
	}
	return b.String()
}

var hosts = func() []string {
	result := make([]string, 0, 6)
	for i := 1; i <= 9; i++ {
		result = append(result, "labnode-"+num2words.Convert(i))
	}
	return result
}()

func TestDisplay_Failed(t *testing.T) {
	services := []string{
		"homeassistant",
		"influxdb3",
		"internet",
		"mariadb",
		"mylongnamedservice",
		"mlflow",
		"mlserver",
		"nginx",
		"openra",
		"plex",
		"postgres",
		"wrangle",
		"zigbee2mqtt",
	}
	tests := []struct {
		name              string
		failedHostID      metric.ID
		failedServices    []int
		expectedName      string
		expectedColour    colour
		expectedOverflows int
		expectedError     bool
	}{
		{
			name:              "happy_failed_visible_service_beside_overflow",
			failedHostID:      metric.MetricHostUsedHomeSpace,
			failedServices:    []int{0},
			expectedName:      "homeassistant",
			expectedColour:    colourAlert,
			expectedOverflows: 5,
			expectedError:     false,
		},
		{
			name:              "happy_failed_offgrid_service_keeps_overflow",
			failedHostID:      metric.MetricHostUsedHomeSpace,
			failedServices:    []int{7, 8},
			expectedName:      "",
			expectedColour:    colourAlert,
			expectedOverflows: 5,
			expectedError:     false,
		},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			layout := compactDisplayLayout(false)
			terminalDims := dimensions{rows(layout, 1), columns(layout, false, 1) + resizes(layout, 1)*10}
			cache := metric.NewRecordCache()
			terminal := newTerminalVirtual(terminalDims.rows, terminalDims.cols, ThemeLight, false)
			display, newErr := NewDisplay(
				[]string{"labnode-one"},
				config.Periods{},
				"",
				true,
				false,
				FormatCompact,
				terminalDims.cols,
				terminalDims.rows,
				0,
				0,
				0,
				func(useUnicode bool) (Terminal, error) { return terminal, nil },
				cache,
				nil,
			)
			if newErr != nil {
				t.Fatalf("NewDisplay: got %v want nil", newErr)
			}
			if _, compileErr := display.Compile(); compileErr != nil {
				t.Fatalf("Compile: got %v want nil", compileErr)
			}
			ctx, cancel := context.WithCancel(context.Background())
			defer cancel()
			if loadErr := display.Load(); loadErr != nil {
				t.Fatalf("Load: got %v want nil", loadErr)
			}
			failedService := map[int]bool{}
			for _, index := range testCase.failedServices {
				failedService[index] = true
			}
			record := func(id metric.ID, i int) metric.Record {
				switch id {
				case metric.MetricServiceName:
					return metric.NewRecord(*metric.NewStringValue(true, services[i], true, services[i]))
				case metric.MetricServiceVersion:
					return metric.NewRecord(*metric.NewStringValue(true, fmt.Sprintf("10.100.%d", 1001+i), true, fmt.Sprintf("10.100.%d", 1001+i)))
				case metric.MetricServiceBackupStatus:
					return metric.NewRecord(*metric.NewBoolValue(false, true))
				case metric.MetricServiceHealthStatus, metric.MetricServiceConfiguredStatus, metric.MetricService:
					return metric.NewRecord(*metric.NewBoolValue(true, true))
				case metric.MetricServiceRestartCount:
					return metric.NewRecord(*metric.NewIntValue(true, 0, true, 0))
				case metric.MetricServiceUpTime:
					return metric.NewRecord(*metric.NewFloatValue(true, float64((i+1)*2000000), false, float64((i+1)*2000000)))
				default:
					value := []int8{100, 50, 0}[i%3]
					return metric.NewRecord(*metric.NewIntValue(true, value, true, value))
				}
			}
			for host, ids := range cache.ListenerIDs() {
				slices.Sort(ids)
				for _, id := range ids {
					if metric.GetIDKind(id) != metric.MetricKindService {
						value := []int8{0, 100, 50}[int(id)%3]
						hostRecord := metric.NewRecord(*metric.NewIntValue(true, value, true, value))
						hostRecord.Value.Failed = id == testCase.failedHostID
						cache.Store(metric.NewRecordGUID(id, host), &hostRecord)
					}
				}
				for i := range services {
					for _, id := range metric.GetIDsByKind([]metric.MetricKind{metric.MetricKindService}) {
						serviceRecord := record(id, i)
						serviceRecord.Value.Failed = failedService[i]
						cache.Store(metric.NewServiceRecordGUID(id, host, fmt.Sprintf("test-svc-%02d", i)), &serviceRecord)
					}
				}
			}
			drawn := make(chan struct{})
			go func() {
				display.Draw(ctx, cancel)
				close(drawn)
			}()
			display.Close()
			<-drawn
			fmt.Printf("Terminal [%dx%d]:\n%s", terminalDims.cols, terminalDims.rows, terminal.string(true))
			find := func(needle string) (int, int) {
				for y := 0; y < terminalDims.rows; y++ {
					line := make([]rune, 0, terminalDims.cols)
					for x := 0; x < terminalDims.cols; x++ {
						char, _, _ := terminal.cell(x, y)
						line = append(line, char)
					}
					if index := strings.Index(string(line), needle); index >= 0 {
						return index, y
					}
				}
				return -1, -1
			}
			label := "Used HME "
			labelCols, labelRows := find(label)
			if labelCols < 0 {
				t.Fatalf("label [%s]: got no match want the failed host box", label)
			}
			if _, got, _ := terminal.cell(labelCols, labelRows); got != testCase.expectedColour {
				t.Errorf("label colour: got %v want %v", got, testCase.expectedColour)
			}
			for offset := range 4 {
				char, _, _ := terminal.cell(labelCols+len(label)+offset, labelRows)
				if char != ' ' {
					t.Errorf("value cell %d: got %q want a blank", offset, char)
				}
			}
			overflows := 0
			for y := 0; y < terminalDims.rows; y++ {
				for x := 0; x < terminalDims.cols; x++ {
					if char, _, _ := terminal.cell(x, y); char == '~' {
						overflows++
					}
				}
			}
			if overflows != testCase.expectedOverflows {
				t.Errorf("overflow markers: got %v want %v", overflows, testCase.expectedOverflows)
			}
			if testCase.expectedName == "" {
				return
			}
			nameCols, nameRows := find(testCase.expectedName)
			if nameCols < 0 {
				t.Fatalf("service [%s]: got no match want the failed service row still named", testCase.expectedName)
			}
			if _, got, _ := terminal.cell(nameCols, nameRows); got != testCase.expectedColour {
				t.Errorf("service name colour: got %v want %v", got, testCase.expectedColour)
			}
			for offset := len(testCase.expectedName); offset < 24; offset++ {
				char, _, _ := terminal.cell(nameCols+offset, nameRows)
				if char != ' ' {
					t.Errorf("service cell %d: got %q want a blank on a failed row", offset, char)
				}
			}
		})
	}
}

func TestDisplay_FailedHostLabelRestoresOnRecovery(t *testing.T) {
	tests := []struct {
		name           string
		failedHostID   metric.ID
		expectedFailed colour
		expectedClear  colour
		expectedError  bool
	}{
		{name: "happy_life_used_drives_recovers", failedHostID: metric.MetricHostLifeUsedDrives, expectedFailed: colourAlert, expectedClear: colourChat, expectedError: false},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			layout := compactDisplayLayout(false)
			terminalDims := dimensions{rows(layout, 1), columns(layout, false, 1) + resizes(layout, 1)*10}
			cache := metric.NewRecordCache()
			terminal := newTerminalVirtual(terminalDims.rows, terminalDims.cols, ThemeLight, false)
			display, newErr := NewDisplay(
				[]string{"labnode-one"}, config.Periods{}, "", true, false, FormatCompact,
				terminalDims.cols, terminalDims.rows, 0, 0, 0,
				func(useUnicode bool) (Terminal, error) { return terminal, nil }, cache, nil,
			)
			if newErr != nil {
				t.Fatalf("NewDisplay: got %v want nil", newErr)
			}
			if _, compileErr := display.Compile(); compileErr != nil {
				t.Fatalf("Compile: got %v want nil", compileErr)
			}
			if loadErr := display.Load(); loadErr != nil {
				t.Fatalf("Load: got %v want nil", loadErr)
			}
			store := func(failed bool) {
				for host, ids := range cache.ListenerIDs() {
					for _, id := range ids {
						if metric.GetIDKind(id) == metric.MetricKindService {
							continue
						}
						hostRecord := metric.NewRecord(*metric.NewIntValue(true, 0, true, 0))
						hostRecord.Value.Failed = failed && id == testCase.failedHostID
						cache.Store(metric.NewRecordGUID(id, host), &hostRecord)
					}
				}
			}
			labelColour := func() colour {
				for y := 0; y < terminalDims.rows; y++ {
					line := make([]rune, 0, terminalDims.cols)
					for x := 0; x < terminalDims.cols; x++ {
						char, _, _ := terminal.cell(x, y)
						line = append(line, char)
					}
					if index := strings.Index(string(line), "Hlth SSD"); index >= 0 {
						_, found, _ := terminal.cell(index, y)
						return found
					}
				}
				t.Fatalf("label [Hlth SSD]: got no match want the host box")
				return colourChat
			}
			store(true)
			for index := range display.boxes {
				display.boxes[index].drawLabels(display)
			}
			if got := labelColour(); got != testCase.expectedFailed {
				t.Errorf("failed label colour: got %v want %v", got, testCase.expectedFailed)
			}
			store(false)
			for index := range display.boxes {
				display.boxes[index].drawValue(display)
			}
			if got := labelColour(); got != testCase.expectedClear {
				t.Errorf("recovered label colour: got %v want %v", got, testCase.expectedClear)
			}
		})
	}
}

func TestDisplay_LogScrolling(t *testing.T) {
	tests := []struct {
		name           string
		pages          int
		ups            int
		expectedOldest bool
		expectedError  bool
	}{
		{
			name:           "happy_pages_back_one",
			pages:          4,
			ups:            1,
			expectedOldest: false,
			expectedError:  false,
		},
		{
			name:           "happy_pages_back_to_the_oldest",
			pages:          3,
			ups:            3,
			expectedOldest: true,
			expectedError:  false,
		},
		{
			name:           "happy_clamps_at_the_oldest",
			pages:          2,
			ups:            9,
			expectedOldest: true,
			expectedError:  false,
		},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			layout := compactDisplayLayout(false)
			caseRows := rows(layout, 1)
			caseCols := columns(layout, false, 1)
			capacity := caseRows - 2
			buffer := scribe.EnableBuffer(slog.LevelDebug, scribe.BufferLines(caseRows))
			t.Cleanup(scribe.Disable)
			terminal := newTerminalVirtual(caseRows, caseCols, ThemeLight, false)
			display, err := NewDisplay(
				hosts[:1], config.Periods{}, "", true, false, FormatCompact,
				caseCols, caseRows, 0, 0, 0,
				func(useUnicode bool) (Terminal, error) { return terminal, nil },
				metric.NewRecordCache(), buffer,
			)
			if err != nil {
				t.Fatalf("New Display err = %v, expected nil", err)
			}
			if _, err = display.Compile(); err != nil {
				t.Fatalf("Compile Display err = %v, expected nil", err)
			}
			if err = display.Load(); err != nil {
				t.Fatalf("Load Display err = %v, expected nil", err)
			}
			display.logOverlay = true
			for range testCase.pages * capacity {
				scribe.Log(scribe.SourceDisplay, scribe.SubjectNone, scribe.ActionRender).Info("received", time.Now(), "scroll fodder")
			}
			display.logRewind()
			display.Logging()
			live := display.logAnchor
			previous := live
			livePage, livePages := display.logPagination()
			if livePage != livePages {
				t.Errorf("live page: got %d want %d", livePage, livePages)
			}
			for up := range testCase.ups {
				display.logPageUp()
				display.Logging()
				if display.logFollow {
					t.Errorf("up %d follow: got %v want %v", up, display.logFollow, false)
				}
				if display.logAnchor > previous {
					t.Errorf("up %d anchor: got %d want at most %d", up, display.logAnchor, previous)
				}
				page, pages := display.logPagination()
				if pages != livePages {
					t.Errorf("up %d pages: got %d want %d", up, pages, livePages)
				}
				if wanted := max(livePages-up-1, 1); page != wanted {
					t.Errorf("up %d page: got %d want %d", up, page, wanted)
				}
				previous = display.logAnchor
			}
			if atOldest := display.logAnchor == buffer.Oldest(); atOldest != testCase.expectedOldest {
				t.Errorf("oldest: got %v want %v", atOldest, testCase.expectedOldest)
			}
			for down := range testCase.ups * 2 {
				if display.logFollow {
					break
				}
				display.logPageDown()
				display.Logging()
				if display.logAnchor < previous {
					t.Errorf("down %d anchor: got %d want at least %d", down, display.logAnchor, previous)
				}
				previous = display.logAnchor
			}
			if !display.logFollow {
				t.Errorf("paged down follow: got %v want %v", display.logFollow, true)
			}
			if display.logAnchor != live {
				t.Errorf("paged down anchor: got %d want %d", display.logAnchor, live)
			}
		})
	}
}

func TestDisplay_LogCoverage(t *testing.T) {
	tests := []struct {
		name          string
		overlayRows   int
		expectedError bool
	}{
		{
			name:          "happy_covers_a_short_overlay",
			overlayRows:   8,
			expectedError: false,
		},
		{
			name:          "happy_covers_a_usual_overlay",
			overlayRows:   22,
			expectedError: false,
		},
		{
			name:          "happy_covers_a_tall_overlay",
			overlayRows:   47,
			expectedError: false,
		},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			layout := compactDisplayLayout(false)
			caseRows := rows(layout, 1)
			caseCols := columns(layout, false, 1)
			buffer := scribe.EnableBuffer(slog.LevelDebug, scribe.BufferLines(60))
			t.Cleanup(scribe.Disable)
			terminal := newTerminalVirtual(caseRows, caseCols, ThemeLight, false)
			display, err := NewDisplay(
				hosts[:1], config.Periods{}, "", true, false, FormatCompact,
				caseCols, caseRows, 0, 0, 0,
				func(useUnicode bool) (Terminal, error) { return terminal, nil },
				metric.NewRecordCache(), buffer,
			)
			if err != nil {
				t.Fatalf("New Display err = %v, expected nil", err)
			}
			if _, err = display.Compile(); err != nil {
				t.Fatalf("Compile Display err = %v, expected nil", err)
			}
			if err = display.Load(); err != nil {
				t.Fatalf("Load Display err = %v, expected nil", err)
			}
			display.logOverlay = true
			display.dimsInit = dimensions{rows: testCase.overlayRows, cols: 200}
			lengths := []int{4, 180, 7, 320, 12, 95, 240, 3, 61, 410, 28, 150, 500, 9}
			for index := range 400 {
				scribe.Log(scribe.SourceDisplay, scribe.SubjectNone, scribe.ActionRender).Info("received", time.Now(), "%s", strings.Repeat("z", lengths[index%len(lengths)]))
			}
			display.logRewind()
			display.Logging()
			_, pages := display.logPagination()
			seen := func(visited map[uint64]bool) {
				for sequence := display.logAnchor; sequence < display.logNext; sequence++ {
					visited[sequence] = true
				}
			}
			absent := func(visited map[uint64]bool, from uint64) int {
				missing := 0
				for sequence := from; sequence < buffer.Version(); sequence++ {
					if !visited[sequence] {
						missing++
					}
				}
				return missing
			}
			if pages > logPagesMax {
				t.Errorf("pages: got %d want at most %d", pages, logPagesMax)
			}
			climbed, climbing := 0, map[uint64]bool{}
			seen(climbing)
			for {
				if page, _ := display.logPagination(); page == 1 {
					break
				}
				display.logPageUp()
				display.Logging()
				seen(climbing)
				if climbed++; climbed > pages {
					t.Fatalf("paging up never reached the oldest page of %d", pages)
				}
			}
			if climbed != pages-1 {
				t.Errorf("ups: got %d want %d", climbed, pages-1)
			}
			reached := display.logAnchor
			if missing := absent(climbing, reached); missing != 0 {
				t.Errorf("ups missed: got %d want 0", missing)
			}
			fallen, falling := 0, map[uint64]bool{}
			seen(falling)
			for !display.logFollow {
				display.logPageDown()
				display.Logging()
				seen(falling)
				if fallen++; fallen > pages+1 {
					t.Fatalf("paging down never reached live from %d pages", pages)
				}
			}
			if fallen != pages {
				t.Errorf("downs: got %d want %d", fallen, pages)
			}
			if missing := absent(falling, reached); missing != 0 {
				t.Errorf("downs missed: got %d want 0", missing)
			}
		})
	}
}

func TestDisplay_LogArriving(t *testing.T) {
	tests := []struct {
		name          string
		trickle       int
		expectedBump  bool
		expectedError bool
	}{
		{
			name:          "happy_a_partial_page_holds_the_total",
			trickle:       6,
			expectedBump:  false,
			expectedError: false,
		},
		{
			name:          "happy_a_whole_page_raises_the_total",
			trickle:       24,
			expectedBump:  true,
			expectedError: false,
		},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			layout := compactDisplayLayout(false)
			caseRows := rows(layout, 1)
			caseCols := columns(layout, false, 1)
			buffer := scribe.EnableBuffer(slog.LevelDebug, scribe.BufferLines(60))
			t.Cleanup(scribe.Disable)
			terminal := newTerminalVirtual(caseRows, caseCols, ThemeLight, false)
			display, err := NewDisplay(
				hosts[:1], config.Periods{}, "", true, false, FormatCompact,
				caseCols, caseRows, 0, 0, 0,
				func(useUnicode bool) (Terminal, error) { return terminal, nil },
				metric.NewRecordCache(), buffer,
			)
			if err != nil {
				t.Fatalf("New Display err = %v, expected nil", err)
			}
			if _, err = display.Compile(); err != nil {
				t.Fatalf("Compile Display err = %v, expected nil", err)
			}
			if err = display.Load(); err != nil {
				t.Fatalf("Load Display err = %v, expected nil", err)
			}
			display.logOverlay = true
			display.dimsInit = dimensions{rows: 22, cols: 200}
			lengths := []int{4, 180, 7, 320, 12, 95, 240, 3, 61, 410, 28, 150}
			emit := func(count int) {
				for index := range count {
					scribe.Log(scribe.SourceDisplay, scribe.SubjectNone, scribe.ActionRender).Info("received", time.Now(), "%s", strings.Repeat("z", lengths[index%len(lengths)]))
				}
			}
			emit(60)
			display.logRewind()
			display.Logging()
			livePage, livePages := display.logPagination()
			if livePage != livePages {
				t.Errorf("live: got %d/%d want equal", livePage, livePages)
			}
			display.logPageUp()
			display.Logging()
			page, pages := display.logPagination()
			if page != livePage-1 || pages != livePages {
				t.Errorf("up: got %d/%d want %d/%d", page, pages, livePage-1, livePages)
			}
			for range testCase.trickle {
				emit(1)
				display.logTick()
				if held, _ := display.logPagination(); held != page {
					t.Errorf("arriving page: got %d want %d", held, page)
				}
			}
			_, arrived := display.logPagination()
			if bumped := arrived > pages; bumped != testCase.expectedBump {
				t.Errorf("bumped: got %v want %v, pages %d from %d", bumped, testCase.expectedBump, arrived, pages)
			}
			display.logPageDown()
			display.Logging()
			if display.logFollow {
				t.Errorf("paged down follow: got %v want %v", display.logFollow, false)
			}
			if next, _ := display.logPagination(); next != page+1 {
				t.Errorf("down page: got %d want %d", next, page+1)
			}
		})
	}
}

func TestDisplay_LogParked(t *testing.T) {
	tests := []struct {
		name          string
		arriving      int
		expectedError bool
	}{
		{
			name:          "happy_holds_through_a_page",
			arriving:      100,
			expectedError: false,
		},
		{
			name:          "happy_holds_through_many_pages",
			arriving:      400,
			expectedError: false,
		},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			const overlayRows = 40
			layout := compactDisplayLayout(false)
			caseRows := rows(layout, 1)
			caseCols := columns(layout, false, 1)
			buffer := scribe.EnableBuffer(slog.LevelDebug, scribe.BufferLines(overlayRows))
			t.Cleanup(scribe.Disable)
			terminal := newTerminalVirtual(caseRows, caseCols, ThemeLight, false)
			display, err := NewDisplay(
				hosts[:1], config.Periods{}, "", true, false, FormatCompact,
				caseCols, caseRows, 0, 0, 0,
				func(useUnicode bool) (Terminal, error) { return terminal, nil },
				metric.NewRecordCache(), buffer,
			)
			if err != nil {
				t.Fatalf("New Display err = %v, expected nil", err)
			}
			if _, err = display.Compile(); err != nil {
				t.Fatalf("Compile Display err = %v, expected nil", err)
			}
			if err = display.Load(); err != nil {
				t.Fatalf("Load Display err = %v, expected nil", err)
			}
			display.logOverlay = true
			display.dimsInit = dimensions{rows: overlayRows, cols: 200}
			emit := func(count int) {
				for range count {
					scribe.Log(scribe.SourceDisplay, scribe.SubjectNone, scribe.ActionRender).Info("received", time.Now(), "%s", strings.Repeat("z", 60))
				}
			}
			emit(scribe.BufferLines(overlayRows) + overlayRows*10)
			display.logRewind()
			display.Logging()
			live, pages := display.logPagination()
			if pages > logPagesMax || live != pages {
				t.Errorf("live: got %d/%d want equal and at most %d", live, pages, logPagesMax)
			}
			display.logPageUp()
			display.Logging()
			parked, _ := display.logPagination()
			for arrived := range testCase.arriving {
				emit(1)
				display.logTick()
				page, total := display.logPagination()
				if page != parked {
					t.Errorf("after %d arrived page: got %d want %d", arrived+1, page, parked)
				}
				if total < pages {
					t.Errorf("after %d arrived total: got %d want at least %d", arrived+1, total, pages)
				}
			}
			display.logRewind()
			display.Logging()
			if page, total := display.logPagination(); page != total || total > logPagesMax {
				t.Errorf("live again: got %d/%d want equal and at most %d", page, total, logPagesMax)
			}
		})
	}
}

func TestDisplay_LogWrapping(t *testing.T) {
	tests := []struct {
		name          string
		screens       int
		flooded       int
		expectedDrop  bool
		expectedError bool
	}{
		{
			name:          "happy_holds_inside_the_ring",
			screens:       50,
			flooded:       40,
			expectedDrop:  false,
			expectedError: false,
		},
		{
			name:          "happy_reanchors_when_wrapped_past",
			screens:       4,
			flooded:       600,
			expectedDrop:  true,
			expectedError: false,
		},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			layout := compactDisplayLayout(false)
			caseRows := rows(layout, 1)
			caseCols := columns(layout, false, 1)
			buffer := scribe.EnableBuffer(slog.LevelDebug, scribe.BufferLines(testCase.screens))
			t.Cleanup(scribe.Disable)
			terminal := newTerminalVirtual(caseRows, caseCols, ThemeLight, false)
			display, err := NewDisplay(
				hosts[:1], config.Periods{}, "", true, false, FormatCompact,
				caseCols, caseRows, 0, 0, 0,
				func(useUnicode bool) (Terminal, error) { return terminal, nil },
				metric.NewRecordCache(), buffer,
			)
			if err != nil {
				t.Fatalf("New Display err = %v, expected nil", err)
			}
			if _, err = display.Compile(); err != nil {
				t.Fatalf("Compile Display err = %v, expected nil", err)
			}
			if err = display.Load(); err != nil {
				t.Fatalf("Load Display err = %v, expected nil", err)
			}
			display.logOverlay = true
			display.dimsInit = dimensions{rows: 22, cols: 200}
			lengths := []int{4, 180, 7, 320, 12, 95, 240, 3, 61, 410, 28, 150}
			emit := func(count int) {
				for index := range count {
					scribe.Log(scribe.SourceDisplay, scribe.SubjectNone, scribe.ActionRender).Info("received", time.Now(), "%s", strings.Repeat("y", lengths[index%len(lengths)]))
				}
			}
			emit(200)
			display.logRewind()
			display.Logging()
			previous, _ := display.logPagination()
			for up := range 6 {
				display.logPageUp()
				display.Logging()
				page, _ := display.logPagination()
				if page != previous-1 {
					t.Errorf("up %d page: got %d want %d", up, page, previous-1)
				}
				previous = page
			}
			for down := range 6 {
				display.logPageDown()
				display.Logging()
				page, _ := display.logPagination()
				if page != previous+1 {
					t.Errorf("down %d page: got %d want %d", down, page, previous+1)
				}
				if display.logFollow {
					t.Errorf("down %d follow: got %v want %v", down, display.logFollow, false)
				}
				previous = page
			}
			display.logPageDown()
			display.Logging()
			if !display.logFollow {
				t.Errorf("paged back to live: got %v want %v", display.logFollow, true)
			}
			display.logPageUp()
			display.Logging()
			previous, _ = display.logPagination()
			parked := display.logAnchor
			emit(testCase.flooded)
			display.logTick()
			dropped := display.logDropped > 0
			if dropped != testCase.expectedDrop {
				t.Errorf("dropped: got %v want %v", dropped, testCase.expectedDrop)
			}
			if display.logAnchor < buffer.Oldest() {
				t.Errorf("anchor: got %d want at least %d", display.logAnchor, buffer.Oldest())
			}
			if !testCase.expectedDrop && display.logAnchor != parked {
				t.Errorf("anchor: got %d want %d", display.logAnchor, parked)
			}
			if display.logFollow {
				t.Errorf("still paused: got %v want %v", display.logFollow, false)
			}
		})
	}
}

func TestDisplay_LogPagination(t *testing.T) {
	tests := []struct {
		name          string
		arriving      int
		expectedPage  int
		expectedPages int
		expectedError bool
	}{
		{
			name:          "happy_pausing_holds_the_page",
			arriving:      0,
			expectedPage:  5,
			expectedPages: 5,
			expectedError: false,
		},
		{
			name:          "happy_one_line_holds_the_total",
			arriving:      1,
			expectedPage:  5,
			expectedPages: 5,
			expectedError: false,
		},
		{
			name:          "happy_a_page_raises_the_total_once",
			arriving:      8,
			expectedPage:  5,
			expectedPages: 6,
			expectedError: false,
		},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			layout := compactDisplayLayout(false)
			caseRows := rows(layout, 1)
			caseCols := columns(layout, false, 1)
			capacity := caseRows - 2
			buffer := scribe.EnableBuffer(slog.LevelDebug, scribe.BufferLines(caseRows))
			t.Cleanup(scribe.Disable)
			terminal := newTerminalVirtual(caseRows, caseCols, ThemeLight, false)
			display, err := NewDisplay(
				hosts[:1], config.Periods{}, "", true, false, FormatCompact,
				caseCols, caseRows, 0, 0, 0,
				func(useUnicode bool) (Terminal, error) { return terminal, nil },
				metric.NewRecordCache(), buffer,
			)
			if err != nil {
				t.Fatalf("New Display err = %v, expected nil", err)
			}
			if _, err = display.Compile(); err != nil {
				t.Fatalf("Compile Display err = %v, expected nil", err)
			}
			if err = display.Load(); err != nil {
				t.Fatalf("Load Display err = %v, expected nil", err)
			}
			display.logOverlay = true
			emit := func(count int) {
				for range count {
					scribe.Log(scribe.SourceDisplay, scribe.SubjectNone, scribe.ActionRender).Info("received", time.Now(), "pagination fodder")
				}
			}
			emit(capacity * 4)
			display.logRewind()
			display.Logging()
			livePage, livePages := display.logPagination()
			live, _ := display.logOverlayStatus()
			display.logFollow = false
			display.Logging()
			heldPage, heldPages := display.logPagination()
			held, _ := display.logOverlayStatus()
			if heldPage != livePage || heldPages != livePages {
				t.Errorf("pausing: got %d/%d want %d/%d", heldPage, heldPages, livePage, livePages)
			}
			if runewidth.StringWidth(live) != runewidth.StringWidth(held) {
				t.Errorf("width: got live %d held %d, want equal", runewidth.StringWidth(live), runewidth.StringWidth(held))
			}
			emit(testCase.arriving)
			page, pages := display.logPagination()
			if page != testCase.expectedPage {
				t.Errorf("page: got %d want %d", page, testCase.expectedPage)
			}
			if pages != testCase.expectedPages {
				t.Errorf("pages: got %d want %d", pages, testCase.expectedPages)
			}
		})
	}
}

func TestDisplay_LogFollowing(t *testing.T) {
	tests := []struct {
		name           string
		emitted        int
		paused         bool
		expectedStatus string
		expectedError  bool
	}{
		{
			name:           "happy_following_is_live",
			emitted:        3,
			paused:         false,
			expectedStatus: " LIVE   2/2 UP/DOWN=PAGE SPACE=PAUSE",
			expectedError:  false,
		},
		{
			name:           "happy_paused_at_the_newest",
			emitted:        0,
			paused:         true,
			expectedStatus: " PAUSED 2/2 UP/DOWN=PAGE SPACE=LIVE ",
			expectedError:  false,
		},
		{
			name:           "happy_paused_holds_a_partial_page",
			emitted:        4,
			paused:         true,
			expectedStatus: " PAUSED 2/2 UP/DOWN=PAGE SPACE=LIVE ",
			expectedError:  false,
		},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			layout := compactDisplayLayout(false)
			caseRows := rows(layout, 1)
			caseCols := columns(layout, false, 1)
			buffer := scribe.EnableBuffer(slog.LevelDebug, scribe.BufferLines(caseRows))
			t.Cleanup(scribe.Disable)
			terminal := newTerminalVirtual(caseRows, caseCols, ThemeLight, false)
			display, err := NewDisplay(
				hosts[:1], config.Periods{}, "", true, false, FormatCompact,
				caseCols, caseRows, 0, 0, 0,
				func(useUnicode bool) (Terminal, error) { return terminal, nil },
				metric.NewRecordCache(), buffer,
			)
			if err != nil {
				t.Fatalf("New Display err = %v, expected nil", err)
			}
			if _, err = display.Compile(); err != nil {
				t.Fatalf("Compile Display err = %v, expected nil", err)
			}
			if err = display.Load(); err != nil {
				t.Fatalf("Load Display err = %v, expected nil", err)
			}
			display.logOverlay = true
			emit := func(count int) {
				for range count {
					scribe.Log(scribe.SourceDisplay, scribe.SubjectNone, scribe.ActionRender).Info("received", time.Now(), "follow fodder")
				}
			}
			emit(caseRows - 2)
			display.logRewind()
			display.Logging()
			if !display.logFollow {
				t.Errorf("rewind follow: got %v want %v", display.logFollow, true)
			}
			if testCase.paused {
				display.logFollow = false
			}
			emit(testCase.emitted)
			if display.logFollow {
				display.logRewind()
			}
			display.Logging()
			status, _ := display.logOverlayStatus()
			if status != testCase.expectedStatus {
				t.Errorf("status: got %q want %q", status, testCase.expectedStatus)
			}
			if display.logFollow && display.logBuffer.Version() != display.logNext {
				t.Errorf("following end: got %d want %d", display.logNext, display.logBuffer.Version())
			}
		})
	}
}

func TestDisplay_LogPaging(t *testing.T) {
	tests := []struct {
		name          string
		pages         int
		expectedError bool
	}{
		{
			name:          "happy_short_of_a_screen",
			pages:         1,
			expectedError: false,
		},
		{
			name:          "happy_fills_and_pauses",
			pages:         2,
			expectedError: false,
		},
		{
			name:          "happy_pages_to_the_newest",
			pages:         4,
			expectedError: false,
		},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			layout := compactDisplayLayout(false)
			caseRows := rows(layout, 1)
			caseCols := columns(layout, false, 1)
			capacity := caseRows - 2
			buffer := scribe.EnableBuffer(slog.LevelDebug, scribe.BufferLines(caseRows))
			t.Cleanup(scribe.Disable)
			terminal := newTerminalVirtual(caseRows, caseCols, ThemeLight, false)
			display, err := NewDisplay(
				hosts[:1], config.Periods{}, "", true, false, FormatCompact,
				caseCols, caseRows, 0, 0, 0,
				func(useUnicode bool) (Terminal, error) { return terminal, nil },
				metric.NewRecordCache(), buffer,
			)
			if err != nil {
				t.Fatalf("New Display err = %v, expected nil", err)
			}
			if _, err = display.Compile(); err != nil {
				t.Fatalf("Compile Display err = %v, expected nil", err)
			}
			if err = display.Load(); err != nil {
				t.Fatalf("Load Display err = %v, expected nil", err)
			}
			display.logOverlay = true
			emit := func(count int) {
				for range count {
					scribe.Log(scribe.SourceDisplay, scribe.SubjectNone, scribe.ActionRender).Info("received", time.Now(), "page fodder")
				}
			}
			emit(capacity)
			display.logRewind()
			previous := uint64(0)
			for page := range testCase.pages {
				pending := page < testCase.pages-1
				if pending {
					emit(capacity)
				}
				display.Logging()
				if display.logNext <= display.logAnchor {
					t.Errorf("page %d rendered: got %d lines, want at least 1", page, display.logNext-display.logAnchor)
				}
				if page > 0 && display.logAnchor != previous {
					t.Errorf("page %d anchor: got %d want %d", page, display.logAnchor, previous)
				}
				behind := display.logNext < buffer.Version()
				if behind != pending {
					t.Errorf("page %d behind: got %v want %v", page, behind, pending)
				}
				previous = display.logNext
				if behind {
					display.logAnchor = display.logNext
				}
			}
			if previous != buffer.Version() {
				t.Errorf("final page end: got %d want %d", previous, buffer.Version())
			}
		})
	}
}

func TestDisplay_LogEntryTallerThanPage(t *testing.T) {
	buffer := scribe.EnableBuffer(slog.LevelDebug, 20)
	t.Cleanup(scribe.Disable)
	scribe.Log(scribe.SourceDisplay, scribe.SubjectNone, scribe.ActionRender).Info(
		"oversize", time.Now(), "[%s]", strings.Repeat("wrapped detail ", 300),
	)
	display := &Display{
		dimsInit:   dimensions{rows: 8, cols: 160},
		logOverlay: true,
		logBuffer:  buffer,
	}
	display.logRewind()
	page, pages := display.logPagination()
	if pages < 2 || page != pages {
		t.Fatalf("live pagination: got %d/%d want multiple pages at the newest", page, pages)
	}
	for expected := pages - 1; expected >= 1; expected-- {
		display.logPageUp()
		page, _ = display.logPagination()
		if page != expected {
			t.Fatalf("page up: got %d want %d", page, expected)
		}
		rows, _, _ := display.logPaged(display.dimsInit.rows - 2)
		if len(rows) == 0 || len(rows) > display.dimsInit.rows-2 {
			t.Fatalf("page up rows: got %d", len(rows))
		}
	}
	for expected := 2; expected <= pages; expected++ {
		display.logPageDown()
		page, _ = display.logPagination()
		if page != expected {
			t.Fatalf("page down: got %d want %d", page, expected)
		}
	}
	display.logPageDown()
	if !display.logFollow {
		t.Fatal("page down from the newest continuation did not resume live follow")
	}
}

func TestDisplay_LogResizePreservesPause(t *testing.T) {
	buffer := scribe.EnableBuffer(slog.LevelDebug, 100)
	t.Cleanup(scribe.Disable)
	for range 40 {
		scribe.Log(scribe.SourceDisplay, scribe.SubjectNone, scribe.ActionRender).Info("resize", time.Now(), "[1] line")
	}
	display := &Display{
		dimsInit:   dimensions{rows: 10, cols: 120},
		logOverlay: true,
		logBuffer:  buffer,
	}
	display.logRewind()
	display.logPageUp()
	anchor := display.logAnchor
	display.dimsInit.cols = 80
	display.logResize()
	if display.logFollow {
		t.Fatal("resize resumed live follow while paused")
	}
	if display.logAnchor != anchor {
		t.Fatalf("resize anchor: got %d want %d", display.logAnchor, anchor)
	}
	display.logPageDown()
	if display.logAnchor <= anchor {
		t.Fatalf("page down after resize: got anchor %d want greater than %d", display.logAnchor, anchor)
	}
	display.logPageUp()
	if display.logAnchor != anchor {
		t.Fatalf("page up after resize: got anchor %d want %d", display.logAnchor, anchor)
	}
}
