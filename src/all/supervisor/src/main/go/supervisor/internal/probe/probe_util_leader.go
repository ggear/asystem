package probe

import (
	"context"
	"encoding/json"
	"fmt"
	"slices"
	"strings"
	"sync"
	"sync/atomic"
	"time"

	"supervisor/internal/config"
	"supervisor/internal/metric"
	"supervisor/internal/scribe"

	mqtt "github.com/eclipse/paho.mqtt.golang"
)

// Leading reports whether this process currently holds the election that owns duty, and the epoch it was won at.
// Every duty today belongs to the one cluster election, so every singleton moves together; a duty needing a
// different eligible set would start a second election under its own name and topic root.
//
// The election runs over retained MQTT topics, which offer no compare-and-set, so correctness rests on every
// candidate computing the same deterministic answer from the same view rather than on an atomic claim:
//  1. Every host eligible by its own config, whose poll loop is alive, holds a session whose last will empties its
//     retained candidacy, and renews that candidacy every refresh; any other host withdraws it.
//  2. Freshness is judged by when a renewal arrived on the receiver's own monotonic clock, never by the sender's
//     timestamp, so no clock skew or clock step between hosts can make a live candidate read stale.
//  3. The leader is the host holding a fresh lease while it is itself a fresh candidate, eligible or not by the
//     receiver's config, otherwise the lowest-named fresh eligible candidate, so an incumbent is never displaced
//     by a host joining, restarting, or rolling out a config that no longer names it.
//  4. A host that is elected must see itself elected continuously for the settle before it claims, which is
//     longer than a deposed leader can go on believing it leads, so two holders never overlap.
//  5. A holder stops leading the moment its own renewals or lease writes go unacknowledged for the ack window,
//     checked again on every call here, and a claim acknowledged across a reattach is discarded.
//  6. A candidate must hear its own renewals arrive live before it claims, since a retained replay proves nothing
//     about delivery: one acknowledged but unheard for the ttl is on a session the broker no longer delivers to,
//     whose view diverges from its peers', so it yields and redials a fresh session before retiring the old one.
//
// Notes:
//   - A vernemq release flushes every retained topic, which drops the session of every candidate, so all of them
//     yield, reattach, and settle again; the lease is gone, so the lowest-named host wins the fresh election.
//   - A supervisor release never sweeps these topics, which sit under the cluster host rather than any one host,
//     and a graceful stop resigns explicitly, so the next holder takes over within the settle.
//   - Nothing here fences the work itself: a caller whose side effect must not repeat checks Leading again
//     immediately before acting, and stamps the epoch on anything it publishes.
func Leading(duty string) (bool, int64) {
	leaderCampaignsMu.Lock()
	campaign := leaderCampaigns[duty]
	leaderCampaignsMu.Unlock()
	if campaign == nil {
		return false, 0
	}
	return campaign.holding(time.Now())
}

func Resign() {
	leaderCampaignsMu.Lock()
	campaigns := make([]*leaderCampaign, 0, len(leaderCampaigns))
	for _, campaign := range leaderCampaigns {
		if !slices.Contains(campaigns, campaign) {
			campaigns = append(campaigns, campaign)
		}
	}
	clear(leaderCampaigns)
	leaderCampaignsMu.Unlock()
	var resigning sync.WaitGroup
	for _, campaign := range campaigns {
		resigning.Go(campaign.resign)
	}
	resigning.Wait()
}

type leaderElection struct {
	name     string
	root     string
	eligible func() []string
	presence string
	alive    func() bool
}

func (e leaderElection) leaseTopic() string {
	return e.root + "/lease"
}

func (e leaderElection) candidateTopic(host string) string {
	return e.root + "/candidate/" + host
}

type leadingProbe interface {
	probe
	duties() []string
}

func clusterElection(configPath string) leaderElection {
	return leaderElection{
		name:     metric.LeaderElection,
		root:     metric.TopicLeaderRoot,
		eligible: func() []string { return config.Load(configPath).HostsByFormFactor(config.FormFactorServer) },
		presence: metric.TopicAllStatus,
		alive:    pollAlive,
	}
}

type leaderLease struct {
	Host      string `json:"host"`
	Epoch     int64  `json:"epoch"`
	ClaimedTS string `json:"claimed_ts"`
	RenewedTS string `json:"renewed_ts"`
}

type leaderCandidacy struct {
	Host      string `json:"host"`
	RenewedTS string `json:"renewed_ts"`
}

type leaderTiming struct {
	refresh        time.Duration
	publishTimeout time.Duration
	ackWindow      time.Duration
	keepAlive      time.Duration
	pingTimeout    time.Duration
	ttl            time.Duration
	settle         time.Duration
}

