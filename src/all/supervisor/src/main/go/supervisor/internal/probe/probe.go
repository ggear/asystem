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
	"sync/atomic"
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
			scribe.Log(scribe.SourceProbe, scribe.SubjectMetric(id), scribe.ActionStart).Error("rejected", registerStart, "no probe registered for the metric")
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
			scribe.Log(scribe.SourceProbe, scribe.SubjectNone, scribe.ActionStart).Error("faulting", probeCreateStart, "probe [%s] with [%v]", p.name(), err)
			delete(probeMap, p)
			scribe.Log(scribe.SourceProbe, scribe.SubjectNone, scribe.ActionStart).Debug("removals", probeCreateStart, "probe [%s] removed from the poll set", p.name())
			continue
		}
		scribe.Log(scribe.SourceProbe, scribe.SubjectNone, scribe.ActionStart).Debug("prepared", probeCreateStart, "probe [%s] metrics [%d]", p.name(), len(p.metrics()))
	}
	scribe.Log(scribe.SourceProbe, scribe.SubjectNone, scribe.ActionStart).Debug("prepared", createStart, "probes [%d]", len(probeMap))
	verifyGates(probeMap)
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
			execPulsing.Store(isPulse)
			if isPulse {
				execPulses.Add(1)
			}
			for p := range execProbes {
				probeStart := time.Now()
				if err := p.run(ctx, isPulse); err != nil {
					scribe.Log(scribe.SourceProbe, scribe.SubjectNone, scribe.ActionSample).Error("faulting", probeStart, "probe [%s] pulse [%v] with [%v]", p.name(), isPulse, err)
				}
				scribe.Log(scribe.SourceProbe, scribe.SubjectNone, scribe.ActionSample).Debug("reported", probeStart, "probe [%s] pulse [%v] metrics [%d]", p.name(), isPulse, len(p.metrics()))
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
			scribe.Log(scribe.SourceProbe, scribe.SubjectNone, scribe.ActionSample).Debug("reported", tickStart, "pulse [%v] probes [%d]", isPulse, len(execProbes))
		}
	}
}

type probe interface {
	name() string
	metrics() []metric.ID
	gates() []metric.GateID
	create(configPath string, cache *metric.RecordCache, mask [metric.MetricMax]bool, periods config.Periods) error
	run(ctx context.Context, isPulse bool) error
	records() *metric.RecordCache
	hasMetric(metric.ID) bool
}

var probesByMetricMask [metric.MetricMax]probe

var errProbeWarmingUp = errors.New("probe is still warming up")

var errEnvironment = errors.New("environment cannot supply this reading")

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

type derivation struct {
	action scribe.Action
	detail string
	args   []any
}

func derived(action scribe.Action, detail string, args ...any) derivation {
	return derivation{action: action, detail: detail, args: args}
}

func (d derivation) empty() bool {
	return d.detail == ""
}

type cacheMetricTask struct {
	valueKind   metric.ValueKind
	metricID    metric.ID
	serviceName string
	sampleFunc  func() (any, derivation, error)
	statsFunc   func(any)
	pulseFunc   func() any
	trendFunc   func() any
}

func newCacheMetricTask[T any](
	valueKind metric.ValueKind,
	metricID metric.ID,
	serviceName string,
	sampleFunc func() (T, derivation, error),
	statsField stats.Stats[T],
	pulseFunc func() T,
	trendFunc func() T,
) cacheMetricTask {
	task := cacheMetricTask{
		valueKind:   valueKind,
		metricID:    metricID,
		serviceName: serviceName,
		sampleFunc: func() (any, derivation, error) {
			return sampleFunc()
		},
		statsFunc: func(value any) {
			statsField.PushAndTick(value.(T))
		},
		pulseFunc: func() any {
			return pulseFunc()
		},
	}
	if trendFunc != nil {
		task.trendFunc = func() any {
			return trendFunc()
		}
	}
	return task
}

