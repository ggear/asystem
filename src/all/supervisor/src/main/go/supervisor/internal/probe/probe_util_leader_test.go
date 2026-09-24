package probe

import (
	"context"
	"encoding/json"
	"fmt"
	"log/slog"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"sync"
	"testing"
	"time"

	"supervisor/internal/config"
	"supervisor/internal/metric"
	"supervisor/internal/scribe"
	"supervisor/internal/testutil"

	mqtt "github.com/eclipse/paho.mqtt.golang"
)

func TestProbeUtilLeader_Elected(t *testing.T) {
	now := time.Now()
	ttl := 30 * time.Second
	lease := func(host string) leaderLease {
		return leaderLease{Host: host, Epoch: 1}
	}
	tests := []struct {
		name           string
		eligible       []string
		candidates     map[string]time.Time
		lease          leaderLease
		leaseArrived   time.Time
		expectedLeader string
		expectedError  bool
	}{
		{
			name:           "nobody_standing",
			eligible:       []string{"mad", "max"},
			candidates:     map[string]time.Time{},
			expectedLeader: "",
			expectedError:  false,
		},
		{
			name:           "lowest_fresh_candidate_without_a_lease",
			eligible:       []string{"max", "mad", "meg"},
			candidates:     map[string]time.Time{"meg": now, "max": now, "mad": now},
			expectedLeader: "mad",
			expectedError:  false,
		},
		{
			name:           "candidate_unheard_for_the_ttl_is_passed_over",
			eligible:       []string{"mad", "max"},
			candidates:     map[string]time.Time{"mad": now.Add(-time.Minute), "max": now},
			expectedLeader: "max",
			expectedError:  false,
		},
		{
			name:           "ineligible_candidate_without_a_lease_is_ignored",
			eligible:       []string{"max"},
			candidates:     map[string]time.Time{"mad": now, "max": now},
			expectedLeader: "max",
			expectedError:  false,
		},
		{
			name:           "incumbent_lease_holds_against_a_lower_newcomer",
			eligible:       []string{"mad", "max"},
			candidates:     map[string]time.Time{"mad": now, "max": now},
			lease:          lease("max"),
			leaseArrived:   now.Add(-5 * time.Second),
			expectedLeader: "max",
			expectedError:  false,
		},
		{
			name:           "incumbent_holds_even_when_this_config_no_longer_names_it",
			eligible:       []string{"max"},
			candidates:     map[string]time.Time{"mad": now, "max": now},
			lease:          lease("mad"),
			leaseArrived:   now,
			expectedLeader: "mad",
			expectedError:  false,
		},
		{
			name:           "lease_unheard_for_the_ttl_falls_back_to_the_lowest",
			eligible:       []string{"mad", "max"},
			candidates:     map[string]time.Time{"mad": now, "max": now},
			lease:          lease("max"),
			leaseArrived:   now.Add(-time.Minute),
			expectedLeader: "mad",
			expectedError:  false,
		},
		{
			name:           "lease_of_a_departed_candidate_is_ignored",
			eligible:       []string{"mad", "max"},
			candidates:     map[string]time.Time{"max": now},
			lease:          lease("mad"),
			leaseArrived:   now,
			expectedLeader: "max",
			expectedError:  false,
		},
		{
			name:           "lease_with_no_host_is_no_lease",
			eligible:       []string{"mad", "max"},
			candidates:     map[string]time.Time{"mad": now, "max": now},
			lease:          leaderLease{},
			leaseArrived:   now,
			expectedLeader: "mad",
			expectedError:  false,
		},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			if leader := leaderElected(tt.eligible, tt.candidates, tt.lease, tt.leaseArrived, now, ttl); leader != tt.expectedLeader {
				t.Errorf("leader: got %q want %q", leader, tt.expectedLeader)
			}
		})
	}
}

func TestProbeUtilLeader_FreshnessIgnoresTheSendersClock(t *testing.T) {
	tests := []struct {
		name            string
		timestampOffset time.Duration
		expectedError   bool
	}{
		{name: "sender_an_hour_ahead", timestampOffset: time.Hour, expectedError: false},
		{name: "sender_an_hour_behind", timestampOffset: -time.Hour, expectedError: false},
		{name: "sender_in_step", timestampOffset: 0, expectedError: false},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			campaign := leaderStubCampaign([]string{"alpha", "bravo"}, "alpha")
			payload, _ := json.Marshal(leaderCandidacy{Host: "bravo", RenewedTS: time.Now().Add(tt.timestampOffset).Format(time.RFC3339Nano)})
			campaign.observe(nil, leaderStubMessage{topic: campaign.election.candidateTopic("bravo"), payload: payload})
			if leader := leaderElected([]string{"bravo"}, campaign.candidates, leaderLease{}, time.Time{}, time.Now(), campaign.timing.ttl); leader != "bravo" {
				t.Errorf("leader: got %q want bravo, a renewal that just arrived is fresh whatever it is stamped", leader)
			}
		})
	}
}

