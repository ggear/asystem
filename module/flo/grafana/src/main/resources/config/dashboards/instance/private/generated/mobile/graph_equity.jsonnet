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
                style='minimal',
                formFactor='Mobile',
                bucket='data_private',
                measurement='equity',
                maxMilliSecSinceUpdate='259200000',
                simpleErrors=false,
            ) +

            [

                  stat.new(
                        title='Holdings Daily Delta',
                        datasource='InfluxDB_V2',
                        unit='currencyUSD',
                        decimals=2,
                        reducerFunction='last',
                        colorMode='value',
                        graphMode='none',
                        justifyMode='auto',
                        thresholdsMode='absolute',
                        repeatDirection='h',
                        pluginVersion='7',
                  ).addThreshold(
                        { color: 'red', value: -9999999 }
                  ).addThreshold(
                        { color: 'yellow', value: -500 }
                  ).addThreshold(
                        { color: 'green', value: 500 }
                  ).addTarget(influxdb.target(query='
from(bucket: "data_private")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "equity")
  |> filter(fn: (r) => r["_field"] == "holdings")
  |> filter(fn: (r) => r["period"] == "1d")
  |> filter(fn: (r) => r["type"] == "price-change-spot")
  |> sort(columns: ["_time"], desc: false)
  |> last()
  |> keep(columns: ["_value"])
                  '))
                      { gridPos: { x: 0, y: 2, w: 24, h: 3 } }
                  ,

                  stat.new(
                        title='Holdings Monthly Delta',
                        datasource='InfluxDB_V2',
                        unit='currencyUSD',
                        decimals=2,
                        reducerFunction='last',
                        colorMode='value',
                        graphMode='none',
                        justifyMode='auto',
                        thresholdsMode='absolute',
                        repeatDirection='h',
                        pluginVersion='7',
                  ).addThreshold(
                        { color: 'red', value: -9999999 }
                  ).addThreshold(
                        { color: 'yellow', value: -500 }
                  ).addThreshold(
                        { color: 'green', value: 500 }
                  ).addTarget(influxdb.target(query='
from(bucket: "data_private")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "equity")
  |> filter(fn: (r) => r["_field"] == "holdings")
  |> filter(fn: (r) => r["period"] == "30d")
  |> filter(fn: (r) => r["type"] == "price-change-spot")
  |> sort(columns: ["_time"], desc: false)
  |> last()
  |> keep(columns: ["_value"])
                  '))
                      { gridPos: { x: 0, y: 10, w: 24, h: 3 } }
                  ,

                  stat.new(
                        title='Holdings Quarterly Delta',
                        datasource='InfluxDB_V2',
                        unit='currencyUSD',
                        decimals=2,
                        reducerFunction='last',
                        colorMode='value',
                        graphMode='none',
                        justifyMode='auto',
                        thresholdsMode='absolute',
                        repeatDirection='h',
                        pluginVersion='7',
                  ).addThreshold(
                        { color: 'red', value: -9999999 }
                  ).addThreshold(
                        { color: 'yellow', value: -500 }
                  ).addThreshold(
                        { color: 'green', value: 500 }
                  ).addTarget(influxdb.target(query='
from(bucket: "data_private")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "equity")
  |> filter(fn: (r) => r["_field"] == "holdings")
  |> filter(fn: (r) => r["period"] == "90d")
  |> filter(fn: (r) => r["type"] == "price-change-spot")
  |> sort(columns: ["_time"], desc: false)
  |> last()
  |> keep(columns: ["_value"])
                  '))
                      { gridPos: { x: 0, y: 18, w: 24, h: 3 } }
                  ,

                  bar.new(
                        title='Portfolio Range Performance',
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
import "strings"
field = "watch"
series = from(bucket: "data_private")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "equity")
  |> filter(fn: (r) => r["_field"] == field)
  |> filter(fn: (r) => r["period"] == "1d")
  |> filter(fn: (r) => r["type"] == "price-close-spot")
  |> keep(columns: ["_time", "_value", "_field"])
  |> aggregateWindow(every: v.windowPeriod, fn: mean, createEmpty: false)
baseline = series
  |> findRecord(fn: (key) => true, idx: 0)
series
  |> map(fn: (r) => ({ r with _value: (r._value - baseline._value) / baseline._value * 100.0 }))
  |> last()
  |> keep(columns: ["_time", "_value"])
  |> rename(columns: { _value: strings.title(v: field) })
                  ')).addTarget(influxdb.target(query='
import "strings"
field = "holdings"
series = from(bucket: "data_private")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "equity")
  |> filter(fn: (r) => r["_field"] == field)
  |> filter(fn: (r) => r["period"] == "1d")
  |> filter(fn: (r) => r["type"] == "price-close-spot")
  |> keep(columns: ["_time", "_value", "_field"])
  |> aggregateWindow(every: v.windowPeriod, fn: mean, createEmpty: false)
baseline = series
  |> findRecord(fn: (key) => true, idx: 0)
series
  |> map(fn: (r) => ({ r with _value: (r._value - baseline._value) / baseline._value * 100.0 }))
  |> last()
  |> keep(columns: ["_time", "_value"])
  |> rename(columns: { _value: strings.title(v: field) })
                  ')).addTarget(influxdb.target(query='
import "strings"
field = "baseline"
series = from(bucket: "data_private")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "equity")
  |> filter(fn: (r) => r["_field"] == field)
  |> filter(fn: (r) => r["period"] == "1d")
  |> filter(fn: (r) => r["type"] == "price-close-spot")
  |> keep(columns: ["_time", "_value", "_field"])
  |> aggregateWindow(every: v.windowPeriod, fn: mean, createEmpty: false)
baseline = series
  |> findRecord(fn: (key) => true, idx: 0)
series
  |> map(fn: (r) => ({ r with _value: (r._value - baseline._value) / baseline._value * 100.0 }))
  |> last()
  |> keep(columns: ["_time", "_value"])
  |> rename(columns: { _value: strings.title(v: field) })
                  '))
                      { gridPos: { x: 0, y: 26, w: 24, h: 8 } }
                  ,

                  gauge.new(
                        title='Holdings Daily Performance',
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
from(bucket: "data_private")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "equity")
  |> filter(fn: (r) => r["_field"] == "holdings")
  |> filter(fn: (r) => r["period"] == "1d")
  |> filter(fn: (r) => r["type"] == "price-change-percentage-spot")
  |> sort(columns: ["_time"], desc: false)
  |> last()
  |> keep(columns: ["_value"])
                  '))
                      { gridPos: { x: 0, y: 5, w: 24, h: 5 } }
                  ,

                  gauge.new(
                        title='Holdings Monthly Performance',
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
from(bucket: "data_private")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "equity")
  |> filter(fn: (r) => r["_field"] == "holdings")
  |> filter(fn: (r) => r["period"] == "30d")
  |> filter(fn: (r) => r["type"] == "price-change-percentage-spot")
  |> sort(columns: ["_time"], desc: false)
  |> last()
  |> keep(columns: ["_value"])
                  '))
                      { gridPos: { x: 0, y: 13, w: 24, h: 5 } }
                  ,

                  gauge.new(
                        title='Holdings Quarterly Performance',
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
from(bucket: "data_private")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "equity")
  |> filter(fn: (r) => r["_field"] == "holdings")
  |> filter(fn: (r) => r["period"] == "90d")
  |> filter(fn: (r) => r["type"] == "price-change-percentage-spot")
  |> sort(columns: ["_time"], desc: false)
  |> last()
  |> keep(columns: ["_value"])
                  '))
                      { gridPos: { x: 0, y: 21, w: 24, h: 5 } }
                  ,

                  graph.new(
                        title='Holdings Performance',
                        datasource='InfluxDB_V2',
                        fill=0,
                        format='',
                        bars=false,
                        lines=true,
                        staircase=false,
                        formatY1='currencyUSD',
                        formatY2='currencyUSD',
                        decimalsY1=0,
                        decimals=2,
                        maxDataPoints=10000
                  ).addTarget(influxdb.target(query='
from(bucket: "data_private")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "equity")
  |> filter(fn: (r) => r["_field"] == "holdings")
  |> filter(fn: (r) => r["period"] == "1d")
  |> filter(fn: (r) => r["type"] == "price-close-spot")
  |> keep(columns: ["_time", "_value"])
  |> rename(columns: { _value: "Daily Value"})
                  ')).addTarget(influxdb.target(query='
import "strings"
bin=1mo
timeRangeStart=v.timeRangeStart
// timeRangeStart=-5m
// timeRangeStart=now()
// timeRangeStart="2021-12-04T02:55:42.581000000Z"
from(bucket: "data_private")
  // |> range(start: time(v: if strings.hasPrefix(v: string(v: timeRangeStart), prefix: "-" ) then string(v: time(v: int(v: now()) + int(v: timeRangeStart) - int(v: bin))) else string(v: time(v: int(v: time(v: timeRangeStart)) - int(v: bin)))), stop: v.timeRangeStop)
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "equity")
  |> filter(fn: (r) => r["_field"] == "holdings")
  |> filter(fn: (r) => r["period"] == "30d")
  |> filter(fn: (r) => r["type"] == "price-change-spot")
  // |> aggregateWindow(every:  bin, fn: last)
  |> keep(columns: ["_time", "_value"])
  |> rename(columns: { _value: "30 Day Delta"})
                  ')).addSeriesOverride(
                        { "alias": "/.*Daily.*/", "steppedLine": false, "bars": false, "lines" :true, "color": "#ffd11a", "yaxis": 1 }
                  ).addSeriesOverride(
                        { "alias": "/.*Day.*/", "steppedLine": false, "bars": true, "lines" :false, "color": "#a6de9f5e", "yaxis": 2 }
                  )
                      { gridPos: { x: 0, y: 34, w: 24, h: 7 } }
                  ,

                  graph.new(
                        title='Portfolio Performance',
                        datasource='InfluxDB_V2',
                        fill=0,
                        format='',
                        bars=false,
                        lines=true,
                        staircase=false,
                        formatY1='percent',
                        decimalsY1=1,
                        decimals=0,
                        maxDataPoints=10000
                  ).addTarget(influxdb.target(query='
import "strings"
field = "watch"
series = from(bucket: "data_private")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "equity")
  |> filter(fn: (r) => r["_field"] == field)
  |> filter(fn: (r) => r["period"] == "1d")
  |> filter(fn: (r) => r["type"] == "price-close-spot")
  |> keep(columns: ["_time", "_value", "_field"])
  |> aggregateWindow(every: v.windowPeriod, fn: mean, createEmpty: false)
baseline = series
  |> findRecord(fn: (key) => true, idx: 0)
series
  |> map(fn: (r) => ({ r with _value: (r._value - baseline._value) / baseline._value * 100.0 }))
  |> keep(columns: ["_time", "_value"])
  |> rename(columns: { _value: strings.title(v: field) })
                  ')).addTarget(influxdb.target(query='
import "strings"
field = "holdings"
series = from(bucket: "data_private")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "equity")
  |> filter(fn: (r) => r["_field"] == field)
  |> filter(fn: (r) => r["period"] == "1d")
  |> filter(fn: (r) => r["type"] == "price-close-spot")
  |> keep(columns: ["_time", "_value", "_field"])
  |> aggregateWindow(every: v.windowPeriod, fn: mean, createEmpty: false)
baseline = series
  |> findRecord(fn: (key) => true, idx: 0)
series
  |> map(fn: (r) => ({ r with _value: (r._value - baseline._value) / baseline._value * 100.0 }))
  |> keep(columns: ["_time", "_value"])
  |> rename(columns: { _value: strings.title(v: field) })
                  ')).addTarget(influxdb.target(query='
import "strings"
field = "baseline"
series = from(bucket: "data_private")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "equity")
  |> filter(fn: (r) => r["_field"] == field)
  |> filter(fn: (r) => r["period"] == "1d")
  |> filter(fn: (r) => r["type"] == "price-close-spot")
  |> keep(columns: ["_time", "_value", "_field"])
  |> aggregateWindow(every: v.windowPeriod, fn: mean, createEmpty: false)
