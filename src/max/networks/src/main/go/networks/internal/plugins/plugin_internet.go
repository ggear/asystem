package plugins

import (
	"context"
	"fmt"
	"math"
	"net"
	"os"
	"sort"
	"sync"
	"sync/atomic"
	"time"

	"networks/internal/config"
	"networks/internal/plugin"
	"networks/internal/scribe"

	"golang.org/x/net/icmp"
	"golang.org/x/net/ipv4"
)

const (
	gatewayScope      = "gateway"
	burstSize         = 8
	burstGap          = 120 * time.Millisecond
	burstTimeout      = 2500 * time.Millisecond
	lossFitMaxPercent = 2.0
	rttFitMaxMs       = 100.0
	jitterFitMaxMs    = 30.0
	targetDownCost    = 15
)

type target struct {
	ip    string
	scope string
}

var publicTargets = []target{
	{"1.1.1.1", "target"},
	{"8.8.8.8", "target"},
	{"9.9.9.9", "target"},
}

type internetPlugin struct {
	probe   func(ctx context.Context, ip string) (time.Duration, error)
	targets []target
	state   *plugin.StateTracker
}

func newInternetPlugin() *internetPlugin {
	return &internetPlugin{probe: probeInternet, targets: buildTargets(config.Load().UnifiHost()), state: plugin.NewStateTracker(plugin.StateOn)}
}

func buildTargets(gateway string) []target {
	targets := make([]target, 0, len(publicTargets)+1)
	if gateway != "" {
		targets = append(targets, target{ip: gateway, scope: gatewayScope})
	}
	return append(targets, publicTargets...)
}

func (p *internetPlugin) Name() string { return "internet" }

func (p *internetPlugin) Mode() plugin.Mode { return plugin.ModeWindowed }

func (p *internetPlugin) Poll(ctx context.Context) (plugin.Sample, error) {
	points := make([]plugin.Point, len(p.targets))
	var wg sync.WaitGroup
	for i, t := range p.targets {
		wg.Add(1)
		go func(i int, t target) {
			defer wg.Done()
			roundTrips := make([]float64, 0, burstSize)
			sent := 0
			for j := 0; j < burstSize; j++ {
				if ctx.Err() != nil {
					break
				}
				sent++
				if d, err := p.probe(ctx, t.ip); err == nil {
					roundTrips = append(roundTrips, float64(d)/float64(time.Millisecond))
				} else {
					scribe.LogDebug("internet", "probe of scope [%s] target [%s] failed [%v]", t.scope, t.ip, err)
				}
				if j < burstSize-1 {
					select {
					case <-ctx.Done():
					case <-time.After(burstGap):
					}
				}
			}
			received := len(roundTrips)
			loss := 100.0
			if sent > 0 {
				loss = 100 * float64(sent-received) / float64(sent)
			}
			scribe.LogDebug("internet", "probed scope [%s] target [%s] sent [%d] recv [%d] loss_pct [%v]", t.scope, t.ip, sent, received, loss)
			tags := []plugin.Tag{{Key: "scope", Value: t.scope}, {Key: "target", Value: t.ip}}
			fields := []plugin.Field{plugin.Int("sent", int64(sent)), plugin.Int("recv", int64(received)), plugin.Float("loss_pct", loss)}
			if received > 0 {
				avg, minRTT, maxRTT, jitter := readInternet(roundTrips)
				fields = append(fields, plugin.Float("avg_rtt_ms", avg), plugin.Float("min_rtt_ms", minRTT), plugin.Float("max_rtt_ms", maxRTT), plugin.Float("jitter_ms", jitter))
			} else {
				fields = append(fields, plugin.Null("avg_rtt_ms"), plugin.Null("min_rtt_ms"), plugin.Null("max_rtt_ms"), plugin.Null("jitter_ms"))
			}
			points[i] = plugin.NewPoint(tags, fields...)
		}(i, t)
	}
	wg.Wait()
	return plugin.Sample{Points: points}, nil
}

func (p *internetPlugin) Aggregate(samples []plugin.Sample) (plugin.Aggregate, error) {
	return diagnoseInternet(samples), nil
}

func (p *internetPlugin) Command(ctx context.Context, newState plugin.State) error {
	return nil
}

func (p *internetPlugin) State() *plugin.StateTracker { return p.state }

var pingSequence atomic.Uint32