func TestProbeUtilLeader_ClaimAcrossAReattachIsDiscarded(t *testing.T) {
	tests := []struct {
		name            string
		reattach        bool
		expectedLeading bool
		expectedError   bool
	}{
		{name: "claim_acknowledged_in_the_same_session_leads", reattach: false, expectedLeading: true, expectedError: false},
		{name: "claim_acknowledged_after_a_reattach_is_discarded", reattach: true, expectedLeading: false, expectedError: false},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			campaign := leaderStubCampaign([]string{"alpha"}, "alpha")
			now := time.Now()
			campaign.attached, campaign.standing, campaign.lastAck = true, true, now
			campaign.candidates["alpha"] = now
			campaign.electedFrom = now.Add(-campaign.timing.settle - time.Second)
			stub := campaign.client.(*leaderStubClient)
			stub.onPublish = func(topic string) func() {
				if topic != campaign.election.leaseTopic() || !tt.reattach {
					return nil
				}
				return func() {
					campaign.mutex.Lock()
					campaign.generation++
					campaign.mutex.Unlock()
				}
			}
			campaign.evaluate(now)
			if leading, _ := campaign.holding(time.Now()); leading != tt.expectedLeading {
				t.Errorf("leading: got %v want %v", leading, tt.expectedLeading)
			}
		})
	}
}

func TestProbeUtilLeader_UnfitHostWithdrawsAndYields(t *testing.T) {
	tests := []struct {
		name          string
		eligible      []string
		alive         bool
		expectedError bool
	}{
		{name: "config_no_longer_names_the_holder", eligible: []string{"bravo"}, alive: true, expectedError: false},
		{name: "holder_poll_loop_stalled", eligible: []string{"alpha", "bravo"}, alive: false, expectedError: false},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			campaign := leaderStubCampaign(tt.eligible, "alpha")
			campaign.election.alive = func() bool { return tt.alive }
			now := time.Now()
			campaign.attached, campaign.standing, campaign.leading = true, true, true
			campaign.lastAck, campaign.lastLease, campaign.epoch = now, now, 1
			campaign.lease, campaign.leaseArrived = leaderLease{Host: "alpha", Epoch: 1}, now
			campaign.candidates["alpha"] = now
			if leading, _ := campaign.holding(now); !leading {
				t.Fatalf("setup leading: got false want true")
			}
			campaign.tick(now)
			stub := campaign.client.(*leaderStubClient)
			if !stub.published(campaign.election.candidateTopic("alpha"), "") {
				t.Errorf("candidacy: got %v want an empty retained candidacy published", stub.publishes())
			}
			if leading, _ := campaign.holding(time.Now()); leading {
				t.Errorf("leading: got true want false once unfit")
			}
			campaign.tick(time.Now())
			if count := stub.count(campaign.election.candidateTopic("alpha")); count != 1 {
				t.Errorf("withdrawals: got %d want 1, an unfit host withdraws once rather than every tick", count)
			}
		})
	}
}

func TestProbeUtilLeader_TickAfterResignationIsInert(t *testing.T) {
	campaign := leaderStubCampaign([]string{"alpha"}, "alpha")
	campaign.attached, campaign.standing = true, true
	campaign.stopping.Store(true)
	campaign.tick(time.Now())
	campaign.attach(campaign.client)
	if publishes := campaign.client.(*leaderStubClient).publishes(); len(publishes) != 0 {
		t.Errorf("publishes: got %v want none once resignation has begun", publishes)
	}
}

