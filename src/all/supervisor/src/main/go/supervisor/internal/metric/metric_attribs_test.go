package metric

import (
	"strings"
	"testing"
)

func TestMetricAccessors_GetIDName(t *testing.T) {
	testCases := []struct {
		name          string
		id            ID
		expectedName  string
		expectedError bool
	}{
		{name: "host", id: MetricHost, expectedName: "host", expectedError: false},
		{name: "host metric", id: MetricHostUsedProcessor, expectedName: "host/used_processor", expectedError: false},
		{name: "service", id: MetricService, expectedName: "service", expectedError: false},
		{name: "service metric", id: MetricServiceHealthStatus, expectedName: "service/health_status", expectedError: false},
		{name: "out of range", id: MetricMax, expectedName: "", expectedError: false},
	}
	for _, testCase := range testCases {
		t.Run(testCase.name, func(t *testing.T) {
			if name := GetIDName(testCase.id); name != testCase.expectedName {
				t.Errorf("name: got %v want %v", name, testCase.expectedName)
			}
		})
	}
}

func TestMetricAccessors_GetIDNameIsUniqueAndTemplated(t *testing.T) {
	names := map[string]ID{}
	for _, id := range GetIDs() {
		name := GetIDName(id)
		if name == "" {
			t.Errorf("%v: name must not be empty", id)
			continue
		}
		if strings.Contains(name, "$") {
			t.Errorf("%v: name [%s] must hold no template placeholder", id, name)
		}
		if seen, found := names[name]; found {
			t.Errorf("%v: name [%s] is already used by %v", id, name, seen)
		}
		names[name] = id
	}
}
