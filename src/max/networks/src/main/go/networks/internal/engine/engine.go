package engine

import (
	"bytes"
	"context"
	"errors"
	"fmt"
	"networks/internal/plugin"
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
	sampleBuffers      map[string]*sampleBuffer
	broker             *brokerClient
	database           *databaseClient
	lineProtocolMu     sync.Mutex
	lineProtocolBuffer bytes.Buffer
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
	sampleBufferCap := int(e.AggregatePeriod / e.PollPeriod)
	e.sampleBuffers = map[string]*sampleBuffer{}
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
		}
		name := p.Name()
		if _, exists := pluginNames[name]; exists {
			return fmt.Errorf("duplicate plugin [%s]", name)
		}
		pluginNames[name] = struct{}{}
		if p.Mode() == plugin.ModeWindowed {
			e.sampleBuffers[name] = newSampleBuffer(sampleBufferCap)
		}
	}
	return nil
}

func (e *Engine) Run(ctx context.Context) error {
	if err := ctx.Err(); err != nil {
		return err
	}
	if e.DaemonLoop {
		scribe.Infof(scribe.Global, "starting loop poll every [%s], aggregated over [%s] across [%d] plugins", e.PollPeriod, e.AggregatePeriod, len(e.Plugins))
	} else {
		scribe.Infof(scribe.Global, "running single check across [%d] plugins", len(e.Plugins))
	}
	if e.PublishData {
		if broker, err := newBrokerClient(ctx, e.runCommand); err != nil {
			scribe.Errorf(scribe.Global, "failed to connect to broker [%v]", err)
		} else {
			e.broker = broker
		}
		if database, err := newDatabaseClient(); err != nil {
			scribe.Errorf(scribe.Global, "failed to connect to database [%v]", err)
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
			e.sampleBuffers[p.Name()].Add(m)
			e.sampleMu.Unlock()
			scribe.Debugf(p.Name(), "polled [%d] points", len(m.Points))
		}(p)
	}
	wg.Wait()
}

func (e *Engine) AggregateSamples(ctx context.Context, plugins []plugin.Plugin) []plugin.Aggregate {
	scribe.Debugf(scribe.Global, "aggregating [%d] plugins", len(plugins))
	aggregates := make([]plugin.Aggregate, 0, len(plugins))
	for _, p := range plugins {
		start := time.Now()
		var samples []plugin.Sample
		if p.Mode() == plugin.ModeWindowed {
			buffer := e.sampleBuffers[p.Name()]
			e.sampleMu.Lock()
			samples = buffer.Samples()
			e.sampleMu.Unlock()
			if len(samples) == 0 {
				m := e.safePoll(ctx, p)
				e.sampleMu.Lock()
				buffer.Add(m)
				samples = buffer.Samples()
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
		scribe.Diagnosis(p.Name(), string(v.Status), v.Score, took, v.Reason)
	}
	return aggregates
}

func (e *Engine) safePoll(ctx context.Context, p plugin.Plugin) (m plugin.Sample) {
	defer func() {
		if r := recover(); r != nil {
			scribe.Errorf(p.Name(), "panicked during poll [%v]", r)
			m = plugin.Sample{}
		}
		m.Plugin = p.Name()
		if m.Timestamp.IsZero() {
			m.Timestamp = time.Now()
		}
	}()
	sample, err := p.Poll(ctx)
	if err != nil {
		scribe.Warnf(p.Name(), "poll failed [%v]", err)
	}
	return sample
}

func (e *Engine) safeAggregate(p plugin.Plugin, samples []plugin.Sample) (v plugin.Aggregate) {
	defer func() {
		if r := recover(); r != nil {
			scribe.Errorf(p.Name(), "panicked during aggregate [%v]", r)
			v = plugin.Diagnose(plugin.StatusDead, 0, "PLUGIN_PANIC", "plugin panicked during aggregate")
		}
		v.Plugin = p.Name()
		v.WindowSize = int(e.AggregatePeriod / time.Second)
		v.SampleCount = len(samples)
		if v.Timestamp.IsZero() {
			v.Timestamp = time.Now()
		}
	}()
	aggregate, err := p.Aggregate(samples)
	if err != nil {
		scribe.Warnf(p.Name(), "aggregate failed [%v]", err)
		return plugin.Diagnose(plugin.StatusDead, 0, "PLUGIN_ERROR", err.Error())
	}
	return aggregate
}
func (e *Engine) publishAggregate(ctx context.Context, m plugin.Aggregate) {
	if e.broker != nil {
		e.broker.publishAggregate(m)
	}
	if e.database != nil {
		e.lineProtocolMu.Lock()
		e.lineProtocolBuffer.Reset()
		m.AppendLineProtocol(&e.lineProtocolBuffer, "network", time.Now().UnixNano())
		data := append([]byte(nil), e.lineProtocolBuffer.Bytes()...)
		e.lineProtocolMu.Unlock()
		if len(data) > 0 {
			e.database.write(ctx, data)
		}
	}
}

func (e *Engine) shutdown() {
	if e.broker != nil {
		e.broker.disconnect()
	}
	if e.database != nil {
		e.database.close()
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