func runMetricCacheTasks(p probe, isPulse bool, gates gateSet, tasks []cacheMetricTask) {
	tasksStart := time.Now()
	census := metricCensus{}
	for _, task := range tasks {
		cache := p.records()
		if cache == nil {
			scribe.Log(scribe.SourceProbe, scribe.SubjectMetric(task.metricID), scribe.ActionSample).Error("unusable", tasksStart, "metric missing the required cache")
			continue
		}
		if !p.hasMetric(task.metricID) {
			continue
		}
		census.count(runMetricCacheTask(p, isPulse, gates, task), task)
	}
	if !isPulse || census.total == 0 {
		return
	}
	scribe.Log(scribe.SourceProbe, scribe.SubjectNone, scribe.ActionCensus).Debug("reported", tasksStart, "probe [%s] metrics [%3d]%s, green [%d] amber [%d] red [%d] unknown [%d]%s",
		p.name(), census.total, census.subject(), census.green, census.amber, census.red, census.unknown, census.faults())
}

func runMetricCacheTask(p probe, isPulse bool, gates gateSet, task cacheMetricTask) string {
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
	if metric.GetIDPulseRule(task.metricID).IsZero() {
		missing = append(missing, "pulseRule")
	}
	if len(missing) > 0 {
		scribe.Log(scribe.SourceProbe, scribe.SubjectMetric(task.metricID), scribe.ActionSample).Error("unusable", taskStart, "metric missing required fields [%s]", strings.Join(missing, ","))
		return metricStatusUnknown
	}
	sample, derivation, err := task.sampleFunc()
	errored := err != nil && !errors.Is(err, errProbeWarmingUp)
	trackMetricFault(p, task, err, errored)
	task.statsFunc(sample)
	if !isPulse {
		return metricStatusUnknown
	}
	reportMetricDerivation(p, task, taskStart, derivation, err)
	hostName := config.Load(execConfigPath).Host()
	if hostName == "" {
		scribe.Log(scribe.SourceProbe, scribe.SubjectMetric(task.metricID), scribe.ActionSample).Error("unusable", taskStart, "metric missing the host name")
		return metricStatusUnknown
	}
	guid := metric.NewServiceRecordGUID(task.metricID, hostName, task.serviceName)
	pulse := task.pulseFunc()
	if pulse == nil {
		reportMetricStatus(p, task, taskStart, metricStatusUnknown, nil, false, nil, nil, err)
		return metricStatusUnknown
	}
	unit := metric.GetIDUnit(task.metricID)
	pulseValue, pulseNumeric := numericValue(pulse)
	pulseResult := metric.GetIDPulseRule(task.metricID).Evaluate(unit, pulseValue, pulseNumeric,
		siblingResolver(p, hostName, false), gates.resolve)
	pulseOK := pulseResult.OK && !errored
	var valueErr error
	var value *metric.ValueData
	var trendOK *bool
	trendRule := metric.GetIDTrendRule(task.metricID)
	trend := any(nil)
	if task.trendFunc != nil {
		trend = task.trendFunc()
	}
	var trendResult metric.RuleResult
	if trendRule.IsZero() || trend == nil {
		value, valueErr = metric.NewDataPulseValue(pulseOK, pulse)
	} else {
		trendValue, trendNumeric := numericValue(trend)
		trendResult = trendRule.Evaluate(unit, trendValue, trendNumeric,
			siblingResolver(p, hostName, true), gates.resolve)
		trended := trendResult.OK && !errored
		trendOK = &trended
		value, valueErr = metric.NewDataValue(pulseOK, pulse, trended, trend)
	}
	reportMetricRule(task.metricID, taskStart, pulseOK, pulseResult.Detail, trendOK, trendResult.Detail)
	if valueErr != nil {
		scribe.Log(scribe.SourceProbe, scribe.SubjectMetric(task.metricID), scribe.ActionCompute).Error("faulting", taskStart, "metric value builder with [%v]", valueErr)
		return metricStatusUnknown
	}
	record := metric.NewRecord(*value)
	p.records().Store(guid, &record)
	status := metricStatusOf(pulseOK, trendOK)
	reportMetricStatus(p, task, taskStart, status, pulse, pulseOK, trend, trendOK, err)
	return status
}

