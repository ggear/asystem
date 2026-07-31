package engine

import (
	"context"
	"errors"
	"fmt"
	"networks/internal/config"
	"networks/internal/scribe"
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

func newDatabaseClient() (*databaseClient, error) {
	database := config.Load().Database()
	if database == "" {
		return nil, errors.New("database address is empty")
	}
	client, _, err := newDatabaseInfluxClient()
	if err != nil {
		return nil, err
	}
	scribe.Infof(scribe.Global, "connected to database [%s]", database)
	return &databaseClient{url: database, client: client}, nil
}

func (d *databaseClient) write(ctx context.Context, data []byte) {
	d.mu.Lock()
	defer d.mu.Unlock()
	if err := d.client.Write(ctx, data); err != nil {
		scribe.Warnf(scribe.Global, "database write failed [%s] [%v]", d.url, err)
		newClient, _, reconnectErr := newDatabaseInfluxClient()
		if reconnectErr != nil {
			scribe.Warnf(scribe.Global, "failed to reconnect to database [%s] [%v]", d.url, reconnectErr)
			return
		}
		_ = d.client.Close()
		d.client = newClient
		scribe.Infof(scribe.Global, "reconnected to database [%s]", d.url)
		return
	}
	scribe.Debugf(scribe.Global, "wrote [%d] bytes to database", len(data))
}

func (d *databaseClient) close() {
	d.mu.Lock()
	defer d.mu.Unlock()
	if err := d.client.Close(); err != nil {
		scribe.Warnf(scribe.Global, "database disconnect failed [%s] [%v]", d.url, err)
	}
}
