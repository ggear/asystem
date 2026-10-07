package remote

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"net/http/cookiejar"
	"net/url"
	"network/internal/scribe"
	"time"
)

const gatewayHTTPTimeout = 10 * time.Second

type Gateway struct {
	base     string
	site     string
	user     string
	token    string
	loggedIn bool
	client   *http.Client
}

type GatewayDevice struct {
	Name               string               `json:"name"`
	Mac                string               `json:"mac"`
	Type               string               `json:"type"`
	State              int                  `json:"state"`
	LastSeen           int64                `json:"last_seen"`
	Uptime             int64                `json:"uptime"`
	Satisfaction       *int                 `json:"satisfaction"`
	NumSta             int                  `json:"num_sta"`
	Overheating        bool                 `json:"overheating"`
	HasTemperature     bool                 `json:"has_temperature"`
	TotalUsedPower     *float64             `json:"total_used_power"`
	TotalMaxPower      *float64             `json:"total_max_power"`
	GeneralTemperature *float64             `json:"general_temperature"`
	Temperatures       []GatewayTemperature `json:"temperatures"`
	SystemStats        GatewaySystemStats   `json:"system-stats"`
	Uplink             GatewayUplink        `json:"uplink"`
	PortTable          []GatewayPort        `json:"port_table"`
}

type GatewaySystemStats struct {
	CPU    string `json:"cpu"`
	Memory string `json:"mem"`
}

type GatewayTemperature struct {
	Name  string  `json:"name"`
	Value float64 `json:"value"`
}

type GatewayUplink struct {
	Speed            int    `json:"speed"`
	RxBytes          int64  `json:"rx_bytes"`
	TxBytes          int64  `json:"tx_bytes"`
	UplinkDeviceName string `json:"uplink_device_name"`
	UplinkRemotePort int    `json:"uplink_remote_port"`
}

type GatewayClient struct {
	Name     string `json:"name"`
	Hostname string `json:"hostname"`
	SwMac    string `json:"sw_mac"`
	SwPort   int    `json:"sw_port"`
}

type GatewayPort struct {
	PortIdx  int    `json:"port_idx"`
	Name     string `json:"name"`
	Up       bool   `json:"up"`
	Speed    int    `json:"speed"`
	RxBytes  int64  `json:"rx_bytes"`
	TxBytes  int64  `json:"tx_bytes"`
	PoePower string `json:"poe_power"`
}

func NewGateway(base, site, user, token string) (*Gateway, error) {
	if base == "" {
		return nil, errors.New("gateway url is empty")
	}
	jar, err := cookiejar.New(nil)
	if err != nil {
		return nil, err
	}
	return &Gateway{base: base, site: site, user: user, token: token, client: &http.Client{Timeout: gatewayHTTPTimeout, Jar: jar}}, nil
}

func (g *Gateway) Devices(ctx context.Context) ([]GatewayDevice, error) {
	var body struct {
		Data []GatewayDevice `json:"data"`
	}
	if err := g.get(ctx, "/proxy/network/api/s/"+url.PathEscape(g.site)+"/stat/device", &body); err != nil {
		return nil, err
	}
	return body.Data, nil
}

func (g *Gateway) Clients(ctx context.Context) ([]GatewayClient, error) {
	var body struct {
		Data []GatewayClient `json:"data"`
	}
	if err := g.get(ctx, "/proxy/network/api/s/"+url.PathEscape(g.site)+"/stat/sta", &body); err != nil {
		return nil, err
	}
	return body.Data, nil
}

func (g *Gateway) Close() error {
	g.client.CloseIdleConnections()
	return nil
}

func (g *Gateway) login(ctx context.Context) error {
	payload, _ := json.Marshal(map[string]string{"username": g.user, "password": g.token})
	request, err := http.NewRequestWithContext(ctx, http.MethodPost, g.base+"/api/auth/login", bytes.NewReader(payload))
	if err != nil {
		return err
	}
	request.Header.Set("Content-Type", "application/json")
	response, err := g.client.Do(request)
	if err != nil {
		return err
	}
	defer response.Body.Close()
	drain(response.Body)
	if response.StatusCode != http.StatusOK {
		return fmt.Errorf("login failed [%s] status [%d]", g.base, response.StatusCode)
	}
	g.loggedIn = true
	scribe.LogDebug(scribe.Global, "gateway logging in at [%s]", g.base)
	return nil
}

func (g *Gateway) get(ctx context.Context, path string, out any) error {
	scribe.LogDebug(scribe.Global, "gateway requesting path [%s]", path)
	return g.getWithRetry(ctx, path, out, true)
}

func (g *Gateway) getWithRetry(ctx context.Context, path string, out any, allowRetry bool) error {
	if !g.loggedIn {
		if err := g.login(ctx); err != nil {
			return err
		}
	}
	request, err := http.NewRequestWithContext(ctx, http.MethodGet, g.base+path, nil)
	if err != nil {
		return err
	}
	response, err := g.client.Do(request)
	if err != nil {
		return err
	}
	defer response.Body.Close()
	if response.StatusCode == http.StatusUnauthorized {
		drain(response.Body)
		g.loggedIn = false
		if !allowRetry {
			return fmt.Errorf("request failed [%s] status [%d] after re-login", path, response.StatusCode)
		}
		if err := g.login(ctx); err != nil {
			return err
		}
		return g.getWithRetry(ctx, path, out, false)
	}
	if response.StatusCode != http.StatusOK {
		drain(response.Body)
		return fmt.Errorf("request failed [%s] status [%d]", path, response.StatusCode)
	}
	return json.NewDecoder(response.Body).Decode(out)
}

func drain(reader io.Reader) {
	_, _ = io.Copy(io.Discard, reader)
}
