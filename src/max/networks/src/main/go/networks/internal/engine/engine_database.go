package engine

import (
	"context"
	"errors"
	"fmt"
	"log/slog"
	"networks/internal/config"
	"sync"
	"time"

	"github.com/InfluxCommunity/influxdb3-go/influxdb3"
)

type databaseClient struct {
	mu     sync.Mutex
	url    string
	client *influxdb3.Client
}

func newDatabaseInfluxClient() (*influxdb3.Client, string, error) {
	cfg := config.Load()
	database := cfg.Database()
	if database == "" {
		return nil, "", errors.New("database address is empty")
	}
	token := cfg.DatabaseToken()
	if token == "" {
		return nil, "", errors.New("database token not configured")
	}
	databaseURL := fmt.Sprintf("http://%s", database)
	client, err := influxdb3.New(influxdb3.ClientConfig{Host: databaseURL, Token: token, Database: cfg.DatabaseName()})
	if err != nil {
		return nil, databaseURL, fmt.Errorf("new client failed [%s] [%w]", databaseURL, err)
	}
	return client, databaseURL, nil
}

func (e *Engine) connectDatabase() {
	if config.Load().Database() == "" {
		slog.Warn("state", "engine", "database", "phase", "connect", "error", "database address is empty")
		return
	}
	connectStart := time.Now()
	client, databaseURL, err := newDatabaseInfluxClient()
	if err != nil {
		slog.Error("state", "engine", "database", "phase", "connect", "error", err)
		return
	}
	slog.Info("state", "engine", "database", "phase", "connect", "duration", time.Since(connectStart).Truncate(time.Millisecond))
	e.database = &databaseClient{url: databaseURL, client: client}
}

func (d *databaseClient) write(ctx context.Context, data []byte) {
	d.mu.Lock()
	defer d.mu.Unlock()
	if err := d.client.Write(ctx, data); err != nil {
		slog.Warn("state", "engine", "database", "phase", "write", "database", d.url, "error", err)
		reconnectStart := time.Now()
		newClient, _, reconnectErr := newDatabaseInfluxClient()
		if reconnectErr != nil {
			slog.Warn("state", "engine", "database", "phase", "reconnect", "duration", time.Since(reconnectStart).Truncate(time.Millisecond), "database", d.url, "error", reconnectErr)
			return
		}
		_ = d.client.Close()
		d.client = newClient
		slog.Info("state", "engine", "database", "phase", "reconnect", "duration", time.Since(reconnectStart).Truncate(time.Millisecond))
		return
	}
	slog.Debug("state", "engine", "database", "phase", "write", "bytes", len(data))
}

func (d *databaseClient) close() {
	d.mu.Lock()
	defer d.mu.Unlock()
	if err := d.client.Close(); err != nil {
		slog.Warn("state", "engine", "database", "phase", "disconnect", "database", d.url, "error", err)
	}
}
