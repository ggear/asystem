package engine

import (
	"slices"
	"testing"
	"time"
)

func TestEngineUtilHosts_Status(t *testing.T) {
	tests := []struct {
		name            string
		steps           func(*hostLiveness)
		expectedOnline  bool
		expectedKnown   bool
		expectedStamped bool
	}{
		{name: "an_unseen_host_counts_as_online", steps: func(*hostLiveness) {}, expectedOnline: true},
		{name: "a_stored_online_is_online_and_known", steps: func(h *hostLiveness) { h.store("alpha", true) }, expectedOnline: true, expectedKnown: true},
		{name: "a_stored_offline_is_offline_and_stamped", steps: func(h *hostLiveness) { h.store("alpha", false) }, expectedKnown: true, expectedStamped: true},
		{name: "online_after_offline_is_online_and_keeps_its_stamp", steps: func(h *hostLiveness) {
			h.store("alpha", false)
			h.store("alpha", true)
		}, expectedOnline: true, expectedKnown: true, expectedStamped: true},
		{name: "a_reset_forgets_status_and_stamp", steps: func(h *hostLiveness) {
			h.store("alpha", false)
			h.reset(time.Now())
		}, expectedOnline: true},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			hosts := newHostLiveness()
			test.steps(hosts)
			online, known := hosts.statusOf("alpha")
			if hosts.assertOnline("alpha") != test.expectedOnline || known != test.expectedKnown || (hosts.offlineAtOf("alpha") > 0) != test.expectedStamped {
				t.Fatalf("status: got online %v known %v online-asserted %v stamp [%d] want online %v known %v stamped %v",
					online, known, hosts.assertOnline("alpha"), hosts.offlineAtOf("alpha"), test.expectedOnline, test.expectedKnown, test.expectedStamped)
			}
		})
	}
}

