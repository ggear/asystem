{
  graphs()::
  
    local grafana = import 'grafonnet/grafana.libsonnet';
    local dashboard = grafana.dashboard;
    local graph = grafana.graphPanel;
    local influxdb = grafana.influxdb;
    
    [

      graph.new(
        title='Power Consumption',
        datasource='InfluxDB',
        fill=0,
        format='short'
      ).addTarget(influxdb.target(query='
from(bucket: "asystem")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["entity_id"] == "office_power_consumption" or r["entity_id"] == "servers_power_consumption" or r["entity_id"] == "towelrails_power_consumption")
  |> rename(columns: {friendly_name: "name"})
  |> keep(columns: ["table", "_start", "_stop", "_time", "_value", "name"])
  |> fill(usePrevious: true)
  |> aggregateWindow(every: v.windowPeriod, fn: max, createEmpty: false)
        ')) { gridPos: { x: 0, y: 0, w: 24, h: 10 } },

    ],
}
