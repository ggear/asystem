package plugin

import (
	"context"
	"errors"
	"maps"
	"slices"
	"strings"
	"testing"
	"time"
)

func TestZigbee_Poll(t *testing.T) {
	var asked [][]string
	p := newZigbeePlugin()
	retained := map[string][]byte{
		"zigbee/bridge/state":                 []byte(`{"state":"online"}`),
		"zigbee/bridge/devices":               []byte(`[{"friendly_name":"Coordinator","type":"Coordinator"},{"friendly_name":"lamp","type":"Router"},{"friendly_name":"Kitchen/Pendant","type":"Router"}]`),
		"zigbee/bridge/definitions":           []byte(`{}`),
		"zigbee/lamp":                         []byte(`{"linkquality":120,"last_seen":"2026-10-07T08:13:10+08:00"}`),
		"zigbee/lamp/availability":            []byte(`{"state":"online"}`),
		"zigbee/Kitchen/Pendant":              []byte(`{"linkquality":90}`),
		"zigbee/Kitchen/Pendant/availability": []byte(`{"state":"online"}`),
		"zigbee/Hallway":                      []byte(`{"state":"ON"}`),
	}
	p.probe = func(_ context.Context, topics []string) (map[string][]byte, error) {
		asked = append(asked, topics)
		delivered := map[string][]byte{}
		for topic, payload := range retained {
			for _, filter := range topics {
				if topicMatches(filter, topic) {
					delivered[topic] = payload
				}
			}
		}
		return delivered, nil
	}
	first, err := p.Poll(context.Background())
	if err != nil {
		t.Fatalf("poll: unexpected error %v", err)
	}
	second, err := p.Poll(context.Background())
	if err != nil {
		t.Fatalf("second poll: unexpected error %v", err)
	}
	if !slices.Contains(asked[1], "zigbee/Kitchen/Pendant") || slices.Contains(asked[1], "zigbee/+") {
		t.Errorf("topics: got %v want each catalogued device's exact topics once the catalogue is known", asked[1])
	}
	pendant := slices.IndexFunc(second.Readings.(zigbeeSample).devices, func(d zigbeeReading) bool { return d.name == "Kitchen/Pendant" })
	if pendant < 0 || !second.Readings.(zigbeeSample).devices[pendant].available || second.Readings.(zigbeeSample).devices[pendant].lqi != 90 {
		t.Errorf("Kitchen/Pendant: got %+v want available with lqi 90 though its name spans two topic levels", second.Readings)
	}
	p.catalogued = p.catalogued.Add(-zigbeeCatalogueAge)
	if _, err := p.Poll(context.Background()); err != nil {
		t.Fatalf("third poll: unexpected error %v", err)
	}
	refreshed := []bool{slices.Contains(asked[0], "zigbee/bridge/devices"), slices.Contains(asked[1], "zigbee/bridge/devices"), slices.Contains(asked[2], "zigbee/bridge/devices")}
	if !slices.Equal(refreshed, []bool{true, false, true}) {
		t.Errorf("catalogue fetched: got %v want [true false true] (first poll, cached, refreshed once stale)", refreshed)
	}
	if first.Timestamp.IsZero() {
		t.Errorf("timestamp: got zero want the poll time stamped on the sample")
	}
	for _, topics := range asked {
		if slices.Contains(topics, "zigbee/#") || slices.Contains(topics, "zigbee/bridge/definitions") {
			t.Errorf("topics: got %v want narrowed subscriptions without the definitions", topics)
		}
	}
	sample, _ := first.Readings.(zigbeeSample)
	if !sample.online || len(sample.devices) != 2 || sample.devices[0].name != "lamp" || !sample.devices[0].available {
		t.Fatalf("sample: got %+v want online with the lamp read and the pendant catalogued (coordinator and group skipped)", sample)
	}
}

