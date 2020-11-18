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
        title='Servers Min Uptime',
        datasource='InfluxDB2',
        unit='s',
        decimals=1,
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
        { color: 'yellow', value: 43200 }
      ).addThreshold(
        { color: 'green', value: 86400 }
      ).addTarget(influxdb.target(query='// Start
from(bucket: "hosts")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "system")
  |> filter(fn: (r) => r["_field"] == "uptime")
  |> group()
  |> min()
  |> keep(columns: ["_value"])
  // End')) { gridPos: { x: 0, y: 0, w: 5, h: 3 } },

      stat.new(
        title='Servers Median Uptime',
        datasource='InfluxDB2',
        unit='s',
        decimals=1,
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
        { color: 'yellow', value: 43200 }
      ).addThreshold(
        { color: 'green', value: 86400 }
      ).addTarget(influxdb.target(query='// Start
from(bucket: "hosts")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "system")
  |> filter(fn: (r) => r["_field"] == "uptime")
  |> group()
  |> map(fn: (r) => ({ r with _value: float(v: r._value) }))
  |> median(column: "_value")
  |> keep(columns: ["_value"])
  // End')) { gridPos: { x: 5, y: 0, w: 5, h: 3 } },

      stat.new(
        title='Servers Max Uptime',
        datasource='InfluxDB2',
        unit='s',
        decimals=1,
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
        { color: 'yellow', value: 43200 }
      ).addThreshold(
        { color: 'green', value: 86400 }
      ).addTarget(influxdb.target(query='// Start
from(bucket: "hosts")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "system")
  |> filter(fn: (r) => r["_field"] == "uptime")
  |> group()
  |> max()
  |> keep(columns: ["_value"])
  // End')) { gridPos: { x: 10, y: 0, w: 5, h: 3 } },

      bar.new(
        title='Servers with Peak Usage <50%',
        datasource='InfluxDB2',
        unit='percent',
        thresholds=[
          { 'color': 'red', 'value': null },
          { 'color': 'yellow', 'value': 50 },
          { 'color': 'green', 'value': 90 }
        ],
      ).addTarget(influxdb.target(query='// Start
import "math"
from(bucket: "hosts")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "cpu")
  |> filter(fn: (r) => r["_field"] == "usage_idle")
  |> filter(fn: (r) => r["cpu"] == "cpu-total")
  |> keep(columns: ["_time", "_value", "host"])
  |> map(fn: (r) => ({ r with _value: 100.0 - r._value }))
  |> max()
  |> group()
  |> map(fn: (r) => ({ r with index: 1 }))
  |> cumulativeSum(columns: ["index"])
  |> map(fn: (r) => ({ r with _value: if r._value > 50.0 then 1 else 0 }))
  |> cumulativeSum(columns: ["_value"])
  |> last()
  |> map(fn: (r) => ({ r with "CPU": math.mMin(x: 100.0, y: 100.0 - float(v: r._value) / float(v: r.index) * 100.0) }))
  |> keep(columns: ["CPU"])
// End')).addTarget(influxdb.target(query='// Start
import "math"
from(bucket: "hosts")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "mem")
  |> filter(fn: (r) => r["_field"] == "used_percent")
  |> keep(columns: ["_time", "_value", "host"])
  |> max()
  |> group()
  |> map(fn: (r) => ({ r with index: 1 }))
  |> cumulativeSum(columns: ["index"])
  |> map(fn: (r) => ({ r with _value: if r._value > 50.0 then 1 else 0 }))
  |> cumulativeSum(columns: ["_value"])
  |> last()
  |> map(fn: (r) => ({ r with "RAM": math.mMin(x: 100.0, y: 100.0 - float(v: r._value) / float(v: r.index) * 100.0) }))
  |> keep(columns: ["RAM"])
// End')).addTarget(influxdb.target(query='// Start
import "math"
from(bucket: "hosts")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "diskio")
  |> filter(fn: (r) => r["_field"] == "read_bytes")
  |> keep(columns: ["_time", "_value", "host"])
  |> aggregateWindow(every: v.windowPeriod, fn: mean, createEmpty: true)
  |> fill(column: "_value", usePrevious: true)
  |> derivative(unit: 1s, nonNegative: true)
  |> max()
  |> group()
  |> map(fn: (r) => ({ r with index: 1 }))
  |> cumulativeSum(columns: ["index"])
  |> map(fn: (r) => ({ r with _value: if r._value > 100000000 then 1 else 0 }))
  |> cumulativeSum(columns: ["_value"])
  |> last()
  |> map(fn: (r) => ({ r with "IOPS": math.mMin(x: 100.0, y: 100.0 - float(v: r._value) / float(v: r.index) * 100.0) }))
  |> keep(columns: ["IOPS"])
// End')).addTarget(influxdb.target(query='// Start
import "math"
from(bucket: "hosts")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "net")
  |> filter(fn: (r) => r["_field"] == "bytes_recv")
  |> keep(columns: ["_time", "_value", "host"])
  |> aggregateWindow(every: v.windowPeriod, fn: mean, createEmpty: true)
  |> fill(column: "_value", usePrevious: true)
  |> derivative(unit: 1s, nonNegative: true)
  |> max()
  |> group()
  |> map(fn: (r) => ({ r with index: 1 }))
  |> cumulativeSum(columns: ["index"])
  |> map(fn: (r) => ({ r with _value: if r._value > 62500000 then 1 else 0 }))
  |> cumulativeSum(columns: ["_value"])
  |> last()
  |> map(fn: (r) => ({ r with "Network": math.mMin(x: 100.0, y: 100.0 - float(v: r._value) / float(v: r.index) * 100.0) }))
  |> keep(columns: ["Network"])
// End')) { gridPos: { x: 15, y: 0, w: 9, h: 8 } },

      gauge.new(
        title='Server Mean CPU Availability',
        datasource='InfluxDB2',
        reducerFunction='last',
        showThresholdLabels=false,
        showThresholdMarkers=true,
        unit='percent',
        min=0,
        max=100,
        decimals=0,
        thresholdsMode='percentage',
        repeatDirection='h',
        pluginVersion='7',
      ).addThreshold(
        { color: 'red', value: 0 }
      ).addThreshold(
        { color: 'yellow', value: 35 }
      ).addThreshold(
        { color: 'green', value: 65 }
      ).addTarget(influxdb.target(query='// Start
from(bucket: "hosts")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "cpu")
  |> filter(fn: (r) => r["_field"] == "usage_idle")
  |> filter(fn: (r) => r["cpu"] == "cpu-total")
  |> keep(columns: ["_time", "_value"])
  |> aggregateWindow(every: v.windowPeriod, fn: mean, createEmpty: false)
  |> mean()
  |> map(fn: (r) => ({ r with _value: r._value }))
  |> keep(columns: ["_value"])
// End')) { gridPos: { x: 0, y: 3, w: 5, h: 5 } },

      gauge.new(
        title='Server Mean Memory Availability',
        datasource='InfluxDB2',
        reducerFunction='last',
        showThresholdLabels=false,
        showThresholdMarkers=true,
        unit='percent',
        min=0,
        max=100,
        decimals=0,
        thresholdsMode='percentage',
        repeatDirection='h',
        pluginVersion='7',
      ).addThreshold(
        { color: 'red', value: 0 }
      ).addThreshold(
        { color: 'yellow', value: 35 }
      ).addThreshold(
        { color: 'green', value: 65 }
      ).addTarget(influxdb.target(query='// Start
from(bucket: "hosts")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "mem")
  |> filter(fn: (r) => r["_field"] == "used_percent")
  |> keep(columns: ["_time", "_value"])
  |> aggregateWindow(every: v.windowPeriod, fn: mean, createEmpty: false)
  |> mean()
  |> map(fn: (r) => ({ r with _value: 100.0 - r._value }))
  |> keep(columns: ["_value"])
// End')) { gridPos: { x: 5, y: 3, w: 5, h: 5 } },

      gauge.new(
        title='Server Mean 30< Temperature >100ºC',
        datasource='InfluxDB2',
        reducerFunction='last',
        showThresholdLabels=false,
        showThresholdMarkers=true,
        unit='ºC',
        min=0,
        max=100,
        decimals=0,
        thresholdsMode='percentage',
        repeatDirection='h',
        pluginVersion='7',
      ).addThreshold(
        { color: 'red', value: 0 }
      ).addThreshold(
        { color: 'yellow', value: 35 }
      ).addThreshold(
        { color: 'green', value: 65 }
      ).addTarget(influxdb.target(query='// Start
from(bucket: "hosts")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "sensors" and r["_field"] == "temp_input" and r["feature"] == "package_id_0")
  |> keep(columns: ["_time", "_value"])
  |> aggregateWindow(every: v.windowPeriod, fn: mean, createEmpty: false)
  |> mean()

  |> map(fn: (r) => ({ r with _value: 130.0 - r._value }))

  |> keep(columns: ["_value"])
// End')) { gridPos: { x: 10, y: 3, w: 5, h: 5 } },

      graph.new(
        title='Server CPU Usage',
        datasource='InfluxDB2',
        fill=1,
        format='percent',
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
from(bucket: "hosts")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "cpu")
  |> filter(fn: (r) => r["_field"] == "usage_idle")
  |> filter(fn: (r) => r["cpu"] == "cpu-total")
  |> keep(columns: ["_time", "_value", "host"])
  |> aggregateWindow(every: v.windowPeriod, fn: mean, createEmpty: false)
  |> fill(column: "_value", usePrevious: true)
  |> map(fn: (r) => ({ r with _value: 100.0 - r._value }))
  |> keep(columns: ["_time", "_value", "host"])
// End')) { gridPos: { x: 0, y: 8, w: 24, h: 12 } },

      graph.new(
        title='Server RAM Usage',
        datasource='InfluxDB2',
        fill=1,
        format='percent',
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
from(bucket: "hosts")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "mem")
  |> filter(fn: (r) => r["_field"] == "used_percent")
  |> keep(columns: ["_time", "_value", "host"])
  |> aggregateWindow(every: v.windowPeriod, fn: mean, createEmpty: false)
  |> fill(column: "_value", usePrevious: true)
  |> keep(columns: ["_time", "_value", "host"])
// End')) { gridPos: { x: 0, y: 20, w: 24, h: 12 } },

      graph.new(
        title='Server IOPS Usage',
        datasource='InfluxDB2',
        fill=1,
        format='Bps',
        bars=false,
        lines=true,
        staircase=true,
        points=false,
        pointradius=1,
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
from(bucket: "hosts")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "diskio")
  |> filter(fn: (r) => r["_field"] == "read_bytes")
  |> keep(columns: ["_time", "_value", "host"])
  |> aggregateWindow(every: v.windowPeriod, fn: mean, createEmpty: false)
  |> fill(column: "_value", usePrevious: true)
  |> derivative(unit: 1s, nonNegative: true)
  |> map(fn: (r) => ({ r with host: r.host + " (Read)" }))
// End')).addTarget(influxdb.target(query='// Start
from(bucket: "hosts")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "diskio")
  |> filter(fn: (r) => r["_field"] == "write_bytes")
  |> keep(columns: ["_time", "_value", "host"])
  |> aggregateWindow(every: v.windowPeriod, fn: mean, createEmpty: false)
  |> fill(column: "_value", usePrevious: true)
  |> derivative(unit: 1s, nonNegative: true)
  |> map(fn: (r) => ({ r with host: r.host + " (Write)" }))
// End')).addSeriesOverride(
        { "alias": "/.*Write.*/", "transform": "negative-Y" }
      ) { gridPos: { x: 0, y: 32, w: 24, h: 12 } },

      graph.new(
        title='Server Network Usage',
        datasource='InfluxDB2',
        fill=1,
        format='Bps',
        bars=false,
        lines=true,
        staircase=true,
        points=false,
        pointradius=1,
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
from(bucket: "hosts")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "net")
  |> filter(fn: (r) => r["_field"] == "bytes_recv")
  |> keep(columns: ["_time", "_value", "host"])
  |> aggregateWindow(every: v.windowPeriod, fn: mean, createEmpty: false)
  |> fill(column: "_value", usePrevious: true)
  |> derivative(unit: 1s, nonNegative: true)
  |> map(fn: (r) => ({ r with host: r.host + " (Receive)" }))
// End')).addTarget(influxdb.target(query='// Start
from(bucket: "hosts")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "net")
  |> filter(fn: (r) => r["_field"] == "bytes_sent")
  |> keep(columns: ["_time", "_value", "host"])
  |> aggregateWindow(every: v.windowPeriod, fn: mean, createEmpty: false)
  |> fill(column: "_value", usePrevious: true)
  |> derivative(unit: 1s, nonNegative: true)
  |> map(fn: (r) => ({ r with host: r.host + " (Transmit)" }))
// End')).addSeriesOverride(
        { "alias": "/.*Transmit.*/", "transform": "negative-Y" }
      ) { gridPos: { x: 0, y: 46, w: 24, h: 12 } },

      graph.new(
        title='Server Temperature',
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
        legend_sideWidth=425
      ).addTarget(influxdb.target(query='// Start
from(bucket: "hosts")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "sensors" and r["_field"] == "temp_input" and r["feature"] == "package_id_0")
  |> keep(columns: ["table", "_start", "_stop", "_time", "_value", "host"])
  |> aggregateWindow(every: v.windowPeriod, fn: max, createEmpty: false)
// End')).addTarget(influxdb.target(query='// Start
from(bucket: "asystem")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["entity_id"] == "utility_temperature")
  |> set(key: "host", value: "ambient-rack")
  |> keep(columns: ["table", "_start", "_stop", "_time", "_value", "host"])
  |> aggregateWindow(every: v.windowPeriod, fn: max, createEmpty: false)
  |> fill(column: "_value", usePrevious: true)
// End'))
      { gridPos: { x: 0, y: 58, w: 24, h: 12 } },

    ],
}
