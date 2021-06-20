//ASDASHBOARD_DEFAULTS time_from='now-25y', refresh=''
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
  |> filter(fn: (r) => r["period"] == "1mo")
  |> last()
  |> keep(columns: ["_value"])
                  '))
//ASM                 { gridPos: { x: 0, y: 0, w: 24, h: 3 } }
//AST                 { gridPos: { x: 0, y: 0, w: 5, h: 3 } }
//ASD                 { gridPos: { x: 0, y: 0, w: 5, h: 3 } }
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
  |> filter(fn: (r) => r["period"] == "1mo")
  |> last()
  |> keep(columns: ["_value"])
                  '))
//ASM                 { gridPos: { x: 0, y: 8, w: 24, h: 3 } }
//AST                 { gridPos: { x: 5, y: 0, w: 5, h: 3 } }
//ASD                 { gridPos: { x: 5, y: 0, w: 5, h: 3 } }
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
//ASM                 { gridPos: { x: 0, y: 16, w: 24, h: 3 } }
//AST                 { gridPos: { x: 10, y: 0, w: 5, h: 3 } }
//ASD                 { gridPos: { x: 10, y: 0, w: 5, h: 3 } }
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
  |> filter(fn: (r) => r["period"] == "1mo")
  |> keep(columns: ["_time", "_value"])
  |> mean(column: "_value")
  |> rename(fn: (column) => "Net")
                  ')).addTarget(influxdb.target(query='
from(bucket: "data_public")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "interest")
  |> filter(fn: (r) => r["_field"] == "retail")
  |> filter(fn: (r) => r["period"] == "1mo")
  |> keep(columns: ["_time", "_value"])
  |> mean(column: "_value")
  |> rename(fn: (column) => "Retail")
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
//ASM                 { gridPos: { x: 0, y: 24, w: 24, h: 8 } }
//AST                 { gridPos: { x: 15, y: 0, w: 9, h: 8 } }
//ASD                 { gridPos: { x: 15, y: 0, w: 9, h: 8 } }
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
//ASM                 { gridPos: { x: 0, y: 3, w: 24, h: 5 } }
//AST                 { gridPos: { x: 0, y: 3, w: 5, h: 5 } }
//ASD                 { gridPos: { x: 0, y: 3, w: 5, h: 5 } }
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
  |> filter(fn: (r) => r["period"] == "10y")
  |> last()
  |> keep(columns: ["_value"])
                  '))
//ASM                 { gridPos: { x: 0, y: 11, w: 24, h: 5 } }
//AST                 { gridPos: { x: 5, y: 3, w: 5, h: 5 } }
//ASD                 { gridPos: { x: 5, y: 3, w: 5, h: 5 } }
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
//ASM                 { gridPos: { x: 0, y: 19, w: 24, h: 5 } }
//AST                 { gridPos: { x: 10, y: 3, w: 5, h: 5 } }
//ASD                 { gridPos: { x: 10, y: 3, w: 5, h: 5 } }
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
//ASD                   legend_values=true,
//ASD                   legend_min=true,
//ASD                   legend_max=true,
//ASD                   legend_current=true,
//ASD                   legend_total=false,
//ASD                   legend_avg=false,
//ASD                   legend_alignAsTable=true,
//ASD                   legend_rightSide=true,
//ASD                   legend_sideWidth=330
                  ).addTarget(influxdb.target(query='
from(bucket: "data_public")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "interest")
  |> filter(fn: (r) => r["_field"] == "net")
  |> filter(fn: (r) => r["period"] == "1mo")
  |> keep(columns: ["_time", "_value", "_field"])
                  ')).addTarget(influxdb.target(query='
from(bucket: "data_public")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "interest")
  |> filter(fn: (r) => r["_field"] == "retail")
  |> filter(fn: (r) => r["period"] == "1mo")
  |> keep(columns: ["_time", "_value", "_field"])
                  ')).addTarget(influxdb.target(query='
