package engine

import (
	"context"
	"errors"
	"supervisor/internal/config"
	"supervisor/internal/metric"
	"supervisor/internal/probe"
	"time"
)

// DONE:
//  - Indexer to ignore Shadows
//  - Update Size() to ignore schema
//  - Remove index from newCacheMetricTask
//  - Make sure display reconciles ServiceIndexSchema to ServiceIndex for GUID on lookup
//  - Add probe profile debug logs
//  - Add config services, test
//  - Make sure Evict to only work on non __SCHEMA services, to only evict from specific host and service name, to set value to nil
//  - Delete to only work on non __SCHEMA services, to only delete from specific host and service name, to only delete if value is nil
// TODO:
//  - Implement cache Purge func and routine for stream, Evict and Delete across entire cache.
//  - Purge invoked as a goroutine for stream, procedurally for probes in execute
//  - Implement all Load funcs and test cases
//  - drawValue to ~ out if necessary
//  - Implement display update tests
//  - Validate hot path is fast, validate dont recompute tags/topics

func LoadAllProbesOnce(configPath string, cache *metric.RecordCache) error {
	hostName := config.LocalHostName()
	if hostName == "" {
		return errors.New("cannot resolve local host name")
	}
	for _, id := range metric.GetIDs() {
		record := metric.NewRecord(metric.NewNilValue())
		cache.Store(metric.NewServiceSchemaRecordGUID(id, hostName, 0), &record)
	}
	periods := config.Periods{
		PollSecs:     1,
		PulseSecs:    1,
		TrendHours:   0,
		CacheHours:   0,
		SnapshotMins: 0,
	}
	if err := probe.Create(configPath, cache, periods); err != nil {
		return err
	}
	timeout := time.Duration(2.25*periods.PulseSecs) * time.Second
	ctx, cancel := context.WithTimeout(context.Background(), timeout)
	defer cancel()
	err := probe.Execute(ctx)
	if err != nil && !errors.Is(err, context.DeadlineExceeded) {
		return err
	}
	return nil
}

func LoadListeningProbesLoop(cache *metric.RecordCache, periods config.Periods) error {
	_ = periods
	// TODO:
	//  - Loop over listeners, load each and its deps into cache
	//  - Start probes, writing to cache per metric
	return nil
}

func LoadListeningStreamLoop(cache *metric.RecordCache, periods config.Periods) error {
	_ = periods
	// TODO:
	//  - Loop over listeners, load each into cache (not deps)
	//  - Start topic subscriptions, writing to cache per metric
	//  - Start reaper routine, if timestamp > poll period + 1, set to nil
	return nil
}

func LoadAllProbesPublishLoop(cache *metric.RecordCache, periods config.Periods) error {
	_ = periods
	// TODO:
	//  - Loop over all metrics and load into cache
	//  - Start probes, writing to cache per metric (necessary for deps, not for JSON/LineProto),
	//                  writing async cache.publishStream by value (JSON) per metric,
	//                  writing line protocol to reused buffer per metric,
	//                  writing async cache.publishHistory by value (ValueString LineProto) at the end fo cycle
	return nil
}
