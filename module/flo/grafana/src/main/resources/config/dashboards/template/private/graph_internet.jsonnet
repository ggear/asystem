//ASDASHBOARD_DEFAULTS time_from='now-6h', refresh='', timepicker=timepicker.new(refresh_intervals=['20s'], time_options=['5m', '15m', '1h', '6h', '12h', '24h', '2d', '7d', '30d', '60d', '90d'])
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
//ASM           style='minimal',
//AST           style='medial',
//ASD           style='maximal',
//ASM           formFactor='Mobile',
//AST           formFactor='Tablet',
//ASD           formFactor='Desktop',
                bucket='host_private',
                measurement='internet',
                maxMilliSecSincePoll=200000,
                maxMilliSecSinceUpdate=200000,
                filter_data='',
                filter_metadata='',
                filter_metadata_delta='',
            ) +

            [

                  stat.new(
                        title='Internet Uptime',
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
  |> filter(fn: (r) => r["_measurement"] == "internet")
  |> filter(fn: (r) => r["_field"] == "uptime_s")
  |> filter(fn: (r) => r["metric"] == "network")
  |> keep(columns: ["_time", "_value"])
  |> sort(columns: ["_time"])
  |> last()
                  '))
//ASM                 { gridPos: { x: 0, y: 2, w: 24, h: 3 } }
//AST                 { gridPos: { x: 0, y: 2, w: 5, h: 3 } }
//ASD                 { gridPos: { x: 0, y: 2, w: 5, h: 3 } }
                  ,

                  stat.new(
                        title='Domain Uptime',
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
                        { color: 'yellow', value: 600 }
                  ).addThreshold(
                        { color: 'green', value: 12000 }
                  ).addTarget(influxdb.target(query='
from(bucket: "host_private")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "internet")
  |> filter(fn: (r) => r["_field"] == "uptime_s")
  |> filter(fn: (r) => r["metric"] == "certificate")
  |> keep(columns: ["_time", "_value"])
  |> sort(columns: ["_time"])
  |> last()
                  '))
//ASM                 { gridPos: { x: 0, y: 10, w: 24, h: 3 } }
//AST                 { gridPos: { x: 5, y: 2, w: 5, h: 3 } }
//ASD                 { gridPos: { x: 5, y: 2, w: 5, h: 3 } }
                  ,

                  stat.new(
                        title='Certificate Expiry',
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
                        { color: 'yellow', value: 432000 }
                  ).addThreshold(
                        { color: 'green', value: 864000 }
                  ).addTarget(influxdb.target(query='
from(bucket: "host_private")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "internet")
  |> filter(fn: (r) => r["_field"] == "expiry_s")
  |> filter(fn: (r) => r["metric"] == "certificate")
  |> keep(columns: ["_time", "_value"])
  |> sort(columns: ["_time"])
  |> last()
                  '))
//ASM                 { gridPos: { x: 0, y: 18, w: 24, h: 3 } }
//AST                 { gridPos: { x: 10, y: 2, w: 5, h: 3 } }
//ASD                 { gridPos: { x: 10, y: 2, w: 5, h: 3 } }
                  ,

                  bar.new(
                        title='Service Availability',
                        datasource='InfluxDB_V2',
                        unit='percent',
                        thresholds=[
                              { 'color': 'red', 'value': null },
                              { 'color': 'yellow', 'value': 80 },
                              { 'color': 'green', 'value': 90 }
                        ],
                  ).addTarget(influxdb.target(query='
import "math"
from(bucket: "host_private")
 |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
 |> filter(fn: (r) => r["_measurement"] == "internet")
 |> filter(fn: (r) => r["_field"] == "uptime_delta_s")
 |> filter(fn: (r) => r["metric"] == "network" or r["metric"] == "lookup" or r["metric"] == "certificate")
 |> keep(columns: ["_start", "_stop", "_value", "metric"])
 |> sum()
 |> map(fn: (r) => ({ r with _value: math.mMin(x: 100.0, y: math.floor(x: r._value / (1.0 * float(v: uint(v: r._stop) - uint(v: r._start))) * 100000000000.0)) }))
 |> map(fn: (r) => ({ r with metric: if r.metric == "certificate" then "Certificate" else (if r.metric == "lookup" then "Domain" else (if r.metric == "network" then "Internet" else r.metric)) }))
 |> keep(columns: ["_value", "metric"])
 |> rename(columns: {_value: ""})
                  '))
//ASM                 { gridPos: { x: 0, y: 26, w: 24, h: 8 } }
//AST                 { gridPos: { x: 15, y: 2, w: 9, h: 8 } }
//ASD                 { gridPos: { x: 15, y: 2, w: 9, h: 8 } }
                  ,

                  gauge.new(
                        title='Internet Max Upload',
                        datasource='InfluxDB_V2',
                        reducerFunction='last',
                        showThresholdLabels=false,
                        showThresholdMarkers=true,
                        unit="MBs",
                        min=0,
                        max=2.5,
                        decimals=1,
                        thresholdsMode='percentage',
                        repeatDirection='h',
                        pluginVersion='7',
                  ).addThreshold(
                        { color: 'red', value: 0 }
                  ).addThreshold(
                        { color: 'yellow', value: 30 }
                  ).addThreshold(
                        { color: 'green', value: 70 }
                  ).addTarget(influxdb.target(query='
from(bucket: "host_private")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "internet")
  |> filter(fn: (r) => r["_field"] == "upload_mbps")
  |> filter(fn: (r) => r["metric"] == "upload")
  |> keep(columns: ["_time", "_value"])
  |> sort(columns: ["_time"])
  |> last()
                  '))
//ASM                 { gridPos: { x: 0, y: 5, w: 24, h: 5 } }
//AST                 { gridPos: { x: 0, y: 5, w: 5, h: 5 } }
//ASD                 { gridPos: { x: 0, y: 5, w: 5, h: 5 } }
                  ,

                  gauge.new(
                        title='Internet Max Download',
                        datasource='InfluxDB_V2',
                        reducerFunction='last',
                        showThresholdLabels=false,
                        showThresholdMarkers=true,
                        unit="MBs",
                        min=0,
                        max=6.25,
                        decimals=1,
                        thresholdsMode='percentage',
                        repeatDirection='h',
                        pluginVersion='7',
                  ).addThreshold(
                        { color: 'red', value: 0 }
                  ).addThreshold(
                        { color: 'yellow', value: 30 }
                  ).addThreshold(
                        { color: 'green', value: 70 }
                  ).addTarget(influxdb.target(query='
from(bucket: "host_private")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "internet")
  |> filter(fn: (r) => r["_field"] == "download_mbps")
  |> filter(fn: (r) => r["metric"] == "download")
  |> keep(columns: ["_time", "_value"])
  |> sort(columns: ["_time"])
  |> last()
                  '))
//ASM                 { gridPos: { x: 0, y: 13, w: 24, h: 5 } }
//AST                 { gridPos: { x: 5, y: 5, w: 5, h: 5 } }
//ASD                 { gridPos: { x: 5, y: 5, w: 5, h: 5 } }
                  ,

                  stat.new(
                        title='Internet Mean Latency',
                        datasource='InfluxDB_V2',
                        unit='ms',
                        decimals=1,
                        reducerFunction='last',
                        colorMode='value',
                        graphMode='area',
                        justifyMode='auto',
                        thresholdsMode='absolute',
                        repeatDirection='h',
                        pluginVersion='7',
                  ).addThreshold(
                        { color: 'red', value: 0 }
                  ).addThreshold(
                        { color: 'green', value: 0.1 }
                  ).addThreshold(
                        { color: 'yellow', value: 20 }
                  ).addThreshold(
                        { color: 'red', value: 30 }
                  ).addTarget(influxdb.target(query='
from(bucket: "host_private")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "internet")
  |> filter(fn: (r) => r["_field"] == "ping_min_ms")
  |> filter(fn: (r) => r["metric"] == "ping")
  |> keep(columns: ["_time", "_value"])
  |> sort(columns: ["_time"])
  |> aggregateWindow(every: v.windowPeriod, fn: mean, createEmpty: false)
  |> fill(column: "_value", usePrevious: true)
                  '))
//ASM                 { gridPos: { x: 0, y: 21, w: 24, h: 5 } }
//AST                 { gridPos: { x: 10, y: 5, w: 5, h: 5 } }
//ASD                 { gridPos: { x: 10, y: 5, w: 5, h: 5 } }
                  ,

                  graph.new(
                        title='Internet Total Throughput',
                        datasource='InfluxDB_V2',
                        fill=0,
                        format='Bps',
                        bars=true,
                        lines=false,
                        staircase=false,
//ASD                   legend_values=true,
//ASD                   legend_min=true,
//ASD                   legend_max=true,
//ASD                   legend_current=false,
//ASD                   legend_total=false,
//ASD                   legend_avg=true,
//ASD                   legend_alignAsTable=true,
//ASD                   legend_rightSide=true,
//ASD                   legend_sideWidth=400
                  ).addTarget(influxdb.target(query='
from(bucket: "host_private")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "usg_wan_ports")
  |> filter(fn: (r) => r["_field"] == "tx_bytes")
  |> keep(columns: ["_time", "_value", "name"])
  |> sort(columns: ["_time"])
  |> aggregateWindow(every: v.windowPeriod, fn: max, createEmpty: false)
  |> derivative(unit: 1s, nonNegative: true)
  |> keep(columns: ["_time", "_value"])
  |> rename(columns: {_value: "Upload"})
                  ')).addTarget(influxdb.target(query='
from(bucket: "host_private")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "usg_wan_ports")
  |> filter(fn: (r) => r["_field"] == "rx_bytes")
  |> keep(columns: ["_time", "_value", "name"])
  |> sort(columns: ["_time"])
  |> aggregateWindow(every: v.windowPeriod, fn: max, createEmpty: false)
  |> derivative(unit: 1s, nonNegative: true)
  |> keep(columns: ["_time", "_value"])
  |> rename(columns: {_value: "Download"})
                  ')).addSeriesOverride(
                        { "alias": "Upload", "transform": "negative-Y" }
                  )
//ASM                 { gridPos: { x: 0, y: 34, w: 24, h: 7 } }
//AST                 { gridPos: { x: 0, y: 10, w: 24, h: 12 } }
//ASD                 { gridPos: { x: 0, y: 10, w: 24, h: 12 } }
                  ,

                  graph.new(
                        title='Internet Max Throughput',
                        datasource='InfluxDB_V2',
                        fill=0,
                        format='MBs',
                        bars=false,
                        lines=true,
                        staircase=true,
//ASD                   legend_values=true,
//ASD                   legend_min=true,
//ASD                   legend_max=true,
//ASD                   legend_current=false,
//ASD                   legend_total=false,
//ASD                   legend_avg=true,
//ASD                   legend_alignAsTable=true,
//ASD                   legend_rightSide=true,
//ASD                   legend_sideWidth=400
                  ).addTarget(influxdb.target(query='
from(bucket: "host_private")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "internet")
  |> filter(fn: (r) => r["_field"] == "upload_mbps")
  |> keep(columns: ["_time", "_value", "metric"])
  |> aggregateWindow(every: v.windowPeriod, fn: max, createEmpty: false)
  |> sort(columns: ["_time"])
  |> fill(column: "_value", usePrevious: true)
  |> keep(columns: ["_time", "_value"])
  |> rename(columns: {_value: "Upload"})
                  ')).addTarget(influxdb.target(query='
from(bucket: "host_private")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "internet")
  |> filter(fn: (r) => r["_field"] == "download_mbps")
  |> keep(columns: ["_time", "_value", "metric"])
  |> aggregateWindow(every: v.windowPeriod, fn: max, createEmpty: false)
  |> sort(columns: ["_time"])
  |> fill(column: "_value", usePrevious: true)
  |> keep(columns: ["_time", "_value"])
  |> rename(columns: {_value: "Download"})
                  ')).addSeriesOverride(
                        { "alias": "Upload", "transform": "negative-Y" }
                  )
//ASM                 { gridPos: { x: 0, y: 41, w: 24, h: 7 } }
//AST                 { gridPos: { x: 0, y: 22, w: 24, h: 12 } }
//ASD                 { gridPos: { x: 0, y: 22, w: 24, h: 12 } }
                  ,

                  graph.new(
                        title='Internet Min Latency',
                        datasource='InfluxDB_V2',
                        fill=0,
                        format='ms',
                        bars=false,
                        lines=true,
                        staircase=true,
//ASD                   legend_values=true,
//ASD                   legend_min=true,
//ASD                   legend_max=true,
//ASD                   legend_current=false,
//ASD                   legend_total=false,
//ASD                   legend_avg=true,
//ASD                   legend_alignAsTable=true,
//ASD                   legend_rightSide=true,
//ASD                   legend_sideWidth=400
                  ).addTarget(influxdb.target(query='
import "strings"
from(bucket: "host_private")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "internet")
  |> filter(fn: (r) => r["_field"] == "ping_min_ms")
  |> filter(fn: (r) => r["metric"] == "ping")
  |> keep(columns: ["_time", "_value", "host_location"])
  |> aggregateWindow(every: v.windowPeriod, fn: min, createEmpty: false)
  |> sort(columns: ["_time"])
  |> fill(column: "_value", usePrevious: true)
  |> keep(columns: ["_time", "_value", "host_location"])
  |> map(fn: (r) => ({ r with host_location: strings.title(v: r.host_location) }))
  |> rename(columns: {_value: ""})
                  '))
//ASM                 { gridPos: { x: 0, y: 48, w: 24, h: 7 } }
//AST                 { gridPos: { x: 0, y: 34, w: 24, h: 12 } }
//ASD                 { gridPos: { x: 0, y: 34, w: 24, h: 12 } }
                  ,

                  table.new(
                        title='Internet Categorised Throughput',
                        datasource='InfluxDB_V2',
                        default_unit='decbytes'
                  ).addTarget(influxdb.target(query='
start_bytes = from(bucket: "host_private")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "clientdpi")
  |> filter(fn: (r) => r["mac"] == "TOTAL")
  |> filter(fn: (r) => r["application"] == "TOTAL")
  |> filter(fn: (r) => r["_field"] == "rx_bytes" or r["_field"] == "tx_bytes")
  |> first()
  |> keep(columns: ["category", "_field", "_value"])
  |> pivot(rowKey:["category"], columnKey: ["_field"], valueColumn: "_value")
  |> map(fn: (r) => ({ r with rx_bytes_start: r.rx_bytes }))
  |> map(fn: (r) => ({ r with tx_bytes_start: r.tx_bytes }))
  |> keep(columns: ["category", "rx_bytes_start", "tx_bytes_start"])
finish_bytes = from(bucket: "host_private")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "clientdpi")
  |> filter(fn: (r) => r["mac"] == "TOTAL")
  |> filter(fn: (r) => r["application"] == "TOTAL")
  |> filter(fn: (r) => r["_field"] == "rx_bytes" or r["_field"] == "tx_bytes")
  |> last()
  |> keep(columns: ["category", "_field", "_value"])
  |> pivot(rowKey:["category"], columnKey: ["_field"], valueColumn: "_value")
  |> keep(columns: ["category", "rx_bytes", "tx_bytes"])
join(tables: {d1: start_bytes, d2: finish_bytes},      on: ["category"])
  |> map(fn: (r) => ({ r with "Category": r.category }))
  |> map(fn: (r) => ({ r with "Received": r.rx_bytes - r.rx_bytes_start }))
  |> map(fn: (r) => ({ r with "Transmitted": r.tx_bytes - r.tx_bytes_start }))
  |> map(fn: (r) => ({ r with "Received Total": r.rx_bytes }))
  |> map(fn: (r) => ({ r with "Transmitted Total": r.tx_bytes }))
  |> keep(columns: ["Category", "Received", "Transmitted", "Received Total", "Transmitted Total"])
  |> sort(columns: ["Received"], desc: true)
                  '))
//ASM                 { gridPos: { x: 0, y: 55, w: 24, h: 7 } }
//AST                 { gridPos: { x: 0, y: 46, w: 24, h: 12 } }
//ASD                 { gridPos: { x: 0, y: 46, w: 24, h: 12 } }
                  ,

                  table.new(
                        title='Domain Resolution',
                        datasource='InfluxDB_V2'
                  ).addTarget(influxdb.target(query='
start_ips = from(bucket: "host_private")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "internet")
  |> filter(fn: (r) => r["_field"] == "ip")
  |> keep(columns: ["_time", "_value", "host_resolver"])
  |> truncateTimeColumn(unit: 30s)
  |> pivot(rowKey:["_time"], columnKey: ["host_resolver"], valueColumn: "_value")
  |> filter(fn: (r) => r["*.*.*.*"] != "unknown")
  |> sort(columns: ["_time"], desc: false)
  |> unique(column: "*.*.*.*")
  |> sort(columns: ["_time"], desc: true)
finish_ips = from(bucket: "host_private")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "internet")
  |> filter(fn: (r) => r["_field"] == "ip")
  |> keep(columns: ["_time", "_value", "host_resolver"])
  |> truncateTimeColumn(unit: 30s)
  |> pivot(rowKey:["_time"], columnKey: ["host_resolver"], valueColumn: "_value")
  |> filter(fn: (r) => r["*.*.*.*"] != "unknown")
  |> sort(columns: ["_time"], desc: true)
  |> unique(column: "*.*.*.*")
  |> sort(columns: ["_time"], desc: true)
unknown_ips = from(bucket: "host_private")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "internet")
  |> filter(fn: (r) => r["_field"] == "ip")
  |> keep(columns: ["_time", "_value", "host_resolver"])
  |> truncateTimeColumn(unit: 30s)
  |> pivot(rowKey:["_time"], columnKey: ["host_resolver"], valueColumn: "_value")
  |> filter(fn: (r) => r["*.*.*.*"] == "unknown")
  |> sort(columns: ["_time"], desc: true)
union(tables: [start_ips, finish_ips, unknown_ips])
  |> sort(columns: ["_time"], desc: true)
  |> rename(columns: {_time: "Time"})
                  '))
//ASM                 { gridPos: { x: 0, y: 62, w: 24, h: 7 } }
//AST                 { gridPos: { x: 0, y: 58, w: 24, h: 12 } }
//ASD                 { gridPos: { x: 0, y: 58, w: 24, h: 12 } }
                  ,

            ],
}
