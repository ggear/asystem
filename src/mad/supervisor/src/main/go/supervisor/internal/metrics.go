package internal

import (
	"fmt"
	"os"
	"strconv"
	"strings"
)

const (
	TopicNamespaceIndex   = 0
	TopicHostIndex        = 1
	TopicTypeIndex        = 2
	TopicCategoryIndex    = 3
	TopicDescriptionIndex = 4
	TopicLabelIndex       = 5
)

type Metric struct {
	Topic    string
	Load     func(int) MetricValue
	Payload  MetricValue
	OnChange func(previous, current MetricValue)
}

type MetricValue struct {
	OK    bool   `json:"ok"`
	Unit  string `json:"unit,omitempty"`
	Value string `json:"value,omitempty"`
}

type MetricNode struct {
	Metric   *Metric
	Children map[string]*MetricNode
	Order    []string
}

func (m *Metric) GetNamespace() (string, error) {
	parts := strings.Split(m.Topic, "/")
	if len(parts) <= TopicNamespaceIndex {
		return "", fmt.Errorf("invalid topic [%s], namespace/# not found", m.Topic)
	}
	return parts[TopicNamespaceIndex], nil
}

func (m *Metric) GetHostname() (string, error) {
	parts := strings.Split(m.Topic, "/")
	if len(parts) <= TopicHostIndex {
		return "", fmt.Errorf("invalid topic [%s], +/hostname/# not found", m.Topic)
	}
	return parts[TopicHostIndex], nil
}

func (m *Metric) GetType() (string, error) {
	parts := strings.Split(m.Topic, "/")
	if len(parts) <= TopicHostIndex {
		return "", fmt.Errorf("invalid topic [%s], +/+/type/# not found", m.Topic)
	}
	return parts[TopicTypeIndex], nil
}

func (m *Metric) GetCategory() string {
	parts := strings.Split(m.Topic, "/")
	if len(parts) <= TopicCategoryIndex {
		return ""
	}
	return parts[TopicCategoryIndex]
}

func (m *Metric) GetDescription() string {
	parts := strings.Split(m.Topic, "/")
	if len(parts) <= TopicDescriptionIndex {
		return ""
	}
	return parts[TopicDescriptionIndex]
}

func (m *Metric) GetLabel() string {
	parts := strings.Split(m.Topic, "/")
	if len(parts) <= TopicLabelIndex {
		return ""
	}
	return parts[TopicLabelIndex]
}

func (m *Metric) AsInt() (int, error) {
	return strconv.Atoi(m.Payload.Value)
}

func (m *Metric) AsFloat() (float64, error) {
	return strconv.ParseFloat(m.Payload.Value, 64)
}

func (m *Metric) AsBool() (bool, error) {
	v := strings.ToLower(m.Payload.Value)
	if v == "true" || v == "1" {
		return true, nil
	}
	if v == "false" || v == "0" {
		return false, nil
	}
	return false, fmt.Errorf("invalid boolean value: %s", m.Payload.Value)
}

func (m *Metric) Update(current MetricValue) {
	if m.HasChanged(&Metric{Payload: current}) {
		previous := m.Payload
		m.Payload = current
		m.OnChange(previous, current)
	}
}

func (m *Metric) HasChanged(other *Metric) bool {
	return m.Payload.OK != other.Payload.OK ||
		m.Payload.Unit != other.Payload.Unit ||
		m.Payload.Value != other.Payload.Value
}

