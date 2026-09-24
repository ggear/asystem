package probe

import (
	"encoding/json"
	"errors"
	"os"
	"path/filepath"
	"slices"
	"strings"
	"testing"
	"time"

	"supervisor/internal/config"
	"supervisor/internal/metric"
)

func TestProbeImplCluster_Health(t *testing.T) {
	now := time.Unix(1_800_000_000, 0)
	payload := func(ok, failed bool, age time.Duration) string {
		value := metric.NewBoolValue(ok, ok)
		value.Timestamp = now.Add(-age).Unix()
		value.Failed = failed
		encoded, err := json.Marshal(value)
		if err != nil {
			t.Fatalf("marshal: got %v want nil", err)
		}
		return string(encoded)
	}
	healthy := func(hosts ...string) map[string]string {
		retained := map[string]string{}
		for _, host := range hosts {
			retained["supervisor/"+host+"/status"] = metric.AvailabilityOnline
			retained["supervisor/"+host+"/data/host"] = payload(true, false, 0)
			retained["supervisor/"+host+"/data/service/plex"] = payload(true, false, 0)
		}
		return retained
	}
	with := func(retained map[string]string, topic, value string) map[string]string {
		retained[topic] = value
		return retained
	}
	tests := []struct {
		name               string
		hosts              []string
		retained           map[string]string
		expectedHostsOK    int
		expectedServices   int
		expectedServicesOK int
		expectedFaults     string
		expectedError      bool
	}{
		{
			name:               "every_host_and_service_ok",
			hosts:              []string{"mad", "max"},
			retained:           healthy("mad", "max"),
			expectedHostsOK:    2,
			expectedServices:   2,
			expectedServicesOK: 2,
			expectedFaults:     "",
			expectedError:      false,
		},
		{
			name:               "configured_host_never_reported",
			hosts:              []string{"mad", "max"},
			retained:           healthy("mad"),
			expectedHostsOK:    1,
			expectedServices:   1,
			expectedServicesOK: 1,
			expectedFaults:     "max=offline",
			expectedError:      false,
		},
		{
			name:               "host_offline_with_retained_green_data",
			hosts:              []string{"mad"},
			retained:           with(healthy("mad"), "supervisor/mad/status", metric.AvailabilityOffline),
			expectedHostsOK:    0,
			expectedServices:   1,
			expectedServicesOK: 1,
			expectedFaults:     "mad=offline",
			expectedError:      false,
		},
		{
			name:               "host_aggregate_not_ok",
			hosts:              []string{"mad"},
			retained:           with(healthy("mad"), "supervisor/mad/data/host", payload(false, false, 0)),
			expectedHostsOK:    0,
			expectedServices:   1,
			expectedServicesOK: 1,
			expectedFaults:     "mad=not-ok",
			expectedError:      false,
		},
		{
			name:               "host_record_older_than_the_stale_window",
			hosts:              []string{"mad"},
			retained:           with(healthy("mad"), "supervisor/mad/data/host", payload(true, false, time.Hour)),
			expectedHostsOK:    0,
			expectedServices:   1,
			expectedServicesOK: 1,
			expectedFaults:     "mad=stale",
			expectedError:      false,
		},
		{
			name:               "service_failed_sample",
			hosts:              []string{"mad"},
			retained:           with(healthy("mad"), "supervisor/mad/data/service/plex", payload(true, true, 0)),
			expectedHostsOK:    1,
			expectedServices:   1,
			expectedServicesOK: 0,
			expectedFaults:     "mad/plex=not-ok",
			expectedError:      false,
		},
		{
			name:               "tombstoned_service_is_not_counted",
			hosts:              []string{"mad"},
			retained:           with(healthy("mad"), "supervisor/mad/data/service/plex", ""),
			expectedHostsOK:    1,
			expectedServices:   0,
			expectedServicesOK: 0,
			expectedFaults:     "",
			expectedError:      false,
		},
		{
			name:               "unconfigured_host_is_ignored",
			hosts:              []string{"mad"},
			retained:           with(healthy("mad"), "supervisor/old/status", metric.AvailabilityOffline),
			expectedHostsOK:    1,
			expectedServices:   1,
			expectedServicesOK: 1,
			expectedFaults:     "",
			expectedError:      false,
		},
		{
			name:               "service_metric_topics_are_not_services",
			hosts:              []string{"mad"},
			retained:           with(healthy("mad"), "supervisor/mad/data/service/plex/used_memory", payload(false, false, 0)),
			expectedHostsOK:    1,
			expectedServices:   1,
			expectedServicesOK: 1,
			expectedFaults:     "",
			expectedError:      false,
		},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			verdict := clusterHealth(tt.hosts, tt.retained, now, 15*time.Minute)
			if verdict.hostsOK != tt.expectedHostsOK {
				t.Errorf("hostsOK: got %d want %d", verdict.hostsOK, tt.expectedHostsOK)
			}
			if verdict.services != tt.expectedServices {
				t.Errorf("services: got %d want %d", verdict.services, tt.expectedServices)
			}
			if verdict.servicesOK != tt.expectedServicesOK {
				t.Errorf("servicesOK: got %d want %d", verdict.servicesOK, tt.expectedServicesOK)
			}
			if faults := strings.Join(verdict.faults, ","); faults != tt.expectedFaults {
				t.Errorf("faults: got %s want %s", faults, tt.expectedFaults)
			}
		})
	}
}

