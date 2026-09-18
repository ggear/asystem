package metric

import (
	"fmt"
	"strings"
	"time"

	"supervisor/internal/schema"
)

func Cadence(pollPeriod string, pulseFactor int) string {
	poll, err := time.ParseDuration(pollPeriod)
	if err != nil || poll <= 0 || pulseFactor < 1 {
		return pollPeriod
	}
	pulse := poll * time.Duration(pulseFactor)
	switch {
	case pulse%time.Hour == 0:
		return fmt.Sprintf("%dh", pulse/time.Hour)
	case pulse%time.Minute == 0:
		return fmt.Sprintf("%dm", pulse/time.Minute)
	case pulse%time.Second == 0:
		return fmt.Sprintf("%ds", pulse/time.Second)
	default:
		return pulse.String()
	}
}

func Relations(hosts []string, services []string, cadence string) []schema.Relation {
	host := schema.Relation{
		Path:        "supervisor/host",
		Description: "health and utilisation of one host",
		Cadence:     cadence,
		Entities:    append([]string{}, hosts...),
		Dimensions: []schema.Dimension{
			{Key: "host", Description: "name of the monitored host", Subject: true},
		},
		Measures: []schema.Measure{},
	}
	service := schema.Relation{
		Path:        "supervisor/service",
		Description: "health and utilisation of one service on one host",
		Cadence:     cadence,
		Entities:    append([]string{}, services...),
		Dimensions: []schema.Dimension{
			{Key: "host", Description: "name of the host running the service"},
			{Key: "service", Description: "name of the monitored service", Subject: true},
		},
		Measures: []schema.Measure{},
	}
	for _, id := range GetIDs() {
		builder := metricBuildersByID[id]
		if builder.template == "" {
			continue
		}
		relation := &host
		if strings.Contains(builder.template, "$SERVICE") {
			relation = &service
		}
		relation.Measures = append(relation.Measures, schema.Measure{
			Key:         GetIDField(id),
			Kind:        GetIDKindSchema(id),
			Unit:        builder.unit,
			Description: builder.description,
			Persist:     builder.persisted,
		})
		if builder.persisted {
			relation.Measures = append(relation.Measures, schema.Measure{
				Key:         GetIDField(id) + "_trend",
				Kind:        GetIDKindSchema(id),
				Unit:        builder.unit,
				Description: builder.description + ", smoothed across the trend window",
				Persist:     true,
			})
		}
	}
	return []schema.Relation{host, service}
}

func HostRelation() schema.Relation { return Relations(nil, nil, "")[0] }

func ServiceRelation() schema.Relation { return Relations(nil, nil, "")[1] }

func Topics() []schema.Topic {
	topics := make([]schema.Topic, 0, len(metricBuildersByID))
	for _, id := range GetIDs() {
		builder := metricBuildersByID[id]
		if builder.template == "" {
			continue
		}
		template := strings.ReplaceAll(builder.template, "$SCOPE", ScopeData)
		if builder.metricKind == MetricKindCluster {
			template = strings.ReplaceAll(template, "$HOST", HostAll)
		}
		topics = append(topics, schema.Topic{
			Template: template,
			Role:     schema.RoleState,
		})
	}
	for _, template := range []string{
		TopicBackupStatus("$HOST"),
		TopicBackupStage("$HOST", "$STAGE"),
		TopicBackupService("$HOST", "$BACKUP_SERVICE"),
		TopicBackupScrub("$SCRUB_HOST"),
		TopicBackupReaper(),
		TopicBackupStatus(HostAll),
		TopicLeaderLease,
		TopicLeaderCandidate("$LEADER_HOST"),
	} {
		topics = append(topics, schema.Topic{Template: template, Role: schema.RoleState})
	}
	topics = append(topics,
		schema.Topic{Template: TopicAllStatus, Role: schema.RoleAvailability},
		schema.Topic{Template: TopicAllCommand, Role: schema.RoleCommand},
	)
	return topics
}

