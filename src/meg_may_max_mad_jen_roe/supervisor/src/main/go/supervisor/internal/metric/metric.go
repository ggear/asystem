package metric

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
	MetricHostWarnTemperatureOfMax
	MetricHostSpinFanSpeedOfMax
	MetricHostLifeUsedDrives
	MetricHostUsedSystemSpace
	MetricHostUsedShareSpace
	MetricHostUsedBackupSpace
	MetricHostUsedSwapSpace
	MetricHostUsedDiskOps
	MetricHostUsedNetwork
	MetricHostRunningTime
	MetricHostTemperature
	MetricServices
	MetricServicesMaxMemory
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
	MetricServiceRunningTime
	MetricServiceMaxMemory
	MetricServiceRestartCount
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
	for id := ID(0); id < MetricMax; id++ {
		ids[id] = id
	}
	return ids
}

func GetIDDeps(id ID) []ID {
	if id < 0 || id >= MetricMax {
		return nil
	}
	return metricBuildersByID[id].deps
}

func GetIDKind(id ID) MetricKind {
	if id < 0 || id >= MetricMax {
		return MetricKindUnset
	}
	return metricBuildersByID[id].kind
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
		if allowed[builder.kind] {
			ids = append(ids, builder.id)
		}
	}
	return ids
}