type leaderCampaign struct {
	election     leaderElection
	host         string
	timing       leaderTiming
	client       mqtt.Client
	retired      mqtt.Client
	configPath   string
	present      mqtt.Client
	presenceMu   sync.Mutex
	attaching    sync.Mutex
	ticking      sync.Mutex
	resigned     sync.Once
	stopping     atomic.Bool
	mutex        sync.Mutex
	attached     bool
	attachedAt   time.Time
	generation   uint64
	standing     bool
	lastAck      time.Time
	lastLease    time.Time
	heardSelf    time.Time
	ackSince     time.Time
	redials      int
	leaseSeen    time.Time
	leaseLive    time.Time
	candidates   map[string]time.Time
	skewed       map[string]bool
	lease        leaderLease
	leaseArrived time.Time
	electedFrom  time.Time
	leading      bool
	vacated      bool
	holdingSeen  bool
	renewFailing bool
	observedHost string
	observedFrom int64
	staleHosts   map[string]bool
	ticks        int
	withdrawnAt  map[string]time.Time
	resignedBy   string
	resignedAt   time.Time
	orphanedBy   string
	orphanTicks  int
	electedPeer  string
	electedAt    time.Time
	epoch        int64
	claimed      time.Time
}

func leaderCampaignStart(ctx context.Context, configPath, host string, election leaderElection, duties []string) {
	leaderCampaignsMu.Lock()
	defer leaderCampaignsMu.Unlock()
	if len(duties) == 0 || leaderCampaigns[duties[0]] != nil {
		return
	}
	startedAt := time.Now()
	campaign, err := newLeaderCampaign(configPath, host, election, leaderTimingProduction)
	if err != nil {
		scribe.Log(scribe.SourceProbeLeader, scribe.SubjectHost(host), scribe.ActionStart).Warnf("faulting", startedAt, "[%s] election not started with [%v], this host never leads it", election.name, err)
		return
	}
	for _, duty := range duties {
		leaderCampaigns[duty] = campaign
	}
	scribe.Log(scribe.SourceProbeLeader, scribe.SubjectHost(host), scribe.ActionStart).Infof("schedule", startedAt, "[%s] election joined for duties [%s], eligible [%s]",
		election.name, strings.Join(duties, ","), strings.Join(election.eligible(), ","))
	go campaign.run(ctx)
}

func newLeaderCampaign(configPath, host string, election leaderElection, timing leaderTiming) (*leaderCampaign, error) {
	campaign := newLeaderCampaignState(configPath, host, election, timing)
	client, err := campaign.dial()
	if err != nil {
		return nil, err
	}
	campaign.client = client
	client.Connect()
	return campaign, nil
}

func newLeaderCampaignState(configPath, host string, election leaderElection, timing leaderTiming) *leaderCampaign {
	return &leaderCampaign{election: election, host: host, configPath: configPath, timing: timing, candidates: map[string]time.Time{}, skewed: map[string]bool{}, staleHosts: map[string]bool{}, withdrawnAt: map[string]time.Time{}}
}

func (c *leaderCampaign) sessionOptions(role string) (*mqtt.ClientOptions, error) {
	options, err := brokerOptions(c.configPath, role+"-"+c.election.name)
	if err != nil {
		return nil, err
	}
	return options.SetAutoReconnect(true).SetMaxReconnectInterval(brokerReconnectCap).
		SetConnectRetry(true).SetConnectRetryInterval(c.timing.refresh).
		SetKeepAlive(c.timing.keepAlive).SetPingTimeout(c.timing.pingTimeout), nil
}

func (c *leaderCampaign) dial() (mqtt.Client, error) {
	options, err := c.sessionOptions("leader")
	if err != nil {
		return nil, err
	}
	options.SetWill(c.election.candidateTopic(c.host), "", 1, true).
		SetOnConnectHandler(func(client mqtt.Client) { c.attach(client) }).
		SetConnectionLostHandler(func(client mqtt.Client, lost error) {
			if c.session() == client {
				c.detach(fmt.Sprintf("connection lost with [%v]", lost))
			}
		})
	return mqtt.NewClient(options), nil
}

func (c *leaderCampaign) session() mqtt.Client {
	c.mutex.Lock()
	defer c.mutex.Unlock()
	return c.client
}

func (c *leaderCampaign) run(ctx context.Context) {
	ticker := time.NewTicker(c.timing.refresh)
	defer ticker.Stop()
	for {
		select {
		case <-ctx.Done():
			c.resign()
			return
		case <-ticker.C:
			if ctx.Err() != nil {
				continue
			}
			c.tick(time.Now())
		}
	}
}

