package engine

import (
	"bytes"
	"encoding/json"
	"fmt"
	"net"
	"os"
	"path/filepath"
	"sort"
	"storage/internal/config"
	"strings"
	"sync"
	"time"

	"golang.org/x/crypto/ssh"
	"golang.org/x/crypto/ssh/knownhosts"
)

func collectRemote(cfg *config.Config, drives []string) []HostDoc {
	hosts := cfg.Hosts()
	docs := make([]HostDoc, len(hosts))
	var wg sync.WaitGroup
	for i, host := range hosts {
		wg.Add(1)
		go func(i int, host config.HostEntry) {
			defer wg.Done()
			docs[i] = collectOneHost(host, drives)
		}(i, host)
	}
	wg.Wait()
	sort.Slice(docs, func(i, j int) bool { return docs[i].Label < docs[j].Label })
	return docs
}

func collectOneHost(host config.HostEntry, drives []string) HostDoc {
	base := HostDoc{Index: host.Index, Label: host.Label, Name: host.Host}
	output, err := runRemote(host.Host, remoteRunBudget(host), drives)
	if err != nil {
		base.State = HostStateUnreachable
		base.Error = err.Error()
		return base
	}
	var document Document
	if err := json.Unmarshal(output, &document); err != nil || len(document.Hosts) == 0 {
		base.State = HostStateUnreachable
		base.Error = fmt.Sprintf("malformed response [%s] [%v]", host.Host, err)
		return base
	}
	remote := document.Hosts[0]
	remote.Index = host.Index
	remote.Label = host.Label
	remote.Name = host.Host
	if remote.State == "" {
		remote.State = HostStateMeasured
	}
	return remote
}

func remoteRunBudget(host config.HostEntry) time.Duration {
	mounts := len(host.Shares) + remoteRunExtraMounts
	return remoteRunMargin + time.Duration(mounts)*statfsTimeout
}

func runRemote(host string, budget time.Duration, drives []string) ([]byte, error) {
	client, err := dialHost(host)
	if err != nil {
		return nil, fmt.Errorf("ssh dial failed [%s] [%w]", host, err)
	}
	defer client.Close()
	session, err := client.NewSession()
	if err != nil {
		return nil, fmt.Errorf("ssh session failed [%s] [%w]", host, err)
	}
	defer session.Close()
	var stdout, stderr bytes.Buffer
	session.Stdout = &stdout
	session.Stderr = &stderr
	command := fmt.Sprintf("%s space -m %s -d %s --json", remoteInstallPath, ModeLocal, shellQuote(strings.Join(drives, ",")))
	done := make(chan error, 1)
	go func() { done <- session.Run(command) }()
	select {
	case err := <-done:
		if err != nil {
			return nil, fmt.Errorf("ssh command failed [%s] [%v] [%s]", host, err, strings.TrimSpace(stderr.String()))
		}
		return stdout.Bytes(), nil
	case <-time.After(budget):
		return nil, fmt.Errorf("ssh command timed out [%s] after [%s]", host, budget)
	}
}

func dialHost(host string) (*ssh.Client, error) {
	auth, err := sshAuth()
	if err != nil {
		return nil, err
	}
	callback, err := knownHostsCallback()
	if err != nil {
		return nil, err
	}
	config := &ssh.ClientConfig{
		User:            "root",
		Auth:            auth,
		HostKeyCallback: callback,
		Timeout:         remoteDialTimeout,
	}
	address := net.JoinHostPort(host, remoteSSHPort)
	return ssh.Dial("tcp", address, config)
}

func sshAuth() ([]ssh.AuthMethod, error) {
	home, err := os.UserHomeDir()
	if err != nil {
		return nil, err
	}
	for _, name := range []string{"id_ed25519", "id_rsa"} {
		data, err := os.ReadFile(filepath.Join(home, ".ssh", name))
		if err != nil {
			continue
		}
		signer, err := ssh.ParsePrivateKey(data)
		if err != nil {
			continue
		}
		return []ssh.AuthMethod{ssh.PublicKeys(signer)}, nil
	}
	return nil, fmt.Errorf("no usable private key found under [~/.ssh]")
}

func knownHostsCallback() (ssh.HostKeyCallback, error) {
	home, err := os.UserHomeDir()
	if err != nil {
		return nil, err
	}
	return knownhosts.New(filepath.Join(home, ".ssh", "known_hosts"))
}

func shellQuote(value string) string {
	return "'" + strings.ReplaceAll(value, "'", `'\''`) + "'"
}

const (
	remoteInstallPath = "/var/lib/asystem/install/storage/latest/storage"
	remoteDialTimeout = 5 * time.Second
	remoteRunMargin   = 6 * time.Second
	remoteSSHPort     = "22"

	remoteRunExtraMounts = 2
)
