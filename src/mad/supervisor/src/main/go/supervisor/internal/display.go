package internal

type metricDisplay struct {
	row         int
	col         int
	labelWidth  int
	valueWidth  int
	scaledWidth int
	labelAlign  string
	valueAlign  string
	prefix      string
	spacer      string
	suffix      string
	label       string
	topic       string
}

func CacheCompactDisplay(serviceCount int) ([][]metricDisplay, [][]metricDisplay, error) {
	hostMetrics := make([][]metricDisplay, 4)
	for i := range hostMetrics {
		hostMetrics[i] = make([]metricDisplay, 3)
	}
	hostEnums := []metricEnum{
		metricHostComputeUsedProcessor,
		metricHostComputeUsedMemory,
		metricHostStorageUsedSystemDrive,
		metricHostHealthFailedServices,
		metricHostHealthFailedShares,
		metricHostHealthFailedBackups,
		metricHostRuntimePeakTemperatureMax,
		metricHostRuntimePeakFanSpeedMax,
		metricHostRuntimeLifeUsedDrives,
		metricHostStorageUsedShareDrives,
		metricHostStorageUsedBackupDrives,
		metricHostComputeAllocatedMemory,
	}
	for i := 0; i < 4; i++ {
		for j := 0; j < 3; j++ {
			idx := i*3 + j
			topic := metricBuilders[hostEnums[idx]].topicBuilder.template
			hostMetrics[i][j] = metricDisplay{topic: topic}
		}
	}

	//for i := range hostMetrics {
	//	serviceMetrics[i] = make([]metricDisplay, 3)
	//}
	//serviceMetrics := make([][]metricDisplay, 4)
	//serviceEnums := []metricEnum{
	//	metricServiceUsedProcessor,
	//	metricServiceUsedMemory,
	//	metricServiceBackupStatus,
	//	metricServiceAllOk,
	//	metricServiceConfiguredStatus,
	//	metricServiceRestartCount,
	//	metricServiceName,
	//	metricServiceVersion,
	//	metricServiceRuntime,
	//	metricServiceUsedProcessor,
	//	metricServiceUsedMemory,
	//	metricServiceBackupStatus,
	//}

	return hostMetrics, nil, nil
}
