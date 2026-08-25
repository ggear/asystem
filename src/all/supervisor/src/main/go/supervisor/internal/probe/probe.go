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
	"sync"
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
	census := metricCensus{}
	for _, task := range tasks {
		cache := p.records()
		if cache == nil {
			scribe.Probe("state", p.name()).Error("metric", tasksStart, "invalid  [%s] metric missing the required cache", metric.GetIDName(task.metricID))
			continue
		}
		if !p.hasMetric(task.metricID) {
			continue
		}
		census.count(runMetricCacheTask(p, isPulse, task), task)
	}
	if !isPulse || census.total == 0 {
		return
	}
	scribe.Probe("profiling", p.name()).Debug("census", tasksStart, "reported [%3d] metrics%s, green [%d] amber [%d] red [%d] unknown [%d]%s",
		census.total, census.subject(), census.green, census.amber, census.red, census.unknown, census.faults())
}

func runMetricCacheTask(p probe, isPulse bool, task cacheMetricTask) string {
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
		scribe.Probe("state", p.name()).Error("metric", taskStart, "invalid  [%s] metric missing required fields [%s]", metric.GetIDName(task.metricID), strings.Join(missing, ","))
		return metricStatusUnknown
	}
	sample, err := task.sampleFunc()
	errored := err != nil && !errors.Is(err, errProbeWarmingUp)
	trackMetricFault(p, task, err, errored)
	task.statsFunc(sample)
	if !isPulse {
		return metricStatusUnknown
	}
	hostName := config.Load(execConfigPath).Host()
	if hostName == "" {
		scribe.Probe("state", p.name()).Error("metric", taskStart, "invalid  [%s] metric missing the host name", metric.GetIDName(task.metricID))
		return metricStatusUnknown
	}
	guid := metric.NewServiceRecordGUID(task.metricID, hostName, task.serviceName)
	pulse := task.pulseFunc()
	if pulse == nil {
		reportMetricStatus(p, task, taskStart, metricStatusUnknown, nil, false, nil, nil, err)
		return metricStatusUnknown
	}
	pulseOK := task.pulseOKFunc(pulse) && !errored
	var valueErr error
	var value *metric.ValueData
	var trendOK *bool
	trend := any(nil)
	if task.trendFunc != nil {
		trend = task.trendFunc()
	}
	if task.trendOKFunc == nil || trend == nil {
		value, valueErr = metric.NewDataPulseValue(pulseOK, pulse)
	} else {
		trended := task.trendOKFunc(trend) && !errored
		trendOK = &trended
		value, valueErr = metric.NewDataValue(pulseOK, pulse, trended, trend)
	}
	if valueErr != nil {
		scribe.Probe("state", p.name()).Error("metric", taskStart, "failed   [%s] metric value builder with [%v]", metric.GetIDName(task.metricID), valueErr)
		return metricStatusUnknown
	}
	record := metric.NewRecord(*value)
	p.records().Store(guid, &record)
	status := metricStatusOf(pulseOK, trendOK)
	reportMetricStatus(p, task, taskStart, status, pulse, pulseOK, trend, trendOK, err)
	return status
}

func trackMetricFault(p probe, task cacheMetricTask, err error, errored bool) {
	key := metricFaultKey{metricID: task.metricID, serviceName: task.serviceName}
	message := ""
	if err != nil {
		message = err.Error()
	}
	metricFaultsMutex.Lock()
	tracked, faulting := metricFaults[key]
	switch {
	case errored && (!faulting || tracked.message != message):
		tracked = &metricFault{message: message, since: time.Now(), logged: time.Now(), polls: 1}
		metricFaults[key] = tracked
	case errored:
		tracked.polls++
	case faulting:
		delete(metricFaults, key)
	}
	fault := metricFault{}
	repeat := false
	if tracked != nil {
		if errored && fault.polls != 1 && time.Since(tracked.logged) >= metricFaultRepeat {
			tracked.logged = time.Now()
			repeat = true
		}
		fault = *tracked
	}
	metricFaultsMutex.Unlock()
	name := metric.GetIDName(task.metricID)
	switch {
	case errored && fault.polls == 1:
		scribe.Probe("state", p.name()).Error("metric", fault.since, "failed   [%s] metric%s with [%v]", name, metricSubject(task), err)
	case errored && repeat:
		scribe.Probe("state", p.name()).Debug("metric", fault.since, "failing  [%s] metric%s for [%d] polls with [%v]", name, metricSubject(task), fault.polls, err)
	case !errored && faulting:
		scribe.Probe("state", p.name()).Info("metric", fault.since, "restored [%s] metric%s after [%d] failed polls with [%s]", name, metricSubject(task), fault.polls, fault.message)
	}
}