func (c *leaderCampaign) tick(now time.Time) {
	c.ticking.Lock()
	defer c.ticking.Unlock()
	if c.stopping.Load() {
		return
	}
	if !c.client.IsConnectionOpen() {
		c.detach("session is not open")
		return
	}
	c.mutex.Lock()
	attached := c.attached
	c.mutex.Unlock()
	if !attached {
		c.attach(c.client)
		return
	}
	if reason, faulted := c.unfit(); reason != "" {
		c.withdrawCandidacy(now, reason, faulted, false)
	} else {
		c.renew()
	}
	c.mutex.Lock()
	silent := sinceLatest(now, c.heardSelf, c.attachedAt, c.ackSince)
	deaf := c.standing && now.Sub(c.lastAck) <= c.timing.ackWindow && silent > c.timing.ttl
	if !deaf && c.heardSelf.After(c.attachedAt) {
		c.redials = 0
	}
	c.mutex.Unlock()
	if deaf {
		client, err := c.dial()
		if err != nil {
			scribe.Log(scribe.SourceProbeLeader, scribe.SubjectHost(c.host), scribe.ActionConnect).Warnf("faulting", now, "[%s] election session deaf for [%s] s, redial failed with [%v]", c.election.name, elapsedSeconds(silent), err)
			return
		}
		c.mutex.Lock()
		if c.stopping.Load() {
			c.mutex.Unlock()
			return
		}
		c.redials++
		redials := c.redials
		c.retired, c.client = c.client, client
		c.mutex.Unlock()
		logger := scribe.Log(scribe.SourceProbeLeader, scribe.SubjectHost(c.host), scribe.ActionConnect)
		if redials == 1 || redials%leaderRedialRestate == 0 {
			logger.Warnf("faulting", now, "[%s] election session deaf for [%s] s, renewals acknowledged but none delivered back, redialling a fresh session, attempt [%d]", c.election.name, elapsedSeconds(silent), redials)
		} else {
			logger.Debugf("faulting", now, "[%s] election session deaf for [%s] s, renewals acknowledged but none delivered back, redialling a fresh session, attempt [%d]", c.election.name, elapsedSeconds(silent), redials)
		}
		c.detach("its session stopped delivering")
		client.Connect()
		return
	}
	c.evaluate(now)
	if c.stopping.Load() {
		return
	}
	c.census(now)
	if held, _ := c.holding(time.Now()); held {
		c.appear()
	} else {
		c.vanish("this host no longer holds the election")
		c.vacate(now)
	}
}

