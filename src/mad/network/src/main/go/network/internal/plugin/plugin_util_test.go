package plugin

import (
	"context"
	"encoding/json"
	"math"
	"net/http"
	"net/http/httptest"
	"strings"
	"sync/atomic"
	"testing"
	"time"

	"network/internal/remote"
)

func TestPluginUtilSample_DeltaTracker(t *testing.T) {
	d := newDeltaTracker()
	steps := []struct {
		name       string
		key        string
		cumulative int64
		expected   int64
		expectedOK bool
	}{
		{name: "first_seen_unknown", key: "rx", cumulative: 100, expected: 0, expectedOK: false},
		{name: "increment", key: "rx", cumulative: 150, expected: 50, expectedOK: true},
		{name: "equal_zero", key: "rx", cumulative: 150, expected: 0, expectedOK: true},
		{name: "reset_unknown", key: "rx", cumulative: 120, expected: 0, expectedOK: false},
		{name: "increment_after_reset", key: "rx", cumulative: 170, expected: 50, expectedOK: true},
		{name: "other_key_first_seen", key: "tx", cumulative: 10, expected: 0, expectedOK: false},
		{name: "other_key_increment", key: "tx", cumulative: 25, expected: 15, expectedOK: true},
	}
	for _, step := range steps {
		got, ok := d.Delta(step.key, step.cumulative)
		if got != step.expected || ok != step.expectedOK {
			t.Errorf("%s: got %d (ok %v) want %d (ok %v)", step.name, got, ok, step.expected, step.expectedOK)
		}
	}
}

func TestPluginUtilGateway_FetchReusedWithinACycle(t *testing.T) {
	var deviceFetches, clientFetches atomic.Int32
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		switch r.URL.Path {
		case "/api/auth/login":
		case "/proxy/network/api/s/default/stat/device":
			deviceFetches.Add(1)
			_, _ = w.Write([]byte(`{"data":[{"name":"udm-dar"}]}`))
		case "/proxy/network/api/s/default/stat/sta":
			clientFetches.Add(1)
			_, _ = w.Write([]byte(`{"data":[{"name":"camera"}]}`))
		default:
			http.NotFound(w, r)
		}
	}))
	defer server.Close()
	gateway, err := remote.NewGateway(server.URL, "default", "user", "token")
	if err != nil {
		t.Fatalf("gateway: %v", err)
	}
	session := gatewaySession{gateway: gateway}
	for range 2 {
		devices, clients, err := session.fetch(context.Background())
		if err != nil || len(devices) != 1 || len(clients) != 1 {
			t.Fatalf("fetch: got %d devices %d clients error %v want one of each", len(devices), len(clients), err)
		}
	}
	if deviceFetches.Load() != 1 || clientFetches.Load() != 1 {
		t.Errorf("fetches within reuse: got devices %d clients %d want 1 each, shared by ethernet and wireless", deviceFetches.Load(), clientFetches.Load())
	}
	session.fetched = session.fetched.Add(-gatewayReuse)
	if _, _, err := session.fetch(context.Background()); err != nil {
		t.Fatalf("fetch after reuse: %v", err)
	}
	if deviceFetches.Load() != 2 {
		t.Errorf("fetches after reuse expired: got %d want 2", deviceFetches.Load())
	}
}