baseline = series
  |> findRecord(fn: (key) => true, idx: 0)
series
  |> map(fn: (r) => ({ r with _value: (r._value - baseline._value) / baseline._value * 100.0 }))
  |> keep(columns: ["_time", "_value"])
  |> rename(columns: { _value: strings.title(v: field) })
                  '))
                      { gridPos: { x: 0, y: 41, w: 24, h: 7 } }
                  ,

                  graph.new(
                        title='Equities Performance',
                        datasource='InfluxDB_V2',
                        fill=0,
                        format='',
                        bars=false,
                        lines=true,
                        staircase=false,
                        formatY1='percent',
                        decimalsY1=1,
                        decimals=0,
                        maxDataPoints=10000
                  ).addTarget(influxdb.target(query='
import "strings"
field = "clne"
series = from(bucket: "data_private")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "equity" and r["_field"] == field and r["period"] == "1d" and r["type"] == "price-close-spot")
  |> keep(columns: ["_time", "_value", "_field"])
  |> aggregateWindow(every: v.windowPeriod, fn: mean, createEmpty: false)
baseline = series
  |> findRecord(fn: (key) => true, idx: 0)
series
  |> map(fn: (r) => ({ r with _value: (r._value - baseline._value) / baseline._value * 100.0 }))
  |> keep(columns: ["_time", "_value"])
  |> rename(columns: { _value: strings.toUpper(v: field) })
                  ')).addTarget(influxdb.target(query='
import "strings"
field = "erth"
series = from(bucket: "data_private")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "equity" and r["_field"] == field and r["period"] == "1d" and r["type"] == "price-close-spot")
  |> keep(columns: ["_time", "_value", "_field"])
  |> aggregateWindow(every: v.windowPeriod, fn: mean, createEmpty: false)
