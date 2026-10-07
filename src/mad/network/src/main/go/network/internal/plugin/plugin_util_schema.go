package plugin

import (
	"network/internal/config"
	"network/internal/remote"
	"network/internal/schema"
)

const aggregateCadence = config.DefaultAggregatePeriod

func Schema() schema.Database {
	plugins := registered()
	names := make([]string, 0, len(plugins))
	for _, p := range plugins {
		names = append(names, p.Name())
	}
	diagnosis.Entities(names...)
	return schema.Registered()
}

func BrokerSchema() schema.Broker { return schema.Broker(brokerPayloads) }

var brokerPayloads = []schema.Payload{
	{
		Role: schema.RoleState,
		Root: schema.Member{Members: []schema.Member{
			{Key: "timestamp", Kind: schema.KindInt},
			{Key: "ok", Kind: schema.KindBool},
			{Key: "status", Kind: schema.KindStr, Enum: []string{string(StatusFit), string(StatusSick), string(StatusDead)}},
			{Key: "score", Kind: schema.KindInt, Enum: []string{"0-100"}},
		}},
	},
	{
		Role: schema.RoleCommand,
		Root: schema.Member{Enum: []string{StateOn.String(), StateOff.String()}},
	},
	{
		Role: schema.RoleAvailability,
		Root: schema.Member{Enum: []string{remote.BrokerStatusOnline, remote.BrokerStatusOffline}},
	},
}
