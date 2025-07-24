// WARNING: This file is written by the build process, any manual edits will be lost!

{

      new(
            style='maximal',
            formFactor='Desktop',
            datasource='InfluxDB_V2',
            bucket='data_public',
            measurement=null,
            maxMilliSecSincePoll=1800000000,
            maxMilliSecSinceUpdate=1800000000,
            filter_data='|> filter(fn: (r) => r["type"] != "metadata")',
            filter_metadata='|> filter(fn: (r) => r["type"] == "metadata")',
            filter_metadata_delta='|> filter(fn: (r) => r["_field"] == "data_delta_rows") |> filter(fn: (r) => r["type"] == "metadata") |> filter(fn: (r) => r["_value"] > 0)',
            simpleErrors=true,
      )::

            local grafana = import 'grafonnet/grafana.libsonnet';
            local dashboard = grafana.dashboard;
            local text = grafana.text;
            local stat = grafana.statPanel;
            local graph = grafana.graphPanel;
            local table = grafana.tablePanel;
            local gauge = grafana.gaugePanel;
            local bar = grafana.barGaugePanel;
            local influxdb = grafana.influxdb;

            [

                  text.new(
                        title='Dashboards',
                        span=null,
                        mode='html',
                        content='
<p style="text-align: center">
  <a href="/">All</a></li>
    &nbsp;&nbsp;|&nbsp;&nbsp;
  <a href="/d/home-' + std.asciiLower(formFactor) + '/home">' + formFactor + '</a></li>
</p>
                        ',
                  )
                      { gridPos: { x: 0, y: 0, w: (if style == 'maximal' then 2 else (if style == 'medial' then 6 else 24)), h: 2 } }
                  ,
           ]

           + (if style == 'maximal' || style == 'medial' || style == 'minimal' then [
                  stat.new(
                        title='Time Since Update',
                        datasource=datasource,
                        fields='duration',
                        decimals=0,
                        unit='dtdurationms',
                        colorMode='value',
                        graphMode='none',
                        justifyMode='auto',
                        thresholdsMode='absolute',
                        repeatDirection='h',
                        pluginVersion='7',
                  ).addThreshold(
                        { color: 'red', value: '' }
                  ).addThreshold(
                        { color: 'green', value: 0 }
                  ).addThreshold(
                        { color: 'yellow', value: maxMilliSecSinceUpdate }
                  ).addThreshold(
                        { color: 'red', value: maxMilliSecSinceUpdate }
                  ).addTarget(influxdb.target(query='
from(bucket: "' + bucket + '")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "' + measurement + '")
  ' + filter_metadata_delta + '
  |> sort(columns: ["_time"], desc: false)
  |> last()
  |> keep(columns: ["_time"])
  |> set(key: "_value", value: "")
  |> group()
  |> last()
  |> map(fn: (r) => ({ r with duration: int(v: uint(v: now()) - uint(v: r._time)) / 1000000 }))
  |> keep(columns: ["duration"])
                  '))
                      { gridPos: { x: (if style == 'maximal' then 4 else (if style == 'medial' then 6 else 0)), y: 0, w: (if style == 'maximal' then 2 else (if style == 'medial' then 6 else 24)), h: 2 } }
                  ,
           ] else [])

           + (if style == 'maximal' then [
                  stat.new(
                        title='Last Updated',
                        datasource=datasource,
                        fields='_time',
                        decimals=0,
                        unit='',
                        colorMode='value',
                        graphMode='none',
                        justifyMode='auto',
                        thresholdsMode='absolute',
                        repeatDirection='h',
                        pluginVersion='7',
                  ).addThreshold(
                        { color: 'red', value: 0 }
                  ).addThreshold(
                        { color: 'yellow', value: 0 }
                  ).addThreshold(
                        { color: 'green', value: 0 }
                  ).addTarget(influxdb.target(query='
from(bucket: "' + bucket + '")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "' + measurement + '")
  ' + filter_metadata_delta + '
  |> sort(columns: ["_time"], desc: false)
  |> last()
  |> keep(columns: ["_time"])
  |> set(key: "_value", value: "")
  |> group()
  |> last()
  |> keep(columns: ["_time"])
                  '))
                      { gridPos: { x: 6, y: 0, w: 2, h: 2 } }
                  ,
           ] else [])

           + (if style == 'maximal' then [
                  stat.new(
                        title='Time Since Poll',
                        datasource=datasource,
                        fields='duration',
                        decimals=0,
                        unit='dtdurationms',
                        colorMode='value',
                        graphMode='none',
                        justifyMode='auto',
                        thresholdsMode='absolute',
                        repeatDirection='h',
                        pluginVersion='7',
                  ).addThreshold(
                        { color: 'red', value: '' }
                  ).addThreshold(
                        { color: 'green', value: 0 }
                  ).addThreshold(
                        { color: 'yellow', value: maxMilliSecSincePoll }
                  ).addThreshold(
                        { color: 'red', value: maxMilliSecSincePoll }
                  ).addTarget(influxdb.target(query='
from(bucket: "' + bucket + '")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "' + measurement + '")
  ' + filter_metadata + '
  |> last()
  |> keep(columns: ["_time"])
  |> set(key: "_value", value: "")
  |> group()
  |> last()
  |> map(fn: (r) => ({ r with duration: int(v: uint(v: now()) - uint(v: r._time)) / 1000000 }))
  |> keep(columns: ["duration"])
                  '))
                      { gridPos: { x: 2, y: 0, w: 2, h: 2 } }
                  ,
           ] else [])

           + (if style == 'maximal' then [
                  stat.new(
                        title='Update Metrics',
                        datasource=datasource,
                        fields='_value',
                        decimals=0,
                        unit='',
                        colorMode='value',
                        graphMode='none',
                        justifyMode='auto',
                        thresholdsMode='absolute',
                        repeatDirection='h',
                        pluginVersion='7',
                  ).addThreshold(
                        { color: 'red', value: 0 }
                  ).addThreshold(
                        { color: 'yellow', value: 0 }
                  ).addThreshold(
                        { color: 'green', value: 0 }
                  ).addTarget(influxdb.target(query='
updated = from(bucket: "' + bucket + '")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "' + measurement + '")
  ' + filter_data + '
  |> last()
  |> keep(columns: ["_time"])
  |> set(key: "_value", value: "")
  |> group()
  |> last()
  |> keep(columns: ["_time"])
  |> findRecord(fn: (key) => true, idx: 0)
from(bucket: "' + bucket + '")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "' + measurement + '")
  ' + filter_data + '
  |> filter(fn: (r) => r["_time"] == updated._time)
  |> last()
  |> keep(columns: ["_time"])
  |> set(key: "_value", value: "")
  |> group()
  |> count()
                  '))
                      { gridPos: { x: 8, y: 0, w: 2, h: 2 } }
                  ,
           ] else [])

           + (if style == 'maximal' then [
                  stat.new(
                        title='Update Points',
                        datasource=datasource,
                        fields='_value',
                        decimals=0,
                        unit='',
                        colorMode='value',
                        graphMode='none',
                        justifyMode='auto',
                        thresholdsMode='absolute',
                        repeatDirection='h',
                        pluginVersion='7',
                  ).addThreshold(
                        { color: 'red', value: 0 }
                  ).addThreshold(
                        { color: 'yellow', value: 0 }
                  ).addThreshold(
                        { color: 'green', value: 0 }
                  ).addTarget(influxdb.target(query='
updated = from(bucket: "' + bucket + '")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "' + measurement + '")
  ' + filter_data + '
  |> last()
  |> keep(columns: ["_time"])
  |> set(key: "_value", value: "")
  |> group()
  |> last()
  |> keep(columns: ["_time"])
  |> findRecord(fn: (key) => true, idx: 0)
from(bucket: "' + bucket + '")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "' + measurement + '")
  ' + filter_data + '
  |> filter(fn: (r) => r["_time"] == updated._time)
  |> keep(columns: ["_time"])
  |> set(key: "_value", value: "")
  |> group()
  |> count()
                  '))
                      { gridPos: { x: 10, y: 0, w: 2, h: 2 } }
                  ,
           ] else [])

           + (if style == 'maximal' then [
                  stat.new(
                        title='Total Metrics',
                        datasource=datasource,
                        fields='_value',
                        decimals=0,
                        unit='locale',
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
                  ).addTarget(influxdb.target(query='
from(bucket: "' + bucket + '")
  |> range(start: -100y, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "' + measurement + '")
  ' + filter_data + '
  |> last()
  |> keep(columns: ["_time"])
  |> set(key: "_value", value: "")
  |> group()
  |> count()
  |> keep(columns: ["_value"])
                  '))
                      { gridPos: { x: 12, y: 0, w: 2, h: 2 } }
                  ,
           ] else [])

           + (if style == 'maximal' || style == 'medial' then [
                  stat.new(
                        title='Total Points',
                        datasource=datasource,
                        fields='_value',
                        decimals=0,
                        unit='locale',
                        colorMode='value',
                        graphMode='none',
                        justifyMode='auto',
                        thresholdsMode='absolute',
                        repeatDirection='h',
                        pluginVersion='7',
                  ).addThreshold(
                        { color: 'red', value: 0 }
                  ).addThreshold(
                        { color: 'yellow', value: 50 }
                  ).addThreshold(
                        { color: 'green', value: 100 }
                  ).addTarget(influxdb.target(query='
from(bucket: "' + bucket + '")
  |> range(start: -100y, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "' + measurement + '")
  ' + filter_data + '
  |> group()
  |> count()
  |> keep(columns: ["_value"])
                  '))
                      { gridPos: { x: (if style == 'maximal' then 14 else 12), y: 0, w: (if style == 'maximal' then 2 else 6), h: 2 } }
                  ,
           ] else [])

           + (if style == 'maximal' then [
                  stat.new(
                        title='Source Errors',
                        datasource=datasource,
                        fields='_value',
                        decimals=0,
                        unit='',
                        colorMode='value',
                        graphMode='none',
                        justifyMode='auto',
                        thresholdsMode='absolute',
                        repeatDirection='h',
                        pluginVersion='7',
                  ).addThreshold(
                        { color: 'red', value: '' }
                  ).addThreshold(
                        { color: 'green', value: 0 }
                  ).addThreshold(
                        { color: 'yellow', value: 1 }
                  ).addThreshold(
                        { color: 'red', value: 1 }
                  ).addTarget(influxdb.target(query=(if simpleErrors then '
from(bucket: "' + bucket + '")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "' + measurement + '")
  |> keep(columns: ["_time"])
  |> set(key: "_value", value: "")
  |> group()
  |> count()
  |> keep(columns: ["_value"])
  |> map(fn: (r) => ({ r with _value: if r._value > 0 then 0 else 1 }))
  |> filter(fn: (r) => r["_value"] == 0)
  |> last()
  |> keep(columns: ["_value"])
                  ' else '
from(bucket: "' + bucket + '")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "' + measurement + '")
  |> filter(fn: (r) => r["_field"] == "sources_errored")
  |> last()
  |> keep(columns: ["_value"])
                  ')))
                      { gridPos: { x: 16, y: 0, w: 2, h: 2 } }
                  ,
           ] else [])

           + (if style == 'maximal' then [
                  stat.new(
                        title='File Errors',
                        datasource=datasource,
                        fields='_value',
                        decimals=0,
                        unit='',
                        colorMode='value',
                        graphMode='none',
                        justifyMode='auto',
                        thresholdsMode='absolute',
                        repeatDirection='h',
                        pluginVersion='7',
                  ).addThreshold(
                        { color: 'red', value: '' }
                  ).addThreshold(
                        { color: 'green', value: 0 }
                  ).addThreshold(
                        { color: 'yellow', value: 1 }
                  ).addThreshold(
                        { color: 'red', value: 1 }
                  ).addTarget(influxdb.target(query=(if simpleErrors then '
from(bucket: "' + bucket + '")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "' + measurement + '")
  |> keep(columns: ["_time"])
  |> set(key: "_value", value: "")
  |> group()
  |> count()
  |> keep(columns: ["_value"])
  |> map(fn: (r) => ({ r with _value: if r._value > 0 then 0 else 1 }))
  |> filter(fn: (r) => r["_value"] == 0)
  |> last()
  |> keep(columns: ["_value"])
                  ' else '
from(bucket: "' + bucket + '")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "' + measurement + '")
  |> filter(fn: (r) => r["_field"] == "files_errored")
  |> last()
  |> keep(columns: ["_value"])
                  ')))
                      { gridPos: { x: 18, y: 0, w: 2, h: 2 } }
                  ,
           ] else [])

           + (if style == 'maximal' then [
                  stat.new(
                        title='Data Errors',
                        datasource=datasource,
                        fields='_value',
                        decimals=0,
                        unit='',
                        colorMode='value',
                        graphMode='none',
                        justifyMode='auto',
                        thresholdsMode='absolute',
                        repeatDirection='h',
                        pluginVersion='7',
                  ).addThreshold(
                        { color: 'red', value: '' }
                  ).addThreshold(
                        { color: 'green', value: 0 }
                  ).addThreshold(
                        { color: 'yellow', value: 1 }
                  ).addThreshold(
                        { color: 'red', value: 1 }
                  ).addTarget(influxdb.target(query=(if simpleErrors then '
from(bucket: "' + bucket + '")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "' + measurement + '")
  |> keep(columns: ["_time"])
  |> set(key: "_value", value: "")
  |> group()
  |> count()
  |> keep(columns: ["_value"])
  |> map(fn: (r) => ({ r with _value: if r._value > 0 then 0 else 1 }))
  |> filter(fn: (r) => r["_value"] == 0)
  |> last()
  |> keep(columns: ["_value"])
                  ' else '
from(bucket: "' + bucket + '")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "' + measurement + '")
  |> filter(fn: (r) => r["_field"] == "data_errored")
  |> last()
  |> keep(columns: ["_value"])
                  ')))
                      { gridPos: { x: 20, y: 0, w: 2, h: 2 } }
                  ,
           ] else [])

           + (if style == 'maximal' then [
                  stat.new(
                        title='Egress Errors',
                        datasource=datasource,
                        fields='_value',
                        decimals=0,
                        unit='',
                        colorMode='value',
                        graphMode='none',
                        justifyMode='auto',
                        thresholdsMode='absolute',
                        repeatDirection='h',
                        pluginVersion='7',
                  ).addThreshold(
                        { color: 'red', value: '' }
                  ).addThreshold(
                        { color: 'green', value: 0 }
                  ).addThreshold(
                        { color: 'yellow', value: 1 }
                  ).addThreshold(
                        { color: 'red', value: 1 }
                  ).addTarget(influxdb.target(query=(if simpleErrors then '
from(bucket: "' + bucket + '")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "' + measurement + '")
  |> keep(columns: ["_time"])
  |> set(key: "_value", value: "")
  |> group()
  |> count()
  |> keep(columns: ["_value"])
  |> map(fn: (r) => ({ r with _value: if r._value > 0 then 0 else 1 }))
  |> filter(fn: (r) => r["_value"] == 0)
  |> last()
  |> keep(columns: ["_value"])
                  ' else '
from(bucket: "' + bucket + '")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "' + measurement + '")
  |> filter(fn: (r) => r["_field"] == "egress_errored")
  |> last()
  |> keep(columns: ["_value"])
                  ')))
                      { gridPos: { x: 22, y: 0, w: 2, h: 2 } }
                  ,
           ] else [])

           + (if style == 'medial' || style == 'minimal' then [
                  stat.new(
                        title='Update Errors',
                        datasource=datasource,
                        fields='_value',
                        decimals=0,
                        unit='',
                        colorMode='value',
                        graphMode='none',
                        justifyMode='auto',
                        thresholdsMode='absolute',
                        repeatDirection='h',
                        pluginVersion='7',
                  ).addThreshold(
                        { color: 'red', value: '' }
                  ).addThreshold(
                        { color: 'green', value: 0 }
                  ).addThreshold(
                        { color: 'yellow', value: 1 }
                  ).addThreshold(
                        { color: 'red', value: 1 }
                  ).addTarget(influxdb.target(query=(if simpleErrors then '
from(bucket: "' + bucket + '")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "' + measurement + '")
  |> keep(columns: ["_time"])
  |> set(key: "_value", value: "")
  |> group()
  |> count()
  |> keep(columns: ["_value"])
  |> map(fn: (r) => ({ r with _value: if r._value > 0 then 0 else 1 }))
  |> filter(fn: (r) => r["_value"] == 0)
  |> last()
  |> keep(columns: ["_value"])
                  ' else '
from(bucket: "' + bucket + '")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "' + measurement + '")
  |> filter(fn: (r) => r["_field"] == "sources_errored" or r["_field"] == "files_errored" or r["_field"] == "data_errored" or r["_field"] == "egress_errored")
  |> last()
  |> group()
  |> sum()
                  ')))
                      { gridPos: { x: (if style == 'medial' then 18 else 0), y: (if style == 'medial' then 0 else 2), w: (if style == 'medial' then 6 else 24), h: 2 } }
                  ,
           ] else [])

}
