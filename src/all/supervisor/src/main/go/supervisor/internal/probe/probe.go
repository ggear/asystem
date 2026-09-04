package probe

import (
	"context"
	"errors"
	"fmt"
	"maps"
	"reflect"
	"slices"
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
	dormant() bool
	metrics() []metric.ID
	gates() []metric.GateID
	create(configPath string, cache *metric.RecordCache, mask [metric.MetricMax]bool, periods config.Periods) error
	poll(ctx context.Context, isPulse bool) error
	records() *metric.RecordCache
	hasMetric(metric.ID) bool
}

type cycledProbe interface {
	probe
	cycle(ctx context.Context, hour int, isHour bool)
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
	dormant := map[string]bool{}
	registerStart := time.Now()
	for _, id := range cache.IDs() {
		if id < 0 || id >= metric.MetricMax {
			continue
		}
		p := probesByMetricID[id]
		if p != nil && p.dormant() {
			dormant[probeNamed(p)] = true
			continue
		}
		if p == nil {
			scribe.Log(scribe.SourceProbe, scribe.SubjectMetric(id), scribe.ActionStart).Errorf("rejected", registerStart, "[none] probe registered")
			continue
		}
		mask := probeMap[p]
		mask[id] = true
		probeMap[p] = mask
	}
	for _, name := range slices.Sorted(maps.Keys(dormant)) {
		scribe.Log(scribe.SourceProbe, scribe.SubjectHost(config.Load(configPath).Host()), scribe.ActionStart).Infof("excluded", registerStart, "[%s] is dormant, so it never polls and its metrics stay unpublished", name)
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

func RunPoll(ctx context.Context, onPulse func(isHeartbeat bool)) error {
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
				if err := p.poll(ctx, isPulse); err != nil {
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

func RunCycle(ctx context.Context) {
	cycleStart := config.NowIncludingSuspend()
	firedHour := cycleStart.Hour()
	scribe.Log(scribe.SourceProbe, scribe.SubjectHost(config.Load(execConfigPath).Host()), scribe.ActionStart).Debugf("watching", cycleStart, "[%02d] hour seeded as already crossed, cycle ticks every [%s]", firedHour, cycleInterval)
	ticker := time.NewTicker(cycleInterval)
	defer ticker.Stop()
	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			tickStart := config.NowIncludingSuspend()
			hour := tickStart.Hour()
			isHour := hour != firedHour
			firedHour = hour
			offered := 0
			for p := range execProbes {
				if cycled, ok := p.(cycledProbe); ok {
					offered++
					go cycled.cycle(ctx, hour, isHour)
				}
			}
			if isHour {
				scribe.Log(scribe.SourceProbe, scribe.SubjectHost(config.Load(execConfigPath).Host()), scribe.ActionStart).Debugf("schedule", tickStart, "[%02d] hour crossed, offered to [%d] cycled probes", hour, offered)
			}
		}
	}
}

func init() {
	registerProbes(
		func() probe { return newServicesProbe() },
		func() probe { return newHostProbe() },
		func() probe { return newBackupProbe() },
	)
	verifyProbes()
}

func probeNamed(p probe) string {
	probeType := reflect.TypeOf(p)
	if probeType.Kind() == reflect.Pointer {
		probeType = probeType.Elem()
	}
	return probeType.Name()
}

func registerProbes(builders ...func() probe) []probe {
	created := make([]probe, 0, len(builders))
	for _, build := range builders {
		probe := build()
		if probe == nil {
			panic("nil probe registration")
		}
		for _, id := range probe.metrics() {
			if id >= 0 && id < metric.MetricMax {
				if probesByMetricID[id] != nil && probesByMetricID[id] != probe {
					panic(fmt.Sprintf("multiple execProbes [%s,%s] registering metric ID [%d]", probeNamed(probe), probeNamed(probesByMetricID[id]), id))
				}
				probesByMetricID[id] = probe
			}
		}
		created = append(created, probe)
	}
	return created
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

func runCacheMetricTasks(p probe, isPulse bool, gates gateSet, tasks []cacheMetricTask) {
	tasksStart := time.Now()
	census := metricCensus{}
	cache := p.records()
	for _, task := range tasks {
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
	scoped := ""
	if census.service != metric.ServiceNameUnset {
		scoped = fmt.Sprintf(" of service [%s]", census.service)
	}
	faults := ""
	if len(census.faulted) > 0 {
		faults = fmt.Sprintf(", not green [%s]", strings.Join(census.faulted, " "))
	}
	scribe.Log(scribe.SourceProbe, p.subject(), scribe.ActionCensus).Debugf("reported", tasksStart, "[%3d] metrics%s, green [%3d] amber [%3d] red [%3d] unknown [%3d]%s",
		census.total, scoped, census.green, census.amber, census.red, census.unknown, faults)
}

func runCacheMetricTask(p probe, isPulse bool, gates gateSet, task cacheMetricTask) metricStatus {
	taskStart := time.Now()
	if metric.GetIDPulseRule(task.metricID).IsZero() {
		scribe.Log(scribe.SourceProbe, scribe.SubjectMetric(task.metricID), scribe.ActionSample).Errorf("unusable", taskStart, "[pulseRule] not declared")
		return metricStatusUnknown
	}
	sample, derivation, err := task.sampleFunc()
	warming := errors.Is(err, errProbeWarmingUp)
	seeding := warming && metric.GetIDWarming(task.metricID)
	errored := err != nil && !warming
	trackMetricFault(task, err, errored)
	if err == nil {
		task.statsFunc(sample)
	} else {
		task.tickFunc()
	}
	if !isPulse {
		return metricStatusUnknown
	}
	if derivation.detail == "" {
		if err == nil {
			scribe.Log(scribe.SourceProbe, scribe.SubjectMetric(task.metricID), scribe.ActionCompute).Errorf("unstated", taskStart, "%spublished a value stating no derivation", metricScope(task))
		}
	} else {
		rendered := derivation.detail
		if len(derivation.args) > 0 {
			rendered = fmt.Sprintf(derivation.detail, derivation.args...)
		}
		verb, stated, _ := strings.Cut(strings.TrimLeft(rendered, " "), " ")
		scribe.Log(scribe.SourceProbe, scribe.SubjectMetric(task.metricID), derivation.action).Debugf(verb, taskStart, "%s", strings.TrimLeft(stated, " "))
	}
	hostName := config.Load(execConfigPath).Host()
	if hostName == "" {
		scribe.Log(scribe.SourceProbe, scribe.SubjectMetric(task.metricID), scribe.ActionSample).Errorf("unusable", taskStart, "[missing] the host name")
		return metricStatusUnknown
	}
	guid := metric.NewServiceRecordGUID(task.metricID, hostName, task.serviceName)
	pulse := task.pulseFunc()
	if seeding || pulse == nil {
		reportMetricStatus(task, taskStart, metricStatusUnknown, pulse, false, nil, nil, err)
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
	ruleLogger := scribe.Log(scribe.SourceProbe, scribe.SubjectMetric(task.metricID), scribe.ActionCompute)
	if trendOK == nil {
		reportPulsingf(ruleLogger, "computed", taskStart, "ok pulse [%v] %s", pulseOK, pulseResult.Detail)
	} else {
		reportPulsingf(ruleLogger, "computed", taskStart, "ok pulse [%v] %s, ok trend [%v] %s", pulseOK, pulseResult.Detail, *trendOK, trendResult.Detail)
	}
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

func reportMetricStatus(task cacheMetricTask, taskStart time.Time, status metricStatus, pulse any, pulseOK bool, trend any, trendOK *bool, err error) {
	key := metricFaultKey{metricID: task.metricID, serviceName: task.serviceName}
	metricStatusesMu.Lock()
	previous, seen := metricStatuses[key]
	metricStatuses[key] = status
	metricStatusesMu.Unlock()
	if seen && previous == status {
		return
	}
	was := "none"
	if seen {
		was = previous.String()
	}
	trended := any("none")
	if trendOK != nil {
		trended = *trendOK
	}
	metricValue := func(value any) any {
		if value == nil {
			return "none"
		}
		return value
	}
	scribe.Log(scribe.SourceProbe, scribe.SubjectMetric(task.metricID), scribe.ActionCompute).Debugf("observed", taskStart, "%sstatus [%s] was [%s] pulse [%v] ok [%v] trend [%v] ok [%v] error [%v]",
		metricScope(task), status, was, metricValue(pulse), pulseOK, metricValue(trend), trended, metricValue(err))
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
	number := float64(0)
	numeric := true
	switch typed := value.(type) {
	case int8:
		number = float64(typed)
	case float64:
		number = typed
	case bool:
		if typed {
			number = 1
		}
	default:
		numeric = false
	}
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

func metricScope(task cacheMetricTask) string {
	if task.serviceName == metric.ServiceNameUnset {
		return "[host] "
	}
	return fmt.Sprintf("[%s] ", task.serviceName)
}

const (
	metricFaultRepeat = time.Minute
	cycleInterval     = time.Minute

	bytesPerMiB = 1 << 20
)

var (
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
