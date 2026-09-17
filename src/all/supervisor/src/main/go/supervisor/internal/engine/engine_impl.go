package engine

import (
	"context"
	"errors"
	"supervisor/internal/config"
	"supervisor/internal/metric"
	"supervisor/internal/probe"
	"supervisor/internal/scribe"
	"time"
)

// RunAllProbesOnce runs every probe for a single pulse cycle, then exits.
//
// Flow:
//  1. Seed a nil record for every metric ID.
//  2. Create the probes with every metric registered, and with no trend tracking.
//  3. Run once, under a timeout of three pulses, being 3s by default.
//
// Notes:
//   - The cache belongs to the caller and is discarded on return, so nothing here needs removing.
func RunAllProbesOnce(ctx context.Context, configPath string, cache *metric.RecordCache) {
	for _, id := range metric.GetIDs() {
		record := metric.NewRecord(metric.NewNilValue())
		cache.Store(metric.NewServiceSchemaRecordGUID(id, metric.GetIDHost(id, config.Load(configPath).Host()), 0), &record)
	}
	periods := config.Periods{
		PollMillis:   500,
		PulseMillis:  1000,
		TrendHours:   0,
		CacheMins:    0,
		SnapshotMins: 0,
	}
	createStart := time.Now()
	if err := probe.Create(configPath, cache, periods); err != nil {
		scribe.Log(scribe.SourceEngine, scribe.SubjectNone, scribe.ActionStart).Errorf("faulting", createStart, "[%s] loop with [%v]", loopAllProbesOnce, err)
		return
	}
	timeout := time.Duration(3*periods.PulseMillis) * time.Millisecond
	ctx, cancel := context.WithTimeout(ctx, timeout)
	defer cancel()
	runStart := time.Now()
	err := probe.RunPoll(ctx, nil)
	if err != nil && !errors.Is(err, context.DeadlineExceeded) {
		scribe.Log(scribe.SourceEngine, scribe.SubjectNone, scribe.ActionStop).Errorf("faulting", runStart, "[%s] loop with [%v]", loopAllProbesOnce, err)
	}
}

const loopAllProbesOnce = "all probes once"
