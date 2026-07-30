package engine

import (
	"context"
	"errors"
	"fmt"
	"log/slog"
	"networks/internal/config"
	"sync"

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
	database := config.Load().Database()
	if database == "" {
		slog.Warn("database address is empty")
		return
	}
	client, _, err := newDatabaseInfluxClient()
	if err != nil {
		slog.Error(fmt.Sprintf("failed to connect to database [%v]", err))
		return
	}
	slog.Info(fmt.Sprintf("connected to database [%s]", database))
	e.database = &databaseClient{url: database, client: client}
}

func (d *databaseClient) write(ctx context.Context, data []byte) {
	d.mu.Lock()
	defer d.mu.Unlock()
	if err := d.client.Write(ctx, data); err != nil {
		slog.Warn(fmt.Sprintf("database write failed [%s] [%v]", d.url, err))
		newClient, _, reconnectErr := newDatabaseInfluxClient()
		if reconnectErr != nil {
			slog.Warn(fmt.Sprintf("failed to reconnect to database [%s] [%v]", d.url, reconnectErr))
			return
		}
		_ = d.client.Close()
		d.client = newClient
		slog.Info(fmt.Sprintf("reconnected to database [%s]", d.url))
		return
	}
	slog.Debug("state", "engine", "database", "phase", "write", "bytes", len(data))
}

func (d *databaseClient) close() {
	d.mu.Lock()
	defer d.mu.Unlock()
	if err := d.client.Close(); err != nil {
		slog.Warn(fmt.Sprintf("database disconnect failed [%s] [%v]", d.url, err))
	}
}
