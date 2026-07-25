package engine

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"log/slog"
	"net/http"
	"net/http/cookiejar"
	"time"
)

const routerHTTPTimeout = 10 * time.Second

type RouterClient struct {
	base     string
	site     string
	user     string
	pass     string
	http     *http.Client
	loggedIn bool
}

type RouterDevice struct {
	Name         string       `json:"name"`
	Mac          string       `json:"mac"`
	Type         string       `json:"type"`
	State        int          `json:"state"`
	Satisfaction int          `json:"satisfaction"`
	NumSta       int          `json:"num_sta"`
	PortTable    []RouterPort `json:"port_table"`
}

type RouterPort struct {
	PortIdx    int    `json:"port_idx"`
	Name       string `json:"name"`
	Up         bool   `json:"up"`
	Enable     bool   `json:"enable"`
	Speed      int    `json:"speed"`
	FullDuplex bool   `json:"full_duplex"`
	RxErrors   int64  `json:"rx_errors"`
	TxErrors   int64  `json:"tx_errors"`
}

type RouterStation struct {
	Mac          string `json:"mac"`
	Satisfaction int    `json:"satisfaction"`
	Signal       int    `json:"signal"`
	ApMac        string `json:"ap_mac"`
}

func NewRouterClient(base, site, user, pass string) (*RouterClient, error) {
	if base == "" {
		return nil, errors.New("router url is empty")
	}
	jar, err := cookiejar.New(nil)
	if err != nil {
		return nil, err
	}
	return &RouterClient{base: base, site: site, user: user, pass: pass, http: &http.Client{Timeout: routerHTTPTimeout, Jar: jar}}, nil
}

func (c *RouterClient) login(ctx context.Context) error {
	payload, _ := json.Marshal(map[string]string{"username": c.user, "password": c.pass})
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, c.base+"/api/auth/login", bytes.NewReader(payload))
	if err != nil {
		return err
	}
	req.Header.Set("Content-Type", "application/json")
	resp, err := c.http.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	io.Copy(io.Discard, resp.Body)
	if resp.StatusCode != http.StatusOK {
		return fmt.Errorf("login failed [%s] status [%d]", c.base, resp.StatusCode)
	}
	c.loggedIn = true
	slog.Debug("router", "phase", "login", "url", c.base)
	return nil
}

func (c *RouterClient) get(ctx context.Context, path string, out any) error {
	slog.Debug("router", "phase", "request", "path", path)
	return c.getWithRetry(ctx, path, out, true)
}

func (c *RouterClient) getWithRetry(ctx context.Context, path string, out any, allowRetry bool) error {
	if !c.loggedIn {
		if err := c.login(ctx); err != nil {
			return err
		}
	}
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, c.base+path, nil)
	if err != nil {
		return err
	}
	resp, err := c.http.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	if resp.StatusCode == http.StatusUnauthorized {
		c.loggedIn = false
		if !allowRetry {
			return fmt.Errorf("request failed [%s] status [%d] after re-login", path, resp.StatusCode)
		}
		if err := c.login(ctx); err != nil {
			return err
		}
		return c.getWithRetry(ctx, path, out, false)
	}
	if resp.StatusCode != http.StatusOK {
		return fmt.Errorf("request failed [%s] status [%d]", path, resp.StatusCode)
	}
	return json.NewDecoder(resp.Body).Decode(out)
}

func (c *RouterClient) Devices(ctx context.Context) ([]RouterDevice, error) {
	var body struct {
		Data []RouterDevice `json:"data"`
	}
	if err := c.get(ctx, "/proxy/network/api/s/"+c.site+"/stat/device", &body); err != nil {
		return nil, err
	}
	return body.Data, nil
}

func (c *RouterClient) Stations(ctx context.Context) ([]RouterStation, error) {
	var body struct {
		Data []RouterStation `json:"data"`
	}
	if err := c.get(ctx, "/proxy/network/api/s/"+c.site+"/stat/sta", &body); err != nil {
		return nil, err
	}
	return body.Data, nil
}
