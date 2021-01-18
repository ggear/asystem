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

      stat.new(
        title='GBP/AUD Last Snapshot',
        datasource='InfluxDB2',
        unit='',
        decimals=3,
        reducerFunction='last',
        colorMode='value',
        graphMode='none',
        justifyMode='auto',
        thresholdsMode='absolute',
        repeatDirection='h',
        pluginVersion='7',
      ).addThreshold(
        { color: 'red', value: 0 }
      ).addThreshold(
        { color: 'yellow', value: 1.58 }
      ).addThreshold(
        { color: 'green', value: 2.07 }
      ).addTarget(influxdb.target(query='// Start
from(bucket: "asystem")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "fx")
  |> filter(fn: (r) => r["_field"] == "GBP/AUD")
  |> filter(fn: (r) => r["period"] == "daily")
  |> filter(fn: (r) => r["type"] == "snapshot")
  |> sort(columns: ["_time"], desc: false)
  |> last()
  |> map(fn: (r) => ({ r with _value: 1.0 / r._value }))
  |> keep(columns: ["_value"])
// End')) { gridPos: { x: 0, y: 0, w: 5, h: 3 } },

      stat.new(
        title='USD/AUD Last Snapshot',
        datasource='InfluxDB2',
        unit='',
        decimals=3,
        reducerFunction='last',
        colorMode='value',
        graphMode='none',
        justifyMode='auto',
        thresholdsMode='absolute',
        repeatDirection='h',
        pluginVersion='7',
      ).addThreshold(
        { color: 'red', value: 0 }
      ).addThreshold(
        { color: 'yellow', value: 1.23 }
      ).addThreshold(
        { color: 'green', value: 1.8 }
      ).addTarget(influxdb.target(query='// Start
from(bucket: "asystem")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "fx")
  |> filter(fn: (r) => r["_field"] == "USD/AUD")
  |> filter(fn: (r) => r["period"] == "daily")
  |> filter(fn: (r) => r["type"] == "snapshot")
  |> sort(columns: ["_time"], desc: false)
  |> last()
  |> map(fn: (r) => ({ r with _value: 1.0 / r._value }))
  |> keep(columns: ["_value"])
// End')) { gridPos: { x: 5, y: 0, w: 5, h: 3 } },

      stat.new(
        title='SGD/AUD Last Snapshot',
        datasource='InfluxDB2',
        unit='',
        decimals=3,
        reducerFunction='last',
        colorMode='value',
        graphMode='none',
        justifyMode='auto',
        thresholdsMode='absolute',
        repeatDirection='h',
        pluginVersion='7',
      ).addThreshold(
        { color: 'red', value: 0 }
      ).addThreshold(
        { color: 'yellow', value: 0.91 }
      ).addThreshold(
        { color: 'green', value: 1.23 }
      ).addTarget(influxdb.target(query='// Start
from(bucket: "asystem")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "fx")
  |> filter(fn: (r) => r["_field"] == "SGD/AUD")
  |> filter(fn: (r) => r["period"] == "daily")
  |> filter(fn: (r) => r["type"] == "snapshot")
  |> sort(columns: ["_time"], desc: false)
  |> map(fn: (r) => ({ r with _value: 1.0 / r._value }))
  |> last()
  |> keep(columns: ["_value"])
// End')) { gridPos: { x: 10, y: 0, w: 5, h: 3 } },

      bar.new(
        title='CCY Ranged Deltas',
        datasource='InfluxDB2',
        unit='percent',
        min=-30,
        max=30,
        thresholds=[
          { 'color': 'red', 'value': -9999 },
          { 'color': 'yellow', 'value': -0.5 },
          { 'color': 'gree', 'value': 0.5 },
        ],
      ).addTarget(influxdb.target(query='// Start
first_snapshot = from(bucket: "asystem")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "fx")
  |> filter(fn: (r) => r["_field"] == "GBP/AUD")
  |> filter(fn: (r) => r["period"] == "daily")
  |> filter(fn: (r) => r["type"] == "snapshot")
  |> sort(columns: ["_time"], desc: true)
  |> last()
  |> findColumn(fn: (key) => key._measurement == "fx", column: "_value")
from(bucket: "asystem")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "fx")
  |> filter(fn: (r) => r["_field"] == "GBP/AUD")
  |> filter(fn: (r) => r["period"] == "daily")
  |> filter(fn: (r) => r["type"] == "snapshot")
  |> sort(columns: ["_time"], desc: false)
  |> last()
  |> map(fn: (r) => ({ r with "GBP/AUD": (r._value - first_snapshot[0]) / first_snapshot[0] * -100.0 }))
  |> keep(columns: ["GBP/AUD"])
// End')).addTarget(influxdb.target(query='// Start
first_snapshot = from(bucket: "asystem")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "fx")
  |> filter(fn: (r) => r["_field"] == "USD/AUD")
  |> filter(fn: (r) => r["period"] == "daily")
  |> filter(fn: (r) => r["type"] == "snapshot")
  |> sort(columns: ["_time"], desc: true)
  |> last()
  |> findColumn(fn: (key) => key._measurement == "fx", column: "_value")
from(bucket: "asystem")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "fx")
  |> filter(fn: (r) => r["_field"] == "USD/AUD")
  |> filter(fn: (r) => r["period"] == "daily")
  |> filter(fn: (r) => r["type"] == "snapshot")
  |> sort(columns: ["_time"], desc: false)
  |> last()
  |> map(fn: (r) => ({ r with "USD/AUD": (r._value - first_snapshot[0]) / first_snapshot[0] * -100.0 }))
  |> keep(columns: ["USD/AUD"])
// End')).addTarget(influxdb.target(query='// Start
first_snapshot = from(bucket: "asystem")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "fx")
  |> filter(fn: (r) => r["_field"] == "SGD/AUD")
  |> filter(fn: (r) => r["period"] == "daily")
  |> filter(fn: (r) => r["type"] == "snapshot")
  |> sort(columns: ["_time"], desc: true)
  |> last()
  |> findColumn(fn: (key) => key._measurement == "fx", column: "_value")
