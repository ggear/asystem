package probe

import (
	"errors"
)

var ErrProcessorProbeWarmingUp = errors.New("processor probe is warming up")

type Periods struct {
	PollSecs     int
	PulseSecs    int
	TrendHours   int
	CacheHours   int
	SnapshotMins int
}