func TestPluginUtilDevice_Read(t *testing.T) {
	now := time.Unix(1_800_000_000, 0)
	satisfaction := func(v int) *int { return &v }
	gateway := func(cpu, memory string, rx int64) remote.GatewayDevice {
		return remote.GatewayDevice{Name: "gw", State: 1, LastSeen: now.Unix(), Uptime: 86400,
			SystemStats: remote.GatewaySystemStats{CPU: cpu, Memory: memory},
			PortTable: []remote.GatewayPort{
				{PortIdx: 9, Up: true, Speed: 100, RxBytes: rx, TxBytes: 0},
				{PortIdx: 8, Up: true, Speed: 1000, RxBytes: rx, TxBytes: rx},
				{PortIdx: 2, Up: false, Speed: 1000, RxBytes: 1 << 40},
			}}
	}
	tests := []struct {
		name               string
		gap                time.Duration
		first, second      remote.GatewayDevice
		expectedUp         bool
		expectedTraffic    bool
		expectedThroughput float64
		expectedNetwork    float64
		expectedExperience float64
		expectedRestarted  bool
	}{
		{
			name:               "synthetic_experience_full_below_knees",
			first:              gateway("50", "85", 0),
			second:             gateway("50", "85", 750_000_000),
			expectedUp:         true,
			expectedTraffic:    true,
			expectedThroughput: 40,
			expectedNetwork:    20,
			expectedExperience: 100,
		},
		{
			name:               "synthetic_experience_cpu_past_knee",
			first:              gateway("90", "50", 0),
			second:             gateway("90", "50", 0),
			expectedUp:         true,
			expectedTraffic:    true,
			expectedExperience: 50,
		},
		{
			name:               "synthetic_experience_memory_past_later_knee",
			first:              gateway("10", "95", 0),
			second:             gateway("10", "95", 0),
			expectedUp:         true,
			expectedTraffic:    true,
			expectedExperience: 50,
		},
		{
			name:               "synthetic_experience_wan_link_saturating",
			first:              gateway("10", "50", 0),
			second:             gateway("10", "50", 3_375_000_000),
			expectedUp:         true,
			expectedTraffic:    true,
			expectedThroughput: 180,
			expectedNetwork:    90,
			expectedExperience: 50,
		},
		{
			name:               "reported_satisfaction_within_headroom",
			first:              remote.GatewayDevice{Name: "gw", State: 1, LastSeen: now.Unix(), Satisfaction: satisfaction(97), SystemStats: remote.GatewaySystemStats{CPU: "20", Memory: "50"}},
			second:             remote.GatewayDevice{Name: "gw", State: 1, LastSeen: now.Unix(), Satisfaction: satisfaction(97), SystemStats: remote.GatewaySystemStats{CPU: "20", Memory: "50"}},
			expectedUp:         true,
			expectedTraffic:    true,
			expectedExperience: 97,
		},
		{
			name:               "reported_satisfaction_capped_by_headroom",
			first:              remote.GatewayDevice{Name: "gw", State: 1, LastSeen: now.Unix(), Satisfaction: satisfaction(97), SystemStats: remote.GatewaySystemStats{CPU: "99", Memory: "99"}},
			second:             remote.GatewayDevice{Name: "gw", State: 1, LastSeen: now.Unix(), Satisfaction: satisfaction(97), SystemStats: remote.GatewaySystemStats{CPU: "99", Memory: "99"}},
			expectedUp:         true,
			expectedTraffic:    true,
			expectedExperience: 5,
		},
		{
			name:               "uptime_inside_the_check_gap_is_restarted",
			first:              remote.GatewayDevice{Name: "gw", State: 1, Uptime: 500, Satisfaction: satisfaction(100)},
			second:             remote.GatewayDevice{Name: "gw", State: 1, LastSeen: now.Unix(), Uptime: 290, Satisfaction: satisfaction(100)},
			expectedUp:         true,
			expectedTraffic:    true,
			expectedExperience: 100,
			expectedRestarted:  true,
		},
		{
			name:               "uptime_beyond_the_check_gap_is_not_restarted",
			first:              remote.GatewayDevice{Name: "gw", State: 1, Uptime: 300, Satisfaction: satisfaction(100)},
			second:             remote.GatewayDevice{Name: "gw", State: 1, LastSeen: now.Unix(), Uptime: 600, Satisfaction: satisfaction(100)},
			expectedUp:         true,
			expectedTraffic:    true,
			expectedExperience: 100,
		},
		{
			name:               "rate_spans_reports_not_polls_after_an_absence",
			gap:                30 * time.Minute,
			first:              gateway("10", "50", 0),
			second:             gateway("10", "50", 675_000_000),
			expectedUp:         true,
			expectedTraffic:    true,
			expectedThroughput: 6,
			expectedNetwork:    3,
			expectedExperience: 100,
		},
		{
			name:               "no_new_report_has_no_traffic",
			gap:                -1,
			first:              gateway("10", "50", 0),
			second:             gateway("10", "50", 675_000_000),
			expectedUp:         true,
			expectedTraffic:    false,
			expectedExperience: 100,
		},
		{
			name:               "uplink_used_when_no_ports",
			first:              remote.GatewayDevice{Name: "gw", State: 1, LastSeen: now.Unix(), Satisfaction: satisfaction(98), Uplink: remote.GatewayUplink{Speed: 1000, RxBytes: 0, TxBytes: 0}},
			second:             remote.GatewayDevice{Name: "gw", State: 1, LastSeen: now.Unix(), Satisfaction: satisfaction(98), Uplink: remote.GatewayUplink{Speed: 1000, RxBytes: 75_000_000, TxBytes: 37_500_000}},
			expectedUp:         true,
			expectedTraffic:    true,
			expectedThroughput: 3,
			expectedNetwork:    0.2,
			expectedExperience: 98,
		},
		{
			name:               "counter_reset_after_restart_has_no_traffic",
			first:              remote.GatewayDevice{Name: "gw", State: 1, LastSeen: now.Unix(), Uptime: 86400, Satisfaction: satisfaction(100), Uplink: remote.GatewayUplink{RxBytes: 900, TxBytes: 900}},
			second:             remote.GatewayDevice{Name: "gw", State: 1, LastSeen: now.Unix(), Uptime: 60, Satisfaction: satisfaction(100), Uplink: remote.GatewayUplink{RxBytes: 10, TxBytes: 10}},
			expectedUp:         true,
			expectedTraffic:    false,
			expectedExperience: 100,
			expectedRestarted:  true,
		},
		{
			name:   "stale_last_seen_is_down",
			first:  remote.GatewayDevice{Name: "gw", State: 1, LastSeen: now.Unix()},
			second: remote.GatewayDevice{Name: "gw", State: 1, LastSeen: now.Add(-6 * time.Minute).Unix()},
		},
		{
			name:   "disconnected_is_down",
			first:  remote.GatewayDevice{Name: "gw", State: 1, LastSeen: now.Unix()},
			second: remote.GatewayDevice{Name: "gw", State: 0, LastSeen: now.Unix()},
		},
		{
			name:   "missing_is_down",
			first:  remote.GatewayDevice{Name: "gw", State: 1, LastSeen: now.Unix()},
			second: remote.GatewayDevice{Name: "other", State: 1, LastSeen: now.Unix()},
		},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			gap := test.gap
			switch gap {
			case 0:
				gap = 5 * time.Minute
			case -1:
				gap = 0
			}
			first := test.first
			first.LastSeen = test.second.LastSeen - int64(gap/time.Second)
			deltas := newDeltaTracker()
			readDevices([]remote.GatewayDevice{first}, []string{"gw"}, deltas, now.Add(-gap))
			readings := readDevices([]remote.GatewayDevice{test.second}, []string{"gw"}, deltas, now)
			if len(readings) != 1 || readings[0].name != "gw" {
				t.Fatalf("readings: got %+v want one reading for gw", readings)
			}
			got := readings[0]
			if got.up != test.expectedUp {
				t.Fatalf("up: got %v want %v", got.up, test.expectedUp)
			}
			if got.hasTraffic != test.expectedTraffic {
				t.Errorf("has traffic: got %v want %v", got.hasTraffic, test.expectedTraffic)
			}
			if math.Abs(got.throughput-test.expectedThroughput) > 1e-6 {
				t.Errorf("throughput_mbps: got %v want %v", got.throughput, test.expectedThroughput)
			}
			if math.Abs(got.network-test.expectedNetwork) > 1e-6 {
				t.Errorf("network_pct: got %v want %v", got.network, test.expectedNetwork)
			}
			if math.Abs(got.experience-test.expectedExperience) > 1e-6 {
				t.Errorf("experience_pct: got %v want %v", got.experience, test.expectedExperience)
			}
			if got.restarted != test.expectedRestarted {
				t.Errorf("restarted: got %v want %v", got.restarted, test.expectedRestarted)
			}
		})
	}
}