from(bucket: "asystem")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "fx")
  |> filter(fn: (r) => r["_field"] == "SGD/AUD")
  |> filter(fn: (r) => r["period"] == "daily")
  |> filter(fn: (r) => r["type"] == "snapshot")
  |> sort(columns: ["_time"], desc: false)
  |> last()
  |> map(fn: (r) => ({ r with "SGD/AUD": (r._value - first_snapshot[0]) / first_snapshot[0] * -100.0 }))
  |> keep(columns: ["SGD/AUD"])
// End')) { gridPos: { x: 15, y: 0, w: 9, h: 8 } },

      gauge.new(
        title='GBP/AUD Last Delta',
        datasource='InfluxDB2',
        reducerFunction='last',
        showThresholdLabels=false,
        showThresholdMarkers=true,
        unit='percent',
        min=-2,
        max=2,
        decimals=2,
        repeatDirection='h',
        pluginVersion='7',
      ).addThreshold(
        { color: 'red', value: -9999 }
      ).addThreshold(
        { color: 'yellow', value: -0.5 }
      ).addThreshold(
        { color: 'green', value: 0.5 }
      ).addTarget(influxdb.target(query='// Start
from(bucket: "asystem")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "fx")
  |> filter(fn: (r) => r["_field"] == "GBP/AUD")
  |> filter(fn: (r) => r["period"] == "daily")
  |> filter(fn: (r) => r["type"] == "delta")
  |> sort(columns: ["_time"], desc: false)
  |> last()
  |> keep(columns: ["_value"])
  |> map(fn: (r) => ({ r with _value: -1.0 * r._value }))
// End')) { gridPos: { x: 0, y: 3, w: 5, h: 5 } },

      gauge.new(
        title='USD/AUD Last Delta',
        datasource='InfluxDB2',
        reducerFunction='last',
        showThresholdLabels=false,
        showThresholdMarkers=true,
        unit='percent',
        min=-2,
        max=2,
        decimals=2,
        repeatDirection='h',
        pluginVersion='7',
      ).addThreshold(
        { color: 'red', value: -9999 }
      ).addThreshold(
        { color: 'yellow', value: -0.5 }
      ).addThreshold(
        { color: 'green', value: 0.5 }
      ).addTarget(influxdb.target(query='// Start
from(bucket: "asystem")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "fx")
  |> filter(fn: (r) => r["_field"] == "USD/AUD")
  |> filter(fn: (r) => r["period"] == "daily")
  |> filter(fn: (r) => r["type"] == "delta")
  |> sort(columns: ["_time"], desc: false)
  |> last()
  |> keep(columns: ["_value"])
  |> map(fn: (r) => ({ r with _value: -1.0 * r._value }))
// End')) { gridPos: { x: 5, y: 3, w: 5, h: 5 } },

      gauge.new(
        title='SGD/AUD Last Delta',
        datasource='InfluxDB2',
        reducerFunction='last',
        showThresholdLabels=false,
        showThresholdMarkers=true,
        unit='percent',
        min=-2,
        max=2,
        decimals=2,
        repeatDirection='h',
        pluginVersion='7',
      ).addThreshold(
        { color: 'red', value: -9999 }
      ).addThreshold(
        { color: 'yellow', value: -0.5 }
      ).addThreshold(
        { color: 'green', value: 0.5 }
      ).addTarget(influxdb.target(query='// Start
from(bucket: "asystem")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "fx")
  |> filter(fn: (r) => r["_field"] == "SGD/AUD")
  |> filter(fn: (r) => r["period"] == "daily")
  |> filter(fn: (r) => r["type"] == "delta")
  |> sort(columns: ["_time"], desc: false)
  |> last()
  |> keep(columns: ["_value"])
  |> map(fn: (r) => ({ r with _value: -1.0 * r._value }))
// End')) { gridPos: { x: 10, y: 3, w: 5, h: 5 } },

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
  |> filter(fn: (r) => r["type"] == "delta")
  |> filter(fn: (r) => r["_field"] == "GBP/AUD")
  |> keep(columns: ["_time", "_value", "type"])
  |> map(fn: (r) => ({ r with _value: -1.0 * r._value }))
// End')).addTarget(influxdb.target(query='// Start
from(bucket: "asystem")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "fx")
  |> filter(fn: (r) => r["period"] == "daily")
  |> filter(fn: (r) => r["type"] == "snapshot")
  |> filter(fn: (r) => r["_field"] == "GBP/AUD")
  |> keep(columns: ["_time", "_value", "type"])
  |> map(fn: (r) => ({ r with _value: 1.0 / r._value }))
// End')).addSeriesOverride(
        { "alias": "/.*snapshot.*/", "bars": false, "lines": true, "linewidth": 2, "zindex": 3, "yaxis": 2 }
      ) { gridPos: { x: 0, y: 8, w: 24, h: 12 } },

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
  |> filter(fn: (r) => r["type"] == "delta")
  |> filter(fn: (r) => r["_field"] == "USD/AUD")
  |> keep(columns: ["_time", "_value", "type"])
  |> map(fn: (r) => ({ r with _value: -1.0 * r._value }))
// End')).addTarget(influxdb.target(query='// Start
from(bucket: "asystem")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "fx")
  |> filter(fn: (r) => r["period"] == "daily")
  |> filter(fn: (r) => r["type"] == "snapshot")
  |> filter(fn: (r) => r["_field"] == "USD/AUD")
  |> keep(columns: ["_time", "_value", "type"])
  |> map(fn: (r) => ({ r with _value: 1.0 / r._value }))
