package plugins

import (
	"context"
	"fmt"
	"log/slog"
	"math"
	"net"
	"sort"
	"strings"
	"time"

	"networks/internal/plugin"
)

const (
	checkDomain        = "home.janeandgraham.com"
	domainProbeTimeout = 5 * time.Second
)

type resolver struct {
	name    string
	address string
}

var resolvers = []resolver{
	{name: "cloudflare", address: "1.1.1.1:53"},
	{name: "google", address: "8.8.8.8:53"},
	{name: "quad9", address: "9.9.9.9:53"},
	{name: "opendns", address: "208.67.222.222:53"},
	{name: "adguard", address: "94.140.14.14:53"},
}

type domainResult struct {
	addresses []string
	latency   time.Duration
}

type domainPlugin struct {
	probe func(ctx context.Context, server, domain string) (domainResult, error)
	state *plugin.StateTracker
}

func newDomainPlugin() *domainPlugin {
	return &domainPlugin{probe: probeDomain, state: plugin.NewStateTracker(plugin.StateOn)}
}

func (p *domainPlugin) Name() string { return "domain" }

func (p *domainPlugin) Mode() plugin.Mode { return plugin.ModeSnapshot }

func (p *domainPlugin) Poll(ctx context.Context) (plugin.Sample, error) {
	points := make([]plugin.Point, 0, len(resolvers))
	for _, r := range resolvers {
		result, err := p.probe(ctx, r.address, checkDomain)
		if err != nil || len(result.addresses) == 0 {
			slog.Debug(fmt.Sprintf("plugin [domain] probe of resolver [%s] server [%s] failed [%v]", r.name, r.address, err))
			points = append(points, plugin.NewPoint(
				[]plugin.Tag{{Key: "scope", Value: "resolver"}, {Key: "resolver", Value: r.name}, {Key: "addresses", Value: ""}},
				plugin.Bool("resolved", false), plugin.Null("latency_ms")))
			continue
		}
		addresses := strings.Join(result.addresses, ",")
		latency := plugin.Round(float64(result.latency)/float64(time.Millisecond), 1)
		slog.Debug(fmt.Sprintf("plugin [domain] probed resolver [%s] server [%s] addresses [%s] latency_ms [%v]", r.name, r.address, addresses, latency))
		points = append(points, plugin.NewPoint(
			[]plugin.Tag{{Key: "scope", Value: "resolver"}, {Key: "resolver", Value: r.name}, {Key: "addresses", Value: addresses}},
			plugin.Bool("resolved", true), plugin.Float("latency_ms", latency)))
	}
	return plugin.Sample{Points: points}, nil
}

func (p *domainPlugin) Aggregate(samples []plugin.Sample) (plugin.Aggregate, error) {
	return diagnoseDomain(samples), nil
}

func (p *domainPlugin) Command(ctx context.Context, newState plugin.State) error {
	return nil
}

func (p *domainPlugin) State() *plugin.StateTracker { return p.state }

func probeDomain(ctx context.Context, server, domain string) (domainResult, error) {
	dnsResolver := &net.Resolver{
		PreferGo: true,
		Dial: func(dialCtx context.Context, network, _ string) (net.Conn, error) {
			dialer := net.Dialer{Timeout: domainProbeTimeout}
			return dialer.DialContext(dialCtx, network, server)
		},
	}
	queryCtx, cancel := context.WithTimeout(ctx, domainProbeTimeout)
	defer cancel()
	start := time.Now()
	ips, err := dnsResolver.LookupIP(queryCtx, "ip4", domain)
	if err != nil {
		return domainResult{}, err
	}
	addresses := make([]string, 0, len(ips))
	for _, ip := range ips {
		addresses = append(addresses, ip.String())
	}
	sort.Strings(addresses)
	return domainResult{addresses: addresses, latency: time.Since(start)}, nil
}

func diagnoseDomain(samples []plugin.Sample) plugin.Aggregate {
	points := plugin.LatestPoints(samples)
	total := len(points)
	resolved := 0
	counts := map[string]int{}
	for _, point := range points {
		if ok, _ := point.Bool("resolved"); !ok {
			continue
		}
		resolved++
		addresses, _ := point.Tag("addresses")
		counts[addresses]++
	}
	consensus := ""
	agreeing := 0
	for addresses, count := range counts {
		if count > agreeing || (count == agreeing && addresses < consensus) {
			consensus = addresses
			agreeing = count
		}
	}
	failed := total - resolved
	score := 0
	if total > 0 {
		score = plugin.Clamp(int(math.Round(100 * float64(agreeing) / float64(total))))
	}
	result := plugin.Aggregate{}
	switch {
	case total == 0 || resolved == 0:
		result = plugin.Diagnose(plugin.StatusDead, 0, "NO_RESOLUTION", fmt.Sprintf("no resolver returned an address for [%s]", checkDomain))
	case failed > 0:
		result = plugin.Diagnose(plugin.StatusSick, score, "PARTIAL_RESOLUTION", fmt.Sprintf("resolution failed on %d/%d resolvers", failed, total))
	case agreeing < total:
		result = plugin.Diagnose(plugin.StatusSick, score, "RECORD_MISMATCH", fmt.Sprintf("only %d/%d resolvers agree on the same address set", agreeing, total))
	default:
		result = plugin.Diagnose(plugin.StatusFit, score, "RESOLVED", fmt.Sprintf("all %d resolvers agree on [%s]", total, consensus))
	}
	result.Points = reportDomain(result.Score, consensus, agreeing, failed, points)
	return result
}

func reportDomain(score int, consensus string, agreeing, failed int, resolverPoints []plugin.Point) []plugin.Point {
	details := make([]plugin.Point, 0, len(resolverPoints))
	for _, point := range resolverPoints {
		addresses, _ := point.Tag("addresses")
		resolved, _ := point.Bool("resolved")
		fields := []plugin.Field{plugin.Bool("resolved", resolved), plugin.Bool("match", resolved && addresses == consensus)}
		if latency, ok := point.Float("latency_ms"); ok {
			fields = append(fields, plugin.Float("latency_ms", latency))
		} else {
			fields = append(fields, plugin.Null("latency_ms"))
		}
		details = append(details, plugin.NewPoint(point.Tags, fields...))
	}
	summary := plugin.NewPoint(
		[]plugin.Tag{{Key: "scope", Value: "summary"}, {Key: "domain", Value: checkDomain}, {Key: "consensus", Value: consensus}},
		plugin.Int("score", int64(score)),
		plugin.Int("resolver_count", int64(len(resolverPoints))),
		plugin.Int("agree_count", int64(agreeing)),
		plugin.Int("failed_count", int64(failed)))
	return plugin.PrependSummaryPoints(summary, details)
}

func init() {
	plugin.Register(newDomainPlugin())
}
