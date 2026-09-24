package probe

import (
	"encoding/json"
	"fmt"
	"time"

	"supervisor/internal/config"
	"supervisor/internal/metric"
)

func runBackupAuto(request BackupRequest) error {
	configPath, want := request.Config, request.Argument
	if want == "" {
		state, expires, found, err := backupReaperState(configPath)
		if err != nil {
			return err
		}
		switch {
		case !found:
			fmt.Println("reaper is undeclared, which the cluster reads as armed")
		case state == metric.CommandOff && expires != "":
			fmt.Printf("reaper is paused until [%s], the backup disk stays powered until then\n", expires)
		case state == metric.CommandOn:
			fmt.Println("reaper is armed, the backup disk is powered down again when nothing needs it")
		default:
			fmt.Printf("reaper reads [%s/%s], which states no deadline, so the cluster reads it as armed\n", state, expires)
		}
		return nil
	}
	if want == backupAutoOff {
		expires := backupReaperPauseUntil(time.Now()).Format(time.RFC3339)
		if err := backupReaperSet(configPath, metric.CommandOff, expires); err != nil {
			return err
		}
		fmt.Printf("reaper paused until [%s], the backup disk stays powered until then whatever else happens\n", expires)
		return nil
	}
	if err := backupReaperSet(configPath, metric.CommandOn, ""); err != nil {
		return err
	}
	fmt.Println("reaper armed, the backup disk is powered down again when nothing needs it")
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
