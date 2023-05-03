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
                        title='Rain',
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
|> filter(fn: (r) => r["entity_id"] == "roof_hourly_rain")
|> filter(fn: (r) => r["_field"] == "value")
|> keep(columns: ["_time", "_value", "friendly_name"])
|> aggregateWindow(every: v.windowPeriod, fn: mean, createEmpty: false)
                  '))
                  { gridPos: { x: 0, y: 2, w: 24, h: 12 } },

                  graph.new(
                        title='Rain',
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
|> filter(fn: (r) => r["entity_id"] == "roof_daily_rain")
|> filter(fn: (r) => r["_field"] == "value")
|> keep(columns: ["_time", "_value", "friendly_name"])
|> aggregateWindow(every: v.windowPeriod, fn: mean, createEmpty: false)
                  '))
                  { gridPos: { x: 0, y: 2, w: 24, h: 12 } },

                  graph.new(
                        title='Rain',
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
|> filter(fn: (r) => r["entity_id"] == "roof_yearly_rain")
|> filter(fn: (r) => r["_field"] == "value")
|> keep(columns: ["_time", "_value", "friendly_name"])
|> aggregateWindow(every: v.windowPeriod, fn: mean, createEmpty: false)
                  '))
                  { gridPos: { x: 0, y: 2, w: 24, h: 12 } },

            ],
}