func CacheMetrics() map[string]*MetricNode {
	hostname, err := os.Hostname()
	if err != nil {
		hostname = "unknown"
	}
	topicNamespace := "supervisor/" + hostname

	metricsHost := []Metric{
		// HOST COMPUTE
		{Topic: topicNamespace + "/host/compute/used_processor/used_cpu"},
		{Topic: topicNamespace + "/host/compute/used_memory/used_ram"},
		{Topic: topicNamespace + "/host/compute/allocated_memory/aloc_ram"},
		{Topic: topicNamespace + "/host/compute"},
		// HOST HEALTH
		{Topic: topicNamespace + "/host/health/failed_services/fail_svc"},
		{Topic: topicNamespace + "/host/health/failed_shares/fail_shr"},
		{Topic: topicNamespace + "/host/health/failed_backups/fail_bkp"},
		{Topic: topicNamespace + "/host/health"},
		// HOST RUNTIME
		{Topic: topicNamespace + "/host/runtime/peak_temperature/peak_tem"},
		{Topic: topicNamespace + "/host/runtime/peak_fan/peak_fan"},
		{Topic: topicNamespace + "/host/runtime/life_drives/life_ssd"},
		{Topic: topicNamespace + "/host/runtime"},
		// HOST STORAGE
		{Topic: topicNamespace + "/host/storage/used_system_drive/used_sys"},
		{Topic: topicNamespace + "/host/storage/used_share_drives/used_shr"},
		{Topic: topicNamespace + "/host/storage/used_backup_drives/used_bkp"},
		{Topic: topicNamespace + "/host/storage"},
		// HOST
		{Topic: topicNamespace + "/host"},
	}

	// TODO
	if serviceSlice, err := GetServices(hostname, SchemaDefaultPath); err != nil {
		fmt.Println(err)
	} else {
		fmt.Println(serviceSlice)
	}
	metricsService := []Metric{
		// SERVICE
		{Topic: topicNamespace + "/service/monitor/version/ver"},
		{Topic: topicNamespace + "/service/monitor/processor/cpu"},
		{Topic: topicNamespace + "/service/monitor/memory/ram"},
		{Topic: topicNamespace + "/service/monitor/backups/bkp"},
		{Topic: topicNamespace + "/service/monitor/all_ok/aok"},
		{Topic: topicNamespace + "/service/monitor/configured/cfg"},
		{Topic: topicNamespace + "/service/monitor/restarts/rst"},
		{Topic: topicNamespace + "/service/monitor/runtime/run"},
		{Topic: topicNamespace + "/service/monitor"},
	}
	metricsService = append(metricsService, Metric{Topic: topicNamespace + "/service"})

	allMetrics := append(metricsHost, metricsService...)
	metricsTree := make(map[string]*MetricNode)
	for _, metric := range allMetrics {
		topicRelative := strings.TrimPrefix(metric.Topic, topicNamespace+"/")
		topicParts := strings.Split(topicRelative, "/")
		currentLevel := metricsTree
		var parentNode *MetricNode
		for partIndex, topicPart := range topicParts {
			currentNode, exists := currentLevel[topicPart]
			if !exists {
				currentNode = &MetricNode{Children: make(map[string]*MetricNode)}
				currentLevel[topicPart] = currentNode
				if parentNode != nil {
					parentNode.Order = append(parentNode.Order, topicPart)
				}
			}
			parentNode = currentNode
			if partIndex == len(topicParts)-1 {
				currentNode.Metric = &metric
			}
			currentLevel = currentNode.Children
		}
	}
	return metricsTree
}

func GetMetrics(metrics map[string]*MetricNode, topic string, ignoreRoot bool) []*Metric {
	topic = strings.TrimSpace(topic)
	if topic == "" {
		return []*Metric{}
	}
	topicParts := strings.Split(topic, "/")
	currentLevel := metrics
	var targetNode *MetricNode
	for _, topicPart := range topicParts {
		var exists bool
		targetNode, exists = currentLevel[topicPart]
		if !exists {
			return []*Metric{}
		}
		currentLevel = targetNode.Children
	}
	var results []*Metric
	var traverse func(node *MetricNode)
	traverse = func(node *MetricNode) {
		if node == nil {
			return
		}
		if node.Metric != nil {
			results = append(results, node.Metric)
		}
		for _, childKey := range node.Order {
			traverse(node.Children[childKey])
		}
	}
	if ignoreRoot {
		for _, childKey := range targetNode.Order {
			traverse(targetNode.Children[childKey])
		}
	} else {
		traverse(targetNode)
	}
	return results
}

func GetMetric(metrics map[string]*MetricNode, topic string) *Metric {
	metricSlice := GetMetrics(metrics, topic, false)
	if len(metricSlice) > 0 {
		return metricSlice[0]
	}
	return nil
}