func TestZigbee_PollError(t *testing.T) {
	p := newZigbeePlugin()
	p.probe = func(context.Context, []string) (map[string][]byte, error) {
		return nil, errors.New("broker unreachable")
	}
	if _, err := p.Poll(context.Background()); err == nil {
		t.Fatal("poll: expected probe error to propagate, got nil")
	}
	if got, _ := p.Aggregate([]Sample{{}}); got.Status != StatusDead {
		t.Errorf("aggregate after failed poll: got %s want dead", got.Status)
	}
}

func TestZigbee_Read(t *testing.T) {
	now := time.Date(2026, 10, 7, 9, 0, 0, 0, time.UTC)
	messages := map[string][]byte{
		"zigbee/bridge/state":      []byte(`online`),
		"zigbee/bridge/devices":    []byte(`[{"friendly_name":"coord","type":"Coordinator"},{"friendly_name":"plug","type":"Router"},{"friendly_name":"bulb","type":"Router"},{"friendly_name":"sensor","type":"EndDevice"}]`),
		"zigbee/plug":              []byte(`{"linkquality":65,"last_seen":"2026-10-07T16:50:00+08:00"}`),
		"zigbee/plug/availability": []byte(`{"state":"online"}`),
		"zigbee/bulb":              []byte(`{"state":"OFF","last_seen":1791333000000}`),
		"zigbee/bulb/availability": []byte(`{"state":"offline"}`),
		"zigbee/sensor":            []byte(`not json`),
	}
	sample, catalogue := readZigbee("zigbee", messages, nil)
	if !sample.online || len(catalogue) != 4 {
		t.Fatalf("sample: got online %v catalogue %d want online with 4 catalogued", sample.online, len(catalogue))
	}
	if len(sample.devices) != 3 {
		t.Fatalf("devices: got %d want 3 (coordinator skipped)", len(sample.devices))
	}
	plug, bulb, sensor := sample.devices[0], sample.devices[1], sample.devices[2]
	if !plug.available || !plug.hasLQI || plug.lqi != 65 || !plug.hasLastSeen || plug.lastSeen.Unix() != now.Add(-10*time.Minute).Unix() {
		t.Errorf("plug: got %+v want available lqi 65 last seen 10 minutes ago", plug)
	}
	if bulb.available || bulb.hasLQI || !bulb.hasLastSeen || bulb.lastSeen.UnixMilli() != 1791333000000 {
		t.Errorf("bulb: got %+v want unavailable without lqi and an epoch last seen", bulb)
	}
	if sensor.hasLQI || sensor.hasLastSeen || sensor.available {
		t.Errorf("sensor: got %+v want nothing from an unparseable payload", sensor)
	}
	cached, kept := readZigbee("zigbee", map[string][]byte{"zigbee/bridge/state": []byte(`offline`)}, catalogue)
	if cached.online || len(kept) != 4 || len(cached.devices) != 3 {
		t.Errorf("cached catalogue: got online %v catalogue %d devices %d want offline reusing the 4 catalogued", cached.online, len(kept), len(cached.devices))
	}
}

