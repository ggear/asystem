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
	warnDays    = 21
	dialTimeout = 5 * time.Second
)

type endpoint struct {
	addr string
	sni  string
}

var endpoints = []endpoint{
	{addr: "home.asystem.io:443", sni: "home.asystem.io"},
}

type dialResult struct {
	notBefore time.Time
	notAfter  time.Time
	verified  bool
}

type certificatesPlugin struct {
	dial func(ctx context.Context, addr, sni string) (dialResult, error)
}

func newCertificatesPlugin() *certificatesPlugin {
	return &certificatesPlugin{dial: dialTLS}
}

func (p *certificatesPlugin) Name() string { return "certificates" }

func (p *certificatesPlugin) PollPhase() bool { return false }

func (p *certificatesPlugin) Poll(ctx context.Context) (plugin.Message, error) {
	now := time.Now()
	points := make([]plugin.Point, 0, len(endpoints))
	for _, e := range endpoints {
		tags := []plugin.Tag{{Key: "scope", Value: "endpoint"}, {Key: "endpoint", Value: e.addr}}
		result, err := p.dial(ctx, e.addr, e.sni)
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
		points = append(points, plugin.NewPoint(tags, plugin.Float("days_to_expiry", plugin.Round(days, 1)), plugin.Float("validity_pct", plugin.Round(clampPercent(validity), 1)), plugin.Bool("verified", true)))
	}
	return plugin.Message{Points: points}, nil
}

func (p *certificatesPlugin) Aggregate(samples []plugin.Message) (plugin.Message, error) {
	return decideCertificates(samples), nil
}

func dialTLS(ctx context.Context, addr, sni string) (dialResult, error) {
	dialer := &net.Dialer{Timeout: dialTimeout}
	conn, err := tls.DialWithDialer(dialer, "tcp", addr, &tls.Config{ServerName: sni})
	if err != nil {
		return dialResult{}, err
	}
	defer conn.Close()
	certs := conn.ConnectionState().PeerCertificates
	if len(certs) == 0 {
		return dialResult{}, err
	}
	leaf := certs[0]
	return dialResult{notBefore: leaf.NotBefore, notAfter: leaf.NotAfter, verified: true}, nil
}

func clampPercent(v float64) float64 {
	if v < 0 {
		return 0
	}
	if v > 100 {
		return 100
	}
	return v
}

func decideCertificates(samples []plugin.Message) plugin.Message {
	points := plugin.LatestPoints(samples)
	reachable := 0
	failed := 0
	minDays := math.MaxFloat64
	nearestPercent := 100.0
	for _, point := range points {
		verified := plugin.BoolField(point, "verified")
		days, hasDays := plugin.FloatField(point, "days_to_expiry")
		if !verified || !hasDays {
			failed++
			continue
		}
		reachable++
		if days < minDays {
			minDays = days
			if percent, ok := plugin.FloatField(point, "validity_pct"); ok {
				nearestPercent = percent
			}
		}
	}
	score := plugin.Clamp(int(math.Round(nearestPercent)))
	result := plugin.Message{}
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
	result.Points = buildCertificatesPoints(result.Score, minDays, failed, points)
	return result
}

func buildCertificatesPoints(score int, minDays float64, failed int, endpointPoints []plugin.Point) []plugin.Point {
	warning := 0
	for _, point := range endpointPoints {
		if days, ok := plugin.FloatField(point, "days_to_expiry"); ok && days < warnDays {
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