func TestPluginUtilDevice_ReadRateSpansEachLinksOwnGap(t *testing.T) {
	now := time.Unix(1_800_000_000, 0)
	poll := func(at time.Time, linkUp bool, bytes int64) remote.GatewayDevice {
		return remote.GatewayDevice{Name: "sw", State: 1, LastSeen: at.Unix(), Uptime: 86400, Satisfaction: new(int),
			SystemStats: remote.GatewaySystemStats{CPU: "10", Memory: "10"},
			PortTable: []remote.GatewayPort{
				{PortIdx: 1, Up: true, Speed: 1000},
				{PortIdx: 2, Up: linkUp, Speed: 1000, RxBytes: bytes, TxBytes: bytes},
			}}
	}
	deltas := newDeltaTracker()
	readDevices([]remote.GatewayDevice{poll(now.Add(-10*time.Minute), true, 0)}, []string{"sw"}, deltas, now.Add(-10*time.Minute))
	readDevices([]remote.GatewayDevice{poll(now.Add(-5*time.Minute), false, 0)}, []string{"sw"}, deltas, now.Add(-5*time.Minute))
	got := readDevices([]remote.GatewayDevice{poll(now, true, 750_000_000)}, []string{"sw"}, deltas, now)[0]
	if math.Abs(got.throughput-20) > 1e-6 {
		t.Errorf("throughput_mbps: got %v want 20 (1.5 GB over the link's own 10 minutes, not the device's last 5)", got.throughput)
	}
	if math.Abs(got.network-1) > 1e-6 {
		t.Errorf("network_pct: got %v want 1", got.network)
	}
}

