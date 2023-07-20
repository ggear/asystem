{
      graphs()::

            local grafana = import 'grafonnet/grafana.libsonnet';
            local asystem = import 'default/generated/asystem-library.jsonnet';
            local dashboard = grafana.dashboard;
            local stat = grafana.statPanel;
            local graph = grafana.graphPanel;
            local table = grafana.tablePanel;
            local gauge = grafana.gaugePanel;
            local bar = grafana.barGaugePanel;
            local influxdb = grafana.influxdb;
            local header = asystem.header;

            header.new(
                style='maximal',
                formFactor='Desktop',
                datasource='InfluxDB_V2',

// TODO: Update this to include metadata rows when re-implemented in Go
                measurement='__FIXME__',

                maxMilliSecSinceUpdate='259200000',
            ) +

            [

                  graph.new(
                        title='Current Power Consumption',
                        datasource='InfluxDB_V2',
                        fill=0,
                        format='short',
                        bars=false,
                        lines=true,
                        staircase=false,
                        legend_values=true,
                        legend_min=true,
                        legend_max=true,
                        legend_current=false,
                        legend_total=false,
                        legend_avg=true,
                        legend_alignAsTable=true,
                        legend_rightSide=true,
                        legend_sideWidth=400,
                  ).addTarget(influxdb.target(query='
from(bucket: "home_private")
|> range(start: v.timeRangeStart, stop: v.timeRangeStop)
|> filter(fn: (r) => r["entity_id"] == "home_power" or r["entity_id"] == "home_base_power" or r["entity_id"] == "home_peak_power")
|> filter(fn: (r) => r["_field"] == "value")
|> keep(columns: ["_time", "_value", "friendly_name"])
|> aggregateWindow(every: v.windowPeriod, fn: mean, createEmpty: true)
                  '))
                  { gridPos: { x: 0, y: 2, w: 24, h: 12 } },

                  graph.new(
                        title='Current Power Consumption',
                        datasource='InfluxDB_V2',
                        fill=0,
                        format='short',
                        bars=false,
                        lines=true,
                        staircase=false,
                        legend_values=true,
                        legend_min=true,
                        legend_max=true,
                        legend_current=false,
                        legend_total=false,
                        legend_avg=true,
                        legend_alignAsTable=true,
                        legend_rightSide=true,
                        legend_sideWidth=400,
                  ).addTarget(influxdb.target(query='
from(bucket: "home_private")
|> range(start: v.timeRangeStart, stop: v.timeRangeStop)
|> filter(fn: (r) => r["entity_id"] == "lights_power" or r["entity_id"] == "fans_power" or r["entity_id"] == "all_standby_power" or r["entity_id"] == "kitchen_coffee_machine_power" or r["entity_id"] == "study_battery_charger_power" or r["entity_id"] == "laundry_vacuum_charger_power" or r["entity_id"] == "roof_water_booster_power" or r["entity_id"] == "kitchen_dish_washer_power" or r["entity_id"] == "laundry_clothes_dryer_power" or r["entity_id"] == "laundry_washing_machine_power" or r["entity_id"] == "kitchen_fridge_power" or r["entity_id"] == "deck_freezer_power" or r["entity_id"] == "bathroom_towel_rails_power" or r["entity_id"] == "study_outlet_power" or r["entity_id"] == "office_outlet_power" or r["entity_id"] == "audio_visual_devices_power" or r["entity_id"] == "servers_network_power")
|> filter(fn: (r) => r["_field"] == "value")
|> keep(columns: ["_time", "_value", "friendly_name"])
|> aggregateWindow(every: v.windowPeriod, fn: mean, createEmpty: true)
                  '))
                  { gridPos: { x: 0, y: 2, w: 24, h: 12 } },

                  graph.new(
                        title='Daily Energy Consumption',
                        datasource='InfluxDB_V2',
                        fill=0,
                        format='short',
                        bars=false,
                        lines=true,
                        staircase=false,
                        legend_values=true,
                        legend_min=true,
                        legend_max=true,
                        legend_current=false,
                        legend_total=false,
                        legend_avg=true,
                        legend_alignAsTable=true,
                        legend_rightSide=true,
                        legend_sideWidth=400,
                  ).addTarget(influxdb.target(query='
from(bucket: "home_private")
|> range(start: v.timeRangeStart, stop: v.timeRangeStop)
|> filter(fn: (r) => r["entity_id"] == "home_energy_daily" or r["entity_id"] == "home_base_energy_daily" or r["entity_id"] == "home_peak_energy_daily")
|> filter(fn: (r) => r["_field"] == "value")
|> keep(columns: ["_time", "_value", "friendly_name"])
|> aggregateWindow(every: v.windowPeriod, fn: mean, createEmpty: false)
                  '))
                  { gridPos: { x: 0, y: 2, w: 24, h: 12 } },

                  graph.new(
                        title='Daily Energy Consumption',
                        datasource='InfluxDB_V2',
                        fill=0,
                        format='short',
                        bars=false,
                        lines=true,
                        staircase=false,
                        legend_values=true,
                        legend_min=true,
                        legend_max=true,
                        legend_current=false,
                        legend_total=false,
                        legend_avg=true,
                        legend_alignAsTable=true,
                        legend_rightSide=true,
                        legend_sideWidth=400,
                  ).addTarget(influxdb.target(query='
from(bucket: "home_private")
|> range(start: v.timeRangeStart, stop: v.timeRangeStop)
|> filter(fn: (r) => r["entity_id"] == "lights_energy_daily" or r["entity_id"] == "fans_energy_daily" or r["entity_id"] == "all_standby_energy_daily" or r["entity_id"] == "kitchen_coffee_machine_energy_daily" or r["entity_id"] == "study_battery_charger_energy_daily" or r["entity_id"] == "laundry_vacuum_charger_energy_daily" or r["entity_id"] == "roof_water_booster_energy_daily" or r["entity_id"] == "kitchen_dish_washer_energy_daily" or r["entity_id"] == "laundry_clothes_dryer_energy_daily" or r["entity_id"] == "laundry_washing_machine_energy_daily" or r["entity_id"] == "kitchen_fridge_energy_daily" or r["entity_id"] == "deck_freezer_energy_daily" or r["entity_id"] == "bathroom_towel_rails_energy_daily" or r["entity_id"] == "study_outlet_energy_daily" or r["entity_id"] == "office_outlet_energy_daily" or r["entity_id"] == "audio_visual_devices_energy_daily" or r["entity_id"] == "servers_network_energy_daily")
|> filter(fn: (r) => r["_field"] == "value")
|> keep(columns: ["_time", "_value", "friendly_name"])
|> aggregateWindow(every: v.windowPeriod, fn: mean, createEmpty: false)
                  '))
                  { gridPos: { x: 0, y: 2, w: 24, h: 12 } },

            ],
}
