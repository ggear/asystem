package engine

import (
	"bytes"
	"context"
	"errors"
	"fmt"
	"network/internal/config"
	"network/internal/plugin"
	"network/internal/remote"
	"network/internal/scribe"
	"reflect"
	"sync"
	"time"
)

type Engine struct {
	DaemonLoop         bool
	PublishData        bool
	Plugins            []plugin.Plugin
	PollPeriod         time.Duration
	AggregatePeriod    time.Duration
	sampleMu           sync.Mutex
	sampleWindow       int
	sampleWindows      map[string]int
	sampleBuffers      map[string][]plugin.Sample
	pollStrides        map[string]int
	pollLocks          map[string]*sync.Mutex
	polls              int
	refreshMu          sync.Mutex
	refreshGap         time.Duration
	refreshing         map[string]bool
	refreshed          map[string]time.Time
	lineProtocolMu     sync.Mutex
	lineProtocolBuffer bytes.Buffer
	broker             *remote.Broker
	database           *remote.Database
}

func Create(e *Engine) error {
	if e == nil {
		return errors.New("engine is nil")
	}
	if len(e.Plugins) == 0 {
		return errors.New("no plugins selected")
	}
	if e.PollPeriod <= 0 {
		return fmt.Errorf("invalid poll period [%s] must be > 0", e.PollPeriod)
	}
	if e.AggregatePeriod <= 0 {
		return fmt.Errorf("invalid aggregate period [%s] must be > 0", e.AggregatePeriod)
	}
	if e.AggregatePeriod%e.PollPeriod != 0 {
		return fmt.Errorf("invalid aggregate period [%s] must be a whole multiple of poll period [%s]", e.AggregatePeriod, e.PollPeriod)
	}
	e.sampleWindow = int(e.AggregatePeriod / e.PollPeriod)
	e.sampleWindows = map[string]int{}
	e.sampleBuffers = map[string][]plugin.Sample{}
	e.pollStrides = map[string]int{}
	e.pollLocks = map[string]*sync.Mutex{}
	e.refreshGap = refreshGap
	e.refreshing = map[string]bool{}
	e.refreshed = map[string]time.Time{}
	pluginNames := make(map[string]struct{}, len(e.Plugins))
	for _, p := range e.Plugins {
		if p == nil {
			return errors.New("plugin is nil")
		}
		value := reflect.ValueOf(p)
		switch value.Kind() {
		case reflect.Chan, reflect.Func, reflect.Interface, reflect.Map, reflect.Pointer, reflect.Slice:
			if value.IsNil() {
				return errors.New("plugin is nil")
			}
		default:
		}
		name := p.Name()
		if _, exists := pluginNames[name]; exists {
			return fmt.Errorf("duplicate plugin [%s]", name)
		}
		pluginNames[name] = struct{}{}
		e.sampleBuffers[name] = nil
		e.pollLocks[name] = &sync.Mutex{}
		if p.Mode() == plugin.ModeSnapshot {
			e.sampleWindows[name] = 1
		} else if paced, ok := p.(plugin.Paced); ok && paced.PollPeriod() > e.PollPeriod {
			period := paced.PollPeriod()
			if period%e.PollPeriod != 0 || e.AggregatePeriod%period != 0 {
				return fmt.Errorf("invalid poll period [%s] of plugin [%s] must be a whole multiple of poll period [%s] dividing aggregate period [%s]", period, name, e.PollPeriod, e.AggregatePeriod)
			}
			e.pollStrides[name] = int(period / e.PollPeriod)
			e.sampleWindows[name] = int(e.AggregatePeriod / period)
		}
	}
	return nil
}

func (e *Engine) Run(ctx context.Context) error {
	if err := ctx.Err(); err != nil {
		return err
	}
	if e.DaemonLoop {
		scribe.LogInfo(scribe.Global, "starting loop poll every [%s], aggregated over [%s] across [%d] plugins", e.PollPeriod, e.AggregatePeriod, len(e.Plugins))
	} else {
		scribe.LogInfo(scribe.Global, "running single check across [%d] plugins", len(e.Plugins))
	}
	if e.PublishData {
		loaded := config.Load()
		onCommand := func(name string, payload []byte) { go e.handleCommand(ctx, name, payload) }
		if broker, err := remote.NewBroker(loaded.Broker(), loaded.BrokerToken(), onCommand); err != nil {
			scribe.LogError(scribe.Global, "failed to connect to broker [%v]", err)
		} else {
			e.broker = broker
		}
		if loaded.Database() == "" {
			scribe.LogWarn(scribe.Global, "database address is empty")
		} else if database, err := remote.NewDatabase(loaded.Database(), loaded.DatabaseToken(), loaded.DatabaseName()); err != nil {
			scribe.LogError(scribe.Global, "failed to connect to database [%v]", err)
		} else {
			e.database = database
		}
	}
	defer e.shutdown()
	e.PollSamples(ctx)
	for _, aggregate := range e.AggregateSamples(ctx, e.Plugins) {
		e.publishAggregate(ctx, aggregate)
	}
	if !e.DaemonLoop {
		return nil
	}
	pollTicker := time.NewTicker(e.PollPeriod)
	defer pollTicker.Stop()
	pollsPerAggregate := int(e.AggregatePeriod / e.PollPeriod)
	polls := 0
	for {
		select {
		case <-ctx.Done():
			return ctx.Err()
		case <-pollTicker.C:
			e.PollSamples(ctx)
			polls++
			if polls == pollsPerAggregate {
				polls = 0
				e.publishStatus()
				for _, aggregate := range e.AggregateSamples(ctx, e.Plugins) {
					e.publishAggregate(ctx, aggregate)
				}
				continue
			}
			for _, aggregate := range e.AggregateChanges() {
				e.publishAggregate(ctx, aggregate)
			}
		}
	}
}