func TestProbeUtilLeader_VacantClusterMarksPresenceOffline(t *testing.T) {
	tests := []struct {
		name            string
		otherLease      bool
		attachedFor     time.Duration
		expectedOffline bool
		expectedError   bool
	}{
		{name: "nobody_holds_after_the_settle", otherLease: false, attachedFor: time.Minute, expectedOffline: true, expectedError: false},
		{name: "another_host_holds_a_fresh_lease", otherLease: true, attachedFor: time.Minute, expectedOffline: false, expectedError: false},
		{name: "still_settling_after_attach", otherLease: false, attachedFor: 100 * time.Millisecond, expectedOffline: false, expectedError: false},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			campaign := leaderStubCampaign([]string{"alpha", "bravo"}, "bravo")
			campaign.election.presence = "test/presence"
			now := time.Now()
			campaign.attached, campaign.attachedAt = true, now.Add(-tt.attachedFor)
			if tt.otherLease {
				campaign.candidates["alpha"] = now
				campaign.lease, campaign.leaseArrived = leaderLease{Host: "alpha", Epoch: 1}, now
			}
			campaign.tick(now)
			campaign.tick(now)
			stub := campaign.client.(*leaderStubClient)
			if offline := stub.published("test/presence", metric.AvailabilityOffline); offline != tt.expectedOffline {
				t.Errorf("offline: got %v want %v, publishes %v", offline, tt.expectedOffline, stub.publishes())
			}
			if tt.expectedOffline && stub.count("test/presence") != 1 {
				t.Errorf("offline publishes: got %d want 1 per vacancy", stub.count("test/presence"))
			}
		})
	}
}

func TestProbeUtilLeader_ClaimantDoesNotReportItsOwnVacancy(t *testing.T) {
	campaign := leaderStubCampaign([]string{"alpha"}, "alpha")
	campaign.election.presence = "test/presence"
	now := time.Now()
	campaign.attached, campaign.attachedAt, campaign.leading = true, now.Add(-time.Minute), true
	campaign.vacate(now)
	if published := campaign.client.(*leaderStubClient).published("test/presence", metric.AvailabilityOffline); published {
		t.Errorf("offline: got published want none from a host that has just claimed before its lease arrived")
	}
}

func TestProbeUtilLeader_WithdrawalLogsAHostFactAtInfo(t *testing.T) {
	tests := []struct {
		name          string
		eligible      []string
		alive         bool
		expectedLevel slog.Level
		expectedError bool
	}{
		{name: "ineligible_by_config_is_a_host_fact", eligible: []string{"bravo"}, alive: true, expectedLevel: slog.LevelInfo, expectedError: false},
		{name: "stalled_poll_loop_is_a_fault", eligible: []string{"alpha"}, alive: false, expectedLevel: slog.LevelWarn, expectedError: false},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			buffer := scribe.EnableBuffer(slog.LevelDebug, 100)
			t.Cleanup(func() { scribe.EnableStdout(slog.LevelDebug) })
			campaign := leaderStubCampaign(tt.eligible, "alpha")
			campaign.election.alive = func() bool { return tt.alive }
			campaign.attached, campaign.standing = true, true
			campaign.tick(time.Now())
			found := false
			for _, line := range buffer.Tail(100) {
				if strings.Contains(line.Detail, "candidacy withdrawn") {
					found = true
					if line.Level != tt.expectedLevel {
						t.Errorf("level: got %v want %v for [%s]", line.Level, tt.expectedLevel, line.Detail)
					}
				}
			}
			if !found {
				t.Errorf("withdrawal: got no log line want one at %v", tt.expectedLevel)
			}
		})
	}
}

func TestProbeUtilLeader_GracefulResignationShortensTheSettle(t *testing.T) {
	tests := []struct {
		name              string
		clearCandidacy    bool
		clearLease        bool
		retained          bool
		expectedAfterTick bool
		expectedError     bool
	}{
		{name: "resigned_leader_hands_over_after_one_refresh", clearCandidacy: true, clearLease: true, retained: false, expectedAfterTick: true, expectedError: false},
		{name: "crashed_leader_will_keeps_the_full_settle", clearCandidacy: true, clearLease: false, retained: false, expectedAfterTick: false, expectedError: false},
		{name: "lease_cleared_by_hand_keeps_the_full_settle", clearCandidacy: false, clearLease: true, retained: false, expectedAfterTick: false, expectedError: false},
		{name: "retained_clears_on_attach_keep_the_full_settle", clearCandidacy: true, clearLease: true, retained: true, expectedAfterTick: false, expectedError: false},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			campaign := leaderStubCampaign([]string{"alpha", "bravo"}, "bravo")
			start := time.Now()
			campaign.attached, campaign.standing, campaign.lastAck = true, true, start.Add(time.Hour)
			campaign.candidates["alpha"], campaign.candidates["bravo"] = start, start
			alphaLease, _ := json.Marshal(leaderLease{Host: "alpha", Epoch: 1})
			campaign.observe(nil, leaderStubMessage{topic: campaign.election.leaseTopic(), payload: alphaLease})
			if tt.clearCandidacy {
				campaign.observe(nil, leaderStubMessage{topic: campaign.election.candidateTopic("alpha"), retained: tt.retained})
			}
			if tt.clearLease {
				campaign.observe(nil, leaderStubMessage{topic: campaign.election.leaseTopic(), retained: tt.retained})
			}
			if !tt.clearCandidacy {
				delete(campaign.candidates, "alpha")
			}
			campaign.evaluate(start)
			campaign.evaluate(start.Add(campaign.timing.refresh))
			if leading, _ := campaign.holding(start.Add(campaign.timing.refresh)); leading != tt.expectedAfterTick {
				t.Errorf("leading after one refresh: got %v want %v", leading, tt.expectedAfterTick)
			}
			campaign.evaluate(start.Add(campaign.timing.refresh + time.Millisecond))
			campaign.evaluate(start.Add(campaign.timing.settle))
			if leading, _ := campaign.holding(start.Add(campaign.timing.settle)); !leading {
				t.Errorf("leading after the full settle: got false want true, a leader must not re-settle once its own lease arrives")
			}
		})
	}
}

