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
