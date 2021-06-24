                  graph.new(
                        title='Temperature Dailies',
                        datasource='InfluxDB_V2',
                        fill=3,
                        format='ºC',
                        bars=false,
                        lines=true,
                        staircase=true,
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
from(bucket: "asystem")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["entity_id"] == "roof_temperature")
  |> set(key: "name", value: "Roof High")
  |> keep(columns: ["table", "_start", "_stop", "_time", "_value", "name"])
  |> fill(usePrevious: true)
  |> timeShift(duration: -8h)
  |> aggregateWindow(every: 1d, fn: max, createEmpty: false)
                  ')).addTarget(influxdb.target(query='
from(bucket: "asystem")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["entity_id"] == "bom_perth_max_temp_c_1" and r["_field"] == "value")
  |> keep(columns: ["table", "_start", "_stop", "_time", "_value"])
  |> fill(usePrevious: true)
  |> timeShift(duration: 16h)
  |> aggregateWindow(every: 1d, fn: mean, createEmpty: false)
  |> set(key: "name", value: "Forecast High")
                  ')).addTarget(influxdb.target(query='
from(bucket: "asystem")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["entity_id"] == "roof_temperature")
  |> set(key: "name", value: "Roof Low")
  |> keep(columns: ["table", "_start", "_stop", "_time", "_value", "name"])
  |> fill(usePrevious: true)
  |> timeShift(duration: -8h)
  |> aggregateWindow(every: 1d, fn: min, createEmpty: false)
                  ')).addTarget(influxdb.target(query='
from(bucket: "asystem")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["entity_id"] == "bom_perth_min_temp_c_1" and r["_field"] == "value")
  |> keep(columns: ["table", "_start", "_stop", "_time", "_value"])
  |> fill(usePrevious: true)
  |> timeShift(duration: 16h)
  |> aggregateWindow(every: 1d, fn: mean, createEmpty: false)
  |> set(key: "name", value: "Forecast Low")
                  ')) { gridPos: { x: 0, y: 0, w: 24, h: 7 } },