func TestProbeUtilLeader_LeadsWhileConfigsDisagree(t *testing.T) {
	testutil.RequiresDocker(t)
	if _, _, err := testutil.SetupBrokerContainer(t); err != nil {
		t.Fatalf("setup broker container failed: %v", err)
	}
	t.Cleanup(config.Reset)
	configFile := filepath.Join(t.TempDir(), "config.json")
	content := fmt.Sprintf(`{"asystem":{"version":"10.100.6000","host":"alpha","broker":{"host":%q,"port":%q}}}`, os.Getenv("VERNEMQ_HOST"), os.Getenv("VERNEMQ_API_PORT"))
	if err := os.WriteFile(configFile, []byte(content), 0644); err != nil {
		t.Fatalf("write config file failed: %v", err)
	}
	timing := leaderTiming{refresh: 200 * time.Millisecond, publishTimeout: 150 * time.Millisecond, ackWindow: 550 * time.Millisecond,
		keepAlive: 2 * time.Second, pingTimeout: time.Second, ttl: 4 * time.Second, settle: time.Second}
	name := fmt.Sprintf("test-%d", time.Now().UnixNano())
	eligible := map[string][]string{"alpha": {"bravo", "charlie"}, "bravo": {"alpha", "bravo", "charlie"}, "charlie": {"alpha", "bravo", "charlie"}}
	campaigns := map[string]*leaderCampaign{}
	for _, host := range []string{"alpha", "bravo", "charlie"} {
		view := eligible[host]
		campaign, err := newLeaderCampaign(configFile, host, leaderElection{name: name, root: "test/" + name, eligible: func() []string { return view }}, timing)
		if err != nil {
			t.Fatalf("join %s: got %v want nil", host, err)
		}
		ctx, cancel := context.WithCancel(context.Background())
		t.Cleanup(cancel)
		campaigns[host] = campaign
		go campaign.run(ctx)
	}
	deadline := time.Now().Add(timing.settle + 4*time.Second)
	for time.Now().Before(deadline) {
		var holding []string
		for host, campaign := range campaigns {
			if leading, _ := campaign.holding(time.Now()); leading {
				holding = append(holding, host)
			}
		}
		if len(holding) > 1 {
			t.Fatalf("holders: got %v want at most one", holding)
		}
		if len(holding) == 1 {
			if holding[0] != "bravo" {
				t.Fatalf("holder: got %s want bravo, alpha's own config excludes it", holding[0])
			}
			return
		}
		time.Sleep(20 * time.Millisecond)
	}
	t.Fatalf("holder: got none want bravo while alpha's config disagrees with its peers")
}

func TestProbeUtilLeader_TimingInvariants(t *testing.T) {
	timing := leaderTimingProduction
	if timing.ackWindow != 2*timing.refresh+timing.publishTimeout {
		t.Errorf("ackWindow: got %v want two refreshes and a publish timeout [%v]", timing.ackWindow, 2*timing.refresh+timing.publishTimeout)
	}
	if timing.settle <= timing.ackWindow {
		t.Errorf("settle: got %v want above the ackWindow %v, or a deposed holder could overlap its successor", timing.settle, timing.ackWindow)
	}
	if timing.ttl <= timing.ackWindow+timing.refresh {
		t.Errorf("ttl: got %v want above ackWindow plus refresh %v, or a live candidate could read stale", timing.ttl, timing.ackWindow+timing.refresh)
	}
	if timing.keepAlive < time.Second {
		t.Errorf("keepAlive: got %v want at least a second, the MQTT unit", timing.keepAlive)
	}
	if timing.publishTimeout >= timing.refresh {
		t.Errorf("publishTimeout: got %v want below the refresh %v, or renewals queue behind each other", timing.publishTimeout, timing.refresh)
	}
}

