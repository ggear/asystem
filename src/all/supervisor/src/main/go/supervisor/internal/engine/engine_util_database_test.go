package engine

import (
	"context"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"
)

func TestEngineUtilDatabase_Backoff(t *testing.T) {
	tests := []struct {
		name     string
		attempt  int
		expected time.Duration
	}{
		{"first attempt waits the base", 0, databaseRetry},
		{"each attempt doubles", 2, 4 * databaseRetry},
		{"growth stops at the interval", 10, databaseInterval},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			if actual := databaseBackoff(testCase.attempt); actual != testCase.expected {
				t.Errorf("backoff: got [%s] want [%s]", actual, testCase.expected)
			}
		})
	}
}

func TestEngineUtilDatabase_Reachable(t *testing.T) {
	healthy := httptest.NewServer(http.HandlerFunc(func(writer http.ResponseWriter, _ *http.Request) { writer.WriteHeader(http.StatusOK) }))
	defer healthy.Close()
	closed := httptest.NewServer(http.NotFoundHandler())
	closedEndpoint := strings.TrimPrefix(closed.URL, "http://")
	closed.Close()
	tests := []struct {
		name          string
		endpoint      string
		expectedError bool
	}{
		{"a listening server is reachable", strings.TrimPrefix(healthy.URL, "http://"), false},
		{"a closed port is not", closedEndpoint, true},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			err := databaseReachable(context.Background(), testCase.endpoint)
			if (err != nil) != testCase.expectedError {
				t.Errorf("reachable: got error [%v] want error [%t]", err, testCase.expectedError)
			}
		})
	}
}