baseline = series
  |> findRecord(fn: (key) => true, idx: 0)
series
  |> map(fn: (r) => ({ r with _value: (r._value - baseline._value) / baseline._value * 100.0 }))
  |> keep(columns: ["_time", "_value"])
  |> rename(columns: { _value: strings.toUpper(v: field) })
                  ')).addTarget(influxdb.target(query='
import "strings"
field = "gold"
series = from(bucket: "data_private")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "equity" and r["_field"] == field and r["period"] == "1d" and r["type"] == "price-close-spot")
  |> keep(columns: ["_time", "_value", "_field"])
  |> aggregateWindow(every: v.windowPeriod, fn: mean, createEmpty: false)
baseline = series
  |> findRecord(fn: (key) => true, idx: 0)
series
  |> map(fn: (r) => ({ r with _value: (r._value - baseline._value) / baseline._value * 100.0 }))
  |> keep(columns: ["_time", "_value"])
  |> rename(columns: { _value: strings.toUpper(v: field) })
                  ')).addTarget(influxdb.target(query='
import "strings"
field = "iaf"
series = from(bucket: "data_private")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "equity" and r["_field"] == field and r["period"] == "1d" and r["type"] == "price-close-spot")
  |> keep(columns: ["_time", "_value", "_field"])
  |> aggregateWindow(every: v.windowPeriod, fn: mean, createEmpty: false)