func reportMetricStatus(p probe, task cacheMetricTask, taskStart time.Time, status string, pulse any, pulseOK bool, trend any, trendOK *bool, err error) {
	key := metricFaultKey{metricID: task.metricID, serviceName: task.serviceName}
	metricStatusesMutex.Lock()
	previous, seen := metricStatuses[key]
	metricStatuses[key] = status
	metricStatusesMutex.Unlock()
	if seen && previous == status {
		return
	}
	scribe.Probe("state", p.name()).Debug("metric", taskStart, "observed [%s] metric%s status [%s] was [%s] pulse [%v] ok [%v] trend [%v] ok [%v] error [%v]",
		metric.GetIDName(task.metricID), metricSubject(task), status, metricStatusPrevious(seen, previous), metricValue(pulse), pulseOK, metricValue(trend), metricFlag(trendOK), metricError(err))
}

func metricStatusOf(pulseOK bool, trendOK *bool) string {
	if !pulseOK {
		return metricStatusRed
	}
	if trendOK != nil && *trendOK {
		return metricStatusGreen
	}
	return metricStatusAmber
}

func metricStatusPrevious(seen bool, previous string) string {
	if !seen {
		return "none"
	}
	return previous
}

func metricSubject(task cacheMetricTask) string {
	if task.serviceName == metric.ServiceNameUnset {
		return ""
	}
	return fmt.Sprintf(" service [%s]", task.serviceName)
}

func metricValue(value any) any {
	if value == nil {
		return "none"
	}
	return value
}

func metricError(err error) any {
	if err == nil {
		return "none"
	}
	return err
}

func metricFlag(value *bool) any {
	if value == nil {
		return "none"
	}
	return *value
}

type metricFaultKey struct {
	metricID    metric.ID
	serviceName string
}

type metricFault struct {
	message string
	since   time.Time
	logged  time.Time
	polls   int
}

type metricCensus struct {
	total   int
	green   int
	amber   int
	red     int
	unknown int
	service string
	faulted []string
}

func (c *metricCensus) count(status string, task cacheMetricTask) {
	c.total++
	c.service = task.serviceName
	switch status {
	case metricStatusGreen:
		c.green++
	case metricStatusAmber:
		c.amber++
		c.faulted = append(c.faulted, metric.GetIDName(task.metricID)+"="+status)
	case metricStatusRed:
		c.red++
		c.faulted = append(c.faulted, metric.GetIDName(task.metricID)+"="+status)
	default:
		c.unknown++
	}
}

func (c *metricCensus) subject() string {
	if c.service == metric.ServiceNameUnset {
		return ""
	}
	return fmt.Sprintf(" of service [%s]", c.service)
}

func (c *metricCensus) faults() string {
	if len(c.faulted) == 0 {
		return ""
	}
	return fmt.Sprintf(", not green [%s]", strings.Join(c.faulted, " "))
}

const (
	metricFaultRepeat = time.Minute
)

const (
	metricStatusGreen   = "green"
	metricStatusAmber   = "amber"
	metricStatusRed     = "red"
	metricStatusUnknown = "unknown"
)

var (
	metricFaults        = map[metricFaultKey]*metricFault{}
	metricFaultsMutex   sync.Mutex
	metricStatuses      = map[metricFaultKey]string{}
	metricStatusesMutex sync.Mutex
)

var execPeriods config.Periods
var execProbes map[probe][metric.MetricMax]bool
var execConfigPath string
