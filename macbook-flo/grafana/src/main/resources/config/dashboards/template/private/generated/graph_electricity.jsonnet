//ASDASHBOARD_DEFAULTS time_from='now-7d', refresh='', timepicker=timepicker.new(refresh_intervals=['1m'], time_options=['5m', '15m', '1h', '6h', '12h', '24h', '2d', '7d', '30d', '60d', '90d'])
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
//ASM           style='minimal',
//AST           style='medial',
//ASD           style='maximal',
//ASM           formFactor='Mobile',
//AST           formFactor='Tablet',
//ASD           formFactor='Desktop',
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
//ASD                   legend_values=true,
//ASD                   legend_min=true,
//ASD                   legend_max=true,
//ASD                   legend_current=false,
//ASD                   legend_total=false,
//ASD                   legend_avg=true,
//ASD                   legend_alignAsTable=true,
//ASD                   legend_rightSide=true,
//ASD                   legend_sideWidth=330,
                  ).addTarget(influxdb.target(query='
from(bucket: "home_private")
|> range(start: v.timeRangeStart, stop: v.timeRangeStop)
|> filter(fn: (r) => r["entity_id"] == "home_peak_power" or r["entity_id"] == "home_base_power" or r["entity_id"] == "home_power")
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
//ASD                   legend_values=true,
//ASD                   legend_min=true,
//ASD                   legend_max=true,
//ASD                   legend_current=false,
//ASD                   legend_total=false,
//ASD                   legend_avg=true,
//ASD                   legend_alignAsTable=true,
//ASD                   legend_rightSide=true,
//ASD                   legend_sideWidth=330,
                  ).addTarget(influxdb.target(query='
from(bucket: "home_private")
|> range(start: v.timeRangeStart, stop: v.timeRangeStop)
|> filter(fn: (r) => r["entity_id"] == "various_adhoc_outlet_current_consumption" or r["entity_id"] == "study_battery_charger_current_consumption" or r["entity_id"] == "laundry_vacuum_charger_current_consumption" or r["entity_id"] == "home_lights_power" or r["entity_id"] == "home_fans_power" or r["entity_id"] == "kitchen_dish_washer_current_consumption" or r["entity_id"] == "laundry_clothes_dryer_current_consumption" or r["entity_id"] == "laundry_washing_machine_current_consumption" or r["entity_id"] == "kitchen_coffee_machine_current_consumption" or r["entity_id"] == "kitchen_fridge_current_consumption" or r["entity_id"] == "deck_freezer_current_consumption" or r["entity_id"] == "deck_festoons_current_consumption" or r["entity_id"] == "lounge_tv_current_consumption" or r["entity_id"] == "bathroom_rails_current_consumption" or r["entity_id"] == "study_outlet_current_consumption" or r["entity_id"] == "office_outlet_current_consumption" or r["entity_id"] == "server_network_power" or r["entity_id"] == "rack_modem_current_consumption" or r["entity_id"] == "rack_outlet_current_consumption" or r["entity_id"] == "kitchen_fan_current_consumption" or r["entity_id"] == "roof_network_switch_current_consumption")
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
//ASD                   legend_values=true,
//ASD                   legend_min=true,
//ASD                   legend_max=true,
//ASD                   legend_current=false,
//ASD                   legend_total=false,
//ASD                   legend_avg=true,
//ASD                   legend_alignAsTable=true,
//ASD                   legend_rightSide=true,
//ASD                   legend_sideWidth=330,
                  ).addTarget(influxdb.target(query='
from(bucket: "home_private")
|> range(start: v.timeRangeStart, stop: v.timeRangeStop)
|> filter(fn: (r) => r["entity_id"] == "home_peak_energy_daily" or r["entity_id"] == "home_base_energy_daily" or r["entity_id"] == "home_energy_daily")
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
//ASD                   legend_values=true,
//ASD                   legend_min=true,
//ASD                   legend_max=true,
//ASD                   legend_current=false,
//ASD                   legend_total=false,
//ASD                   legend_avg=true,
//ASD                   legend_alignAsTable=true,
//ASD                   legend_rightSide=true,
//ASD                   legend_sideWidth=330,
                  ).addTarget(influxdb.target(query='
from(bucket: "home_private")
|> range(start: v.timeRangeStart, stop: v.timeRangeStop)
|> filter(fn: (r) => r["entity_id"] == "various_adhoc_outlet_today_s_consumption" or r["entity_id"] == "study_battery_charger_today_s_consumption" or r["entity_id"] == "laundry_vacuum_charger_today_s_consumption" or r["entity_id"] == "home_lights_energy_daily" or r["entity_id"] == "home_fans_energy_daily" or r["entity_id"] == "kitchen_dish_washer_today_s_consumption" or r["entity_id"] == "laundry_clothes_dryer_today_s_consumption" or r["entity_id"] == "laundry_washing_machine_today_s_consumption" or r["entity_id"] == "kitchen_coffee_machine_today_s_consumption" or r["entity_id"] == "kitchen_fridge_today_s_consumption" or r["entity_id"] == "deck_freezer_today_s_consumption" or r["entity_id"] == "deck_festoons_today_s_consumption" or r["entity_id"] == "lounge_tv_today_s_consumption" or r["entity_id"] == "bathroom_rails_today_s_consumption" or r["entity_id"] == "study_outlet_today_s_consumption" or r["entity_id"] == "office_outlet_today_s_consumption" or r["entity_id"] == "roof_network_switch_today_s_consumption" or r["entity_id"] == "rack_modem_today_s_consumption" or r["entity_id"] == "server_network_energy_daily" or r["entity_id"] == "rack_outlet_today_s_consumption" or r["entity_id"] == "kitchen_fan_today_s_consumption")
|> keep(columns: ["_time", "_value", "friendly_name"])
|> aggregateWindow(every: v.windowPeriod, fn: mean, createEmpty: false)
                  '))
                  { gridPos: { x: 0, y: 2, w: 24, h: 12 } },

            ],
}
