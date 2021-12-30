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
                style='maximal',
                datasource='InfluxDB_V2',
                measurement='currency',
                maxMilliSecSinceUpdate='259200000',
            ) +

            [

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
                        legend_current=false,
                        legend_total=false,
                        legend_avg=true,
                        legend_alignAsTable=true,
                        legend_rightSide=true,
                        legend_sideWidth=330
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
                  graph.new(
                        title='Temperature',
                        datasource='InfluxDB_V2',
                        fill=0,
                        format='short',
                        bars=false,
                        lines=true,
                        staircase=false,
                        legend_values=true,
                        legend_min=true,
                        legend_max=true,
                        legend_current=false,
                        legend_total=false,
                        legend_avg=true,
                        legend_alignAsTable=true,
                        legend_rightSide=true,
                        legend_sideWidth=330,
                  ).addTarget(influxdb.target(query='
from(bucket: "home_private")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["entity_id"] == "roof_temperature" or r["entity_id"] == "ada_temperature" or r["entity_id"] == "basement_temperature" or r["entity_id"] == "dining_temperature" or r["entity_id"] == "edwin_temperature" or r["entity_id"] == "kitchen_temperature" or r["entity_id"] == "laundry_temperature" or r["entity_id"] == "lounge_temperature" or r["entity_id"] == "office_temperature" or r["entity_id"] == "pantry_temperature" or r["entity_id"] == "parents_temperature" or r["entity_id"] == "rack_temperature")
  |> keep(columns: ["_time", "_value", "friendly_name"])
  |> aggregateWindow(every: v.windowPeriod, fn: mean, createEmpty: false)
                  '))
                  { gridPos: { x: 0, y: 0, w: 24, h: 12 } },

                  graph.new(
                        title='Carbon Dioxide',
                        datasource='InfluxDB_V2',
                        fill=0,
                        format='short',
                        bars=false,
                        lines=true,
                        staircase=false,
                        legend_values=true,
                        legend_min=true,
                        legend_max=true,
                        legend_current=false,
                        legend_total=false,
                        legend_avg=true,
                        legend_alignAsTable=true,
                        legend_rightSide=true,
                        legend_sideWidth=330,
                  ).addTarget(influxdb.target(query='
from(bucket: "home_private")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["entity_id"] == "dining_carbon_dioxide" or r["entity_id"] == "edwin_carbon_dioxide" or r["entity_id"] == "kitchen_carbon_dioxide" or r["entity_id"] == "lounge_carbon_dioxide" or r["entity_id"] == "office_carbon_dioxide" or r["entity_id"] == "pantry_carbon_dioxide" or r["entity_id"] == "parents_carbon_dioxide")
  |> keep(columns: ["_time", "_value", "friendly_name"])
  |> aggregateWindow(every: v.windowPeriod, fn: mean, createEmpty: false)
                  '))
                  { gridPos: { x: 0, y: 0, w: 24, h: 12 } },

                  graph.new(
                        title='Noise',
                        datasource='InfluxDB_V2',
                        fill=0,
                        format='short',
                        bars=false,
                        lines=true,
                        staircase=false,
                        legend_values=true,
                        legend_min=true,
                        legend_max=true,
                        legend_current=false,
                        legend_total=false,
                        legend_avg=true,
                        legend_alignAsTable=true,
                        legend_rightSide=true,
                        legend_sideWidth=330,
                  ).addTarget(influxdb.target(query='
from(bucket: "home_private")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["entity_id"] == "ada_noise" or r["entity_id"] == "edwin_noise" or r["entity_id"] == "kitchen_noise" or r["entity_id"] == "laundry_noise" or r["entity_id"] == "office_noise" or r["entity_id"] == "parents_noise")
  |> keep(columns: ["_time", "_value", "friendly_name"])
  |> aggregateWindow(every: v.windowPeriod, fn: mean, createEmpty: false)
                  '))
                  { gridPos: { x: 0, y: 0, w: 24, h: 12 } },

                  graph.new(
                        title='Humidity',
                        datasource='InfluxDB_V2',
                        fill=0,
                        format='short',
                        bars=false,
                        lines=true,
                        staircase=false,
                        legend_values=true,
                        legend_min=true,
                        legend_max=true,
                        legend_current=false,
                        legend_total=false,
                        legend_avg=true,
                        legend_alignAsTable=true,
                        legend_rightSide=true,
                        legend_sideWidth=330,
                  ).addTarget(influxdb.target(query='
from(bucket: "home_private")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["entity_id"] == "roof_humidity" or r["entity_id"] == "ada_humidity" or r["entity_id"] == "basement_humidity" or r["entity_id"] == "dining_humidity" or r["entity_id"] == "edwin_humidity" or r["entity_id"] == "kitchen_humidity" or r["entity_id"] == "laundry_humidity" or r["entity_id"] == "lounge_humidity" or r["entity_id"] == "office_humidity" or r["entity_id"] == "pantry_humidity" or r["entity_id"] == "parents_humidity" or r["entity_id"] == "rack_humidity")
  |> keep(columns: ["_time", "_value", "friendly_name"])
  |> aggregateWindow(every: v.windowPeriod, fn: mean, createEmpty: false)
                  '))
                  { gridPos: { x: 0, y: 0, w: 24, h: 12 } },

            ],
}
