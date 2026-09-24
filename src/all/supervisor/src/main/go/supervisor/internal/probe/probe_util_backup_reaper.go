package probe

import (
	"encoding/json"
	"fmt"
	"time"

	"supervisor/internal/config"
	"supervisor/internal/metric"
	"supervisor/internal/scribe"
)

func runBackupAuto(request BackupRequest) error {
	started := time.Now()
	configPath, want := request.Config, request.Argument
	report := func(verb, detail string, args ...any) {
		scribe.Log(scribe.SourceBackup, scribe.SubjectNone, scribe.ActionPublish).Infof(verb, started, detail, args...)
	}
	if want == "" {
		state, expires, found, err := backupReaperState(configPath)
		if err != nil {
			return err
		}
		switch {
		case !found:
			report("reported", "[undeclared] reaper, which the cluster reads as armed")
		case state == metric.CommandOff && expires != "":
			report("reported", "[%s] reaper is paused until then, the backup disk stays powered", expires)
		case state == metric.CommandOn:
			report("reported", "[armed] reaper, the backup disk is powered down again when nothing needs it")
		default:
			report("reported", "[%s/%s] reaper states no deadline, so the cluster reads it as armed", state, expires)
		}
		return nil
	}
	if want == backupAutoOff {
		expires := backupReaperPauseUntil(time.Now()).Format(time.RFC3339)
		if err := backupReaperSet(configPath, metric.CommandOff, expires); err != nil {
			return err
		}
		report("switched", "[%s] reaper is paused until then, the backup disk stays powered whatever else happens", expires)
		return nil
	}
	if err := backupReaperSet(configPath, metric.CommandOn, ""); err != nil {
		return err
	}
	report("switched", "[armed] reaper, the backup disk is powered down again when nothing needs it")
	return nil
}

func publishRunStatus(configPath string, document backupSummary) error {
	client, err := brokerDial(configPath, "status")
	if err != nil {
		return err
	}
	defer client.close()
	payload, marshalErr := json.Marshal(document)
	if marshalErr != nil {
		return marshalErr
	}
	return client.publishRetained(metric.TopicBackupStatus(configHost(configPath)), string(payload))
}

func powerBackupDisk(configPath, state string) error {
	topic := config.Load(configPath).BackupCommandTopic()
	if topic == "" {
		return nil
	}
	client, err := brokerDial(configPath, "power")
	if err != nil {
		return err
	}
	defer client.close()
	return client.publishCommand(topic, state)
}

func backupReaperState(configPath string) (state, expiresTS string, found bool, err error) {
	watch, dialErr := brokerWatch(configPath, configHost(configPath), metric.TopicBackupReaper())
	if dialErr != nil {
		return "", "", false, dialErr
	}
	defer watch.close()
	deadline := time.Now().Add(reaperQueryTimeout)
	for time.Now().Before(deadline) {
		payloads, ready := watch.readRetained()
		if ready {
			raw, ok := payloads[metric.TopicBackupReaper()]
			if !ok {
				return "", "", false, nil
			}
			var reaper backupReaperSummary
			if json.Unmarshal([]byte(raw), &reaper) != nil {
				return "", "", false, nil
			}
			return reaper.State, reaper.ExpiresTS, true, nil
		}
		time.Sleep(reaperQueryPoll)
	}
	return "", "", false, fmt.Errorf("broker did not settle within [%s]", reaperQueryTimeout)
}

func backupReaperSet(configPath, state, expiresTS string) error {
	client, err := brokerDial(configPath, "auto")
	if err != nil {
		return err
	}
	defer client.close()
	payload, _ := json.Marshal(backupReaperSummary{State: state, ExpiresTS: expiresTS})
	return client.publishRetained(metric.TopicBackupReaper(), string(payload))
}

func backupReaperPauseUntil(now time.Time) time.Time {
	next := time.Date(now.Year(), now.Month(), now.Day(), backupScheduledHour, 0, 0, 0, now.Location())
	if !next.After(now) {
		next = next.AddDate(0, 0, 1)
	}
	return next
}

const (
	backupAutoOn  = "on"
	backupAutoOff = "off"

	reaperQueryTimeout = 5 * time.Second
	reaperQueryPoll    = 100 * time.Millisecond
)
