{
  graphs()::
  
    local grafana = import 'grafonnet/grafana.libsonnet';
    local dashboard = grafana.dashboard;
    local graph = grafana.graphPanel;
    local influxdb = grafana.influxdb;
    
    [

      graph.new(
        title='Rain',
        datasource='InfluxDB2',
        fill=0,
        format='short'
      ).addTarget(influxdb.target(query='
from(bucket: "asystem")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["entity_id"] == "last_30_min_rain")
  |> keep(columns: ["table", "_start", "_stop", "_time", "_value", "friendly_name"])
  |> fill(usePrevious: true)
  |> aggregateWindow(every: v.windowPeriod, fn: max, createEmpty: false)
      ')) { gridPos: { x: 0, y: 0, w: 24, h: 10 } },

    ],
}
