package engine

import (
	"bytes"
	"encoding/json"
	"errors"
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
)

func collectRemote(loaded *config.Config, filters []string) []HostDoc {
	collectHost := func(host config.HostEntry) HostDoc {
		unreachable := HostDoc{Index: host.Index, Label: host.Label, Name: host.Host, State: HostStateUnreachable}
		budget := remoteRunMargin + time.Duration(len(host.Shares)+remoteRunExtraMounts)*statfsTimeout
		output, err := runRemote(host.Host, budget, filters)
		if err != nil {
			unreachable.Error = err.Error()
			return unreachable
		}
		var document Document
		if err := json.Unmarshal(output, &document); err != nil || len(document.Hosts) == 0 {
			unreachable.Error = fmt.Sprintf("malformed response [%s] [%v]", host.Host, err)
			return unreachable
		}
		remote := document.Hosts[0]
		remote.Index = host.Index
		remote.Label = host.Label
		remote.Name = host.Host
		if remote.State == "" {
			remote.State = HostStateMeasured
		}
		for index := range remote.Mounts {
			if remote.Mounts[index].State == "" {
				remote.Mounts[index].State = MountStateMeasured
			}
		}
		return remote
	}
	hosts := loaded.Hosts()
	docs := make([]HostDoc, len(hosts))
	var waitGroup sync.WaitGroup
	for i, host := range hosts {
		waitGroup.Go(func() { docs[i] = collectHost(host) })
	}
	waitGroup.Wait()
	sort.Slice(docs, func(i, j int) bool { return docs[i].Label < docs[j].Label })
	return docs
}

func runRemote(host string, budget time.Duration, filters []string) ([]byte, error) {
	client, err := dialHost(host, budget)
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
	command := fmt.Sprintf("%s space -m %s -f %s --json", remoteInstallPath, ModeLocal, shellQuote(strings.Join(filters, ",")))
	done := make(chan error, 1)
	go func() { done <- session.Run(command) }()
	select {
	case err := <-done:
		var exitError *ssh.ExitError
		if errors.As(err, &exitError) && stdout.Len() > 0 {
			return stdout.Bytes(), nil
		}
		if err != nil {
			return nil, fmt.Errorf("ssh command failed [%s] [%v] [%s]", host, err, strings.TrimSpace(stderr.String()))
		}
		return stdout.Bytes(), nil
	case <-time.After(budget):
		return nil, fmt.Errorf("ssh command timed out [%s] after [%s]", host, budget)
	}
}

func dialHost(host string, budget time.Duration) (*ssh.Client, error) {
	auth, err := loadSSHAuth()
	if err != nil {
		return nil, err
	}
	address := net.JoinHostPort(host, remoteSSHPort)
	connection, err := net.DialTimeout("tcp", address, remoteDialTimeout)
	if err != nil {
		return nil, err
	}
	if err := connection.SetDeadline(time.Now().Add(remoteDialTimeout + budget)); err != nil {
		_ = connection.Close()
		return nil, err
	}
	clientConfig := &ssh.ClientConfig{
		User:            "root",
		Auth:            auth,
		HostKeyCallback: ssh.InsecureIgnoreHostKey(),
	}
	clientConnection, channels, requests, err := ssh.NewClientConn(connection, address, clientConfig)
	if err != nil {
		_ = connection.Close()
		return nil, err
	}
	return ssh.NewClient(clientConnection, channels, requests), nil
}

func loadSSHAuth() ([]ssh.AuthMethod, error) {
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