func TestProbeUtilLeader_OneHolderAcrossFailover(t *testing.T) {
	testutil.RequiresDocker(t)
	_, observer, err := testutil.SetupBrokerContainer(t)
	if err != nil {
		t.Fatalf("setup broker container failed: %v", err)
	}
	t.Cleanup(config.Reset)
	configFile := filepath.Join(t.TempDir(), "config.json")
	content := fmt.Sprintf(`{"asystem":{"version":"10.100.6000","host":"alpha","broker":{"host":%q,"port":%q}}}`, os.Getenv("VERNEMQ_HOST"), os.Getenv("VERNEMQ_API_PORT"))
	if err := os.WriteFile(configFile, []byte(content), 0644); err != nil {
		t.Fatalf("write config file failed: %v", err)
	}
	timing := leaderTiming{
		refresh:        200 * time.Millisecond,
		publishTimeout: 150 * time.Millisecond,
		ackWindow:      550 * time.Millisecond,
		keepAlive:      2 * time.Second,
		pingTimeout:    time.Second,
		ttl:            4 * time.Second,
		settle:         time.Second,
	}
	hosts := []string{"alpha", "bravo", "charlie"}
	name := fmt.Sprintf("test-%d", time.Now().UnixNano())
	role := leaderElection{name: name, root: "test/" + name, eligible: func() []string { return hosts }}
	role.presence = "test/" + role.name + "/status"
	var mutex sync.Mutex
	campaigns := map[string]*leaderCampaign{}
	cancels := map[string]context.CancelFunc{}
	join := func(host string) {
		campaign, joinErr := newLeaderCampaign(configFile, host, role, timing)
		if joinErr != nil {
			t.Fatalf("join %s: got %v want nil", host, joinErr)
		}
		ctx, cancel := context.WithCancel(context.Background())
		mutex.Lock()
		campaigns[host], cancels[host] = campaign, cancel
		mutex.Unlock()
		go campaign.run(ctx)
	}
	t.Cleanup(func() {
		mutex.Lock()
		defer mutex.Unlock()
		for _, cancel := range cancels {
			cancel()
		}
	})
	holders := func() []string {
		mutex.Lock()
		defer mutex.Unlock()
		var holding []string
		for host, campaign := range campaigns {
			if leading, _ := campaign.holding(time.Now()); leading {
				holding = append(holding, host)
			}
		}
		return holding
	}
	await := func(phase, want string, within time.Duration) {
		deadline := time.Now().Add(within)
		for time.Now().Before(deadline) {
			holding := holders()
			if len(holding) > 1 {
				t.Fatalf("%s holders: got %v want at most one", phase, holding)
			}
			if len(holding) == 1 && holding[0] == want {
				return
			}
			time.Sleep(20 * time.Millisecond)
		}
		t.Fatalf("%s holder: got %v want [%s] within %v", phase, holders(), want, within)
	}
	hold := func(phase, want string, over time.Duration) {
		deadline := time.Now().Add(over)
		for time.Now().Before(deadline) {
			if holding := holders(); len(holding) != 1 || holding[0] != want {
				t.Fatalf("%s holders: got %v want only [%s] throughout", phase, holding, want)
			}
			time.Sleep(20 * time.Millisecond)
		}
	}
	for _, host := range hosts {
		join(host)
	}
	await("first_election", "alpha", timing.settle+3*time.Second)
	hold("steady", "alpha", 2*time.Second)
	retainedOf := func(topic string) string {
		retained := make(chan string, 1)
		token := observer.Subscribe(topic, 1, func(_ mqtt.Client, message mqtt.Message) {
			select {
			case retained <- string(message.Payload()):
			default:
			}
		})
		if !token.WaitTimeout(2*time.Second) || token.Error() != nil {
			t.Fatalf("subscribe %s: got %v want nil", topic, token.Error())
		}
		defer func() { observer.Unsubscribe(topic).WaitTimeout(2 * time.Second) }()
		select {
		case payload := <-retained:
			return payload
		case <-time.After(2 * time.Second):
			return ""
		}
	}
	lease := retainedOf(role.leaseTopic())
	if presence := retainedOf(role.presence); presence != metric.AvailabilityOnline {
		t.Fatalf("presence: got %q want %q while a holder exists", presence, metric.AvailabilityOnline)
	}
	var claimed leaderLease
	if json.Unmarshal([]byte(lease), &claimed) != nil || claimed.Host != "alpha" || claimed.Epoch == 0 {
		t.Fatalf("lease: got %q want alpha with an epoch", lease)
	}
	mutex.Lock()
	crashed := campaigns["alpha"]
	cancels["alpha"] = func() {}
	delete(campaigns, "alpha")
	mutex.Unlock()
	crashed.client.Disconnect(0)
	await("crash_failover", "bravo", timing.ttl+timing.settle+3*time.Second)
	join("alpha")
	hold("incumbent_survives_a_lower_rejoin", "bravo", timing.ttl+timing.settle)
	mutex.Lock()
	cancelBravo := cancels["bravo"]
	delete(campaigns, "bravo")
	mutex.Unlock()
	cancelBravo()
	await("graceful_handover_without_waiting_out_the_ttl", "alpha", timing.settle+2*time.Second)
	hold("settled_after_handover", "alpha", time.Second)
	if presence := retainedOf(role.presence); presence != metric.AvailabilityOnline {
		t.Fatalf("presence after handover: got %q want %q from the new holder", presence, metric.AvailabilityOnline)
	}
	mutex.Lock()
	for host, cancel := range cancels {
		cancel()
		delete(campaigns, host)
	}
	mutex.Unlock()
	deadline := time.Now().Add(3 * time.Second)
	for retainedOf(role.presence) != metric.AvailabilityOffline && time.Now().Before(deadline) {
		time.Sleep(100 * time.Millisecond)
	}
	if presence := retainedOf(role.presence); presence != metric.AvailabilityOffline {
		t.Fatalf("presence after every holder resigned: got %q want %q", presence, metric.AvailabilityOffline)
	}
}

