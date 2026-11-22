package probe

import (
	"fmt"
	"slices"
	"strings"
	"time"
)

func parseRestartPolicy(text string) (restartPolicy, error) {
	policy := restartPolicy{stable: restartStableDefault}
	for line := range strings.SplitSeq(text, "\n") {
		line = strings.TrimSpace(line)
		if line == "" || strings.HasPrefix(line, "#") {
			continue
		}
		key, value, found := strings.Cut(line, "=")
		if !found {
			return restartPolicy{}, fmt.Errorf("policy line [%s] is not key=value", line)
		}
		switch key {
		case "requires":
			requirement, err := parseRestartRequirement(value)
			if err != nil {
				return restartPolicy{}, err
			}
			policy.requires = append(policy.requires, requirement)
		case "requires_stable":
			duration, err := time.ParseDuration(value)
			if err != nil || duration < 0 {
				return restartPolicy{}, fmt.Errorf("policy requires_stable [%s] is not a duration", value)
			}
			policy.stable = duration
		case "settle_min":
			duration, err := time.ParseDuration(value)
			if err != nil || duration < 0 {
				return restartPolicy{}, fmt.Errorf("policy settle_min [%s] is not a duration", value)
			}
			policy.settleMin = duration
		default:
			return restartPolicy{}, fmt.Errorf("policy key [%s] is unknown", key)
		}
	}
	return policy, nil
}

func parseRestartRequirement(value string) (restartRequirement, error) {
	kind, target, found := strings.Cut(value, ":")
	if !found || target == "" {
		return restartRequirement{}, fmt.Errorf("policy requires [%s] is not kind:target", value)
	}
	switch kind {
	case restartKindMount:
		if !strings.HasPrefix(target, "/") {
			return restartRequirement{}, fmt.Errorf("policy requires mount [%s] is not an absolute path", target)
		}
	case restartKindMounts:
		if target != restartMountsAllCIFS {
			return restartRequirement{}, fmt.Errorf("policy requires mounts [%s] is not [%s]", target, restartMountsAllCIFS)
		}
	case restartKindTCP:
		if host, port, split := strings.Cut(target, ":"); !split || host == "" || port == "" {
			return restartRequirement{}, fmt.Errorf("policy requires %s [%s] is not host:port", kind, target)
		}
	case restartKindMQTT:
		if fields := strings.Split(target, ":"); len(fields) != 3 || fields[0] == "" || fields[1] == "" || !slices.Contains(restartMQTTProtocols, fields[2]) {
			return restartRequirement{}, fmt.Errorf("policy requires %s [%s] is not host:port:protocol with protocol one of [%s]", kind, target, strings.Join(restartMQTTProtocols, ","))
		}
	case restartKindHealthy:
	default:
		return restartRequirement{}, fmt.Errorf("policy requires kind [%s] is unknown", kind)
	}
	return restartRequirement{kind: kind, target: target}, nil
}

type restartRequirement struct {
	kind   string
	target string
}

type restartPolicy struct {
	requires  []restartRequirement
	stable    time.Duration
	settleMin time.Duration
}

const (
	restartKindMount   = "mount"
	restartKindMounts  = "mounts"
	restartKindTCP     = "tcp"
	restartKindMQTT    = "mqtt"
	restartKindHealthy = "healthy"

	restartStableDefault = 60 * time.Second
	restartMountsAllCIFS = "all-cifs"
)

var restartMQTTProtocols = []string{"mqttv31", "mqttv311", "mqttv5"}
