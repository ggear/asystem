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
                style='maximal',
                formFactor='Desktop',
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
  |> filter(fn: (r) => r["type"] == "price-change-value-spot")
  |> sort(columns: ["_time"], desc: false)
  |> last()
  |> keep(columns: ["_value"])
                  '))
                      { gridPos: { x: 0, y: 2, w: 5, h: 3 } }
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
  |> filter(fn: (r) => r["type"] == "price-change-value-spot")
  |> sort(columns: ["_time"], desc: false)
  |> last()
  |> keep(columns: ["_value"])
                  '))
                      { gridPos: { x: 5, y: 2, w: 5, h: 3 } }
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
  |> filter(fn: (r) => r["type"] == "price-change-value-spot")
  |> sort(columns: ["_time"], desc: false)
  |> last()
  |> keep(columns: ["_value"])
                  '))
                      { gridPos: { x: 10, y: 2, w: 5, h: 3 } }
                  ,

                  bar.new(
                        title='Portfolio Range Deltas',
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
  |> filter(fn: (r) => r["period"] == "1d")
  |> filter(fn: (r) => r["type"] == "price-close-spot")
  |> filter(fn: (r) => r["_field"] == field)
  |> keep(columns: ["_time", "_value", "_field"])
  |> aggregateWindow(every: v.windowPeriod, fn: mean, createEmpty: false)
baseline = series
  |> findRecord(fn: (key) => true, idx: 0)
series
  |> map(fn: (r) => ({ r with _value: (baseline._value - r._value) / baseline._value * 100.0 }))
  |> last()
  |> keep(columns: ["_time", "_value"])
  |> rename(columns: {_value: strings.title(v: field)})
                  ')).addTarget(influxdb.target(query='
import "strings"
field = "holdings"
series = from(bucket: "data_private")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "equity")
  |> filter(fn: (r) => r["period"] == "1d")
  |> filter(fn: (r) => r["type"] == "price-close-spot")
  |> filter(fn: (r) => r["_field"] == field)
  |> keep(columns: ["_time", "_value", "_field"])
  |> aggregateWindow(every: v.windowPeriod, fn: mean, createEmpty: false)
baseline = series
  |> findRecord(fn: (key) => true, idx: 0)
series
  |> map(fn: (r) => ({ r with _value: (baseline._value - r._value) / baseline._value * 100.0 }))
  |> last()
  |> keep(columns: ["_time", "_value"])
  |> rename(columns: {_value: strings.title(v: field)})
                  ')).addTarget(influxdb.target(query='
import "strings"
field = "baseline"
series = from(bucket: "data_private")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "equity")
  |> filter(fn: (r) => r["period"] == "1d")
  |> filter(fn: (r) => r["type"] == "price-close-spot")
  |> filter(fn: (r) => r["_field"] == field)
  |> keep(columns: ["_time", "_value", "_field"])
  |> aggregateWindow(every: v.windowPeriod, fn: mean, createEmpty: false)
baseline = series
  |> findRecord(fn: (key) => true, idx: 0)
