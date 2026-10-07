package plugin

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

	"network/internal/config"
	"network/internal/schema"
	"network/internal/scribe"

	"golang.org/x/net/icmp"
	"golang.org/x/net/ipv4"
)

const (
	internetGatewayName    = "gateway"
	internetBurstSize      = 8
	internetBurstGap       = 120 * time.Millisecond
	internetBurstTimeout   = 2500 * time.Millisecond
	internetLossFitMax     = 2.0
	internetRTTFitMax      = 100.0
	internetJitterFitMax   = 30.0
	internetTargetDownCost = 15
)

var (
	internetPublicTargets = []string{"1.1.1.1", "8.8.8.8", "9.9.9.9"}
	internetPingSequence  atomic.Uint32
)

var (
	internetTarget    = schema.Declare("internet/target", "internet reachability, one row per ping target", aggregateCadence).Entities(append([]string{internetGatewayName}, internetPublicTargets...)...)
	internetName      = internetTarget.Subject("target", "ping target, either the local gateway or a public address")
	internetReachable = internetTarget.Bool("reachable", "target answered at least one ping across the window")
	internetLoss      = internetTarget.Float("loss_pct", "%", "packet loss across the window")
	internetRTT       = internetTarget.Float("rtt_ms", "ms", "mean round trip time across the window")
	internetJitter    = internetTarget.Float("jitter_ms", "ms", "mean jitter across the window")
)

type internetReading struct {
	target  string
	gateway bool
	lossPct float64
	rttMs   float64
	jitter  float64
	hasRTT  bool
}

type internetPlugin struct {
	probe   func(ctx context.Context, ip string) (time.Duration, error)
	targets []internetPingTarget
	state   *StateTracker
}

func newInternetPlugin() *internetPlugin {
	return &internetPlugin{probe: probeInternet, targets: internetPingTargets(config.Load().UnifiHost()), state: NewStateTracker(StateOn)}
}

func (p *internetPlugin) Name() string { return "internet" }

func (p *internetPlugin) Mode() Mode { return ModeWindowed }

func (p *internetPlugin) Poll(ctx context.Context) (Sample, error) {
	padded := func(ip string) string {
		octets := net.ParseIP(ip).To4()
		if octets == nil {
			return ip
		}
		return fmt.Sprintf("%03d.%03d.%03d.%03d", octets[0], octets[1], octets[2], octets[3])
	}
	readings := make([]internetReading, len(p.targets))
	var wg sync.WaitGroup
	for i, t := range p.targets {
		wg.Go(func() {
			roundTrips := make([]float64, 0, internetBurstSize)
			sent := 0
			for j := range internetBurstSize {
				if ctx.Err() != nil {
					break
				}
				sent++
				if d, err := p.probe(ctx, t.ip); err == nil {
					roundTrips = append(roundTrips, float64(d)/float64(time.Millisecond))
				} else {
					scribe.LogDebug("internet", "probe of [%s] failed [%v]", padded(t.ip), err)
				}
				if j < internetBurstSize-1 {
					select {
					case <-ctx.Done():
					case <-time.After(internetBurstGap):
					}
				}
			}
			received := len(roundTrips)
			loss := 100.0
			if sent > 0 {
				loss = 100 * float64(sent-received) / float64(sent)
			}
			scribe.LogDebug("internet", "probed [%s] sent [%d] recv [%d] loss_pct [%v]", padded(t.ip), sent, received, loss)
			reading := internetReading{target: t.ip, gateway: t.gateway, lossPct: loss}
			if received > 0 {
				reading.rttMs, reading.jitter = readInternet(roundTrips)
				reading.hasRTT = true
			}
			readings[i] = reading
		})
	}
	wg.Wait()
	return Sample{Readings: readings}, nil
}

func (p *internetPlugin) Aggregate(samples []Sample) (Aggregate, error) {
	return diagnoseInternet(samples), nil
}

func (p *internetPlugin) Command(context.Context, State) error {
	return nil
}

func (p *internetPlugin) State() *StateTracker { return p.state }