func (c *leaderCampaign) census(now time.Time) {
	c.mutex.Lock()
	lapse := c.lapse(now)
	held, wasHeld := lapse == "", c.holdingSeen
	c.holdingSeen = held
	c.ticks++
	report := c.ticks%leaderCensusTicks == 0
	var standing []string
	for host, arrived := range c.candidates {
		age := now.Sub(arrived)
		stale := age > c.timing.ttl
		if stale && !c.staleHosts[host] {
			scribe.Log(scribe.SourceProbeLeader, scribe.SubjectHost(host), scribe.ActionCensus).Infof("observed", arrived, "[%s] election candidacy unheard for [%s] s, counted stale", c.election.name, elapsedSeconds(age))
		}
		c.staleHosts[host] = stale
		if report {
			standing = append(standing, fmt.Sprintf("%s=%s", host, age.Round(time.Second)))
		}
	}
	elected := ""
	if c.attached {
		elected = leaderElected(c.election.eligible(), c.candidates, c.lease, c.leaseArrived, now, c.timing.ttl)
	}
	if elected != c.electedPeer {
		c.electedPeer, c.electedAt = elected, now
	}
	unleased := sinceLatest(now, c.leaseSeen, c.attachedAt, c.electedAt)
	liveLease := c.lease.Host != "" && now.Sub(c.leaseLive) <= c.timing.ttl
	wasOrphaned, orphan := c.orphanedBy, c.orphanedBy
	if c.attached {
		switch {
		case liveLease || elected == "" || elected == c.host || (orphan != "" && orphan != elected):
			orphan = ""
		case unleased > c.timing.settle+2*c.timing.ttl:
			orphan = elected
		}
	}
	c.orphanedBy = orphan
	restate := false
	if orphan != "" && orphan == wasOrphaned {
		c.orphanTicks++
		restate = c.orphanTicks%leaderOrphanTicks == 0
	} else {
		c.orphanTicks = 0
	}
	leaseHost, leaseAge := leaderNamed(c.lease.Host), now.Sub(c.leaseArrived).Round(time.Second)
	settling := time.Duration(0)
	if !c.electedFrom.IsZero() {
		settling = now.Sub(c.electedFrom).Round(time.Second)
	}
	attached, standingSelf, epoch, believed := c.attached, c.standing, c.epoch, c.leading
	c.mutex.Unlock()
	switch {
	case orphan != "" && (orphan != wasOrphaned || restate):
		scribe.Log(scribe.SourceProbeLeader, scribe.SubjectHost(c.host), scribe.ActionCensus).Warnf("faulting", now,
			"[%s] election elects [%s] but no lease has arrived for [%s] s, its duties are unowned", c.election.name, orphan, elapsedSeconds(unleased))
	case orphan == "" && wasOrphaned != "" && liveLease:
		scribe.Log(scribe.SourceProbeLeader, scribe.SubjectHost(c.host), scribe.ActionCensus).Infof("restored", now,
			"[%s] election lease held by [%s] again, [%s] no longer elected without one", c.election.name, leaseHost, wasOrphaned)
	case orphan == "" && wasOrphaned != "":
		scribe.Log(scribe.SourceProbeLeader, scribe.SubjectHost(c.host), scribe.ActionCensus).Infof("observed", now,
			"[%s] election no longer elects [%s], electing [%s] instead", c.election.name, wasOrphaned, leaderNamed(elected))
	}
	if wasHeld && !held && believed {
		scribe.Log(scribe.SourceProbeLeader, scribe.SubjectHost(c.host), scribe.ActionStop).Warnf("released", now, "[%s] leadership at epoch [%d] lapsed, %s", c.election.name, epoch, lapse)
	}
	if report {
		slices.Sort(standing)
		scribe.Log(scribe.SourceProbeLeader, scribe.SubjectHost(c.host), scribe.ActionCensus).Debugf("reported", now, "[%s] election, holding [%v], attached [%v], standing [%v], settling [%s] s, lease [%s] aged [%s] s, candidates [%s]",
			c.election.name, held, attached, standingSelf, elapsedSeconds(settling), leaseHost, elapsedSeconds(leaseAge), strings.Join(standing, ","))
	}
}

func (c *leaderCampaign) unfit() (string, bool) {
	if !slices.Contains(c.election.eligible(), c.host) {
		return "this host is not eligible by its own config", false
	}
	if c.election.alive != nil && !c.election.alive() {
		return "this host's poll loop has stalled", true
	}
	return "", false
}

func (c *leaderCampaign) attach(client mqtt.Client) {
	if c.stopping.Load() || !c.attaching.TryLock() {
		return
	}
	defer c.attaching.Unlock()
	if c.session() != client {
		return
	}
	attachStart := time.Now()
	c.detach("reattaching")
	c.mutex.Lock()
	generation := c.generation
	c.mutex.Unlock()
	filters := map[string]byte{
		c.election.leaseTopic():        1,
		c.election.candidateTopic("+"): 1,
	}
	token := client.SubscribeMultiple(filters, c.observe)
	if !token.WaitTimeout(c.timing.publishTimeout) || token.Error() != nil {
		scribe.Log(scribe.SourceProbeLeader, scribe.SubjectHost(c.host), scribe.ActionSubscribe).Warnf("faulting", attachStart, "[%s] election subscribe failed with [%v], retrying", c.election.name, token.Error())
		return
	}
	if granted, ok := token.(*mqtt.SubscribeToken); ok {
		for filter, code := range granted.Result() {
			if code > brokerQosMax {
				scribe.Log(scribe.SourceProbeLeader, scribe.SubjectHost(c.host), scribe.ActionSubscribe).Warnf("faulting", attachStart, "[%s] election subscribe refused [%s] with code [%d], retrying", c.election.name, filter, code)
				return
			}
		}
	}
	if c.stopping.Load() {
		return
	}
	if reason, faulted := c.unfit(); reason != "" {
		c.withdrawCandidacy(attachStart, reason, faulted, true)
	} else if !c.renew() {
		return
	}
	c.mutex.Lock()
	if c.client != client || c.generation != generation {
		c.mutex.Unlock()
		return
	}
	c.attached = true
	c.attachedAt = attachStart
	c.generation++
	retired := c.retired
	c.retired = nil
	c.mutex.Unlock()
	if retired != nil {
		retired.Disconnect(250)
	}
	scribe.Log(scribe.SourceProbeLeader, scribe.SubjectHost(c.host), scribe.ActionSubscribe).Infof("attached", attachStart, "[%s] election, settling for [%s] before any claim", c.election.name, c.timing.settle)
}

