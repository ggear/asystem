package plugin

import (
	"context"
	"sync"
	"time"

	"network/internal/config"
	"network/internal/remote"
)

const gatewayReuse = time.Minute

var sharedGateway gatewaySession

type gatewaySession struct {
	mu      sync.Mutex
	gateway *remote.Gateway
	fetched time.Time
	devices []remote.GatewayDevice
	clients []remote.GatewayClient
}

func (s *gatewaySession) fetch(ctx context.Context) ([]remote.GatewayDevice, []remote.GatewayClient, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	if !s.fetched.IsZero() && time.Since(s.fetched) < gatewayReuse {
		return s.devices, s.clients, nil
	}
	if s.gateway == nil {
		cfg := config.Load()
		gateway, err := remote.NewGateway(cfg.UnifiURL(), cfg.UnifiSite(), cfg.UnifiUser(), cfg.UnifiToken())
		if err != nil {
			return nil, nil, err
		}
		s.gateway = gateway
	}
	devices, err := s.gateway.Devices(ctx)
	if err != nil {
		return nil, nil, err
	}
	clients, err := s.gateway.Clients(ctx)
	if err != nil {
		return nil, nil, err
	}
	s.devices, s.clients, s.fetched = devices, clients, time.Now()
	return devices, clients, nil
}
