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
                datasource='InfluxDB_V2',
                measurement='currency',
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
  |> filter(fn: (r) => r["entity_id"] == "fridge_power_consumption" or r["entity_id"] == "servers_power_consumption" or r["entity_id"] == "kitchenfan_power_consumption" or r["entity_id"] == "towelrails_power_consumption")
  |> keep(columns: ["_time", "_value", "friendly_name"])
  |> aggregateWindow(every: v.windowPeriod, fn: mean, createEmpty: false)
                  '))
                  { gridPos: { x: 0, y: 0, w: 24, h: 12 } },

                  graph.new(
                        title='Energy Consumption',
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
  |> filter(fn: (r) => r["entity_id"] == "fridge_energy_consumption" or r["entity_id"] == "servers_energy_consumption" or r["entity_id"] == "kitchenfan_energy_consumption" or r["entity_id"] == "towelrails_energy_consumption")
  |> keep(columns: ["_time", "_value", "friendly_name"])
  |> aggregateWindow(every: v.windowPeriod, fn: mean, createEmpty: false)
                  '))
                  { gridPos: { x: 0, y: 0, w: 24, h: 12 } },

            ],
}
