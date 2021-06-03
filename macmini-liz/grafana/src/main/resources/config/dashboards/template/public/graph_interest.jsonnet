// GRAPH_DASHBOARD_DEFAULTS: time_from='now-5y', refresh=''
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
        title='Retail Rate Last Snapshot',
        datasource='InfluxDB2Private',
        unit='percent',
        decimals=2,
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
  |> filter(fn: (r) => r["_measurement"] == "interest")
  |> filter(fn: (r) => r["_field"] == "retail")
  |> filter(fn: (r) => r["period"] == "1-month")
  |> sort(columns: ["_time"], desc: false)
  |> last()
  |> keep(columns: ["_value"])
// End')) { gridPos: { x: 0, y: 0, w: 5, h: 3 } },

      stat.new(
        title='Inflation Rate Last Snapshot',
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
        title='Net Rate Last Snapshot',
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
        title='Rates Ranged Means',
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
import "regexp"
import "experimental"
normalizeTime = (t) => {
  normalized =
    if regexp.matchRegexpString(r: /[n|u|s|m|h|d|w|o|y]/, v: t) then experimental.addDuration(d: duration(v: t), to: now())
    else time(v: t)
  return normalized
}
first_snapshot = from(bucket: "data_public")
  |> range(start: experimental.subDuration(d:0d, from:normalizeTime(t: string(v: v.timeRangeStart))), stop: v.timeRangeStop)  |> filter(fn: (r) => r["_measurement"] == "currency")
  |> filter(fn: (r) => r["_field"] == "AUD/GBP")
  |> filter(fn: (r) => r["period"] == "1-day")
  |> filter(fn: (r) => r["type"] == "snapshot")
  |> sort(columns: ["_time"], desc: true)
  |> last()
  |> findColumn(fn: (key) => key._measurement == "fx", column: "_value")
from(bucket: "data_public")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "currency")
  |> filter(fn: (r) => r["_field"] == "AUD/GBP")
  |> filter(fn: (r) => r["period"] == "1-day")
  |> filter(fn: (r) => r["type"] == "snapshot")
  |> sort(columns: ["_time"], desc: false)
  |> last()
  |> map(fn: (r) => ({ r with "AUD/GBP": (r._value - first_snapshot[0]) / first_snapshot[0] * -100.0 }))
  |> keep(columns: ["AUD/GBP"])
// End')).addTarget(influxdb.target(query='// Start
import "regexp"
import "experimental"
normalizeTime = (t) => {
  normalized =
    if regexp.matchRegexpString(r: /[n|u|s|m|h|d|w|o|y]/, v: t) then experimental.addDuration(d: duration(v: t), to: now())
    else time(v: t)
  return normalized
}
first_snapshot = from(bucket: "data_public")
  |> range(start: experimental.subDuration(d:0d, from:normalizeTime(t: string(v: v.timeRangeStart))), stop: v.timeRangeStop)  |> filter(fn: (r) => r["_measurement"] == "currency")
  |> filter(fn: (r) => r["_field"] == "AUD/USD")
  |> filter(fn: (r) => r["period"] == "1-day")
  |> filter(fn: (r) => r["type"] == "snapshot")
  |> sort(columns: ["_time"], desc: true)
  |> last()
  |> findColumn(fn: (key) => key._measurement == "fx", column: "_value")
from(bucket: "data_public")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "currency")
  |> filter(fn: (r) => r["_field"] == "AUD/USD")
  |> filter(fn: (r) => r["period"] == "1-day")
  |> filter(fn: (r) => r["type"] == "snapshot")
  |> sort(columns: ["_time"], desc: false)
  |> last()
  |> map(fn: (r) => ({ r with "AUD/USD": (r._value - first_snapshot[0]) / first_snapshot[0] * -100.0 }))
  |> keep(columns: ["AUD/USD"])
// End')).addTarget(influxdb.target(query='// Start
import "regexp"
import "experimental"
normalizeTime = (t) => {
  normalized =
    if regexp.matchRegexpString(r: /[n|u|s|m|h|d|w|o|y]/, v: t) then experimental.addDuration(d: duration(v: t), to: now())
    else time(v: t)
  return normalized
}
first_snapshot = from(bucket: "data_public")
  |> range(start: experimental.subDuration(d:0d, from:normalizeTime(t: string(v: v.timeRangeStart))), stop: v.timeRangeStop)  |> filter(fn: (r) => r["_measurement"] == "currency")
  |> filter(fn: (r) => r["_field"] == "AUD/SGD")
  |> filter(fn: (r) => r["period"] == "1-day")
  |> filter(fn: (r) => r["type"] == "snapshot")
  |> sort(columns: ["_time"], desc: true)
  |> last()
  |> findColumn(fn: (key) => key._measurement == "fx", column: "_value")
from(bucket: "data_public")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "currency")
  |> filter(fn: (r) => r["_field"] == "AUD/SGD")
  |> filter(fn: (r) => r["period"] == "1-day")
  |> filter(fn: (r) => r["type"] == "snapshot")
  |> sort(columns: ["_time"], desc: false)
  |> last()
  |> map(fn: (r) => ({ r with "AUD/SGD": (r._value - first_snapshot[0]) / first_snapshot[0] * -100.0 }))
  |> keep(columns: ["AUD/SGD"])
// End')) { gridPos: { x: 15, y: 0, w: 9, h: 8 } },

      gauge.new(
        title='Retail Rate 5-Year Mean',
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
        title='Inflation Rate 5-Year Mean',
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
        title='Net Rate 5-Year Mean',
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
        title='Interest Rate Monthly Means',
        datasource='InfluxDB2Private',
        fill=0,
        format='',
        bars=true,
        lines=false,
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
from(bucket: "data_public")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "interest")
  |> filter(fn: (r) => r["_field"] == "net")
  |> filter(fn: (r) => r["period"] == "1-month")
  |> keep(columns: ["_time", "_value", "_field"])
// End')).addTarget(influxdb.target(query='// Start
from(bucket: "data_public")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "interest")
  |> filter(fn: (r) => r["_field"] == "retail")
  |> filter(fn: (r) => r["period"] == "1-month")
  |> keep(columns: ["_time", "_value", "_field"])
// End')).addTarget(influxdb.target(query='// Start
from(bucket: "data_public")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "interest")
  |> filter(fn: (r) => r["_field"] == "inflation")
  |> filter(fn: (r) => r["period"] == "1-month")
  |> keep(columns: ["_time", "_value", "_field"])
// End')).addSeriesOverride(
        { "alias": "/.*retail.*/", "bars": false, "lines": true, "linewidth": 2, "zindex": 3, "yaxis": 1 }
      ).addSeriesOverride(
        { "alias": "/.*inflation.*/", "bars": false, "lines": true, "linewidth": 2, "zindex": 3, "yaxis": 1 }
      ) { gridPos: { x: 0, y: 8, w: 24, h: 12 } },

    ],
}