func Payloads() []schema.Payload {
	value := schema.Member{
		Key:  "value",
		Enum: []string{"number", "text", "true", "false"},
	}
	detail := func(key string) schema.Member {
		return schema.Member{Key: key, Members: []schema.Member{
			{Key: "ok", Kind: schema.KindBool},
			value,
		}}
	}
	backupSettled := []string{
		BackupStateRunning,
		BackupStateSuccess,
		BackupStateStopped,
		BackupStateTimeout,
		BackupStateFailure,
	}
	backupStageStatus := schema.Member{Members: []schema.Member{
		{Key: "run_id", Kind: schema.KindStr},
		{Key: "state", Enum: backupSettled},
		{Key: "trigger", Enum: []string{BackupTriggerSystem, BackupTriggerManual}},
		{Key: "started_ts", Kind: schema.KindStr},
		{Key: "finished_ts", Kind: schema.KindStr},
		{Key: "expires_ts", Kind: schema.KindStr},
		{Key: "timeout_hours", Kind: schema.KindInt},
		{Key: "duration_s", Kind: schema.KindInt},
		{Key: "success_bool", Kind: schema.KindBool},
		{Key: "disk_usage_perc", Kind: schema.KindFloat},
		{Key: "disk_used_mb", Kind: schema.KindInt},
		{Key: "disk_total_mb", Kind: schema.KindInt},
		{Key: "disk_unclean_bool", Kind: schema.KindBool},
		{Key: "total_mb", Kind: schema.KindInt},
		{Key: "file_count", Kind: schema.KindInt},
		{Key: "size_mb", Kind: schema.KindInt},
		{Key: "files_held", Kind: schema.KindInt},
		{Key: "files_created", Kind: schema.KindInt},
		{Key: "files_deleted", Kind: schema.KindInt},
		{Key: "size_held_mb", Kind: schema.KindInt},
		{Key: "sent_mb", Kind: schema.KindInt},
	}}
	backupHostStatus := schema.Member{Members: []schema.Member{
		{Key: "run_id", Kind: schema.KindStr},
		{Key: "state", Enum: backupSettled},
		{Key: "trigger", Enum: []string{BackupTriggerSystem, BackupTriggerManual}},
		{Key: "started_ts", Kind: schema.KindStr},
		{Key: "finished_ts", Kind: schema.KindStr},
		{Key: "duration_s", Kind: schema.KindInt},
		{Key: "success_bool", Kind: schema.KindBool},
		{Key: "disk_usage_perc", Kind: schema.KindFloat},
		{Key: "file_count", Kind: schema.KindInt},
		{Key: "size_mb", Kind: schema.KindInt},
		{Key: "files_held", Kind: schema.KindInt},
		{Key: "files_created", Kind: schema.KindInt},
		{Key: "files_deleted", Kind: schema.KindInt},
		{Key: "size_held_mb", Kind: schema.KindInt},
		{Key: "sent_mb", Kind: schema.KindInt},
		{Key: "stages_run", Kind: schema.KindInt},
		{Key: "stages_failed", Kind: schema.KindInt},
		{Key: "stages_halted", Kind: schema.KindInt},
	}}
	backupServiceStatus := schema.Member{Members: []schema.Member{
		{Key: "run_id", Kind: schema.KindStr},
		{Key: "backup_id", Kind: schema.KindStr},
		{Key: "state", Enum: []string{
			BackupStateRunning,
			BackupStateSuccess,
			BackupStateSkipped,
			BackupStateFailure,
		}},
		{Key: "started_ts", Kind: schema.KindStr},
		{Key: "finished_ts", Kind: schema.KindStr},
		{Key: "duration_s", Kind: schema.KindInt},
		{Key: "success_bool", Kind: schema.KindBool},
		{Key: "kind", Kind: schema.KindStr},
		{Key: "version", Kind: schema.KindStr},
		{Key: "file_count", Kind: schema.KindInt},
		{Key: "size_mb", Kind: schema.KindInt},
	}}
	return []schema.Payload{
		{
			Role:  schema.RoleState,
			Match: "*/leader/lease",
			Root: schema.Member{Members: []schema.Member{
				{Key: "host", Kind: schema.KindStr},
				{Key: "epoch", Kind: schema.KindInt},
				{Key: "claimed_ts", Kind: schema.KindStr},
				{Key: "renewed_ts", Kind: schema.KindStr},
			}},
		},
		{
			Role:  schema.RoleState,
			Match: "*/leader/candidate/*",
			Root: schema.Member{Members: []schema.Member{
				{Key: "host", Kind: schema.KindStr},
				{Key: "renewed_ts", Kind: schema.KindStr},
			}},
		},
		{
			Role:  schema.RoleState,
			Match: "*/" + HostAll + "/backup/status",
			Root: schema.Member{Members: []schema.Member{
				{Key: "run_id", Kind: schema.KindStr},
				{Key: "state", Enum: []string{
					BackupStateRunning,
					BackupStateSuccess,
					BackupStateFailure,
					BackupStateTimeout,
				}},
				{Key: "started_ts", Kind: schema.KindStr},
				{Key: "finished_ts", Kind: schema.KindStr},
				{Key: "duration_s", Kind: schema.KindInt},
				{Key: "success_bool", Kind: schema.KindBool},
				{Key: "power_bool", Kind: schema.KindBool},
				{Key: "hosts_expected", Kind: schema.KindInt},
				{Key: "hosts_reported", Kind: schema.KindInt},
				{Key: "hosts_failed", Kind: schema.KindInt},
				{Key: "leader_host", Kind: schema.KindStr},
				{Key: "leader_epoch", Kind: schema.KindInt},
			}},
		},
		{Role: schema.RoleState, Match: "*/backup/status", Root: backupHostStatus},
		{
			Role:  schema.RoleState,
			Match: "*/backup/stage/tertiary/scrub/status",
			Root: schema.Member{Members: []schema.Member{
				{Key: "run_id", Kind: schema.KindStr},
				{Key: "state", Enum: []string{
					BackupStateSuccess,
					BackupStateSkipped,
					BackupStateStopped,
					BackupStateTimeout,
					BackupStateFailure,
					BackupStateRunning,
				}},
				{Key: "started_ts", Kind: schema.KindStr},
				{Key: "finished_ts", Kind: schema.KindStr},
				{Key: "duration_s", Kind: schema.KindInt},
				{Key: "expires_ts", Kind: schema.KindStr},
				{Key: "success_bool", Kind: schema.KindBool},
				{Key: "scrubbed_mb", Kind: schema.KindInt},
				{Key: "progress_perc", Kind: schema.KindFloat},
				{Key: "errors_found", Kind: schema.KindInt},
				{Key: "errors_corrected", Kind: schema.KindInt},
				{Key: "errors_uncorrectable", Kind: schema.KindInt},
				{Key: "files_to_delete", Kind: schema.KindStr},
				{Key: "files_to_delete_count", Kind: schema.KindInt},
				{Key: "device_errors", Kind: schema.KindInt},
				{Key: "chunks_relocated", Kind: schema.KindInt},
			}},
		},
		{Role: schema.RoleState, Match: "*/backup/stage/*/service/*/status", Root: backupServiceStatus},
		{Role: schema.RoleState, Match: "*/backup/stage/*/status", Root: backupStageStatus},
		{
			Role: schema.RoleState,
			Root: schema.Member{Members: []schema.Member{
				{Key: "timestamp", Kind: schema.KindInt},
				{Key: "failed", Kind: schema.KindBool},
				detail("pulse"),
				detail("trend"),
			}},
		},
		{
			Role:  schema.RoleState,
			Match: "*/backup/reaper",
			Root: schema.Member{Members: []schema.Member{
				{Key: "state", Enum: []string{CommandOn, CommandOff}},
				{Key: "expires_ts", Kind: schema.KindStr},
			}},
		},
		{
			Role: schema.RoleCommand,
			Root: schema.Member{Enum: []string{CommandOn, CommandOff}},
		},
		{
			Role: schema.RoleAvailability,
			Root: schema.Member{Enum: []string{AvailabilityOnline, AvailabilityOffline}},
		},
	}
}

