package plugins

import (
	"context"
	"crypto/tls"
	"fmt"
	"math"
	"net"
	"time"

	"networks/internal/plugin"
	"networks/internal/scribe"
)

const (
	warnDays     = 21
	probeTimeout = 5 * time.Second
)

var certsEndpoints = []string{
	"home.janeandgraham.com:443",
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
	points := make([]plugin.Point, 0, len(certsEndpoints))
	for _, address := range certsEndpoints {
		tags := []plugin.Tag{{Key: "scope", Value: "endpoint"}, {Key: "endpoint", Value: address}}
		result, err := p.probe(ctx, address)
		if err != nil {
			scribe.LogDebug("certs", "probe of endpoint [%s] failed [%v]", address, err)
			points = append(points, plugin.NewPoint(tags, plugin.Null("days_to_expiry"), plugin.Null("validity_percentage"), plugin.Bool("verified", false)))
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
		points = append(points, plugin.NewPoint(tags, plugin.Float("days_to_expiry", plugin.Round(daysToExpiry, 1)), plugin.Float("validity_percentage", plugin.Round(validityPercentage, 1)), plugin.Bool("verified", true)))
	}
	return plugin.Sample{Points: points}, nil
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
	failed := 0
	reachable := 0
	nearestPercent := 100.0
	minDays := math.MaxFloat64
	points := plugin.LatestPoints(samples)
	for _, point := range points {
		verified, _ := point.Bool("verified")
		days, hasDays := point.Float("days_to_expiry")
		percent, hasPercent := point.Float("validity_percentage")
		if !verified || !hasDays || !hasPercent {
			failed++
			continue
		}
		reachable++
		if days < minDays {
			minDays = days
			nearestPercent = percent
		}
	}
	score := plugin.Clamp(int(math.Round(nearestPercent)))
	result := plugin.Aggregate{}
	switch {
	case len(points) == 0 || reachable == 0:
		result = plugin.Diagnose(plugin.StatusDead, 0, "PROBE_UNREACHABLE: no certificate endpoint reachable across window")
		minDays = 0
	case failed > 0:
		result = plugin.Diagnose(plugin.StatusSick, score, fmt.Sprintf("VERIFY_FAILED: verify or reachability failure on [%d] of [%d] endpoints", failed, failed+reachable))
	case minDays < warnDays:
		result = plugin.Diagnose(plugin.StatusSick, score, fmt.Sprintf("EXPIRING_SOON: nearest certificate expires in [%.0f] days", minDays))
	default:
		result = plugin.Diagnose(plugin.StatusFit, score, fmt.Sprintf("VALID: nearest certificate valid for [%.0f] days", minDays))
	}
	result.Points = reportCerts(result.Score, minDays, failed, points)
	return result
}

func reportCerts(score int, minDays float64, failed int, endpointPoints []plugin.Point) []plugin.Point {
	warning := 0
	for _, point := range endpointPoints {
		if days, ok := point.Float("days_to_expiry"); ok && days < warnDays {
			warning++
		}
	}
	summary := plugin.NewPoint([]plugin.Tag{{Key: "scope", Value: "summary"}},
		plugin.Int("score", int64(score)),
		plugin.Float("min_days_to_expiry", plugin.Round(minDays, 1)),
		plugin.Int("warning_count", int64(warning)),
		plugin.Int("verify_failed_count", int64(failed)))
	return plugin.PrependSummaryPoints(summary, endpointPoints)
}

func init() {
	plugin.Register(newCertsPlugin())
}
