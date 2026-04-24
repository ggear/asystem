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
	"supervisor/internal/testutil"
	"testing"

	"github.com/divan/num2words"
	"github.com/mattn/go-runewidth"
	"github.com/sergi/go-diff/diffmatchpatch"
)

func TestDisplay(t *testing.T) {
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
					cache,
					func(useUnicode bool) (Terminal, error) { return terminal, nil },
					caseHosts,
					caseTerminalDims.cols,
					caseTerminalDims.rows,
					0,
					0,
					attemptedFormat,
					testCase.useUnicode,
					config.Periods{},
					true,
					"",
					nil,
					0,
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
					for i := 0; i < len(services); i++ {
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

func TestDisplaySad(t *testing.T) {
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
				metric.NewRecordCache(),
				func(useUnicode bool) (Terminal, error) {
					return newTerminalVirtual(testCase.dims.rows, testCase.dims.cols, ThemeDark, useUnicode), nil
				},
				testCase.hosts,
				testCase.dims.cols,
				testCase.dims.rows,
				0,
				0,
				testCase.format,
				testCase.useUnicode,
				config.Periods{},
				true,
				"",
				nil,
				0,
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

func TestFormatDurationShort(t *testing.T) {
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

func TestDisplay_Highlight(t *testing.T) {
	tests := []struct {
		name     string
		pulse    *bool
		trend    *bool
		expected colour
	}{
		{
			name:     "happy_pulse_trend",
			pulse:    testutil.BoolToPtr(true),
			trend:    testutil.BoolToPtr(true),
			expected: colourCheer,
		},
		{
			name:     "happy_pulse_only",
			pulse:    testutil.BoolToPtr(true),
			trend:    testutil.BoolToPtr(false),
			expected: colourWarn,
		},
		{
			name:     "happy_no_pulse",
			pulse:    testutil.BoolToPtr(false),
			trend:    testutil.BoolToPtr(true),
			expected: colourAlert,
		},
		{
			name:     "happy_no_pulse_no_trend",
			pulse:    testutil.BoolToPtr(false),
			trend:    testutil.BoolToPtr(false),
			expected: colourAlert,
		},
		{
			name:     "happy_nil_pulse",
			pulse:    nil,
			trend:    testutil.BoolToPtr(true),
			expected: colourChat,
		},
		{
			name:     "happy_nil_trend",
			pulse:    testutil.BoolToPtr(true),
			trend:    nil,
			expected: colourWarn,
		},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			rendered := highlight(testCase.pulse, testCase.trend)
			if rendered != testCase.expected {
				t.Fatalf("Got render = %v, expected %v", rendered, testCase.expected)
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
