{
  graphs()::
  
    local grafana = import 'grafonnet/grafana.libsonnet';
    local dashboard = grafana.dashboard;
    local graph = grafana.graphPanel;
    local influxdb = grafana.influxdb;
    
    [

      graph.new(
        title='WAN',
        datasource='InfluxDB2',
        fill=0,
        format='decBps',
        staircase=true
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
      ) { gridPos: { x: 0, y: 0, w: 24, h: 10 } },

    ],
}
