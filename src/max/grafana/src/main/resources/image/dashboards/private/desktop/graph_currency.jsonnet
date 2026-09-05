// WARNING: This file is written by the build process, any manual edits will be lost!

{
      graphs()::

            local grafana = import 'grafonnet/grafana.libsonnet';
            local asystem = import 'default/asystem-library.jsonnet';
            local dashboard = grafana.dashboard;
            local stat = grafana.statPanel;
            local graph = grafana.graphPanel;
            local table = grafana.tablePanel;
            local gauge = grafana.gaugePanel;
            local bar = grafana.barGaugePanel;
            local influxdb = grafana.influxdb;
            local header = asystem.header;

            header.new(
                style='maximal',
                formFactor='Desktop',
                measurement='currency',
                maxMilliSecSinceUpdate='259200000',
                simpleErrors=false,
            ) +

            [

                  stat.new(
                        title='GBP/AUD Last End of Day',
                        datasource='InfluxDB_V2',
                        unit='currencyUSD',
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
                  ).addTarget(influxdb.target(query='
from(bucket: "data_public")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "currency")
  |> filter(fn: (r) => r["_field"] == "aud/gbp")
  |> filter(fn: (r) => r["period"] == "1d")
  |> filter(fn: (r) => r["type"] == "snapshot")
  |> sort(columns: ["_time"], desc: false)
  |> last()
  |> map(fn: (r) => ({ r with _value: 1.0 / r._value }))
  |> keep(columns: ["_value"])
                  '))
                      { gridPos: { x: 0, y: 2, w: 5, h: 3 } }
                  ,

                  stat.new(
                        title='USD/AUD Last End of Day',
                        datasource='InfluxDB_V2',
                        unit='currencyUSD',
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
                  ).addTarget(influxdb.target(query='
from(bucket: "data_public")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "currency")
  |> filter(fn: (r) => r["_field"] == "aud/usd")
  |> filter(fn: (r) => r["period"] == "1d")
  |> filter(fn: (r) => r["type"] == "snapshot")
  |> sort(columns: ["_time"], desc: false)
  |> last()
  |> map(fn: (r) => ({ r with _value: 1.0 / r._value }))
  |> keep(columns: ["_value"])
                  '))
                      { gridPos: { x: 5, y: 2, w: 5, h: 3 } }
                  ,

                  stat.new(
                        title='SGD/AUD Last End of Day',
                        datasource='InfluxDB_V2',
                        unit='currencyUSD',
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
                  ).addTarget(influxdb.target(query='
from(bucket: "data_public")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "currency")
  |> filter(fn: (r) => r["_field"] == "aud/sgd")
  |> filter(fn: (r) => r["period"] == "1d")
  |> filter(fn: (r) => r["type"] == "snapshot")
  |> sort(columns: ["_time"], desc: false)
  |> map(fn: (r) => ({ r with _value: 1.0 / r._value }))
  |> last()
  |> keep(columns: ["_value"])
                  '))
                      { gridPos: { x: 10, y: 2, w: 5, h: 3 } }
                  ,

                  bar.new(
                        title='CCY/AUD Range End of Day Deltas',
                        datasource='InfluxDB_V2',
                        unit='percent',
                        min=-30,
                        max=30,
                        thresholds=[
                              { 'color': 'red', 'value': -9999 },
                              { 'color': 'yellow', 'value': -0.5 },
                              { 'color': 'green', 'value': 0.5 },
                        ],
                  ).addTarget(influxdb.target(query='
field = "aud/gbp"
series = from(bucket: "data_public")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "currency")
  |> filter(fn: (r) => r["period"] == "1d")
  |> filter(fn: (r) => r["type"] == "snapshot")
  |> filter(fn: (r) => r["_field"] == field)
  |> keep(columns: ["_time", "_value", "_field"])
  |> aggregateWindow(every: v.windowPeriod, fn: mean, createEmpty: false)
baseline = series
  |> findRecord(fn: (key) => true, idx: 0)
series
  |> map(fn: (r) => ({ r with _value: (baseline._value - r._value) / baseline._value * 100.0 }))
  |> last()
  |> keep(columns: ["_time", "_value"])
  |> rename(columns: {_value: "GBP/AUD"})
                  ')).addTarget(influxdb.target(query='
field = "aud/usd"
series = from(bucket: "data_public")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "currency")
  |> filter(fn: (r) => r["period"] == "1d")
  |> filter(fn: (r) => r["type"] == "snapshot")
  |> filter(fn: (r) => r["_field"] == field)
  |> keep(columns: ["_time", "_value", "_field"])
  |> aggregateWindow(every: v.windowPeriod, fn: mean, createEmpty: false)
baseline = series
  |> findRecord(fn: (key) => true, idx: 0)
series
  |> map(fn: (r) => ({ r with _value: (baseline._value - r._value) / baseline._value * 100.0 }))
  |> last()
  |> keep(columns: ["_time", "_value"])
  |> rename(columns: {_value: "USD/AUD"})
                  ')).addTarget(influxdb.target(query='
field = "aud/sgd"
series = from(bucket: "data_public")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "currency")
  |> filter(fn: (r) => r["period"] == "1d")
  |> filter(fn: (r) => r["type"] == "snapshot")
  |> filter(fn: (r) => r["_field"] == field)
  |> keep(columns: ["_time", "_value", "_field"])
  |> aggregateWindow(every: v.windowPeriod, fn: mean, createEmpty: false)
baseline = series
  |> findRecord(fn: (key) => true, idx: 0)
series
  |> map(fn: (r) => ({ r with _value: (baseline._value - r._value) / baseline._value * 100.0 }))
  |> last()
  |> keep(columns: ["_time", "_value"])
  |> rename(columns: {_value: "SGD/AUD"})
                  '))
                      { gridPos: { x: 15, y: 2, w: 9, h: 8 } }
                  ,

                  gauge.new(
                        title='GBP/AUD Last End of Day Delta',
                        datasource='InfluxDB_V2',
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
                  ).addTarget(influxdb.target(query='
from(bucket: "data_public")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "currency")
  |> filter(fn: (r) => r["_field"] == "aud/gbp")
  |> filter(fn: (r) => r["period"] == "1d")
  |> filter(fn: (r) => r["type"] == "delta")
  |> sort(columns: ["_time"], desc: false)
  |> last()
  |> keep(columns: ["_value"])
  |> map(fn: (r) => ({ r with _value: -1.0 * r._value }))
                  '))
                      { gridPos: { x: 0, y: 5, w: 5, h: 5 } }
                  ,

                  gauge.new(
                        title='USD/AUD Last End of Day Delta',
                        datasource='InfluxDB_V2',
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
                  ).addTarget(influxdb.target(query='
from(bucket: "data_public")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "currency")
  |> filter(fn: (r) => r["_field"] == "aud/usd")
  |> filter(fn: (r) => r["period"] == "1d")
  |> filter(fn: (r) => r["type"] == "delta")
  |> sort(columns: ["_time"], desc: false)
  |> last()
  |> keep(columns: ["_value"])
  |> map(fn: (r) => ({ r with _value: -1.0 * r._value }))
                  '))
                      { gridPos: { x: 5, y: 5, w: 5, h: 5 } }
                  ,

                  gauge.new(
                        title='SGD/AUD Last End of Day Delta',
                        datasource='InfluxDB_V2',
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
                  ).addTarget(influxdb.target(query='
from(bucket: "data_public")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "currency")
  |> filter(fn: (r) => r["_field"] == "aud/sgd")
  |> filter(fn: (r) => r["period"] == "1d")
  |> filter(fn: (r) => r["type"] == "delta")
  |> sort(columns: ["_time"], desc: false)
  |> last()
  |> keep(columns: ["_value"])
  |> map(fn: (r) => ({ r with _value: -1.0 * r._value }))
                  '))
                      { gridPos: { x: 10, y: 5, w: 5, h: 5 } }
                  ,

                  graph.new(
                        title='CCY/AUD Range End of Day Deltas',
                        datasource='InfluxDB_V2',
                        fill=0,
                        format='',
                        bars=false,
                        lines=true,
                        staircase=false,
                        formatY1='percent',
                        decimals=2,
                        legend_values=true,
                        legend_min=true,
                        legend_max=true,
                        legend_current=false,
                        legend_total=false,
                        legend_avg=true,
                        legend_alignAsTable=true,
                        legend_rightSide=true,
                        legend_sideWidth=400,
                        maxDataPoints=10000
                  ).addTarget(influxdb.target(query='
field = "aud/gbp"
series = from(bucket: "data_public")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "currency")
  |> filter(fn: (r) => r["period"] == "1d")
  |> filter(fn: (r) => r["type"] == "snapshot")
  |> filter(fn: (r) => r["_field"] == field)
  |> keep(columns: ["_time", "_value", "_field"])
  |> aggregateWindow(every: v.windowPeriod, fn: mean, createEmpty: false)
baseline = series
  |> findRecord(fn: (key) => true, idx: 0)
series
  |> map(fn: (r) => ({ r with _value: (baseline._value - r._value) / baseline._value * 100.0 }))
  |> keep(columns: ["_time", "_value"])
  |> rename(columns: {_value: "GBP/AUD"})
                  ')).addTarget(influxdb.target(query='
field = "aud/usd"
series = from(bucket: "data_public")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "currency")
  |> filter(fn: (r) => r["period"] == "1d")
  |> filter(fn: (r) => r["type"] == "snapshot")
  |> filter(fn: (r) => r["_field"] == field)
  |> keep(columns: ["_time", "_value", "_field"])
  |> aggregateWindow(every: v.windowPeriod, fn: mean, createEmpty: false)
baseline = series
  |> findRecord(fn: (key) => true, idx: 0)
series
  |> map(fn: (r) => ({ r with _value: (baseline._value - r._value) / baseline._value * 100.0 }))
  |> keep(columns: ["_time", "_value"])
  |> rename(columns: {_value: "USD/AUD"})
                  ')).addTarget(influxdb.target(query='
field = "aud/sgd"
series = from(bucket: "data_public")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "currency")
  |> filter(fn: (r) => r["period"] == "1d")
  |> filter(fn: (r) => r["type"] == "snapshot")
  |> filter(fn: (r) => r["_field"] == field)
  |> keep(columns: ["_time", "_value", "_field"])
  |> aggregateWindow(every: v.windowPeriod, fn: mean, createEmpty: false)
baseline = series
  |> findRecord(fn: (key) => true, idx: 0)
series
  |> map(fn: (r) => ({ r with _value: (baseline._value - r._value) / baseline._value * 100.0 }))
  |> keep(columns: ["_time", "_value"])
  |> rename(columns: {_value: "SGD/AUD"})
                  '))
                      { gridPos: { x: 0, y: 10, w: 24, h: 12 } }
                  ,

                  graph.new(
                        title='GBP/AUD End of Days',
                        datasource='InfluxDB_V2',
                        fill=0,
                        format='',
                        bars=false,
                        lines=true,
                        staircase=false,
                        formatY1='currencyUSD',
                        decimals=2,
                        legend_values=true,
                        legend_min=true,
                        legend_max=true,
                        legend_current=false,
                        legend_total=false,
                        legend_avg=true,
                        legend_alignAsTable=true,
                        legend_rightSide=true,
                        legend_sideWidth=400,
                        maxDataPoints=10000
                  ).addTarget(influxdb.target(query='
from(bucket: "data_public")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "currency")
  |> filter(fn: (r) => r["period"] == "1d")
  |> filter(fn: (r) => r["type"] == "snapshot")
  |> filter(fn: (r) => r["_field"] == "aud/gbp")
  |> keep(columns: ["_time", "_value"])
  |> sort(columns: ["_time"])
  |> unique(column: "_time")
  |> map(fn: (r) => ({ r with _value: 1.0 / r._value }))
  |> rename(columns: {_value: "GBP/AUD"})
                  ')).addSeriesOverride(
                        { "alias": "/.*AUD.*/", "yaxis": 1 }
                  )
                      { gridPos: { x: 0, y: 22, w: 24, h: 12 } }
                  ,

                  graph.new(
                        title='USD/AUD End of Days',
                        datasource='InfluxDB_V2',
                        fill=0,
                        format='',
                        bars=false,
                        lines=true,
                        staircase=false,
                        formatY1='currencyUSD',
                        decimals=2,
                        legend_values=true,
                        legend_min=true,
                        legend_max=true,
                        legend_current=false,
                        legend_total=false,
                        legend_avg=true,
                        legend_alignAsTable=true,
                        legend_rightSide=true,
                        legend_sideWidth=400,
                        maxDataPoints=10000
                  ).addTarget(influxdb.target(query='
from(bucket: "data_public")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "currency")
  |> filter(fn: (r) => r["period"] == "1d")
  |> filter(fn: (r) => r["type"] == "snapshot")
  |> filter(fn: (r) => r["_field"] == "aud/usd")
  |> keep(columns: ["_time", "_value"])
  |> sort(columns: ["_time"])
  |> unique(column: "_time")
  |> map(fn: (r) => ({ r with _value: 1.0 / r._value }))
  |> rename(columns: {_value: "USD/AUD"})
                  ')).addSeriesOverride(
                        { "alias": "/.*AUD.*/", "yaxis": 1 }
                  )
                      { gridPos: { x: 0, y: 34, w: 24, h: 12 } }
                  ,

                  graph.new(
                        title='SGD/AUD End of Days',
                        datasource='InfluxDB_V2',
                        fill=0,
                        format='',
                        bars=false,
                        lines=true,
                        staircase=false,
                        formatY1='currencyUSD',
                        decimals=2,
                        legend_values=true,
                        legend_min=true,
                        legend_max=true,
                        legend_current=false,
                        legend_total=false,
                        legend_avg=true,
                        legend_alignAsTable=true,
                        legend_rightSide=true,
                        legend_sideWidth=400,
                        maxDataPoints=10000
                  ).addTarget(influxdb.target(query='
from(bucket: "data_public")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "currency")
  |> filter(fn: (r) => r["period"] == "1d")
  |> filter(fn: (r) => r["type"] == "snapshot")
  |> filter(fn: (r) => r["_field"] == "aud/sgd")
  |> keep(columns: ["_time", "_value"])
  |> sort(columns: ["_time"])
  |> unique(column: "_time")
  |> map(fn: (r) => ({ r with _value: 1.0 / r._value }))
  |> rename(columns: {_value: "SGD/AUD"})
                  ')).addSeriesOverride(
                        { "alias": "/.*AUD.*/", "yaxis": 1 }
                  )
                      { gridPos: { x: 0, y: 46, w: 24, h: 12 } }
                  ,

            ],
}
