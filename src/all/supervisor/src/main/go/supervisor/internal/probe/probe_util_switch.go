package probe

import (
	"context"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"slices"
	"strings"
	"sync"
	"time"

	"supervisor/internal/config"
	"supervisor/internal/metric"
	"supervisor/internal/scribe"
)

func Switch(ctx context.Context, hostName string, topic string, payload []byte) {
	started := time.Now()
	request, err := parseSwitchCommand(hostName, topic, payload)
	if errors.Is(err, errSwitchOther) {
		return
	}
	if err != nil {
		scribe.Log(scribe.SourceProbeSwitch, scribe.SubjectTopic(topic), scribe.ActionSubscribe).Errorf("rejected", started, "[%s] command refused, %v", string(payload), err)
		return
	}
	decision := switchInstance.handle(ctx, request)
	scribe.Log(scribe.SourceProbeSwitch, scribe.SubjectService(request.service), scribe.ActionSubscribe).Infof("accepted", started, "[%s] command, decided [%s]", strings.ToUpper(strings.TrimSpace(string(payload))), decision)
}

func parseSwitchCommand(hostName string, topic string, payload []byte) (switchRequest, error) {
	tokens := strings.Split(topic, "/")
	if len(tokens) != 5 || tokens[0] != "supervisor" || tokens[2] != "command" || tokens[3] != metric.EntityService || tokens[4] == "" {
		return switchRequest{}, fmt.Errorf("topic [%s] is not a service command", topic)
	}
	if tokens[1] != hostName {
		return switchRequest{}, errSwitchOther
	}
	switch strings.ToUpper(strings.TrimSpace(string(payload))) {
	case metric.CommandOn:
		return switchRequest{service: tokens[4], on: true}, nil
	case metric.CommandOff:
		return switchRequest{service: tokens[4]}, nil
	}
	return switchRequest{}, fmt.Errorf("payload [%s] is neither ON nor OFF", string(payload))
}

func newSwitcher() *switcher {
	return &switcher{
		busy: make(map[string]bool),
		log:  newSwitchLog(config.DirServiceHome),
		running: func(ctx context.Context, service string) bool {
			running, _ := dockerServiceState(ctx, service)
			return running
		},
		asleep: serviceAsleep,
		known: func(service string) bool {
			_, err := os.Stat(installScript(service))
			return err == nil
		},
		limit: func(service string, verb string) (time.Duration, error) {
			if verb == "start" {
				return installLimit(service, switchStartWait...)
			}
			return installLimit(service, switchSleepWait...)
		},
		run: runInstall,
	}
}

func serviceAsleep(service string) bool {
	_, err := os.Stat(filepath.Join(installRoot, service, installSleepMarker))
	return err == nil
}

func (s *switcher) handle(ctx context.Context, request switchRequest) string {
	verb, name := "sleep", metric.CommandOff
	if request.on {
		verb, name = "start", metric.CommandOn
	}
	if !s.known(request.service) {
		s.log.write(request.service, "switch [%s] command [%s] refused, no installed [install.sh]", request.service, name)
		return "unknown service"
	}
	running, asleep := s.running(ctx, request.service), s.asleep(request.service)
	if request.on && running && !asleep {
		s.log.write(request.service, "switch [%s] command [%s] skipped, already on", request.service, name)
		return "already on"
	}
	if !request.on && !running && asleep {
		s.log.write(request.service, "switch [%s] command [%s] skipped, already asleep", request.service, name)
		return "already asleep"
	}
	limit, err := s.limit(request.service, verb)
	if err != nil {
		s.log.write(request.service, "switch [%s] command [%s] refused, install limits unreadable [%v]", request.service, name, err)
		return "limits unreadable"
	}
	s.mutex.Lock()
	if s.busy[request.service] {
		s.mutex.Unlock()
		s.log.write(request.service, "switch [%s] command [%s] skipped, a command is still running", request.service, name)
		return "busy"
	}
	s.busy[request.service] = true
	s.mutex.Unlock()
	s.workers.Add(1)
	go s.perform(context.WithoutCancel(ctx), request, verb, name, limit)
	return "accepted"
}

func (s *switcher) perform(ctx context.Context, request switchRequest, verb string, name string, limit time.Duration) {
	defer s.workers.Done()
	started := time.Now()
	s.log.write(request.service, "switch [%s] command [%s] running install.sh [%s] limit [%s]", request.service, name, verb, limit)
	code, output := s.run(ctx, request.service, verb, limit)
	for line := range strings.SplitSeq(strings.TrimSpace(output), "\n") {
		if line != "" {
			s.log.write(request.service, "install.sh | %s", line)
		}
	}
	s.log.write(request.service, "switch [%s] command [%s] exit [%d] took [%s]", request.service, name, code, time.Since(started).Truncate(time.Millisecond))
	level := scribe.Log(scribe.SourceProbeSwitch, scribe.SubjectService(request.service), scribe.ActionStart)
	if code == 0 {
		level.Infof("switched", started, "[%s] command, install.sh [%s] finished", name, verb)
	} else {
		level.Warnf("switched", started, "[%s] command, install.sh [%s] exited [%d]", name, verb, code)
	}
	s.mutex.Lock()
	delete(s.busy, request.service)
	s.mutex.Unlock()
}

type switchRequest struct {
	service string
	on      bool
}

type switcher struct {
	mutex   sync.Mutex
	workers sync.WaitGroup
	busy    map[string]bool
	log     *restartLog
	running func(ctx context.Context, service string) bool
	asleep  func(service string) bool
	known   func(service string) bool
	limit   func(service string, verb string) (time.Duration, error)
	run     func(ctx context.Context, service string, verb string, limit time.Duration) (int, string)
}

var (
	installRoot     = config.DirInstall
	errSwitchOther  = errors.New("[other] host's command")
	switchInstance  = newSwitcher()
	switchSleepWait = slices.Repeat([]string{"SERVICE_STOP_SECONDS"}, installStopSteps)
	switchStartWait = append(slices.Clone(switchSleepWait), "SERVICE_WAIT_EXECUTING_SECONDS", "SERVICE_WAIT_HEALTHY_SECONDS")
)

const (
	installStopSteps = 3
)
