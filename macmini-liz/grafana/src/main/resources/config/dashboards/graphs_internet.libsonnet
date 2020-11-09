{
  graphs()::
  
    local grafana = import 'grafonnet/grafana.libsonnet';
    local dashboard = grafana.dashboard;
    local stat = grafana.statPanel;
    local graph = grafana.graphPanel;
    local table = grafana.tablePanel;
    local gauge = grafana.gaugePanel;
    local influxdb = grafana.influxdb;
    
    [

      stat.new(
        title='Internet Uptime',
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
  |> filter(fn: (r) => r["_measurement"] == "internet")
  |> filter(fn: (r) => r["_field"] == "uptime_s")
  |> filter(fn: (r) => r["metric"] == "network")
  |> keep(columns: ["_time", "_value"])
  |> sort(columns: ["_time"])
  |> last()
// End')) { gridPos: { x: 0, y: 0, w: 4, h: 3 } },

      stat.new(
        title='Service Availability',
        datasource='InfluxDB2',
        unit='percent',
        decimals=0,
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
        { color: 'yellow', value: 80 }
      ).addThreshold(
        { color: 'green', value: 99 }
      ).addTarget(influxdb.target(query='// Start
import "math"
from(bucket: "hosts")
 |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
 |> filter(fn: (r) => r["_measurement"] == "internet")
 |> filter(fn: (r) => r["_field"] == "uptime_delta_s")
 |> filter(fn: (r) => r["metric"] == "network" or r["metric"] == "lookup" or r["metric"] == "certificate")
 |> keep(columns: ["_start", "_stop", "_value"])
 |> sum()
 |> map(fn: (r) => ({ r with _value: math.mMin(x: 100.0, y: math.floor(x: r._value / (3.0 * float(v: uint(v: r._stop) - uint(v: r._start))) * 100000000000.0)) }))
// End')) { gridPos: { x: 0, y: 3, w: 4, h: 3 } },

      stat.new(
        title='Domain Uptime',
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
        { color: 'yellow', value: 600 }
      ).addThreshold(
        { color: 'green', value: 12000 }
      ).addTarget(influxdb.target(query='// Start
from(bucket: "hosts")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "internet")
  |> filter(fn: (r) => r["_field"] == "uptime_s")
  |> filter(fn: (r) => r["metric"] == "certificate")
  |> keep(columns: ["_time", "_value"])
  |> sort(columns: ["_time"])
  |> last()
// End')) { gridPos: { x: 4, y: 0, w: 4, h: 3 } },

      stat.new(
        title='Certificate Expiry',
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
        { color: 'yellow', value: 432000 }
      ).addThreshold(
        { color: 'green', value: 864000 }
      ).addTarget(influxdb.target(query='// Start
from(bucket: "hosts")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "internet")
  |> filter(fn: (r) => r["_field"] == "expiry_s")
  |> filter(fn: (r) => r["metric"] == "certificate")
  |> keep(columns: ["_time", "_value"])
  |> sort(columns: ["_time"])
  |> last()
// End')) { gridPos: { x: 4, y: 3, w: 4, h: 3 } },

      stat.new(
        title='Internet Latency',
        datasource='InfluxDB2',
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
      ).addTarget(influxdb.target(query='// Start
from(bucket: "hosts")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "internet")
  |> filter(fn: (r) => r["_field"] == "ping_min_ms")
  |> filter(fn: (r) => r["metric"] == "ping")
  |> filter(fn: (r) => r["host_location"] == "perth")
  |> keep(columns: ["_time", "_value"])
  |> sort(columns: ["_time"])
  |> aggregateWindow(every: v.windowPeriod, fn: mean, createEmpty: true)
  |> fill(column: "_value", usePrevious: true)
// End')) { gridPos: { x: 8, y: 3, w: 6, h: 6 } },

      gauge.new(
        title='Internet Download',
        datasource='InfluxDB2',
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
      ).addTarget(influxdb.target(query='// Start
from(bucket: "hosts")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "internet")
  |> filter(fn: (r) => r["_field"] == "download_mbps")
  |> filter(fn: (r) => r["metric"] == "download")
  |> keep(columns: ["_time", "_value"])
  |> sort(columns: ["_time"])
  |> last()
// End')) { gridPos: { x: 14, y: 0, w: 5, h: 6 } },

      gauge.new(
        title='Internet Upload',
        datasource='InfluxDB2',
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
      ).addTarget(influxdb.target(query='// Start
from(bucket: "hosts")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "internet")
  |> filter(fn: (r) => r["_field"] == "upload_mbps")
  |> filter(fn: (r) => r["metric"] == "upload")
  |> keep(columns: ["_time", "_value"])
  |> sort(columns: ["_time"])
  |> last()
// End')) { gridPos: { x: 19, y: 0, w: 5, h: 6 } },


      graph.new(
        title='Internet Throughput',
        datasource='InfluxDB2',
        fill=0,
        format='Bps',
        bars=true,
        lines=false,
        staircase=false,
        legend_values=true,
        legend_min=true,
        legend_max=true,
        legend_current=true,
        legend_total=false,
        legend_avg=false,
        legend_alignAsTable=true,
        legend_rightSide=true,
        legend_sideWidth=350
      ).addTarget(influxdb.target(query='// Start
from(bucket: "hosts")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "usg_wan_ports")
  |> filter(fn: (r) => r["_field"] == "rx_bytes")
  |> set(key: "name", value: "Download")
  |> keep(columns: ["table", "_start", "_stop", "_time", "_value", "name"])
  |> sort(columns: ["_time"])
  |> aggregateWindow(every: v.windowPeriod, fn: max, createEmpty: true)
  |> derivative(unit: 1s, nonNegative: true)
// End')).addTarget(influxdb.target(query='// Start
from(bucket: "hosts")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "usg_wan_ports")
  |> filter(fn: (r) => r["_field"] == "tx_bytes")
  |> set(key: "name", value: "Upload")
  |> keep(columns: ["table", "_start", "_stop", "_time", "_value", "name"])
  |> sort(columns: ["_time"])
  |> aggregateWindow(every: v.windowPeriod, fn: max, createEmpty: true)
  |> derivative(unit: 1s, nonNegative: true)
// End')).addSeriesOverride(
        { "alias": "Upload", "transform": "negative-Y" }
      ) { gridPos: { x: 0, y: 6, w: 24, h: 12 } },


      graph.new(
        title='Internet Latency',
        datasource='InfluxDB2',
        fill=0,
        format='ms',
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
        legend_sideWidth=350
      ).addTarget(influxdb.target(query='// Start
import "strings"
from(bucket: "hosts")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "internet")
  |> filter(fn: (r) => r["_field"] == "ping_min_ms")
  |> filter(fn: (r) => r["metric"] == "ping")
  |> keep(columns: ["_time", "_value", "host_location"])
  |> aggregateWindow(every: v.windowPeriod, fn: min, createEmpty: true)
  |> map(fn: (r) => ({ r with host_location: strings.title(v: r.host_location) }))
  |> sort(columns: ["_time"])
  |> fill(column: "_value", usePrevious: true)
// End')) { gridPos: { x: 0, y: 36, w: 24, h: 12 } },

      table.new(
        title='Domain Resolution',
        datasource='InfluxDB2'
      ).addTarget(influxdb.target(query='// Start
start_ips = from(bucket: "hosts")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "internet")
  |> filter(fn: (r) => r["_field"] == "ip")
  |> keep(columns: ["_time", "_value", "host_resolver"])
  |> truncateTimeColumn(unit: 30s)
  |> pivot(rowKey:["_time"], columnKey: ["host_resolver"], valueColumn: "_value")
  |> sort(columns: ["_time"], desc: false)
  |> unique(column: "*.*.*.*")
  |> sort(columns: ["_time"], desc: true)
finish_ips = from(bucket: "hosts")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "internet")
  |> filter(fn: (r) => r["_field"] == "ip")
  |> keep(columns: ["_time", "_value", "host_resolver"])
  |> truncateTimeColumn(unit: 30s)
  |> pivot(rowKey:["_time"], columnKey: ["host_resolver"], valueColumn: "_value")
  |> sort(columns: ["_time"], desc: true)
  |> unique(column: "*.*.*.*")
  |> sort(columns: ["_time"], desc: true)
union(tables: [start_ips, finish_ips])
  |> sort(columns: ["_time"], desc: true)
// End')) { gridPos: { x: 0, y: 48, w: 24, h: 12 } },

    ],
}
