package engine

import (
	"bytes"
	"context"
	"errors"
	"fmt"
	"net/http"
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
	online     bool
	attempts   int
	lostAt     time.Time
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

func databaseConnect(ctx context.Context, configPath string) (*databaseClient, error) {
	connectStart := time.Now()
	client, endpoint, err := newInfluxClient(configPath)
	if err != nil {
		return nil, fmt.Errorf("connect failed [%w]", err)
	}
	database := &databaseClient{configPath: configPath, endpoint: endpoint, client: client, lostAt: connectStart}
	for attempt := 0; ; attempt++ {
		reachErr := databaseReachable(ctx, endpoint)
		if reachErr == nil {
			database.online = true
			database.connected(connectStart, "connected", attempt)
			return database, nil
		}
		database.attempts = attempt + 1
		if attempt >= databaseAttempts {
			database.lost(connectStart, reachErr)
			return database, nil
		}
		database.offline(connectStart)
		select {
		case <-ctx.Done():
			return database, nil
		case <-time.After(databaseBackoff(attempt)):
		}
	}
}

func databaseReachable(ctx context.Context, endpoint string) error {
	requestCtx, cancel := context.WithTimeout(ctx, databaseTimeout)
	defer cancel()
	request, err := http.NewRequestWithContext(requestCtx, http.MethodGet, fmt.Sprintf("http://%s/health", endpoint), nil)
	if err != nil {
		return err
	}
	response, err := (&http.Client{Timeout: databaseTimeout}).Do(request)
	if err != nil {
		return err
	}
	_ = response.Body.Close()
	return nil
}

func databaseBackoff(attempt int) time.Duration {
	backoff := databaseRetry << attempt
	return min(backoff, databaseInterval)
}

func (d *databaseClient) write(ctx context.Context, data []byte) {
	writeStart := time.Now()
	err := d.client.Write(ctx, data)
	for attempt := range databaseRetries {
		if err == nil {
			break
		}
		select {
		case <-ctx.Done():
			return
		case <-time.After(databaseBackoff(attempt)):
		}
		err = d.client.Write(ctx, data)
	}
	if err == nil {
		if !d.online {
			d.online = true
			d.connected(d.lostAt, "reconnected", d.attempts)
			d.attempts = 0
		}
		return
	}
	d.attempts++
	scribe.Log(scribe.SourceDatabase, scribe.SubjectEndpoint(d.endpoint), scribe.ActionPublish).Warn("rejected", writeStart, "[%d] bytes dropped with [%v]", len(data), err)
	if !d.online {
		d.offline(d.lostAt)
		return
	}
	d.online = false
	d.lostAt = writeStart
	d.lost(writeStart, err)
	newClient, _, rebuildErr := newInfluxClient(d.configPath)
	if rebuildErr != nil {
		scribe.Log(scribe.SourceDatabase, scribe.SubjectEndpoint(d.endpoint), scribe.ActionConnect).Warn("sessions", writeStart, "[failed] rebuild with [%v]", rebuildErr)
		return
	}
	_ = d.client.Close()
	d.client = newClient
}

func (d *databaseClient) connected(since time.Time, state string, attempts int) {
	scribe.Log(scribe.SourceDatabase, scribe.SubjectEndpoint(d.endpoint), scribe.ActionConnect).Info("sessions", since, "[%s] after [%d] attempts", state, attempts)
}

func (d *databaseClient) offline(since time.Time) {
	scribe.Log(scribe.SourceDatabase, scribe.SubjectEndpoint(d.endpoint), scribe.ActionConnect).Debug("sessions", since, "[offline] attempt [%d]", d.attempts)
}

func (d *databaseClient) lost(since time.Time, err error) {
	scribe.Log(scribe.SourceDatabase, scribe.SubjectEndpoint(d.endpoint), scribe.ActionDisconnect).Warn("sessions", since, "[lost] connection with [%v]", err)
}

func (d *databaseClient) close() {
	closeStart := time.Now()
	if err := d.client.Close(); err != nil {
		scribe.Log(scribe.SourceDatabase, scribe.SubjectEndpoint(d.endpoint), scribe.ActionDisconnect).Warn("sessions", closeStart, "[failed] close with [%v]", err)
	}
}

const (
	databaseTimeout  = 3 * time.Second
	databaseInterval = 10 * time.Second
	databaseRetry    = 500 * time.Millisecond
	databaseAttempts = 3
	databaseRetries  = 2
)
