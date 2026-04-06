package testutil

import (
	"sort"
	"strings"
)

func MapToString(tags map[string]string) string {
	tagStrings := make([]string, 0, len(tags))
	for k, v := range tags {
		tagStrings = append(tagStrings, k+":"+v)
	}
	sort.Strings(tagStrings)
	return strings.Join(tagStrings, ", ")
}

func BoolToPtr(value bool) *bool {
	return &value
}

func StringToPtr(value string) *string {
	return &value
}
