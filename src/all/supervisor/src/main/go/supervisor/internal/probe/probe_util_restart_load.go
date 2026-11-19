package probe

import (
	"context"
	"fmt"
	"os"
	"path/filepath"
	"sync"
	"time"

	"supervisor/internal/config"
)

func newRestartPolicyLoader() *restartPolicyLoader {
	return &restartPolicyLoader{install: config.DirInstall, run: bounded, cache: make(map[string]restartLoaded)}
}

func (l *restartPolicyLoader) ready(ctx context.Context, service string) bool {
	script := filepath.Join(l.install, service, config.DirInstallLatestLink, restartScriptLeaf)
	_, code, abandoned := l.run(ctx, restartHookWait, "bash", script, "ready")
	return !abandoned && code == 0
}

func (l *restartPolicyLoader) load(ctx context.Context, service string) (restartPolicy, bool, error) {
	l.mutex.Lock()
	defer l.mutex.Unlock()
	script := filepath.Join(l.install, service, config.DirInstallLatestLink, restartScriptLeaf)
	info, err := os.Stat(script)
	if err != nil {
		delete(l.cache, service)
		return restartPolicy{}, false, nil
	}
	resolved, _ := filepath.EvalSymlinks(script)
	key := fmt.Sprintf("%s|%d|%d", resolved, info.ModTime().UnixNano(), info.Size())
	if cached, found := l.cache[service]; found && cached.key == key {
		return cached.policy, cached.enabled, nil
	}
	_, code, abandoned := l.run(ctx, restartHookWait, "bash", script, "enabled")
	if abandoned {
		return restartPolicy{}, false, fmt.Errorf("enabled hook of [%s] was abandoned", script)
	}
	if code != 0 {
		l.cache[service] = restartLoaded{key: key}
		return restartPolicy{}, false, nil
	}
	text, code, abandoned := l.run(ctx, restartHookWait, "bash", script, "policy")
	if abandoned || code != 0 {
		return restartPolicy{}, false, fmt.Errorf("policy hook of [%s] failed with exit [%d] abandoned [%v]", script, code, abandoned)
	}
	policy, err := parseRestartPolicy(text)
	if err != nil {
		return restartPolicy{}, false, fmt.Errorf("policy of [%s] is invalid [%w]", script, err)
	}
	l.cache[service] = restartLoaded{key: key, enabled: true, policy: policy}
	return policy, true, nil
}

type restartLoaded struct {
	key     string
	enabled bool
	policy  restartPolicy
}

type restartPolicyLoader struct {
	mutex   sync.Mutex
	install string
	run     func(ctx context.Context, limit time.Duration, name string, args ...string) (string, int, bool)
	cache   map[string]restartLoaded
}

const (
	restartScriptLeaf = "restart.sh"
	restartHookWait   = 30 * time.Second
)
