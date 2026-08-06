package plugins

import (
	"context"
	"crypto/tls"
	"fmt"
	"math"
	"net"
	"time"

	"networks/internal/plugin"
	"networks/internal/schema"
	"networks/internal/scribe"
)

const (
	warnDays     = 21
	probeTimeout = 5 * time.Second
)

var certsEndpoints = []string{
	"home.janeandgraham.com:443",
}

var (
	certsHome            = schema.Declare("certs/home", "certificate health across the monitored endpoints", aggregateCadence)
	certsOK              = certsHome.Bool("ok", "every endpoint verified and none expiring inside the warning window")
	certsScore           = certsHome.Int("score", "count", "diagnosis score from 0 to 100")
	certsMinExpiryDays   = certsHome.Float("min_expiry_days", "days", "days until the nearest certificate expires")
	certsEndpointsTotal  = certsHome.Int("endpoints_total", "count", "endpoints monitored")
	certsEndpointsFailed = certsHome.Int("endpoints_failed", "count", "endpoints unreachable or failing verification")
)

type certsReading struct {
	endpoint string
	days     float64
	validity float64
	verified bool
}

type certsResult struct {
	notBefore time.Time
	notAfter  time.Time
}

type certsPlugin struct {
	probe func(ctx context.Context, address string) (certsResult, error)
	state *plugin.StateTracker
}

func newCertsPlugin() *certsPlugin {
	return &certsPlugin{probe: probeCerts, state: plugin.NewStateTracker(plugin.StateOn)}
}

func (p *certsPlugin) Name() string { return "certs" }

func (p *certsPlugin) Mode() plugin.Mode { return plugin.ModeSnapshot }

func (p *certsPlugin) Poll(ctx context.Context) (plugin.Sample, error) {
	now := time.Now()
	readings := make([]certsReading, 0, len(certsEndpoints))
	for _, address := range certsEndpoints {
		result, err := p.probe(ctx, address)
		if err != nil {
			scribe.LogDebug("certs", "probe of endpoint [%s] failed [%v]", address, err)
			readings = append(readings, certsReading{endpoint: address})
			continue
		}
		scribe.LogDebug("certs", "probed endpoint [%s] not_after [%s]", address, result.notAfter)
		daysToExpiry := result.notAfter.Sub(now).Hours() / 24
		validityPercentage := 100.0
		total := result.notAfter.Sub(result.notBefore).Seconds()
		if total > 0 {
			validityPercentage = 100 * result.notAfter.Sub(now).Seconds() / total
		}
		if validityPercentage < 0 {
			validityPercentage = 0
		} else if validityPercentage > 100 {
			validityPercentage = 100
		}
		readings = append(readings, certsReading{
			endpoint: address,
			days:     plugin.Round(daysToExpiry, 1),
			validity: plugin.Round(validityPercentage, 1),
			verified: true,
		})
	}
	return plugin.Sample{Readings: readings}, nil
}

func (p *certsPlugin) Aggregate(samples []plugin.Sample) (plugin.Aggregate, error) {
	return diagnoseCerts(samples), nil
}

func (p *certsPlugin) Command(_ context.Context, _ plugin.State) error {
	return nil
}

func (p *certsPlugin) State() *plugin.StateTracker { return p.state }

func probeCerts(ctx context.Context, address string) (certsResult, error) {
	host, _, err := net.SplitHostPort(address)
	if err != nil {
		return certsResult{}, fmt.Errorf("invalid endpoint [%s] [%w]", address, err)
	}
	dialer := tls.Dialer{NetDialer: &net.Dialer{Timeout: probeTimeout}, Config: &tls.Config{ServerName: host}}
	connection, err := dialer.DialContext(ctx, "tcp", address)
	if err != nil {
		return certsResult{}, err
	}
	defer func() {
		if err := connection.Close(); err != nil {
			scribe.LogDebug("certs", "close of endpoint [%s] failed [%v]", address, err)
		}
	}()
	certs := connection.(*tls.Conn).ConnectionState().PeerCertificates
	if len(certs) == 0 {
		return certsResult{}, fmt.Errorf("no peer certificates [%s]", address)
	}
	leaf := certs[0]
	return certsResult{notBefore: leaf.NotBefore, notAfter: leaf.NotAfter}, nil
}

func diagnoseCerts(samples []plugin.Sample) plugin.Aggregate {
	stats := certsStats{minDays: math.MaxFloat64}
	nearestPercent := 100.0
	readings := plugin.Latest[[]certsReading](samples)
	for _, reading := range readings {
		if !reading.verified {
			stats.failed++
			continue
		}
		stats.reachable++
		if reading.days < warnDays {
			stats.warning++
		}
		if reading.days < stats.minDays {
			stats.minDays = reading.days
			nearestPercent = reading.validity
		}
	}
	score := plugin.Clamp(int(math.Round(nearestPercent)))
	result := plugin.Aggregate{}
	switch {
	case len(readings) == 0 || stats.reachable == 0:
		result = plugin.Diagnose(plugin.StatusDead, 0, "PROBE_UNREACHABLE: no certificate endpoint reachable across window")
		stats.minDays = 0
	case stats.failed > 0:
		result = plugin.Diagnose(plugin.StatusSick, score, fmt.Sprintf("VERIFY_FAILED: verify or reachability failure on [%d] of [%d] endpoints", stats.failed, stats.failed+stats.reachable))
	case stats.minDays < warnDays:
		result = plugin.Diagnose(plugin.StatusSick, score, fmt.Sprintf("EXPIRING_SOON: nearest certificate expires in [%.0f] days", stats.minDays))
	default:
		result = plugin.Diagnose(plugin.StatusFit, score, fmt.Sprintf("VALID: nearest certificate valid for [%.0f] days", stats.minDays))
	}
	stats.score = result.Score
	stats.ok = result.OK
	result.Points = reportCerts(stats)
	return result
}

func reportCerts(stats certsStats) []schema.Point {
	return []schema.Point{certsHome.Point(
		certsOK.Of(stats.ok),
		certsScore.Of(int64(stats.score)),
		certsMinExpiryDays.Of(plugin.Round(stats.minDays, 1)),
		certsEndpointsTotal.Of(int64(stats.reachable+stats.failed)),
		certsEndpointsFailed.Of(int64(stats.failed)))}
}

type certsStats struct {
	ok        bool
	score     int
	minDays   float64
	warning   int
	failed    int
	reachable int
}

func init() {
	plugin.Register(newCertsPlugin())
}
