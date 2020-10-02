{
  graphs()::
  
    local grafana = import 'grafonnet/grafana.libsonnet';
    local dashboard = grafana.dashboard;
    local graph = grafana.graphPanel;
    local influxdb = grafana.influxdb;
    
    [

      graph.new(
        title='Temperature Means',
        datasource='InfluxDB',
        fill=3,
        format='ºC',
        staircase=true
      ).addTarget(influxdb.target(query='
from(bucket: "asystem")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["entity_id"] == "roof_temperature")
  |> keep(columns: ["table", "_start", "_stop", "_time", "_value", "name"])
  |> set(key: "name", value: "Roof High")
  |> timeShift(duration: -32h)
  |> fill(usePrevious: true)
  |> aggregateWindow(every: 1d, fn: max, createEmpty: false)
      ')) { gridPos: { x: 0, y: 0, w: 24, h: 10 } },

      graph.new(
        title='Temperature',
        datasource='InfluxDB',
        fill=0,
        format='short'
      ).addTarget(influxdb.target(query='
from(bucket: "asystem")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["entity_id"] == "roof_temperature" or r["entity_id"] == "ada_temperature" or r["entity_id"] == "basement_temperature" or r["entity_id"] == "deck_temperature" or r["entity_id"] == "dining_temperature" or r["entity_id"] == "edwin_temperature" or r["entity_id"] == "kitchen_temperature" or r["entity_id"] == "laundry_temperature" or r["entity_id"] == "lounge_temperature" or r["entity_id"] == "office_temperature" or r["entity_id"] == "pantry_temperature" or r["entity_id"] == "parents_temperature" or r["entity_id"] == "utility_temperature")
  |> rename(columns: {friendly_name: "name"})
  |> keep(columns: ["table", "_start", "_stop", "_time", "_value", "name"])
  |> fill(usePrevious: true)
  |> aggregateWindow(every: v.windowPeriod, fn: max, createEmpty: false)
        ')) { gridPos: { x: 0, y: 0, w: 24, h: 10 } },

      graph.new(
        title='Carbon Dioxide',
        datasource='InfluxDB',
        fill=0,
        format='short'
      ).addTarget(influxdb.target(query='
from(bucket: "asystem")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["entity_id"] == "ada_carbon_dioxide" or r["entity_id"] == "dining_carbon_dioxide" or r["entity_id"] == "edwin_carbon_dioxide" or r["entity_id"] == "kitchen_carbon_dioxide" or r["entity_id"] == "laundry_carbon_dioxide" or r["entity_id"] == "lounge_carbon_dioxide" or r["entity_id"] == "office_carbon_dioxide" or r["entity_id"] == "pantry_carbon_dioxide" or r["entity_id"] == "parents_carbon_dioxide")
  |> rename(columns: {friendly_name: "name"})
  |> keep(columns: ["table", "_start", "_stop", "_time", "_value", "name"])
  |> fill(usePrevious: true)
  |> aggregateWindow(every: v.windowPeriod, fn: max, createEmpty: false)
        ')) { gridPos: { x: 0, y: 0, w: 24, h: 10 } },

      graph.new(
        title='Noise',
        datasource='InfluxDB',
        fill=0,
        format='short'
      ).addTarget(influxdb.target(query='
from(bucket: "asystem")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["entity_id"] == "ada_noise" or r["entity_id"] == "edwin_noise" or r["entity_id"] == "kitchen_noise" or r["entity_id"] == "laundry_noise" or r["entity_id"] == "office_noise" or r["entity_id"] == "parents_noise")
  |> rename(columns: {friendly_name: "name"})
  |> keep(columns: ["table", "_start", "_stop", "_time", "_value", "name"])
  |> fill(usePrevious: true)
  |> aggregateWindow(every: v.windowPeriod, fn: max, createEmpty: false)
        ')) { gridPos: { x: 0, y: 0, w: 24, h: 10 } },

      graph.new(
        title='Pressure',
        datasource='InfluxDB',
        fill=0,
        format='short'
      ).addTarget(influxdb.target(query='
from(bucket: "asystem")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["entity_id"] == "roof_pressure" or r["entity_id"] == "ada_pressure" or r["entity_id"] == "edwin_pressure" or r["entity_id"] == "kitchen_pressure" or r["entity_id"] == "laundry_pressure" or r["entity_id"] == "office_pressure" or r["entity_id"] == "parents_pressure")
  |> rename(columns: {friendly_name: "name"})
  |> keep(columns: ["table", "_start", "_stop", "_time", "_value", "name"])
  |> fill(usePrevious: true)
  |> aggregateWindow(every: v.windowPeriod, fn: max, createEmpty: false)
        ')) { gridPos: { x: 0, y: 0, w: 24, h: 10 } },

      graph.new(
        title='Humidity',
        datasource='InfluxDB',
        fill=0,
        format='short'
      ).addTarget(influxdb.target(query='
from(bucket: "asystem")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["entity_id"] == "roof_humidity" or r["entity_id"] == "ada_humidity" or r["entity_id"] == "basement_humidity" or r["entity_id"] == "deck_humidity" or r["entity_id"] == "dining_humidity" or r["entity_id"] == "edwin_humidity" or r["entity_id"] == "kitchen_humidity" or r["entity_id"] == "laundry_humidity" or r["entity_id"] == "lounge_humidity" or r["entity_id"] == "office_humidity" or r["entity_id"] == "pantry_humidity" or r["entity_id"] == "parents_humidity" or r["entity_id"] == "utility_humidity")
  |> rename(columns: {friendly_name: "name"})
  |> keep(columns: ["table", "_start", "_stop", "_time", "_value", "name"])
  |> fill(usePrevious: true)
  |> aggregateWindow(every: v.windowPeriod, fn: max, createEmpty: false)
        ')) { gridPos: { x: 0, y: 0, w: 24, h: 10 } },

      graph.new(
        title='Dew Point',
        datasource='InfluxDB',
        fill=0,
        format='short'
      ).addTarget(influxdb.target(query='
from(bucket: "asystem")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["entity_id"] == "utility_dew_point" or r["entity_id"] == "roof_dew_point")
  |> rename(columns: {friendly_name: "name"})
  |> keep(columns: ["table", "_start", "_stop", "_time", "_value", "name"])
  |> fill(usePrevious: true)
  |> aggregateWindow(every: v.windowPeriod, fn: max, createEmpty: false)
        ')) { gridPos: { x: 0, y: 0, w: 24, h: 10 } },

    ],
}
