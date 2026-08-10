package cmd

import (
	"testing"
	"time"
)

func TestCmd_MakePeriods(t *testing.T) {
	tests := []struct {
		name          string
		poll          string
		aggregate     string
		expectedPoll  time.Duration
		expectedAgg   time.Duration
		expectedError bool
	}{
		{name: "valid_multiple", poll: "5m", aggregate: "15m", expectedPoll: 5 * time.Minute, expectedAgg: 15 * time.Minute, expectedError: false},
		{name: "equal_periods", poll: "5m", aggregate: "5m", expectedPoll: 5 * time.Minute, expectedAgg: 5 * time.Minute, expectedError: false},
		{name: "bad_poll_format", poll: "nope", aggregate: "15m", expectedError: true},
		{name: "poll_zero", poll: "0s", aggregate: "15m", expectedError: true},
		{name: "poll_negative", poll: "-5m", aggregate: "15m", expectedError: true},
		{name: "bad_aggregate_format", poll: "5m", aggregate: "nope", expectedError: true},
		{name: "aggregate_zero", poll: "5m", aggregate: "0s", expectedError: true},
		{name: "not_whole_multiple", poll: "5m", aggregate: "12m", expectedError: true},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			poll, aggregate, err := makePeriods(test.poll, test.aggregate)
			if (err != nil) != test.expectedError {
				t.Fatalf("error mismatch: got %v want error=%v", err, test.expectedError)
			}
			if test.expectedError {
				return
			}
			if poll != test.expectedPoll {
				t.Errorf("poll: got %s want %s", poll, test.expectedPoll)
			}
			if aggregate != test.expectedAgg {
				t.Errorf("aggregate: got %s want %s", aggregate, test.expectedAgg)
			}
		})
	}
}