baseline = series
  |> findRecord(fn: (key) => true, idx: 0)
series
  |> map(fn: (r) => ({ r with _value: (r._value - baseline._value) / baseline._value * 100.0 }))
  |> keep(columns: ["_time", "_value"])
  |> rename(columns: { _value: strings.toUpper(v: field) })
                  ')).addTarget(influxdb.target(query='
import "strings"
field = "mck"
series = from(bucket: "data_private")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "equity" and r["_field"] == field and r["period"] == "1d" and r["type"] == "price-close-spot")
  |> keep(columns: ["_time", "_value", "_field"])
  |> aggregateWindow(every: v.windowPeriod, fn: mean, createEmpty: false)
baseline = series
  |> findRecord(fn: (key) => true, idx: 0)
series
  |> map(fn: (r) => ({ r with _value: (r._value - baseline._value) / baseline._value * 100.0 }))
  |> keep(columns: ["_time", "_value"])
  |> rename(columns: { _value: strings.toUpper(v: field) })
                  ')).addTarget(influxdb.target(query='
import "strings"
field = "msg"
series = from(bucket: "data_private")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "equity" and r["_field"] == field and r["period"] == "1d" and r["type"] == "price-close-spot")
  |> keep(columns: ["_time", "_value", "_field"])
  |> aggregateWindow(every: v.windowPeriod, fn: mean, createEmpty: false)
