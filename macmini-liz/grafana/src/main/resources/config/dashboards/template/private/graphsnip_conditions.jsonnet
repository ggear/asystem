      graph.new(
        title='Temperature Dailies',
        datasource='InfluxDB_V2',
        fill=3,
        format='ºC',
        bars=false,
        lines=true,
        staircase=true,
        legend_values=true,
        legend_min=true,
        legend_max=true,
        legend_current=true,
        legend_total=false,
        legend_avg=false,
        legend_alignAsTable=true,
        legend_rightSide=true,
        legend_sideWidth=425
      ).addTarget(influxdb.target(query='// Start
from(bucket: "asystem")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["entity_id"] == "roof_temperature")
  |> set(key: "name", value: "Roof High")
  |> keep(columns: ["table", "_start", "_stop", "_time", "_value", "name"])
  |> fill(usePrevious: true)
  |> timeShift(duration: -8h)
  |> aggregateWindow(every: 1d, fn: max, createEmpty: false)
// End')).addTarget(influxdb.target(query='// Start
from(bucket: "asystem")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["entity_id"] == "bom_perth_max_temp_c_1" and r["_field"] == "value")
  |> keep(columns: ["table", "_start", "_stop", "_time", "_value"])
  |> fill(usePrevious: true)
  |> timeShift(duration: 16h)
  |> aggregateWindow(every: 1d, fn: mean, createEmpty: false)
  |> set(key: "name", value: "Forecast High")
// End')).addTarget(influxdb.target(query='// Start
from(bucket: "asystem")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["entity_id"] == "roof_temperature")
  |> set(key: "name", value: "Roof Low")
  |> keep(columns: ["table", "_start", "_stop", "_time", "_value", "name"])
  |> fill(usePrevious: true)
  |> timeShift(duration: -8h)
  |> aggregateWindow(every: 1d, fn: min, createEmpty: false)
// End')).addTarget(influxdb.target(query='// Start
from(bucket: "asystem")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["entity_id"] == "bom_perth_min_temp_c_1" and r["_field"] == "value")
  |> keep(columns: ["table", "_start", "_stop", "_time", "_value"])
  |> fill(usePrevious: true)
  |> timeShift(duration: 16h)
  |> aggregateWindow(every: 1d, fn: mean, createEmpty: false)
  |> set(key: "name", value: "Forecast Low")
// End')) { gridPos: { x: 0, y: 0, w: 24, h: 12 } },
