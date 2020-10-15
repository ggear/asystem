{
  graphs()::
  
    local grafana = import 'grafonnet/grafana.libsonnet';
    local dashboard = grafana.dashboard;
    local graph = grafana.graphPanel;
    local influxdb = grafana.influxdb;
    
    [

      graph.new(
        title='CPU Temperature',
        datasource='InfluxDB2',
        fill=0,
        format='short'
      ).addTarget(influxdb.target(query='
from(bucket: "hosts")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "sensors" and r["_field"] == "temp_input" and r["feature"] == "package_id_0")
  |> keep(columns: ["table", "_start", "_stop", "_time", "_value", "host"])
  |> aggregateWindow(every: v.windowPeriod, fn: max, createEmpty: false)
      ')) { gridPos: { x: 0, y: 0, w: 24, h: 10 } },

    ],
}
