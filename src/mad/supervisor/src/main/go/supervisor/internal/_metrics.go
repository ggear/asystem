package internal

//
//const (
//	topicNamespaceIndex = iota
//	topicHostIndex
//	topicTypeIndex
//	topicCategoryIndex
//	topicDescriptionIndex
//	topicLabelIndex
//)
//
//type TopicHost int
//
//const (
//	TopicComputeUsedProcessor TopicHost = iota
//	TopicComputeUsedMemory
//	TopicComputeAllocatedMemory
//	TopicHealthFailedServices
//	TopicHealthFailedShares
//	TopicHealthFailedBackups
//	TopicRuntimePeakTemp
//	TopicRuntimePeakFan
//	TopicRuntimeLifeDrives
//	TopicStorageUsedSystem
//	TopicStorageUsedShares
//	TopicStorageUsedBackups
//)
//
//type TopicMeta struct {
//	Path     string
//	Unit     string
//	Category string
//}
//
//var topicHostMeta = [...]TopicMeta{
//	TopicComputeUsedProcessor:   {"compute/used_processor/used_cpu", "%", "compute"},
//	TopicComputeUsedMemory:      {"compute/used_memory/used_ram", "%", "compute"},
//	TopicComputeAllocatedMemory: {"compute/allocated_memory/aloc_ram", "%", "compute"},
//	TopicHealthFailedServices:   {"health/failed_services/fail_svc", "%", "health"},
//	TopicHealthFailedShares:     {"health/failed_shares/fail_shr", "%", "health"},
//	TopicHealthFailedBackups:    {"health/failed_backups/fail_bkp", "%", "health"},
//	TopicRuntimePeakTemp:        {"runtime/peak_temperature/peak_tem", "°C", "runtime"},
//	TopicRuntimePeakFan:         {"runtime/peak_fan/peak_fan", "%", "runtime"},
//	TopicRuntimeLifeDrives:      {"runtime/life_drives/life_ssd", "d", "runtime"},
//	TopicStorageUsedSystem:      {"storage/used_system_drive/used_sys", "%", "storage"},
//	TopicStorageUsedShares:      {"storage/used_share_drives/used_shr", "%", "storage"},
//	TopicStorageUsedBackups:     {"storage/used_backup_drives/used_bkp", "%", "storage"},
//}
//
//func (m TopicHost) Topic() string    { return topicHostMeta[m].Path }
//func (m TopicHost) Unit() string     { return topicHostMeta[m].Unit }
//func (m TopicHost) Category() string { return topicHostMeta[m].Category }
//
//// TODO: Merge metricBuilder into Topic
////       Have runtime checks and tests to make sure all are defined - eg add a Count to TopicHost and ensure topicHostMeta len == it
////       Add service, as enum host/service
////       Add rollups and full topic name, as enum metric/derivative
////       Have load metrics use this, iterate and make available as a map
////       Have load relaxed/compact display use this in table, taking in map and binding by Topic
//
////var topicHost = [...]string{
////	TopicComputeUsedProcessor:   "compute/used_processor/used_cpu",
////	TopicComputeUsedMemory:      "compute/used_memory/used_ram",
////	TopicComputeAllocatedMemory: "compute/allocated_memory/aloc_ram",
////	TopicHealthFailedServices:   "health/failed_services/fail_svc",
////	TopicHealthFailedShares:     "health/failed_shares/fail_shr",
////	TopicHealthFailedBackups:    "health/failed_backups/fail_bkp",
////	TopicRuntimePeakTemp:        "runtime/peak_temperature/peak_tem",
////	TopicRuntimePeakFan:         "runtime/peak_fan/peak_fan",
////	TopicRuntimeLifeDrives:      "runtime/life_drives/life_ssd",
////	TopicStorageUsedSystem:      "storage/used_system_drive/used_sys",
////	TopicStorageUsedShares:      "storage/used_share_drives/used_shr",
////	TopicStorageUsedBackups:     "storage/used_backup_drives/used_bkp",
////}
////
////func (m TopicHost) String() string {
////	if m < 0 || int(m) >= len(topicHost) {
////		return ""
////	}
////	return topicHost[m]
////}
//
//type metricBuilder struct {
//	Topic    string
//	Load     func(int) MetricValue
//	Payload  MetricValue
//	Order    []string
//	Children map[string]*metricBuilder
//	OnChange func(previous, current MetricValue)
//}
//
//type MetricValue struct {
//	OK    bool   `json:"ok"`
//	Unit  string `json:"unit,omitempty"`
//	Value string `json:"value,omitempty"`
//}
//
//type MetricDisplay struct {
//	Format      string
//	Row         int
//	Col         int
//	LabelWidth  int
//	ValueWidth  int
//	ScaledWidth int
//	LabelAlign  string
//	ValueAlign  string
//	Prefix      string
//	Spacer      string
//	Suffix      string
//	Topic       string
//}
//
//func NewMetricDisplayArray() [][]MetricDisplay {
//	displays := make([][]MetricDisplay, 4)
//	for i := range displays {
//		displays[i] = make([]MetricDisplay, 4)
//	}
//
//	displays[0][0] = MetricDisplay{Format: "%s", Row: 0, Col: 0, LabelWidth: 12, ValueWidth: 5, ScaledWidth: 20, LabelAlign: "left", ValueAlign: "right", Prefix: "[", Spacer: " ", Suffix: "]", Topic: TopicComputeUsedProcessor.Topic()}
//	displays[0][1] = MetricDisplay{Format: "%s", Row: 0, Col: 1, LabelWidth: 12, ValueWidth: 5, ScaledWidth: 20, LabelAlign: "left", ValueAlign: "right", Prefix: "[", Spacer: " ", Suffix: "]", Topic: TopicComputeUsedMemory.Topic()}
//	displays[0][2] = MetricDisplay{Format: "%s", Row: 0, Col: 2, LabelWidth: 12, ValueWidth: 5, ScaledWidth: 20, LabelAlign: "left", ValueAlign: "right", Prefix: "[", Spacer: " ", Suffix: "]", Topic: TopicRuntimePeakTemp.Topic()}
//	displays[0][3] = MetricDisplay{Format: "%s", Row: 0, Col: 3, LabelWidth: 12, ValueWidth: 5, ScaledWidth: 20, LabelAlign: "left", ValueAlign: "right", Prefix: "[", Spacer: " ", Suffix: "]", Topic: TopicRuntimePeakFan.Topic()}
//
//	displays[1][0] = MetricDisplay{Format: "%s", Row: 1, Col: 0, LabelWidth: 12, ValueWidth: 5, ScaledWidth: 20, LabelAlign: "left", ValueAlign: "right", Prefix: "[", Spacer: " ", Suffix: "]", Topic: TopicStorageUsedSystem.Topic()}
//	displays[1][1] = MetricDisplay{Format: "%s", Row: 1, Col: 1, LabelWidth: 12, ValueWidth: 5, ScaledWidth: 20, LabelAlign: "left", ValueAlign: "right", Prefix: "[", Spacer: " ", Suffix: "]", Topic: TopicStorageUsedShares.Topic()}
//	displays[1][2] = MetricDisplay{Format: "%s", Row: 1, Col: 2, LabelWidth: 12, ValueWidth: 5, ScaledWidth: 20, LabelAlign: "left", ValueAlign: "right", Prefix: "[", Spacer: " ", Suffix: "]", Topic: TopicStorageUsedBackups.Topic()}
//	displays[1][3] = MetricDisplay{Format: "%s", Row: 1, Col: 3, LabelWidth: 12, ValueWidth: 5, ScaledWidth: 20, LabelAlign: "left", ValueAlign: "right", Prefix: "[", Spacer: " ", Suffix: "]", Topic: TopicRuntimeLifeDrives.Topic()}
//
//	displays[2][0] = MetricDisplay{Format: "%s", Row: 2, Col: 0, LabelWidth: 12, ValueWidth: 5, ScaledWidth: 20, LabelAlign: "left", ValueAlign: "right", Prefix: "[", Spacer: " ", Suffix: "]", Topic: TopicHealthFailedServices.Topic()}
//	displays[2][1] = MetricDisplay{Format: "%s", Row: 2, Col: 1, LabelWidth: 12, ValueWidth: 5, ScaledWidth: 20, LabelAlign: "left", ValueAlign: "right", Prefix: "[", Spacer: " ", Suffix: "]", Topic: TopicHealthFailedShares.Topic()}
//	displays[2][2] = MetricDisplay{Format: "%s", Row: 2, Col: 2, LabelWidth: 12, ValueWidth: 5, ScaledWidth: 20, LabelAlign: "left", ValueAlign: "right", Prefix: "[", Spacer: " ", Suffix: "]", Topic: TopicHealthFailedBackups.Topic()}
//	displays[2][3] = MetricDisplay{Format: "%s", Row: 2, Col: 3, LabelWidth: 12, ValueWidth: 5, ScaledWidth: 20, LabelAlign: "left", ValueAlign: "right", Prefix: "[", Spacer: " ", Suffix: "]", Topic: TopicComputeAllocatedMemory.Topic()}
//
//	return displays
//}
//
//func (m *metricBuilder) GetNamespace() (string, error) {
//	parts := strings.Split(m.Topic, "/")
//	if len(parts) <= topicNamespaceIndex {
//		return "", fmt.Errorf("invalid topic [%s], namespace/# not found", m.Topic)
//	}
//	return parts[topicNamespaceIndex], nil
//}
//
//func (m *metricBuilder) GetHostname() (string, error) {
//	parts := strings.Split(m.Topic, "/")
//	if len(parts) <= topicHostIndex {
//		return "", fmt.Errorf("invalid topic [%s], +/hostname/# not found", m.Topic)
//	}
//	return parts[topicHostIndex], nil
//}
//
//func (m *metricBuilder) GetType() (string, error) {
//	parts := strings.Split(m.Topic, "/")
//	if len(parts) <= topicHostIndex {
//		return "", fmt.Errorf("invalid topic [%s], +/+/type/# not found", m.Topic)
//	}
//	return parts[topicTypeIndex], nil
//}
//
//func (m *metricBuilder) GetCategory() string {
//	parts := strings.Split(m.Topic, "/")
//	if len(parts) <= topicCategoryIndex {
//		return ""
//	}
//	return parts[topicCategoryIndex]
//}
//
//func (m *metricBuilder) GetDescription() string {
//	parts := strings.Split(m.Topic, "/")
//	if len(parts) <= topicDescriptionIndex {
//		return ""
//	}
//	return parts[topicDescriptionIndex]
//}
//
//func (m *metricBuilder) GetLabel() string {
//	parts := strings.Split(m.Topic, "/")
//	if len(parts) <= topicLabelIndex {
//		return ""
//	}
//	return parts[topicLabelIndex]
//}
//
//func (m *metricBuilder) AsInt() (int, error) {
//	return strconv.Atoi(m.Payload.Value)
//}
//
//func (m *metricBuilder) AsFloat() (float64, error) {
//	return strconv.ParseFloat(m.Payload.Value, 64)
//}
//
//func (m *metricBuilder) AsBool() (bool, error) {
//	v := strings.ToLower(m.Payload.Value)
//	if v == "true" || v == "1" {
//		return true, nil
//	}
//	if v == "false" || v == "0" {
//		return false, nil
//	}
//	return false, fmt.Errorf("invalid boolean value: %s", m.Payload.Value)
//}
//
//func (m *metricBuilder) Update(current MetricValue) {
//	if m.HasChanged(&metricBuilder{Payload: current}) {
//		previous := m.Payload
//		m.Payload = current
//		m.OnChange(previous, current)
//	}
//}
//
//func (m *metricBuilder) HasChanged(other *metricBuilder) bool {
//	return m.Payload.OK != other.Payload.OK ||
//		m.Payload.Unit != other.Payload.Unit ||
//		m.Payload.Value != other.Payload.Value
//}
//
//func CacheMetrics(hostname string, schemaPath string) (map[string]*metricBuilder, error) {
//	if hostname == "" {
//		return nil, fmt.Errorf("hostname not defined")
//	}
//	topicNamespace := "supervisor/" + hostname
//	metricsHost := []metricBuilder{
//		// HOST COMPUTE
//		{Topic: topicNamespace + "/host/compute/used_processor/used_cpu"},
//		{Topic: topicNamespace + "/host/compute/used_memory/used_ram"},
//		{Topic: topicNamespace + "/host/compute/allocated_memory/aloc_ram"},
//		{Topic: topicNamespace + "/host/compute"},
//		// HOST HEALTH
//		{Topic: topicNamespace + "/host/health/failed_services/fail_svc"},
//		{Topic: topicNamespace + "/host/health/failed_shares/fail_shr"},
//		{Topic: topicNamespace + "/host/health/failed_backups/fail_bkp"},
//		{Topic: topicNamespace + "/host/health"},
//		// HOST RUNTIME
//		{Topic: topicNamespace + "/host/runtime/peak_temperature/peak_tem"},
//		{Topic: topicNamespace + "/host/runtime/peak_fan/peak_fan"},
//		{Topic: topicNamespace + "/host/runtime/life_drives/life_ssd"},
//		{Topic: topicNamespace + "/host/runtime"},
//		// HOST STORAGE
//		{Topic: topicNamespace + "/host/storage/used_system_drive/used_sys"},
//		{Topic: topicNamespace + "/host/storage/used_share_drives/used_shr"},
//		{Topic: topicNamespace + "/host/storage/used_backup_drives/used_bkp"},
//		{Topic: topicNamespace + "/host/storage"},
//		// HOST
//		{Topic: topicNamespace + "/host"},
//	}
//	serviceSlice, err := GetServices(hostname, schemaPath)
//	if err != nil {
//		return nil, err
//	}
//	var metricsService []metricBuilder
//	for _, service := range serviceSlice {
//		metricsService = append(metricsService,
//			metricBuilder{Topic: topicNamespace + "/service/" + service + "/version/ver"},
//			metricBuilder{Topic: topicNamespace + "/service/" + service + "/processor/cpu"},
//			metricBuilder{Topic: topicNamespace + "/service/" + service + "/memory/ram"},
//			metricBuilder{Topic: topicNamespace + "/service/" + service + "/backups/bkp"},
//			metricBuilder{Topic: topicNamespace + "/service/" + service + "/all_ok/aok"},
//			metricBuilder{Topic: topicNamespace + "/service/" + service + "/configured/cfg"},
//			metricBuilder{Topic: topicNamespace + "/service/" + service + "/restarts/rst"},
//			metricBuilder{Topic: topicNamespace + "/service/" + service + "/runtime/run"},
//			metricBuilder{Topic: topicNamespace + "/service/" + service},
//		)
//	}
//	metricsService = append(metricsService, metricBuilder{Topic: topicNamespace + "/service"})
//	allMetrics := append(metricsHost, metricsService...)
//	metricsTree := make(map[string]*metricBuilder)
//	for _, metric := range allMetrics {
//		topicRelative := strings.TrimPrefix(metric.Topic, topicNamespace+"/")
//		topicParts := strings.Split(topicRelative, "/")
//		currentLevel := metricsTree
//		var parentNode *metricBuilder
//		for partIndex, topicPart := range topicParts {
//			currentNode, exists := currentLevel[topicPart]
//			if !exists {
//				currentNode = &metricBuilder{Children: make(map[string]*metricBuilder)}
//				currentLevel[topicPart] = currentNode
//				if parentNode != nil {
//					parentNode.Order = append(parentNode.Order, topicPart)
//				}
//			}
//			parentNode = currentNode
//			if partIndex == len(topicParts)-1 {
//				currentNode.Topic = metric.Topic
//				currentNode.Load = metric.Load
//				currentNode.Payload = metric.Payload
//				currentNode.OnChange = metric.OnChange
//			}
//			currentLevel = currentNode.Children
//		}
//	}
//	return metricsTree, nil
//}
//
//func GetMetrics(metrics map[string]*metricBuilder, topic string) []*metricBuilder {
//	topic = strings.TrimSpace(topic)
//	if topic == "" {
//		return []*metricBuilder{}
//	}
//	topicParts := strings.Split(topic, "/")
//	currentLevel := metrics
//	var targetNode *metricBuilder
//	for _, topicPart := range topicParts {
//		var exists bool
//		targetNode, exists = currentLevel[topicPart]
//		if !exists {
//			return []*metricBuilder{}
//		}
//		currentLevel = targetNode.Children
//	}
//	var results []*metricBuilder
//	var traverse func(node *metricBuilder)
//	traverse = func(node *metricBuilder) {
//		if node == nil {
//			return
//		}
//		if node.Topic != "" {
//			results = append(results, node)
//		}
//		for _, childKey := range node.Order {
//			traverse(node.Children[childKey])
//		}
//	}
//	traverse(targetNode)
//	return results
//}
//
//func GetMetric(metrics map[string]*metricBuilder, topic string) *metricBuilder {
//	metricSlice := GetMetrics(metrics, topic)
//	if len(metricSlice) > 0 {
//		return metricSlice[0]
//	}
//	return nil
//}
