package probe

import (
	"fmt"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"sync"
	"time"
)

func (s *restoreSession) merge() {
	if !s.defined[restoreHookMerged] {
		s.fault(fmt.Sprintf("module [%s] defines no restore_merged, merge is not offered", s.module))
		return
	}
	s.swept()
	s.report(fmt.Sprintf("staging   [%d] artifact(s) into scratch", len(s.chain)))
	scratch, err := s.staged()
	if err != nil {
		s.fault(fmt.Sprintf("could not stage [%s] into scratch [%v]", s.run, err))
		s.tornDown(s.scratchDir())
		return
	}
	defer func() {
		if !s.request.KeepScratch {
			s.tornDown(scratch)
		}
	}()
	s.report("counting   fingerprinting scratch")
	staged, err := s.fingerprinted(scratch)
	if err != nil {
		s.fault(fmt.Sprintf("could not fingerprint scratch [%s] [%v]", scratch, err))
		return
	}
	s.report("sealing    scratch read only")
	if sealErr := s.sealed(scratch); sealErr != nil {
		s.fault(fmt.Sprintf("could not seal scratch [%s] read only", scratch))
		return
	}
	live, err := s.fingerprinted(s.liveAddress())
	if err != nil {
		s.fault("could not fingerprint live")
		return
	}
	planned := differingBackupUnits(staged, live)
	s.report(fmt.Sprintf("merge     [%d] closed unit(s) differ from live", len(planned)))
	for _, unit := range planned[:min(len(planned), 20)] {
		s.report("plan      [" + unit + "]")
	}
	if len(planned) > 20 {
		s.report(fmt.Sprintf("plan      and [%d] more", len(planned)-20))
	}
	if !s.request.Force || !s.backedUp() {
		return
	}
	progress := filepath.Join(filepath.Dir(s.scratchDir()), s.run+".merged")
	if os.MkdirAll(filepath.Dir(progress), 0o755) != nil {
		s.fault("could not create the progress directory")
		return
	}
	done := map[string]bool{}
	if data, readErr := os.ReadFile(progress); readErr == nil {
		for line := range strings.SplitSeq(string(data), "\n") {
			done[line] = true
		}
	}
	stats := progress + ".stats"
	_ = os.Remove(stats)
	jobs := max(restoreSetting("RESTORE_MERGE_JOBS", 3), 1)
	every := time.Duration(restoreSetting("RESTORE_PROGRESS_SECONDS", 30)) * time.Second
	s.report(fmt.Sprintf("merge     merging [%d] unit(s) with [%d] job(s), progress is recorded in [%s]", len(planned), jobs, progress))
	var (
		mutex   sync.Mutex
		wait    sync.WaitGroup
		failed  []string
		started = time.Now()
		slots   = make(chan struct{}, jobs)
	)
	recorded := func() int {
		mutex.Lock()
		defer mutex.Unlock()
		return len(done)
	}
	finished := make(chan struct{})
	go func() {
		ticker := time.NewTicker(every)
		defer ticker.Stop()
		for {
			select {
			case <-ticker.C:
				s.report(fmt.Sprintf("merge     merged [%d] of [%d] units, [%s] elapsed", recorded(), len(planned), time.Since(started).Round(time.Second)))
			case <-finished:
				return
			}
		}
	}()
	for _, unit := range planned {
		if done[unit] {
			continue
		}
		slots <- struct{}{}
		wait.Go(func() {
			defer func() { <-slots }()
			_, mergeErr := s.hooked(restoreHookMerged, "", unit, scratch, stats)
			mutex.Lock()
			defer mutex.Unlock()
			if mergeErr != nil {
				failed = append(failed, unit)
				return
			}
			done[unit] = true
			if file, openErr := os.OpenFile(progress, os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0o644); openErr == nil {
				_, _ = file.WriteString(unit + "\n")
				_ = file.Close()
			}
		})
	}
	wait.Wait()
	close(finished)
	if len(failed) > 0 {
		for _, unit := range failed {
			s.fault(fmt.Sprintf("could not merge [%s]", unit))
		}
		return
	}
	s.changed += len(planned)
	s.report("verify    merge written, restarting [" + s.module + "] and waiting for its counts to settle")
	_, _, _ = bounded(s.ctx, restoreHookWait, "docker", "restart", s.module)
	want := map[string]int64{}
	for _, unit := range staged {
		want[unit.name] = unit.count
	}
	attempts, pause := restoreSetting("RESTORE_VERIFY_ATTEMPTS", 24), time.Duration(restoreSetting("RESTORE_VERIFY_SLEEP", 5))*time.Second
	var shorts []string
	for attempt := 1; attempt <= attempts; attempt++ {
		after, _ := s.fingerprinted(s.liveAddress())
		held := map[string]int64{}
		for _, unit := range after {
			held[unit.name] = unit.count
		}
		shorts = shorts[:0]
		for _, unit := range planned {
			if held[unit] < want[unit] {
				shorts = append(shorts, fmt.Sprintf("unit [%s] holds [%d] after the merge, wants at least [%d]", unit, held[unit], want[unit]))
			}
		}
		if len(shorts) == 0 {
			break
		}
		s.report(fmt.Sprintf("verify    attempt [%d] of [%d], [%d] unit(s) still short", attempt, attempts, len(shorts)))
		if attempt < attempts {
			select {
			case <-time.After(pause):
			case <-s.ctx.Done():
				attempt = attempts
			}
		}
	}
	for _, line := range shorts {
		s.fault(line)
	}
	if len(shorts) == 0 {
		s.report("verify    every merged unit holds at least the backup's count")
		_ = os.Remove(progress)
		_ = os.Remove(stats)
	}
}

func (s *restoreSession) liveAddress() string {
	output, _ := s.hooked("restore_live_address", "")
	return strings.TrimSpace(output)
}

func restoreSetting(name string, fallback int) int {
	if value, err := strconv.Atoi(os.Getenv(name)); err == nil {
		return value
	}
	return fallback
}
