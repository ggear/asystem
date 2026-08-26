package metric

//go:generate go tool stringer -type=ID -output=metric_string.go

type ID int

// noinspection GoNameStartsWithPackageName
const (
	MetricHost ID = iota
	MetricHostUsedProcessor
	MetricHostUsedMemory
	MetricHostAllocatedMemory
	MetricHostFailedLogs
	MetricHostFailedShares
	MetricHostFailedBackups
	MetricHostWarnTemperature
	MetricHostSpinFanSpeed
	MetricHostLifeUsedDrives
	MetricHostUsedHomeSpace
	MetricHostUsedShareSpace
	MetricHostUsedBackupSpace
	MetricHostUsedSwapSpace
	MetricHostUsedDiskOps
	MetricHostUsedNetwork
	MetricHostRunningTime
	MetricHostTemperature
	MetricHostServices
	MetricHostServicesMaxMemory
	MetricService
	MetricServiceBackupStatus
	MetricServiceHealthStatus
	MetricServiceConfiguredStatus
	MetricServiceName
	MetricServiceVersion
	MetricServiceUsedProcessor
	MetricServiceUsedMemory
	MetricServiceUsedDiskOps
	MetricServiceUsedNetwork
	MetricServiceUpTime
	MetricServiceMaxMemory
	MetricServiceRestartCount
	MetricHostFailedDrives
	MetricMax
)

// noinspection GoNameStartsWithPackageName
type MetricKind int

// noinspection GoNameStartsWithPackageName
const (
	MetricKindUnset MetricKind = iota
	MetricKindHost
	MetricKindServices
	MetricKindService
	MetricKindSupervisor
)

const (
	ServiceNameUnset  = ""
	ServiceNameSchema = "__SCHEMA"
	ServiceIndexUnset = -1
)

func GetIDs() []ID {
	ids := make([]ID, MetricMax)
	for id := range MetricMax {
		ids[id] = id
	}
	return ids
}

func GetIDDeps(id ID) []ID {
	if id < 0 || id >= MetricMax {
		return nil
	}
	return metricBuildersByID[id].dependencies
}

func GetIDKind(id ID) MetricKind {
	if id < 0 || id >= MetricMax {
		return MetricKindUnset
	}
	return metricBuildersByID[id].metricKind
}

func GetIDUnit(id ID) string {
	if id < 0 || id >= MetricMax {
		return ""
	}
	return metricBuildersByID[id].unit
}

func GetIDWarming(id ID) bool {
	if id < 0 || id >= MetricMax {
		return false
	}
	return metricBuildersByID[id].warming
}

func GetIDPulseRule(id ID) Rule {
	if id < 0 || id >= MetricMax {
		return Rule{}
	}
	return metricBuildersByID[id].pulseRule
}

func GetIDTrendRule(id ID) Rule {
	if id < 0 || id >= MetricMax {
		return Rule{}
	}
	return metricBuildersByID[id].trendRule
}

func GetIDsByKind(types []MetricKind) []ID {
	if len(types) == 0 {
		return nil
	}
	allowed := make(map[MetricKind]bool, len(types))
	for _, t := range types {
		if t == MetricKindUnset {
			continue
		}
		allowed[t] = true
	}
	if len(allowed) == 0 {
		return nil
	}
	ids := make([]ID, 0, MetricMax)
	for _, builder := range metricBuildersByID {
		if allowed[builder.metricKind] {
			ids = append(ids, builder.id)
		}
	}
	return ids
}
