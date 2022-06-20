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
                style='medial',
                formFactor='Tablet',
                bucket='host_private',
                measurement='system',
                maxMilliSecSincePoll=10000,
                maxMilliSecSinceUpdate=10000,
                filter_data='',
                filter_metadata='',
                filter_metadata_delta='',
            ) +

            [

                  stat.new(
                        title='Servers Min Uptime',
                        datasource='InfluxDB_V2',
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
                  ).addTarget(influxdb.target(query='
from(bucket: "host_private")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "system")
  |> filter(fn: (r) => r["_field"] == "uptime")
  |> last()
  |> group()
  |> min()
  |> keep(columns: ["_value"])
                  '))
                      { gridPos: { x: 0, y: 2, w: 5, h: 3 } }
                  ,

                  stat.new(
                        title='Servers OS Volumes >80%',
                        datasource='InfluxDB_V2',
                        unit='',
                        decimals=0,
                        reducerFunction='last',
                        colorMode='value',
                        graphMode='none',
                        justifyMode='auto',
                        thresholdsMode='absolute',
                        repeatDirection='h',
                        pluginVersion='7',
                  ).addThreshold(
                        { color: 'green', value: 0 }
                  ).addThreshold(
                        { color: 'yellow', value: 1 }
                  ).addThreshold(
                        { color: 'red', value: 2 }
                  ).addTarget(influxdb.target(query='
from(bucket: "host_private")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "disk")
  |> filter(fn: (r) => r["_field"] == "used_percent")
  |> filter(fn: (r) => r["path"] == "/" or r["path"] == "/var" or r["path"] == "/tmp")
  |> keep(columns: ["_value", "host", "path"])
  |> max()
  |> map(fn: (r) => ({ r with _value: if r._value > 80.0 then 1 else 0 }))
  |> keep(columns: ["_value"])
  |> sum()
                  '))
                      { gridPos: { x: 5, y: 2, w: 5, h: 3 } }
                  ,

                  stat.new(
                        title='Servers Data Volumes >80%',
                        datasource='InfluxDB_V2',
                        unit='',
                        decimals=0,
                        reducerFunction='last',
                        colorMode='value',
                        graphMode='none',
                        justifyMode='auto',
                        thresholdsMode='absolute',
                        repeatDirection='h',
                        pluginVersion='7',
                  ).addThreshold(
                        { color: 'green', value: 0 }
                  ).addThreshold(
                        { color: 'yellow', value: 1 }
                  ).addThreshold(
                        { color: 'red', value: 2 }
                  ).addTarget(influxdb.target(query='
from(bucket: "host_private")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "disk")
  |> filter(fn: (r) => r["_field"] == "used_percent")
  |> filter(fn: (r) => r["path"] == "/home")
  |> keep(columns: ["_value", "host"])
  |> max()
  |> map(fn: (r) => ({ r with _value: if r._value > 80.0 then 1 else 0 }))
  |> keep(columns: ["_value"])
  |> sum()
                  '))
                      { gridPos: { x: 10, y: 2, w: 5, h: 3 } }
                  ,

                  bar.new(
                        title='Servers with Peak Usage <50%',
                        datasource='InfluxDB_V2',
                        unit='percent',
                        thresholds=[
                              { 'color': 'red', 'value': null },
                              { 'color': 'yellow', 'value': 50 },
                              { 'color': 'green', 'value': 90 }
                        ],
                  ).addTarget(influxdb.target(query='
import "math"
from(bucket: "host_private")
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
                  ')).addTarget(influxdb.target(query='
import "math"
from(bucket: "host_private")
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
                  ')).addTarget(influxdb.target(query='
import "math"
from(bucket: "host_private")
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
                  ')).addTarget(influxdb.target(query='
import "math"
from(bucket: "host_private")
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
                  '))
                      { gridPos: { x: 15, y: 2, w: 9, h: 8 } }
                  ,

                  gauge.new(
                        title='Server Mean CPU Availability',
                        datasource='InfluxDB_V2',
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
                  ).addTarget(influxdb.target(query='
from(bucket: "host_private")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "cpu")
  |> filter(fn: (r) => r["_field"] == "usage_idle")
  |> filter(fn: (r) => r["cpu"] == "cpu-total")
  |> aggregateWindow(every: v.windowPeriod, fn: mean, createEmpty: false)
  |> mean()
  |> map(fn: (r) => ({ r with _value: r._value }))
  |> keep(columns: ["_value"])
                  '))
                      { gridPos: { x: 0, y: 5, w: 5, h: 5 } }
                  ,

                  gauge.new(
                        title='Server Mean Memory Availability',
                        datasource='InfluxDB_V2',
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
                  ).addTarget(influxdb.target(query='
from(bucket: "host_private")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "mem")
  |> filter(fn: (r) => r["_field"] == "used_percent")
  |> aggregateWindow(every: v.windowPeriod, fn: mean, createEmpty: false)
  |> mean()
  |> map(fn: (r) => ({ r with _value: 100.0 - r._value }))
  |> keep(columns: ["_value"])
                  '))
                      { gridPos: { x: 5, y: 5, w: 5, h: 5 } }
                  ,

                  gauge.new(
                        title='Server Mean 30< Temperature >100ºC',
                        datasource='InfluxDB_V2',
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
                  ).addTarget(influxdb.target(query='
from(bucket: "host_private")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "sensors" and r["_field"] == "temp_input" and r["feature"] == "package_id_0")
  |> aggregateWindow(every: v.windowPeriod, fn: mean, createEmpty: false)
  |> mean()
  |> map(fn: (r) => ({ r with _value: 130.0 - r._value }))
  |> keep(columns: ["_value"])
                  '))
                      { gridPos: { x: 10, y: 5, w: 5, h: 5 } }
                  ,

                  graph.new(
                        title='Server CPU Usage',
                        datasource='InfluxDB_V2',
                        fill=1,
                        format='percent',
                        bars=false,
                        lines=true,
                        staircase=true,
                  ).addTarget(influxdb.target(query='
from(bucket: "host_private")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "cpu")
  |> filter(fn: (r) => r["_field"] == "usage_idle")
  |> filter(fn: (r) => r["cpu"] == "cpu-total")
  |> aggregateWindow(every: v.windowPeriod, fn: mean, createEmpty: false)
  |> fill(column: "_value", usePrevious: true)
  |> map(fn: (r) => ({ r with _value: 100.0 - r._value }))
  |> keep(columns: ["_time", "_value", "host"])
  |> rename(columns: {_value: ""})
                  '))
                      { gridPos: { x: 0, y: 10, w: 24, h: 12 } }
                  ,

                  graph.new(
                        title='Server RAM Usage',
                        datasource='InfluxDB_V2',
                        fill=1,
                        format='percent',
                        bars=false,
                        lines=true,
                        staircase=true,
                  ).addTarget(influxdb.target(query='
from(bucket: "host_private")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "mem")
  |> filter(fn: (r) => r["_field"] == "used_percent")
  |> aggregateWindow(every: v.windowPeriod, fn: mean, createEmpty: false)
  |> fill(column: "_value", usePrevious: true)
  |> keep(columns: ["_time", "_value", "host"])
  |> rename(columns: {_value: ""})
                  '))
                      { gridPos: { x: 0, y: 22, w: 24, h: 12 } }
                  ,

                  graph.new(
                        title='Server Swap Usage',
                        datasource='InfluxDB_V2',
                        fill=1,
                        format='percent',
                        bars=false,
                        lines=true,
                        staircase=true,
                  ).addTarget(influxdb.target(query='
from(bucket: "host_private")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "swap")
  |> filter(fn: (r) => r["_field"] == "used_percent")
  |> aggregateWindow(every: v.windowPeriod, fn: mean, createEmpty: false)
  |> fill(column: "_value", usePrevious: true)
  |> keep(columns: ["_time", "_value", "host"])
  |> rename(columns: {_value: ""})
                  '))
                      { gridPos: { x: 0, y: 34, w: 24, h: 12 } }
                  ,

                  graph.new(
                        title='Server Volume Usage',
                        datasource='InfluxDB_V2',
                        fill=1,
                        format='percent',
                        bars=false,
                        lines=true,
                        staircase=true,
                  ).addTarget(influxdb.target(query='
import "strings"
from(bucket: "host_private")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "disk")
  |> filter(fn: (r) => r["_field"] == "used_percent")
  |> aggregateWindow(every: v.windowPeriod, fn: mean, createEmpty: false)
  |> keep(columns: ["_time", "_value", "host", "path"])
  |> map(fn: (r) => ({ r with path: r.host + " (" + r.path + ")" }))
  |> keep(columns: ["_time", "_value", "path"])
  |> sort(columns: ["_time"])
  |> rename(columns: {_value: ""})
                  '))
                      { gridPos: { x: 0, y: 46, w: 24, h: 12 } }
                  ,

                  graph.new(
                        title='Server IOPS Usage',
                        datasource='InfluxDB_V2',
                        fill=1,
                        format='Bps',
                        bars=false,
                        lines=true,
                        staircase=true,
                        points=false,
                        pointradius=1,
                  ).addTarget(influxdb.target(query='
from(bucket: "host_private")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "diskio")
  |> filter(fn: (r) => r["_field"] == "read_bytes")
  |> aggregateWindow(every: v.windowPeriod, fn: mean, createEmpty: false)
  |> fill(column: "_value", usePrevious: true)
  |> derivative(unit: 1s, nonNegative: true)
  |> keep(columns: ["_time", "_value", "host"])
  |> map(fn: (r) => ({ r with host: r.host + " + Read" }))
  |> rename(columns: {_value: ""})
                  ')).addTarget(influxdb.target(query='
from(bucket: "host_private")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "diskio")
  |> filter(fn: (r) => r["_field"] == "write_bytes")
  |> aggregateWindow(every: v.windowPeriod, fn: mean, createEmpty: false)
  |> fill(column: "_value", usePrevious: true)
  |> derivative(unit: 1s, nonNegative: true)
  |> keep(columns: ["_time", "_value", "host"])
  |> map(fn: (r) => ({ r with host: r.host + " - Write" }))
  |> rename(columns: {_value: ""})
                  ')).addSeriesOverride(
                        { "alias": "/.*Write.*/", "transform": "negative-Y" }
                  )
                      { gridPos: { x: 0, y: 58, w: 24, h: 12 } }
                  ,

                  graph.new(
                        title='Server Network Usage',
                        datasource='InfluxDB_V2',
                        fill=1,
                        format='Bps',
                        bars=false,
                        lines=true,
                        staircase=true,
                        points=false,
                        pointradius=1,
                  ).addTarget(influxdb.target(query='
from(bucket: "host_private")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "net")
  |> filter(fn: (r) => r["_field"] == "bytes_recv")
  |> aggregateWindow(every: v.windowPeriod, fn: mean, createEmpty: false)
  |> fill(column: "_value", usePrevious: true)
  |> derivative(unit: 1s, nonNegative: true)
  |> keep(columns: ["_time", "_value", "host"])
  |> map(fn: (r) => ({ r with host: r.host + " + Receive" }))
  |> rename(columns: {_value: ""})
                  ')).addTarget(influxdb.target(query='
from(bucket: "host_private")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "net")
  |> filter(fn: (r) => r["_field"] == "bytes_sent")
  |> aggregateWindow(every: v.windowPeriod, fn: mean, createEmpty: false)
  |> fill(column: "_value", usePrevious: true)
  |> derivative(unit: 1s, nonNegative: true)
  |> keep(columns: ["_time", "_value", "host"])
  |> map(fn: (r) => ({ r with host: r.host + " - Transmit" }))
  |> rename(columns: {_value: ""})
                  ')).addSeriesOverride(
                        { "alias": "/.*Transmit.*/", "transform": "negative-Y" }
                  )
                      { gridPos: { x: 0, y: 70, w: 24, h: 12 } }
                  ,

                  graph.new(
                        title='Server Temperature',
                        datasource='InfluxDB_V2',
                        fill=0,
                        format='ºC',
                        bars=false,
                        lines=true,
                        staircase=false,
                  ).addTarget(influxdb.target(query='
import "strings"
bin=10m
timeRangeStart=v.timeRangeStart
// timeRangeStart=-5m
// timeRangeStart=now()
// timeRangeStart="2021-12-04T02:55:42.581000000Z"
union(tables: [
  from(bucket: "host_private")
    |> range(start: time(v: if strings.hasPrefix(v: string(v: timeRangeStart), prefix: "-" ) then string(v: time(v: int(v: now()) + int(v: timeRangeStart) - int(v: bin))) else string(v: time(v: int(v: time(v: timeRangeStart)) - int(v: bin)))), stop: v.timeRangeStop)
    |> filter(fn: (r) => r["_measurement"] == "sensors" and r["_field"] == "temp_input" and r["feature"] == "package_id_0")
    |> keep(columns: ["_time", "_value", "host"])
    |> aggregateWindow(every: bin, fn: mean, createEmpty: false)
    |> keep(columns: ["_time", "_value", "host"]),
  from(bucket: "home_private")
    |> range(start: time(v: if strings.hasPrefix(v: string(v: timeRangeStart), prefix: "-" ) then string(v: time(v: int(v: now()) + int(v: timeRangeStart) - int(v: bin))) else string(v: time(v: int(v: time(v: timeRangeStart)) - int(v: bin)))), stop: v.timeRangeStop)
    |> filter(fn: (r) => r["entity_id"] == "rack_temperature")
    |> keep(columns: ["_time", "_value"])
    |> aggregateWindow(every: bin, fn: mean, createEmpty: false)
    |> set(key: "host", value: "rack-ambient")
    |> keep(columns: ["_time", "_value", "host"])
])
  |> group(columns: ["host"], mode:"by")
                  '))
                      { gridPos: { x: 0, y: 82, w: 24, h: 12 } }
                  ,

            ],
}
