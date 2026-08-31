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

type probe interface {
	subject() scribe.Subject
	metrics() []metric.ID
	gates() []metric.GateID
	create(configPath string, cache *metric.RecordCache, mask [metric.MetricMax]bool, periods config.Periods) error
	run(ctx context.Context, isPulse bool) error
	records() *metric.RecordCache
	hasMetric(metric.ID) bool
}

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
		p := probesByMetricID[id]
		if p == nil {
			scribe.Log(scribe.SourceProbe, scribe.SubjectMetric(id), scribe.ActionStart).Errorf("rejected", registerStart, "[none] probe registered")
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
			scribe.Log(scribe.SourceProbe, p.subject(), scribe.ActionStart).Errorf("faulting", probeCreateStart, "[create] failed with [%v]", err)
			delete(probeMap, p)
			scribe.Log(scribe.SourceProbe, p.subject(), scribe.ActionStart).Debugf("removals", probeCreateStart, "[removed] from the poll set")
			continue
		}
		scribe.Log(scribe.SourceProbe, p.subject(), scribe.ActionStart).Debugf("prepared", probeCreateStart, "[%d] metrics", len(p.metrics()))
	}
	scribe.Log(scribe.SourceProbe, scribe.SubjectHost(config.Load(configPath).Host()), scribe.ActionStart).Debugf("prepared", createStart, "[%d] probes", len(probeMap))
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
					scribe.Log(scribe.SourceProbe, p.subject(), scribe.ActionSample).Errorf("faulting", probeStart, "[%v] pulse with [%v]", isPulse, err)
				}
				scribe.Log(scribe.SourceProbe, p.subject(), scribe.ActionSample).Debugf("reported", probeStart, "[%v] pulse, metrics [%3d]", isPulse, len(p.metrics()))
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
			scribe.Log(scribe.SourceProbe, scribe.SubjectHost(config.Load(execConfigPath).Host()), scribe.ActionSample).Debugf("reported", tickStart, "[%3d] probes, pulse [%v]", len(execProbes), isPulse)
		}
	}
}

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
			if probesByMetricID[id] != nil && probesByMetricID[id] != probe {
				thisType := reflect.TypeOf(probe)
				if thisType.Kind() == reflect.Pointer {
					thisType = thisType.Elem()
				}
				thatType := reflect.TypeOf(probesByMetricID[id])
				if thatType.Kind() == reflect.Pointer {
					thatType = thatType.Elem()
				}
				panic(fmt.Sprintf("multiple execProbes [%s,%s] registering metric ID [%d]", thisType.Name(), thatType.Name(), id))
			}
			probesByMetricID[id] = probe
		}
	}
}

func verifyProbes() {
	for _, id := range metric.GetIDs() {
		if probesByMetricID[id] == nil {
			panic(fmt.Sprintf("no probe registered for metric ID [%d]", id))
		}
	}
}

type derivation struct {
	action scribe.Action
	detail string
	args   []any
	inert  bool
}

func derivedf(action scribe.Action, detail string, args ...any) derivation {
	return derivation{action: action, detail: detail, args: args}
}