func TestProbeUtilLeader_YieldsWhenTheBrokerStopsAnswering(t *testing.T) {
	testutil.RequiresDocker(t)
	broker, _, err := testutil.SetupBrokerContainer(t)
	if err != nil {
		t.Fatalf("setup broker container failed: %v", err)
	}
	t.Cleanup(config.Reset)
	configFile := filepath.Join(t.TempDir(), "config.json")
	content := fmt.Sprintf(`{"asystem":{"version":"10.100.6000","host":"alpha","broker":{"host":%q,"port":%q}}}`, os.Getenv("VERNEMQ_HOST"), os.Getenv("VERNEMQ_API_PORT"))
	if err := os.WriteFile(configFile, []byte(content), 0644); err != nil {
		t.Fatalf("write config file failed: %v", err)
	}
	timing := leaderTiming{
		refresh:        200 * time.Millisecond,
		publishTimeout: 150 * time.Millisecond,
		ackWindow:      550 * time.Millisecond,
		keepAlive:      5 * time.Second,
		pingTimeout:    3 * time.Second,
		ttl:            1500 * time.Millisecond,
		settle:         time.Second,
	}
	hosts := []string{"alpha", "bravo"}
	name := fmt.Sprintf("test-%d", time.Now().UnixNano())
	role := leaderElection{name: name, root: "test/" + name, eligible: func() []string { return hosts }}
	campaigns := map[string]*leaderCampaign{}
	for _, host := range hosts {
		campaign, joinErr := newLeaderCampaign(configFile, host, role, timing)
		if joinErr != nil {
			t.Fatalf("join %s: got %v want nil", host, joinErr)
		}
		ctx, cancel := context.WithCancel(context.Background())
		t.Cleanup(cancel)
		campaigns[host] = campaign
		go campaign.run(ctx)
	}
	holders := func() []string {
		var holding []string
		for _, host := range hosts {
			if leading, _ := campaigns[host].holding(time.Now()); leading {
				holding = append(holding, host)
			}
		}
		return holding
	}
	watch := func(phase string, over time.Duration, done func([]string) bool) bool {
		deadline := time.Now().Add(over)
		for time.Now().Before(deadline) {
			holding := holders()
			if len(holding) > 1 {
				t.Fatalf("%s holders: got %v want at most one", phase, holding)
			}
			if done != nil && done(holding) {
				return true
			}
			time.Sleep(10 * time.Millisecond)
		}
		return done == nil
	}
	if !watch("first_election", timing.settle+3*time.Second, func(holding []string) bool { return len(holding) == 1 }) {
		t.Fatalf("first_election holder: got %v want one within the settle", holders())
	}
	containerID := broker.GetContainerID()
	if out, pauseErr := exec.Command("docker", "pause", containerID).CombinedOutput(); pauseErr != nil {
		t.Fatalf("docker pause: got %v %s want nil", pauseErr, out)
	}
	paused := time.Now()
	resumed := false
	t.Cleanup(func() {
		if !resumed {
			_ = exec.Command("docker", "unpause", containerID).Run()
		}
	})
	if !watch("frozen_broker", timing.ackWindow+2*timing.refresh, func(holding []string) bool { return len(holding) == 0 }) {
		t.Fatalf("frozen_broker holders: got %v want none within the ack window of the freeze", holders())
	}
	t.Logf("Yielded [%v] after the broker froze, ack window [%v]", time.Since(paused).Round(time.Millisecond), timing.ackWindow)
	watch("still_frozen", 2*time.Second, func(holding []string) bool { return len(holding) != 0 })
	if holding := holders(); len(holding) != 0 {
		t.Fatalf("still_frozen holders: got %v want none while nothing is acknowledged", holding)
	}
	if out, unpauseErr := exec.Command("docker", "unpause", containerID).CombinedOutput(); unpauseErr != nil {
		t.Fatalf("docker unpause: got %v %s want nil", unpauseErr, out)
	}
	resumed = true
	if !watch("thawed_broker", timing.keepAlive*3+timing.ttl+timing.settle, func(holding []string) bool { return len(holding) == 1 }) {
		t.Fatalf("thawed_broker holder: got %v want one again after the broker answers", holders())
	}
	watch("settled_after_thaw", 2*time.Second, nil)
}

