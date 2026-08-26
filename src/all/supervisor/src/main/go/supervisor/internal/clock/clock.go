package clock

import "time"

func NowIncludingSuspend() time.Time {
	return time.Now().Round(0)
}

func SinceIncludingSuspend(instant time.Time) time.Duration {
	return time.Since(instant.Round(0))
}
