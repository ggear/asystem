{
  graphs()::
  
    local grafana = import 'grafonnet/grafana.libsonnet';
    local dashboard = grafana.dashboard;
    local graph = grafana.graphPanel;
    local influxdb = grafana.influxdb;
    
    [

      graph.new(
        title='Temperature',
        datasource='InfluxDB2',
        fill=0,
        format='ºC',
        bars=false,
        lines=true,
        staircase=false,
        legend_values=true,
        legend_min=true,
        legend_max=true,
        legend_current=true,
        legend_total=false,
        legend_avg=false,
        legend_alignAsTable=true,
        legend_rightSide=true,
        legend_sideWidth=350
      ).addTarget(influxdb.target(query='// Start
from(bucket: "hosts")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "sensors" and r["_field"] == "temp_input" and r["feature"] == "package_id_0")
  |> keep(columns: ["table", "_start", "_stop", "_time", "_value", "host"])
  |> aggregateWindow(every: v.windowPeriod, fn: max, createEmpty: false)
// End')).addTarget(influxdb.target(query='// Start
from(bucket: "hosts")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "usg" and r["_field"] == "temp_CPU")
  |> set(key: "host", value: "udm-rack")
  |> keep(columns: ["table", "_start", "_stop", "_time", "_value", "host"])
  |> aggregateWindow(every: v.windowPeriod, fn: max, createEmpty: false)
// End')).addTarget(influxdb.target(query='// Start
from(bucket: "asystem")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["entity_id"] == "utility_temperature")
  |> set(key: "host", value: "ambient-rack")
  |> keep(columns: ["table", "_start", "_stop", "_time", "_value", "host"])
  |> aggregateWindow(every: v.windowPeriod, fn: max, createEmpty: false)
      '))
      { gridPos: { x: 0, y: 0, w: 24, h: 12 } },

    ],
}