func TopicLeaderCandidate(host string) string {
	return TopicLeaderRoot + "/candidate/" + host
}

func TopicBackupRoot(host string) string {
	return "supervisor/" + host + "/backup"
}

func TopicBackupStatus(host string) string {
	return TopicBackupRoot(host) + "/status"
}

func TopicBackupStage(host, stage string) string {
	return TopicBackupRoot(host) + "/stage/" + stage + "/status"
}

func TopicBackupStagePrefix(host string) string {
	return TopicBackupRoot(host) + "/stage/"
}

func TopicBackupService(host, service string) string {
	return TopicBackupRoot(host) + "/stage/primary/service/" + service + "/status"
}

func TopicBackupScrub(host string) string {
	return TopicBackupRoot(host) + "/stage/tertiary/scrub/status"
}

func TopicBackupReaper() string {
	return TopicBackupRoot(HostAll) + "/reaper"
}

const (
	BackupStateRunning = "running"
	BackupStateSuccess = "success"
	BackupStateSkipped = "skipped"
	BackupStateStopped = "stopped"
	BackupStateTimeout = "timeout"
	BackupStateFailure = "failure"

	BackupTriggerSystem = "system"
	BackupTriggerManual = "manual"
)

const (
	LeaderElection     = "leader"
	LeaderDutyBackup   = "backup"
	LeaderDutySentinel = "sentinel"

	EntityCluster = "cluster"
	EntityHost    = "host"
	EntityService = "service"

	TopicAllStatus   = "supervisor/" + HostAll + "/status"
	TopicLeaderRoot  = "supervisor/" + HostAll + "/leader"
	TopicLeaderLease = TopicLeaderRoot + "/lease"
	TopicAllCommand  = "supervisor/" + HostAll + "/command/" + EntityCluster
)

const (
	CommandOn  = "ON"
	CommandOff = "OFF"
)

const (
	AvailabilityOnline  = "online"
	AvailabilityOffline = "offline"
)
