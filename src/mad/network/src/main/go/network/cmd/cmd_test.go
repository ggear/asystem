package cmd

import (
	"testing"
	"time"
)

func TestCmd_MakePeriods(t *testing.T) {
	tests := []struct {
		name              string
		poll              string
		aggregate         string
		expectedPoll      time.Duration
		expectedAggregate time.Duration
		expectedError     bool
	}{
		{name: "valid_multiple", poll: "5m", aggregate: "15m", expectedPoll: 5 * time.Minute, expectedAggregate: 15 * time.Minute, expectedError: false},
		{name: "equal_periods", poll: "5m", aggregate: "5m", expectedPoll: 5 * time.Minute, expectedAggregate: 5 * time.Minute, expectedError: false},
		{name: "bad_poll_format", poll: "nope", aggregate: "15m", expectedError: true},
		{name: "poll_zero", poll: "0s", aggregate: "15m", expectedError: true},
		{name: "poll_negative", poll: "-5m", aggregate: "15m", expectedError: true},
		{name: "bad_aggregate_format", poll: "5m", aggregate: "nope", expectedError: true},
		{name: "aggregate_zero", poll: "5m", aggregate: "0s", expectedError: true},
		{name: "not_whole_multiple", poll: "5m", aggregate: "12m", expectedError: true},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			poll, aggregate, err := makePeriods(testCase.poll, testCase.aggregate)
			if (err != nil) != testCase.expectedError {
				t.Fatalf("error mismatch: got %v want error=%v", err, testCase.expectedError)
			}
			if testCase.expectedError {
				return
			}
			if poll != testCase.expectedPoll {
				t.Errorf("poll: got %s want %s", poll, testCase.expectedPoll)
			}
			if aggregate != testCase.expectedAggregate {
				t.Errorf("aggregate: got %s want %s", aggregate, testCase.expectedAggregate)
			}
		})
	}
}
