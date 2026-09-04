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
		topics = append(topics, schema.Topic{
			Template: strings.ReplaceAll(builder.template, "$SCOPE", ScopeData),
			Role:     schema.RoleState,
		})
	}
	for _, template := range []string{
		"supervisor/$HOST/backup/status",
		"supervisor/$HOST/backup/stage/$STAGE/status",
		"supervisor/$HOST/backup/stage/primary/service/$BACKUP_SERVICE/status",
		"supervisor/cluster-all/backup/leader",
		"supervisor/cluster-all/backup/status",
	} {
		topics = append(topics, schema.Topic{Template: template, Role: schema.RoleState})
	}
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
	backupStatus := schema.Member{Members: []schema.Member{
		{Key: "run_id", Kind: schema.KindStr},
		{Key: "state", Enum: []string{"idle", "running", "complete", "skipped", "failed", "timeout"}},
		{Key: "trigger", Enum: []string{"scheduled", "manual"}},
		{Key: "started_ts", Kind: schema.KindStr},
		{Key: "finished_ts", Kind: schema.KindStr},
		{Key: "expires_ts", Kind: schema.KindStr},
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
	}}
	return []schema.Payload{
		{
			Role:  schema.RoleState,
			Match: "*/backup/leader",
			Root: schema.Member{Members: []schema.Member{
				{Key: "host", Kind: schema.KindStr},
				{Key: "epoch", Kind: schema.KindInt},
				{Key: "run_id", Kind: schema.KindStr},
				{Key: "claimed_ts", Kind: schema.KindStr},
				{Key: "expires_ts", Kind: schema.KindStr},
			}},
		},
		{
			Role:  schema.RoleState,
			Match: "*/cluster-all/backup/status",
			Root: schema.Member{Members: []schema.Member{
				{Key: "run_id", Kind: schema.KindStr},
				{Key: "state", Enum: []string{"running", "complete", "failed", "timeout"}},
				{Key: "started_ts", Kind: schema.KindStr},
				{Key: "finished_ts", Kind: schema.KindStr},
				{Key: "duration_s", Kind: schema.KindInt},
				{Key: "success_bool", Kind: schema.KindBool},
				{Key: "power_bool", Kind: schema.KindBool},
				{Key: "hosts_expected", Kind: schema.KindInt},
				{Key: "hosts_reported", Kind: schema.KindInt},
				{Key: "hosts_failed", Kind: schema.KindInt},
			}},
		},
		{Role: schema.RoleState, Match: "*/backup/status", Root: backupStatus},
		{Role: schema.RoleState, Match: "*/backup/stage/*/status", Root: backupStatus},
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
			Role: schema.RoleCommand,
			Root: schema.Member{Enum: []string{"ON", "OFF"}},
		},
		{
			Role: schema.RoleAvailability,
			Root: schema.Member{Enum: []string{"online", "offline"}},
		},
	}
}
