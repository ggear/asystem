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
//ASD                   legend_sideWidth=330
                  ).addTarget(influxdb.target(query='
from(bucket: "home_private")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["entity_id"] == "roof_temperature")
  |> keep(columns: ["_time", "_value", "friendly_name"])
  |> aggregateWindow(every: v.windowPeriod, fn: mean, createEmpty: false)
  |> map(fn: (r) => ({ r with friendly_name: "Actual" }))
                  ')).addTarget(influxdb.target(query='
import "strings"
from(bucket: "home_private")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "°C")
  |> filter(fn: (r) => r["entity_id"] == "darlington_forecast_temp_max_0" or r["entity_id"] == "darlington_forecast_temp_min_0")
  |> filter(fn: (r) => r["_field"] == "value")
  |> aggregateWindow(every: v.windowPeriod, fn: last, createEmpty: false)
  |> map(fn: (r) => ({ r with friendly_name: strings.replaceAll(v: r.friendly_name, t: "darlington_forecast Temp", u: "Forecast") }))
  |> map(fn: (r) => ({ r with friendly_name: strings.replaceAll(v: r.friendly_name, t: " 0", u: "") }))
  |> keep(columns: ["_time", "_value", "friendly_name"])
                  ')) { gridPos: { x: 0, y: 2, w: 24, h: 12 } },