func TestProbeImplCluster_Monitored(t *testing.T) {
	tests := []struct {
		name              string
		services          map[string][]string
		expectedMonitored []string
		expectedError     bool
	}{
		{
			name:              "host_running_services_is_monitored",
			services:          map[string][]string{"mad": {"plex", "supervisor"}},
			expectedMonitored: []string{"mad"},
			expectedError:     false,
		},
		{
			name:              "host_running_only_supervisor_is_excluded",
			services:          map[string][]string{"jen": {"supervisor", "weewx"}, "jil": {"supervisor"}},
			expectedMonitored: []string{"jen"},
			expectedError:     false,
		},
		{
			name:              "host_running_nothing_is_excluded",
			services:          map[string][]string{"jil": {}},
			expectedMonitored: nil,
			expectedError:     false,
		},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			hosts := make([]string, 0, len(tt.services))
			for host := range tt.services {
				hosts = append(hosts, host)
			}
			slices.Sort(hosts)
			monitored := clusterMonitored(hosts, func(host string) []string { return tt.services[host] })
			if !slices.Equal(monitored, tt.expectedMonitored) {
				t.Errorf("monitored: got %v want %v", monitored, tt.expectedMonitored)
			}
		})
	}
}

func TestProbeImplCluster_RedialsADetachedWatch(t *testing.T) {
	t.Cleanup(config.Reset)
	configFile := filepath.Join(t.TempDir(), "config.json")
	if err := os.WriteFile(configFile, []byte(`{"asystem":{"version":"10.100.6000","host":"mad","broker":{"host":"127.0.0.1","port":"1"},"schema":[{"host":"mad","services":["plex"]}]}}`), 0644); err != nil {
		t.Fatalf("write config file failed: %v", err)
	}
	detached := brokerWatcherWith(&leaderStubClient{open: false}, map[string]string{})
	probe := &clusterProbe{configPath: configFile, watched: true}
	probe.dialed.Store(time.Now().UnixNano())
	probe.watch.Store(detached)
	for poll := 1; poll < clusterRedialPolls; poll++ {
		if _, _, err := probe.cluster(); !errors.Is(err, errEnvironment) {
			t.Fatalf("poll %d error: got %v want an environment fault while detached", poll, err)
		}
		if probe.watch.Load() != detached {
			t.Fatalf("poll %d watch: got it dropped want it kept until [%d] polls", poll, clusterRedialPolls)
		}
	}
	if _, _, err := probe.cluster(); !errors.Is(err, errEnvironment) {
		t.Fatalf("redial poll error: got %v want an environment fault", err)
	}
	if probe.watch.Load() != nil {
		t.Fatalf("watch: got it kept want it dropped for a redial after [%d] detached polls", clusterRedialPolls)
	}
	if _, _, err := probe.cluster(); !errors.Is(err, errEnvironment) {
		t.Fatalf("after redial error: got %v want an environment fault, not a warm-up that hides the outage", err)
	}
}