func (c *leaderCampaign) detach(reason string) {
	detachStart := time.Now()
	c.mutex.Lock()
	wasLeading := c.leading
	c.attached = false
	c.generation++
	c.leading = false
	c.vacated = false
	c.electedFrom = time.Time{}
	c.candidates = map[string]time.Time{}
	c.lease = leaderLease{}
	c.leaseArrived = time.Time{}
	c.resignedBy = ""
	c.withdrawnAt = map[string]time.Time{}
	c.mutex.Unlock()
	if wasLeading {
		scribe.Log(scribe.SourceProbeLeader, scribe.SubjectHost(c.host), scribe.ActionDisconnect).Warnf("released", detachStart, "[%s] leadership yielded, %s", c.election.name, reason)
	}
	c.vanish(reason)
}

func (c *leaderCampaign) appear() {
	if c.election.presence == "" || c.stopping.Load() {
		return
	}
	c.presenceMu.Lock()
	defer c.presenceMu.Unlock()
	if held, _ := c.holding(time.Now()); !held {
		return
	}
	if c.present != nil {
		if c.present.IsConnectionOpen() {
			c.present.Publish(c.election.presence, 1, true, []byte(metric.AvailabilityOnline))
		}
		return
	}
	appearStart := time.Now()
	options, err := c.sessionOptions("presence")
	if err != nil {
		scribe.Log(scribe.SourceProbeLeader, scribe.SubjectHost(c.host), scribe.ActionConnect).Warnf("faulting", appearStart, "[%s] presence not published with [%v]", c.election.presence, err)
		return
	}
	topic := c.election.presence
	options.SetWill(topic, metric.AvailabilityOffline, 1, true).
		SetOnConnectHandler(func(client mqtt.Client) { client.Publish(topic, 1, true, []byte(metric.AvailabilityOnline)) })
	c.present = mqtt.NewClient(options)
	c.present.Connect()
	scribe.Log(scribe.SourceProbeLeader, scribe.SubjectHost(c.host), scribe.ActionPublish).Infof("assigned", appearStart, "[%s] presence [%s] held by this host for election [%s]", topic, metric.AvailabilityOnline, c.election.name)
}

func (c *leaderCampaign) vanish(reason string) {
	c.presenceMu.Lock()
	present := c.present
	c.present = nil
	c.presenceMu.Unlock()
	if present == nil {
		return
	}
	vanishStart := time.Now()
	cleared := false
	if present.IsConnectionOpen() {
		token := present.Publish(c.election.presence, 1, true, []byte(metric.AvailabilityOffline))
		cleared = token.WaitTimeout(min(c.timing.publishTimeout, leaderResignBudget)) && token.Error() == nil
	}
	present.Disconnect(250)
	scribe.Log(scribe.SourceProbeLeader, scribe.SubjectHost(c.host), scribe.ActionPublish).Infof("released", vanishStart, "[%s] presence [%s] acknowledged [%v], %s", c.election.presence, metric.AvailabilityOffline, cleared, reason)
}

func (c *leaderCampaign) vacate(now time.Time) {
	if c.election.presence == "" {
		return
	}
	c.mutex.Lock()
	vacant := c.attached && !c.vacated && !c.leading && now.Sub(c.attachedAt) >= c.timing.settle &&
		leaderElected(nil, c.candidates, c.lease, c.leaseArrived, now, c.timing.ttl) == "" && !c.leaseHeld(now)
	c.mutex.Unlock()
	if !vacant {
		return
	}
	if !c.publish(c.election.presence, []byte(metric.AvailabilityOffline)) {
		return
	}
	c.mutex.Lock()
	c.vacated = true
	c.mutex.Unlock()
	scribe.Log(scribe.SourceProbeLeader, scribe.SubjectHost(c.host), scribe.ActionPublish).Infof("observed", now, "[%s] presence [%s], nobody has held election [%s] since this host attached", c.election.presence, metric.AvailabilityOffline, c.election.name)
}

func (c *leaderCampaign) leaseHeld(now time.Time) bool {
	return c.lease.Host != "" && !c.leaseArrived.IsZero() && now.Sub(c.leaseArrived) <= c.timing.ttl
}

