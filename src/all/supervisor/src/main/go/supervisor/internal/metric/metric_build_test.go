package metric

import (
	"fmt"
	"strings"
	"supervisor/internal/testutil"
	"testing"
)

func TestMetricBuild_IDToAndFromTopic(t *testing.T) {
	tests := []struct {
		name          string
		expectedError bool
	}{
		{
			name:          "happy",
			expectedError: false,
		},
	}
	for _, tt := range tests {
		seenTags := make(map[string]bool)
		seenTopics := make(map[string]bool)
		for _, id := range GetIDs() {
			t.Run(fmt.Sprintf("%s_ID_%02d", tt.name, id), func(t *testing.T) {
				serviceName := ServiceNameUnset
				if strings.Contains(metricBuildersByID[id].template, "$SERVICE") {
					serviceName = "a-service"
				}
				topic, tags, err := buildFromID(id, "labnode-one", serviceName, "data")
				if (err != nil) != tt.expectedError {
					t.Fatalf("Got err = %v, expected error? %t", err, tt.expectedError)
				}
				tagsStr := testutil.MapToString(tags)
				if seenTags[tagsStr] && tagsStr != "" {
					t.Fatalf("Duplicate tag set found [%s] for metric ID [%d]", tagsStr, id)
				}
				seenTags[tagsStr] = true
				if seenTopics[topic] {
					t.Fatalf("Duplicate topic found [%s] for metric ID [%d]", tagsStr, id)
				}
				seenTopics[topic] = true
				t.Logf("Metric ID [%02d] -> topic [%s], tags [%s]", id, topic, tagsStr)
				builtID, builtTags, err := buildFromTopic(topic)
				if (err != nil) != tt.expectedError {
					t.Fatalf("Got err = %v, expected error? %t", err, tt.expectedError)
				}
				builtTagsStr := testutil.MapToString(builtTags)
				t.Logf("Metric Topic [%s] -> ID [%02d], tags [%s]", topic, builtID, builtTagsStr)
				if builtID != id {
					t.Fatalf("ID mismatch: got %d, expected %d", builtID, id)
				}
				if builtTagsStr != tagsStr {
					t.Fatalf("Tags mismatch: got %s, expected %s", builtTagsStr, tagsStr)
				}
			})
		}
	}
}

func TestMetricBuild_TopicToAndFromID(t *testing.T) {
	tests := []struct {
		name                   string
		topic                  string
		hostName               string
		scope                  string
		serviceName            string
		expected               ID
		expectedFromIDError    bool
		expectedFromTopicError bool
	}{
		{
			name:                   "happy_host",
			topic:                  "supervisor/host/data/host/used_processor",
			hostName:               "host",
			scope:                  "data",
			serviceName:            ServiceNameUnset,
			expected:               MetricHostUsedProcessor,
			expectedFromIDError:    false,
			expectedFromTopicError: false,
		},
		{
			name:                   "happy_service",
			topic:                  "supervisor/labnode-one/data/service/service/used_processor",
			hostName:               "labnode-one",
			scope:                  "data",
			serviceName:            "service",
			expected:               MetricServiceUsedProcessor,
			expectedFromIDError:    false,
			expectedFromTopicError: false,
		},
		{
			name:                   "happy_meta_scope",
			topic:                  "supervisor/labnode-one/meta/host/used_processor",
			hostName:               "labnode-one",
			scope:                  "meta",
			serviceName:            ServiceNameUnset,
			expected:               MetricHostUsedProcessor,
			expectedFromIDError:    false,
			expectedFromTopicError: false,
		},
		{
			name:                   "happy_meta_scope_service",
			topic:                  "supervisor/labnode-one/meta/service/a-service/used_processor",
			hostName:               "labnode-one",
			scope:                  "meta",
			serviceName:            "a-service",
			expected:               MetricServiceUsedProcessor,
			expectedFromIDError:    false,
			expectedFromTopicError: false,
		},
		{
			name:                   "sad_invalid_scope",
			topic:                  "supervisor/labnode-one/data/host/used_processor",
			hostName:               "labnode-one",
			scope:                  "invalid",
			serviceName:            ServiceNameUnset,
			expected:               MetricHostUsedProcessor,
			expectedFromIDError:    true,
			expectedFromTopicError: false,
		},
		{
			name:                   "sad_empty_scope",
			topic:                  "supervisor/labnode-one/data/host/used_processor",
			hostName:               "labnode-one",
			scope:                  "",
			serviceName:            ServiceNameUnset,
			expected:               MetricHostUsedProcessor,
			expectedFromIDError:    true,
			expectedFromTopicError: false,
		},
		{
			name:                   "sad_no_service",
			topic:                  "supervisor/labnode-one/data/service/a-service/used_processor",
			hostName:               "labnode-one",
			scope:                  "data",
			serviceName:            ServiceNameUnset,
			expected:               MetricServiceUsedProcessor,
			expectedFromIDError:    true,
			expectedFromTopicError: false,
		},
		{
			name:                   "sad_badly_named_service_topic_tilda",
			topic:                  "supervisor/labnode-one/data/service/a~service/used_processor",
			hostName:               "labnode-one",
			scope:                  "data",
			serviceName:            "aservice",
			expected:               MetricServiceUsedProcessor,
			expectedFromIDError:    false,
			expectedFromTopicError: true,
		},
		{
			name:                   "sad_badly_named_service_id_tilda",
			topic:                  "supervisor/labnode-one/data/service/aservice/used_processor",
			hostName:               "labnode-one",
			scope:                  "data",
			serviceName:            "a~service",
			expected:               MetricServiceUsedProcessor,
			expectedFromIDError:    true,
			expectedFromTopicError: false,
		},
		{
			name:                   "sad_badly_named_service_id_slashes",
			topic:                  "supervisor/labnode-one/data/service/a-service/used_processor",
			hostName:               "labnode-one",
			scope:                  "data",
			serviceName:            "a/service",
			expected:               MetricServiceUsedProcessor,
			expectedFromIDError:    true,
			expectedFromTopicError: false,
		},
		{
			name:                   "sad_badly_named_service_topic_slashes",
			topic:                  "supervisor/labnode-one/data/service/a/service/used_processor",
			hostName:               "labnode-one",
			scope:                  "data",
			serviceName:            "a-service",
			expected:               MetricServiceUsedProcessor,
			expectedFromIDError:    false,
			expectedFromTopicError: true,
		},
		{
			name:                   "sad_meta",
			topic:                  "supervisor/labnode-one/data",
			expectedFromIDError:    false,
			expectedFromTopicError: true,
		},
		{
			name:                   "sad_command",
			topic:                  strings.NewReplacer("$HOST", "labnode-one").Replace(templateCommand),
			expectedFromIDError:    false,
			expectedFromTopicError: true,
		},
		{
			name:                   "sad_snapshot",
			topic:                  strings.NewReplacer("$HOST", "labnode-one").Replace(templateSnapshot),
			expectedFromIDError:    false,
			expectedFromTopicError: true,
		},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			id, tags, err := buildFromTopic(tt.topic)
			if (err != nil) != tt.expectedFromTopicError {
				t.Fatalf("buildFromTopic(): error = %v, expected error? %t", err, tt.expectedFromTopicError)
			}
			if tt.expectedFromTopicError {
				return
			}
			if id != tt.expected {
				t.Fatalf("ID mismatch: got %d, expected %d", id, tt.expected)
			}
			builtTopic, builtTags, err := buildFromID(id, tt.hostName, tt.serviceName, tt.scope)
			if (err != nil) != tt.expectedFromIDError {
				t.Fatalf("buildFromID(): error = %v, expected error? %t", err, tt.expectedFromIDError)
			}
			if tt.expectedFromIDError {
				return
			}
			if builtTopic != tt.topic {
				t.Fatalf("Topic mismatch: got %s, expected %s", builtTopic, tt.topic)
			}
			if testutil.MapToString(builtTags) != testutil.MapToString(tags) {
				t.Fatalf("Tags mismatch: got %s, expected %s", testutil.MapToString(builtTags), testutil.MapToString(tags))
			}
		})
	}
}