func TestProbeImplCluster_OnlyServersStandForElection(t *testing.T) {
	t.Cleanup(config.Reset)
	configFile := filepath.Join(t.TempDir(), "config.json")
	schema := `[{"host":"macmini-mad","form_factor":"server","stages":["primary","secondary","tertiary"],"services":["plex","supervisor"]},` +
		`{"host":"raspbpi-jen","form_factor":"edge","stages":["primary","secondary"],"services":["supervisor","weewx"]}]`
	if err := os.WriteFile(configFile, []byte(`{"asystem":{"version":"10.100.6000","host":"raspbpi-jen","schema":`+schema+`}}`), 0644); err != nil {
		t.Fatalf("write config file failed: %v", err)
	}
	cluster := clusterElection(configFile)
	if eligible := cluster.eligible(); !slices.Equal(eligible, []string{"macmini-mad"}) {
		t.Errorf("eligible: got %v want [macmini-mad], an edge host must never lead", eligible)
	}
	if cluster.leaseTopic() != metric.TopicLeaderLease || cluster.candidateTopic("macmini-mad") != metric.TopicLeaderCandidate("macmini-mad") {
		t.Errorf("topics: got [%s] [%s] want the declared cluster topics", cluster.leaseTopic(), cluster.candidateTopic("macmini-mad"))
	}
}

func TestProbeImplCluster_EveryDutyAnswersFromTheClusterElection(t *testing.T) {
	holder := leaderStubCampaign([]string{"alpha"}, "alpha")
	now := time.Now()
	holder.attached, holder.standing, holder.leading, holder.epoch = true, true, true, 9
	holder.lastAck, holder.lastLease = now.Add(time.Hour), now.Add(time.Hour)
	holder.lease, holder.leaseArrived = leaderLease{Host: "alpha", Epoch: 9}, now
	leaderCampaignsMu.Lock()
	for _, duty := range []string{metric.LeaderDutyBackup, metric.LeaderDutySentinel} {
		leaderCampaigns[duty] = holder
	}
	leaderCampaignsMu.Unlock()
	t.Cleanup(func() {
		leaderCampaignsMu.Lock()
		clear(leaderCampaigns)
		leaderCampaignsMu.Unlock()
	})
	tests := []struct {
		name            string
		duty            string
		expectedLeading bool
		expectedEpoch   int64
		expectedError   bool
	}{
		{name: "backup_duty", duty: metric.LeaderDutyBackup, expectedLeading: true, expectedEpoch: 9, expectedError: false},
		{name: "cluster_duty", duty: metric.LeaderDutySentinel, expectedLeading: true, expectedEpoch: 9, expectedError: false},
		{name: "undeclared_duty", duty: "undeclared", expectedLeading: false, expectedEpoch: 0, expectedError: false},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			if leading, epoch := Leading(tt.duty); leading != tt.expectedLeading || epoch != tt.expectedEpoch {
				t.Errorf("leading: got [%v] epoch [%d] want [%v] epoch [%d]", leading, epoch, tt.expectedLeading, tt.expectedEpoch)
			}
		})
	}
	for _, probe := range []leadingProbe{&backupProbe{}, &clusterProbe{}} {
		if duties := probe.duties(); len(duties) != 1 {
			t.Errorf("duties: got %v want exactly one duty per singleton probe", duties)
		}
	}
}
