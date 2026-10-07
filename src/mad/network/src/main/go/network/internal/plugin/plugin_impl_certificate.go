package plugin

import (
	"context"
	"crypto/tls"
	"fmt"
	"math"
	"net"
	"time"

	"network/internal/schema"
	"network/internal/scribe"
)

const (
	certificateWarnDays = 21
	certificateTimeout  = 5 * time.Second
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
	state *StateTracker
}

func newCertificatePlugin() *certificatePlugin {
	return &certificatePlugin{probe: probeCertificate, state: NewStateTracker(StateOn)}
}

func (p *certificatePlugin) Name() string { return "certificate" }

func (p *certificatePlugin) Mode() Mode { return ModeSnapshot }

func (p *certificatePlugin) Poll(ctx context.Context) (Sample, error) {
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
		validity := 100.0
		if lifetime := result.notAfter.Sub(result.notBefore).Seconds(); lifetime > 0 {
			validity = math.Min(math.Max(100*result.notAfter.Sub(now).Seconds()/lifetime, 0), 100)
		}
		readings = append(readings, certificateReading{endpoint: address, days: daysToExpiry, validity: validity, verified: true})
	}
	return Sample{Readings: readings}, nil
}

func (p *certificatePlugin) Aggregate(samples []Sample) (Aggregate, error) {
	return diagnoseCertificate(samples), nil
}

func (p *certificatePlugin) Command(context.Context, State) error {
	return nil
}

func (p *certificatePlugin) State() *StateTracker { return p.state }

func probeCertificate(ctx context.Context, address string) (certificateResult, error) {
	host, _, err := net.SplitHostPort(address)
	if err != nil {
		return certificateResult{}, fmt.Errorf("invalid endpoint [%s] [%w]", address, err)
	}
	dialer := tls.Dialer{NetDialer: &net.Dialer{Timeout: certificateTimeout}, Config: &tls.Config{ServerName: host}}
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

func diagnoseCertificate(samples []Sample) Aggregate {
	readings := latestReading[[]certificateReading](samples)
	failed := 0
	nearestDays, nearestValidity := math.MaxFloat64, 100.0
	for _, reading := range readings {
		if !reading.verified {
			failed++
			continue
		}
		if reading.days < nearestDays {
			nearestDays, nearestValidity = reading.days, reading.validity
		}
	}
	nearestDays = math.Round(nearestDays)
	score := clamp(int(math.Round(nearestValidity)))
	result := Aggregate{}
	switch {
	case failed == len(readings):
		result = Diagnose(StatusDead, 0, "PROBE_UNREACHABLE: no certificate endpoint reachable")
	case failed > 0:
		result = Diagnose(StatusSick, score, fmt.Sprintf("VERIFY_FAILED: verify or reachability failure on %d of %d endpoints", failed, len(readings)))
	case nearestDays < certificateWarnDays:
		result = Diagnose(StatusSick, score, fmt.Sprintf("EXPIRING_SOON: nearest certificate expires in %.0f days", nearestDays))
	default:
		result = Diagnose(StatusFit, score, fmt.Sprintf("VALID: nearest certificate valid for %.0f days", nearestDays))
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
				certificateExpiryDays.Of(round(reading.days, 1)),
				certificateValidityPct.Of(round(reading.validity, 0)))
		}
		points = append(points, certificateEndpoint.Point(point...))
	}
	return points
}

func init() {
	register(newCertificatePlugin())
}
