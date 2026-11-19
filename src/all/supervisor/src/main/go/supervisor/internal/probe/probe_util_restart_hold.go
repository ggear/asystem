package probe

import (
	"os"
	"strings"
)

func restartHostHeld(path string) bool {
	data, err := os.ReadFile(path)
	if err != nil {
		return false
	}
	lines := strings.Split(strings.TrimSpace(string(data)), "\n")
	last := strings.TrimSpace(lines[len(lines)-1])
	if last == "" {
		return false
	}
	return !strings.HasPrefix(last, "awoke ")
}

const (
	restartHoldPath = "/host/run/asleep.state"
)
