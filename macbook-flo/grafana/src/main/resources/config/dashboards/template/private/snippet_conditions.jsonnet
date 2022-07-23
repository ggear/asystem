                  graph.new(
                        title='Temperature Forecast',
                        datasource='InfluxDB_V2',
                        fill=0,
                        format='ºC',
                        bars=false,
                        lines=true,
                        staircase=true,
//ASD                   legend_values=true,
//ASD                   legend_min=true,
//ASD                   legend_max=true,
//ASD                   legend_current=false,
//ASD                   legend_total=false,
//ASD                   legend_avg=true,
//ASD                   legend_alignAsTable=true,
//ASD                   legend_rightSide=true,
//ASD                   legend_sideWidth=380
                  ).addTarget(influxdb.target(query='
import "strings"
bin=1d
metric="min"
entity_id="darlington_forecast_temp_" + metric + "_0"
label=strings.title(v: metric)
timeRangeStart=v.timeRangeStart
// timeRangeStart=-5m
// timeRangeStart=now()
// timeRangeStart="2022-06-14T02:55:42.581000000Z"
from(bucket: "home_private")
  |> range(start: time(v: if strings.hasPrefix(v: string(v: timeRangeStart), prefix: "-" ) then string(v: time(v: int(v: now()) + int(v: timeRangeStart) - 2*int(v: bin))) else string(v: time(v: int(v: time(v: timeRangeStart)) - 2*int(v: bin)))), stop: v.timeRangeStop)
  |> filter(fn: (r) => r["entity_id"] == entity_id)
  |> filter(fn: (r) => r["_field"] == "value")
  |> group()
  |> aggregateWindow(every:  bin, fn: last, createEmpty: true)
  |> fill(column: "_value", usePrevious: true)
  |> keep(columns: ["_time", "_value"])
  |> rename(columns: {_value: label})
                  ')).addTarget(influxdb.target(query='
import "strings"
bin=1d
metric="max"
entity_id="darlington_forecast_temp_" + metric + "_0"
label=strings.title(v: metric)
timeRangeStart=v.timeRangeStart
// timeRangeStart=-5m
// timeRangeStart=now()
// timeRangeStart="2022-06-14T02:55:42.581000000Z"
from(bucket: "home_private")
  |> range(start: time(v: if strings.hasPrefix(v: string(v: timeRangeStart), prefix: "-" ) then string(v: time(v: int(v: now()) + int(v: timeRangeStart) - 2*int(v: bin))) else string(v: time(v: int(v: time(v: timeRangeStart)) - 2*int(v: bin)))), stop: v.timeRangeStop)
  |> filter(fn: (r) => r["entity_id"] == entity_id)
  |> filter(fn: (r) => r["_field"] == "value")
  |> group()
  |> aggregateWindow(every:  bin, fn: last, createEmpty: true)
  |> fill(column: "_value", usePrevious: true)
  |> keep(columns: ["_time", "_value"])
  |> rename(columns: {_value: label})
                    ')).addTarget(influxdb.target(query='
from(bucket: "home_private")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["entity_id"] == "roof_temperature")
  |> keep(columns: ["_time", "_value"])
  |> aggregateWindow(every: v.windowPeriod, fn: mean, createEmpty: false)
  |> keep(columns: ["_time", "_value"])
  |> rename(columns: {_value: "Actual"})
                  ')) { gridPos: { x: 0, y: 2, w: 24, h: 12 } },

                  graph.new(
                        title='Lounge',
                        datasource='InfluxDB_V2',
                        fill=0,
                        format='',
                        bars=false,
                        lines=true,
                        staircase=false,
                        formatY1='ºC',
                        formatY2='µg/m³',
//ASD                   legend_values=true,
//ASD                   legend_min=true,
//ASD                   legend_max=true,
//ASD                   legend_current=false,
//ASD                   legend_total=false,
//ASD                   legend_avg=true,
//ASD                   legend_alignAsTable=true,
//ASD                   legend_rightSide=true,
//ASD                   legend_sideWidth=380,
                        maxDataPoints=10000
                  ).addTarget(influxdb.target(query='
from(bucket: "home_private")
|> range(start: v.timeRangeStart, stop: v.timeRangeStop)
|> filter(fn: (r) => r["entity_id"] == "compensation_sensor_netatmo_bertram_2_office_lounge_temperature")
|> filter(fn: (r) => r["_field"] == "value")
|> aggregateWindow(every: v.windowPeriod, fn: mean, createEmpty: false)
|> keep(columns: ["_time", "_value"])
|> rename(columns: {_value: "Lounge Temperature"})
                  ')).addTarget(influxdb.target(query='
from(bucket: "home_private")
|> range(start: v.timeRangeStart, stop: v.timeRangeStop)
|> filter(fn: (r) => r["entity_id"] == "lounge_air_purifier_pm25")
|> filter(fn: (r) => r["_field"] == "value")
|> aggregateWindow(every: v.windowPeriod, fn: mean, createEmpty: false)
|> keep(columns: ["_time", "_value"])
|> rename(columns: {_value: "Air Quality"})
                  ')).addSeriesOverride(
                        { "alias": "/.*Temperature.*/", "steppedLine": false, "bars": false, "lines" :true, "yaxis": 1 }
                  ).addSeriesOverride(
                        { "alias": "/.*Air.*/", "steppedLine": false, "bars": false, "lines" :true, "yaxis": 2 }
                  ) { gridPos: { x: 0, y: 2, w: 24, h: 12 } },