func (c *leaderCampaign) observe(client mqtt.Client, message mqtt.Message) {
	received := time.Now()
	topic := message.Topic()
	payload := strings.TrimSpace(string(message.Payload()))
	c.mutex.Lock()
	defer c.mutex.Unlock()
	if client != c.client {
		return
	}
	if topic == c.election.leaseTopic() {
		if !message.Retained() {
			c.leaseSeen = received
		}
		previous := c.lease.Host
		c.lease = leaderLease{}
		c.leaseArrived = time.Time{}
		c.resignedBy = ""
		if payload != "" && json.Unmarshal([]byte(payload), &c.lease) == nil && c.lease.Host != "" {
			c.leaseArrived = received
			c.vacated = false
			c.leaseLive = time.Time{}
			if !message.Retained() {
				c.leaseLive = received
			}
		} else if payload == "" && previous != "" && !message.Retained() {
			c.resignedBy, c.resignedAt = previous, received
		}
		if c.lease.Host != c.observedHost || c.lease.Epoch != c.observedFrom {
			c.observedHost, c.observedFrom = c.lease.Host, c.lease.Epoch
			scribe.Log(scribe.SourceProbeLeader, scribe.SubjectHost(c.host), scribe.ActionSubscribe).Infof("observed", received, "[%s] election led by [%s] at epoch [%d]", c.election.name, leaderNamed(c.lease.Host), c.lease.Epoch)
		}
		return
	}
	host, found := strings.CutPrefix(topic, c.election.candidateTopic(""))
	if !found || host == "" || strings.Contains(host, "/") {
		return
	}
	if host == c.host && !message.Retained() {
		c.heardSelf = received
	}
	var candidacy leaderCandidacy
	if payload == "" || json.Unmarshal([]byte(payload), &candidacy) != nil || candidacy.Host != host {
		if payload == "" && !message.Retained() {
			c.withdrawnAt[host] = received
		}
		if _, standing := c.candidates[host]; standing {
			scribe.Log(scribe.SourceProbeLeader, scribe.SubjectHost(host), scribe.ActionSubscribe).Infof("excluded", received, "[%s] election candidacy withdrawn or cleared by its will", c.election.name)
		}
		delete(c.candidates, host)
		delete(c.staleHosts, host)
		return
	}
	if _, standing := c.candidates[host]; !standing || c.staleHosts[host] {
		scribe.Log(scribe.SourceProbeLeader, scribe.SubjectHost(host), scribe.ActionSubscribe).Infof("observed", received, "[%s] election candidacy standing, retained [%v]", c.election.name, message.Retained())
	}
	c.candidates[host] = received
	renewed, parseErr := time.Parse(time.RFC3339Nano, candidacy.RenewedTS)
	if skew := received.Sub(renewed).Abs(); parseErr == nil && !message.Retained() && skew > leaderSkewWarn && !c.skewed[host] {
		c.skewed[host] = true
		scribe.Log(scribe.SourceProbeLeader, scribe.SubjectHost(host), scribe.ActionSubscribe).Warnf("observed", received, "[%s] election candidacy stamped [%s] ms off this clock, freshness is judged on arrival so the election is unaffected", c.election.name, elapsedMillis(skew))
	}
}

func (c *leaderCampaign) renew() bool {
	if c.stopping.Load() {
		return false
	}
	renewStart := time.Now()
	payload, _ := json.Marshal(leaderCandidacy{Host: c.host, RenewedTS: renewStart.Format(time.RFC3339Nano)})
	if !c.publish(c.election.candidateTopic(c.host), payload) {
		c.mutex.Lock()
		wasFailing := c.renewFailing
		c.renewFailing = true
		c.mutex.Unlock()
		logger := scribe.Log(scribe.SourceProbeLeader, scribe.SubjectHost(c.host), scribe.ActionPublish)
		if !wasFailing {
			logger.Warnf("faulting", renewStart, "[%s] election candidacy unacknowledged within [%s], leadership lapses after [%s]", c.election.name, c.timing.publishTimeout, c.timing.ackWindow)
		} else {
			logger.Debugf("faulting", renewStart, "[%s] election candidacy unacknowledged within [%s]", c.election.name, c.timing.publishTimeout)
		}
		return false
	}
	c.mutex.Lock()
	previousAck := c.lastAck
	c.lastAck = renewStart
	wasStanding, wasFailing := c.standing, c.renewFailing
	c.standing, c.renewFailing = true, false
	if !wasStanding || renewStart.Sub(previousAck) > c.timing.ttl {
		c.ackSince = renewStart
	}
	c.mutex.Unlock()
	if !wasStanding {
		scribe.Log(scribe.SourceProbeLeader, scribe.SubjectHost(c.host), scribe.ActionPublish).Infof("restored", renewStart, "[%s] election candidacy standing for this host", c.election.name)
	} else if wasFailing {
		scribe.Log(scribe.SourceProbeLeader, scribe.SubjectHost(c.host), scribe.ActionPublish).Infof("restored", renewStart, "[%s] election candidacy acknowledged again", c.election.name)
	}
	return true
}

