package probe

import (
	"fmt"
	"sort"
	"strings"
	"supervisor/internal/metric"
)

type gateSet map[metric.GateID]func() bool

func (g gateSet) resolve(gate metric.GateID) (bool, bool) {
	bound, found := g[gate]
	if !found {
		return false, false
	}
	return bound(), true
}

func siblingResolver(p probe, hostName string, trended bool) metric.ValueResolver {
	return func(id metric.ID) (float64, bool) {
		record, found := p.records().LoadByID(id, hostName, metric.ServiceIndexUnset)
		if !found || record == nil {
			return 0, false
		}
		detail := record.Value.Pulse
		if trended {
			detail = record.Value.Trend
		}
		if detail == nil || !detail.OK {
			return 0, false
		}
		if detail.Kind == metric.ValueFloat {
			return detail.ValueFloat, true
		}
		return float64(detail.ValueInt), true
	}
}

func verifyGates(probeMap map[probe][metric.MetricMax]bool) {
	referenced := map[metric.GateID]bool{}
	declared := map[metric.GateID]bool{}
	for candidate := range probeMap {
		for _, gate := range candidate.gates() {
			declared[gate] = true
		}
		for _, id := range candidate.metrics() {
			for _, gate := range metric.GetIDPulseRule(id).Gates() {
				referenced[gate] = true
			}
			for _, gate := range metric.GetIDTrendRule(id).Gates() {
				referenced[gate] = true
			}
		}
	}
	var undeclared []string
	for gate := range referenced {
		if !declared[gate] {
			undeclared = append(undeclared, gate.String())
		}
	}
	var unreferenced []string
	for gate := range declared {
		if !referenced[gate] {
			unreferenced = append(unreferenced, gate.String())
		}
	}
	sort.Strings(undeclared)
	sort.Strings(unreferenced)
	if len(undeclared) > 0 {
		panic(fmt.Sprintf("error: gate(s) [%s] are named in metricBuildersByID but declared by no probe", strings.Join(undeclared, ",")))
	}
	if len(unreferenced) > 0 {
		panic(fmt.Sprintf("error: gate(s) [%s] are declared by a probe but named in no metric rule", strings.Join(unreferenced, ",")))
	}
}
