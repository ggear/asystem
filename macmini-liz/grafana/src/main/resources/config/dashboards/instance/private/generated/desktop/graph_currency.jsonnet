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
        datasource='InfluxDB2Private',
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
from(bucket: "data_public")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "currency")
  |> filter(fn: (r) => r["_field"] == "AUD/GBP")
  |> filter(fn: (r) => r["period"] == "1-day")
  |> filter(fn: (r) => r["type"] == "snapshot")
  |> sort(columns: ["_time"], desc: false)
  |> last()
  |> map(fn: (r) => ({ r with _value: 1.0 / r._value }))
  |> keep(columns: ["_value"])
// End')) { gridPos: { x: 0, y: 0, w: 5, h: 3 } },

      stat.new(
        title='USD/AUD Last Snapshot',
        datasource='InfluxDB2Private',
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
from(bucket: "data_public")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "currency")
  |> filter(fn: (r) => r["_field"] == "AUD/USD")
  |> filter(fn: (r) => r["period"] == "1-day")
  |> filter(fn: (r) => r["type"] == "snapshot")
  |> sort(columns: ["_time"], desc: false)
  |> last()
  |> map(fn: (r) => ({ r with _value: 1.0 / r._value }))
  |> keep(columns: ["_value"])
// End')) { gridPos: { x: 5, y: 0, w: 5, h: 3 } },

      stat.new(
        title='SGD/AUD Last Snapshot',
        datasource='InfluxDB2Private',
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
from(bucket: "data_public")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "currency")
  |> filter(fn: (r) => r["_field"] == "AUD/SGD")
  |> filter(fn: (r) => r["period"] == "1-day")
  |> filter(fn: (r) => r["type"] == "snapshot")
  |> sort(columns: ["_time"], desc: false)
  |> map(fn: (r) => ({ r with _value: 1.0 / r._value }))
  |> last()
  |> keep(columns: ["_value"])
// End')) { gridPos: { x: 10, y: 0, w: 5, h: 3 } },

      bar.new(
        title='CCY/AUD Range Deltas',
        datasource='InfluxDB2Private',
        unit='percent',
        min=-30,
        max=30,
        thresholds=[
          { 'color': 'red', 'value': -9999 },
          { 'color': 'yellow', 'value': -0.5 },
          { 'color': 'green', 'value': 0.5 },
        ],
      ).addTarget(influxdb.target(query='// Start
field = "AUD/GBP"
series = from(bucket: "data_public")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "currency")
  |> filter(fn: (r) => r["period"] == "1-day")
  |> filter(fn: (r) => r["type"] == "snapshot")
  |> filter(fn: (r) => r["_field"] == field)
  |> keep(columns: ["_time", "_value", "_field"])
  |> aggregateWindow(every: v.windowPeriod, fn: mean, createEmpty: false)
baseline = series
  |> findRecord(fn: (key) => true, idx: 0)
series
  |> map(fn: (r) => ({ r with _value: (baseline._value - r._value) / baseline._value * 100.0 }))
  |> last()
  |> keep(columns: ["_time", "_value", "_field"])
// End')).addTarget(influxdb.target(query='// Start
field = "AUD/USD"
series = from(bucket: "data_public")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "currency")
  |> filter(fn: (r) => r["period"] == "1-day")
  |> filter(fn: (r) => r["type"] == "snapshot")
  |> filter(fn: (r) => r["_field"] == field)
  |> keep(columns: ["_time", "_value", "_field"])
  |> aggregateWindow(every: v.windowPeriod, fn: mean, createEmpty: false)
baseline = series
  |> findRecord(fn: (key) => true, idx: 0)
series
  |> map(fn: (r) => ({ r with _value: (baseline._value - r._value) / baseline._value * 100.0 }))
  |> last()
  |> keep(columns: ["_time", "_value", "_field"])
// End')).addTarget(influxdb.target(query='// Start
field = "AUD/SGD"
series = from(bucket: "data_public")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "currency")
  |> filter(fn: (r) => r["period"] == "1-day")
  |> filter(fn: (r) => r["type"] == "snapshot")
  |> filter(fn: (r) => r["_field"] == field)
  |> keep(columns: ["_time", "_value", "_field"])
  |> aggregateWindow(every: v.windowPeriod, fn: mean, createEmpty: false)
baseline = series
  |> findRecord(fn: (key) => true, idx: 0)