func TestEngineUtilHosts_Quiet(t *testing.T) {
	now := time.Now()
	tests := []struct {
		name          string
		steps         func(*hostLiveness)
		provenAfter   time.Duration
		unprovenAfter time.Duration
		staleAfter    time.Duration
		expectedQuiet []string
	}{
		{name: "a_host_heard_inside_the_window_is_not_quiet", steps: func(h *hostLiveness) {
			h.reset(now.Add(-time.Minute))
			h.heardAt["alpha"] = now.Add(-2 * time.Second)
			h.heardAt["beta"] = now.Add(-2 * time.Second)
		}, provenAfter: 10 * time.Second},
		{name: "a_host_heard_before_the_window_is_quiet", steps: func(h *hostLiveness) {
			h.reset(now.Add(-time.Minute))
			h.heardAt["alpha"] = now.Add(-30 * time.Second)
			h.heardAt["beta"] = now.Add(-2 * time.Second)
		}, provenAfter: 10 * time.Second, expectedQuiet: []string{"alpha"}},
		{name: "a_host_never_heard_is_judged_from_the_open", steps: func(h *hostLiveness) {
			h.reset(now.Add(-5 * time.Second))
			h.heardAt["beta"] = now
		}, provenAfter: 10 * time.Second},
		{name: "a_host_never_heard_is_quiet_once_the_open_is_old", steps: func(h *hostLiveness) {
			h.reset(now.Add(-30 * time.Second))
			h.heardAt["beta"] = now
		}, provenAfter: 10 * time.Second, expectedQuiet: []string{"alpha"}},
		{name: "a_hearing_before_the_open_does_not_count", steps: func(h *hostLiveness) {
			h.heardAt["alpha"] = now.Add(-time.Minute)
			h.reset(now.Add(-2 * time.Second))
			h.heardAt["beta"] = now
		}, provenAfter: 10 * time.Second},
		{name: "an_offline_host_is_never_quiet", steps: func(h *hostLiveness) {
			h.reset(now.Add(-time.Hour))
			h.store("alpha", false)
			h.heardAt["beta"] = now
		}, provenAfter: 10 * time.Second},
		{name: "a_zero_window_makes_every_online_host_quiet", steps: func(h *hostLiveness) {
			h.reset(now.Add(-time.Second))
			h.heardAt["alpha"] = now.Add(-time.Millisecond)
			h.heardAt["beta"] = now.Add(-time.Millisecond)
		}, expectedQuiet: []string{"alpha", "beta"}},
		{name: "a_host_not_heard_since_the_open_is_judged_by_the_shorter_window", steps: func(h *hostLiveness) {
			h.reset(now.Add(-6 * time.Second))
			h.heardAt["beta"] = now
		}, provenAfter: 10 * time.Second, unprovenAfter: 5 * time.Second, expectedQuiet: []string{"alpha"}},
		{name: "a_host_heard_since_the_open_keeps_the_longer_window", steps: func(h *hostLiveness) {
			h.reset(now.Add(-20 * time.Second))
			h.heardAt["alpha"] = now.Add(-6 * time.Second)
			h.heardAt["beta"] = now
		}, provenAfter: 10 * time.Second, unprovenAfter: 5 * time.Second},
		{name: "a_host_whose_freshest_retained_stamp_predates_the_open_is_quiet_at_once", steps: func(h *hostLiveness) {
			h.reset(now.Add(-2 * time.Second))
			h.hearRetained("alpha", now.Add(-time.Hour).Unix())
			h.hearRetained("alpha", now.Add(-2*time.Hour).Unix())
			h.hearRetained("beta", now.Add(-3*time.Second).Unix())
			h.hearRetained("beta", now.Add(-time.Hour).Unix())
		}, provenAfter: time.Minute, unprovenAfter: time.Minute, staleAfter: 10 * time.Second, expectedQuiet: []string{"alpha"}},
		{name: "an_old_stamp_is_not_judged_before_the_flood_settles", steps: func(h *hostLiveness) {
			h.reset(now.Add(-200 * time.Millisecond))
			h.hearRetained("alpha", now.Add(-time.Hour).Unix())
		}, provenAfter: time.Minute, unprovenAfter: time.Minute, staleAfter: 10 * time.Second},
		{name: "a_host_heard_live_is_not_judged_on_its_stamps", steps: func(h *hostLiveness) {
			h.reset(now.Add(-5 * time.Second))
			h.hearRetained("alpha", now.Add(-time.Hour).Unix())
			h.heardAt["alpha"] = now.Add(-time.Second)
		}, provenAfter: time.Minute, unprovenAfter: time.Minute, staleAfter: 10 * time.Second},
		{name: "a_payload_without_a_timestamp_proves_nothing_either_way", steps: func(h *hostLiveness) {
			h.reset(now.Add(-5 * time.Second))
			h.hearRetained("alpha", 0)
		}, provenAfter: time.Minute, unprovenAfter: time.Minute, staleAfter: 10 * time.Second},
		{name: "a_zero_stale_age_turns_the_stamp_rule_off", steps: func(h *hostLiveness) {
			h.reset(now.Add(-5 * time.Second))
			h.hearRetained("alpha", now.Add(-time.Hour).Unix())
		}, provenAfter: time.Minute, unprovenAfter: time.Minute},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			hosts := newHostLiveness()
			test.steps(hosts)
			unprovenAfter := test.unprovenAfter
			if unprovenAfter == 0 {
				unprovenAfter = test.provenAfter
			}
			quiet := hosts.quietAmong([]string{"alpha", "beta"}, now, quietLimits{provenAfter: test.provenAfter, unprovenAfter: unprovenAfter, staleAfter: test.staleAfter})
			got := make([]string, 0, len(quiet))
			for hostName := range quiet {
				got = append(got, hostName)
			}
			slices.Sort(got)
			if !slices.Equal(got, append([]string{}, test.expectedQuiet...)) && !(len(got) == 0 && len(test.expectedQuiet) == 0) {
				t.Fatalf("quiet: got %v want %v", got, test.expectedQuiet)
			}
		})
	}
}
