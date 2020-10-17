{
  graphs()::
  
    local grafana = import 'grafonnet/grafana.libsonnet';
    local dashboard = grafana.dashboard;
    local graph = grafana.graphPanel;
    local table = grafana.tablePanel;
    local influxdb = grafana.influxdb;
    
    [

      table.new(
        title='WAN',
        datasource='InfluxDB2'
      ).addTarget(influxdb.target(query='
from(bucket: "hosts")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "usg" and r["_field"] == "ip")
  |> unique(column: "_value")
  |> set(key: "name", value: "IP")
  |> keep(columns: ["_time", "_value", "name"])
  |> sort(columns: ["_time"], desc: true)
      ')) { gridPos: { x: 0, y: 0, w: 6, h: 6 } },

      graph.new(
        title='WAN',
        datasource='InfluxDB2',
        fill=0,
        format='decBps',
        bars=true,
        lines=false,
        staircase=false,
        legend_values=true,
        legend_min=true,
        legend_max=true,
        legend_current=true,
        legend_total=false,
        legend_avg=true,
        legend_alignAsTable=true,
        legend_rightSide=true,
        legend_sideWidth=350
      ).addTarget(influxdb.target(query='
from(bucket: "hosts")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "usg_wan_ports")
  |> filter(fn: (r) => r["_field"] == "rx_bytes")
  |> set(key: "name", value: "Receiving")
  |> keep(columns: ["table", "_start", "_stop", "_time", "_value", "name"])
  |> aggregateWindow(every: v.windowPeriod, fn: max, createEmpty: true)
  |> derivative(unit: 1s, nonNegative: true)
      ')).addTarget(influxdb.target(query='
from(bucket: "hosts")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "usg_wan_ports")
  |> filter(fn: (r) => r["_field"] == "tx_bytes")
  |> set(key: "name", value: "Transmitting")
  |> keep(columns: ["table", "_start", "_stop", "_time", "_value", "name"])
  |> aggregateWindow(every: v.windowPeriod, fn: max, createEmpty: true)
  |> derivative(unit: 1s, nonNegative: true)
      ')).addSeriesOverride(
        { "alias": "Transmitting", "transform": "negative-Y" }
      ) { gridPos: { x: 0, y: 0, w: 24, h: 12 } },

      graph.new(
        title='LAN',
        datasource='InfluxDB2',
        fill=0,
        format='decBps',
        bars=true,
        lines=false,
        staircase=false,
        legend_values=true,
        legend_min=true,
        legend_max=true,
        legend_current=true,
        legend_total=false,
        legend_avg=true,
        legend_alignAsTable=true,
        legend_rightSide=true,
        legend_sideWidth=350
      ).addTarget(influxdb.target(query='
from(bucket: "hosts")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "usg")
  |> filter(fn: (r) => r["_field"] == "lan-rx_bytes")
  |> set(key: "name", value: "Receiving")
  |> keep(columns: ["table", "_start", "_stop", "_time", "_value", "name"])
  |> aggregateWindow(every: v.windowPeriod, fn: max, createEmpty: true)
  |> derivative(unit: 1s, nonNegative: true)
      ')).addTarget(influxdb.target(query='
from(bucket: "hosts")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "usg")
  |> filter(fn: (r) => r["_field"] == "lan-tx_bytes")
  |> set(key: "name", value: "Transmitting")
  |> keep(columns: ["table", "_start", "_stop", "_time", "_value", "name"])
  |> aggregateWindow(every: v.windowPeriod, fn: max, createEmpty: true)
  |> derivative(unit: 1s, nonNegative: true)
      ')).addSeriesOverride(
        { "alias": "Transmitting", "transform": "negative-Y" }
      ) { gridPos: { x: 0, y: 0, w: 24, h: 12 } },

    ],
}