func TestPluginUtilDevice_ReadDecodesController(t *testing.T) {
	now := time.Unix(1_800_000_000, 0)
	payload := `[
		{"name":"udm-dar","type":"udm","state":1,"last_seen":1800000000,"uptime":7803542,"satisfaction":null,"num_sta":53,"overheating":false,
		 "system-stats":{"cpu":"19.4","mem":"81.0","uptime":"7803542"},
		 "temperatures":[{"name":"CPU","type":"cpu","value":40.75},{"name":"PHY","type":"board","value":41.5}],
		 "port_table":[{"port_idx":9,"up":true,"speed":100,"rx_bytes":10,"tx_bytes":20}]},
		{"name":"usw-dar-ceiling","type":"usw","state":1,"last_seen":1800000000,"uptime":612,"satisfaction":100,"num_sta":2,
		 "has_temperature":false,"general_temperature":0,"total_used_power":19.5,"total_max_power":45,"system-stats":{"cpu":"15.4","mem":"37.0"},
		 "port_table":[{"port_idx":1,"up":true,"speed":1000,"rx_bytes":1,"tx_bytes":1,"poe_power":"7.96"},{"port_idx":2,"up":true,"speed":100,"poe_power":"2.63"}]},
		{"name":"uap-dar-hallway","type":"uap","state":1,"last_seen":1800000000,"satisfaction":98,"num_sta":27,
		 "system-stats":{"cpu":"7.1","mem":"59.3"},"port_table":[],"uplink":{"type":"wire","speed":1000,"rx_bytes":25589376,"tx_bytes":4410287,"uplink_device_name":"usw-dar-ceiling","uplink_remote_port":1}}
	]`
	var devices []remote.GatewayDevice
	if err := json.Unmarshal([]byte(payload), &devices); err != nil {
		t.Fatalf("decode: %v", err)
	}
	readings := readDevices(devices, []string{"udm-dar", "usw-dar-ceiling", "uap-dar-hallway"}, newDeltaTracker(), now)
	udm, ceiling, hallway := readings[0], readings[1], readings[2]
	if !udm.up || udm.cpu != 19.4 || udm.memory != 81 || udm.clients != 53 {
		t.Errorf("udm: got %+v want up with cpu 19.4 memory 81 clients 53", udm)
	}
	if !udm.hasTemperature || udm.temperature != 41.5 {
		t.Errorf("udm temperature: got %v (has %v) want the hottest sensor 41.5", udm.temperature, udm.hasTemperature)
	}
	if udm.experience != 100 {
		t.Errorf("udm experience: got %v want 100 derived with cpu and memory below their knees", udm.experience)
	}
	if ceiling.experience != 100 || ceiling.restarted || ceiling.hasTemperature {
		t.Errorf("ceiling: got %+v want reported experience 100, no restart judged on a first sight, no temperature", ceiling)
	}
	if !ceiling.hasPoE || ceiling.poe != 19.5 || math.Abs(ceiling.poeBudget-43.333333) > 1e-4 {
		t.Errorf("ceiling poe: got %v W %v%% (has %v) want 19.5 W of a 45 W budget", ceiling.poe, ceiling.poeBudget, ceiling.hasPoE)
	}
	if udm.hasPoE {
		t.Errorf("udm poe: got set want unset without a budget")
	}
	if hallway.experience != 98 || hallway.clients != 27 || hallway.memory != 59.3 {
		t.Errorf("hallway: got %+v want experience 98 clients 27 memory 59.3", hallway)
	}
}