series
  |> map(fn: (r) => ({ r with _value: (baseline._value - r._value) / baseline._value * 100.0 }))
  |> last()
  |> keep(columns: ["_time", "_value", "_field"])
// End')) { gridPos: { x: 15, y: 0, w: 9, h: 8 } },

      gauge.new(
        title='GBP/AUD Last Delta',
        datasource='InfluxDB2Private',
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
from(bucket: "data_public")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "currency")
  |> filter(fn: (r) => r["_field"] == "AUD/GBP")
  |> filter(fn: (r) => r["period"] == "1-day")
  |> filter(fn: (r) => r["type"] == "delta")
  |> sort(columns: ["_time"], desc: false)
  |> last()
  |> keep(columns: ["_value"])
  |> map(fn: (r) => ({ r with _value: -1.0 * r._value }))
// End')) { gridPos: { x: 0, y: 3, w: 5, h: 5 } },

      gauge.new(
        title='USD/AUD Last Delta',
        datasource='InfluxDB2Private',
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
from(bucket: "data_public")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "currency")
  |> filter(fn: (r) => r["_field"] == "AUD/USD")
  |> filter(fn: (r) => r["period"] == "1-day")
  |> filter(fn: (r) => r["type"] == "delta")
  |> sort(columns: ["_time"], desc: false)
  |> last()
  |> keep(columns: ["_value"])
  |> map(fn: (r) => ({ r with _value: -1.0 * r._value }))
// End')) { gridPos: { x: 5, y: 3, w: 5, h: 5 } },

      gauge.new(
        title='SGD/AUD Last Delta',
        datasource='InfluxDB2Private',
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
from(bucket: "data_public")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "currency")
  |> filter(fn: (r) => r["_field"] == "AUD/SGD")
  |> filter(fn: (r) => r["period"] == "1-day")
  |> filter(fn: (r) => r["type"] == "delta")
  |> sort(columns: ["_time"], desc: false)
  |> last()
  |> keep(columns: ["_value"])
  |> map(fn: (r) => ({ r with _value: -1.0 * r._value }))
// End')) { gridPos: { x: 10, y: 3, w: 5, h: 5 } },

      graph.new(
        title='CCY/AUD Deltas',
        datasource='InfluxDB2Private',
        fill=0,
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
        legend_sideWidth=425,
        maxDataPoints=10000
      ).addTarget(influxdb.target(query='// Start
field = "AUD/GBP"
series = from(bucket: "data_public")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "currency")
  |> filter(fn: (r) => r["period"] == "1-day")
  |> filter(fn: (r) => r["type"] == "snapshot")
  |> filter(fn: (r) => r["_field"] == field)
  |> keep(columns: ["_time", "_value", "_field"])
  |> aggregateWindow(every: v.windowPeriod, fn: mean, createEmpty: false)
baseline = series
  |> findRecord(fn: (key) => true, idx: 0)
series
  |> map(fn: (r) => ({ r with _value: (baseline._value - r._value) / baseline._value * 100.0 }))
// End')).addTarget(influxdb.target(query='// Start
field = "AUD/USD"
series = from(bucket: "data_public")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "currency")
  |> filter(fn: (r) => r["period"] == "1-day")
  |> filter(fn: (r) => r["type"] == "snapshot")
  |> filter(fn: (r) => r["_field"] == field)
  |> keep(columns: ["_time", "_value", "_field"])
  |> aggregateWindow(every: v.windowPeriod, fn: mean, createEmpty: false)
baseline = series
  |> findRecord(fn: (key) => true, idx: 0)
series
  |> map(fn: (r) => ({ r with _value: (baseline._value - r._value) / baseline._value * 100.0 }))
// End')).addTarget(influxdb.target(query='// Start
field = "AUD/SGD"
series = from(bucket: "data_public")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "currency")
  |> filter(fn: (r) => r["period"] == "1-day")
  |> filter(fn: (r) => r["type"] == "snapshot")
  |> filter(fn: (r) => r["_field"] == field)
  |> keep(columns: ["_time", "_value", "_field"])
  |> aggregateWindow(every: v.windowPeriod, fn: mean, createEmpty: false)
baseline = series
  |> findRecord(fn: (key) => true, idx: 0)
series
  |> map(fn: (r) => ({ r with _value: (baseline._value - r._value) / baseline._value * 100.0 }))
