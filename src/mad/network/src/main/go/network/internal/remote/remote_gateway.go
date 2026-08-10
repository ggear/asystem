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
	Name         string        `json:"name"`
	Mac          string        `json:"mac"`
	Type         string        `json:"type"`
	State        int           `json:"state"`
	Satisfaction int           `json:"satisfaction"`
	NumSta       int           `json:"num_sta"`
	PortTable    []GatewayPort `json:"port_table"`
}

type GatewayPort struct {
	PortIdx    int    `json:"port_idx"`
	Name       string `json:"name"`
	Up         bool   `json:"up"`
	Enable     bool   `json:"enable"`
	Speed      int    `json:"speed"`
	FullDuplex bool   `json:"full_duplex"`
	RxErrors   int64  `json:"rx_errors"`
	TxErrors   int64  `json:"tx_errors"`
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