baseline = series
  |> findRecord(fn: (key) => true, idx: 0)
series
  |> map(fn: (r) => ({ r with _value: (r._value - baseline._value) / baseline._value * 100.0 }))
  |> keep(columns: ["_time", "_value"])
  |> rename(columns: { _value: strings.toUpper(v: field) })
                  ')).addTarget(influxdb.target(query='
import "strings"
field = "muk"
series = from(bucket: "data_private")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "equity" and r["_field"] == field and r["period"] == "1d" and r["type"] == "price-close-spot")
  |> keep(columns: ["_time", "_value", "_field"])
  |> aggregateWindow(every: v.windowPeriod, fn: mean, createEmpty: false)
baseline = series
  |> findRecord(fn: (key) => true, idx: 0)
series
  |> map(fn: (r) => ({ r with _value: (r._value - baseline._value) / baseline._value * 100.0 }))
  |> keep(columns: ["_time", "_value"])
  |> rename(columns: { _value: strings.toUpper(v: field) })
                  ')).addTarget(influxdb.target(query='
import "strings"
field = "mus"
series = from(bucket: "data_private")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "equity" and r["_field"] == field and r["period"] == "1d" and r["type"] == "price-close-spot")
  |> keep(columns: ["_time", "_value", "_field"])
  |> aggregateWindow(every: v.windowPeriod, fn: mean, createEmpty: false)
baseline = series
  |> findRecord(fn: (key) => true, idx: 0)
series
  |> map(fn: (r) => ({ r with _value: (r._value - baseline._value) / baseline._value * 100.0 }))
  |> keep(columns: ["_time", "_value"])
  |> rename(columns: { _value: strings.toUpper(v: field) })
                  ')).addTarget(influxdb.target(query='
import "strings"
field = "vae"
series = from(bucket: "data_private")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "equity" and r["_field"] == field and r["period"] == "1d" and r["type"] == "price-close-spot")
  |> keep(columns: ["_time", "_value", "_field"])
  |> aggregateWindow(every: v.windowPeriod, fn: mean, createEmpty: false)
baseline = series
  |> findRecord(fn: (key) => true, idx: 0)
series
  |> map(fn: (r) => ({ r with _value: (r._value - baseline._value) / baseline._value * 100.0 }))
  |> keep(columns: ["_time", "_value"])
  |> rename(columns: { _value: strings.toUpper(v: field) })
                  ')).addTarget(influxdb.target(query='
import "strings"
field = "vas"
series = from(bucket: "data_private")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "equity" and r["_field"] == field and r["period"] == "1d" and r["type"] == "price-close-spot")
  |> keep(columns: ["_time", "_value", "_field"])
  |> aggregateWindow(every: v.windowPeriod, fn: mean, createEmpty: false)
baseline = series
  |> findRecord(fn: (key) => true, idx: 0)
