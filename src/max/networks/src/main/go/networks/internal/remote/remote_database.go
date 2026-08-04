package remote

import (
	"context"
	"errors"
	"fmt"
	"networks/internal/scribe"

	"github.com/InfluxCommunity/influxdb3-go/influxdb3"
)

type Database struct {
	address string
	client  *influxdb3.Client
}

func NewDatabase(address, token, name string) (*Database, error) {
	if address == "" {
		return nil, errors.New("database address is empty")
	}
	client, err := newInfluxClient(address, token, name)
	if err != nil {
		return nil, err
	}
	scribe.LogInfo(scribe.Global, "configured database client [%s]", address)
	return &Database{address: address, client: client}, nil
}

func (d *Database) Write(ctx context.Context, line []byte) {
	if err := d.client.Write(ctx, line); err != nil {
		scribe.LogWarn(scribe.Global, "database write failed [%s] [%v]", d.address, err)
		return
	}
	scribe.LogDebug(scribe.Global, "wrote [%d] bytes to database", len(line))
}

func (d *Database) Close() error {
	return d.client.Close()
}

func newInfluxClient(address, token, name string) (*influxdb3.Client, error) {
	if token == "" {
		return nil, errors.New("database token not configured")
	}
	databaseURL := fmt.Sprintf("http://%s", address)
	client, err := influxdb3.New(influxdb3.ClientConfig{Host: databaseURL, Token: token, Database: name})
	if err != nil {
		return nil, fmt.Errorf("new client failed [%s] [%w]", databaseURL, err)
	}
	return client, nil
}
