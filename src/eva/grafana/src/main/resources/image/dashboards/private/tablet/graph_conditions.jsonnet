// WARNING: This file is written by the build process, any manual edits will be lost!

{
      graphs()::

            local grafana = import 'grafonnet/grafana.libsonnet';
            local asystem = import 'default/asystem-library.jsonnet';
            local dashboard = grafana.dashboard;
            local stat = grafana.statPanel;
            local graph = grafana.graphPanel;
            local table = grafana.tablePanel;
            local gauge = grafana.gaugePanel;
            local bar = grafana.barGaugePanel;
            local influxdb = grafana.influxdb;
            local header = asystem.header;

            header.new(
                style='medial',
                formFactor='Tablet',
                datasource='InfluxDB_V2',

// TODO: Update this to include metadata rows when re-implemented in Go
                measurement='__FIXME__',

                maxMilliSecSinceUpdate='259200000',
            ) +

            [

                  graph.new(
                        title='Temperature Forecast',
                        datasource='InfluxDB_V2',
                        fill=0,
                        format='ºC',
                        bars=false,
                        lines=true,
                        staircase=true,
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
                        maxDataPoints=10000
                  ).addTarget(influxdb.target(query='
from(bucket: "home_private")
|> range(start: v.timeRangeStart, stop: v.timeRangeStop)
|> filter(fn: (r) => r["entity_id"] == "compensation_sensor_roof_temperature")
|> filter(fn: (r) => r["_field"] == "value")
|> aggregateWindow(every: v.windowPeriod, fn: mean, createEmpty: false)
|> keep(columns: ["_time", "_value"])
|> rename(columns: {_value: "Roof Temperature"})
                  ')).addTarget(influxdb.target(query='
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
|> rename(columns: {_value: "Lounge Air Quality"})
                  ')).addTarget(influxdb.target(query='
from(bucket: "home_private")
|> range(start: v.timeRangeStart, stop: v.timeRangeStop)
|> filter(fn: (r) => r["entity_id"] == "dining_air_purifier_pm25")
|> filter(fn: (r) => r["_field"] == "value")
|> aggregateWindow(every: v.windowPeriod, fn: mean, createEmpty: false)
|> keep(columns: ["_time", "_value"])
|> rename(columns: {_value: "Dining Air Quality"})
                  ')).addSeriesOverride(
                        { "alias": "/.*Temperature.*/", "steppedLine": false, "bars": false, "lines" :true, "yaxis": 1 }
                  ).addSeriesOverride(
                        { "alias": "/.*Air.*/", "steppedLine": false, "bars": false, "lines" :true, "yaxis": 2 }
                  ) { gridPos: { x: 0, y: 2, w: 24, h: 12 } },
                  graph.new(
                        title='Temperature',
                        datasource='InfluxDB_V2',
                        fill=0,
                        format='short',
                        bars=false,
                        lines=true,
                        staircase=false,
                  ).addTarget(influxdb.target(query='
from(bucket: "home_private")
|> range(start: v.timeRangeStart, stop: v.timeRangeStop)
|> filter(fn: (r) => r["entity_id"] == "compensation_sensor_roof_temperature" or r["entity_id"] == "compensation_sensor_ada_temperature" or r["entity_id"] == "compensation_sensor_edwin_temperature" or r["entity_id"] == "compensation_sensor_office_lounge_temperature" or r["entity_id"] == "compensation_sensor_parents_temperature" or r["entity_id"] == "compensation_sensor_office_temperature" or r["entity_id"] == "compensation_sensor_kitchen_temperature" or r["entity_id"] == "compensation_sensor_office_pantry_temperature" or r["entity_id"] == "compensation_sensor_office_dining_temperature" or r["entity_id"] == "compensation_sensor_laundry_temperature" or r["entity_id"] == "compensation_sensor_wardrobe_temperature" or r["entity_id"] == "compensation_sensor_utility_temperature" or r["entity_id"] == "deck_festoons_plug_temperature" or r["entity_id"] == "compensation_sensor_deck_festoons_plug_temperature" or r["entity_id"] == "compensation_sensor_office_basement_temperature")
|> filter(fn: (r) => r["_field"] == "value")
|> keep(columns: ["_time", "_value", "friendly_name"])
|> aggregateWindow(every: v.windowPeriod, fn: mean, createEmpty: false)
                  '))
                  { gridPos: { x: 0, y: 2, w: 24, h: 12 } },

                  graph.new(
                        title='Air Quality',
                        datasource='InfluxDB_V2',
                        fill=0,
                        format='short',
                        bars=false,
                        lines=true,
                        staircase=false,
                  ).addTarget(influxdb.target(query='
from(bucket: "home_private")
|> range(start: v.timeRangeStart, stop: v.timeRangeStop)
|> filter(fn: (r) => r["entity_id"] == "dining_air_purifier_pm25" or r["entity_id"] == "lounge_air_purifier_pm25" or r["entity_id"] == "parents_air_purifier_pm25" or r["entity_id"] == "kitchen_air_purifier_pm25")
|> filter(fn: (r) => r["_field"] == "value")
|> keep(columns: ["_time", "_value", "friendly_name"])
|> aggregateWindow(every: v.windowPeriod, fn: mean, createEmpty: false)
                  '))
                  { gridPos: { x: 0, y: 2, w: 24, h: 12 } },

                  graph.new(
                        title='Humidity',
                        datasource='InfluxDB_V2',
                        fill=0,
                        format='short',
                        bars=false,
                        lines=true,
                        staircase=false,
                  ).addTarget(influxdb.target(query='
from(bucket: "home_private")
|> range(start: v.timeRangeStart, stop: v.timeRangeStop)
|> filter(fn: (r) => r["entity_id"] == "roof_humidity" or r["entity_id"] == "ada_humidity" or r["entity_id"] == "edwin_humidity" or r["entity_id"] == "office_lounge_humidity" or r["entity_id"] == "parents_humidity" or r["entity_id"] == "office_humidity" or r["entity_id"] == "kitchen_humidity" or r["entity_id"] == "office_pantry_humidity" or r["entity_id"] == "office_dining_humidity" or r["entity_id"] == "laundry_humidity" or r["entity_id"] == "wardrobe_humidity" or r["entity_id"] == "office_basement_humidity")
|> filter(fn: (r) => r["_field"] == "value")
|> keep(columns: ["_time", "_value", "friendly_name"])
|> aggregateWindow(every: v.windowPeriod, fn: mean, createEmpty: false)
                  '))
                  { gridPos: { x: 0, y: 2, w: 24, h: 12 } },

                  graph.new(
                        title='Carbon Dioxide',
                        datasource='InfluxDB_V2',
                        fill=0,
                        format='short',
                        bars=false,
                        lines=true,
                        staircase=false,
                  ).addTarget(influxdb.target(query='
from(bucket: "home_private")
|> range(start: v.timeRangeStart, stop: v.timeRangeStop)
|> filter(fn: (r) => r["entity_id"] == "edwin_carbon_dioxide" or r["entity_id"] == "office_carbon_dioxide" or r["entity_id"] == "office_lounge_carbon_dioxide" or r["entity_id"] == "kitchen_carbon_dioxide" or r["entity_id"] == "office_pantry_carbon_dioxide" or r["entity_id"] == "office_dining_carbon_dioxide")
|> filter(fn: (r) => r["_field"] == "value")
|> keep(columns: ["_time", "_value", "friendly_name"])
|> aggregateWindow(every: v.windowPeriod, fn: mean, createEmpty: false)
                  '))
                  { gridPos: { x: 0, y: 2, w: 24, h: 12 } },

                  graph.new(
                        title='Noise',
                        datasource='InfluxDB_V2',
                        fill=0,
                        format='short',
                        bars=false,
                        lines=true,
                        staircase=false,
                  ).addTarget(influxdb.target(query='
from(bucket: "home_private")
|> range(start: v.timeRangeStart, stop: v.timeRangeStop)
|> filter(fn: (r) => r["entity_id"] == "ada_noise" or r["entity_id"] == "edwin_noise" or r["entity_id"] == "parents_noise" or r["entity_id"] == "office_noise" or r["entity_id"] == "kitchen_noise" or r["entity_id"] == "laundry_noise")
|> filter(fn: (r) => r["_field"] == "value")
|> keep(columns: ["_time", "_value", "friendly_name"])
|> aggregateWindow(every: v.windowPeriod, fn: mean, createEmpty: false)
                  '))
                  { gridPos: { x: 0, y: 2, w: 24, h: 12 } },

            ],
}