func leaderStubCampaign(eligible []string, host string) *leaderCampaign {
	campaign := newLeaderCampaignState("", host, leaderElection{name: "test", root: "test/election", eligible: func() []string { return eligible }}, leaderTiming{
		refresh: 200 * time.Millisecond, publishTimeout: 150 * time.Millisecond, ackWindow: 550 * time.Millisecond,
		keepAlive: 2 * time.Second, pingTimeout: time.Second, ttl: 4 * time.Second, settle: time.Second,
	})
	campaign.client = &leaderStubClient{open: true, handler: campaign.observe}
	return campaign
}

type leaderStubPublish struct {
	topic   string
	payload string
}

type leaderStubClient struct {
	mutex     sync.Mutex
	open      bool
	sent      []leaderStubPublish
	onPublish func(topic string) func()
	handler   mqtt.MessageHandler
}

func (s *leaderStubClient) IsConnected() bool      { return s.open }
func (s *leaderStubClient) IsConnectionOpen() bool { return s.open }
func (s *leaderStubClient) Connect() mqtt.Token    { return &leaderStubToken{} }
func (s *leaderStubClient) Disconnect(uint)        { s.open = false }
func (s *leaderStubClient) Publish(topic string, _ byte, _ bool, payload any) mqtt.Token {
	body := ""
	switch typed := payload.(type) {
	case []byte:
		body = string(typed)
	case string:
		body = typed
	}
	s.mutex.Lock()
	s.sent = append(s.sent, leaderStubPublish{topic: topic, payload: body})
	handler := s.handler
	s.mutex.Unlock()
	if handler != nil {
		handler(s, leaderStubMessage{topic: topic, payload: []byte(body)})
	}
	token := &leaderStubToken{}
	if s.onPublish != nil {
		token.hook = s.onPublish(topic)
	}
	return token
}
func (s *leaderStubClient) Subscribe(string, byte, mqtt.MessageHandler) mqtt.Token {
	return &leaderStubToken{}
}
func (s *leaderStubClient) SubscribeMultiple(map[string]byte, mqtt.MessageHandler) mqtt.Token {
	return &leaderStubToken{}
}
func (s *leaderStubClient) Unsubscribe(...string) mqtt.Token     { return &leaderStubToken{} }
func (s *leaderStubClient) AddRoute(string, mqtt.MessageHandler) {}
func (s *leaderStubClient) OptionsReader() mqtt.ClientOptionsReader {
	return mqtt.ClientOptionsReader{}
}

func (s *leaderStubClient) publishes() []leaderStubPublish {
	s.mutex.Lock()
	defer s.mutex.Unlock()
	return append([]leaderStubPublish(nil), s.sent...)
}