series
  |> map(fn: (r) => ({ r with _value: (baseline._value - r._value) / baseline._value * 100.0 }))
  |> last()
  |> keep(columns: ["_time", "_value"])
  |> rename(columns: {_value: strings.title(v: field)})
                  '))
                      { gridPos: { x: 15, y: 2, w: 9, h: 8 } }
                  ,

                  gauge.new(
                        title='Holdings Daily Delta',
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
                      { gridPos: { x: 0, y: 5, w: 5, h: 5 } }
                  ,

                  gauge.new(
                        title='Holdings Monthly Delta',
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
                      { gridPos: { x: 5, y: 5, w: 5, h: 5 } }
                  ,

                  gauge.new(
                        title='Holdings Quarterly Delta',
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
                      { gridPos: { x: 10, y: 5, w: 5, h: 5 } }
                  ,

                  graph.new(
                        title='Holdings Monthly Deltas',
                        datasource='InfluxDB_V2',
                        fill=0,
                        format='',
                        bars=true,
                        lines=false,
                        staircase=false,
                        formatY1='currencyUSD',
                        decimals=2,
                        legend_values=true,
                        legend_min=true,
                        legend_max=true,
                        legend_current=true,
                        legend_total=false,
                        legend_avg=false,
                        legend_alignAsTable=true,
                        legend_rightSide=true,
                        legend_sideWidth=330,
                        maxDataPoints=10000
                  ).addTarget(influxdb.target(query='
from(bucket: "data_private")
  |> range(start: -90d, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "equity")
  |> filter(fn: (r) => r["_field"] == "holdings")
  |> filter(fn: (r) => r["period"] == "30d")
  |> filter(fn: (r) => r["type"] == "price-change-value-spot")
  |> aggregateWindow(every:  1mo, fn: mean)
  |> keep(columns: ["_time", "_value"])
                  '))
                      { gridPos: { x: 0, y: 10, w: 24, h: 12 } }
                  ,

                  graph.new(
                        title='Portfolio Range Deltas',
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
                        legend_current=true,
                        legend_total=false,
                        legend_avg=false,
                        legend_alignAsTable=true,
                        legend_rightSide=true,
                        legend_sideWidth=330,
                        maxDataPoints=10000
                  ).addTarget(influxdb.target(query='
import "strings"
field = "watch"
series = from(bucket: "data_private")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "equity")
  |> filter(fn: (r) => r["period"] == "1d")
  |> filter(fn: (r) => r["type"] == "price-close-spot")
  |> filter(fn: (r) => r["_field"] == field)
  |> keep(columns: ["_time", "_value", "_field"])
  |> aggregateWindow(every: v.windowPeriod, fn: mean, createEmpty: false)
baseline = series
  |> findRecord(fn: (key) => true, idx: 0)
series
  |> map(fn: (r) => ({ r with _value: (baseline._value - r._value) / baseline._value * 100.0 }))
  |> keep(columns: ["_time", "_value"])
  |> rename(columns: {_value: strings.title(v: field)})
                  ')).addTarget(influxdb.target(query='
import "strings"
field = "holdings"
series = from(bucket: "data_private")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "equity")
  |> filter(fn: (r) => r["period"] == "1d")
  |> filter(fn: (r) => r["type"] == "price-close-spot")
  |> filter(fn: (r) => r["_field"] == field)
  |> keep(columns: ["_time", "_value", "_field"])
  |> aggregateWindow(every: v.windowPeriod, fn: mean, createEmpty: false)
baseline = series
  |> findRecord(fn: (key) => true, idx: 0)
series
  |> map(fn: (r) => ({ r with _value: (baseline._value - r._value) / baseline._value * 100.0 }))
  |> keep(columns: ["_time", "_value"])
  |> rename(columns: {_value: strings.title(v: field)})
                  ')).addTarget(influxdb.target(query='
import "strings"
field = "baseline"
series = from(bucket: "data_private")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "equity")
  |> filter(fn: (r) => r["period"] == "1d")
  |> filter(fn: (r) => r["type"] == "price-close-spot")
  |> filter(fn: (r) => r["_field"] == field)
  |> keep(columns: ["_time", "_value", "_field"])
  |> aggregateWindow(every: v.windowPeriod, fn: mean, createEmpty: false)
baseline = series
  |> findRecord(fn: (key) => true, idx: 0)
series
  |> map(fn: (r) => ({ r with _value: (baseline._value - r._value) / baseline._value * 100.0 }))
  |> keep(columns: ["_time", "_value"])
  |> rename(columns: {_value: strings.title(v: field)})
                  '))
                      { gridPos: { x: 0, y: 22, w: 24, h: 12 } }
                  ,

                  graph.new(
                        title='Holdings Value',
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
                        legend_current=true,
                        legend_total=false,
                        legend_avg=false,
                        legend_alignAsTable=true,
                        legend_rightSide=true,
                        legend_sideWidth=330,
                        maxDataPoints=10000
                  ).addTarget(influxdb.target(query='
from(bucket: "data_private")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "equity")
  |> filter(fn: (r) => r["_field"] == "holdings")
  |> filter(fn: (r) => r["period"] == "1d")
  |> filter(fn: (r) => r["type"] == "price-close-spot")
  |> keep(columns: ["_time", "_value"])
                  '))
                      { gridPos: { x: 0, y: 34, w: 24, h: 12 } }
                  ,

            ],
}