func TestZigbee_Diagnose(t *testing.T) {
	healthy := map[string]outletState{"Ada Desk Outlet": {true, 80}, "Deck Fans Outlet": {true, 80}, "Edwin Desk Outlet": {true, 80}, "Kitchen Fan Outlet": {true, 80}}
	with := func(changes map[string]outletState) map[string]outletState {
		merged := maps.Clone(healthy)
		maps.Copy(merged, changes)
		return merged
	}
	bulbs := map[string]outletState{"bulb-on": {true, 80}, "bulb-off": {false, 0}}
	tests := []struct {
		name           string
		samples        []Sample
		expectedStatus Status
		expectedScore  int
		expectedReason string
	}{
		{
			name:           "fit_unavailable_bulbs_ignored",
			samples:        []Sample{zigbeeWindow(true, 0, healthy, bulbs)},
			expectedStatus: StatusFit,
			expectedScore:  75,
			expectedReason: "HEALTHY",
		},
		{
			name:           "fit_single_zero_reading_smoothed_by_median",
			samples:        []Sample{zigbeeWindow(true, 0, healthy, bulbs), zigbeeWindow(true, 0, with(map[string]outletState{"Deck Fans Outlet": {true, 0}}), bulbs), zigbeeWindow(true, 0, healthy, bulbs)},
			expectedStatus: StatusFit,
			expectedScore:  75,
			expectedReason: "HEALTHY",
		},
		{
			name:           "sick_router_offline",
			samples:        []Sample{zigbeeWindow(true, 0, with(map[string]outletState{"Edwin Desk Outlet": {false, 0}}), bulbs)},
			expectedStatus: StatusSick,
			expectedScore:  56,
			expectedReason: "ROUTERS_OFFLINE",
		},
		{
			name:           "sick_weak_router_by_median",
			samples:        []Sample{zigbeeWindow(true, 0, with(map[string]outletState{"Deck Fans Outlet": {true, 5}}), bulbs), zigbeeWindow(true, 0, with(map[string]outletState{"Deck Fans Outlet": {true, 8}}), bulbs)},
			expectedStatus: StatusSick,
			expectedScore:  55,
			expectedReason: "WEAK_ROUTERS: routers with median",
		},
		{
			name:           "sick_router_score_low",
			samples:        []Sample{zigbeeWindow(true, 0, map[string]outletState{"Ada Desk Outlet": {true, 30}, "Deck Fans Outlet": {true, 30}, "Edwin Desk Outlet": {true, 30}, "Kitchen Fan Outlet": {true, 30}}, map[string]outletState{"bulb-on": {true, 100}})},
			expectedStatus: StatusSick,
			expectedScore:  25,
			expectedReason: "WEAK_ROUTERS: router score",
		},
		{
			name:           "sick_weak_mesh",
			samples:        []Sample{zigbeeWindow(true, 0, healthy, map[string]outletState{"a": {true, 10}, "b": {true, 10}, "c": {true, 10}, "d": {true, 10}, "e": {true, 10}, "f": {true, 10}})},
			expectedStatus: StatusSick,
			expectedScore:  65,
			expectedReason: "WEAK_MESH",
		},
		{
			name:           "dead_routers_down",
			samples:        []Sample{zigbeeWindow(true, 0, healthy, bulbs), zigbeeWindow(true, 0, map[string]outletState{"Ada Desk Outlet": {false, 0}, "Deck Fans Outlet": {false, 0}, "Edwin Desk Outlet": {true, 0}, "Kitchen Fan Outlet": {false, 0}}, bulbs)},
			expectedStatus: StatusDead,
			expectedScore:  0,
			expectedReason: "ROUTERS_DOWN",
		},
		{
			name:           "dead_bridge_stale",
			samples:        []Sample{zigbeeWindow(true, 45*time.Minute, healthy, bulbs)},
			expectedStatus: StatusDead,
			expectedScore:  0,
			expectedReason: "BRIDGE_STALE",
		},
		{
			name:           "dead_coordinator_down",
			samples:        []Sample{zigbeeWindow(false, 0, healthy, bulbs)},
			expectedStatus: StatusDead,
			expectedScore:  0,
			expectedReason: "COORDINATOR_DOWN",
		},
		{
			name:           "fit_failed_latest_poll_falls_back_to_the_last_good_one",
			samples:        []Sample{zigbeeWindow(true, 0, healthy, bulbs), {}},
			expectedStatus: StatusFit,
			expectedScore:  75,
			expectedReason: "HEALTHY",
		},
		{
			name:           "dead_no_poll_succeeded",
			samples:        []Sample{{}, {}},
			expectedStatus: StatusDead,
			expectedScore:  0,
			expectedReason: "NO_DATA",
		},
		{
			name:           "fit_router_without_link_quality_is_unknown_not_weak",
			samples:        []Sample{zigbeeWindow(true, 0, with(map[string]outletState{"Deck Fans Outlet": {true, -1}}), bulbs)},
			expectedStatus: StatusFit,
			expectedScore:  75,
			expectedReason: "HEALTHY",
		},
		{
			name:           "fit_no_router_link_quality_yet_is_not_down",
			samples:        []Sample{zigbeeWindow(true, 0, map[string]outletState{"Ada Desk Outlet": {true, -1}, "Deck Fans Outlet": {true, -1}, "Edwin Desk Outlet": {true, -1}, "Kitchen Fan Outlet": {true, -1}}, bulbs)},
			expectedStatus: StatusFit,
			expectedScore:  94,
			expectedReason: "HEALTHY",
		},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			got := diagnoseZigbee(test.samples)
			if got.Status != test.expectedStatus {
				t.Errorf("status: got %s want %s (%s)", got.Status, test.expectedStatus, got.Reason)
			}
			if got.Score != test.expectedScore {
				t.Errorf("score: got %d want %d", got.Score, test.expectedScore)
			}
			if !strings.HasPrefix(got.Reason, test.expectedReason) {
				t.Errorf("reason: got %q want prefix %q", got.Reason, test.expectedReason)
			}
		})
	}
}

