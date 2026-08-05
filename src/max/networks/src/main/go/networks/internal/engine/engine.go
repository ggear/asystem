package engine

import (
	"bytes"
	"context"
	"errors"
	"fmt"
	"networks/internal/config"
	"networks/internal/plugin"
	"networks/internal/remote"
	"networks/internal/scribe"
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
	sampleBuffers      map[string][]plugin.Sample
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
	e.sampleBuffers = map[string][]plugin.Sample{}
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
		if p.Mode() == plugin.ModeWindowed {
			e.sampleBuffers[name] = nil
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
		cfg := config.Load()
		onCommand := func(name string, payload []byte) { e.handleCommand(ctx, name, payload) }
		if broker, err := remote.NewBroker(cfg.Broker(), cfg.BrokerToken(), onCommand); err != nil {
			scribe.LogError(scribe.Global, "failed to connect to broker [%v]", err)
		} else {
			e.broker = broker
		}
		if cfg.Database() == "" {
			scribe.LogWarn(scribe.Global, "database address is empty")
		} else if database, err := remote.NewDatabase(cfg.Database(), cfg.DatabaseToken(), cfg.DatabaseName()); err != nil {
			scribe.LogError(scribe.Global, "failed to connect to database [%v]", err)
		} else {
			e.database = database
		}
	}
	defer e.shutdown()
	e.PollSamples(ctx)
	for _, v := range e.AggregateSamples(ctx, e.Plugins) {
		e.publishAggregate(ctx, v)
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
				for _, v := range e.AggregateSamples(ctx, e.Plugins) {
					e.publishAggregate(ctx, v)
				}
			}
		}
	}
}

func (e *Engine) PollSamples(ctx context.Context) {
	var wg sync.WaitGroup
	for _, p := range e.Plugins {
		if p.Mode() != plugin.ModeWindowed {
			continue
		}
		wg.Add(1)
		go func(p plugin.Plugin) {
			defer wg.Done()
			m := e.safePoll(ctx, p)
			e.sampleMu.Lock()
			e.addSample(p.Name(), m)
			e.sampleMu.Unlock()
			scribe.LogDebug(p.Name(), "polled [%s]", p.Name())
		}(p)
	}
	wg.Wait()
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
				m := e.safePoll(ctx, p)
				e.sampleMu.Lock()
				e.addSample(p.Name(), m)
				samples = e.copySamples(p.Name())
				e.sampleMu.Unlock()
			}
		} else {
			m := e.safePoll(ctx, p)
			samples = []plugin.Sample{m}
		}
		v := e.safeAggregate(p, samples)
		took := time.Since(start)
		state := plugin.StateOff
		if v.OK {
			state = plugin.StateOn
		}
		if tracker := p.State(); tracker != nil {
			tracker.Set(state)
		}
		aggregates = append(aggregates, v)
		scribe.LogDiagnosis(p.Name(), string(v.Status), v.Score, took, v.Reason)
	}
	return aggregates
}

func (e *Engine) safePoll(ctx context.Context, p plugin.Plugin) (m plugin.Sample) {
	defer func() {
		if r := recover(); r != nil {
			scribe.LogError(p.Name(), "panicked during poll [%v]", r)
			m = plugin.Sample{}
		}
		m.Plugin = p.Name()
		if m.Timestamp.IsZero() {
			m.Timestamp = time.Now()
		}
	}()
	sample, err := p.Poll(ctx)
	if err != nil {
		scribe.LogWarn(p.Name(), "poll failed [%v]", err)
	}
	return sample
}

func (e *Engine) safeAggregate(p plugin.Plugin, samples []plugin.Sample) (v plugin.Aggregate) {
	defer func() {
		if r := recover(); r != nil {
			scribe.LogError(p.Name(), "panicked during aggregate [%v]", r)
			v = plugin.Diagnose(plugin.StatusDead, 0, "PLUGIN_PANIC: plugin panicked during aggregate")
		}
		v.Plugin = p.Name()
		v.WindowSeconds = int(e.AggregatePeriod / time.Second)
		if v.Timestamp.IsZero() {
			v.Timestamp = time.Now()
		}
	}()
	aggregate, err := p.Aggregate(samples)
	if err != nil {
		scribe.LogWarn(p.Name(), "aggregate failed [%v]", err)
		return plugin.Diagnose(plugin.StatusDead, 0, fmt.Sprintf("PLUGIN_ERROR: [%s]", err))
	}
	return aggregate
}
func (e *Engine) publishAggregate(ctx context.Context, m plugin.Aggregate) {
	if e.broker != nil {
		if payload, err := m.MarshalJSON(); err != nil {
			scribe.LogWarn(m.Plugin, "marshal for broker failed [%v]", err)
		} else {
			e.broker.Publish(remote.DataTopic(m.Plugin), payload)
		}
	}
	if e.database != nil {
		e.lineProtocolMu.Lock()
		e.lineProtocolBuffer.Reset()
		m.AppendLineProtocol(&e.lineProtocolBuffer, time.Now().UnixNano())
		data := append([]byte(nil), e.lineProtocolBuffer.Bytes()...)
		e.lineProtocolMu.Unlock()
		if len(data) > 0 {
			e.database.Write(ctx, data)
		}
	}
}

func (e *Engine) handleCommand(ctx context.Context, name string, payload []byte) {
	state, ok := plugin.ParseState(string(payload))
	if !ok {
		scribe.LogWarn(name, "command ignored because payload [%s] is unparseable", string(payload))
		return
	}
	e.runCommand(ctx, name, state)
}

func (e *Engine) runCommand(ctx context.Context, name string, state plugin.State) {
	p, ok := e.findPlugin(name)
	if !ok {
		scribe.LogWarn(name, "command ignored because plugin is unknown")
		return
	}
	if err := p.Command(ctx, state); err != nil {
		scribe.LogWarn(name, "command to state [%s] failed [%v]", state.String(), err)
		return
	}
	scribe.LogInfo(name, "command received to set state to [%s]", state.String())
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

func (e *Engine) addSample(name string, m plugin.Sample) {
	buffer := append(e.sampleBuffers[name], m)
	if len(buffer) > e.sampleWindow {
		buffer = buffer[len(buffer)-e.sampleWindow:]
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