func (s *leaderStubClient) published(topic, payload string) bool {
	for _, sent := range s.publishes() {
		if sent.topic == topic && sent.payload == payload {
			return true
		}
	}
	return false
}

func (s *leaderStubClient) count(topic string) int {
	count := 0
	for _, sent := range s.publishes() {
		if sent.topic == topic {
			count++
		}
	}
	return count
}

type leaderStubToken struct {
	hook func()
}

func (t *leaderStubToken) Wait() bool { return t.WaitTimeout(0) }
func (t *leaderStubToken) WaitTimeout(time.Duration) bool {
	if t.hook != nil {
		t.hook()
	}
	return true
}
func (t *leaderStubToken) Done() <-chan struct{} {
	done := make(chan struct{})
	close(done)
	return done
}
func (t *leaderStubToken) Error() error { return nil }

type leaderStubMessage struct {
	topic    string
	payload  []byte
	retained bool
}

func (m leaderStubMessage) Duplicate() bool   { return false }
func (m leaderStubMessage) Qos() byte         { return 1 }
func (m leaderStubMessage) Retained() bool    { return m.retained }
func (m leaderStubMessage) Topic() string     { return m.topic }
func (m leaderStubMessage) MessageID() uint16 { return 0 }
func (m leaderStubMessage) Payload() []byte   { return m.payload }
func (m leaderStubMessage) Ack()              {}

func TestProbeUtilLeader_HoldsOnlyWhileTheLeaseNamesIt(t *testing.T) {
	tests := []struct {
		name            string
		leaseHost       string
		expectedLeading bool
		expectedError   bool
	}{
		{name: "lease_names_this_host", leaseHost: "alpha", expectedLeading: true, expectedError: false},
		{name: "lease_overwritten_by_a_concurrent_claimant", leaseHost: "bravo", expectedLeading: false, expectedError: false},
		{name: "no_lease_received_yet", leaseHost: "", expectedLeading: false, expectedError: false},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			campaign := leaderStubCampaign([]string{"alpha", "bravo"}, "alpha")
			now := time.Now()
			campaign.attached, campaign.standing, campaign.leading = true, true, true
			campaign.lastAck, campaign.lastLease, campaign.epoch = now, now, 1
			campaign.lease, campaign.leaseArrived = leaderLease{Host: tt.leaseHost, Epoch: 1}, now
			if leading, _ := campaign.holding(now); leading != tt.expectedLeading {
				t.Errorf("leading: got %v want %v", leading, tt.expectedLeading)
			}
		})
	}
}

func TestProbeUtilLeader_ResignationMidTickPublishesNothingAfter(t *testing.T) {
	campaign := leaderStubCampaign([]string{"alpha"}, "alpha")
	now := time.Now()
	campaign.attached, campaign.standing = true, true
	campaign.candidates["alpha"] = now
	campaign.electedFrom = now.Add(-campaign.timing.settle - time.Second)
	stub := campaign.client.(*leaderStubClient)
	stub.onPublish = func(topic string) func() {
		if topic != campaign.election.candidateTopic("alpha") {
			return nil
		}
		return func() { campaign.stopping.Store(true) }
	}
	campaign.tick(now)
	if count := stub.count(campaign.election.leaseTopic()); count != 0 {
		t.Errorf("lease publishes: got %d want 0 once resignation began inside the tick", count)
	}
	if leading, _ := campaign.holding(time.Now()); leading {
		t.Errorf("leading: got true want false while stopping")
	}
}

func TestProbeUtilLeader_PresenceRequiresHoldingTheRole(t *testing.T) {
	t.Cleanup(config.Reset)
	configFile := filepath.Join(t.TempDir(), "config.json")
	if err := os.WriteFile(configFile, []byte(`{"asystem":{"version":"10.100.6000","host":"alpha","broker":{"host":"127.0.0.1","port":"1"}}}`), 0644); err != nil {
		t.Fatalf("write config file failed: %v", err)
	}
	campaign := leaderStubCampaign([]string{"alpha"}, "alpha")
	campaign.configPath = configFile
	campaign.election.presence = "test/presence"
	campaign.appear()
	t.Cleanup(func() { campaign.vanish("test cleanup") })
	campaign.presenceMu.Lock()
	present := campaign.present
	campaign.presenceMu.Unlock()
	if present != nil {
		t.Errorf("presence: got a session opened want none for a host that does not hold the role")
	}
}
