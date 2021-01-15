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
        title='GBP/AUD Dailies',
        datasource='InfluxDB2',
        fill=0,
        format='',
        bars=true,
        lines=false,
        staircase=false,
        formatY1='percent',
        min=-2,
        max=2,
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
  |> filter(fn: (r) => r["period"] == "daily")
  |> filter(fn: (r) => r["type"] == "snapshot")
  |> filter(fn: (r) => r["_field"] == "GBP/AUD")
  |> keep(columns: ["_time", "_value", "type"])
// End')).addTarget(influxdb.target(query='// Start
from(bucket: "asystem")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "fx")
  |> filter(fn: (r) => r["period"] == "daily")
  |> filter(fn: (r) => r["type"] == "delta")
  |> filter(fn: (r) => r["_field"] == "GBP/AUD")
  |> keep(columns: ["_time", "_value", "type"])
// End')).addSeriesOverride(
        { "alias": "/.*snapshot.*/", "bars": false, "lines": true, "linewidth": 2, "zindex": 3, "yaxis": 2 }
      ) { gridPos: { x: 0, y: 0, w: 24, h: 12 } },

      graph.new(
        title='USD/AUD Dailies',
        datasource='InfluxDB2',
        fill=0,
        format='',
        bars=true,
        lines=false,
        staircase=false,
        formatY1='percent',
        min=-2,
        max=2,
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
  |> filter(fn: (r) => r["period"] == "daily")
  |> filter(fn: (r) => r["type"] == "snapshot")
  |> filter(fn: (r) => r["_field"] == "USD/AUD")
  |> keep(columns: ["_time", "_value", "type"])
// End')).addTarget(influxdb.target(query='// Start
from(bucket: "asystem")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "fx")
  |> filter(fn: (r) => r["period"] == "daily")
  |> filter(fn: (r) => r["type"] == "delta")
  |> filter(fn: (r) => r["_field"] == "USD/AUD")
  |> keep(columns: ["_time", "_value", "type"])
// End')).addSeriesOverride(
        { "alias": "/.*snapshot.*/", "bars": false, "lines": true, "linewidth": 2, "zindex": 3, "yaxis": 2 }
      ) { gridPos: { x: 0, y: 12, w: 24, h: 12 } },

      graph.new(
        title='SGD/AUD Dailies',
        datasource='InfluxDB2',
        fill=0,
        format='',
        bars=true,
        lines=false,
        staircase=false,
        formatY1='percent',
        min=-2,
        max=2,
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
  |> filter(fn: (r) => r["period"] == "daily")
  |> filter(fn: (r) => r["type"] == "snapshot")
  |> filter(fn: (r) => r["_field"] == "SGD/AUD")
  |> keep(columns: ["_time", "_value", "type"])
// End')).addTarget(influxdb.target(query='// Start
from(bucket: "asystem")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "fx")
  |> filter(fn: (r) => r["period"] == "daily")
  |> filter(fn: (r) => r["type"] == "delta")
  |> filter(fn: (r) => r["_field"] == "SGD/AUD")
  |> keep(columns: ["_time", "_value", "type"])
// End')).addSeriesOverride(
        { "alias": "/.*snapshot.*/", "bars": false, "lines": true, "linewidth": 2, "zindex": 3, "yaxis": 2 }
      ) { gridPos: { x: 0, y: 24, w: 24, h: 12 } },

      graph.new(
        title='CCY Daily Snapshots',
        datasource='InfluxDB2',
        fill=1,
        format='',
        bars=false,
        lines=true,
        staircase=false,
        formatY1='percent',
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
  |> filter(fn: (r) => r["period"] == "daily")
  |> filter(fn: (r) => r["type"] == "snapshot")
  |> keep(columns: ["_time", "_value", "_field"])
// End')) { gridPos: { x: 0, y: 36, w: 24, h: 12 } },

      graph.new(
        title='CCY Daily Deltas',
        datasource='InfluxDB2',
        fill=0,
        format='',
        bars=false,
        lines=true,
        staircase=true,
        formatY1='percent',
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
  |> filter(fn: (r) => r["period"] == "daily")
  |> filter(fn: (r) => r["type"] == "delta")
  |> keep(columns: ["_time", "_value", "_field"])
// End')) { gridPos: { x: 0, y: 48, w: 24, h: 12 } },

      graph.new(
        title='CCY Weekly Deltas',
        datasource='InfluxDB2',
        fill=0,
        format='',
        bars=false,
        lines=true,
        staircase=true,
        formatY1='percent',
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
  |> filter(fn: (r) => r["period"] == "weekly")
  |> filter(fn: (r) => r["type"] == "delta")
  |> keep(columns: ["_time", "_value", "_field"])
// End')) { gridPos: { x: 0, y: 60, w: 24, h: 12 } },

      graph.new(
        title='CCY Monthly Deltas',
        datasource='InfluxDB2',
        fill=0,
        format='',
        bars=false,
        lines=true,
        staircase=true,
        formatY1='percent',
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
  |> filter(fn: (r) => r["period"] == "monthly")
  |> filter(fn: (r) => r["type"] == "delta")
  |> keep(columns: ["_time", "_value", "_field"])
// End')) { gridPos: { x: 0, y: 72, w: 24, h: 12 } },

      graph.new(
        title='CCY Yearly Deltas',
        datasource='InfluxDB2',
        fill=0,
        format='',
        bars=false,
        lines=true,
        staircase=true,
        formatY1='percent',
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
  |> filter(fn: (r) => r["period"] == "yearly")
  |> filter(fn: (r) => r["type"] == "delta")
  |> keep(columns: ["_time", "_value", "_field"])
// End')) { gridPos: { x: 0, y: 84, w: 24, h: 12 } },

    ],
}