func derivedInertf(action scribe.Action, detail string, args ...any) derivation {
	return derivation{action: action, detail: detail, args: args, inert: true}
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
	tickFunc    func()
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
		tickFunc: func() {
			statsField.Tick()
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

type metricFaultKey struct {
	metricID    metric.ID
	serviceName string
}

type metricFault struct {
	message string
	since   time.Time
	logged  time.Time
	polls   int
	warming bool
}

type metricStatus uint8

const (
	metricStatusUnknown metricStatus = iota
	metricStatusRed
	metricStatusAmber
	metricStatusGreen
)

func (s metricStatus) String() string {
	switch s {
	case metricStatusGreen:
		return "green"
	case metricStatusAmber:
		return "amber"
	case metricStatusRed:
		return "red"
	default:
		return "unknown"
	}
}

func metricStatusOf(failed bool, pulseOK bool, trendOK *bool) metricStatus {
	if failed {
		return metricStatusUnknown
	}
	if !pulseOK {
		return metricStatusRed
	}
	if trendOK != nil && *trendOK {
		return metricStatusGreen
	}
	return metricStatusAmber
}

func metricStatusPrevious(seen bool, previous metricStatus) string {
	if !seen {
		return "none"
	}
	return previous.String()
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

func (c *metricCensus) count(status metricStatus, task cacheMetricTask) {
	c.total++
	c.service = task.serviceName
	switch status {
	case metricStatusGreen:
		c.green++
	case metricStatusAmber:
		c.amber++
		c.faulted = append(c.faulted, metric.GetIDName(task.metricID)+"="+status.String())
	case metricStatusRed:
		c.red++
		c.faulted = append(c.faulted, metric.GetIDName(task.metricID)+"="+status.String())
	default:
		c.unknown++
		c.faulted = append(c.faulted, metric.GetIDName(task.metricID)+"="+status.String())
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

func runCacheMetricTasks(p probe, isPulse bool, gates gateSet, tasks []cacheMetricTask) {
	tasksStart := time.Now()
	census := metricCensus{}
	for _, task := range tasks {
		cache := p.records()
		if cache == nil {
			scribe.Log(scribe.SourceProbe, scribe.SubjectMetric(task.metricID), scribe.ActionSample).Errorf("unusable", tasksStart, "[missing] the required cache")
			continue
		}
		if !p.hasMetric(task.metricID) {
			continue
		}
		census.count(runCacheMetricTask(p, isPulse, gates, task), task)
	}
	if !isPulse || census.total == 0 {
		return
	}
	scribe.Log(scribe.SourceProbe, p.subject(), scribe.ActionCensus).Debugf("reported", tasksStart, "[%3d] metrics%s, green [%3d] amber [%3d] red [%3d] unknown [%3d]%s",
		census.total, census.subject(), census.green, census.amber, census.red, census.unknown, census.faults())
}

func runCacheMetricTask(p probe, isPulse bool, gates gateSet, task cacheMetricTask) metricStatus {
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
		scribe.Log(scribe.SourceProbe, scribe.SubjectMetric(task.metricID), scribe.ActionSample).Errorf("unusable", taskStart, "[%s] required fields missing", strings.Join(missing, ","))
		return metricStatusUnknown
	}
	sample, derivation, err := task.sampleFunc()
	warming := errors.Is(err, errProbeWarmingUp)
	seeding := warming && metric.GetIDWarming(task.metricID)
	errored := err != nil && !warming
	trackMetricFault(task, err, errored)
	if err == nil {
		task.statsFunc(sample)
	} else if task.tickFunc != nil {
		task.tickFunc()
	}
	if !isPulse {
		return metricStatusUnknown
	}
	reportMetricDerivation(task, taskStart, derivation, err)
	hostName := config.Load(execConfigPath).Host()
	if hostName == "" {
		scribe.Log(scribe.SourceProbe, scribe.SubjectMetric(task.metricID), scribe.ActionSample).Errorf("unusable", taskStart, "[missing] the host name")
		return metricStatusUnknown
	}
	guid := metric.NewServiceRecordGUID(task.metricID, hostName, task.serviceName)
	pulse := task.pulseFunc()
	if seeding {
		reportMetricStatus(task, taskStart, metricStatusUnknown, pulse, false, nil, nil, err)
		return metricStatusUnknown
	}
	if pulse == nil {
		reportMetricStatus(task, taskStart, metricStatusUnknown, nil, false, nil, nil, err)
		return metricStatusUnknown
	}
	unit := metric.GetIDUnit(task.metricID)
	pulseResult := evaluateRule(metric.GetIDPulseRule(task.metricID), derivation.inert, unit, pulse, siblingResolver(p, hostName, false), gates)
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
		trendResult = evaluateRule(trendRule, derivation.inert, unit, trend, siblingResolver(p, hostName, true), gates)
		trended := trendResult.OK && !errored
		trendOK = &trended
		value, valueErr = metric.NewDataValue(pulseOK, pulse, trended, trend)
	}
	reportMetricRule(task.metricID, taskStart, pulseOK, pulseResult.Detail, trendOK, trendResult.Detail)
	if valueErr != nil {
		scribe.Log(scribe.SourceProbe, scribe.SubjectMetric(task.metricID), scribe.ActionCompute).Errorf("faulting", taskStart, "[builder] value failed with [%v]", valueErr)
		return metricStatusUnknown
	}
	value.Failed = errored && !derivation.inert
	record := metric.NewRecord(*value)
	p.records().Store(guid, &record)
	status := metricStatusOf(value.Failed, pulseOK, trendOK)
	reportMetricStatus(task, taskStart, status, pulse, pulseOK, trend, trendOK, err)
	return status
}

func trackMetricFault(task cacheMetricTask, err error, errored bool) {
	key := metricFaultKey{metricID: task.metricID, serviceName: task.serviceName}
	message := ""
	if err != nil {
		message = err.Error()
	}
	metricFaultsMu.Lock()
	tracked, faulting := metricFaults[key]
	switch {
	case errored && (!faulting || tracked.message != message):
		tracked = &metricFault{message: message, since: config.NowIncludingSuspend(), logged: time.Now(), polls: 1, warming: errors.Is(err, errProbeWarmingUp)}
		metricFaults[key] = tracked
	case errored:
		tracked.polls++
	case faulting:
		delete(metricFaults, key)
	}
	fault := metricFault{}
	repeat := false
	if tracked != nil {
		if errored && tracked.polls != 1 && time.Since(tracked.logged) >= metricFaultRepeat {
			tracked.logged = time.Now()
			repeat = true
		}
		fault = *tracked
	}
	metricFaultsMu.Unlock()
	logger := scribe.Log(scribe.SourceProbe, scribe.SubjectMetric(task.metricID), scribe.ActionSample)
	switch {
	case errored && errors.Is(err, errUnimplemented):
		logger.Debugf("faulting", fault.since, "%swith [%v]", metricScope(task), err)
	case errored && fault.polls == 1 && fault.warming:
		logger.Debugf("faulting", fault.since, "%swith [%v]", metricScope(task), err)
	case errored && fault.polls == 1 && errors.Is(err, errEnvironment):
		logger.Warnf("faulting", fault.since, "%swith [%v]", metricScope(task), err)
	case errored && fault.polls == 1:
		logger.Errorf("faulting", fault.since, "%swith [%v]", metricScope(task), err)
	case errored && repeat:
		logger.Debugf("faulting", fault.since, "%sfor [%d] polls with [%v]", metricScope(task), fault.polls, err)
	case !errored && faulting && fault.warming:
		logger.Debugf("restored", fault.since, "%safter [%d] failed polls with [%s]", metricScope(task), fault.polls, fault.message)
	case !errored && faulting:
		logger.Infof("restored", fault.since, "%safter [%d] failed polls with [%s]", metricScope(task), fault.polls, fault.message)
	}
}

func reportMetricDerivation(task cacheMetricTask, taskStart time.Time, d derivation, err error) {
	if d.empty() {
		if err == nil {
			scribe.Log(scribe.SourceProbe, scribe.SubjectMetric(task.metricID), scribe.ActionCompute).Errorf("unstated", taskStart,
				"%spublished a value stating no derivation", metricScope(task))
		}
		return
	}
	rendered := d.detail
	if len(d.args) > 0 {
		rendered = fmt.Sprintf(d.detail, d.args...)
	}
	verb, detail, _ := strings.Cut(strings.TrimLeft(rendered, " "), " ")
	detail = strings.TrimLeft(detail, " ")
	scribe.Log(scribe.SourceProbe, scribe.SubjectMetric(task.metricID), d.action).Debugf(verb, taskStart, "%s", detail)
}

func reportMetricStatus(task cacheMetricTask, taskStart time.Time, status metricStatus, pulse any, pulseOK bool, trend any, trendOK *bool, err error) {
	key := metricFaultKey{metricID: task.metricID, serviceName: task.serviceName}
	metricStatusesMu.Lock()
	previous, seen := metricStatuses[key]
	metricStatuses[key] = status
	metricStatusesMu.Unlock()
	if seen && previous == status {
		return
	}
	scribe.Log(scribe.SourceProbe, scribe.SubjectMetric(task.metricID), scribe.ActionCompute).Debugf("observed", taskStart, "%sstatus [%s] was [%s] pulse [%v] ok [%v] trend [%v] ok [%v] error [%v]",
		metricScope(task), status, metricStatusPrevious(seen, previous), metricValue(pulse), pulseOK, metricValue(trend), metricFlag(trendOK), metricError(err))
}

func reportMetricRule(metricID metric.ID, taskStart time.Time, pulseOK bool, pulseText string, trendOK *bool, trendText string) {
	logger := scribe.Log(scribe.SourceProbe, scribe.SubjectMetric(metricID), scribe.ActionCompute)
	if trendOK == nil {
		reportPulsingf(logger, "computed", taskStart, "ok pulse [%v] %s", pulseOK, pulseText)
		return
	}
	reportPulsingf(logger, "computed", taskStart, "ok pulse [%v] %s, ok trend [%v] %s", pulseOK, pulseText, *trendOK, trendText)
}

func reportPulsingf(logger scribe.Logger, verb string, started time.Time, detail string, args ...any) {
	if !execPulsing.Load() {
		return
	}
	logger.Debugf(verb, started, detail, args...)
}

func evaluateRule(rule metric.Rule, inert bool, unit string, value any, siblings metric.ValueResolver, gates gateSet) metric.RuleResult {
	if inert {
		return metric.RuleResult{OK: true, Detail: "nothing to measure on this host"}
	}
	number, numeric := numericValue(value)
	return rule.Evaluate(unit, number, numeric, siblings, gates.resolve)
}

func percentValue(value float64) int8 {
	if value < 0 {
		return 0
	}
	if value > 100 {
		return 100
	}
	return int8(value + 0.5)
}

func numericValue(value any) (float64, bool) {
	switch typed := value.(type) {
	case int8:
		return float64(typed), true
	case float64:
		return typed, true
	case bool:
		if typed {
			return 1, true
		}
		return 0, true
	default:
		return 0, false
	}
}

func metricScope(task cacheMetricTask) string {
	if task.serviceName == metric.ServiceNameUnset {
		return "[host] "
	}
	return fmt.Sprintf("[%s] ", task.serviceName)
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

const (
	metricFaultRepeat = time.Minute

	bytesPerMiB = 1 << 20
)

var (
	errUnimplemented  = errors.New("metric not implemented")
	errProbeWarmingUp = errors.New("probe is still warming up")
	errMountContent   = errors.New("mount answered but is not healthy")
	errEnvironment    = errors.New("environment cannot supply this reading")

	execConfigPath string
	execPeriods    config.Periods
	execPulsing    atomic.Bool
	execPulses     atomic.Int64
	execProbes     map[probe][metric.MetricMax]bool

	metricFaults   = map[metricFaultKey]*metricFault{}
	metricFaultsMu sync.Mutex

	metricStatuses   = map[metricFaultKey]metricStatus{}
	metricStatusesMu sync.Mutex

	probesByMetricID [metric.MetricMax]probe
)
