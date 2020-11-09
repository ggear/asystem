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
        title='Gateway Uptime',
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
  |> filter(fn: (r) => r["_measurement"] == "usg")
  |> filter(fn: (r) => r["_field"] == "uptime")
  |> keep(columns: ["_time", "_value"])
  |> last()
// End')) { gridPos: { x: 0, y: 0, w: 4, h: 3 } },

      stat.new(
        title='Network Clients',
        datasource='InfluxDB2',
        unit='clients',
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
        { color: 'yellow', value: 1 }
      ).addThreshold(
        { color: 'green', value: 5 }
      ).addTarget(influxdb.target(query='// Start
from(bucket: "hosts")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "clients")
  |> filter(fn: (r) => r["_field"] == "hostname")
  |> keep(columns: ["_value"])
  |> unique()
  |> count()
// End')) { gridPos: { x: 0, y: 4, w: 4, h: 3 } },

      gauge.new(
        title='Wireless Quality Score (5GHz)',
        datasource='InfluxDB2',
        reducerFunction='last',
        showThresholdLabels=false,
        showThresholdMarkers=true,
        unit="percent",
        min=0,
        max=100,
        decimals=0,
        thresholdsMode='percentage',
        repeatDirection='h',
        pluginVersion='7',
      ).addThreshold(
        { color: 'red', value: 0 }
      ).addThreshold(
        { color: 'yellow', value: 15 }
      ).addThreshold(
        { color: 'green', value: 30 }
      ).addTarget(influxdb.target(query='// Start
from(bucket: "hosts")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "uap_vaps")
  |> filter(fn: (r) => r["_field"] == "ccq")
  |> filter(fn: (r) => r["radio"] == "na")
  |> keep(columns: ["_value"])
  |> mean()
  |> map(fn: (r) => ({ r with _value: r._value / 10.0 }))
// End')) { gridPos: { x: 4, y: 0, w: 5, h: 6 } },

      gauge.new(
        title='Wireless Quality Score (2.4GHz)',
        datasource='InfluxDB2',
        reducerFunction='last',
        showThresholdLabels=false,
        showThresholdMarkers=true,
        unit="percent",
        min=0,
        max=100,
        decimals=0,
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
  |> filter(fn: (r) => r["_measurement"] == "uap_vaps")
  |> filter(fn: (r) => r["_field"] == "ccq")
  |> filter(fn: (r) => r["radio"] == "ng")
  |> keep(columns: ["_value"])
  |> mean()
  |> map(fn: (r) => ({ r with _value: r._value / 10.0 }))
// End')) { gridPos: { x: 9, y: 0, w: 5, h: 6 } },

      gauge.new(
        title='Wireless Success Rate (5GHz)',
        datasource='InfluxDB2',
        reducerFunction='last',
        showThresholdLabels=false,
        showThresholdMarkers=true,
        unit="percent",
        min=0,
        max=100,
        decimals=0,
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
  |> filter(fn: (r) => r["_measurement"] == "uap_vaps")
  |> filter(fn: (r) => r["_field"] == "tx_packets" or r["_field"] == "tx_combined_retries")
  |> filter(fn: (r) => r["radio"] == "na")
  |> keep(columns: ["_time", "_value", "_field"])
  |> aggregateWindow(every: v.windowPeriod, fn: mean, createEmpty: false)
  |> derivative(unit: 1s, nonNegative: true)
  |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
  |> fill(column: "tx_combined_retries", value: 0.0)
  |> filter(fn: (r) => r["tx_packets"] > 0)
  |> map(fn: (r) => ({ r with _value: 100.0 - r.tx_combined_retries / r.tx_packets * 100.0 }))
  |> mean()
// End')) { gridPos: { x: 14, y: 0, w: 5, h: 6 } },

      gauge.new(
        title='Wireless Success Rate (2.4GHz)',
        datasource='InfluxDB2',
        reducerFunction='last',
        showThresholdLabels=false,
        showThresholdMarkers=true,
        unit="percent",
        min=0,
        max=100,
        decimals=0,
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
  |> filter(fn: (r) => r["_measurement"] == "uap_vaps")
  |> filter(fn: (r) => r["_field"] == "tx_packets" or r["_field"] == "tx_combined_retries")
  |> filter(fn: (r) => r["radio"] == "ng")
  |> keep(columns: ["_time", "_value", "_field"])
  |> aggregateWindow(every: v.windowPeriod, fn: mean, createEmpty: false)
  |> derivative(unit: 1s, nonNegative: true)
  |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
  |> fill(column: "tx_combined_retries", value: 0.0)
  |> filter(fn: (r) => r["tx_packets"] > 0)
  |> map(fn: (r) => ({ r with _value: 100.0 - r.tx_combined_retries / r.tx_packets * 100.0 }))
  |> mean()
// End')) { gridPos: { x: 19, y: 0, w: 5, h: 6 } },

      graph.new(
        title='Network Throughput',
        datasource='InfluxDB2',
        fill=0,
        decimals=0,
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
  |> filter(fn: (r) => r["_measurement"] == "usg")
  |> filter(fn: (r) => r["_field"] == "lan-rx_bytes")
  |> set(key: "name", value: "Receive")
  |> keep(columns: ["table", "_start", "_stop", "_time", "_value", "name"])
  |> sort(columns: ["_time"])
  |> aggregateWindow(every: v.windowPeriod, fn: max, createEmpty: true)
  |> derivative(unit: 1s, nonNegative: true)
// End')).addTarget(influxdb.target(query='// Start
from(bucket: "hosts")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "usg")
  |> filter(fn: (r) => r["_field"] == "lan-tx_bytes")
  |> set(key: "name", value: "Transmit")
  |> keep(columns: ["table", "_start", "_stop", "_time", "_value", "name"])
  |> sort(columns: ["_time"])
  |> aggregateWindow(every: v.windowPeriod, fn: max, createEmpty: true)
  |> derivative(unit: 1s, nonNegative: true)
// End')).addSeriesOverride(
        { "alias": "Transmit", "transform": "negative-Y" }
      ) { gridPos: { x: 0, y: 6, w: 24, h: 12 } },

      graph.new(
        title='Network Clients',
        datasource='InfluxDB2',
        fill=1,
        format='short',
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
from(bucket: "hosts")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "clients")
  |> filter(fn: (r) => r["_field"] == "hostname")
  |> keep(columns: ["_time", "_value"])
  |> window(every: v.windowPeriod)
  |> unique()
  |> count()
  |> group()
  |> set(key: "name", value: "Clients")
// TODO: Separate wired/wireless, unfortunately data quality is poor coming from unifi, so many wireless devices show up as wired!
//from(bucket: "hosts")
//  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
//  |> filter(fn: (r) => r["_measurement"] == "clients")
//  |> filter(fn: (r) => r["_field"] == "hostname")
//  |> map(fn: (r) => ({ r with name: if exists r.radio then "Wireless" else "Wired" }))
//  |> keep(columns: ["_time", "_value", "name"])
//  |> window(every: v.windowPeriod)
//  |> unique()
//  |> count()
//  |> group(columns: ["name"], mode:"by")
// End')).addSeriesOverride(
        { "alias": "Transmit", "transform": "negative-Y" }
  ) { gridPos: { x: 0, y: 6, w: 24, h: 12 } },

    ],
}
