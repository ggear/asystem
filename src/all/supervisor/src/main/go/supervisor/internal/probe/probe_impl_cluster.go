package probe

import (
	"context"
	"encoding/json"
	"fmt"
	"slices"
	"strings"
	"sync/atomic"
	"time"

	"supervisor/internal/config"
	"supervisor/internal/metric"
	"supervisor/internal/scribe"
	"supervisor/internal/stats"
)

type clusterProbe struct {
	cache       *metric.RecordCache
	mask        [metric.MetricMax]bool
	periods     config.Periods
	configPath  string
	hostName    string
	clusterBool *stats.BoolStats
	watch       atomic.Pointer[brokerWatcher]
	dialing     atomic.Bool
	dialed      atomic.Int64
	dialErr     atomic.Pointer[error]
	watched     bool
	unready     int
}

func newClusterProbe() *clusterProbe {
	return &clusterProbe{}
}

func (*clusterProbe) subject() scribe.Subject { return scribe.SubjectMetric(metric.MetricCluster) }

func (*clusterProbe) dormant() bool { return false }

func (p *clusterProbe) metrics() []metric.ID {
	return []metric.ID{metric.MetricCluster}
}

func (p *clusterProbe) gates() []metric.GateID { return nil }

func (p *clusterProbe) duties() []string {
	return []string{metric.LeaderDutySentinel}
}

func (p *clusterProbe) create(configPath string, cache *metric.RecordCache, mask [metric.MetricMax]bool, periods config.Periods) error {
	p.cache = cache
	p.mask = mask
	p.periods = periods
	p.configPath = configPath
	p.hostName = config.Load(configPath).Host()
	p.clusterBool = stats.NewBoolStats(periods.TrendHours, float64(periods.PulseMillis)/1000.0, float64(periods.PollMillis)/1000.0)
	return nil
}

func (p *clusterProbe) records() *metric.RecordCache { return p.cache }

func (p *clusterProbe) hasMetric(id metric.ID) bool {
	return id >= 0 && id < metric.MetricMax && p.mask[id]
}

func (p *clusterProbe) poll(_ context.Context, isPulse bool) error {
	runCacheMetricTasks(p, isPulse, nil, []cacheMetricTask{
		newCacheMetricTask(
			metric.ValueBool,
			metric.MetricCluster,
			metric.ServiceNameUnset,
			p.cluster,
			p.clusterBool,
			func() bool { return p.clusterBool.PulseLast() },
			func() bool { return p.clusterBool.TrendMean() },
		),
	})
	return nil
}

func (p *clusterProbe) cluster() (bool, derivation, error) {
	loaded := config.Load(p.configPath)
	hosts := clusterMonitored(loaded.Hosts(), loaded.Services)
	if len(hosts) == 0 {
		return false, derivation{}, fmt.Errorf("no cluster status computed, [%s] configures no hosts running a service besides [%s] [%w]", p.configPath, clusterSelfService, errEnvironment)
	}
	watch := p.watch.Load()
	if watch == nil {
		p.dial()
		if failed := p.dialErr.Load(); failed != nil {
			return false, derivation{}, fmt.Errorf("no cluster status computed, watching the cluster failed with [%v] [%w]", *failed, errEnvironment)
		}
		if p.watched {
			return false, derivation{}, fmt.Errorf("no cluster status computed, the cluster watch is being redialled [%w]", errEnvironment)
		}
		return false, derivation{}, errProbeWarmingUp
	}
	retained, ready := watch.readRetained()
	if !ready {
		p.unready++
		if p.unready >= clusterRedialPolls {
			p.unready = 0
			if p.watch.CompareAndSwap(watch, nil) {
				watch.close()
				scribe.Log(scribe.SourceProbeCluster, p.subject(), scribe.ActionConnect).Warnf("faulting", time.Now(), "[%d] polls with the cluster watch detached, redialling", clusterRedialPolls)
			}
		}
		if !p.watched {
			return false, derivation{}, errProbeWarmingUp
		}
		return false, derivation{}, fmt.Errorf("no cluster status computed, the cluster watch is not attached to the broker [%w]", errEnvironment)
	}
	p.unready = 0
	p.watched = true
	stale := time.Duration(p.periods.HeartbeatSecs*clusterStaleHeartbeats) * time.Second
	verdict := clusterHealth(hosts, retained, time.Now(), stale)
	healthy := len(verdict.faults) == 0
	if healthy {
		return true, derivedf(scribe.ActionCompute, "computed [true] healthy, hosts [%d/%d] and services [%d/%d] ok",
			verdict.hostsOK, len(hosts), verdict.servicesOK, verdict.services), nil
	}
	return false, derivedf(scribe.ActionCompute, "computed [false] healthy, hosts [%d/%d] and services [%d/%d] ok, faults [%s]",
		verdict.hostsOK, len(hosts), verdict.servicesOK, verdict.services, strings.Join(verdict.faults, ",")), nil
}

