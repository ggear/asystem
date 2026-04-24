package engine

import (
	"context"
	"errors"
	"fmt"
	"log/slog"
	"supervisor/internal/config"
	"time"

	"github.com/InfluxCommunity/influxdb3-go/influxdb3"
)

type databaseClient struct {
	configPath string
	url        string
	client     *influxdb3.Client
}

func newInfluxClient(configPath string) (*influxdb3.Client, string, error) {
	cfg := config.Load(configPath)
	database := cfg.Database()
	if database == "" {
		return nil, "", errors.New("database address is empty")
	}
	token := cfg.DatabaseToken()
	if token == "" {
		return nil, "", errors.New("database token not configured")
	}
	databaseURL := fmt.Sprintf("http://%s", database)
	client, err := influxdb3.New(influxdb3.ClientConfig{
		Host:     databaseURL,
		Token:    token,
		Database: cfg.DatabaseName(),
	})
	if err != nil {
		return nil, databaseURL, fmt.Errorf("new client failed [%s]: %w", databaseURL, err)
	}
	return client, databaseURL, nil
}

func databaseConnect(configPath string) (*databaseClient, error) {
	connectStart := time.Now()
	client, databaseURL, err := newInfluxClient(configPath)
	if err != nil {
		return nil, fmt.Errorf("connect failed: %w", err)
	}
	slog.Info("state", "engine", "database", "phase", "connect", "duration", time.Since(connectStart).Truncate(time.Millisecond))
	return &databaseClient{configPath: configPath, url: databaseURL, client: client}, nil
}

func (d *databaseClient) write(ctx context.Context, data []byte) {
	if err := d.client.Write(ctx, data); err != nil {
		slog.Warn("state", "engine", "database", "phase", "write", "database", d.url, "error", err)
		reconnectStart := time.Now()
		newClient, _, reconnErr := newInfluxClient(d.configPath)
		if reconnErr != nil {
			slog.Warn("state", "engine", "database", "phase", "reconnect", "duration", time.Since(reconnectStart).Truncate(time.Millisecond), "database", d.url, "error", reconnErr)
			return
		}
		_ = d.client.Close()
		d.client = newClient
		slog.Info("state", "engine", "database", "phase", "reconnect", "duration", time.Since(reconnectStart).Truncate(time.Millisecond))
	}
}

func (d *databaseClient) close() {
	if err := d.client.Close(); err != nil {
		slog.Warn("state", "engine", "database", "phase", "disconnect", "database", d.url, "error", err)
	}
}
