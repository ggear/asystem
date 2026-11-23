package probe

import (
	"context"
	"net"
	"strings"
	"time"
)

func newRestartChecker() restartChecker {
	return restartChecker{
		run: bounded,
		dial: func(address string, limit time.Duration) error {
			connection, err := net.DialTimeout("tcp", address, limit)
			if err != nil {
				return err
			}
			return connection.Close()
		},
		fstab: fstabPath,
	}
}

func (c restartChecker) met(ctx context.Context, requirement restartRequirement) bool {
	switch requirement.kind {
	case restartKindMount:
		return c.mounted(ctx, requirement.target)
	case restartKindMounts:
		var targets []string
		for _, entry := range readFstab(c.fstab) {
			if entry.fstype == "cifs" {
				targets = append(targets, entry.target)
			}
		}
		for _, target := range targets {
			if !c.mounted(ctx, target) {
				return false
			}
		}
		return len(targets) > 0
	case restartKindTCP:
		return c.dial(requirement.target, restartDialWait) == nil
	case restartKindMQTT:
		fields := strings.Split(requirement.target, ":")
		if len(fields) != 3 {
			return false
		}
		script := `topic="supervisor/restart/probe/$$"; timeout 8 mosquitto_sub -V "$3" -h "$1" -p "$2" -t "$topic" -C 1 -W 5 & sub=$!; for _ in 1 2 3 4 5 6 7 8 9 10; do mosquitto_pub -V "$3" -h "$1" -p "$2" -t "$topic" -m ok; kill -0 "$sub" 2>/dev/null || break; sleep 0.5; done; wait "$sub"`
		out, code, abandoned := c.run(ctx, restartCheckWait, "bash", "-c", script, "restart", fields[0], fields[1], fields[2])
		return !abandoned && code == 0 && strings.TrimSpace(out) == "ok"
	case restartKindHealthy:
		out, code, abandoned := c.run(ctx, restartCheckWait, "docker", "inspect", "--format", "{{.State.Health.Status}}", requirement.target)
		return !abandoned && code == 0 && strings.TrimSpace(out) == restartHealthHealthy
	}
	return false
}

func (c restartChecker) mounted(ctx context.Context, target string) bool {
	if _, code, abandoned := c.run(ctx, restartListWait, "ls", "-A", target); abandoned || code != 0 {
		return false
	}
	out, code, abandoned := c.run(ctx, restartListWait, "findmnt", "-n", "-o", "FSTYPE", "-M", target)
	if abandoned || code != 0 {
		return false
	}
	for line := range strings.SplitSeq(strings.TrimSpace(out), "\n") {
		if line = strings.TrimSpace(line); line != "" && line != "autofs" {
			return true
		}
	}
	return false
}

type restartChecker struct {
	run   func(ctx context.Context, limit time.Duration, name string, args ...string) (string, int, bool)
	dial  func(address string, limit time.Duration) error
	fstab string
}

const (
	restartCheckWait = 10 * time.Second
	restartListWait  = 5 * time.Second
	restartDialWait  = 3 * time.Second
)
