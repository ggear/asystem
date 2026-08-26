package engine

import (
	"context"
	"net"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"
)

func TestEngineDatabase_Backoff(t *testing.T) {
	tests := []struct {
		name            string
		attempt         int
		expectedBackoff time.Duration
	}{
		{name: "happy first attempt waits the retry", attempt: 0, expectedBackoff: databaseRetry},
		{name: "happy second attempt doubles", attempt: 1, expectedBackoff: 2 * databaseRetry},
		{name: "happy later attempts cap at the interval", attempt: 9, expectedBackoff: databaseInterval},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			if got := databaseBackoff(testCase.attempt); got != testCase.expectedBackoff {
				t.Errorf("backoff: got %v want %v", got, testCase.expectedBackoff)
			}
		})
	}
}

func TestEngineDatabase_Reachable(t *testing.T) {
	healthy := httptest.NewServer(http.HandlerFunc(func(writer http.ResponseWriter, _ *http.Request) {
		writer.WriteHeader(http.StatusOK)
	}))
	defer healthy.Close()
	missing := httptest.NewServer(http.HandlerFunc(func(writer http.ResponseWriter, _ *http.Request) {
		writer.WriteHeader(http.StatusNotFound)
	}))
	defer missing.Close()
	listener, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		t.Fatalf("listen: %v", err)
	}
	closed := listener.Addr().String()
	if closeErr := listener.Close(); closeErr != nil {
		t.Fatalf("close: %v", closeErr)
	}
	tests := []struct {
		name          string
		endpoint      string
		expectedError bool
	}{
		{name: "happy answered health is reachable", endpoint: healthy.Listener.Addr().String(), expectedError: false},
		{name: "happy unknown endpoint still answers so is reachable", endpoint: missing.Listener.Addr().String(), expectedError: false},
		{name: "sad refused connection is unreachable", endpoint: closed, expectedError: true},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			reachErr := databaseReachable(context.Background(), testCase.endpoint)
			if (reachErr != nil) != testCase.expectedError {
				t.Errorf("reachable: got %v want error %v", reachErr, testCase.expectedError)
			}
		})
	}
}
