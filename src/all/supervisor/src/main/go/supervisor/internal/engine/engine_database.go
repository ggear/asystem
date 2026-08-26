package engine

import (
	"bytes"
	"context"
	"errors"
	"fmt"
	"sort"
	"supervisor/internal/config"
	"supervisor/internal/metric"
	"supervisor/internal/schema"
	"supervisor/internal/scribe"
	"time"

	"github.com/InfluxCommunity/influxdb3-go/influxdb3"
)

type databaseClient struct {
	configPath string
	endpoint   string
	client     *influxdb3.Client
}

type databaseKey struct {
	host    string
	service string
}

type databaseBatch struct {
	protocol bytes.Buffer
	groups   map[databaseKey]map[string]schema.Field
	host     schema.Relation
	service  schema.Relation
}

func newDatabaseBatch() *databaseBatch {
	return &databaseBatch{
		groups:  make(map[databaseKey]map[string]schema.Field),
		host:    metric.HostRelation(),
		service: metric.ServiceRelation(),
	}
}

func (b *databaseBatch) reset() {
	b.protocol.Reset()
	clear(b.groups)
}

func (b *databaseBatch) add(guid metric.RecordGUID, record *metric.Record) {
	if record.Value.Failed || record.Value.Pulse == nil || len(record.Tags) == 0 {
		return
	}
	field, ok := record.Tags["metric"]
	if !ok {
		return
	}
	key := databaseKey{host: guid.Host, service: guid.ServiceName}
	b.field(key, field, "", record.Value.Pulse)
	if record.Value.Trend != nil {
		b.field(key, field, "_trend", record.Value.Trend)
	}
}

func (b *databaseBatch) field(key databaseKey, field, suffix string, detail *metric.ValueDataDetail) {
	fields := b.groups[key]
	if fields == nil {
		fields = map[string]schema.Field{}
		b.groups[key] = fields
	}
	fields[field+suffix] = schema.Field{Text: detail.Value(), Flag: detail.OK}
}

func (b *databaseBatch) render(timestamp string) int {
	order := make([]databaseKey, 0, len(b.groups))
	for key := range b.groups {
		order = append(order, key)
	}
	sort.Slice(order, func(i, j int) bool {
		if order[i].host != order[j].host {
			return order[i].host < order[j].host
		}
		return order[i].service < order[j].service
	})
	for _, key := range order {
		relation := b.host
		tags := [][2]string{{"host", key.host}}
		if key.service != "" {
			relation = b.service
			tags = append(tags, [2]string{"service", key.service})
		}
		schema.AppendLineProtocol(&b.protocol, "supervisor", relation, tags, b.groups[key], timestamp)
	}
	return b.protocol.Len()
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
		return nil, database, fmt.Errorf("new client failed [%s] [%w]", databaseURL, err)
	}
	return client, database, nil
}

func databaseConnect(configPath string) (*databaseClient, error) {
	connectStart := time.Now()
	client, endpoint, err := newInfluxClient(configPath)
	if err != nil {
		return nil, fmt.Errorf("connect failed [%w]", err)
	}
	scribe.Log(scribe.SourceDatabase, scribe.SubjectEndpoint(endpoint), scribe.ActionConnect).Info("sessions", connectStart, "[connected]")
	return &databaseClient{configPath: configPath, endpoint: endpoint, client: client}, nil
}

func (d *databaseClient) write(ctx context.Context, data []byte) {
	writeStart := time.Now()
	if err := d.client.Write(ctx, data); err != nil {
		scribe.Log(scribe.SourceDatabase, scribe.SubjectEndpoint(d.endpoint), scribe.ActionPublish).Warn("rejected", writeStart, "write failed with [%v]", err)
		reconnectStart := time.Now()
		newClient, _, reconnectErr := newInfluxClient(d.configPath)
		if reconnectErr != nil {
			scribe.Log(scribe.SourceDatabase, scribe.SubjectEndpoint(d.endpoint), scribe.ActionConnect).Warn("sessions", reconnectStart, "[failed] reconnect with [%v]", reconnectErr)
			return
		}
		_ = d.client.Close()
		d.client = newClient
		scribe.Log(scribe.SourceDatabase, scribe.SubjectEndpoint(d.endpoint), scribe.ActionConnect).Info("sessions", reconnectStart, "[reconnected]")
	}
}

func (d *databaseClient) close() {
	closeStart := time.Now()
	if err := d.client.Close(); err != nil {
		scribe.Log(scribe.SourceDatabase, scribe.SubjectEndpoint(d.endpoint), scribe.ActionDisconnect).Warn("sessions", closeStart, "[failed] close with [%v]", err)
	}
}
