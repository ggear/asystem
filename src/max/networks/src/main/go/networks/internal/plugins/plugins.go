package plugins

import (
	"networks/internal/config"
	"networks/internal/schema"
)

const aggregateCadence = config.DefaultAggregatePeriod

func Schema() schema.Database { return schema.Registered() }

func BrokerSchema() schema.Broker { return schema.Broker(brokerPayloads) }

var brokerPayloads = []schema.Payload{
	{
		Role: schema.RoleState,
		Root: schema.Member{Members: []schema.Member{
			{Key: "timestamp", Kind: schema.KindInt},
			{Key: "ok", Kind: schema.KindBool},
			{Key: "status", Kind: schema.KindStr, Enum: []string{"fit", "sick", "dead"}},
			{Key: "score", Kind: schema.KindInt, Enum: []string{"0-100"}},
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
