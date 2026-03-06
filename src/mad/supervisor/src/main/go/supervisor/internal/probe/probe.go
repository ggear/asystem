package probe

import (
	"context"
	"errors"
	"fmt"
	"log/slog"
	"math"
	"reflect"
	"strings"
	"supervisor/internal/config"
	"supervisor/internal/metric"
	"supervisor/internal/stats"
	"time"
)

func Create(configPath string, cache *metric.RecordCache, periods config.Periods) error {
	if cache == nil {
		return fmt.Errorf("cache cannot be nil")
	}
	if periods.PollSecs <= 0 {
		return fmt.Errorf("invalid poll period [%g] seconds", periods.PollSecs)
	}
	if periods.PulseSecs <= 0 {
		return fmt.Errorf("invalid pulse period period [%g] seconds", periods.PulseSecs)
	}
	pulseEveryTick := int(math.Round(periods.PulseSecs / periods.PollSecs))
	if math.Abs(float64(pulseEveryTick)*periods.PollSecs-periods.PulseSecs) > 1e-9 {
		return fmt.Errorf("pulseFunc period [%g] is not a whole multiple of poll period [%g]", periods.PulseSecs, periods.PollSecs)
	}
	probeMap := map[probe][metric.MetricMax]bool{}
	for _, id := range cache.IDs() {
		if id < 0 || id >= metric.MetricMax {
			continue
		}
		p := probesByMetricMask[id]
		if p == nil {
			slog.Error("no probe registered", "metric_id", id)
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
			slog.Error("error creating probe", "probe", p.name(), "error", err)
			delete(probeMap, p)
			slog.Debug("profiling", "probe", p.name(), "phase", "create_probe", "duration", time.Since(probeCreateStart), "success", false)
			continue
		}
		slog.Debug("profiling", "probe", p.name(), "phase", "create_probe", "duration", time.Since(probeCreateStart), "success", true)
	}
	slog.Debug("profiling", "probe", "*", "phase", "create_probe", "duration", time.Since(createStart))
	execProbes = probeMap
	execPeriods = periods
	return nil
}

func Execute(ctx context.Context) error {
	if ctx == nil {
		return fmt.Errorf("context cannot be nil")
	}
	if execProbes == nil {
		return fmt.Errorf("Create must be called before Execute")
	}
	pulseEveryTick := int(math.Round(execPeriods.PulseSecs / execPeriods.PollSecs))
	pulseTickCount := pulseEveryTick
	ticker := time.NewTicker(time.Duration(execPeriods.PollSecs * float64(time.Second)))
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
			for p := range execProbes {
				probeStart := time.Now()
				if err := p.execute(isPulse); err != nil {
					slog.Error("error executing probe", "probe", p.name(), "error", err)
				}
				slog.Debug("profiling", "probe", p.name(), "phase", "execute_tick", "duration", time.Since(probeStart), "is_pulse", isPulse)
			}
			slog.Debug("profiling", "probe", "*", "phase", "execute_tick", "duration", time.Since(tickStart), "is_pulse", isPulse)
		}
	}
}

type probe interface {
	name() string
	metrics() []metric.ID
	create(configPath string, cache *metric.RecordCache, mask [metric.MetricMax]bool, periods config.Periods) error
	execute(isPulse bool) error
	metricCache() *metric.RecordCache
	hasMetric(metric.ID) bool
}

var probesByMetricMask [metric.MetricMax]probe

var errProbeWarmingUp = errors.New("probe is still warming up")

func init() {
	registerProbes(
		func() probe { return newServicesProbe() },
		func() probe { return newSupervisorProbe() },
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

func executeMetricCacheTasks(p probe, isPulse bool, tasks []cacheMetricTask) {
	for _, task := range tasks {
		cache := p.metricCache()
		if cache == nil {
			slog.Error("metric task missing required cache", "id", task.metricID)
			continue
		}
		if !p.hasMetric(task.metricID) {
			continue
		}
		executeMetricCacheTask(p, isPulse, task)
	}
}

func executeMetricCacheTask(p probe, isPulse bool, task cacheMetricTask) {
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
		slog.Error("metric task missing required field", "id", task.metricID, "missing", strings.Join(missing, ","))
		return
	}
	sample, err := task.sampleFunc()
	if err != nil && !errors.Is(err, errProbeWarmingUp) {
		slog.Error("error executing metric task", "id", task.metricID, "error", err)
		return
	}
	task.statsFunc(sample)
	if !isPulse {
		return
	}
	hostName := config.LocalHostName()
	if hostName == "" {
		slog.Error("metric task missing hostName name", "id", task.metricID)
		return
	}
	guid := metric.NewServiceRecordGUID(task.metricID, hostName, task.serviceName)
	pulse := task.pulseFunc()
	pulseOK := task.pulseOKFunc(pulse)
	var valueErr error
	var value *metric.ValueData
	if task.trendFunc == nil || task.trendOKFunc == nil {
		value, valueErr = metric.NewDataPulseValue(pulseOK, pulse)
	} else {
		trend := task.trendFunc()
		trendOK := task.trendOKFunc(trend)
		value, valueErr = metric.NewDataValue(pulseOK, pulse, trendOK, trend)
	}
	if valueErr != nil {
		slog.Error("metric task value builder error", "id", task.metricID, "error", valueErr)
		return
	}
	record := metric.NewRecord(*value)
	p.metricCache().Store(guid, &record)
}

var execPeriods config.Periods
var execProbes map[probe][metric.MetricMax]bool
