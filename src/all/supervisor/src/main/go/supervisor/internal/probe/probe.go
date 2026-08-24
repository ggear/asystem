package probe

import (
	"context"
	"errors"
	"fmt"
	"reflect"
	"strings"
	"supervisor/internal/config"
	"supervisor/internal/metric"
	"supervisor/internal/scribe"
	"supervisor/internal/stats"
	"time"
)

func Create(configPath string, cache *metric.RecordCache, periods config.Periods) error {
	if cache == nil {
		return fmt.Errorf("cache cannot be nil")
	}
	if periods.PollMillis < 1 {
		return fmt.Errorf("invalid poll period [%d]ms, must be >= 1", periods.PollMillis)
	}
	if periods.PulseMillis < 1 {
		return fmt.Errorf("invalid pulse period [%d]ms, must be >= 1", periods.PulseMillis)
	}
	if periods.TrendHours > 0 && periods.PollMillis < 1000 {
		return fmt.Errorf("invalid poll period [%d]ms, must be >= 1000ms when trend is enabled", periods.PollMillis)
	}
	if periods.TrendHours > 0 && periods.PulseMillis < 1000 {
		return fmt.Errorf("invalid pulse period [%d]ms, must be >= 1000ms when trend is enabled", periods.PulseMillis)
	}
	pulseEveryTick := periods.PulseMillis / periods.PollMillis
	if pulseEveryTick*periods.PollMillis != periods.PulseMillis {
		return fmt.Errorf("pulse period [%d]ms is not a whole multiple of poll period [%d]ms", periods.PulseMillis, periods.PollMillis)
	}
	probeMap := map[probe][metric.MetricMax]bool{}
	registerStart := time.Now()
	for _, id := range cache.IDs() {
		if id < 0 || id >= metric.MetricMax {
			continue
		}
		p := probesByMetricMask[id]
		if p == nil {
			scribe.Probe("state", "*").Error("create", registerStart, "missing  [%d] no probe registered for the metric", id)
			continue
		}
		mask := probeMap[p]
		mask[id] = true
		probeMap[p] = mask
	}
	createStart := time.Now()
	for p, mask := range probeMap {
		probeCreateStart := time.Now()
		err := p.create(configPath, cache, mask, periods)
		if err != nil {
			scribe.Probe("state", p.name()).Error("create", probeCreateStart, "failed with [%v]", err)
			delete(probeMap, p)
			scribe.Probe("profiling", p.name()).Debug("create", probeCreateStart, "success  [false], removed from the poll set")
			continue
		}
		scribe.Probe("profiling", p.name()).Debug("create", probeCreateStart, "success  [true], metrics [%d]", len(p.metrics()))
	}
	scribe.Probe("profiling", "*").Debug("create", createStart, "success  [true], created [%d] probes", len(probeMap))
	execProbes = probeMap
	execPeriods = periods
	execConfigPath = configPath
	return nil
}

func Run(ctx context.Context, onPulse func(isHeartbeat bool)) error {
	if execProbes == nil {
		return fmt.Errorf("create must be called before run")
	}
	pulseEveryTick := execPeriods.PulseMillis / execPeriods.PollMillis
	pulseTickCount := 1
	heartbeatEveryPulse := execPeriods.HeartbeatSecs * 1000 / execPeriods.PulseMillis
	heartbeatPulseCount := 1
	ticker := time.NewTicker(time.Duration(execPeriods.PollMillis) * time.Millisecond)
	defer ticker.Stop()
	for {
		select {
		case <-ctx.Done():
			return ctx.Err()
		case <-ticker.C:
			tickStart := time.Now()
			pulseTickCount--
			isPulse := false
			if pulseTickCount == 0 {
				isPulse = true
				pulseTickCount = pulseEveryTick
			}
			phase := "tick"
			if isPulse {
				phase = "pulse"
			}
			for p := range execProbes {
				probeStart := time.Now()
				if err := p.run(ctx, isPulse); err != nil {
					scribe.Probe("state", p.name()).Error(phase, probeStart, "failed with [%v]", err)
				}
				scribe.Probe("profiling", p.name()).Debug(phase, probeStart, "polled   [%d] metrics", len(p.metrics()))
			}
			if isPulse {
				heartbeatPulseCount--
				isHeartbeat := heartbeatPulseCount <= 0
				if isHeartbeat {
					heartbeatPulseCount = heartbeatEveryPulse
				}
				if onPulse != nil {
					onPulse(isHeartbeat)
				}
			}
			scribe.Probe("profiling", "*").Debug(phase, tickStart, "polled   [%d] probes", len(execProbes))
		}
	}
}

type probe interface {
	name() string
	metrics() []metric.ID
	create(configPath string, cache *metric.RecordCache, mask [metric.MetricMax]bool, periods config.Periods) error
	run(ctx context.Context, isPulse bool) error
	records() *metric.RecordCache
	hasMetric(metric.ID) bool
}

var probesByMetricMask [metric.MetricMax]probe

var errProbeWarmingUp = errors.New("probe is still warming up")

const bytesPerMiB = 1 << 20

func init() {
	registerProbes(
		func() probe { return newServicesProbe() },
		func() probe { return newHostProbe() },
	)
	verifyProbes()
}

func registerProbes(builders ...func() probe) []probe {
	created := make([]probe, 0, len(builders))
	for _, build := range builders {
		probe := build()
		registerProbe(probe)
		created = append(created, probe)
	}
	return created
}

