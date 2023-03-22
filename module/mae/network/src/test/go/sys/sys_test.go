package main

import (
	"github.com/ggear/asystem/tree/master/module/mae/internet/src/main/go/pkg"
	"testing"
)

func Test_GetStatus(t *testing.T) {
	status := "Up"
	if status != pkg.GetStatus(status) {
		t.Errorf("Status incorrectly reported")
	}
}
