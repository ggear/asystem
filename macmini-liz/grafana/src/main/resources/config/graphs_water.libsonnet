{
  graphs()::
  
    local grafana = import 'grafonnet/grafana.libsonnet';
    local dashboard = grafana.dashboard;
    local graph = grafana.graphPanel;
    local influxdb = grafana.influxdb;
    
    [

      graph.new(title='Rain', datasource='InfluxDB', fill=0)
        .addTarget(influxdb.target(
          query='from(bucket: "asystem")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["entity_id"] == "last_30_min_rain")
  |> fill(usePrevious: true)
  |> group(columns: ["friendly_name"])
  |> aggregateWindow(every: v.windowPeriod, fn: mean, createEmpty: false)
  |> yield(name: "mean")'
        )) { gridPos: { x: 0, y: 0, w: 24, h: 10 } },

    ],
}