// End')) { gridPos: { x: 0, y: 8, w: 24, h: 12 } },

      graph.new(
        title='GBP/AUD Dailies',
        datasource='InfluxDB2Private',
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
        legend_sideWidth=425,
        maxDataPoints=10000
      ).addTarget(influxdb.target(query='// Start
from(bucket: "data_public")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "currency")
  |> filter(fn: (r) => r["period"] == "1-day")
  |> filter(fn: (r) => r["type"] == "delta")
  |> filter(fn: (r) => r["_field"] == "AUD/GBP")
  |> keep(columns: ["_time", "_value", "type"])
  |> map(fn: (r) => ({ r with _value: -1.0 * r._value }))
// End')).addTarget(influxdb.target(query='// Start
from(bucket: "data_public")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "currency")
  |> filter(fn: (r) => r["period"] == "1-day")
  |> filter(fn: (r) => r["type"] == "snapshot")
  |> filter(fn: (r) => r["_field"] == "AUD/GBP")
  |> keep(columns: ["_time", "_value", "type"])
  |> map(fn: (r) => ({ r with _value: 1.0 / r._value }))
// End')).addSeriesOverride(
        { "alias": "/.*delta.*/", "bars": true, "lines": false, "zindex": 1, "yaxis": 1, "color": "rgba(150, 217, 141, 0.31)" }
      ).addSeriesOverride(
        { "alias": "/.*snapshot.*/", "bars": false, "lines": true, "zindex": 3, "yaxis": 2 }
      ) { gridPos: { x: 0, y: 20, w: 24, h: 12 } },

      graph.new(
        title='USD/AUD Dailies',
        datasource='InfluxDB2Private',
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
        legend_sideWidth=425,
        maxDataPoints=10000
      ).addTarget(influxdb.target(query='// Start
from(bucket: "data_public")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "currency")
  |> filter(fn: (r) => r["period"] == "1-day")
  |> filter(fn: (r) => r["type"] == "delta")
  |> filter(fn: (r) => r["_field"] == "AUD/USD")
  |> keep(columns: ["_time", "_value", "type"])
  |> map(fn: (r) => ({ r with _value: -1.0 * r._value }))
// End')).addTarget(influxdb.target(query='// Start
from(bucket: "data_public")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "currency")
  |> filter(fn: (r) => r["period"] == "1-day")
  |> filter(fn: (r) => r["type"] == "snapshot")
  |> filter(fn: (r) => r["_field"] == "AUD/USD")
  |> keep(columns: ["_time", "_value", "type"])
  |> map(fn: (r) => ({ r with _value: 1.0 / r._value }))
// End')).addSeriesOverride(
        { "alias": "/.*delta.*/", "bars": true, "lines": false, "zindex": 1, "yaxis": 1, "color": "rgba(150, 217, 141, 0.31)" }
      ).addSeriesOverride(
        { "alias": "/.*snapshot.*/", "bars": false, "lines": true, "zindex": 3, "yaxis": 2 }
      ) { gridPos: { x: 0, y: 32, w: 24, h: 12 } },

      graph.new(
        title='SGD/AUD Dailies',
        datasource='InfluxDB2Private',
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
        legend_sideWidth=425,
        maxDataPoints=10000
      ).addTarget(influxdb.target(query='// Start
from(bucket: "data_public")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "currency")
  |> filter(fn: (r) => r["period"] == "1-day")
  |> filter(fn: (r) => r["type"] == "delta")
  |> filter(fn: (r) => r["_field"] == "AUD/SGD")
  |> keep(columns: ["_time", "_value", "type"])
  |> map(fn: (r) => ({ r with _value: -1.0 * r._value }))
// End')).addTarget(influxdb.target(query='// Start
from(bucket: "data_public")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "currency")
  |> filter(fn: (r) => r["period"] == "1-day")
  |> filter(fn: (r) => r["type"] == "snapshot")
  |> filter(fn: (r) => r["_field"] == "AUD/SGD")
  |> keep(columns: ["_time", "_value", "type"])
  |> map(fn: (r) => ({ r with _value: 1.0 / r._value }))
// End')).addSeriesOverride(
        { "alias": "/.*delta.*/", "bars": true, "lines": false, "zindex": 1, "yaxis": 1, "color": "rgba(150, 217, 141, 0.31)" }
      ).addSeriesOverride(
        { "alias": "/.*snapshot.*/", "bars": false, "lines": true, "zindex": 3, "yaxis": 2 }
      ) { gridPos: { x: 0, y: 44, w: 24, h: 12 } },

    ],
}
