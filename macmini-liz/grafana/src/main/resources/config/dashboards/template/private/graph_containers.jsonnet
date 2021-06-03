// GRAPH_DASHBOARD_DEFAULTS: time_from='now-1h', refresh=''
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
        title='Containers Currently Running',
        datasource='InfluxDB2Private',
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
        { color: 'red', value: 0 }
      ).addThreshold(
        { color: 'yellow', value: 5 }
      ).addThreshold(
        { color: 'green', value: 10 }
      ).addTarget(influxdb.target(query='// Start
// TODO: Averaging all values is very slow
// import "math"
// from(bucket: "host_private")
//   |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
//   |> filter(fn: (r) => r["_measurement"] == "docker")
//   |> filter(fn: (r) => r["_field"] == "n_containers_running")
//   |> keep(columns: ["_time", "_value", "_field"])
//   |> group(columns: ["_time", "_field"], mode:"by")
//   |> sum()
//   |> group()
//   |> mean()
//   |> map(fn: (r) => ({ r with _value: math.ceil(x: r._value) }))
from(bucket: "host_private")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "docker")
  |> filter(fn: (r) => r["_field"] == "n_containers_running")
  |> keep(columns: ["_time", "_value", "_field", "host"])
  |> last()
  |> group()
  |> sum()
// End')) { gridPos: { x: 0, y: 0, w: 5, h: 3 } },

      stat.new(
        title='Containers Currently Not Running',
        datasource='InfluxDB2Private',
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
        { color: 'red', value: 1 }
      ).addTarget(influxdb.target(query='// Start
// TODO: Averaging all values is very slow
// import "math"
// from(bucket: "host_private")
//   |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
//   |> filter(fn: (r) => r["_measurement"] == "docker")
//   |> filter(fn: (r) => r["_field"] == "n_containers_paused" or r["_field"] == "n_containers_stopped" )
//   |> keep(columns: ["_time", "_value", "_field"])
//   |> group(columns: ["_time", "_field"], mode:"by")
//   |> sum()
//   |> group()
//   |> mean()
//   |> map(fn: (r) => ({ r with _value: math.ceil(x: r._value) }))
from(bucket: "host_private")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "docker")
  |> filter(fn: (r) => r["_field"] == "n_containers_paused" or r["_field"] == "n_containers_stopped" )
  |> keep(columns: ["_time", "_value", "_field", "host"])
  |> last()
  |> group()
  |> sum()
// End')) { gridPos: { x: 5, y: 0, w: 5, h: 3 } },

      stat.new(
        title='Container Images Currently Installed',
        datasource='InfluxDB2Private',
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
        { color: 'red', value: 0 }
      ).addThreshold(
        { color: 'yellow', value: 5 }
      ).addThreshold(
        { color: 'green', value: 10 }
      ).addTarget(influxdb.target(query='// Start
// TODO: Averaging all values is very slow
// import "math"
// from(bucket: "host_private")
//   |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
//   |> filter(fn: (r) => r["_measurement"] == "docker")
//   |> filter(fn: (r) => r["_field"] == "n_images" )
//   |> keep(columns: ["_time", "_value", "_field"])
//   |> group(columns: ["_time", "_field"], mode:"by")
//   |> sum()
//   |> group()
//   |> mean()
//   |> map(fn: (r) => ({ r with _value: math.ceil(x: r._value) }))
from(bucket: "host_private")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "docker")
  |> filter(fn: (r) => r["_field"] == "n_images" )
  |> keep(columns: ["_time", "_value", "_field", "host"])
  |> last()
  |> group()
  |> sum()
// End')) { gridPos: { x: 10, y: 0, w: 5, h: 3 } },

      bar.new(
        title='Containers with Peak Usage <50%',
        datasource='InfluxDB2Private',
        unit='percent',
        thresholds=[
          { 'color': 'red', 'value': null },
          { 'color': 'yellow', 'value': 50 },
          { 'color': 'green', 'value': 90 }
        ],
      ).addTarget(influxdb.target(query='// Start
import "math"
import "strings"
from(bucket: "host_private")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "docker_container_cpu")
  |> filter(fn: (r) => r["_field"] == "usage_percent")
  |> keep(columns: ["_time", "_value", "container_name", "host"])
  |> max()
  |> group()
  |> map(fn: (r) => ({ r with index: 1 }))
  |> cumulativeSum(columns: ["index"])
  |> map(fn: (r) => ({ r with _value: if strings.containsStr(substr: "macmini", v: r.host)  then r._value / 4.0 else (if strings.containsStr(substr: "macbookpro", v: r.host)  then r._value / 8.0 else r._value) }))
  |> map(fn: (r) => ({ r with _value: if r._value > 50.0 then 1 else 0 }))
  |> cumulativeSum(columns: ["_value"])
  |> last()
  |> map(fn: (r) => ({ r with "CPU": math.mMin(x: 100.0, y: 100.0 - float(v: r._value) / float(v: r.index) * 100.0) }))
  |> keep(columns: ["CPU"])
// End')).addTarget(influxdb.target(query='// Start
import "math"
from(bucket: "host_private")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "docker_container_mem")
  |> filter(fn: (r) => r["_field"] == "usage_percent")
  |> keep(columns: ["_time", "_value", "container_name"])
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
from(bucket: "host_private")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "docker_container_blkio")
  |> filter(fn: (r) => r["_field"] == "io_service_bytes_recursive_read")
  |> keep(columns: ["_time", "_value", "container_name"])
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
from(bucket: "host_private")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "docker_container_net")
  |> filter(fn: (r) => r["_field"] == "rx_bytes" or r["_field"] == "tx_bytes")
  |> keep(columns: ["_time", "_value", "container_name"])
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
        title='Container Mean Running Rate',
        datasource='InfluxDB2Private',
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
        { color: 'yellow', value: 95 }
      ).addThreshold(
        { color: 'green', value: 99 }
      ).addTarget(influxdb.target(query='// Start
import "math"
from(bucket: "host_private")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "docker")
  |> filter(fn: (r) => r["_field"] == "n_containers" or r["_field"] == "n_containers_running")
  |> keep(columns: ["_time", "_value", "_field"])
  |> truncateTimeColumn(unit: v.windowPeriod)
  |> group(columns: ["_time", "_field"], mode:"by")
  |> sum()
  |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
  |> fill(column: "n_containers_running", value: 1)
  |> fill(column: "n_containers", value: 1)
  |> map(fn: (r) => ({ r with _value: math.mMin(x: 100.0, y: float(v: r.n_containers_running) / float(v: r.n_containers) * 100.0) }))
  |> keep(columns: ["_value"])
  |> mean()
// End')) { gridPos: { x: 0, y: 3, w: 5, h: 5 } },

      gauge.new(
        title='Container Mean Healthy Rate',
        datasource='InfluxDB2Private',
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
        { color: 'yellow', value: 95 }
      ).addThreshold(
        { color: 'green', value: 99 }
      ).addTarget(influxdb.target(query='// Start
import "math"
from(bucket: "host_private")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "docker_container_health")
  |> filter(fn: (r) => r["_field"] == "health_status")
  |> filter(fn: (r) => r["_field"] == "health_status")
  |> keep(columns: ["_value", "container_name"])
  |> map(fn: (r) => ({ r with _value: if r._value == "healthy" then 1 else (if r._value == "unhealthy" then -1 else 0) }))
  |> group(columns: ["container_name"], mode:"by")
  |> keep(columns: ["_value"])
  |> map(fn: (r) => ({ r with index: 1 }))
  |> cumulativeSum(columns: ["index"])
  |> cumulativeSum(columns: ["_value"])
  |> last()
  |> map(fn: (r) => ({ r with _value: math.mMin(x: 100.0, y: float(v: r._value) / float(v: r.index) * 100.0) }))
  |> keep(columns: ["_value"])
  |> group()
  |> mean()
// End')) { gridPos: { x: 5, y: 3, w: 5, h: 5 } },

      gauge.new(
        title='Container Image Usage',
        datasource='InfluxDB2Private',
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
        { color: 'yellow', value: 95 }
      ).addThreshold(
        { color: 'green', value: 99 }
      ).addTarget(influxdb.target(query='// Start
import "math"
from(bucket: "host_private")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "docker")
  |> filter(fn: (r) => r["_field"] == "n_containers" or r["_field"] == "n_images")
  |> keep(columns: ["_time", "_value", "_field"])
  |> truncateTimeColumn(unit: v.windowPeriod)
  |> group(columns: ["_time", "_field"], mode:"by")
  |> sum()
  |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
  |> fill(column: "n_images", value: 1)
  |> fill(column: "n_containers", value: 1)
  |> map(fn: (r) => ({ r with _value: math.mMin(x: 100.0, y: float(v: r.n_containers) / float(v: r.n_images) * 100.0) }))
  |> keep(columns: ["_value"])
  |> mean()
// End')) { gridPos: { x: 10, y: 3, w: 5, h: 5 } },

      graph.new(
        title='Container CPU Usage',
        datasource='InfluxDB2Private',
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
import "strings"
from(bucket: "host_private")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "docker_container_cpu")
  |> filter(fn: (r) => r["_field"] == "usage_percent")
  |> keep(columns: ["_time", "_value", "container_name", "host"])
  |> aggregateWindow(every: v.windowPeriod, fn: mean, createEmpty: false)
  |> map(fn: (r) => ({ r with _value: if strings.containsStr(substr: "macmini", v: r.host)  then r._value / 4.0 else (if strings.containsStr(substr: "macbookpro", v: r.host)  then r._value / 8.0 else r._value) }))
  |> map(fn: (r) => ({ r with container_name: r.container_name + " (" + r.host + ")" }))
  |> keep(columns: ["_time", "_value", "container_name"])
// End')) { gridPos: { x: 0, y: 8, w: 24, h: 12 } },

      graph.new(
        title='Container RAM Usage',
        datasource='InfluxDB2Private',
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
from(bucket: "host_private")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "docker_container_mem")
  |> filter(fn: (r) => r["_field"] == "usage_percent")
  |> map(fn: (r) => ({ r with container_name: r.container_name + " (" + r.host + ")" }))
  |> keep(columns: ["_time", "_value", "container_name"])
  |> aggregateWindow(every: v.windowPeriod, fn: mean, createEmpty: false)
  |> fill(column: "_value", usePrevious: true)
// End')) { gridPos: { x: 0, y: 20, w: 24, h: 12 } },

      graph.new(
        title='Container IOPS Usage',
        datasource='InfluxDB2Private',
        fill=0,
        format='Bps',
        bars=false,
        lines=true,
        staircase=false,
        points=true,
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
from(bucket: "host_private")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "docker_container_blkio")
  |> filter(fn: (r) => r["_field"] == "io_service_bytes_recursive_read")
  |> map(fn: (r) => ({ r with container_name: r.container_name + " + Read (" + r.host + ")" }))
  |> keep(columns: ["_time", "_value", "container_name"])
  |> aggregateWindow(every: v.windowPeriod, fn: mean, createEmpty: false)
  |> fill(column: "_value", usePrevious: true)
  |> derivative(unit: 1s, nonNegative: true)
// End')).addTarget(influxdb.target(query='// Start
from(bucket: "host_private")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "docker_container_blkio")
  |> filter(fn: (r) => r["_field"] == "io_service_bytes_recursive_write")
  |> map(fn: (r) => ({ r with container_name: r.container_name + " - Write (" + r.host + ")" }))
  |> keep(columns: ["_time", "_value", "container_name"])
  |> aggregateWindow(every: v.windowPeriod, fn: mean, createEmpty: false)
  |> fill(column: "_value", usePrevious: true)
  |> derivative(unit: 1s, nonNegative: true)
// End')).addSeriesOverride(
        { "alias": "/.*Write.*/", "transform": "negative-Y" }
      ) { gridPos: { x: 0, y: 32, w: 24, h: 12 } },

      graph.new(
        title='Container Network Usage',
        datasource='InfluxDB2Private',
        fill=0,
        format='Bps',
        bars=false,
        lines=true,
        staircase=false,
        points=true,
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
from(bucket: "host_private")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "docker_container_net")
  |> filter(fn: (r) => r["_field"] == "rx_bytes")
  |> map(fn: (r) => ({ r with container_name: r.container_name + " + Receive (" + r.host + ")" }))
  |> keep(columns: ["_time", "_value", "container_name"])
  |> aggregateWindow(every: v.windowPeriod, fn: mean, createEmpty: false)
  |> fill(column: "_value", usePrevious: true)
  |> derivative(unit: 1s, nonNegative: true)
// End')).addTarget(influxdb.target(query='// Start
from(bucket: "host_private")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "docker_container_net")
  |> filter(fn: (r) => r["_field"] == "tx_bytes")
  |> map(fn: (r) => ({ r with container_name: r.container_name + " - Transmit (" + r.host + ")" }))
  |> keep(columns: ["_time", "_value", "container_name"])
  |> aggregateWindow(every: v.windowPeriod, fn: mean, createEmpty: false)
  |> fill(column: "_value", usePrevious: true)
  |> derivative(unit: 1s, nonNegative: true)
