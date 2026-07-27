package engine

import (
	"context"
	"encoding/json"
	"log/slog"
	"networks/internal/plugin"
	"strings"

	mqtt "github.com/eclipse/paho.mqtt.golang"
)

const commandQueueSize = 16

type command struct {
	Action string
	Plugin string
	Result chan plugin.Aggregate
	Source string
}

func (e *Engine) onCommandMessage(_ mqtt.Client, msg mqtt.Message) {
	topic := msg.Topic()
	if topic == brokerResultTopic {
		return
	}
	pluginName := ""
	switch {
	case strings.HasPrefix(topic, brokerCommandPrefix+"/"):
		pluginName = strings.TrimPrefix(topic, brokerCommandPrefix+"/")
	case topic == brokerCommandPrefix:
	default:
		return
	}
	var payload struct {
		Command string `json:"command"`
	}
	if err := json.Unmarshal(msg.Payload(), &payload); err != nil {
		slog.Warn("command", "source", "mqtt", "phase", "parse", "topic", topic, "error", err)
		return
	}
	if payload.Command != "check" {
		slog.Warn("command", "source", "mqtt", "phase", "validate", "topic", topic, "command", payload.Command)
		return
	}
	if pluginName != "" {
		if _, ok := e.pluginByName(pluginName); !ok {
			slog.Warn("command", "source", "mqtt", "phase", "validate", "topic", topic, "error", "unknown plugin")
			return
		}
	}
	e.enqueue(command{Action: "check", Plugin: pluginName, Source: "mqtt"})
}

func (e *Engine) enqueue(c command) {
	select {
	case e.commands <- c:
	default:
		slog.Warn("command", "phase", "enqueue", "source", c.Source, "error", "queue full, dropped")
	}
}

func (e *Engine) drainCommands(ctx context.Context) {
	for {
		select {
		case <-ctx.Done():
			return
		case c := <-e.commands:
			e.runCommand(ctx, c)
		}
	}
}

func (e *Engine) runCommand(ctx context.Context, c command) {
	targets := e.plugins
	if c.Plugin != "" {
		p, ok := e.pluginByName(c.Plugin)
		if !ok {
			if c.Result != nil {
				close(c.Result)
			}
			return
		}
		targets = []plugin.Plugin{p}
	}
	aggregates := e.AggregateSamples(ctx, targets)
	for _, v := range aggregates {
		e.publishAggregate(ctx, v)
		if e.broker != nil && c.Source == "mqtt" {
			e.broker.publishResult(v)
		}
	}
	if c.Result != nil {
		for _, v := range aggregates {
			c.Result <- v
		}
		close(c.Result)
	}
}
