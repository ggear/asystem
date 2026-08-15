package engine

import (
	"context"
	"errors"
	"fmt"
	"supervisor/internal/config"
	"supervisor/internal/scribe"
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
	scribe.Engine("state", "database").Info("connect", connectStart, "database [%s]", databaseURL)
	return &databaseClient{configPath: configPath, url: databaseURL, client: client}, nil
}

func (d *databaseClient) write(ctx context.Context, data []byte) {
	writeStart := time.Now()
	if err := d.client.Write(ctx, data); err != nil {
		scribe.Engine("state", "database").Warn("write", writeStart, "database [%s] failed with [%v]", d.url, err)
		reconnectStart := time.Now()
		newClient, _, reconnErr := newInfluxClient(d.configPath)
		if reconnErr != nil {
			scribe.Engine("state", "database").Warn("reconnect", reconnectStart, "database [%s] failed with [%v]", d.url, reconnErr)
			return
		}
		_ = d.client.Close()
		d.client = newClient
		scribe.Engine("state", "database").Info("reconnect", reconnectStart, "database [%s]", d.url)
	}
}

func (d *databaseClient) close() {
	closeStart := time.Now()
	if err := d.client.Close(); err != nil {
		scribe.Engine("state", "database").Warn("disconnect", closeStart, "database [%s] failed with [%v]", d.url, err)
	}
}
