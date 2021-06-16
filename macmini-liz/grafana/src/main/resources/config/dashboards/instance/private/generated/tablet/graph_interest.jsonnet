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
  |> filter(fn: (r) => r["period"] == "1-month")
  |> last()
  |> keep(columns: ["_value"])
                  '))
                      { gridPos: { x: 0, y: 0, w: 5, h: 3 } }
                  ,

                  stat.new(
                        title='Retail Rate Last Month Mean',
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
  |> filter(fn: (r) => r["_field"] == "retail")
  |> filter(fn: (r) => r["period"] == "1-month")
  |> last()
  |> keep(columns: ["_value"])
                  '))
                      { gridPos: { x: 5, y: 0, w: 5, h: 3 } }
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
  |> filter(fn: (r) => r["period"] == "1-month")
  |> last()
  |> keep(columns: ["_value"])
                  '))
                      { gridPos: { x: 10, y: 0, w: 5, h: 3 } }
                  ,

                  bar.new(
                        title='Interest Rate Range Means',
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
  |> filter(fn: (r) => r["period"] == "1-month")
  |> keep(columns: ["_time", "_value"])
  |> mean(column: "_value")
  |> rename(fn: (column) => "Net")
                  ')).addTarget(influxdb.target(query='
from(bucket: "data_public")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "interest")
  |> filter(fn: (r) => r["_field"] == "retail")
  |> filter(fn: (r) => r["period"] == "1-month")
  |> keep(columns: ["_time", "_value"])
  |> mean(column: "_value")
  |> rename(fn: (column) => "Retail")
                  ')).addTarget(influxdb.target(query='
from(bucket: "data_public")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "interest")
  |> filter(fn: (r) => r["_field"] == "inflation")
  |> filter(fn: (r) => r["period"] == "1-month")
  |> keep(columns: ["_time", "_value"])
  |> mean(column: "_value")
  |> rename(fn: (column) => "Inflation")
                  '))
                      { gridPos: { x: 15, y: 0, w: 9, h: 8 } }
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
  |> filter(fn: (r) => r["period"] == "120-month")
  |> last()
  |> keep(columns: ["_value"])
                  '))
                      { gridPos: { x: 0, y: 3, w: 5, h: 5 } }
                  ,

                  gauge.new(
                        title='Retail Rate 10 Year Mean',
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
  |> filter(fn: (r) => r["_field"] == "retail")
  |> filter(fn: (r) => r["period"] == "120-month")
  |> last()
  |> keep(columns: ["_value"])
                  '))
                      { gridPos: { x: 5, y: 3, w: 5, h: 5 } }
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
  |> filter(fn: (r) => r["period"] == "120-month")
  |> last()
  |> keep(columns: ["_value"])
                  '))
                      { gridPos: { x: 10, y: 3, w: 5, h: 5 } }
                  ,

                  graph.new(
                        title='Interest Rate Monthly Means',
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
  |> filter(fn: (r) => r["period"] == "1-month")
  |> keep(columns: ["_time", "_value", "_field"])
                  ')).addTarget(influxdb.target(query='
from(bucket: "data_public")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "interest")
  |> filter(fn: (r) => r["_field"] == "retail")
  |> filter(fn: (r) => r["period"] == "1-month")
  |> keep(columns: ["_time", "_value", "_field"])
                  ')).addTarget(influxdb.target(query='
from(bucket: "data_public")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "interest")
  |> filter(fn: (r) => r["_field"] == "inflation")
  |> filter(fn: (r) => r["period"] == "1-month")
  |> keep(columns: ["_time", "_value", "_field"])
                  ')).addSeriesOverride(
                        { "alias": "/.*retail.*/", "bars": false, "lines": true, "linewidth": 2, "zindex": 3, "yaxis": 1 }
                  ).addSeriesOverride(
                        { "alias": "/.*inflation.*/", "bars": false, "lines": true, "linewidth": 2, "zindex": 3, "yaxis": 1 }
                  )
                      { gridPos: { x: 0, y: 8, w: 24, h: 12 } }
                  ,

                  graph.new(
                        title='Interest Rate 10 Year Means',
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
  |> filter(fn: (r) => r["period"] == "120-month")
  |> keep(columns: ["_time", "_value", "_field"])
                  ')).addTarget(influxdb.target(query='
from(bucket: "data_public")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "interest")
  |> filter(fn: (r) => r["_field"] == "retail")
  |> filter(fn: (r) => r["period"] == "120-month")
  |> keep(columns: ["_time", "_value", "_field"])
                  ')).addTarget(influxdb.target(query='
from(bucket: "data_public")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "interest")
  |> filter(fn: (r) => r["_field"] == "inflation")
  |> filter(fn: (r) => r["period"] == "120-month")
  |> keep(columns: ["_time", "_value", "_field"])
                  ')).addSeriesOverride(
                        { "alias": "/.*retail.*/", "bars": false, "lines": true, "linewidth": 2, "zindex": 3, "yaxis": 1 }
                  ).addSeriesOverride(
                        { "alias": "/.*inflation.*/", "bars": false, "lines": true, "linewidth": 2, "zindex": 3, "yaxis": 1 }
                  )
                      { gridPos: { x: 0, y: 20, w: 24, h: 12 } }
                  ,

                  graph.new(
                        title='Net Rate n-Monthly Means',
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
  |> filter(fn: (r) => r["period"] == "12-month")
  |> keep(columns: ["_time", "_value", "period"])
                  ')).addTarget(influxdb.target(query='
from(bucket: "data_public")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "interest")
  |> filter(fn: (r) => r["_field"] == "net")
  |> filter(fn: (r) => r["period"] == "60-month")
  |> keep(columns: ["_time", "_value", "period"])
                  ')).addTarget(influxdb.target(query='
from(bucket: "data_public")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "interest")
  |> filter(fn: (r) => r["_field"] == "net")
  |> filter(fn: (r) => r["period"] == "120-month")
  |> keep(columns: ["_time", "_value", "period"])
                  ')).addTarget(influxdb.target(query='
from(bucket: "data_public")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "interest")
  |> filter(fn: (r) => r["_field"] == "net")
  |> filter(fn: (r) => r["period"] == "240-month")
  |> keep(columns: ["_time", "_value", "period"])
                  '))
                      { gridPos: { x: 0, y: 32, w: 24, h: 12 } }
                  ,

            ],
}
