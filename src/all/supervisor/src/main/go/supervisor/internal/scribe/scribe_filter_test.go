package scribe

import "testing"

func TestScribe_SetFilters(t *testing.T) {
	tests := []struct {
		name          string
		source        string
		subject       string
		action        string
		expectedError bool
	}{
		{
			name:          "happy_empty_means_no_filter",
			expectedError: false,
		},
		{
			name:          "happy_valid_source_prefix",
			source:        "probe,broker",
			expectedError: false,
		},
		{
			name:          "happy_valid_action_prefix",
			action:        "compute,census",
			expectedError: false,
		},
		{
			name:          "happy_valid_source_abbreviation",
			source:        "d",
			expectedError: false,
		},
		{
			name:          "happy_open_subject_never_validated",
			subject:       "host/use",
			expectedError: false,
		},
		{
			name:          "sad_unknown_source_prefix",
			source:        "xyz",
			expectedError: true,
		},
		{
			name:          "sad_unknown_action_prefix",
			action:        "xyz",
			expectedError: true,
		},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			t.Cleanup(ResetFilters)
			err := SetFilters(testCase.source, testCase.subject, testCase.action)
			if (err != nil) != testCase.expectedError {
				t.Fatalf("SetFilters: got err = %v, expectedError %v", err, testCase.expectedError)
			}
		})
	}
}

func TestScribe_Allowed(t *testing.T) {
	tests := []struct {
		name          string
		source        string
		subject       string
		action        string
		recordSource  string
		recordSubject string
		recordAction  string
		expected      bool
		expectedError bool
	}{
		{
			name:          "happy_no_filters_allows_everything",
			recordSource:  "probe",
			recordSubject: "host/used_memory",
			recordAction:  "compute",
			expected:      true,
			expectedError: false,
		},
		{
			name:          "happy_source_matches",
			source:        "probe",
			recordSource:  "probe",
			recordSubject: "host/used_memory",
			recordAction:  "compute",
			expected:      true,
			expectedError: false,
		},
		{
			name:          "happy_source_mismatches",
			source:        "broker",
			recordSource:  "probe",
			recordSubject: "host/used_memory",
			recordAction:  "compute",
			expected:      false,
			expectedError: false,
		},
		{
			name:          "happy_subject_prefix_matches",
			subject:       "host/use",
			recordSource:  "probe",
			recordSubject: "host/used_memory",
			recordAction:  "compute",
			expected:      true,
			expectedError: false,
		},
		{
			name:          "happy_subject_prefix_mismatches",
			subject:       "service/",
			recordSource:  "probe",
			recordSubject: "host/used_memory",
			recordAction:  "compute",
			expected:      false,
			expectedError: false,
		},
		{
			name:          "happy_action_or_within_dimension",
			action:        "sample,compute",
			recordSource:  "probe",
			recordSubject: "host/used_memory",
			recordAction:  "compute",
			expected:      true,
			expectedError: false,
		},
		{
			name:          "happy_and_across_dimensions",
			source:        "probe",
			action:        "connect",
			recordSource:  "probe",
			recordSubject: "host/used_memory",
			recordAction:  "compute",
			expected:      false,
			expectedError: false,
		},
		{
			name:          "happy_case_insensitive",
			source:        "PROBE",
			recordSource:  "probe",
			recordSubject: "host/used_memory",
			recordAction:  "compute",
			expected:      true,
			expectedError: false,
		},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			t.Cleanup(ResetFilters)
			if err := SetFilters(testCase.source, testCase.subject, testCase.action); (err != nil) != testCase.expectedError {
				t.Fatalf("SetFilters: got err = %v, expectedError %v", err, testCase.expectedError)
			}
			if got := allowed(testCase.recordSource, testCase.recordSubject, testCase.recordAction); got != testCase.expected {
				t.Errorf("allowed: got %v want %v", got, testCase.expected)
			}
		})
	}
}
