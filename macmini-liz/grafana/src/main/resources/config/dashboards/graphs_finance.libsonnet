{
  graphs()::
  
    local grafana = import 'grafonnet/grafana.libsonnet';
    local dashboard = grafana.dashboard;
    local stat = grafana.statPanel;
    local graph = grafana.graphPanel;
    local table = grafana.tablePanel;
    local gauge = grafana.gaugePanel;
    local bar = grafana.barGaugePanel;
    local influxdb = grafana.influxdb;
    
    [

      graph.new(
        title='FX Rates',
        datasource='InfluxDB2',
        fill=0,
        format='',
        bars=false,
        lines=true,
        staircase=true,
        legend_values=true,
        legend_min=true,
        legend_max=true,
        legend_current=true,
        legend_total=false,
        legend_avg=false,
        legend_alignAsTable=true,
        legend_rightSide=true,
        legend_sideWidth=425
      ).addTarget(influxdb.target(query='// Start
from(bucket: "asystem")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "fx")
  |> filter(fn: (r) => r["_field"] == "GBP/AUD Daily" or r["_field"] == "SGD/AUD Daily" or r["_field"] == "USD/AUD Daily")
  |> keep(columns: ["_time", "_value", "_field"])
// End')).addSeriesOverride(
        { "alias": "/.*Transmit.*/", "transform": "negative-Y" }
      ) { gridPos: { x: 0, y: 0, w: 24, h: 12 } },

      graph.new(
        title='FX Rates',
        datasource='InfluxDB2',
        fill=0,
        format='',
        bars=false,
        lines=true,
        staircase=true,
        legend_values=true,
        legend_min=true,
        legend_max=true,
        legend_current=true,
        legend_total=false,
        legend_avg=false,
        legend_alignAsTable=true,
        legend_rightSide=true,
        legend_sideWidth=425
      ).addTarget(influxdb.target(query='// Start
from(bucket: "asystem")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "fx")
  |> filter(fn: (r) => r["_field"] == "GBP/AUD Weekly" or r["_field"] == "SGD/AUD Weekly" or r["_field"] == "USD/AUD Weekly")
  |> keep(columns: ["_time", "_value", "_field"])
// End')).addSeriesOverride(
        { "alias": "/.*Transmit.*/", "transform": "negative-Y" }
      ) { gridPos: { x: 0, y: 12, w: 24, h: 12 } },

      graph.new(
        title='FX Rates',
        datasource='InfluxDB2',
        fill=0,
        format='',
        bars=false,
        lines=true,
        staircase=true,
        legend_values=true,
        legend_min=true,
        legend_max=true,
        legend_current=true,
        legend_total=false,
        legend_avg=false,
        legend_alignAsTable=true,
        legend_rightSide=true,
        legend_sideWidth=425
      ).addTarget(influxdb.target(query='// Start
from(bucket: "asystem")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "fx")
  |> filter(fn: (r) => r["_field"] == "GBP/AUD Monthly" or r["_field"] == "SGD/AUD Monthly" or r["_field"] == "USD/AUD Monthly")
  |> keep(columns: ["_time", "_value", "_field"])
// End')).addSeriesOverride(
        { "alias": "/.*Transmit.*/", "transform": "negative-Y" }
      ) { gridPos: { x: 0, y: 24, w: 24, h: 12 } },

      graph.new(
        title='FX Rates',
        datasource='InfluxDB2',
        fill=0,
        format='',
        bars=false,
        lines=true,
        staircase=true,
        legend_values=true,
        legend_min=true,
        legend_max=true,
        legend_current=true,
        legend_total=false,
        legend_avg=false,
        legend_alignAsTable=true,
        legend_rightSide=true,
        legend_sideWidth=425
      ).addTarget(influxdb.target(query='// Start
from(bucket: "asystem")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "fx")
  |> filter(fn: (r) => r["_field"] == "GBP/AUD Yearly" or r["_field"] == "SGD/AUD Yearly" or r["_field"] == "USD/AUD Yearly")
  |> keep(columns: ["_time", "_value", "_field"])
// End')).addSeriesOverride(
        { "alias": "/.*Transmit.*/", "transform": "negative-Y" }
      ) { gridPos: { x: 0, y: 36, w: 24, h: 12 } },

      graph.new(
        title='FX Rates',
        datasource='InfluxDB2',
        fill=0,
        format='',
        bars=false,
        lines=true,
        staircase=true,
        legend_values=true,
        legend_min=true,
        legend_max=true,
        legend_current=true,
        legend_total=false,
        legend_avg=false,
        legend_alignAsTable=true,
        legend_rightSide=true,
        legend_sideWidth=425
      ).addTarget(influxdb.target(query='// Start
from(bucket: "asystem")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "fx")
  |> filter(fn: (r) => r["_field"] == "GBP/AUD" or r["_field"] == "SGD/AUD" or r["_field"] == "USD/AUD")
  |> keep(columns: ["_time", "_value", "_field"])
// End')).addSeriesOverride(
        { "alias": "/.*Transmit.*/", "transform": "negative-Y" }
      ) { gridPos: { x: 0, y: 48, w: 24, h: 12 } },

    ],
}