func probeInternet(ctx context.Context, ip string) (time.Duration, error) {
	conn, err := icmp.ListenPacket("udp4", "0.0.0.0")
	if err != nil {
		return 0, err
	}
	defer conn.Close()
	deadline := time.Now().Add(burstTimeout)
	if ctxDeadline, ok := ctx.Deadline(); ok && ctxDeadline.Before(deadline) {
		deadline = ctxDeadline
	}
	if err := conn.SetDeadline(deadline); err != nil {
		return 0, err
	}
	body := &icmp.Echo{ID: os.Getpid() & 0xffff, Seq: int(pingSequence.Add(1)) & 0xffff, Data: []byte("networks")}
	msg := icmp.Message{Type: ipv4.ICMPTypeEcho, Code: 0, Body: body}
	request, err := msg.Marshal(nil)
	if err != nil {
		return 0, err
	}
	start := time.Now()
	if _, err := conn.WriteTo(request, &net.UDPAddr{IP: net.ParseIP(ip)}); err != nil {
		return 0, err
	}
	replyBuffer := make([]byte, 1500)
	for {
		n, _, err := conn.ReadFrom(replyBuffer)
		if err != nil {
			return 0, err
		}
		parsedMessage, err := icmp.ParseMessage(1, replyBuffer[:n])
		if err != nil {
			return 0, err
		}
		if parsedMessage.Type == ipv4.ICMPTypeEchoReply {
			return time.Since(start), nil
		}
	}
}

func readInternet(roundTrips []float64) (avg, minRTT, maxRTT, jitter float64) {
	minRTT = roundTrips[0]
	maxRTT = roundTrips[0]
	sum := 0.0
	for _, v := range roundTrips {
		sum += v
		if v < minRTT {
			minRTT = v
		}
		if v > maxRTT {
			maxRTT = v
		}
	}
	avg = sum / float64(len(roundTrips))
	variance := 0.0
	for _, v := range roundTrips {
		variance += (v - avg) * (v - avg)
	}
	jitter = math.Sqrt(variance / float64(len(roundTrips)))
	return avg, minRTT, maxRTT, jitter
}

func diagnoseInternet(samples []plugin.Sample) plugin.Aggregate {
	accumulators := map[string]*targetAccumulator{}
	for _, message := range samples {
		for _, point := range message.Points {
			ip, _ := point.Tag("target")
			if ip == "" {
				continue
			}
			accumulator := accumulators[ip]
			if accumulator == nil {
				accumulator = &targetAccumulator{}
				accumulators[ip] = accumulator
			}
			if scope, ok := point.Tag("scope"); ok {
				accumulator.scope = scope
			}
			if loss, ok := point.Float("loss_pct"); ok {
				accumulator.lossSum += loss
				accumulator.lossCount++
			}
			if rtt, ok := point.Float("avg_rtt_ms"); ok {
				accumulator.rttSum += rtt
				accumulator.rttCount++
			}
			if jitter, ok := point.Float("jitter_ms"); ok {
				accumulator.jitterSum += jitter
				accumulator.jitterCount++
			}
		}
	}
	order := make([]string, 0, len(accumulators))
	for ip := range accumulators {
		order = append(order, ip)
	}
	sort.Strings(order)
	var gateway *targetAccumulator
	publicIPs := make([]string, 0, len(order))
	for _, ip := range order {
		if accumulators[ip].scope == gatewayScope {
			gateway = accumulators[ip]
		} else {
			publicIPs = append(publicIPs, ip)
		}
	}
	gatewayOK := gateway != nil && gateway.lossCount > 0 && gateway.avgLoss() < 100
	reachable := 0
	lossSum := 0.0
	rttSum, rttCount := 0.0, 0
	jitterSum, jitterCount := 0.0, 0
	for _, ip := range publicIPs {
		accumulator := accumulators[ip]
		lossSum += accumulator.avgLoss()
		if accumulator.avgLoss() < 100 {
			reachable++
		}
		if accumulator.rttCount > 0 {
			rttSum += accumulator.avgRTT()
			rttCount++
		}
		if accumulator.jitterCount > 0 {
			jitterSum += accumulator.avgJitter()
			jitterCount++
		}
	}
	avgLoss := 0.0
	if len(publicIPs) > 0 {
		avgLoss = lossSum / float64(len(publicIPs))
	}
	avgRTT := 0.0
	if rttCount > 0 {
		avgRTT = rttSum / float64(rttCount)
	}
	avgJitter := 0.0
	if jitterCount > 0 {
		avgJitter = jitterSum / float64(jitterCount)
	}
	result := plugin.Aggregate{}
	switch {
	case len(publicIPs) == 0:
		result = plugin.Diagnose(plugin.StatusDead, 0, "NO_DATA: no internet samples in window")
	case !gatewayOK:
		result = plugin.Diagnose(plugin.StatusDead, 0, "LAN_DOWN: gateway unreachable across window")
	case reachable == 0:
		result = plugin.Diagnose(plugin.StatusDead, 0, "ISP_DOWN: all internet targets unreachable across window")
	default:
		latencyPenalty := 0
		if avgRTT > rttFitMaxMs {
			latencyPenalty = int(math.Round((avgRTT - rttFitMaxMs) / 5))
			if latencyPenalty > 30 {
				latencyPenalty = 30
			}
		}
		jitterPenalty := 0
		if avgJitter > jitterFitMaxMs {
			jitterPenalty = int(math.Round((avgJitter - jitterFitMaxMs) / 2))
			if jitterPenalty > 20 {
				jitterPenalty = 20
			}
		}
		score := plugin.Clamp(100 - int(math.Round(avgLoss)) - (len(publicIPs)-reachable)*targetDownCost - latencyPenalty - jitterPenalty)
		switch {
		case avgLoss <= lossFitMaxPercent && reachable == len(publicIPs) && avgRTT <= rttFitMaxMs && avgJitter <= jitterFitMaxMs:
			result = plugin.Diagnose(plugin.StatusFit, score, "UP: internet reachable within normal range")
		case avgRTT > rttFitMaxMs || avgJitter > jitterFitMaxMs:
			result = plugin.Diagnose(plugin.StatusSick, score, fmt.Sprintf("HIGH_LATENCY: elevated latency with average RTT [%.1f]ms and average jitter [%.1f]ms", avgRTT, avgJitter))
		default:
			result = plugin.Diagnose(plugin.StatusSick, score, fmt.Sprintf("ELEVATED_LOSS: elevated loss of [%.1f%%] with [%d] of [%d] targets reachable", avgLoss, reachable, len(publicIPs)))
		}
	}
	result.Points = reportInternet(result.Score, avgLoss, avgRTT, avgJitter, gatewayOK, publicIPs, accumulators)
	return result
}

