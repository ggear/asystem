package engine

import (
	"bytes"
	"context"
	"errors"
	"fmt"
	"log/slog"
	"networks/internal/config"
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
	pollPlugins     []plugin.Plugin
	pollPeriod      time.Duration
	aggregatePeriod time.Duration
	publish         bool
	host            string
	sampleBuffers   map[string]*sampleBuffer
	sampleBufferMu  sync.Mutex
	commands        chan command
	broker          *brokerClient
	database        *databaseClient
	lineMu          sync.Mutex
	lineBuf         bytes.Buffer
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
		host:            config.Load().Host(),
		sampleBuffers:   map[string]*sampleBuffer{},
		commands:        make(chan command, commandQueueSize),
	}
	for _, p := range opts.Plugins {
		if p.PollPhase() {
			e.pollPlugins = append(e.pollPlugins, p)
			e.sampleBuffers[p.Name()] = newSampleBuffer(sampleBufferCap)
		} else {
			e.sampleBuffers[p.Name()] = newSampleBuffer(1)
		}
	}
	return e, nil
}

func (e *Engine) Run(ctx context.Context) error {
	slog.Info("state", "engine", "core", "phase", "start", "poll", e.pollPeriod, "aggregate", e.aggregatePeriod, "plugins", len(e.plugins), "publish", e.publish)
	if e.publish {
		if err := e.connectBroker(); err != nil {
			slog.Error("state", "engine", "broker", "phase", "connect", "error", err)
		}
		e.connectDatabase()
	}
	drainDone := make(chan struct{})
	go func() {
		e.drainCommands(ctx)
		close(drainDone)
	}()
	defer func() {
		<-drainDone
		e.shutdown()
	}()
	pollTicker := time.NewTicker(e.pollPeriod)
	defer pollTicker.Stop()
	aggTicker := time.NewTicker(e.aggregatePeriod)
	defer aggTicker.Stop()
	e.pollOnce(ctx)
	for _, v := range e.Cycle(ctx, e.plugins) {
		e.publishVitals(ctx, v)
	}
	for {
		select {
		case <-ctx.Done():
			return ctx.Err()
		case <-pollTicker.C:
			e.pollOnce(ctx)
		case <-aggTicker.C:
			for _, v := range e.Cycle(ctx, e.plugins) {
				e.publishVitals(ctx, v)
			}
		}
	}
}

func (e *Engine) pollOnce(ctx context.Context) {
	var wg sync.WaitGroup
	for _, p := range e.pollPlugins {
		wg.Add(1)
		go func(p plugin.Plugin) {
			defer wg.Done()
			m := e.safePoll(ctx, p)
			e.sampleBufferMu.Lock()
			e.sampleBuffers[p.Name()].Add(m)
			e.sampleBufferMu.Unlock()
			slog.Debug("pulse", "plugin", p.Name(), "status", string(m.Status), "score", m.Score, "detail", m.Detail)
		}(p)
	}
	wg.Wait()
}

func (e *Engine) Cycle(ctx context.Context, plugins []plugin.Plugin) []plugin.Message {
	slog.Debug("cycle", "phase", "start", "plugins", len(plugins))
	vitals := make([]plugin.Message, 0, len(plugins))
	for _, p := range plugins {
		var samples []plugin.Message
		if p.PollPhase() {
			buffer := e.sampleBuffers[p.Name()]
			e.sampleBufferMu.Lock()
			samples = buffer.Messages()
			e.sampleBufferMu.Unlock()
			if len(samples) == 0 {
				m := e.safePoll(ctx, p)
				e.sampleBufferMu.Lock()
				buffer.Add(m)
				samples = buffer.Messages()
				e.sampleBufferMu.Unlock()
			}
		} else {
			m := e.safePoll(ctx, p)
			samples = []plugin.Message{m}
		}
		v := e.safeAggregate(p, samples)
		vitals = append(vitals, v)
		slog.Info("vitals", "plugin", p.Name(), "status", string(v.Status), "detail", v.Detail, "reason", v.Reason, "score", v.Score, "ok", v.OK)
	}
	return vitals
}

func (e *Engine) safePoll(ctx context.Context, p plugin.Plugin) (m plugin.Message) {
	defer func() {
		if r := recover(); r != nil {
			slog.Error("poll panic", "plugin", p.Name(), "panic", r)
			m = plugin.Message{Status: plugin.StatusDead, Detail: "PLUGIN_PANIC"}
		}
		m.Plugin = p.Name()
		m.Host = e.host
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

func (e *Engine) safeAggregate(p plugin.Plugin, samples []plugin.Message) (v plugin.Message) {
	defer func() {
		if r := recover(); r != nil {
			slog.Error("aggregate panic", "plugin", p.Name(), "panic", r)
			v = plugin.Message{Status: plugin.StatusDead, Detail: "PLUGIN_PANIC"}
		}
		v.Plugin = p.Name()
		v.Host = e.host
		v.SamplePeriodS = int(e.aggregatePeriod / time.Second)
		v.SampleCount = len(samples)
		if v.Timestamp.IsZero() {
			v.Timestamp = time.Now()
		}
	}()
	vitals, err := p.Aggregate(samples)
	if err != nil {
		slog.Warn("aggregate error", "plugin", p.Name(), "error", err)
	}
	return vitals
}

func (e *Engine) publishVitals(ctx context.Context, m plugin.Message) {
	if e.broker != nil {
		e.broker.publishVitals(m)
	}
	if e.database != nil {
		e.lineMu.Lock()
		e.lineBuf.Reset()
		m.AppendLineProtocol(&e.lineBuf, measurement, time.Now().UnixNano())
		data := append([]byte(nil), e.lineBuf.Bytes()...)
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