func (c *leaderCampaign) withdrawCandidacy(now time.Time, reason string, faulted, always bool) {
	c.mutex.Lock()
	wasStanding := c.standing
	c.standing = false
	c.lastAck = time.Time{}
	c.mutex.Unlock()
	if !wasStanding && !always {
		return
	}
	cleared := c.publish(c.election.candidateTopic(c.host), []byte{})
	logger := scribe.Log(scribe.SourceProbeLeader, scribe.SubjectHost(c.host), scribe.ActionRemove)
	if faulted {
		logger.Warnf("excluded", now, "[%s] election candidacy withdrawn, acknowledged [%v], %s", c.election.name, cleared, reason)
		return
	}
	logger.Infof("excluded", now, "[%s] election candidacy withdrawn, acknowledged [%v], %s", c.election.name, cleared, reason)
}

func (c *leaderCampaign) evaluate(now time.Time) {
	c.mutex.Lock()
	elected := ""
	if c.standing {
		elected = leaderElected(c.election.eligible(), c.candidates, c.lease, c.leaseArrived, now, c.timing.ttl)
	}
	settle := c.timing.settle
	if resigned, at := c.resignedBy, c.resignedAt; resigned != "" && resigned != c.host && now.Sub(at) <= c.timing.ttl &&
		!c.withdrawnAt[resigned].IsZero() && at.Sub(c.withdrawnAt[resigned]).Abs() <= leaderResignWindow {
		settle = c.timing.refresh
	}
	settleLog := ""
	switch {
	case elected != c.host:
		if !c.electedFrom.IsZero() && !c.leading {
			settleLog = "abandoned"
		}
		c.electedFrom = time.Time{}
	case c.electedFrom.IsZero():
		c.electedFrom = now
		settleLog = "started"
	}
	wasLeading := c.leading
	settled := elected == c.host && (wasLeading || (c.heardSelf.After(c.attachedAt) && now.Sub(c.electedFrom) >= settle))
	generation := c.generation
	epoch, claimed := c.epoch, c.claimed
	if settled && !wasLeading {
		epoch, claimed = now.UnixNano(), now
	}
	if !settled {
		c.leading = false
	}
	c.mutex.Unlock()
	switch settleLog {
	case "started":
		scribe.Log(scribe.SourceProbeLeader, scribe.SubjectHost(c.host), scribe.ActionRegister).Infof("schedule", now, "[%s] election elects this host, settling for [%s] before claiming, previous leader resigned [%v]", c.election.name, settle, settle != c.timing.settle)
	case "abandoned":
		scribe.Log(scribe.SourceProbeLeader, scribe.SubjectHost(c.host), scribe.ActionRegister).Infof("deferred", now, "[%s] election settle abandoned, [%s] elected instead", c.election.name, leaderNamed(elected))
	}
	if !settled {
		if wasLeading {
			scribe.Log(scribe.SourceProbeLeader, scribe.SubjectHost(c.host), scribe.ActionStop).Infof("released", now, "[%s] leadership yielded to [%s]", c.election.name, leaderNamed(elected))
		}
		return
	}
	payload, _ := json.Marshal(leaderLease{Host: c.host, Epoch: epoch, ClaimedTS: claimed.Format(time.RFC3339Nano), RenewedTS: now.Format(time.RFC3339Nano)})
	if c.stopping.Load() {
		return
	}
	if !c.publish(c.election.leaseTopic(), payload) {
		scribe.Log(scribe.SourceProbeLeader, scribe.SubjectHost(c.host), scribe.ActionPublish).Warnf("faulting", now, "[%s] election lease unacknowledged within [%s]", c.election.name, c.timing.publishTimeout)
		return
	}
	c.mutex.Lock()
	if c.generation != generation || !c.attached || !c.standing || c.stopping.Load() {
		c.mutex.Unlock()
		scribe.Log(scribe.SourceProbeLeader, scribe.SubjectHost(c.host), scribe.ActionPublish).Warnf("excluded", now, "[%s] election lease acknowledged across a reattach, discarding the claim", c.election.name)
		return
	}
	c.lastLease = now
	c.epoch, c.claimed = epoch, claimed
	c.leading = true
	c.mutex.Unlock()
	if !wasLeading {
		scribe.Log(scribe.SourceProbeLeader, scribe.SubjectHost(c.host), scribe.ActionRegister).Infof("assigned", now, "[%s] leadership won at epoch [%d]", c.election.name, epoch)
	}
}

func (c *leaderCampaign) holding(now time.Time) (bool, int64) {
	c.mutex.Lock()
	defer c.mutex.Unlock()
	if c.lapse(now) != "" {
		return false, 0
	}
	return true, c.epoch
}

