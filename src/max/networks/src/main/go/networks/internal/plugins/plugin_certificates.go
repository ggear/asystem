package plugins

import (
	"context"
	"crypto/tls"
	"fmt"
	"math"
	"net"
	"time"

	"networks/internal/plugin"
)

const (
	warnDays     = 21
	probeTimeout = 5 * time.Second
)

type endpoint struct {
	addr string
	sni  string
}

var endpoints = []endpoint{
	{addr: "home.asystem.io:443", sni: "home.asystem.io"},
}

type probeResult struct {
	notBefore time.Time
	notAfter  time.Time
	verified  bool
}

type certificatesPlugin struct {
	probe func(ctx context.Context, addr, sni string) (probeResult, error)
}

func newCertificatesPlugin() *certificatesPlugin {
	return &certificatesPlugin{probe: probeCertificates}
}

func (p *certificatesPlugin) Name() string { return "certificates" }

func (p *certificatesPlugin) SampleMode() plugin.SampleMode { return plugin.Snapshot }

func (p *certificatesPlugin) Poll(ctx context.Context) (plugin.Sample, error) {
	now := time.Now()
	points := make([]plugin.Point, 0, len(endpoints))
	for _, e := range endpoints {
		tags := []plugin.Tag{{Key: "scope", Value: "endpoint"}, {Key: "endpoint", Value: e.addr}}
		result, err := p.probe(ctx, e.addr, e.sni)
		if err != nil || !result.verified {
			points = append(points, plugin.NewPoint(tags, plugin.Null("days_to_expiry"), plugin.Null("validity_pct"), plugin.Bool("verified", false)))
			continue
		}
		days := result.notAfter.Sub(now).Hours() / 24
		validity := 100.0
		total := result.notAfter.Sub(result.notBefore).Seconds()
		if total > 0 {
			validity = 100 * result.notAfter.Sub(now).Seconds() / total
		}
		if validity < 0 {
			validity = 0
		} else if validity > 100 {
			validity = 100
		}
		points = append(points, plugin.NewPoint(tags, plugin.Float("days_to_expiry", plugin.Round(days, 1)), plugin.Float("validity_pct", plugin.Round(validity, 1)), plugin.Bool("verified", true)))
	}
	return plugin.Sample{Points: points}, nil
}

func (p *certificatesPlugin) Aggregate(samples []plugin.Sample) (plugin.Aggregate, error) {
	return diagnoseCertificates(samples), nil
}

func probeCertificates(ctx context.Context, addr, sni string) (probeResult, error) {
	dialer := tls.Dialer{NetDialer: &net.Dialer{Timeout: probeTimeout}, Config: &tls.Config{ServerName: sni}}
	conn, err := dialer.DialContext(ctx, "tcp", addr)
	if err != nil {
		return probeResult{}, err
	}
	defer conn.Close()
	certs := conn.(*tls.Conn).ConnectionState().PeerCertificates
	if len(certs) == 0 {
		return probeResult{}, fmt.Errorf("no peer certificates [%s]", addr)
	}
	leaf := certs[0]
	return probeResult{notBefore: leaf.NotBefore, notAfter: leaf.NotAfter, verified: true}, nil
}

func diagnoseCertificates(samples []plugin.Sample) plugin.Aggregate {
	points := plugin.LatestPoints(samples)
	reachable := 0
	failed := 0
	minDays := math.MaxFloat64
	nearestPercent := 100.0
	for _, point := range points {
		verified, _ := point.Bool("verified")
		days, hasDays := point.Float("days_to_expiry")
		if !verified || !hasDays {
			failed++
			continue
		}
		reachable++
		if days < minDays {
			minDays = days
			if percent, ok := point.Float("validity_pct"); ok {
				nearestPercent = percent
			}
		}
	}
	score := plugin.Clamp(int(math.Round(nearestPercent)))
	result := plugin.Aggregate{}
	switch {
	case len(points) == 0 || reachable == 0:
		result = plugin.Diagnose(plugin.StatusDead, 0, "PROBE_UNREACHABLE", "no certificate endpoint reachable across window")
		minDays = 0
	case failed > 0:
		result = plugin.Diagnose(plugin.StatusSick, score, "VERIFY_FAILED", fmt.Sprintf("verify or reachability failure on %d/%d endpoints", failed, failed+reachable))
	case minDays < warnDays:
		result = plugin.Diagnose(plugin.StatusSick, score, "EXPIRING_SOON", fmt.Sprintf("nearest certificate expires in %.0f days", minDays))
	default:
		result = plugin.Diagnose(plugin.StatusFit, score, "VALID", fmt.Sprintf("nearest certificate valid for %.0f days", minDays))
	}
	result.Points = reportCertificates(result.Score, minDays, failed, points)
	return result
}

func reportCertificates(score int, minDays float64, failed int, endpointPoints []plugin.Point) []plugin.Point {
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
	plugin.Register(newCertificatesPlugin())
}
