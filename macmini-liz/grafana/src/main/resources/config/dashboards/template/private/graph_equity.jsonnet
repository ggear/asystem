//ASDASHBOARD_DEFAULTS time_from='now-1y', refresh='', timepicker=timepicker.new(refresh_intervals=['15m'], time_options=['7d', '30d', '90d', '180d', '1y', '5y', '10y', '25y', '50y'])
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
//ASM           style='minimal',
//AST           style='medial',
//ASD           style='maximal',
//ASM           formFactor='Mobile',
//AST           formFactor='Tablet',
//ASD           formFactor='Desktop',
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
field = "holdings"
from(bucket: "data_private")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "equity")
  |> filter(fn: (r) => r["_field"] == field)
  |> filter(fn: (r) => r["period"] == "1d")
  |> filter(fn: (r) => r["type"] == "price-change-value-spot")
  |> sort(columns: ["_time"], desc: false)
  |> last()
  |> keep(columns: ["_value"])
                  '))
//ASM                 { gridPos: { x: 0, y: 2, w: 24, h: 3 } }
//AST                 { gridPos: { x: 0, y: 2, w: 5, h: 3 } }
//ASD                 { gridPos: { x: 0, y: 2, w: 5, h: 3 } }
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
field = "watch"
from(bucket: "data_private")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "equity")
  |> filter(fn: (r) => r["_field"] == field)
  |> filter(fn: (r) => r["period"] == "1d")
  |> filter(fn: (r) => r["type"] == "price-change-value-spot")
  |> sort(columns: ["_time"], desc: false)
  |> last()
  |> keep(columns: ["_value"])
                  '))
//ASM                 { gridPos: { x: 0, y: 10, w: 24, h: 3 } }
//AST                 { gridPos: { x: 5, y: 2, w: 5, h: 3 } }
//ASD                 { gridPos: { x: 5, y: 2, w: 5, h: 3 } }
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
field = "baseline"
from(bucket: "data_private")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "equity")
  |> filter(fn: (r) => r["_field"] == field)
  |> filter(fn: (r) => r["period"] == "1d")
  |> filter(fn: (r) => r["type"] == "price-change-value-spot")
  |> sort(columns: ["_time"], desc: false)
  |> last()
  |> keep(columns: ["_value"])
                  '))
//ASM                 { gridPos: { x: 0, y: 18, w: 24, h: 3 } }
//AST                 { gridPos: { x: 10, y: 2, w: 5, h: 3 } }
//ASD                 { gridPos: { x: 10, y: 2, w: 5, h: 3 } }
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
                  '))
//ASM                 { gridPos: { x: 0, y: 26, w: 24, h: 8 } }
//AST                 { gridPos: { x: 15, y: 2, w: 9, h: 8 } }
//ASD                 { gridPos: { x: 15, y: 2, w: 9, h: 8 } }
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
                  '))
//ASM                 { gridPos: { x: 0, y: 5, w: 24, h: 5 } }
//AST                 { gridPos: { x: 0, y: 5, w: 5, h: 5 } }
//ASD                 { gridPos: { x: 0, y: 5, w: 5, h: 5 } }
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
                  '))
//ASM                 { gridPos: { x: 0, y: 13, w: 24, h: 5 } }
//AST                 { gridPos: { x: 5, y: 5, w: 5, h: 5 } }
//ASD                 { gridPos: { x: 5, y: 5, w: 5, h: 5 } }
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
                  '))
//ASM                 { gridPos: { x: 0, y: 21, w: 24, h: 5 } }
//AST                 { gridPos: { x: 10, y: 5, w: 5, h: 5 } }
//ASD                 { gridPos: { x: 10, y: 5, w: 5, h: 5 } }
                  ,

                  graph.new(
                        title='Holdings Monthly Deltas',
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
//ASD                   legend_sideWidth=330,
                        maxDataPoints=10000
                  ).addTarget(influxdb.target(query='
                  ')).addTarget(influxdb.target(query='
                  ')).addTarget(influxdb.target(query='
                  '))
//ASM                 { gridPos: { x: 0, y: 34, w: 24, h: 7 } }
//AST                 { gridPos: { x: 0, y: 10, w: 24, h: 12 } }
//ASD                 { gridPos: { x: 0, y: 10, w: 24, h: 12 } }
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
//ASD                   legend_values=true,
//ASD                   legend_min=true,
//ASD                   legend_max=true,
//ASD                   legend_current=true,
//ASD                   legend_total=false,
//ASD                   legend_avg=false,
//ASD                   legend_alignAsTable=true,
//ASD                   legend_rightSide=true,
//ASD                   legend_sideWidth=330,
                        maxDataPoints=10000
                  ).addTarget(influxdb.target(query='
                  ')).addTarget(influxdb.target(query='
                  ')).addTarget(influxdb.target(query='
                  '))
//ASM                 { gridPos: { x: 0, y: 41, w: 24, h: 7 } }
//AST                 { gridPos: { x: 0, y: 22, w: 24, h: 12 } }
//ASD                 { gridPos: { x: 0, y: 22, w: 24, h: 12 } }
                  ,

            ],
}