// End')).addSeriesOverride(
        { "alias": "/.*snapshot.*/", "bars": false, "lines": true, "linewidth": 2, "zindex": 3, "yaxis": 2 }
      ) { gridPos: { x: 0, y: 20, w: 24, h: 12 } },

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
  |> filter(fn: (r) => r["type"] == "delta")
  |> filter(fn: (r) => r["_field"] == "SGD/AUD")
  |> keep(columns: ["_time", "_value", "type"])
  |> map(fn: (r) => ({ r with _value: -1.0 * r._value }))
// End')).addTarget(influxdb.target(query='// Start
from(bucket: "asystem")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "fx")
  |> filter(fn: (r) => r["period"] == "daily")
  |> filter(fn: (r) => r["type"] == "snapshot")
  |> filter(fn: (r) => r["_field"] == "SGD/AUD")
  |> keep(columns: ["_time", "_value", "type"])
  |> map(fn: (r) => ({ r with _value: 1.0 / r._value }))
// End')).addSeriesOverride(
        { "alias": "/.*snapshot.*/", "bars": false, "lines": true, "linewidth": 2, "zindex": 3, "yaxis": 2 }
      ) { gridPos: { x: 0, y: 32, w: 24, h: 12 } },

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
  |> map(fn: (r) => ({ r with _value: -1.0 * r._value }))
// End')) { gridPos: { x: 0, y: 44, w: 24, h: 12 } },

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
  |> map(fn: (r) => ({ r with _value: -1.0 * r._value }))
// End')) { gridPos: { x: 0, y: 56, w: 24, h: 12 } },

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
  |> map(fn: (r) => ({ r with _value: -1.0 * r._value }))
// End')) { gridPos: { x: 0, y: 68, w: 24, h: 12 } },

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
  |> map(fn: (r) => ({ r with _value: -1.0 * r._value }))
// End')) { gridPos: { x: 0, y: 80, w: 24, h: 12 } },

    ],
}