series
  |> map(fn: (r) => ({ r with _value: (r._value - baseline._value) / baseline._value * 100.0 }))
  |> keep(columns: ["_time", "_value"])
  |> rename(columns: { _value: strings.toUpper(v: field) })
                  ')).addTarget(influxdb.target(query='
import "strings"
field = "vdhg"
series = from(bucket: "data_private")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "equity" and r["_field"] == field and r["period"] == "1d" and r["type"] == "price-close-spot")
  |> keep(columns: ["_time", "_value", "_field"])
  |> aggregateWindow(every: v.windowPeriod, fn: mean, createEmpty: false)
baseline = series
  |> findRecord(fn: (key) => true, idx: 0)
series
  |> map(fn: (r) => ({ r with _value: (r._value - baseline._value) / baseline._value * 100.0 }))
  |> keep(columns: ["_time", "_value"])
  |> rename(columns: { _value: strings.toUpper(v: field) })
                  ')).addTarget(influxdb.target(query='
import "strings"
field = "vhy"
series = from(bucket: "data_private")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "equity" and r["_field"] == field and r["period"] == "1d" and r["type"] == "price-close-spot")
  |> keep(columns: ["_time", "_value", "_field"])
  |> aggregateWindow(every: v.windowPeriod, fn: mean, createEmpty: false)
baseline = series
  |> findRecord(fn: (key) => true, idx: 0)
series
  |> map(fn: (r) => ({ r with _value: (r._value - baseline._value) / baseline._value * 100.0 }))
  |> keep(columns: ["_time", "_value"])
  |> rename(columns: { _value: strings.toUpper(v: field) })
                  '))
                      { gridPos: { x: 0, y: 48, w: 24, h: 7 } }
                  ,

                  graph.new(
                        title='Fund Performance',
                        datasource='InfluxDB_V2',
                        fill=0,
                        format='',
                        bars=false,
                        lines=true,
                        staircase=false,
                        formatY1='percent',
                        decimalsY1=1,
                        decimals=0,
                        maxDataPoints=10000
                  ).addTarget(influxdb.target(query='
import "strings"
field = "muk"
type = "spot"
series = from(bucket: "data_private")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "equity" and r["_field"] == field and r["period"] == "1d" and r["type"] == "price-close-" + type)
  |> keep(columns: ["_time", "_value", "_field"])
  |> aggregateWindow(every: v.windowPeriod, fn: mean, createEmpty: false)
baseline = series
  |> findRecord(fn: (key) => true, idx: 0)
series
  |> map(fn: (r) => ({ r with _value: (r._value - baseline._value) / baseline._value * 100.0 }))
  |> keep(columns: ["_time", "_value"])
  |> rename(columns: { _value: strings.toUpper(v: field) + " " + strings.title(v: type)})
                  ')).addTarget(influxdb.target(query='
import "strings"
field = "muk"
type = "base"
series = from(bucket: "data_private")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "equity" and r["_field"] == field and r["period"] == "1d" and r["type"] == "price-close-" + type)
  |> keep(columns: ["_time", "_value", "_field"])
  |> aggregateWindow(every: v.windowPeriod, fn: mean, createEmpty: false)
baseline = series
  |> findRecord(fn: (key) => true, idx: 0)
series
  |> map(fn: (r) => ({ r with _value: (r._value - baseline._value) / baseline._value * 100.0 }))
  |> keep(columns: ["_time", "_value"])
  |> rename(columns: { _value: strings.toUpper(v: field) + " " + strings.title(v: type)})
                  ')).addTarget(influxdb.target(query='
import "strings"
field = "mus"
type = "spot"
series = from(bucket: "data_private")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "equity" and r["_field"] == field and r["period"] == "1d" and r["type"] == "price-close-" + type)
  |> keep(columns: ["_time", "_value", "_field"])
  |> aggregateWindow(every: v.windowPeriod, fn: mean, createEmpty: false)
baseline = series
  |> findRecord(fn: (key) => true, idx: 0)
