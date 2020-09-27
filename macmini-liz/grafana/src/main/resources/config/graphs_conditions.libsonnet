{
  graphs()::
  
    local grafana = import 'grafonnet/grafana.libsonnet';
    local dashboard = grafana.dashboard;
    local graph = grafana.graphPanel;
    local influxdb = grafana.influxdb;
    
    [

      graph.new(title='Temperature', datasource='InfluxDB', fill=0)
        .addTarget(influxdb.target(
          query='from(bucket: "asystem")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["entity_id"] == "roof_temperature" or r["entity_id"] == "ada_temperature" or r["entity_id"] == "basement_temperature" or r["entity_id"] == "deck_temperature" or r["entity_id"] == "dining_temperature" or r["entity_id"] == "edwin_temperature" or r["entity_id"] == "kitchen_temperature" or r["entity_id"] == "laundry_temperature" or r["entity_id"] == "lounge_temperature" or r["entity_id"] == "office_temperature" or r["entity_id"] == "pantry_temperature" or r["entity_id"] == "parents_temperature" or r["entity_id"] == "utility_temperature")
  |> fill(usePrevious: true)
  |> group(columns: ["friendly_name"])
  |> aggregateWindow(every: v.windowPeriod, fn: mean, createEmpty: false)
  |> yield(name: "mean")'
        )) { gridPos: { x: 0, y: 0, w: 24, h: 10 } },

      graph.new(title='Carbon Dioxide', datasource='InfluxDB', fill=0)
        .addTarget(influxdb.target(
          query='from(bucket: "asystem")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["entity_id"] == "ada_carbon_dioxide" or r["entity_id"] == "dining_carbon_dioxide" or r["entity_id"] == "edwin_carbon_dioxide" or r["entity_id"] == "kitchen_carbon_dioxide" or r["entity_id"] == "laundry_carbon_dioxide" or r["entity_id"] == "lounge_carbon_dioxide" or r["entity_id"] == "office_carbon_dioxide" or r["entity_id"] == "pantry_carbon_dioxide" or r["entity_id"] == "parents_carbon_dioxide")
  |> fill(usePrevious: true)
  |> group(columns: ["friendly_name"])
  |> aggregateWindow(every: v.windowPeriod, fn: mean, createEmpty: false)
  |> yield(name: "mean")'
        )) { gridPos: { x: 0, y: 0, w: 24, h: 10 } },

      graph.new(title='Noise', datasource='InfluxDB', fill=0)
        .addTarget(influxdb.target(
          query='from(bucket: "asystem")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["entity_id"] == "ada_noise" or r["entity_id"] == "edwin_noise" or r["entity_id"] == "kitchen_noise" or r["entity_id"] == "laundry_noise" or r["entity_id"] == "office_noise" or r["entity_id"] == "parents_noise")
  |> fill(usePrevious: true)
  |> group(columns: ["friendly_name"])
  |> aggregateWindow(every: v.windowPeriod, fn: mean, createEmpty: false)
  |> yield(name: "mean")'
        )) { gridPos: { x: 0, y: 0, w: 24, h: 10 } },

      graph.new(title='Pressure', datasource='InfluxDB', fill=0)
        .addTarget(influxdb.target(
          query='from(bucket: "asystem")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["entity_id"] == "roof_pressure" or r["entity_id"] == "ada_pressure" or r["entity_id"] == "edwin_pressure" or r["entity_id"] == "kitchen_pressure" or r["entity_id"] == "laundry_pressure" or r["entity_id"] == "office_pressure" or r["entity_id"] == "parents_pressure")
  |> fill(usePrevious: true)
  |> group(columns: ["friendly_name"])
  |> aggregateWindow(every: v.windowPeriod, fn: mean, createEmpty: false)
  |> yield(name: "mean")'
        )) { gridPos: { x: 0, y: 0, w: 24, h: 10 } },

      graph.new(title='Humidity', datasource='InfluxDB', fill=0)
        .addTarget(influxdb.target(
          query='from(bucket: "asystem")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["entity_id"] == "roof_humidity" or r["entity_id"] == "ada_humidity" or r["entity_id"] == "basement_humidity" or r["entity_id"] == "deck_humidity" or r["entity_id"] == "dining_humidity" or r["entity_id"] == "edwin_humidity" or r["entity_id"] == "kitchen_humidity" or r["entity_id"] == "laundry_humidity" or r["entity_id"] == "lounge_humidity" or r["entity_id"] == "office_humidity" or r["entity_id"] == "pantry_humidity" or r["entity_id"] == "parents_humidity" or r["entity_id"] == "utility_humidity")
  |> fill(usePrevious: true)
  |> group(columns: ["friendly_name"])
  |> aggregateWindow(every: v.windowPeriod, fn: mean, createEmpty: false)
  |> yield(name: "mean")'
        )) { gridPos: { x: 0, y: 0, w: 24, h: 10 } },

      graph.new(title='Dew Point', datasource='InfluxDB', fill=0)
        .addTarget(influxdb.target(
          query='from(bucket: "asystem")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["entity_id"] == "utility_dew_point" or r["entity_id"] == "roof_dew_point")
  |> fill(usePrevious: true)
  |> group(columns: ["friendly_name"])
  |> aggregateWindow(every: v.windowPeriod, fn: mean, createEmpty: false)
  |> yield(name: "mean")'
        )) { gridPos: { x: 0, y: 0, w: 24, h: 10 } },

    ],
}
