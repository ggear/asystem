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
                measurement='interest',
                maxMilliSecSinceUpdate='7776000000',
                simpleErrors=false,
            ) +

            [

                  stat.new(
                        title='Net Rate Last Month Mean',
                        datasource='InfluxDB_V2',
                        unit='percent',
                        decimals=2,
                        reducerFunction='last',
                        colorMode='value',
                        graphMode='none',
                        justifyMode='auto',
                        thresholdsMode='absolute',
                        repeatDirection='h',
                        pluginVersion='7',
                  ).addThreshold(
                        { color: 'red', value: -1 }
                  ).addThreshold(
                        { color: 'yellow', value: 1 }
                  ).addThreshold(
                        { color: 'green', value: 3 }
                  ).addTarget(influxdb.target(query='
from(bucket: "data_public")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "interest")
  |> filter(fn: (r) => r["_field"] == "net")
  |> filter(fn: (r) => r["period"] == "1mo")
  |> last()
  |> keep(columns: ["_value"])
                  '))
                      { gridPos: { x: 0, y: 2, w: 5, h: 3 } }
                  ,

                  stat.new(
                        title='Bank Rate Last Month Mean',
                        datasource='InfluxDB_V2',
                        unit='percent',
                        decimals=2,
                        reducerFunction='last',
                        colorMode='value',
                        graphMode='none',
                        justifyMode='auto',
                        thresholdsMode='absolute',
                        repeatDirection='h',
                        pluginVersion='7',
                  ).addThreshold(
                        { color: 'red', value: -1 }
                  ).addThreshold(
                        { color: 'yellow', value: 1 }
                  ).addThreshold(
                        { color: 'green', value: 3 }
                  ).addTarget(influxdb.target(query='
from(bucket: "data_public")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "interest")
  |> filter(fn: (r) => r["_field"] == "'bank'")
  |> filter(fn: (r) => r["period"] == "1mo")
  |> last()
  |> keep(columns: ["_value"])
                  '))
                      { gridPos: { x: 5, y: 2, w: 5, h: 3 } }
                  ,

                  stat.new(
                        title='Inflation Rate Last Month Mean',
                        datasource='InfluxDB_V2',
                        unit='percent',
                        decimals=2,
                        reducerFunction='last',
                        colorMode='value',
                        graphMode='none',
                        justifyMode='auto',
                        thresholdsMode='absolute',
                        repeatDirection='h',
                        pluginVersion='7',
                  ).addThreshold(
                        { color: 'green', value: -1 }
                  ).addThreshold(
                        { color: 'yellow', value: 1 }
                  ).addThreshold(
                        { color: 'red', value: 3 }
                  ).addTarget(influxdb.target(query='
from(bucket: "data_public")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "interest")
  |> filter(fn: (r) => r["_field"] == "inflation")
  |> filter(fn: (r) => r["period"] == "1mo")
  |> last()
  |> keep(columns: ["_value"])
                  '))
                      { gridPos: { x: 10, y: 2, w: 5, h: 3 } }
                  ,

                  bar.new(
                        title='Interest Rates Range Means',
                        datasource='InfluxDB_V2',
                        unit='percent',
                        min=-1,
                        max=5,
                        thresholds=[
                              { 'color': 'red', 'value': -1 },
                              { 'color': 'yellow', 'value': 1 },
                              { 'color': 'green', 'value': 3 },
                        ],
                  ).addTarget(influxdb.target(query='
from(bucket: "data_public")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "interest")
  |> filter(fn: (r) => r["_field"] == "net")
  |> filter(fn: (r) => r["period"] == "1mo")
  |> keep(columns: ["_time", "_value"])
  |> mean(column: "_value")
  |> rename(fn: (column) => "Net")
                  ')).addTarget(influxdb.target(query='
from(bucket: "data_public")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "interest")
  |> filter(fn: (r) => r["_field"] == "'bank'")
  |> filter(fn: (r) => r["period"] == "1mo")
  |> keep(columns: ["_time", "_value"])
  |> mean(column: "_value")
  |> rename(fn: (column) => "Bank")
                  ')).addTarget(influxdb.target(query='
from(bucket: "data_public")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "interest")
  |> filter(fn: (r) => r["_field"] == "inflation")
  |> filter(fn: (r) => r["period"] == "1mo")
  |> keep(columns: ["_time", "_value"])
  |> mean(column: "_value")
  |> rename(fn: (column) => "Inflation")
                  '))
                      { gridPos: { x: 15, y: 2, w: 9, h: 8 } }
                  ,

                  gauge.new(
                        title='Net Rate 10 Year Mean',
                        datasource='InfluxDB_V2',
                        reducerFunction='last',
                        showThresholdLabels=false,
                        showThresholdMarkers=true,
                        unit='percent',
                        min=-1,
                        max=5,
                        decimals=2,
                        repeatDirection='h',
                        pluginVersion='7',
                  ).addThreshold(
                        { color: 'red', value: -1 }
                  ).addThreshold(
                        { color: 'yellow', value: 1 }
                  ).addThreshold(
                        { color: 'green', value: 3 }
                  ).addTarget(influxdb.target(query='
from(bucket: "data_public")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "interest")
  |> filter(fn: (r) => r["_field"] == "net")
  |> filter(fn: (r) => r["period"] == "10y")
  |> last()
  |> keep(columns: ["_value"])
                  '))
                      { gridPos: { x: 0, y: 5, w: 5, h: 5 } }
                  ,

                  gauge.new(
                        title='Bank Rate 10 Year Mean',
                        datasource='InfluxDB_V2',
                        reducerFunction='last',
                        showThresholdLabels=false,
                        showThresholdMarkers=true,
                        unit='percent',
                        min=-1,
                        max=5,
                        decimals=2,
                        repeatDirection='h',
                        pluginVersion='7',
                  ).addThreshold(
                        { color: 'red', value: -1 }
                  ).addThreshold(
                        { color: 'yellow', value: 1 }
                  ).addThreshold(
                        { color: 'green', value: 3 }
                  ).addTarget(influxdb.target(query='
from(bucket: "data_public")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "interest")
  |> filter(fn: (r) => r["_field"] == "'bank'")
  |> filter(fn: (r) => r["period"] == "10y")
  |> last()
  |> keep(columns: ["_value"])
                  '))
                      { gridPos: { x: 5, y: 5, w: 5, h: 5 } }
                  ,

                  gauge.new(
                        title='Inflation Rate 10 Year Mean',
                        datasource='InfluxDB_V2',
                        reducerFunction='last',
                        showThresholdLabels=false,
                        showThresholdMarkers=true,
                        unit='percent',
                        min=-1,
                        max=5,
                        decimals=2,
                        repeatDirection='h',
                        pluginVersion='7',
                  ).addThreshold(
                        { color: 'green', value: -1 }
                  ).addThreshold(
                        { color: 'yellow', value: 1 }
                  ).addThreshold(
                        { color: 'red', value: 3 }
                  ).addTarget(influxdb.target(query='
from(bucket: "data_public")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "interest")
  |> filter(fn: (r) => r["_field"] == "inflation")
  |> filter(fn: (r) => r["period"] == "10y")
  |> last()
  |> keep(columns: ["_value"])
                  '))
                      { gridPos: { x: 10, y: 5, w: 5, h: 5 } }
                  ,

                  graph.new(
                        title='Interest Rates Monthly Means',
                        datasource='InfluxDB_V2',
                        fill=0,
                        format='',
                        bars=true,
                        lines=false,
                        staircase=false,
                        formatY1='percent',
                        decimals=2,
                  ).addTarget(influxdb.target(query='
from(bucket: "data_public")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "interest")
  |> filter(fn: (r) => r["_field"] == "net")
  |> filter(fn: (r) => r["period"] == "1mo")
  |> keep(columns: ["_time", "_value"])
  |> rename(columns: {_value: "Net"})
                  ')).addTarget(influxdb.target(query='
from(bucket: "data_public")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "interest")
  |> filter(fn: (r) => r["_field"] == "'bank'")
  |> filter(fn: (r) => r["period"] == "1mo")
  |> keep(columns: ["_time", "_value"])
  |> rename(columns: {_value: "Bank"})
                  ')).addTarget(influxdb.target(query='
from(bucket: "data_public")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "interest")
  |> filter(fn: (r) => r["_field"] == "inflation")
  |> filter(fn: (r) => r["period"] == "1mo")
  |> keep(columns: ["_time", "_value"])
  |> rename(columns: {_value: "Inflation"})
                  ')).addSeriesOverride(
                        { "alias": "/.*Bank.*/", "bars": false, "lines": true, "linewidth": 2, "zindex": 3, "yaxis": 1 }
                  ).addSeriesOverride(
                        { "alias": "/.*Inflation.*/", "bars": false, "lines": true, "linewidth": 2, "zindex": 3, "yaxis": 1 }
                  )
                      { gridPos: { x: 0, y: 10, w: 24, h: 12 } }
                  ,

                  graph.new(
                        title='Interest Rates 10 Year Means',
                        datasource='InfluxDB_V2',
                        fill=0,
                        format='',
                        bars=true,
                        lines=false,
                        staircase=false,
                        formatY1='percent',
                        decimals=2,
                  ).addTarget(influxdb.target(query='
from(bucket: "data_public")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "interest")
  |> filter(fn: (r) => r["_field"] == "net")
  |> filter(fn: (r) => r["period"] == "10y")
  |> keep(columns: ["_time", "_value"])
  |> rename(columns: {_value: "Net"})
                  ')).addTarget(influxdb.target(query='
from(bucket: "data_public")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "interest")
  |> filter(fn: (r) => r["_field"] == "'bank'")
  |> filter(fn: (r) => r["period"] == "10y")
  |> keep(columns: ["_time", "_value"])
  |> rename(columns: {_value: "Bank"})
                  ')).addTarget(influxdb.target(query='
from(bucket: "data_public")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "interest")
  |> filter(fn: (r) => r["_field"] == "inflation")
  |> filter(fn: (r) => r["period"] == "10y")
  |> keep(columns: ["_time", "_value"])
  |> rename(columns: {_value: "Inflation"})
                  ')).addSeriesOverride(
                        { "alias": "/.*Bank.*/", "bars": false, "lines": true, "linewidth": 2, "zindex": 3, "yaxis": 1 }
                  ).addSeriesOverride(
                        { "alias": "/.*Inflation.*/", "bars": false, "lines": true, "linewidth": 2, "zindex": 3, "yaxis": 1 }
                  )
                      { gridPos: { x: 0, y: 22, w: 24, h: 12 } }
                  ,

                  graph.new(
                        title='Net Rate N Year Means',
                        datasource='InfluxDB_V2',
                        fill=0,
                        format='',
                        bars=false,
                        lines=true,
                        staircase=false,
                        formatY1='percent',
                        decimals=2,
                  ).addTarget(influxdb.target(query='
from(bucket: "data_public")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "interest")
  |> filter(fn: (r) => r["_field"] == "net")
  |> filter(fn: (r) => r["period"] == "1y")
  |> keep(columns: ["_time", "_value"])
  |> rename(columns: {_value: "1 year"})
                  ')).addTarget(influxdb.target(query='
from(bucket: "data_public")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "interest")
  |> filter(fn: (r) => r["_field"] == "net")
  |> filter(fn: (r) => r["period"] == "5y")
  |> keep(columns: ["_time", "_value"])
  |> rename(columns: {_value: "5 year"})
                  ')).addTarget(influxdb.target(query='
from(bucket: "data_public")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "interest")
  |> filter(fn: (r) => r["_field"] == "net")
  |> filter(fn: (r) => r["period"] == "10y")
  |> keep(columns: ["_time", "_value"])
  |> rename(columns: {_value: "10 year"})
                  '))
                      { gridPos: { x: 0, y: 34, w: 24, h: 12 } }
                  ,

            ],
}