func reportInternet(score int, avgLoss, avgRTT, avgJitter float64, gatewayOK bool, publicIPs []string, accumulators map[string]*targetAccumulator) []plugin.Point {
	summary := plugin.NewPoint([]plugin.Tag{{Key: "scope", Value: "summary"}},
		plugin.Int("score", int64(score)),
		plugin.Float("avg_loss_pct", plugin.Round(avgLoss, 1)),
		plugin.Float("avg_rtt_ms", plugin.Round(avgRTT, 1)),
		plugin.Float("avg_jitter_ms", plugin.Round(avgJitter, 1)),
		plugin.Bool("gateway_ok", gatewayOK))
	points := make([]plugin.Point, 0, len(publicIPs)+1)
	points = append(points, summary)
	for _, ip := range publicIPs {
		accumulator := accumulators[ip]
		fields := []plugin.Field{plugin.Bool("ok", accumulator.avgLoss() < 100), plugin.Float("loss_pct", plugin.Round(accumulator.avgLoss(), 1))}
		if accumulator.rttCount > 0 {
			fields = append(fields, plugin.Float("avg_rtt_ms", plugin.Round(accumulator.avgRTT(), 1)))
		} else {
			fields = append(fields, plugin.Null("avg_rtt_ms"))
		}
		points = append(points, plugin.NewPoint([]plugin.Tag{{Key: "scope", Value: "target"}, {Key: "target", Value: ip}}, fields...))
	}
	return points
}

type targetAccumulator struct {
	scope       string
	lossSum     float64
	lossCount   int
	rttSum      float64
	rttCount    int
	jitterSum   float64
	jitterCount int
}

func (a *targetAccumulator) avgLoss() float64 {
	if a.lossCount == 0 {
		return 100
	}
	return a.lossSum / float64(a.lossCount)
}

func (a *targetAccumulator) avgRTT() float64 {
	if a.rttCount == 0 {
		return 0
	}
	return a.rttSum / float64(a.rttCount)
}

func (a *targetAccumulator) avgJitter() float64 {
	if a.jitterCount == 0 {
		return 0
	}
	return a.jitterSum / float64(a.jitterCount)
}

func init() {
	plugin.Register(newInternetPlugin())
}