func probeInternet(ctx context.Context, ip string) (time.Duration, error) {
	conn, err := icmp.ListenPacket("udp4", "0.0.0.0")
	if err != nil {
		return 0, err
	}
	defer conn.Close()
	deadline := time.Now().Add(internetBurstTimeout)
	if ctxDeadline, ok := ctx.Deadline(); ok && ctxDeadline.Before(deadline) {
		deadline = ctxDeadline
	}
	if err := conn.SetDeadline(deadline); err != nil {
		return 0, err
	}
	body := &icmp.Echo{ID: os.Getpid() & 0xffff, Seq: int(internetPingSequence.Add(1)) & 0xffff, Data: []byte("network")}
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

func readInternet(roundTrips []float64) (avg, jitter float64) {
	sum := 0.0
	for _, v := range roundTrips {
		sum += v
	}
	avg = sum / float64(len(roundTrips))
	variance := 0.0
	for _, v := range roundTrips {
		variance += (v - avg) * (v - avg)
	}
	return avg, math.Sqrt(variance / float64(len(roundTrips)))
}

func diagnoseInternet(samples []Sample) Aggregate {
	if len(samples) > 1 {
		newest := samples[len(samples)-1:]
		if len(latestReading[[]internetReading](newest)) > 0 {
			if current := diagnoseInternet(newest); !current.OK {
				return current
			}
		}
	}
	accumulators := map[string]*internetPingAccumulator{}
	for _, readings := range allReadings[[]internetReading](samples) {
		for _, reading := range readings {
			accumulator := accumulators[reading.target]
			if accumulator == nil {
				accumulator = &internetPingAccumulator{gateway: reading.gateway}
				accumulators[reading.target] = accumulator
			}
			accumulator.lossSum += reading.lossPct
			accumulator.polls++
			if reading.hasRTT {
				accumulator.rttSum += reading.rttMs
				accumulator.jitterSum += reading.jitter
				accumulator.replied++
			}
		}
	}
	order := make([]string, 0, len(accumulators))
	for ip := range accumulators {
		order = append(order, ip)
	}
	sort.Strings(order)
	gatewayOK := true
	var publicIPs []string
	for _, ip := range order {
		if accumulators[ip].gateway {
			gatewayOK = accumulators[ip].reachable()
		} else {
			publicIPs = append(publicIPs, ip)
		}
	}
	reachable := 0
	lossSum, rttSum, jitterSum := 0.0, 0.0, 0.0
	replied := 0
	for _, ip := range publicIPs {
		accumulator := accumulators[ip]
		lossSum += accumulator.avgLoss()
		if accumulator.reachable() {
			reachable++
		}
		if accumulator.replied > 0 {
			rttSum += accumulator.avgRTT()
			jitterSum += accumulator.avgJitter()
			replied++
		}
	}
	avgLoss, avgRTT, avgJitter := 0.0, 0.0, 0.0
	if len(publicIPs) > 0 {
		avgLoss = round(lossSum/float64(len(publicIPs)), 1)
	}
	if replied > 0 {
		avgRTT, avgJitter = round(rttSum/float64(replied), 1), round(jitterSum/float64(replied), 1)
	}
	result := Aggregate{}
	switch {
	case len(publicIPs) == 0:
		result = Diagnose(StatusDead, 0, "NO_DATA: no internet samples in window")
	case !gatewayOK:
		result = Diagnose(StatusDead, 0, "LAN_DOWN: gateway unreachable in the latest poll")
	case reachable == 0:
		result = Diagnose(StatusDead, 0, "ISP_DOWN: all internet targets unreachable in the latest poll")
	default:
		latencyPenalty := 0
		if avgRTT > internetRTTFitMax {
			latencyPenalty = min(int(math.Round((avgRTT-internetRTTFitMax)/5)), 30)
		}
		jitterPenalty := 0
		if avgJitter > internetJitterFitMax {
			jitterPenalty = min(int(math.Round((avgJitter-internetJitterFitMax)/2)), 20)
		}
		score := clamp(100 - int(math.Round(avgLoss)) - (len(publicIPs)-reachable)*internetTargetDownCost - latencyPenalty - jitterPenalty)
		switch {
		case avgLoss <= internetLossFitMax && reachable == len(publicIPs) && avgRTT <= internetRTTFitMax && avgJitter <= internetJitterFitMax:
			result = Diagnose(StatusFit, score, "UP: internet reachable within normal range")
		case avgRTT > internetRTTFitMax || avgJitter > internetJitterFitMax:
			result = Diagnose(StatusSick, score, fmt.Sprintf("HIGH_LATENCY: elevated latency with average RTT %.1fms and average jitter %.1fms", avgRTT, avgJitter))
		default:
			result = Diagnose(StatusSick, score, fmt.Sprintf("ELEVATED_LOSS: elevated loss of %.1f%% with %d of %d targets reachable", avgLoss, reachable, len(publicIPs)))
		}
	}
	result.Points = reportInternet(order, accumulators)
	return result
}

func reportInternet(order []string, accumulators map[string]*internetPingAccumulator) []schema.Point {
	points := make([]schema.Point, 0, len(order))
	for _, ip := range order {
		accumulator := accumulators[ip]
		name := ip
		if accumulator.gateway {
			name = internetGatewayName
		}
		points = append(points, internetTarget.Point(
			internetName.Of(name),
			internetReachable.Of(accumulator.reachable()),
			internetLoss.Of(round(accumulator.avgLoss(), 0)),
			internetRTT.Of(round(accumulator.avgRTT(), 1)),
			internetJitter.Of(round(accumulator.avgJitter(), 1))))
	}
	return points
}

type internetPingTarget struct {
	ip      string
	gateway bool
}

type internetPingAccumulator struct {
	gateway   bool
	polls     int
	replied   int
	lossSum   float64
	rttSum    float64
	jitterSum float64
}

func internetPingTargets(gateway string) []internetPingTarget {
	targets := make([]internetPingTarget, 0, len(internetPublicTargets)+1)
	if gateway != "" {
		targets = append(targets, internetPingTarget{ip: gateway, gateway: true})
	}
	for _, ip := range internetPublicTargets {
		targets = append(targets, internetPingTarget{ip: ip})
	}
	return targets
}

func (a *internetPingAccumulator) avgLoss() float64 { return a.lossSum / float64(a.polls) }

func (a *internetPingAccumulator) reachable() bool { return a.avgLoss() < 100 }

func (a *internetPingAccumulator) avgRTT() float64 {
	if a.replied == 0 {
		return 0
	}
	return a.rttSum / float64(a.replied)
}

func (a *internetPingAccumulator) avgJitter() float64 {
	if a.replied == 0 {
		return 0
	}
	return a.jitterSum / float64(a.replied)
}

func init() {
	register(newInternetPlugin())
}