func TestPluginUtilDevice_Diagnose(t *testing.T) {
	healthy := deviceReading{name: "a", up: true, experience: 98, hasTraffic: true, throughput: 5}
	tests := []struct {
		name           string
		readings       []deviceReading
		expectedStatus Status
		expectedScore  int
		expectedReason string
	}{
		{
			name:           "fit_lowest_experience_scores",
			readings:       []deviceReading{healthy, {name: "b", up: true, experience: 91, hasTraffic: true, throughput: 1}},
			expectedStatus: StatusFit,
			expectedScore:  91,
			expectedReason: "UP",
		},
		{
			name:           "fit_before_traffic_is_known",
			readings:       []deviceReading{{name: "a", up: true, experience: 100}},
			expectedStatus: StatusFit,
			expectedScore:  100,
			expectedReason: "UP",
		},
		{
			name:           "sick_poor_experience",
			readings:       []deviceReading{healthy, {name: "b", up: true, experience: 80, hasTraffic: true, throughput: 1}},
			expectedStatus: StatusSick,
			expectedScore:  80,
			expectedReason: "POOR_EXPERIENCE",
		},
		{
			name:           "sick_restarted",
			readings:       []deviceReading{healthy, {name: "b", up: true, experience: 100, restarted: true}},
			expectedStatus: StatusSick,
			expectedScore:  80,
			expectedReason: "RESTARTED",
		},
		{
			name:           "sick_overheating",
			readings:       []deviceReading{{name: "a", up: true, experience: 100, overheating: true, hasTraffic: true, throughput: 1}},
			expectedStatus: StatusSick,
			expectedScore:  90,
			expectedReason: "OVERHEATING",
		},
		{
			name:           "restarted_without_traffic_is_not_dead",
			readings:       []deviceReading{{name: "a", up: true, experience: 100, restarted: true, hasTraffic: true, throughput: 0}},
			expectedStatus: StatusSick,
			expectedScore:  80,
			expectedReason: "RESTARTED",
		},
		{
			name:           "dead_no_traffic",
			readings:       []deviceReading{healthy, {name: "b", up: true, experience: 100, hasTraffic: true, throughput: 0}},
			expectedStatus: StatusDead,
			expectedScore:  0,
			expectedReason: "NO_TRAFFIC",
		},
		{
			name:           "dead_device_down",
			readings:       []deviceReading{healthy, {name: "b"}},
			expectedStatus: StatusDead,
			expectedScore:  0,
			expectedReason: "DEVICE_DOWN",
		},
		{
			name:           "dead_gateway_unreachable",
			expectedStatus: StatusDead,
			expectedScore:  0,
			expectedReason: "GATEWAY_UNREACHABLE",
		},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			got := diagnoseDevices(test.readings, ethernetDevice)
			if got.Status != test.expectedStatus {
				t.Errorf("status: got %s want %s", got.Status, test.expectedStatus)
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

func TestPluginUtilDevice_Report(t *testing.T) {
	readings := []deviceReading{
		{name: "udm-dar", up: true, experience: 99.94, hasTraffic: true, throughput: 4.567, network: 3.21, clients: 53, cpu: 19.44, memory: 81, temperature: 41.5, hasTemperature: true},
		{name: "usw-dar-ceiling", up: true, experience: 100, clients: 2, cpu: 15.4, memory: 37, restarted: true, poe: 19.56, poeBudget: 43.47, hasPoE: true},
		{name: "uap-dar-hallway"},
	}
	points := reportDevices(readings, ethernetDevice)
	if len(points) != len(readings) {
		t.Fatalf("points: got %d want %d (one per device)", len(points), len(readings))
	}
	if experience, _ := ethernetDevice.experience.Read(points[0]); experience != 100 {
		t.Errorf("experience_pct[udm]: got %v want 100, a whole percentage", experience)
	}
	if cpu, _ := ethernetDevice.cpu.Read(points[0]); cpu != 19 {
		t.Errorf("cpu_pct[udm]: got %v want 19, a whole percentage", cpu)
	}
	if throughput, ok := ethernetDevice.throughput.Read(points[0]); !ok || throughput != 4.57 {
		t.Errorf("throughput_mbps[udm]: got %v (set %v) want 4.57", throughput, ok)
	}
	if temperature, ok := ethernetDevice.temperature.Read(points[0]); !ok || temperature != 41.5 {
		t.Errorf("temperature[udm]: got %v (set %v) want 41.5", temperature, ok)
	}
	if _, ok := ethernetDevice.throughput.Read(points[1]); ok {
		t.Errorf("throughput_mbps[ceiling]: got set want unset before traffic is known")
	}
	if _, ok := ethernetDevice.temperature.Read(points[1]); ok {
		t.Errorf("temperature[ceiling]: got set want unset without a sensor")
	}
	if restarted, _ := ethernetDevice.restarted.Read(points[1]); !restarted {
		t.Errorf("restarted[ceiling]: got false want true")
	}
	if poe, ok := ethernetDevice.poe.Read(points[1]); !ok || poe != 19.6 {
		t.Errorf("poe_w[ceiling]: got %v (set %v) want 19.6", poe, ok)
	}
	if _, ok := ethernetDevice.poe.Read(points[0]); ok {
		t.Errorf("poe_w[udm]: got set want unset without a budget")
	}
	for _, check := range []struct {
		name string
		read func() (float64, bool)
	}{
		{"experience_pct", func() (float64, bool) { return ethernetDevice.experience.Read(points[2]) }},
		{"throughput_mbps", func() (float64, bool) { return ethernetDevice.throughput.Read(points[2]) }},
		{"network_pct", func() (float64, bool) { return ethernetDevice.network.Read(points[2]) }},
	} {
		if value, ok := check.read(); !ok || value != 0 {
			t.Errorf("%s[down]: got %v (set %v) want 0", check.name, value, ok)
		}
	}
	accessPoint := reportDevices(readings[:1], wirelessDevice)[0]
	if _, ok := wirelessDevice.experience.Read(accessPoint); !ok {
		t.Errorf("experience_pct[access point]: got unset want the shared measures written")
	}
	if wirelessDevice.temperature != nil || wirelessDevice.poe != nil || wirelessDevice.poeBudget != nil {
		t.Errorf("wireless schema: got temperature or poe declared want neither for access points that report none")
	}
	if _, ok := ethernetDevice.cpu.Read(points[2]); ok {
		t.Errorf("cpu_pct[down]: got set want unset when the device cannot be measured")
	}
}