from(bucket: "data_public")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "interest")
  |> filter(fn: (r) => r["_field"] == "inflation")
  |> filter(fn: (r) => r["period"] == "1mo")
  |> keep(columns: ["_time", "_value", "_field"])
                  ')).addSeriesOverride(
                        { "alias": "/.*retail.*/", "bars": false, "lines": true, "linewidth": 2, "zindex": 3, "yaxis": 1 }
                  ).addSeriesOverride(
                        { "alias": "/.*inflation.*/", "bars": false, "lines": true, "linewidth": 2, "zindex": 3, "yaxis": 1 }
                  )
//ASM                 { gridPos: { x: 0, y: 32, w: 24, h: 7 } }
//AST                 { gridPos: { x: 0, y: 8, w: 24, h: 12 } }
//ASD                 { gridPos: { x: 0, y: 8, w: 24, h: 12 } }
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
//ASD                   legend_values=true,
//ASD                   legend_min=true,
//ASD                   legend_max=true,
//ASD                   legend_current=true,
//ASD                   legend_total=false,
//ASD                   legend_avg=false,
//ASD                   legend_alignAsTable=true,
//ASD                   legend_rightSide=true,
//ASD                   legend_sideWidth=330
                  ).addTarget(influxdb.target(query='
from(bucket: "data_public")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "interest")
  |> filter(fn: (r) => r["_field"] == "net")
  |> filter(fn: (r) => r["period"] == "10y")
  |> keep(columns: ["_time", "_value", "_field"])
                  ')).addTarget(influxdb.target(query='
from(bucket: "data_public")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "interest")
  |> filter(fn: (r) => r["_field"] == "retail")
  |> filter(fn: (r) => r["period"] == "10y")
  |> keep(columns: ["_time", "_value", "_field"])
                  ')).addTarget(influxdb.target(query='
from(bucket: "data_public")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "interest")
  |> filter(fn: (r) => r["_field"] == "inflation")
  |> filter(fn: (r) => r["period"] == "10y")
  |> keep(columns: ["_time", "_value", "_field"])
                  ')).addSeriesOverride(
                        { "alias": "/.*retail.*/", "bars": false, "lines": true, "linewidth": 2, "zindex": 3, "yaxis": 1 }
                  ).addSeriesOverride(
                        { "alias": "/.*inflation.*/", "bars": false, "lines": true, "linewidth": 2, "zindex": 3, "yaxis": 1 }
                  )
//ASM                 { gridPos: { x: 0, y: 39, w: 24, h: 7 } }
//AST                 { gridPos: { x: 0, y: 20, w: 24, h: 12 } }
//ASD                 { gridPos: { x: 0, y: 20, w: 24, h: 12 } }
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
//ASD                   legend_values=true,
//ASD                   legend_min=true,
//ASD                   legend_max=true,
//ASD                   legend_current=true,
//ASD                   legend_total=false,
//ASD                   legend_avg=false,
//ASD                   legend_alignAsTable=true,
//ASD                   legend_rightSide=true,
//ASD                   legend_sideWidth=330
                  ).addTarget(influxdb.target(query='
from(bucket: "data_public")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "interest")
  |> filter(fn: (r) => r["_field"] == "net")
  |> filter(fn: (r) => r["period"] == "1y")
  |> keep(columns: ["_time", "_value", "period"])
                  ')).addTarget(influxdb.target(query='
from(bucket: "data_public")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "interest")
  |> filter(fn: (r) => r["_field"] == "net")
  |> filter(fn: (r) => r["period"] == "5y")
  |> keep(columns: ["_time", "_value", "period"])
                  ')).addTarget(influxdb.target(query='
from(bucket: "data_public")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "interest")
  |> filter(fn: (r) => r["_field"] == "net")
  |> filter(fn: (r) => r["period"] == "10y")
  |> keep(columns: ["_time", "_value", "period"])
                  ')).addTarget(influxdb.target(query='
from(bucket: "data_public")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "interest")
  |> filter(fn: (r) => r["_field"] == "net")
  |> filter(fn: (r) => r["period"] == "20y")
  |> keep(columns: ["_time", "_value", "period"])
                  '))
//ASM                 { gridPos: { x: 0, y: 46, w: 24, h: 7 } }
//AST                 { gridPos: { x: 0, y: 32, w: 24, h: 12 } }
//ASD                 { gridPos: { x: 0, y: 32, w: 24, h: 12 } }
                  ,

            ],
}