func registerProbe(probe probe) {
	if probe == nil {
		panic("nil probe registration")
	}
	for _, id := range probe.metrics() {
		if id >= 0 && id < metric.MetricMax {
			if probesByMetricMask[id] != nil && probesByMetricMask[id] != probe {
				thisType := reflect.TypeOf(probe)
				if thisType.Kind() == reflect.Ptr {
					thisType = thisType.Elem()
				}
				thatType := reflect.TypeOf(probesByMetricMask[id])
				if thatType.Kind() == reflect.Ptr {
					thatType = thatType.Elem()
				}
				panic(fmt.Sprintf("multiple execProbes [%s,%s] registering metric ID [%d]", thisType.Name(), thatType.Name(), id))
			}
			probesByMetricMask[id] = probe
		}
	}
}

func verifyProbes() {
	for _, id := range metric.GetIDs() {
		if probesByMetricMask[id] == nil {
			panic(fmt.Sprintf("no probe registered for metric ID [%d]", id))
		}
	}
}

type cacheMetricTask struct {
	valueKind   metric.ValueKind
	metricID    metric.ID
	serviceName string
	sampleFunc  func() (any, error)
	statsFunc   func(any)
	pulseFunc   func() any
	trendFunc   func() any
	pulseOKFunc func(any) bool
	trendOKFunc func(any) bool
}

func newCacheMetricTask[T any](
	valueKind metric.ValueKind,
	metricID metric.ID,
	serviceName string,
	sampleFunc func() (T, error),
	statsField stats.Stats[T],
	pulseFunc func() T,
	trendFunc func() T,
	pulseOKFunc func(T) bool,
	trendOKFunc func(T) bool,
) cacheMetricTask {
	task := cacheMetricTask{
		valueKind:   valueKind,
		metricID:    metricID,
		serviceName: serviceName,
		sampleFunc: func() (any, error) {
			return sampleFunc()
		},
		statsFunc: func(value any) {
			statsField.PushAndTick(value.(T))
		},
		pulseFunc: func() any {
			return pulseFunc()
		},
		trendFunc: func() any {
			if trendFunc == nil {
				return nil
			}
			return trendFunc()
		},
		pulseOKFunc: func(value any) bool {
			return pulseOKFunc(value.(T))
		},
	}
	if trendFunc != nil {
		task.trendFunc = func() any {
			return trendFunc()
		}
	}
	if trendOKFunc != nil {
		task.trendOKFunc = func(value any) bool {
			return trendOKFunc(value.(T))
		}
	}
	return task
}

func runMetricCacheTasks(p probe, isPulse bool, tasks []cacheMetricTask) {
	tasksStart := time.Now()
	for _, task := range tasks {
		cache := p.records()
		if cache == nil {
			scribe.Probe("state", p.name()).Error("metric", tasksStart, "invalid  [%d] metric missing the required cache", task.metricID)
			continue
		}
		if !p.hasMetric(task.metricID) {
			continue
		}
		runMetricCacheTask(p, isPulse, task)
	}
}

func runMetricCacheTask(p probe, isPulse bool, task cacheMetricTask) {
	taskStart := time.Now()
	var missing []string
	if task.sampleFunc == nil {
		missing = append(missing, "sampleFunc")
	}
	if task.statsFunc == nil {
		missing = append(missing, "statsField")
	}
	if task.pulseFunc == nil {
		missing = append(missing, "pulseFunc")
	}
	if task.pulseOKFunc == nil {
		missing = append(missing, "pulseOKFunc")
	}
	if len(missing) > 0 {
		scribe.Probe("state", p.name()).Error("metric", taskStart, "invalid  [%d] metric missing required fields [%s]", task.metricID, strings.Join(missing, ","))
		return
	}
	sample, err := task.sampleFunc()
	errored := err != nil && !errors.Is(err, errProbeWarmingUp)
	if errored {
		scribe.Probe("state", p.name()).Error("metric", taskStart, "failed   [%d] metric with [%v]", task.metricID, err)
	}
	task.statsFunc(sample)
	if !isPulse {
		return
	}
	hostName := config.Load(execConfigPath).Host()
	if hostName == "" {
		scribe.Probe("state", p.name()).Error("metric", taskStart, "invalid  [%d] metric missing the host name", task.metricID)
		return
	}
	guid := metric.NewServiceRecordGUID(task.metricID, hostName, task.serviceName)
	pulse := task.pulseFunc()
	if pulse == nil {
		return
	}
	pulseOK := task.pulseOKFunc(pulse) && !errored
	var valueErr error
	var value *metric.ValueData
	trend := any(nil)
	if task.trendFunc != nil {
		trend = task.trendFunc()
	}
	if task.trendOKFunc == nil || trend == nil {
		value, valueErr = metric.NewDataPulseValue(pulseOK, pulse)
	} else {
		trendOK := task.trendOKFunc(trend) && !errored
		value, valueErr = metric.NewDataValue(pulseOK, pulse, trendOK, trend)
	}
	if valueErr != nil {
		scribe.Probe("state", p.name()).Error("metric", taskStart, "failed   [%d] metric value builder with [%v]", task.metricID, valueErr)
		return
	}
	record := metric.NewRecord(*value)
	p.records().Store(guid, &record)
}

var execPeriods config.Periods
var execProbes map[probe][metric.MetricMax]bool
var execConfigPath string
