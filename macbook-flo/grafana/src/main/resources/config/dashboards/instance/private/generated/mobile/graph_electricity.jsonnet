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
                style='minimal',
                formFactor='Mobile',
                datasource='InfluxDB_V2',

// TODO: Update this to include metadata rows when re-implemented in Go
                measurement='__FIXME__',

                maxMilliSecSinceUpdate='259200000',
            ) +

            [

                  graph.new(
                        title='Power Consumption',
                        datasource='InfluxDB_V2',
                        fill=0,
                        format='short',
                        bars=false,
                        lines=true,
                        staircase=false,
                  ).addTarget(influxdb.target(query='
from(bucket: "home_private")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["entity_id"] == "various_adhoc_power_consumption" or r["entity_id"] == "rack_modem_power_consumption" or r["entity_id"] == "rack_power_power_consumption" or r["entity_id"] == "roof_switch_power_consumption" or r["entity_id"] == "kitchen_fan_power_consumption" or r["entity_id"] == "kitchen_fridge_power_consumption" or r["entity_id"] == "kitchen_coffee_power_consumption" or r["entity_id"] == "deck_freezer_power_consumption" or r["entity_id"] == "deck_festoons_power_consumption" or r["entity_id"] == "office_power_power_consumption" or r["entity_id"] == "lounge_tv_power_consumption" or r["entity_id"] == "study_power_power_consumption" or r["entity_id"] == "bathroom_towelrails_power_consumption")
  |> keep(columns: ["_time", "_value", "friendly_name"])
  |> aggregateWindow(every: v.windowPeriod, fn: mean, createEmpty: true)
                  '))
                  { gridPos: { x: 0, y: 2, w: 24, h: 12 } },

                  graph.new(
                        title='Energy Consumption',
                        datasource='InfluxDB_V2',
                        fill=0,
                        format='short',
                        bars=false,
                        lines=true,
                        staircase=false,
                  ).addTarget(influxdb.target(query='
from(bucket: "home_private")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["entity_id"] == "various_adhoc_energy_consumption" or r["entity_id"] == "rack_modem_energy_consumption" or r["entity_id"] == "rack_power_energy_consumption" or r["entity_id"] == "roof_switch_energy_consumption" or r["entity_id"] == "kitchen_fan_energy_consumption" or r["entity_id"] == "kitchen_fridge_energy_consumption" or r["entity_id"] == "kitchen_coffee_energy_consumption" or r["entity_id"] == "deck_freezer_energy_consumption" or r["entity_id"] == "deck_festoons_energy_consumption" or r["entity_id"] == "lounge_tv_energy_consumption" or r["entity_id"] == "study_power_energy_consumption" or r["entity_id"] == "office_power_energy_consumption" or r["entity_id"] == "bathroom_towelrails_energy_consumption")
  |> keep(columns: ["_time", "_value", "friendly_name"])
  |> aggregateWindow(every: v.windowPeriod, fn: mean, createEmpty: false)
                  '))
                  { gridPos: { x: 0, y: 2, w: 24, h: 12 } },

            ],
}
