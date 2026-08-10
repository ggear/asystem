package plugins

import (
	"context"
	"fmt"
	"math"
	"net"
	"sort"
	"strings"
	"time"

	"network/internal/plugin"
	"network/internal/schema"
	"network/internal/scribe"
)

const (
	checkDomain        = "home.janeandgraham.com"
	domainProbeTimeout = 5 * time.Second
)

type resolver struct {
	name    string
	address string
}

var domainResolvers = []resolver{
	{name: "cloudflare", address: "1.1.1.1:53"},
	{name: "google", address: "8.8.8.8:53"},
	{name: "quad9", address: "9.9.9.9:53"},
	{name: "opendns", address: "208.67.222.222:53"},
	{name: "adguard", address: "94.140.14.14:53"},
}

var (
	domainResolver     = schema.Declare("domain/resolver", "public DNS resolution of the monitored domain, one row per public resolver", aggregateCadence).Entities(resolverNames()...)
	domainResolverName = domainResolver.Subject("resolver", "public DNS resolver queried")
	domainOK           = domainResolver.Bool("ok", "resolver agreed with the consensus address set")
	domainResolved     = domainResolver.Bool("resolved", "resolver returned an address")
	domainLatencyMs    = domainResolver.Float("latency_ms", "ms", "time taken to resolve")
)

type domainReading struct {
	resolver  string
	addresses string
	resolved  bool
	latencyMs float64
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
	readings := make([]domainReading, 0, len(domainResolvers))
	for _, r := range domainResolvers {
		result, err := p.probe(ctx, r.address, checkDomain)
		if err != nil || len(result.addresses) == 0 {
			scribe.LogDebug("domain", "probe of resolver [%s] server [%s] failed [%v]", r.name, r.address, err)
			readings = append(readings, domainReading{resolver: r.name})
			continue
		}
		addresses := strings.Join(result.addresses, ",")
		latency := plugin.Round(float64(result.latency)/float64(time.Millisecond), 1)
		scribe.LogDebug("domain", "probed resolver [%s] server [%s] addresses [%s] latency_ms [%v]", r.name, r.address, addresses, latency)
		readings = append(readings, domainReading{
			resolver: r.name, addresses: addresses, resolved: true, latencyMs: latency})
	}
	return plugin.Sample{Readings: readings}, nil
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
	readings := plugin.Latest[[]domainReading](samples)
	total := len(readings)
	resolved := 0
	counts := map[string]int{}
	for _, reading := range readings {
		if !reading.resolved {
			continue
		}
		resolved++
		counts[reading.addresses]++
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
		result = plugin.Diagnose(plugin.StatusDead, 0, fmt.Sprintf("NO_RESOLUTION: no resolver returned an address for [%s]", checkDomain))
	case failed > 0:
		result = plugin.Diagnose(plugin.StatusSick, score, fmt.Sprintf("PARTIAL_RESOLUTION: resolution failed on [%d] of [%d] resolvers", failed, total))
	case agreeing < total:
		result = plugin.Diagnose(plugin.StatusSick, score, fmt.Sprintf("RECORD_MISMATCH: only [%d] of [%d] resolvers agree on the same address set", agreeing, total))
	default:
		result = plugin.Diagnose(plugin.StatusFit, score, fmt.Sprintf("RESOLVED: all [%d] resolvers agree on [%s]", total, consensus))
	}
	result.Points = reportDomain(readings, consensus)
	return result
}

func reportDomain(readings []domainReading, consensus string) []schema.Point {
	points := make([]schema.Point, 0, len(readings))
	for _, reading := range readings {
		points = append(points, domainResolver.Point(
			domainResolverName.Of(reading.resolver),
			domainOK.Of(reading.resolved && reading.addresses == consensus),
			domainResolved.Of(reading.resolved),
			domainLatencyMs.Of(plugin.Round(reading.latencyMs, 1))))
	}
	return points
}

func resolverNames() []string {
	names := make([]string, 0, len(domainResolvers))
	for _, r := range domainResolvers {
		names = append(names, r.name)
	}
	return names
}

func init() {
	plugin.Register(newDomainPlugin())
}
