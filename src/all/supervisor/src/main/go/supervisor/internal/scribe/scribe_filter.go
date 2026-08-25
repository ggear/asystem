package scribe

import (
	"fmt"
	"strings"
	"sync"
)

func SetFilters(source, subject, action string) error {
	sourcePrefixes, err := closedPrefixes("source", source, sourceStrings())
	if err != nil {
		return err
	}
	actionPrefixes, err := closedPrefixes("action", action, actionStrings())
	if err != nil {
		return err
	}
	subjectPrefixes := openPrefixes(subject)
	filterMutex.Lock()
	activeFilter = logFilter{source: sourcePrefixes, subject: subjectPrefixes, action: actionPrefixes}
	filterMutex.Unlock()
	return nil
}

func ResetFilters() {
	filterMutex.Lock()
	activeFilter = logFilter{}
	filterMutex.Unlock()
}

func allowed(source, subject, action string) bool {
	filterMutex.Lock()
	filter := activeFilter
	filterMutex.Unlock()
	return matches(source, filter.source) && matches(subject, filter.subject) && matches(action, filter.action)
}

func matches(value string, prefixes []string) bool {
	if len(prefixes) == 0 {
		return true
	}
	lowered := strings.ToLower(value)
	for _, prefix := range prefixes {
		if strings.HasPrefix(lowered, prefix) {
			return true
		}
	}
	return false
}

func openPrefixes(value string) []string {
	if strings.TrimSpace(value) == "" {
		return nil
	}
	prefixes := make([]string, 0, strings.Count(value, ",")+1)
	for token := range strings.SplitSeq(value, ",") {
		if token = strings.ToLower(strings.TrimSpace(token)); token != "" {
			prefixes = append(prefixes, token)
		}
	}
	return prefixes
}

func closedPrefixes(dimension, value string, declared []string) ([]string, error) {
	prefixes := openPrefixes(value)
	for _, prefix := range prefixes {
		matched := false
		for _, candidate := range declared {
			if strings.HasPrefix(strings.ToLower(candidate), prefix) {
				matched = true
				break
			}
		}
		if !matched {
			return nil, fmt.Errorf("log %s filter prefix [%s] matches none of [%s]", dimension, prefix, strings.Join(declared, ", "))
		}
	}
	return prefixes, nil
}

func sourceStrings() []string {
	values := make([]string, len(AllSources))
	for index, source := range AllSources {
		values[index] = source.String()
	}
	return values
}

func actionStrings() []string {
	values := make([]string, len(AllActions))
	for index, action := range AllActions {
		values[index] = action.String()
	}
	return values
}

type logFilter struct {
	source  []string
	subject []string
	action  []string
}

var (
	filterMutex  sync.Mutex
	activeFilter logFilter
)