func TestMetricBuild_HostAggregate(t *testing.T) {
	tests := []struct {
		name             string
		metricID         ID
		expectedEnrolled bool
	}{
		{name: "a bursty rate is excluded", metricID: MetricHostUsedDiskTime, expectedEnrolled: false},
		{name: "a bursty network rate is excluded", metricID: MetricHostUsedNetwork, expectedEnrolled: false},
		{name: "a bursty processor rate is excluded", metricID: MetricHostUsedProcessor, expectedEnrolled: false},
		{name: "a fault count is enrolled", metricID: MetricHostFailedShares, expectedEnrolled: true},
		{name: "a space level is enrolled", metricID: MetricHostUsedHomeSpace, expectedEnrolled: true},
		{name: "a memory level is enrolled", metricID: MetricHostUsedMemory, expectedEnrolled: true},
		{name: "a swap level is enrolled", metricID: MetricHostUsedSwapSpace, expectedEnrolled: true},
		{name: "an always ruled metric is excluded", metricID: MetricHostHaltedBackupStages, expectedEnrolled: false},
		{name: "a service scoped metric is excluded", metricID: MetricServiceUsedMemory, expectedEnrolled: false},
	}
	enrolled := map[ID]bool{}
	for _, id := range GetIDDeps(MetricHost) {
		enrolled[id] = true
	}
	if len(enrolled) == 0 {
		t.Fatalf("aggregate: got no enrolled metrics, want the host metrics that can fail")
	}
	siblings := map[ID]bool{}
	for _, id := range GetIDPulseRule(MetricHost).Siblings() {
		siblings[id] = true
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			if enrolled[test.metricID] != test.expectedEnrolled {
				t.Errorf("dependencies: got %v want %v", enrolled[test.metricID], test.expectedEnrolled)
			}
			if siblings[test.metricID] != test.expectedEnrolled {
				t.Errorf("rule siblings: got %v want %v", siblings[test.metricID], test.expectedEnrolled)
			}
		})
	}
}

func TestMetricBuild_ClusterTopic(t *testing.T) {
	tests := []struct {
		name          string
		hostName      string
		expectedTopic string
		expectedError bool
	}{
		{
			name:          "cluster_host",
			hostName:      GetIDHost(MetricCluster, "labnode-one"),
			expectedTopic: "supervisor/all/data/cluster",
			expectedError: false,
		},
		{
			name:          "host_metric_keeps_its_host",
			hostName:      GetIDHost(MetricHost, "labnode-one"),
			expectedTopic: "supervisor/labnode-one/data/host",
			expectedError: false,
		},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			id := MetricCluster
			if tt.hostName != HostAll {
				id = MetricHost
			}
			topic, _, err := buildFromID(id, tt.hostName, ServiceNameUnset, ScopeData)
			if (err != nil) != tt.expectedError {
				t.Fatalf("err: got %v want error %t", err, tt.expectedError)
			}
			if topic != tt.expectedTopic {
				t.Errorf("topic: got %s want %s", topic, tt.expectedTopic)
			}
			if GetIDKind(MetricCluster) != MetricKindCluster {
				t.Errorf("kind: got %v want %v", GetIDKind(MetricCluster), MetricKindCluster)
			}
		})
	}
}
