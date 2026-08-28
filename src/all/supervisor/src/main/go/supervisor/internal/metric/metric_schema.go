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
	return []schema.Payload{
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
