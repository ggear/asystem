package engine

import "storage/internal/config"

func LocalHost(cfg *config.Config, drives []string) HostDoc {
	return HostDoc{
		Index:   cfg.Index(),
		Label:   cfg.Label(),
		Name:    cfg.Name(),
		Version: cfg.Version(),
		State:   HostStateMeasured,
		Mounts:  CollectLocal(cfg, drives),
	}
}