func derivePulse(logger scribe.Logger, verb string, started time.Time, detail string, args ...any) {
	if !execPulsing.Load() {
		return
	}
	logger.Debug(verb, started, detail, args...)
}

func splitVerb(text string) (string, string) {
	trimmed := strings.TrimLeft(text, " ")
	index := strings.IndexByte(trimmed, ' ')
	if index < 0 {
		return trimmed, ""
	}
	return trimmed[:index], strings.TrimLeft(trimmed[index:], " ")
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
	logger := scribe.Log(scribe.SourceProbe, scribe.SubjectMetric(task.metricID), scribe.ActionSample)
	switch {
	case errored && fault.polls == 1 && errors.Is(err, errEnvironment):
		logger.Warn("faulting", fault.since, "metric%s with [%v]", metricSubject(task), err)
	case errored && fault.polls == 1:
		logger.Error("faulting", fault.since, "metric%s with [%v]", metricSubject(task), err)
	case errored && repeat:
		logger.Debug("faulting", fault.since, "metric%s for [%d] polls with [%v]", metricSubject(task), fault.polls, err)
	case !errored && faulting:
		logger.Info("restored", fault.since, "metric%s after [%d] failed polls with [%s]", metricSubject(task), fault.polls, fault.message)
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
	scribe.Log(scribe.SourceProbe, scribe.SubjectMetric(task.metricID), scribe.ActionCompute).Debug("observed", taskStart, "metric%s status [%s] was [%s] pulse [%v] ok [%v] trend [%v] ok [%v] error [%v]",
		metricSubject(task), status, metricStatusPrevious(seen, previous), metricValue(pulse), pulseOK, metricValue(trend), metricFlag(trendOK), metricError(err))
}

func reportMetricRule(metricID metric.ID, taskStart time.Time, pulseOK bool, pulseText string, trendOK *bool, trendText string) {
	logger := scribe.Log(scribe.SourceProbe, scribe.SubjectMetric(metricID), scribe.ActionCompute)
	if trendOK == nil {
		derivePulse(logger, "computed", taskStart, "ok pulse [%v] %s", pulseOK, pulseText)
		return
	}
	derivePulse(logger, "computed", taskStart, "ok pulse [%v] %s, ok trend [%v] %s", pulseOK, pulseText, *trendOK, trendText)
}

func numericValue(value any) (float64, bool) {
	switch typed := value.(type) {
	case int8:
		return float64(typed), true
	case float64:
		return typed, true
	default:
		return 0, false
	}
}

func stub[T any](id metric.ID) (T, derivation, error) {
	var value T
	return value, stubDerivation(id, value), nil
}

func stubDerivation(id metric.ID, value any) derivation {
	return derived(scribe.ActionCompute, "computed [%v] fixed, metric [%s] is an unimplemented stub so it never varies and is always ok",
		value, metric.GetIDName(id))
}

func reportMetricDerivation(p probe, task cacheMetricTask, taskStart time.Time, d derivation, err error) {
	if d.empty() {
		if err == nil {
			scribe.Log(scribe.SourceProbe, scribe.SubjectMetric(task.metricID), scribe.ActionCompute).Error("unstated", taskStart,
				"metric%s published a value stating no derivation, so nothing explains how it was arrived at", metricSubject(task))
		}
		return
	}
	rendered := d.detail
	if len(d.args) > 0 {
		rendered = fmt.Sprintf(d.detail, d.args...)
	}
	verb, detail := splitVerb(rendered)
	scribe.Log(scribe.SourceProbe, scribe.SubjectMetric(task.metricID), d.action).Debug(verb, taskStart, detail)
}

func metricProbeName(id metric.ID) string {
	if id < 0 || id >= metric.MetricMax || probesByMetricMask[id] == nil {
		return "*"
	}
	return probesByMetricMask[id].name()
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

var execPulsing atomic.Bool

var execPulses atomic.Int64

var execPeriods config.Periods
var execProbes map[probe][metric.MetricMax]bool
var execConfigPath string
