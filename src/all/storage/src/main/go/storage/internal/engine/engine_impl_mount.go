package engine

import (
	"context"
	"os/exec"
	"time"
)

type MountResult struct {
	Mountpoint string
	Message    string
	Failed     bool
}

const mountTimeout = 10 * time.Second

func boundedRun(name string, args ...string) error {
	ctx, cancel := context.WithTimeout(context.Background(), mountTimeout)
	defer cancel()
	return exec.CommandContext(ctx, name, args...).Run()
}
