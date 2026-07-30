package engine

import (
	"bytes"
	"context"
	"errors"
	"fmt"
	"log/slog"
	"networks/internal/plugin"
	"sync"
	"time"
)

const measurement = "network"

type Options struct {
	Plugins         []plugin.Plugin
	PollPeriod      time.Duration
	AggregatePeriod time.Duration
	PublishData     bool
}

type Engine struct {
	plugins         []plugin.Plugin
	pollPeriod      time.Duration
	aggregatePeriod time.Duration
	publish         bool
	sampleBuffers   map[string]*sampleBuffer
	sampleBufferMu  sync.Mutex
	broker          *brokerClient
	database        *databaseClient
	lineMu          sync.Mutex
	lineBuffer      bytes.Buffer
}

func Create(opts Options) (*Engine, error) {
	if len(opts.Plugins) == 0 {
		return nil, errors.New("no plugins selected")
	}
	if opts.PollPeriod <= 0 {
		return nil, fmt.Errorf("invalid poll period [%s] must be > 0", opts.PollPeriod)
	}
	if opts.AggregatePeriod <= 0 {
		return nil, fmt.Errorf("invalid aggregate period [%s] must be > 0", opts.AggregatePeriod)
	}
	if opts.AggregatePeriod%opts.PollPeriod != 0 {
		return nil, fmt.Errorf("invalid aggregate period [%s] must be a whole multiple of poll period [%s]", opts.AggregatePeriod, opts.PollPeriod)
	}
	sampleBufferCap := int(opts.AggregatePeriod / opts.PollPeriod)
	e := &Engine{
		plugins:         opts.Plugins,
		pollPeriod:      opts.PollPeriod,
		aggregatePeriod: opts.AggregatePeriod,
		publish:         opts.PublishData,
		sampleBuffers:   map[string]*sampleBuffer{},
	}
	for _, p := range opts.Plugins {
		if p.Mode() == plugin.ModeWindowed {
			e.sampleBuffers[p.Name()] = newSampleBuffer(sampleBufferCap)
		}
	}
	return e, nil
}

func (e *Engine) Run(ctx context.Context) error {
	slog.Info("state", "engine", "core", "phase", "start", "poll", e.pollPeriod, "aggregate", e.aggregatePeriod, "plugins", len(e.plugins), "publish", e.publish)
	if e.publish {
		if err := e.connectBroker(ctx); err != nil {
			slog.Error("state", "engine", "broker", "phase", "connect", "error", err)
		}
		e.connectDatabase()
	}
	defer e.shutdown()
	pollTicker := time.NewTicker(e.pollPeriod)
	defer pollTicker.Stop()
	aggTicker := time.NewTicker(e.aggregatePeriod)
	defer aggTicker.Stop()
	e.PollSamples(ctx)
	for _, v := range e.AggregateSamples(ctx, e.plugins) {
		e.publishAggregate(ctx, v)
	}
	for {
		select {
		case <-ctx.Done():
			return ctx.Err()
		case <-pollTicker.C:
			e.PollSamples(ctx)
		case <-aggTicker.C:
			for _, v := range e.AggregateSamples(ctx, e.plugins) {
				e.publishAggregate(ctx, v)
			}
		}
	}
}

func (e *Engine) PollSamples(ctx context.Context) {
	var wg sync.WaitGroup
	for _, p := range e.plugins {
		if p.Mode() != plugin.ModeWindowed {
			continue
		}
		wg.Add(1)
		go func(p plugin.Plugin) {
			defer wg.Done()
			m := e.safePoll(ctx, p)
			e.sampleBufferMu.Lock()
			e.sampleBuffers[p.Name()].Add(m)
			e.sampleBufferMu.Unlock()
			slog.Debug("poll", "plugin", p.Name(), "points", len(m.Points))
		}(p)
	}
	wg.Wait()
}

func (e *Engine) AggregateSamples(ctx context.Context, plugins []plugin.Plugin) []plugin.Aggregate {
	slog.Debug("aggregate", "phase", "start", "plugins", len(plugins))
	aggregates := make([]plugin.Aggregate, 0, len(plugins))
	for _, p := range plugins {
		var samples []plugin.Sample
		if p.Mode() == plugin.ModeWindowed {
			buffer := e.sampleBuffers[p.Name()]
			e.sampleBufferMu.Lock()
			samples = buffer.Samples()
			e.sampleBufferMu.Unlock()
			if len(samples) == 0 {
				m := e.safePoll(ctx, p)
				e.sampleBufferMu.Lock()
				buffer.Add(m)
				samples = buffer.Samples()
				e.sampleBufferMu.Unlock()
			}
		} else {
			m := e.safePoll(ctx, p)
			samples = []plugin.Sample{m}
		}
		v := e.safeAggregate(p, samples)
		state := plugin.StateOff
		if v.OK {
			state = plugin.StateOn
		}
		if tracker := p.State(); tracker != nil {
			tracker.Set(state)
		}
		aggregates = append(aggregates, v)
		slog.Info("aggregate", "plugin", p.Name(), "status", string(v.Status), "detail", v.Detail, "reason", v.Reason, "score", v.Score, "ok", v.OK)
	}
	return aggregates
}

func (e *Engine) safePoll(ctx context.Context, p plugin.Plugin) (m plugin.Sample) {
	defer func() {
		if r := recover(); r != nil {
			slog.Error("poll panic", "plugin", p.Name(), "panic", r)
			m = plugin.Sample{}
		}
		m.Plugin = p.Name()
		if m.Timestamp.IsZero() {
			m.Timestamp = time.Now()
		}
	}()
	sample, err := p.Poll(ctx)
	if err != nil {
		slog.Warn("poll error", "plugin", p.Name(), "error", err)
	}
	return sample
}

func (e *Engine) safeAggregate(p plugin.Plugin, samples []plugin.Sample) (v plugin.Aggregate) {
	defer func() {
		if r := recover(); r != nil {
			slog.Error("aggregate panic", "plugin", p.Name(), "panic", r)
			v = plugin.Diagnose(plugin.StatusDead, 0, "PLUGIN_PANIC", "plugin panicked during aggregate")
		}
		v.Plugin = p.Name()
		v.WindowSize = int(e.aggregatePeriod / time.Second)
		v.SampleCount = len(samples)
		if v.Timestamp.IsZero() {
			v.Timestamp = time.Now()
		}
	}()
	aggregate, err := p.Aggregate(samples)
	if err != nil {
		slog.Warn("aggregate error", "plugin", p.Name(), "error", err)
	}
	return aggregate
}

func (e *Engine) publishAggregate(ctx context.Context, m plugin.Aggregate) {
	if e.broker != nil {
		e.broker.publishAggregate(m)
	}
	if e.database != nil {
		e.lineMu.Lock()
		e.lineBuffer.Reset()
		m.AppendLineProtocol(&e.lineBuffer, measurement, time.Now().UnixNano())
		data := append([]byte(nil), e.lineBuffer.Bytes()...)
		e.lineMu.Unlock()
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

func (e *Engine) pluginByName(name string) (plugin.Plugin, bool) {
	for _, p := range e.plugins {
		if p.Name() == name {
			return p, true
		}
	}
	return nil, false
}