series
  |> map(fn: (r) => ({ r with _value: (r._value - baseline._value) / baseline._value * 100.0 }))
  |> keep(columns: ["_time", "_value"])
  |> rename(columns: { _value: strings.toUpper(v: field) + " " + strings.title(v: type)})
                  ')).addTarget(influxdb.target(query='
import "strings"
field = "mus"
type = "base"
series = from(bucket: "data_private")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "equity" and r["_field"] == field and r["period"] == "1d" and r["type"] == "price-close-" + type)
  |> keep(columns: ["_time", "_value", "_field"])
  |> aggregateWindow(every: v.windowPeriod, fn: mean, createEmpty: false)
baseline = series
  |> findRecord(fn: (key) => true, idx: 0)
series
  |> map(fn: (r) => ({ r with _value: (r._value - baseline._value) / baseline._value * 100.0 }))
  |> keep(columns: ["_time", "_value"])
  |> rename(columns: { _value: strings.toUpper(v: field) + " " + strings.title(v: type)})
                  ')).addTarget(influxdb.target(query='
import "strings"
field = "msg"
type = "spot"
series = from(bucket: "data_private")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "equity" and r["_field"] == field and r["period"] == "1d" and r["type"] == "price-close-" + type)
  |> keep(columns: ["_time", "_value", "_field"])
  |> aggregateWindow(every: v.windowPeriod, fn: mean, createEmpty: false)
baseline = series
  |> findRecord(fn: (key) => true, idx: 0)
series
  |> map(fn: (r) => ({ r with _value: (r._value - baseline._value) / baseline._value * 100.0 }))
  |> keep(columns: ["_time", "_value"])
  |> rename(columns: { _value: strings.toUpper(v: field) + " " + strings.title(v: type)})
                  ')).addTarget(influxdb.target(query='
import "strings"
field = "msg"
type = "base"
series = from(bucket: "data_private")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "equity" and r["_field"] == field and r["period"] == "1d" and r["type"] == "price-close-" + type)
  |> keep(columns: ["_time", "_value", "_field"])
  |> aggregateWindow(every: v.windowPeriod, fn: mean, createEmpty: false)
baseline = series
  |> findRecord(fn: (key) => true, idx: 0)
series
  |> map(fn: (r) => ({ r with _value: (r._value - baseline._value) / baseline._value * 100.0 }))
  |> keep(columns: ["_time", "_value"])
  |> rename(columns: { _value: strings.toUpper(v: field) + " " + strings.title(v: type)})
                  ')).addTarget(influxdb.target(query='
import "strings"
field = "mck"
type = "spot"
series = from(bucket: "data_private")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "equity" and r["_field"] == field and r["period"] == "1d" and r["type"] == "price-close-" + type)
  |> keep(columns: ["_time", "_value", "_field"])
  |> aggregateWindow(every: v.windowPeriod, fn: mean, createEmpty: false)
baseline = series
  |> findRecord(fn: (key) => true, idx: 0)
series
  |> map(fn: (r) => ({ r with _value: (r._value - baseline._value) / baseline._value * 100.0 }))
  |> keep(columns: ["_time", "_value"])
  |> rename(columns: { _value: strings.toUpper(v: field) + " " + strings.title(v: type)})
                  ')).addTarget(influxdb.target(query='
import "strings"
field = "mck"
type = "base"
series = from(bucket: "data_private")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "equity" and r["_field"] == field and r["period"] == "1d" and r["type"] == "price-close-" + type)
  |> keep(columns: ["_time", "_value", "_field"])
  |> aggregateWindow(every: v.windowPeriod, fn: mean, createEmpty: false)
baseline = series
  |> findRecord(fn: (key) => true, idx: 0)
series
  |> map(fn: (r) => ({ r with _value: (r._value - baseline._value) / baseline._value * 100.0 }))
  |> keep(columns: ["_time", "_value"])
  |> rename(columns: { _value: strings.toUpper(v: field) + " " + strings.title(v: type)})
                  '))
                      { gridPos: { x: 0, y: 48, w: 24, h: 7 } }
                  ,

            ],
}