// End')).addSeriesOverride(
        { "alias": "/.*Transmit.*/", "transform": "negative-Y" }
      ) { gridPos: { x: 0, y: 46, w: 24, h: 12 } },

      table.new(
        title='Container Current Process Status',
        datasource='InfluxDB2Private',
        default_unit='ns'
      ).addTarget(influxdb.target(query='// Start
status = from(bucket: "host_private")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "docker_container_status")
  |> filter(fn: (r) => r["_field"] == "uptime_ns")
  |> last()
  |> map(fn: (r) => ({ r with "Name": r.container_name }))
  |> map(fn: (r) => ({ r with "Status": r.container_status }))
  |> map(fn: (r) => ({ r with "Uptime": r._value }))
  |> map(fn: (r) => ({ r with "Host": r.host }))
  |> keep(columns: ["Name", "Status", "Uptime", "Host"])
  |> group()
health = from(bucket: "host_private")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "docker_container_health")
  |> filter(fn: (r) => r["_field"] == "health_status")
  |> last()
  |> map(fn: (r) => ({ r with "Name": r.container_name }))
  |> map(fn: (r) => ({ r with "Temperature": r._value }))
  |> map(fn: (r) => ({ r with "Host": r.host }))
  |> keep(columns: ["Name", "Temperature", "Host"])
  |> group()
union(tables: [status, health])
  |> group(columns: ["Name"])
  |> sort(columns: ["_time"], desc: true)
  |> fill(column: "Status", usePrevious: true)
  |> fill(column: "Uptime", usePrevious: true)
  |> fill(column: "Temperature", value: "healthy")
  |> map(fn: (r) => ({ r with _value: 0 }))
  |> last()
  |> keep(columns: ["Name", "Status", "Temperature", "Uptime", "Host"])
  |> group()
// End')) { gridPos: { x: 0, y: 60, w: 24, h: 18 } },

    ],
}