func (e *Engine) PollSamples(ctx context.Context) {
	e.sampleMu.Lock()
	tick := e.polls
	e.polls++
	e.sampleMu.Unlock()
	var group sync.WaitGroup
	for _, p := range e.Plugins {
		tracker := p.State()
		down := tracker != nil && tracker.Get() == plugin.StateOff
		if p.Mode() == plugin.ModeSnapshot && !down {
			continue
		}
		if stride, paced := e.pollStrides[p.Name()]; paced && !down && tick%stride != 0 {
			continue
		}
		group.Add(1)
		go func(p plugin.Plugin) {
			defer group.Done()
			sample := e.safePoll(ctx, p)
			e.sampleMu.Lock()
			e.addSample(p.Name(), sample)
			e.sampleMu.Unlock()
			scribe.LogDebug(p.Name(), "polled [%s]", p.Name())
		}(p)
	}
	group.Wait()
}

func (e *Engine) AggregateSamples(ctx context.Context, plugins []plugin.Plugin) []plugin.Aggregate {
	scribe.LogDebug(scribe.Global, "aggregating [%d] plugins", len(plugins))
	aggregates := make([]plugin.Aggregate, 0, len(plugins))
	for _, p := range plugins {
		start := time.Now()
		var samples []plugin.Sample
		if p.Mode() == plugin.ModeWindowed {
			e.sampleMu.Lock()
			samples = e.copySamples(p.Name())
			e.sampleMu.Unlock()
			if len(samples) == 0 {
				sample := e.safePoll(ctx, p)
				e.sampleMu.Lock()
				e.addSample(p.Name(), sample)
				samples = e.copySamples(p.Name())
				e.sampleMu.Unlock()
			}
		} else {
			sample := e.safePoll(ctx, p)
			samples = []plugin.Sample{sample}
		}
		aggregate := e.safeAggregate(p, samples)
		took := time.Since(start)
		state := plugin.StateOff
		if aggregate.OK {
			state = plugin.StateOn
		}
		if tracker := p.State(); tracker != nil {
			tracker.Set(state)
		}
		aggregates = append(aggregates, aggregate)
		scribe.LogDiagnosis(p.Name(), string(aggregate.Status), aggregate.Score, took, aggregate.Reason)
	}
	return aggregates
}

func (e *Engine) AggregateChanges() []plugin.Aggregate {
	var aggregates []plugin.Aggregate
	for _, p := range e.Plugins {
		tracker := p.State()
		if tracker == nil || (p.Mode() == plugin.ModeSnapshot && tracker.Get() == plugin.StateOn) {
			continue
		}
		start := time.Now()
		e.sampleMu.Lock()
		samples := e.copySamples(p.Name())
		e.sampleMu.Unlock()
		if len(samples) == 0 {
			continue
		}
		aggregate := e.safeAggregate(p, samples)
		state := plugin.StateOff
		if aggregate.OK {
			state = plugin.StateOn
		}
		if tracker.Get() == state {
			continue
		}
		tracker.Set(state)
		aggregates = append(aggregates, aggregate)
		scribe.LogDiagnosis(p.Name(), string(aggregate.Status), aggregate.Score, time.Since(start), aggregate.Reason)
	}
	return aggregates
}

func (e *Engine) safePoll(ctx context.Context, p plugin.Plugin) (sample plugin.Sample) {
	pollLock := e.pollLocks[p.Name()]
	pollLock.Lock()
	defer pollLock.Unlock()
	defer func() {
		if recovered := recover(); recovered != nil {
			scribe.LogError(p.Name(), "panicked during poll [%v]", recovered)
			sample = plugin.Sample{}
		}
		if sample.Timestamp.IsZero() {
			sample.Timestamp = time.Now()
		}
	}()
	polled, err := p.Poll(ctx)
	if err != nil {
		scribe.LogWarn(p.Name(), "poll failed [%v]", err)
	}
	return polled
}

