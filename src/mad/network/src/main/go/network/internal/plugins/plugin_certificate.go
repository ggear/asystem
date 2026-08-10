package plugins

import (
	"context"
	"crypto/tls"
	"fmt"
	"math"
	"net"
	"time"

	"network/internal/plugin"
	"network/internal/schema"
	"network/internal/scribe"
)

const (
	warnDays     = 21
	probeTimeout = 5 * time.Second
)

var certificateEndpoints = []string{
	"home.janeandgraham.com:443",
}

var (
	certificateEndpoint    = schema.Declare("certificate/endpoint", "certificate health, one row per monitored endpoint", aggregateCadence).Entities(certificateEndpoints...)
	certificateName        = certificateEndpoint.Subject("endpoint", "monitored TLS endpoint")
	certificateVerified    = certificateEndpoint.Bool("verified", "endpoint reachable and its certificate verified")
	certificateExpiryDays  = certificateEndpoint.Float("expiry_days", "d", "days until the certificate expires")
	certificateValidityPct = certificateEndpoint.Float("validity_pct", "%", "share of the certificate lifetime still remaining")
)

type certificateReading struct {
	endpoint string
	days     float64
	validity float64
	verified bool
}

type certificateResult struct {
	notBefore time.Time
	notAfter  time.Time
}

type certificatePlugin struct {
	probe func(ctx context.Context, address string) (certificateResult, error)
	state *plugin.StateTracker
}

func newCertificatePlugin() *certificatePlugin {
	return &certificatePlugin{probe: probeCertificate, state: plugin.NewStateTracker(plugin.StateOn)}
}

func (p *certificatePlugin) Name() string { return "certificate" }

func (p *certificatePlugin) Mode() plugin.Mode { return plugin.ModeSnapshot }

func (p *certificatePlugin) Poll(ctx context.Context) (plugin.Sample, error) {
	now := time.Now()
	readings := make([]certificateReading, 0, len(certificateEndpoints))
	for _, address := range certificateEndpoints {
		result, err := p.probe(ctx, address)
		if err != nil {
			scribe.LogDebug("certificate", "probe of endpoint [%s] failed [%v]", address, err)
			readings = append(readings, certificateReading{endpoint: address})
			continue
		}
		scribe.LogDebug("certificate", "probed endpoint [%s] not_after [%s]", address, result.notAfter)
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
		readings = append(readings, certificateReading{
			endpoint: address,
			days:     plugin.Round(daysToExpiry, 1),
			validity: plugin.Round(validityPercentage, 1),
			verified: true,
		})
	}
	return plugin.Sample{Readings: readings}, nil
}

func (p *certificatePlugin) Aggregate(samples []plugin.Sample) (plugin.Aggregate, error) {
	return diagnoseCertificate(samples), nil
}

func (p *certificatePlugin) Command(_ context.Context, _ plugin.State) error {
	return nil
}

func (p *certificatePlugin) State() *plugin.StateTracker { return p.state }

func probeCertificate(ctx context.Context, address string) (certificateResult, error) {
	host, _, err := net.SplitHostPort(address)
	if err != nil {
		return certificateResult{}, fmt.Errorf("invalid endpoint [%s] [%w]", address, err)
	}
	dialer := tls.Dialer{NetDialer: &net.Dialer{Timeout: probeTimeout}, Config: &tls.Config{ServerName: host}}
	connection, err := dialer.DialContext(ctx, "tcp", address)
	if err != nil {
		return certificateResult{}, err
	}
	defer func() {
		if err := connection.Close(); err != nil {
			scribe.LogDebug("certificate", "close of endpoint [%s] failed [%v]", address, err)
		}
	}()
	certs := connection.(*tls.Conn).ConnectionState().PeerCertificates
	if len(certs) == 0 {
		return certificateResult{}, fmt.Errorf("no peer certificates [%s]", address)
	}
	leaf := certs[0]
	return certificateResult{notBefore: leaf.NotBefore, notAfter: leaf.NotAfter}, nil
}

func diagnoseCertificate(samples []plugin.Sample) plugin.Aggregate {
	stats := certificateStats{minDays: math.MaxFloat64}
	nearestPercent := 100.0
	readings := plugin.Latest[[]certificateReading](samples)
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
	result.Points = reportCertificate(readings)
	return result
}

func reportCertificate(readings []certificateReading) []schema.Point {
	points := make([]schema.Point, 0, len(readings))
	for _, reading := range readings {
		point := []schema.Value{
			certificateName.Of(reading.endpoint),
			certificateVerified.Of(reading.verified),
		}
		if reading.verified {
			point = append(point,
				certificateExpiryDays.Of(plugin.Round(reading.days, 1)),
				certificateValidityPct.Of(plugin.Round(reading.validity, 1)))
		}
		points = append(points, certificateEndpoint.Point(point...))
	}
	return points
}

type certificateStats struct {
	minDays   float64
	warning   int
	failed    int
	reachable int
}

func init() {
	plugin.Register(newCertificatePlugin())
}
