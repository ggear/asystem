package engine

import (
	"context"
	"os/exec"
	"time"
)

func boundedRun(name string, args ...string) error {
	ctx, cancel := context.WithTimeout(context.Background(), mountTimeout)
	defer cancel()
	return exec.CommandContext(ctx, name, args...).Run()
}

type MountResult struct {
	Message string
	Failed  bool
}

const mountTimeout = 10 * time.Second
