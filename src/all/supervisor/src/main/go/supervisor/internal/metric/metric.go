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
	MetricHostFailedBackupStages
	MetricHostWarnTemperature
	MetricHostSpinFanSpeed
	MetricHostUsedDriveLife
	MetricHostUsedHomeSpace
	MetricHostUsedShareSpace
	MetricHostUsedBackupSpace
	MetricHostUsedSwapSpace
	MetricHostUsedDiskTime
	MetricHostUsedNetwork
	MetricHostUpTime
	MetricHostTemperature
	MetricHostServicesStatus
	MetricHostServicesMaxMemory
	MetricService
	MetricServiceBackupStatus
	MetricServiceHealthStatus
	MetricServiceConfiguredStatus
	MetricServiceName
	MetricServiceVersion
	MetricServiceUsedProcessor
	MetricServiceUsedMemory
	MetricServiceUsedDiskRate
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