func TestZigbee_Report(t *testing.T) {
	now := time.Date(2026, 10, 7, 9, 0, 0, 0, time.UTC)
	latest := zigbeeSample{online: true, devices: []zigbeeReading{
		{name: "plug", available: true, lqi: 7, hasLQI: true, lastSeen: now.Add(-90 * time.Second), hasLastSeen: true},
		{name: "bulb", available: false, lqi: 40, hasLQI: true},
	}}
	points := reportZigbee(latest, now, map[string]float64{"plug": 64.5, "bulb": 40}, 61.25, 70)
	if len(points) != 4 {
		t.Fatalf("points: got %d want 4 (two devices and two scores)", len(points))
	}
	if lqi, ok := zigbeeLQI.Read(points[0]); !ok || lqi != 65 {
		t.Errorf("lqi[plug]: got %d (set %v) want the window median 65, not the latest 7", lqi, ok)
	}
	if age, ok := zigbeeLastSeen.Read(points[0]); !ok || age != 90 {
		t.Errorf("last_seen_s[plug]: got %d (set %v) want 90", age, ok)
	}
	if _, ok := zigbeeLQI.Read(points[1]); ok {
		t.Errorf("lqi[bulb]: got set want unset while unavailable")
	}
	if _, ok := zigbeeLastSeen.Read(points[1]); ok {
		t.Errorf("last_seen_s[bulb]: got set want unset without a report")
	}
	for index, expected := range map[int]struct {
		name  string
		value float64
	}{2: {"router", 61}, 3: {"mesh", 70}} {
		if name, _ := zigbeeExperienceName.Read(points[index]); name != expected.name {
			t.Errorf("score[%d]: got %q want %q", index, name, expected.name)
		}
		if value, _ := zigbeeExperiencePct.Read(points[index]); value != expected.value {
			t.Errorf("value[%s]: got %v want %v", expected.name, value, expected.value)
		}
	}
}

type outletState struct {
	available bool
	lqi       int
}

func zigbeeWindow(online bool, quiet time.Duration, groups ...map[string]outletState) Sample {
	at := time.Date(2026, 10, 7, 9, 0, 0, 0, time.UTC)
	sample := zigbeeSample{online: online}
	for _, group := range groups {
		for name, state := range group {
			sample.devices = append(sample.devices, zigbeeReading{
				name: name, available: state.available, lqi: max(state.lqi, 0), hasLQI: state.lqi >= 0,
				lastSeen: at.Add(-quiet - time.Minute), hasLastSeen: true})
		}
	}
	return Sample{Timestamp: at, Readings: sample}
}

func topicMatches(filter, topic string) bool {
	filters, levels := strings.Split(filter, "/"), strings.Split(topic, "/")
	for index, level := range filters {
		if level == "#" {
			return true
		}
		if index >= len(levels) || (level != "+" && level != levels[index]) {
			return false
		}
	}
	return len(filters) == len(levels)
}