func (c *leaderCampaign) lapse(now time.Time) string {
	switch {
	case c.stopping.Load():
		return "the process is stopping"
	case !c.leading:
		return "this host is not elected"
	case !c.attached:
		return "the session is not attached"
	case !c.standing:
		return "this host is not standing"
	case c.lease.Host != c.host:
		return "the lease names [" + leaderNamed(c.lease.Host) + "]"
	case now.Sub(c.lastAck) > c.timing.ackWindow:
		return "candidacy renewals unacknowledged for [" + elapsedSeconds(now.Sub(c.lastAck)) + "] s"
	case now.Sub(c.lastLease) > c.timing.ackWindow:
		return "lease writes unacknowledged for [" + elapsedSeconds(now.Sub(c.lastLease)) + "] s"
	case !c.client.IsConnectionOpen():
		return "the broker session is closed"
	}
	return ""
}

func (c *leaderCampaign) resign() {
	c.resigned.Do(c.withdraw)
}

func (c *leaderCampaign) withdraw() {
	resignStart := time.Now()
	c.stopping.Store(true)
	locked := c.ticking.TryLock()
	for !locked && time.Since(resignStart) < leaderResignBudget/2 {
		time.Sleep(10 * time.Millisecond)
		locked = c.ticking.TryLock()
	}
	if locked {
		defer c.ticking.Unlock()
	}
	c.mutex.Lock()
	holding := c.leading || c.lease.Host == c.host
	client, retired := c.client, c.retired
	c.retired = nil
	c.mutex.Unlock()
	publisher := client
	if !client.IsConnectionOpen() && retired != nil {
		publisher = retired
	}
	var tokens []mqtt.Token
	if publisher.IsConnectionOpen() {
		tokens = append(tokens, publisher.Publish(c.election.candidateTopic(c.host), 1, true, []byte{}))
		if holding {
			tokens = append(tokens, publisher.Publish(c.election.leaseTopic(), 1, true, []byte{}))
		}
	}
	c.detach("the process is stopping")
	cleared := 0
	deadline := resignStart.Add(leaderResignBudget)
	for _, token := range tokens {
		if token.WaitTimeout(max(time.Until(deadline), 0)) && token.Error() == nil {
			cleared++
		}
	}
	client.Disconnect(250)
	if retired != nil {
		retired.Disconnect(250)
	}
	scribe.Log(scribe.SourceProbeLeader, scribe.SubjectHost(c.host), scribe.ActionStop).Infof("released", resignStart, "[%s] election resigned, leading [%v], cleared [%d/%d] retained topics", c.election.name, holding, cleared, len(tokens))
}

func (c *leaderCampaign) publish(topic string, payload []byte) bool {
	token := c.session().Publish(topic, 1, true, payload)
	return token.WaitTimeout(c.timing.publishTimeout) && token.Error() == nil
}

func leaderElected(eligible []string, candidates map[string]time.Time, lease leaderLease, leaseArrived, now time.Time, ttl time.Duration) string {
	fresh := func(arrived time.Time) bool {
		return !arrived.IsZero() && now.Sub(arrived) <= ttl
	}
	if lease.Host != "" && fresh(leaseArrived) && fresh(candidates[lease.Host]) {
		return lease.Host
	}
	var alive []string
	for _, host := range eligible {
		if fresh(candidates[host]) && !slices.Contains(alive, host) {
			alive = append(alive, host)
		}
	}
	if len(alive) == 0 {
		return ""
	}
	slices.Sort(alive)
	return alive[0]
}

func sinceLatest(now time.Time, marks ...time.Time) time.Duration {
	latest := time.Time{}
	for _, mark := range marks {
		if mark.After(latest) {
			latest = mark
		}
	}
	return now.Sub(latest)
}

func leaderNamed(host string) string {
	if host == "" {
		return "nobody"
	}
	return host
}

const (
	leaderSkewWarn      = 5 * time.Second
	leaderResignBudget  = 2 * time.Second
	leaderCensusTicks   = 12
	leaderOrphanTicks   = 720
	leaderRedialRestate = 100
	leaderResignWindow  = 5 * time.Second
)

var leaderTimingProduction = leaderTiming{
	refresh:        5 * time.Second,
	publishTimeout: 3 * time.Second,
	ackWindow:      13 * time.Second,
	keepAlive:      10 * time.Second,
	pingTimeout:    5 * time.Second,
	ttl:            30 * time.Second,
	settle:         20 * time.Second,
}

var (
	leaderCampaignsMu sync.Mutex
	leaderCampaigns   = map[string]*leaderCampaign{}
)