func (e *Engine) safeAggregate(p plugin.Plugin, samples []plugin.Sample) (aggregate plugin.Aggregate) {
	defer func() {
		if recovered := recover(); recovered != nil {
			scribe.LogError(p.Name(), "panicked during aggregate [%v]", recovered)
			aggregate = plugin.Diagnose(plugin.StatusDead, 0, "PLUGIN_PANIC: plugin panicked during aggregate")
		}
		aggregate.Plugin = p.Name()
		if aggregate.Timestamp.IsZero() {
			aggregate.Timestamp = time.Now()
		}
		aggregate.Points = append(aggregate.Points, plugin.DiagnosisPoint(aggregate.Plugin, aggregate.OK, aggregate.Score))
	}()
	diagnosed, err := p.Aggregate(samples)
	if err != nil {
		scribe.LogWarn(p.Name(), "aggregate failed [%v]", err)
		return plugin.Diagnose(plugin.StatusDead, 0, fmt.Sprintf("PLUGIN_ERROR: %s", err))
	}
	return diagnosed
}

func (e *Engine) publishStatus() {
	if e.broker == nil {
		return
	}
	if err := e.broker.PublishStatus(); err != nil {
		scribe.LogWarn(scribe.Global, "publishing online status to broker failed [%v]", err)
	}
}

func (e *Engine) publishBroker(aggregate plugin.Aggregate) {
	if e.broker == nil {
		return
	}
	payload, err := aggregate.MarshalJSON()
	if err != nil {
		scribe.LogWarn(aggregate.Plugin, "marshal for broker failed [%v]", err)
		return
	}
	if err := e.broker.Publish(remote.DataTopic(aggregate.Plugin), payload); err != nil {
		scribe.LogWarn(aggregate.Plugin, "publishing to broker failed [%v]", err)
	}
}

func (e *Engine) publishAggregate(ctx context.Context, aggregate plugin.Aggregate) {
	e.publishBroker(aggregate)
	if e.database != nil {
		e.lineProtocolMu.Lock()
		e.lineProtocolBuffer.Reset()
		aggregate.AppendLineProtocol(&e.lineProtocolBuffer, time.Now().UnixNano())
		data := append([]byte(nil), e.lineProtocolBuffer.Bytes()...)
		e.lineProtocolMu.Unlock()
		if len(data) > 0 {
			e.database.Write(ctx, data)
		}
	}
}

func (e *Engine) handleCommand(ctx context.Context, name string, payload []byte) {
	if _, ok := plugin.ParseState(string(payload)); !ok {
		scribe.LogWarn(name, "command ignored because payload [%s] is unparseable", string(payload))
		return
	}
	p, ok := e.findPlugin(name)
	if !ok {
		scribe.LogWarn(name, "command ignored because plugin is unknown")
		return
	}
	e.refreshMu.Lock()
	if e.refreshing[name] || time.Since(e.refreshed[name]) < e.refreshGap {
		e.refreshMu.Unlock()
		scribe.LogDebug(name, "command ignored because a refresh is running or recent")
		return
	}
	e.refreshing[name] = true
	e.refreshMu.Unlock()
	defer func() {
		e.refreshMu.Lock()
		delete(e.refreshing, name)
		e.refreshed[name] = time.Now()
		e.refreshMu.Unlock()
	}()
	start := time.Now()
	sample := e.safePoll(ctx, p)
	e.sampleMu.Lock()
	e.addSample(name, sample)
	samples := e.copySamples(name)
	e.sampleMu.Unlock()
	aggregate := e.safeAggregate(p, samples)
	if tracker := p.State(); tracker != nil {
		state := plugin.StateOff
		if aggregate.OK {
			state = plugin.StateOn
		}
		tracker.Set(state)
	}
	e.publishBroker(aggregate)
	scribe.LogDiagnosis(name, string(aggregate.Status), aggregate.Score, time.Since(start), aggregate.Reason)
}

func (e *Engine) shutdown() {
	if e.broker != nil {
		if err := e.broker.Close(); err != nil {
			scribe.LogWarn(scribe.Global, "broker disconnect failed [%v]", err)
		}
	}
	if e.database != nil {
		if err := e.database.Close(); err != nil {
			scribe.LogWarn(scribe.Global, "database disconnect failed [%v]", err)
		}
	}
}

func (e *Engine) findPlugin(name string) (plugin.Plugin, bool) {
	for _, p := range e.Plugins {
		if p.Name() == name {
			return p, true
		}
	}
	return nil, false
}

func (e *Engine) addSample(name string, sample plugin.Sample) {
	window := e.sampleWindow
	if paced, ok := e.sampleWindows[name]; ok {
		window = paced
	}
	buffer := append(e.sampleBuffers[name], sample)
	if len(buffer) > window {
		buffer = buffer[len(buffer)-window:]
	}
	e.sampleBuffers[name] = buffer
}

func (e *Engine) copySamples(name string) []plugin.Sample {
	buffer := e.sampleBuffers[name]
	if len(buffer) == 0 {
		return nil
	}
	return append([]plugin.Sample(nil), buffer...)
}

const refreshGap = 5 * time.Second
