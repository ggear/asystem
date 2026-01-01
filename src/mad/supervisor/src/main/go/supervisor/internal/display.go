package internal

type cellDisplay struct {
	cell         int
	topBorder    borderDisplay
	leftBorder   borderDisplay
	rightBorder  borderDisplay
	bottomBorder borderDisplay
	metrics      [][]metricDisplay
}

type borderDisplay struct {
	labelWidth  int
	scaledWidth int
	labelAlign  string
	prefix      string
	spacer      string
	suffix      string
	label       string
}

type metricDisplay struct {
	id          metricID
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
}

func CacheCompactDisplay(serviceCount int) ([][]metricDisplay, [][]metricDisplay, error) {
	hostMetrics := make([][]metricDisplay, 4)
	for i := range hostMetrics {
		hostMetrics[i] = make([]metricDisplay, 3)
	}
	for i := 0; i < 4; i++ {
		for j := 0; j < 3; j++ {
			hostMetrics[i][j] = metricDisplay{}
		}
	}

	//for i := range hostMetrics {
	//	serviceMetrics[i] = make([]metricDisplay, 3)
	//}
	//serviceMetrics := make([][]metricDisplay, 4)
	//serviceEnums := []metricID{
	//	metricServiceUsedProcessor,topic
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