func (p *clusterProbe) dial() {
	if (p.dialed.Load() != 0 && time.Since(time.Unix(0, p.dialed.Load())) < brokerReconnectCap) || !p.dialing.CompareAndSwap(false, true) {
		return
	}
	p.dialed.Store(time.Now().UnixNano())
	go func() {
		defer p.dialing.Store(false)
		dialStart := time.Now()
		watch, err := brokerWatch(p.configPath, p.hostName, clusterStatusFilters...)
		if err != nil {
			p.dialErr.Store(&err)
			scribe.Log(scribe.SourceProbeCluster, p.subject(), scribe.ActionConnect).Warnf("faulting", dialStart, "[%v] watching the cluster, retrying in [%s]", err, brokerReconnectCap)
			return
		}
		p.dialErr.Store(nil)
		p.watch.Store(watch)
		scribe.Log(scribe.SourceProbeCluster, p.subject(), scribe.ActionConnect).Infof("attached", dialStart, "[%d] filters watching the cluster", len(clusterStatusFilters))
	}()
}

type clusterVerdict struct {
	hostsOK    int
	services   int
	servicesOK int
	faults     []string
}

func clusterMonitored(hosts []string, services func(string) []string) []string {
	var monitored []string
	for _, host := range hosts {
		if slices.ContainsFunc(services(host), func(service string) bool { return service != clusterSelfService }) {
			monitored = append(monitored, host)
		}
	}
	return monitored
}

func clusterHealth(hosts []string, retained map[string]string, now time.Time, stale time.Duration) clusterVerdict {
	verdict := clusterVerdict{}
	current := func(payload string) (metric.ValueData, string) {
		if payload == "" {
			return metric.ValueData{}, "unreported"
		}
		var value metric.ValueData
		if json.Unmarshal([]byte(payload), &value) != nil {
			return value, "unreadable"
		}
		switch {
		case value.Pulse == nil:
			return value, "unreported"
		case stale > 0 && now.Sub(time.Unix(value.Timestamp, 0)) > stale:
			return value, "stale"
		case value.Failed || !value.Pulse.OK:
			return value, "not-ok"
		}
		return value, ""
	}
	for _, host := range slices.Sorted(slices.Values(hosts)) {
		hostFault := ""
		if status := strings.TrimSpace(retained["supervisor/"+host+"/status"]); status != metric.AvailabilityOnline {
			hostFault = "offline"
		}
		if _, fault := current(retained["supervisor/"+host+"/data/host"]); hostFault == "" {
			hostFault = fault
		}
		if hostFault == "" {
			verdict.hostsOK++
		} else {
			verdict.faults = append(verdict.faults, host+"="+hostFault)
		}
		prefix := "supervisor/" + host + "/data/service/"
		var services []string
		for topic := range retained {
			if service, found := strings.CutPrefix(topic, prefix); found && service != "" && !strings.Contains(service, "/") {
				services = append(services, service)
			}
		}
		slices.Sort(services)
		for _, service := range services {
			value, fault := current(retained[prefix+service])
			if fault == "unreported" && value.Pulse == nil {
				continue
			}
			verdict.services++
			if fault == "" {
				verdict.servicesOK++
				continue
			}
			verdict.faults = append(verdict.faults, host+"/"+service+"="+fault)
		}
	}
	return verdict
}

const (
	clusterSelfService     = "supervisor"
	clusterStaleHeartbeats = 3
	clusterRedialPolls     = 20
)

var clusterStatusFilters = []string{
	"supervisor/+/status",
	"supervisor/+/data/host",
	"supervisor/+/data/service/+",
}
