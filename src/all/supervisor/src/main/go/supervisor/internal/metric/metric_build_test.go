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
